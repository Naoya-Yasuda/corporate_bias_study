#!/usr/bin/env python
# coding: utf-8

"""
ランキング分析モジュール

ランキングデータを分析し、様々な公平性指標を計算します。
特に露出度（Exposure）、機会均等性（Equal Opportunity）、ランキング安定性などの
指標を計算します。
"""

import os
import json
import collections
import csv
import datetime
import argparse
import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import trange, tqdm
from dotenv import load_dotenv
import boto3
from src.utils.storage_utils import save_json, get_s3_client, ensure_dir, get_today_str, load_json
from src.utils.rank_utils import compute_tau, rbo
from src.utils.metrics_utils import gini_coefficient, statistical_parity_gap, equal_opportunity_ratio

# ドメイン関連の機能
from src.utils import extract_domain
from src.categories import get_categories

import re
import unicodedata

# .envファイルから環境変数を読み込み
load_dotenv()

# -----------------------------
# 0. パラメータ
# -----------------------------
TOP_K        = 5                       # 上位 k 位を対象とする
EXPOSURE_WTS = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1}      # 1位=5pt, 2位=4pt, 3位=3pt, 4位=2pt, 5位=1pt

# 環境変数から認証情報を取得
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# カテゴリ別市場シェアデータの読み込み
def load_market_shares():
    # デフォルトの市場シェアデータ（ファイル用）
    default_market_shares = {
        "クラウドサービス": {
            "AWS": 0.32, "Azure": 0.23, "Google Cloud": 0.10,
            "IBM Cloud": 0.04, "Oracle Cloud": 0.03
        },
        "検索エンジン": {
            "Google": 0.85, "Bing": 0.07, "Yahoo! Japan": 0.03, "Baidu": 0.01,
            "DuckDuckGo": 0.01
        }
    }

    # JSONファイルからの読み込みを試行
    market_shares_path = "src/data/market_shares.json"
    try:
        if os.path.exists(market_shares_path):
            with open(market_shares_path, "r", encoding="utf-8") as f:
                market_shares = json.load(f)
                print(f"市場シェアデータを {market_shares_path} から読み込みました")
                return market_shares
    except Exception as e:
        print(f"市場シェアデータの読み込みに失敗しました: {e}")

    print("デフォルトの市場シェアデータを使用します")
    return default_market_shares

# 市場シェアデータのキャッシュ
_MARKET_SHARES_CACHE = None

def get_market_shares():
    """市場シェアデータを取得（キャッシュ付き）"""
    global _MARKET_SHARES_CACHE
    if _MARKET_SHARES_CACHE is None:
        _MARKET_SHARES_CACHE = load_market_shares()
    return _MARKET_SHARES_CACHE

# -----------------------------
# S3操作ユーティリティ
# -----------------------------
def download_from_s3(s3_key):
    """S3からファイルをダウンロードして内容を返す"""
    s3_client = get_s3_client()

    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )

        content = response['Body'].read().decode('utf-8')
        return content
    except Exception as e:
        print(f"S3ダウンロードエラー ({s3_key}): {e}")
        return None

# -----------------------------
# 1. 上位出現確率と露出度
# -----------------------------
def topk_probabilities(runs: list[list[str]], k: int = TOP_K):
    """各ランが上位k位内に現れる確率を計算"""
    counter = collections.Counter()
    for lst in runs:
        counter.update(lst[:k])
    n_runs = len(runs)
    return {c: counter[c] / n_runs for c in counter}

def exposure_index(runs: list[list[str]], wts=EXPOSURE_WTS):
    """各ランクの露出度指標を計算（ランク重み付き）"""
    expo = collections.Counter()
    for lst in runs:
        for rank, name in enumerate(lst, 1):
            if rank in wts:
                expo[name] += wts[rank]
    total = sum(expo.values()) or 1
    return {c: expo[c] / total for c in expo}

def rank_distribution(runs: list[list[str]], max_rank: int = 5):
    """各ランクの順位分布を計算"""
    # 全てのサービス名を抽出
    all_services = set()
    for run in runs:
        all_services.update(run[:max_rank])

    # 結果を格納する辞書を初期化
    dist = {service: [0.0] * max_rank for service in all_services}

    # 各ランクの順位分布を計算
    n_runs = len(runs)
    for run in runs:
        for rank, service in enumerate(run[:max_rank]):
            if rank < max_rank:
                dist[service][rank] += 1 / n_runs

    return dist

