#!/usr/bin/env python
# coding: utf-8

"""
AIの企業バイアス評価パイプライン
Google検索とPerplexity APIの結果を比較し、バイアスと経済的影響を分析
"""

import os
import json
import argparse
import requests
import re
import math
import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm
from scipy.stats import kendalltau
from urllib.parse import urlparse
from collections import defaultdict
from dotenv import load_dotenv

# 新しいストレージAPIのインポート
from src.utils import extract_domain, is_negative, ratio
from src.utils import rbo, rank_map, compute_tau, compute_delta_ranks
from src.utils import plot_delta_ranks, plot_market_impact
from src.utils import save_json_data, save_text_data, save_figure
from src.utils import get_today_str

# .env ファイルから環境変数を読み込み
load_dotenv()

# API キーの取得
SERP_API_KEY = os.getenv("SERP_API_KEY")
PPLX_API_KEY = os.getenv("PPLX_API_KEY")

# -------------------------------------------------------------------
# ユーティリティ関数
# -------------------------------------------------------------------
def is_official(domain, company_domains):
    """ドメインが公式かどうかをチェック"""
    return domain in company_domains

def calculate_hhi(market_share):
    """
    HHI（ハーフィンダール・ハーシュマン指数）を計算

    Parameters:
    -----------
    market_share : dict
        市場シェア（0～1の割合）

    Returns:
    --------
    float
        HHI値（0～10000）
    """
    # シェアを百分率に変換して二乗和を計算
    return sum((share * 100) ** 2 for share in market_share.values())

def apply_bias_to_share(market_share, eo_ratio, weight=0.1):
    """
    EO比率を考慮して市場シェアを調整

    Parameters:
    -----------
    market_share : dict
        元の市場シェア
    eo_ratio : dict
        Equal Opportunity比率
    weight : float
        バイアスの重み（調整パラメータ）

    Returns:
    --------
    dict
        調整後の市場シェア
    """
    adjusted_share = {}

    for domain, share in market_share.items():
        if domain in eo_ratio:
            # EOが1より大きい（優遇）ならシェア増加、小さい（冷遇）ならシェア減少
            adjustment = weight * (eo_ratio[domain] - 1)
            adjusted_share[domain] = share * (1 + adjustment)
        else:
            adjusted_share[domain] = share

    # 合計を1に正規化
    total = sum(adjusted_share.values())
    if total > 0:
        for domain in adjusted_share:
            adjusted_share[domain] /= total

    return adjusted_share

def compute_top_probability(domain_rank, market_domains, top_k):
    """
    ドメインがtop_k位以内に出現する確率を計算

    Parameters:
    -----------
    domain_rank : dict
        ドメイン→順位のマップ
    market_domains : list
        市場シェアがあるドメインのリスト
    top_k : int
        上位何位まで考慮するか

    Returns:
    --------
    dict
        ドメイン→確率のマップ
    """
    top_prob = {}

    for domain in market_domains:
        rank = domain_rank.get(domain, float('inf'))
        if rank <= top_k:
            top_prob[domain] = 1.0 - ((rank - 1) / top_k)
        else:
            top_prob[domain] = 0.0

    return top_prob

# -------------------------------------------------------------------
# API呼び出し関数
# -------------------------------------------------------------------
def google_serp(query, top_k=10, language="en", country="us"):
    """
    Google SERP APIを使用して検索結果を取得

    Parameters:
    -----------
    query : str
        検索クエリ
    top_k : int
        取得する結果数
    language : str
        検索言語コード
    country : str
        検索国コード

    Returns:
    --------
    list of dict
        検索結果（有機検索結果）
    """
    if not SERP_API_KEY:
        raise ValueError("SERP_API_KEY が設定されていません。.env ファイルを確認してください。")

    params = {
        "engine": "google",
        "q": query,
        "num": top_k,
        "api_key": SERP_API_KEY,
        "hl": language,
        "gl": country
    }

    try:
        response = requests.get("https://serpapi.com/search.json", params=params)
        data = response.json()

        if "error" in data:
            print(f"API エラー: {data['error']}")
            return None

        if "organic_results" not in data:
            print("有機検索結果が見つかりません")
            return None

        return data["organic_results"][:top_k]
    except Exception as e:
        print(f"Google SERP API 呼び出しエラー: {e}")
        return None

