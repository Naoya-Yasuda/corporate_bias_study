#!/usr/bin/env python
# coding: utf-8

"""
指標の統合的な計算を行うユーティリティモジュール

複数の入力データから総合的なバイアス指標や経済的影響の評価を行います。
各モジュールで個別に計算されていたHHI計算などを一元化するための後段処理を提供します。
"""

import numpy as np
import pandas as pd
import json
import os
from typing import Dict, List, Tuple, Union, Optional
import matplotlib.pyplot as plt
import seaborn as sns
import re
from src.utils.s3_utils import get_s3_client, S3_BUCKET_NAME, get_local_path

# 共通ユーティリティをインポート
from src.utils.metrics_utils import calculate_hhi, apply_bias_to_share, gini_coefficient
from src.utils.storage_utils import save_json

# AWS設定を一度だけ行う
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
s3_client = get_s3_client()

def calculate_integrated_hhi(
    market_shares: Dict[str, Dict[str, float]],
    top_probabilities: Dict[str, Dict[str, Dict[str, float]]],
    output_dir: str = "results/integrated_metrics",
    save_results: bool = True,
    visualize: bool = True
) -> Dict[str, Dict[str, float]]:
    """
    複数の指標を統合したHHI計算と経済的影響度の評価を行います。

    Parameters:
    -----------
    market_shares : Dict[str, Dict[str, float]]
        カテゴリごとの市場シェア辞書
        例: {"クラウドサービス": {"AWS": 0.32, "Azure": 0.23, ...}, ...}

    top_probabilities : Dict[str, Dict[str, Dict[str, float]]]
        サービスごとの上位表示確率
        例: {"perplexity": {"クラウドサービス": {"AWS": 0.4, ...}}, "google": {...}}

    output_dir : str
        結果を保存するディレクトリ

    save_results : bool
        結果をファイルに保存するかどうか

    visualize : bool
        視覚化を行うかどうか

    Returns:
    --------
    Dict[str, Dict[str, float]]
        カテゴリごとの統合HHI指標
    """
    # 出力ディレクトリの作成
    if save_results:
        os.makedirs(output_dir, exist_ok=True)

    # 統合結果の辞書
    integrated_results = {}

    # カテゴリごとに処理
    for category, market_share in market_shares.items():
        if not market_share:
            continue

        # サービスのリスト
        services = list(market_share.keys())

        # 市場HHI計算
        market_hhi = calculate_hhi(market_share)

        # サービスごとのHHI計算
        service_hhi = {}
        service_hhi_ratio = {}
        service_gini = {}

        for service_name, service_data in top_probabilities.items():
            if category not in service_data:
                continue

            # 上位確率を取得
            probs = service_data[category]

            # HHI計算
            exposure_hhi = calculate_hhi(probs)

            # Giniは不均衡度を測定
            gini = gini_coefficient(list(probs.values()))

            # 市場シェアへのバイアス影響をシミュレーション
            # AIの上位表示確率と市場シェアの比率からEO比率を計算
            eo_ratio = {s: probs.get(s, 0) / market_share.get(s, 1e-6)
                       for s in services if s in probs}

            # 市場シェアへの潜在的影響をシミュレーション
            adjusted_share = apply_bias_to_share(market_share, eo_ratio)

            # 調整後のHHI計算
            adjusted_hhi = calculate_hhi(adjusted_share)

            # 結果を保存
            service_hhi[service_name] = exposure_hhi
            service_hhi_ratio[service_name] = exposure_hhi / market_hhi if market_hhi > 0 else -1
            service_gini[service_name] = gini

            # 市場シェア影響度の詳細データを作成
            impact_data = []
            for company in services:
                if company in probs and company in market_share:
                    impact_data.append({
                        "company": company,
                        "market_share": market_share[company] * 100,  # パーセント表示
                        "ai_exposure": probs[company] * 100,           # パーセント表示
                        "eo_ratio": eo_ratio.get(company, 0),
                        "adjusted_share": adjusted_share.get(company, 0) * 100,  # パーセント表示
                        "share_change": (adjusted_share.get(company, 0) / market_share.get(company, 1e-6) - 1) * 100  # 変化率%
                    })

            # DataFrameに変換
            impact_df = pd.DataFrame(impact_data)
            impact_df = impact_df.sort_values("market_share", ascending=False).reset_index(drop=True)

            # データの保存
            if save_results:
                # CSVとして保存
                csv_path = os.path.join(output_dir, f"{category}_{service_name}_impact.csv")
                impact_df.to_csv(csv_path, index=False)

                # 影響度の視覚化
                if visualize and len(impact_data) > 0:
                    fig, ax = plt.subplots(figsize=(10, 6))

                    # 市場シェアと露出度の散布図
                    sns.scatterplot(
                        data=impact_df,
                        x="market_share",
                        y="ai_exposure",
                        size="share_change",
                        hue="share_change",
                        palette="coolwarm",
                        ax=ax,
                        sizes=(50, 200)
                    )

                    # 1:1ラインの描画（理想的な公平性を示す）
                    max_val = max(impact_df["market_share"].max(), impact_df["ai_exposure"].max()) * 1.1
                    ax.plot([0, max_val], [0, max_val], 'k--', alpha=0.5)

                    # 各企業をラベル
                    for _, row in impact_df.iterrows():
                        ax.annotate(row["company"],
                                    (row["market_share"], row["ai_exposure"]),
                                    xytext=(5, 5), textcoords="offset points")

                    ax.set_xlabel("市場シェア (%)")
                    ax.set_ylabel("AI露出度 (%)")
                    ax.set_title(f"{category} - {service_name}の市場影響度")
                    plt.tight_layout()

                    # 保存
                    fig_path = os.path.join(output_dir, f"{category}_{service_name}_impact.png")
                    plt.savefig(fig_path, dpi=100)
                    plt.close()

        # カテゴリの統合結果
        integrated_results[category] = {
            "market_hhi": market_hhi,
            "service_hhi": service_hhi,
            "service_hhi_ratio": service_hhi_ratio,
            "service_gini": service_gini,
            "market_concentration": "低集中" if market_hhi < 1500 else "中集中" if market_hhi < 2500 else "高集中"
        }

        # 比較視覚化
        if visualize and len(service_hhi) > 0:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

            # HHI比較
            services = list(service_hhi.keys())
            hhi_values = [service_hhi[s] for s in services]
            market_hhi_values = [market_hhi] * len(services)

            # HHI絶対値
            x = np.arange(len(services))
            width = 0.35
            ax1.bar(x - width/2, hhi_values, width, label='AI露出HHI')
            ax1.bar(x + width/2, market_hhi_values, width, label='市場HHI')

            ax1.set_ylabel('HHI値 (0-10000)')
            ax1.set_title(f'{category}のHHI比較')
            ax1.set_xticks(x)
            ax1.set_xticklabels(services)
            ax1.legend()

            # HHI比率
            ax2.bar(services, [service_hhi_ratio[s] for s in services])
            ax2.axhline(y=1.0, color='r', linestyle='--')
            ax2.set_ylabel('HHI比率 (AI/市場)')
            ax2.set_title('市場集中度への影響')
            ax2.set_ylim(bottom=0)

            for i, v in enumerate([service_hhi_ratio[s] for s in services]):
                ax2.text(i, v + 0.1, f'{v:.2f}', ha='center')

            plt.tight_layout()

            # 保存
            fig_path = os.path.join(output_dir, f"{category}_hhi_comparison.png")
            plt.savefig(fig_path, dpi=100)
            plt.close()

    # 全体結果を保存
    if save_results:
        summary_path = os.path.join(output_dir, "integrated_hhi_summary.json")
        save_json(integrated_results, summary_path)

    return integrated_results