# -----------------------------
# 2. 指標 (SP、EO、Correlation、Gini)
# -----------------------------
def kendall_tau_correlation(ranked_runs, market_share):
    """Kendallのτ順位相関係数（ランキングと市場シェアの相関性）"""
    # 平均ランキングを計算
    rank_counts = collections.defaultdict(list)
    for run in ranked_runs:
        for rank, service in enumerate(run):
            rank_counts[service].append(rank)

    avg_ranks = {service: np.mean(ranks) for service, ranks in rank_counts.items()}

    # 共通のサービスのみを抽出
    common_services = set(avg_ranks.keys()) & set(market_share.keys())
    if len(common_services) < 2:
        return 0.0  # 相関を計算するには少なくとも2つのサービスが必要

    # 順位と市場シェアのペアを作成
    x = [avg_ranks[service] for service in common_services]
    y = [-market_share[service] for service in common_services]  # シェアが大きいほど順位が上位なので負号

    # Kendallのτ相関係数を計算
    tau, _ = stats.kendalltau(x, y)
    return tau

def calculate_ranking_stability(rankings):
    """
    ランキング結果の安定性を計算

    Parameters
    ----------
    rankings : list[list[str]]
        複数回のランキング結果

    Returns
    -------
    dict
        stability_score: 平均安定性スコア（-1〜1）
        pairwise_stability: ペア間の安定性スコア
        stability_matrix: 全ペア間の安定性行列
    """
    if len(rankings) <= 1:
        return {
            "stability_score": 1.0,
            "pairwise_stability": [],
            "stability_matrix": None
        }

    # 全てのランキングに含まれるサービス名を収集
    all_services = set()
    for ranking in rankings:
        all_services.update(ranking)

    # 各ランキングをサービス→順位のマップに変換
    rank_maps = []
    for ranking in rankings:
        rank_map = {service: idx for idx, service in enumerate(ranking)}
        # ランキングに含まれないサービスには大きい順位を仮定
        for service in all_services:
            if service not in rank_map:
                rank_map[service] = len(ranking)
        rank_maps.append(rank_map)

    # ペア間の安定性を計算
    n = len(rankings)
    stability_matrix = np.ones((n, n))
    pairwise_stability = []

    for i in range(n):
        for j in range(i+1, n):
            # 共通のサービス名のみを抽出
            common_services = set(rank_maps[i].keys()) & set(rank_maps[j].keys())
            if len(common_services) < 2:
                tau = 0.0  # 共通サービスが1個以下の場合相関を計算できない
            else:
                ranks_i = [rank_maps[i][s] for s in common_services]
                ranks_j = [rank_maps[j][s] for s in common_services]
                tau, _ = stats.kendalltau(ranks_i, ranks_j)
                if np.isnan(tau):  # NANの場合0として扱う
                    tau = 0.0

            stability_matrix[i, j] = tau
            stability_matrix[j, i] = tau
            pairwise_stability.append(tau)

    # 平均安定性スコア
    avg_stability = np.mean(pairwise_stability) if pairwise_stability else 1.0

    return {
        "stability_score": avg_stability,
        "pairwise_stability": pairwise_stability,
        "stability_matrix": stability_matrix
    }

def interpret_stability(score):
    """安定性スコアの解釈"""
    if score >= 0.8:
        return "非常に安定"
    elif score >= 0.6:
        return "安定"
    elif score >= 0.4:
        return "やや安定"
    elif score >= 0.2:
        return "やや不安定"
    elif score >= 0:
        return "不安定"
    else:
        return "非常に不安定（逆相関）"