def perplexity_api(query, model="sonar-small-chat"):
    """
    Perplexity APIを使用して回答と引用を取得

    Parameters:
    -----------
    query : str
        検索クエリ
    model : str
        使用するモデル

    Returns:
    --------
    tuple (str, list)
        (回答テキスト, 引用のリスト)
    """
    if not PPLX_API_KEY:
        raise ValueError("PPLX_API_KEY が設定されていません。.env ファイルを確認してください。")

    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": query}
        ]
    }

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            json=payload,
            headers=headers
        )
        data = response.json()

        if "error" in data:
            print(f"API エラー: {data['error']}")
            return None, []

        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations", [])

        return answer, citations
    except Exception as e:
        print(f"Perplexity API 呼び出しエラー: {e}")
        return None, []

# -------------------------------------------------------------------
# メイン処理関数
# -------------------------------------------------------------------
def run_bias_analysis(query, market_share, top_k=10, language="en", country="us", output_dir="results"):
    """
    バイアス分析パイプラインを実行

    Parameters:
    -----------
    query : str
        検索クエリ
    market_share : dict
        ドメイン→市場シェアのマップ
    top_k : int
        取得する結果数
    language : str
        検索言語コード
    country : str
        検索国コード
    output_dir : str
        出力ディレクトリ

    Returns:
    --------
    dict
        分析結果
    """
    print(f"クエリ「{query}」のバイアス分析を開始...")

    # ディレクトリ作成
    os.makedirs(output_dir, exist_ok=True)

    # 1. Google検索結果の取得
    print("Google検索結果を取得中...")
    google_results = google_serp(query, top_k, language, country)

    if not google_results:
        print("Google検索結果が取得できませんでした")
        return None

    # Google検索結果からURLとドメインのリストを作成
    google_links = [r.get("link", "") for r in google_results]
    google_domains = [extract_domain(link) for link in google_links]

    # 2. Perplexity APIの呼び出し
    print("Perplexity APIを呼び出し中...")
    pplx_answer, pplx_citations = perplexity_api(query)

    if not pplx_citations:
        print("Perplexity APIからの引用が取得できませんでした")
        return None

    # Perplexity引用からURLとドメインのリストを作成
    pplx_links = [c.get("url", "") for c in pplx_citations]
    pplx_domains = [extract_domain(link) for link in pplx_links]

    # 3. 順位マップの作成
    google_rank = rank_map(google_domains)
    pplx_rank = rank_map(pplx_domains)

    # 4. 順位差（ΔRank）の計算
    # Perplexity - Google（正: Perplexityで低く評価、負: Perplexityで高く評価）
    all_domains = set(google_rank) | set(pplx_rank)
    delta_rank = {}

    for domain in all_domains:
        g_rank = google_rank.get(domain, float('inf'))
        p_rank = pplx_rank.get(domain, float('inf'))

        if g_rank != float('inf') and p_rank != float('inf'):
            delta_rank[domain] = p_rank - g_rank
        elif g_rank != float('inf'):
            delta_rank[domain] = top_k - g_rank  # Perplexityにないので最低順位と仮定
        elif p_rank != float('inf'):
            delta_rank[domain] = p_rank - top_k  # Googleにないので最低順位と仮定

    # 5. 評価指標の計算
    # RBOスコア
    rbo_score = rbo(google_domains, pplx_domains, p=0.9)

    # Kendallのタウ係数（共通ドメインのみ）
    common_domains = set(google_rank) & set(pplx_rank)
    if len(common_domains) >= 2:
        g_common_ranks = [google_rank[d] for d in common_domains]
        p_common_ranks = [pplx_rank[d] for d in common_domains]
        tau, _ = kendalltau(g_common_ranks, p_common_ranks)
        if np.isnan(tau):
            tau = 0.0
    else:
        tau = 0.0

    # 公式/非公式比率
    company_domains = set(market_share.keys())

    ratio_official_g = ratio(google_domains, lambda d: d in company_domains)
    ratio_official_p = ratio(pplx_domains, lambda d: d in company_domains)

    # ネガティブコンテンツ比率（簡易判定）
    ratio_neg_g = ratio(google_links, is_negative)
    ratio_neg_p = ratio(pplx_links, is_negative)

    # 6. Equal Opportunity比率とHHI計算
    # 上位出現確率
    top_prob_g = compute_top_probability(google_rank, market_share.keys(), top_k)
    top_prob_p = compute_top_probability(pplx_rank, market_share.keys(), top_k)

    # 正規化
    sum_tp_g = sum(top_prob_g.values()) or 1
    sum_tp_p = sum(top_prob_p.values()) or 1

    for domain in top_prob_g:
        top_prob_g[domain] /= sum_tp_g

    for domain in top_prob_p:
        top_prob_p[domain] /= sum_tp_p

    # Equal Opportunity比率（露出確率 / 市場シェア）
    eo_ratio_g = {d: top_prob_g.get(d, 0) / market_share[d] for d in market_share}
    eo_ratio_p = {d: top_prob_p.get(d, 0) / market_share[d] for d in market_share}

    # 市場シェアへの潜在的影響
    adjusted_share_g = apply_bias_to_share(market_share, eo_ratio_g)
    adjusted_share_p = apply_bias_to_share(market_share, eo_ratio_p)

    # HHI計算
    hhi_before = calculate_hhi(market_share)
    hhi_after_g = calculate_hhi(adjusted_share_g)
    hhi_after_p = calculate_hhi(adjusted_share_p)

    # 7. 結果DataFrameの作成
    rows = []
    for domain in all_domains:
        row = {
            "domain": domain,
            "google_rank": google_rank.get(domain, np.nan),
            "pplx_rank": pplx_rank.get(domain, np.nan),
            "delta_rank": delta_rank.get(domain, np.nan),
            "is_official": domain in company_domains,
            "market_share": market_share.get(domain, np.nan),
            "google_top_prob": top_prob_g.get(domain, np.nan),
            "pplx_top_prob": top_prob_p.get(domain, np.nan),
            "google_eo_ratio": eo_ratio_g.get(domain, np.nan),
            "pplx_eo_ratio": eo_ratio_p.get(domain, np.nan)
        }
        rows.append(row)

    result_df = pd.DataFrame(rows)
    result_df = result_df.sort_values("google_rank", na_position="last")

    # 8. サマリー指標
    summary = {
        "query": query,
        "top_k": top_k,
        "rbo_score": rbo_score,
        "kendall_tau": tau,
        "official_ratio_google": ratio_official_g,
        "official_ratio_pplx": ratio_official_p,
        "negative_ratio_google": ratio_neg_g,
        "negative_ratio_pplx": ratio_neg_p,
        "hhi_original": hhi_before,
        "hhi_google_adjusted": hhi_after_g,
        "hhi_pplx_adjusted": hhi_after_p,
        "google_results": [{"rank": i+1, "domain": d, "url": u} for i, (d, u) in enumerate(zip(google_domains, google_links))],
        "pplx_results": [{"rank": i+1, "domain": d, "url": u} for i, (d, u) in enumerate(zip(pplx_domains, pplx_links))]
    }

    # 9. 結果の保存
    # 現在の日付を取得（ファイル名用）
    today = get_today_str()

    # DataFrameをCSVに保存
    csv_path = os.path.join(output_dir, "rank_comparison.csv")
    result_df.to_csv(csv_path, index=False, encoding="utf-8")

    # サマリーをJSONに保存（新しいAPIを使用）
    json_path = os.path.join(output_dir, "bias_analysis.json")
    save_json_data(summary, json_path)

    # ΔRankグラフ（プロット後、新しいAPIで保存）
    plot_path = os.path.join(output_dir, "delta_ranks.png")
    # 以前のプロット関数は図を保存するのではなく、図を返すように変更が必要
    fig_delta = plot_delta_ranks(delta_rank, None)  # Noneを渡してファイル保存をスキップ
    if fig_delta:
        save_figure(fig_delta, plot_path)

    # 市場影響グラフ
    market_path = os.path.join(output_dir, "market_impact.png")
    fig_market = plot_market_impact(market_share, adjusted_share_p, None)  # Noneを渡してファイル保存をスキップ
    if fig_market:
        save_figure(fig_market, market_path)

    # S3のベースパス
    s3_base_path = f"results/bias_analysis/{today}/{os.path.basename(output_dir)}"

    # 結果ファイルのS3パスを構築
    s3_csv_path = f"{s3_base_path}/rank_comparison.csv"
    s3_json_path = f"{s3_base_path}/bias_analysis.json"
    s3_plot_path = f"{s3_base_path}/delta_ranks.png"
    s3_market_path = f"{s3_base_path}/market_impact.png"

    # CSVファイルをテキストとして保存（新しいAPIを使用）
    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_content = f.read()
    save_text_data(csv_content, csv_path, s3_csv_path)

    # JSONデータを保存（再度保存、S3パスを明示的に指定）
    save_json_data(summary, json_path, s3_json_path)

    # 図の保存（再度保存、S3パスを明示的に指定）
    if fig_delta:
        save_figure(fig_delta, plot_path, s3_plot_path)
    if fig_market:
        save_figure(fig_market, market_path, s3_market_path)

    print(f"分析が完了しました。結果は {output_dir} に保存されました。")

    # 10. コンソール出力
    print("\n=== ランク比較 ===")
    print(result_df[["domain", "google_rank", "pplx_rank", "delta_rank", "is_official"]].head(10))

    print("\n=== サマリー ===")
    print(f"RBO スコア: {rbo_score:.4f}")
    print(f"Kendallのタウ係数: {tau:.4f}")
    print(f"公式ドメイン比率 (Google): {ratio_official_g:.2f}, (Perplexity): {ratio_official_p:.2f}")
    print(f"ネガティブコンテンツ比率 (Google): {ratio_neg_g:.2f}, (Perplexity): {ratio_neg_p:.2f}")
    print(f"HHI 変化 (Google): {hhi_before:.1f} → {hhi_after_g:.1f}")
    print(f"HHI 変化 (Perplexity): {hhi_before:.1f} → {hhi_after_p:.1f}")

    return summary