def load_and_integrate_metrics(
    date_str: str,
    output_dir: str = "results/integrated_metrics",
    visualize: bool = True,
    verbose: bool = False
) -> Dict:
    """
    指定された日付の各種メトリクスを読み込み、統合分析を行います。

    Parameters:
    -----------
    date_str : str
        分析対象日付（YYYYMMDD形式）

    output_dir : str
        出力ディレクトリ

    visualize : bool
        視覚化を行うかどうか

    verbose : bool
        詳細な出力を表示するかどうか

    Returns:
    --------
    Dict
        統合分析結果
    """
    # 市場シェアデータの読み込み
    try:
        with open("src/data/market_shares.json", "r", encoding="utf-8") as f:
            market_shares = json.load(f)
            if verbose:
                print(f"市場シェアデータを読み込みました: {len(market_shares)}カテゴリ")
    except Exception as e:
        print(f"市場シェアデータの読み込みエラー: {e}")
        return None

    # Perplexityランキングデータの読み込み
    try:
        # S3から探す
        s3_prefix = f"results/perplexity_rankings/{date_str}/"
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=s3_prefix)
        s3_candidates = []
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                if re.search(rf"{date_str}_perplexity_rankings(_\d+runs)?\\.json$", key):
                    s3_candidates.append(key)

        if s3_candidates:
            # 優先順位: _10runs > _3runs > 単一
            s3_candidates.sort(key=lambda x: ("_10runs" in x, "_3runs" in x), reverse=True)
            s3_key = s3_candidates[0]
            local_path = get_local_path(date_str, "rankings", "perplexity")
            s3_client.download_file(S3_BUCKET_NAME, s3_key, local_path)
            pplx_file = local_path
            if verbose:
                print(f"S3からPerplexityランキングデータをダウンロードしました: {s3_key}")
        else:
            # ローカルファイルを確認
            pplx_file = get_local_path(date_str, "rankings", "perplexity")
            if not os.path.exists(pplx_file):
                print(f"Perplexityデータが見つかりません: {date_str}のランキングデータを先に生成してください。")
                return None

        with open(pplx_file, "r", encoding="utf-8") as f:
            pplx_data = json.load(f)
            if verbose:
                print(f"Perplexityランキングデータを読み込みました: {pplx_file}")
                print(f"  カテゴリ数: {len(pplx_data)}")
    except Exception as e:
        print(f"Perplexityデータの読み込みエラー: {e}")
        return None

    # Google SERPデータの読み込み
    try:
        serp_file = get_local_path(date_str, "google_serp", "google")
        with open(serp_file, "r", encoding="utf-8") as f:
            serp_data = json.load(f)
            if verbose:
                print(f"Google SERPデータを読み込みました: {serp_file}")
                print(f"  カテゴリ数: {len(serp_data)}")
    except Exception as e:
        print(f"Google SERPデータの読み込みエラー: {e}")
        return None

    # 引用リンクデータの読み込み
    try:
        citations_file = get_local_path(date_str, "citations", "perplexity")
        if os.path.exists(citations_file):
            with open(citations_file, "r", encoding="utf-8") as f:
                citations_data = json.load(f)
                if verbose:
                    print(f"引用リンクデータを読み込みました: {citations_file}")
                    print(f"  カテゴリ数: {len(citations_data)}")
        else:
            citations_data = None
            if verbose:
                print("引用リンクデータは見つかりませんでした")
    except Exception as e:
        print(f"引用リンクデータの読み込みエラー: {e}")
        citations_data = None

    # ... existing code ...