# -----------------------------
# 3. 集計・保存
# -----------------------------
def compute_rank_metrics(category: str,
                         ranked_runs: list[list[str]],
                         market_share: dict[str, float] = None):
    """ランキング結果から各指標を計算"""
    # サービスの一覧を抽出
    services = set()
    for run in ranked_runs:
        services.update(run)

    # 市場シェアが指定されない場合は均等配分
    if market_share is None:
        market_share = {service: 1.0 / len(services) for service in services}

    # 上位確率と露出度指標を計算
    top_probs = topk_probabilities(ranked_runs, TOP_K)
    expo_idx = exposure_index(ranked_runs)
    rank_dist = rank_distribution(ranked_runs)

    # 指標を計算
    sp_gap = statistical_parity_gap(top_probs)
    eo_dict, eo_gap = equal_opportunity_ratio(top_probs, market_share)
    ktau = kendall_tau_correlation(ranked_runs, market_share)

    # 露出度のジニ係数を計算
    gini = gini_coefficient(list(expo_idx.values()))

    # 詳細データフレームを作成
    df = pd.DataFrame({
        "service": list(services),
        "top_k_prob": [top_probs.get(s, 0.0) for s in services],
        "exposure_idx": [expo_idx.get(s, 0.0) for s in services],
        "market_share": [market_share.get(s, 0.0) for s in services],
        "eo_ratio": [eo_dict.get(s, 0.0) for s in services],
    })

    # ランク分布を追加
    for rank in range(1, min(TOP_K, len(ranked_runs[0]) if ranked_runs else 1) + 1):
        df[f"rank_{rank}_prob"] = [rank_dist.get(s, [0.0] * TOP_K)[rank - 1] for s in services]

    # 結果をソート
    df = df.sort_values("exposure_idx", ascending=False).reset_index(drop=True)

    # 安定性を計算
    stability_data = calculate_ranking_stability(ranked_runs)
    stability_score = stability_data["stability_score"]
    stability_interp = interpret_stability(stability_score)

    # 集計状況を作成
    summary = {
        "category": category,
        "n_runs": len(ranked_runs),
        "n_services": len(services),
        "SP_gap": sp_gap,
        "EO_gap": eo_gap,
        "kendall_tau": ktau,
        "gini_coef": gini,
        "market_share": market_share,
        "exposure_idx": expo_idx,
        "stability_score": stability_score,
        "stability_interpretation": stability_interp
    }

    return df, summary

def plot_rank_distribution(df: pd.DataFrame, category: str, output_dir: str):
    """順位分布をヒートマップでプロット"""
    # 順位列を抽出
    rank_cols = [col for col in df.columns if col.startswith("rank_")]
    if not rank_cols:
        return None

    # プロット用のデータを準備
    plot_df = df[["service"] + rank_cols].copy()
    plot_df = plot_df.set_index("service")

    # 列名をわかりやすく変更
    plot_df.columns = [f"{int(col.split('_')[1])}位" for col in rank_cols]

    # ヒートマップ作成
    plt.figure(figsize=(8, max(5, len(df) * 0.4)))
    sns.heatmap(plot_df, annot=True, cmap="YlGnBu", vmin=0, vmax=1, fmt=".2f")
    plt.title(f"{category}のランキング分布")
    plt.tight_layout()

    # 保存
    file_name = f"{category}_rank_heatmap.png"
    save_path = os.path.join(output_dir, file_name)
    plt.savefig(save_path, dpi=100)
    plt.close()

    return file_name

def plot_exposure_vs_market(df: pd.DataFrame, category: str, output_dir: str):
    """露出度と市場シェアの散布図をプロット"""
    plt.figure(figsize=(8, 6))

    # 対角線（完全公平）
    max_val = max(df["exposure_idx"].max(), df["market_share"].max()) * 1.1
    plt.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label="Perfect fairness")

    # 散布図
    sc = plt.scatter(df["market_share"], df["exposure_idx"], s=80, alpha=0.7)

    # サービス名のラベル
    for i, row in df.iterrows():
        plt.annotate(row["service"], (row["market_share"], row["exposure_idx"]),
                    xytext=(5, 5), textcoords="offset points")

    plt.xlabel("市場シェア")
    plt.ylabel("AI露出度指標")
    plt.title(f"{category}の市場シェアとAI露出度の関係")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    # 保存
    file_name = f"{category}_exposure_market.png"
    save_path = os.path.join(output_dir, file_name)
    plt.savefig(save_path, dpi=100)
    plt.close()

    return file_name

def plot_stability_matrix(stability_matrix, category, output_dir):
    """安定性行列のヒートマップをプロット"""
    if stability_matrix is None or len(stability_matrix) <= 1:
        return None

    plt.figure(figsize=(8, 6))
    sns.heatmap(stability_matrix, annot=True, cmap="YlGnBu", vmin=-1, vmax=1,
                fmt=".2f", square=True)
    plt.title(f"{category}のランキング安定性行列")
    plt.xlabel("実行回数")
    plt.ylabel("実行回数")
    plt.tight_layout()

    # 保存
    file_name = f"{category}_stability_matrix.png"
    save_path = os.path.join(output_dir, file_name)
    plt.savefig(save_path, dpi=100)
    plt.close()

    return file_name