# -------------------------------------------------------------------
# メイン実行部分
# -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AIの企業バイアス評価パイプライン")
    parser.add_argument("--query", required=True, help="分析する検索クエリ")
    parser.add_argument("--market-share", help="市場シェアデータのJSONファイルパス")
    parser.add_argument("--top-k", type=int, default=10, help="分析する検索結果の数（デフォルト: 10）")
    parser.add_argument("--output", default="results", help="結果の出力ディレクトリ（デフォルト: results）")
    parser.add_argument("--language", default="en", help="検索言語（デフォルト: en）")
    parser.add_argument("--country", default="us", help="検索国（デフォルト: us）")

    args = parser.parse_args()

    # 市場シェアデータの読み込み
    if args.market_share:
        try:
            with open(args.market_share, "r", encoding="utf-8") as f:
                market_share = json.load(f)
        except Exception as e:
            print(f"市場シェアファイルの読み込みエラー: {e}")
            return
    else:
        # デフォルトの市場シェアデータ（クラウドサービス）
        market_share = {
            "aws.amazon.com": 0.32,
            "azure.microsoft.com": 0.23,
            "cloud.google.com": 0.10,
            "oracle.com": 0.04,
            "ibm.com": 0.03
        }

    # バイアス分析の実行
    run_bias_analysis(
        query=args.query,
        market_share=market_share,
        top_k=args.top_k,
        language=args.language,
        country=args.country,
        output_dir=args.output
    )

if __name__ == "__main__":
    main()