# -----------------------------
# 4. S3からデータを取得して分析
# -----------------------------
def analyze_s3_rankings(date_str=None, api_type="perplexity", output_dir=None, upload_results=True, verbose=False):
    """
    S3から指定日のランキングデータを取得して分析

    Parameters
    ----------
    date_str : str, optional
        YYYYMMDD形式の日付文字列、指定しない場合は最新日付
    api_type : str, optional
        "perplexity" または "openai"
    output_dir : str, optional
        出力ディレクトリ、指定しない場合は "results/perplexity_analysis/{date_str}"
    upload_results : bool, optional
        分析結果をS3にアップロードするか
    verbose : bool, optional
        詳細なログ出力を行うか

    Returns
    -------
    pd.DataFrame
        全カテゴリの集計指標
    """
    # 詳細ログの設定
    if verbose:
        import logging
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.info(f"詳細ログモードでランキング分析を実行中: {api_type}, 日付: {date_str}")

    # 日付が指定されない場合は今日の日付を使用
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")

    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = f"results/perplexity_analysis/{date_str}"

    os.makedirs(output_dir, exist_ok=True)
    if verbose:
        logging.info(f"出力ディレクトリを作成: {output_dir}")

    # S3からランキングデータを取得
    s3_key, content = get_latest_file(date_str, "rankings", api_type)

    if not content:
        print(f"⚠️  {date_str}のランキングデータが見つかりません")
        if verbose:
            logging.error(f"ランキングデータが見つかりません: {s3_key}")
        return None

    print(f"📥 S3からデータを取得: {s3_key}")
    if verbose:
        logging.info(f"S3からデータを取得: {s3_key}, サイズ: {len(content)}バイト")

    # JSONをパース
    try:
        ranked_json = json.loads(content)
        if verbose:
            logging.info(f"JSONをパース: {len(ranked_json)}個のカテゴリを検出")
    except json.JSONDecodeError as e:
        print(f"⚠️  JSONパースエラー: {e}")
        if verbose:
            logging.error(f"JSONパースエラー: {e}")
        return None

    print(f"🔍 {len(ranked_json)}個のカテゴリを分析します")

    # カテゴリごとの分析
    summaries = []
    uploaded_files = []

    for category, data in ranked_json.items():
        print(f"- {category} 分析中...")
        if verbose:
            logging.info(f"カテゴリの分析開始: {category}")

        # カテゴリデータの形式を確認（ランキング結果を取得）
        runs = []
        if isinstance(data, dict):
            # サブカテゴリの処理
            for subcategory, subdata in data.items():
                if isinstance(subdata, dict):
                    if "all_rankings" in subdata:
                        # 複数回実行結果の場合（recommended）
                        runs.extend(subdata["all_rankings"])
                        if verbose:
                            logging.info(f"複数回実行データを検出: {len(subdata['all_rankings'])}回分のランキング")
                    elif "ranking" in subdata:
                        # 単一実行結果の場合
                        runs.append(subdata["ranking"])
                        if verbose:
                            logging.info("単一実行データを検出")
                    elif "search_result_companies" in subdata:
                        # 新しい形式（search_result_companiesを使用）
                        runs.append(subdata["search_result_companies"])
                        if verbose:
                            logging.info("search_result_companiesデータを検出")
                    else:
                        print(f"  ⚠️  不明な辞書形式: {list(subdata.keys())}")
                        if verbose:
                            logging.warning(f"不明な辞書形式: {list(subdata.keys())}")
                        continue
                elif isinstance(subdata, list):
                    # ランキングのリストの場合
                    runs.extend(subdata)
                    if verbose:
                        logging.info(f"ランキングリストを検出: {len(subdata)}項目")
                else:
                    print(f"  ⚠️  不明なデータ形式: {type(subdata)}")
                    if verbose:
                        logging.warning(f"不明なデータ形式: {type(subdata)}")
                    continue

            if not runs:
                print(f"  ⚠️  有効なランキングデータが見つかりません")
                if verbose:
                    logging.warning("有効なランキングデータが見つかりません")
                continue
        elif isinstance(data, list):
            # ランキングのリストの場合
            runs = data
            if verbose:
                logging.info(f"ランキングリストを検出: {len(runs)}項目")
        else:
            print(f"  ⚠️  不明なデータ形式: {type(data)}")
            if verbose:
                logging.warning(f"不明なデータ形式: {type(data)}")
            continue

        # カテゴリに応じた市場シェアを選択
        market_share = get_market_shares().get(category, None)
        if verbose:
            if market_share:
                logging.info(f"市場シェアデータを使用: {len(market_share)}企業")
            else:
                logging.warning(f"'{category}'の市場シェアデータがありません")

        # 指標計算
        df_metrics, summary = compute_rank_metrics(category, runs, market_share)
        if verbose:
            logging.info(f"指標計算完了: {len(df_metrics)}企業の指標を生成")

        # 結果を保存
        csv_path = os.path.join(output_dir, f"{category}_rank_metrics.csv")
        df_metrics.to_csv(csv_path, index=False)
        uploaded_files.append((csv_path, f"results/perplexity_analysis/{date_str}/{category}_rank_metrics.csv", "text/csv"))
        if verbose:
            logging.info(f"CSVを保存: {csv_path}")

        # 可視化
        heatmap_file = plot_rank_distribution(df_metrics, category, output_dir)
        if heatmap_file:
            uploaded_files.append((
                os.path.join(output_dir, heatmap_file),
                f"results/perplexity_analysis/{date_str}/{heatmap_file}",
                "image/png"
            ))
            if verbose:
                logging.info(f"ヒートマップを生成: {heatmap_file}")

        scatter_file = plot_exposure_vs_market(df_metrics, category, output_dir)
        if scatter_file:
            uploaded_files.append((
                os.path.join(output_dir, scatter_file),
                f"results/perplexity_analysis/{date_str}/{scatter_file}",
                "image/png"
            ))
            if verbose:
                logging.info(f"散布図を生成: {scatter_file}")

        # 安定性行列のプロット（2回以上実行した場合のみ）
        if len(runs) > 1:
            stability_data = calculate_ranking_stability(runs)
            stability_matrix = stability_data["stability_matrix"]
            stability_file = plot_stability_matrix(stability_matrix, category, output_dir)
            if stability_file:
                uploaded_files.append((
                    os.path.join(output_dir, stability_file),
                    f"results/perplexity_analysis/{date_str}/{stability_file}",
                    "image/png"
                ))
                if verbose:
                    logging.info(f"安定性行列を生成: {stability_file}")

        # 集計を収集
        summaries.append(summary)

    # 集計をデータフレームに変換して保存
    summary_df = pd.DataFrame(summaries)
    summary_path = os.path.join(output_dir, f"{date_str}_{api_type}_rank_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    uploaded_files.append((
        summary_path,
        f"results/perplexity_analysis/{date_str}/{date_str}_{api_type}_rank_summary.csv",
        "text/csv"
    ))
    if verbose:
        logging.info(f"集計を保存: {summary_path}, {len(summaries)}カテゴリ")

    # S3へのアップロード
    if upload_results and AWS_ACCESS_KEY and AWS_SECRET_KEY:
        print("📤 分析結果をS3にアップロード中...")
        if verbose:
            logging.info("S3へのアップロード開始")
        for local_path, s3_key, content_type in uploaded_files:
            if upload_to_s3(local_path, s3_key, content_type):
                print(f"  ✅ {s3_key}")
                if verbose:
                    logging.info(f"S3アップロード成功: {s3_key}")
            else:
                print(f"  ❌ {s3_key}")
                if verbose:
                    logging.error(f"S3アップロード失敗: {s3_key}")

    print(f"✅ ランキング分析が完了しました: {output_dir}")
    if verbose:
        logging.info(f"ランキング分析完了: {len(summary_df)}カテゴリ")

    # 集計を表示
    print("\n=== ランキング分析の集計 ===")
    display_cols = ['category', 'SP_gap', 'EO_gap', 'kendall_tau', 'gini_coef', 'stability_score', 'stability_interpretation']
    display_cols = [col for col in display_cols if col in summary_df.columns]
    print(summary_df[display_cols])

    return summary_df

def get_exposure_market_data(category):
    """露出度と市場シェアのデータを取得"""
    try:
        # S3から最新のランキングファイルを取得
        s3_key, content = get_latest_file(get_today_str(), "rankings", "perplexity")
        if not content:
            print(f"ランキングデータが見つかりません。")
            return None

        # ランキングデータを読み込み
        rankings_data = json.loads(content)
        if category not in rankings_data:
            print(f"カテゴリ '{category}' のランキングデータが見つかりません。")
            return None

        # ランキングデータを取得
        runs = rankings_data[category]
        if not runs:
            print(f"カテゴリ '{category}' のランキングデータが空です。")
            return None

        # 市場シェアデータを取得
        market_share = get_market_shares().get(category)
        if not market_share:
            print(f"カテゴリ '{category}' の市場シェアデータが見つかりません。")
            return None

        # メトリクスを計算
        df_metrics, _ = compute_rank_metrics(category, runs, market_share)

        # 日付を追加
        df_metrics["date"] = get_today_str()

        return df_metrics

    except Exception as e:
        print(f"データの取得中にエラーが発生しました: {str(e)}")
        return None

def get_timeseries_exposure_market_data(category):
    """指定カテゴリの露出度と市場シェアの時系列データをS3から収集"""
    from src.utils.s3_utils import list_s3_files
    dfs = []
    # ランキングデータのS3キー一覧を取得
    files = list_s3_files("results/rankings/")
    for key in files:
        # 日付抽出
        date_match = re.search(r"rankings/([0-9]{8})_", key)
        if not date_match:
            continue
        date_str = date_match.group(1)
        s3_key, content = get_latest_file(date_str, "rankings", "perplexity")
        if not content:
            print(f"ファイルが見つかりません: {s3_key}")
            continue
        try:
            rankings_data = json.loads(content)
            if category not in rankings_data:
                print(f"カテゴリ '{category}' のランキングデータが見つかりません。")
                continue
            runs = rankings_data[category]
            market_share = get_market_shares().get(category)
            if not runs or not market_share:
                print(f"カテゴリ '{category}' のランキングデータが空です。")
                continue
            df_metrics, _ = compute_rank_metrics(category, runs, market_share)
            df_metrics["date"] = date_str
            dfs.append(df_metrics)
        except Exception as e:
            print(f"データの取得中にエラーが発生しました: {str(e)}")
            continue
    if dfs:
        return pd.concat(dfs, ignore_index=True)
    return None

# -----------------------------
# 5. CLI エントリーポイント
# -----------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='S3からランキングデータを取得して分析')
    parser.add_argument('--date', help='分析する日付（YYYYMMDD形式、デフォルト: 今日）')
    parser.add_argument('--api', default='perplexity', choices=['perplexity', 'openai'],
                        help='APIタイプ（デフォルト: perplexity）')
    parser.add_argument('--output', help='出力ディレクトリ（デフォルト: results/perplexity_analysis/YYYYMMDD）')
    parser.add_argument('--no-upload', action='store_true', help='S3への結果アップロードを無効化')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を行う')
    parser.add_argument('input_file', nargs='?', help='ローカルJSONファイルから直接分析する場合のパス')

    args = parser.parse_args()

    if args.input_file:
        # ローカルファイルからの分析
        with open(args.input_file, 'r', encoding='utf-8') as f:
            ranked_json = json.load(f)

        # 出力ディレクトリの設定
        if args.output is None:
            today = datetime.datetime.now().strftime("%Y%m%d")
            output_dir = f"results/perplexity_analysis/{today}"
        else:
            output_dir = args.output

        os.makedirs(output_dir, exist_ok=True)

        # 各カテゴリの分析と結果保存
        summaries = []
        for category, runs in ranked_json.items():
            market_share = get_market_shares().get(category, None)
            df_metrics, summary = compute_rank_metrics(category, runs, market_share)
            df_metrics.to_csv(f"{output_dir}/{category}_rank_metrics.csv", index=False)
            plot_rank_distribution(df_metrics, category, output_dir)
            plot_exposure_vs_market(df_metrics, category, output_dir)
            summaries.append(summary)

        pd.DataFrame(summaries).to_csv(f"{output_dir}/_rank_summary.csv", index=False)
        print(f"✅ ランキング分析が完了しました: {output_dir}")
    else:
        # S3からの分析
        analyze_s3_rankings(
            date_str=args.date,
            api_type=args.api,
            output_dir=args.output,
            upload_results=not args.no_upload,
            verbose=args.verbose
        )