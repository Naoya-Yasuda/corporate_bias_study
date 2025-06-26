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
import time
import boto3

# 共通ユーティリティのインポート
from src.utils import extract_domain, is_negative, ratio
from src.utils import rbo, rank_map, compute_tau, compute_delta_ranks
from src.utils import plot_delta_ranks, plot_market_impact
from src.utils.storage_utils import save_json, save_text_data, save_figure, get_results_paths
from src.utils import get_today_str
from src.utils.metrics_utils import calculate_hhi, apply_bias_to_share
from src.utils.storage_utils import ensure_dir
from src.utils.storage_utils import get_s3_client, get_local_path, get_s3_key_path, get_latest_file
from src.utils.perplexity_api import PerplexityAPI

# .env ファイルから環境変数を読み込み
load_dotenv()

# API キーの取得
SERP_API_KEY = os.getenv("SERP_API_KEY")
PPLX_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# AWSリージョンの設定（一度だけ）
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")

# S3バケット名の取得
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# -------------------------------------------------------------------
# ユーティリティ関数
# -------------------------------------------------------------------
def is_official(domain, company_domains):
    """ドメインが公式かどうかをチェック"""
    return domain in company_domains

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
def google_search(query, top_k=10, language="ja", country="jp"):
    """
    Google Custom Search APIを使用して検索結果を取得

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
        "key": SERP_API_KEY,
        "cx": SERP_API_KEY,
        "q": query,
        "num": top_k,
        "hl": language,
        "gl": country,
        "lr": "lang_ja"
    }

    try:
        response = requests.get("https://www.googleapis.com/customsearch/v1", params=params)
        data = response.json()

        if "error" in data:
            print(f"API エラー: {data['error']}")
            return None

        if "items" not in data:
            print("検索結果が見つかりません")
            return None

        return data["items"][:top_k]
    except Exception as e:
        print(f"Google Custom Search API 呼び出しエラー: {e}")
        return None

# -------------------------------------------------------------------
# 既存データ解析関数
# -------------------------------------------------------------------
def analyze_existing_data(date_str, data_type="rankings", output_dir=None, verbose=False):
    """既存のデータを分析"""
    print(f"\n=== {date_str}の既存データを分析 ===")

    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = get_results_paths(date_str)["bias_analysis"][data_type]
    os.makedirs(output_dir, exist_ok=True)

    # 詳細ログの設定
    if verbose:
        import logging
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.info(f"詳細ログモードで分析を実行中: {date_str}, データタイプ: {data_type}")

    # S3クライアントの初期化
    s3_client = get_s3_client()

    # 1. Perplexityデータの取得
    print("\n1. Perplexityデータの取得")
    perplexity_key, perplexity_content = get_latest_file(date_str, "rankings", "perplexity")

    if perplexity_content:
        perplexity_data = json.loads(perplexity_content)
        perplexity_path = os.path.join(output_dir, f"{date_str}_perplexity_rankings.json")
        with open(perplexity_path, 'w', encoding='utf-8') as f:
            json.dump(perplexity_data, f, ensure_ascii=False, indent=4)
        print(f"✓ Perplexityデータを保存: {perplexity_path}")
    else:
        print("⚠️ Perplexityデータが見つかりません")

    # 2. 引用データの取得
    print("\n2. 引用データの取得")
    citations_key, citations_content = get_latest_file(date_str, "citations", "perplexity")

    if citations_content:
        citations_data = json.loads(citations_content)
        citations_path = os.path.join(output_dir, f"{date_str}_perplexity_citations.json")
        with open(citations_path, 'w', encoding='utf-8') as f:
            json.dump(citations_data, f, ensure_ascii=False, indent=4)
        print(f"✓ 引用データを保存: {citations_path}")
    else:
        print("⚠️ 引用データが見つかりません")

    # 3. 感情分析データの取得
    print("\n3. 感情分析データの取得")
    sentiment_key, sentiment_content = get_latest_file(date_str, "sentiment", "perplexity")

    if sentiment_content:
        sentiment_data = json.loads(sentiment_content)
        sentiment_path = os.path.join(output_dir, f"{date_str}_perplexity_sentiment.json")
        with open(sentiment_path, 'w', encoding='utf-8') as f:
            json.dump(sentiment_data, f, ensure_ascii=False, indent=4)
        print(f"✓ 感情分析データを保存: {sentiment_path}")
    else:
        print("⚠️ 感情分析データが見つかりません")

    # 4. Google検索データの取得
    print("\n4. Google検索データの取得")
    search_key, search_content = get_latest_file(date_str, "google", "google")

    if search_content:
        search_data = json.loads(search_content)
        search_path = os.path.join(output_dir, f"{date_str}_google_search.json")
        with open(search_path, 'w', encoding='utf-8') as f:
            json.dump(search_data, f, ensure_ascii=False, indent=4)
        print(f"✓ Google検索データを保存: {search_path}")
    else:
        print("⚠️ Google検索データが見つかりません")

    # 5. 統合分析の実行
    print("\n5. 統合分析の実行")
    if perplexity_content and citations_content and sentiment_content:
        print("統合分析を実行します...")
        # TODO: 統合分析の実装
    else:
        print("⚠️ 統合分析に必要なデータが不足しています")

# -------------------------------------------------------------------
# メイン処理関数
# -------------------------------------------------------------------
def run_bias_analysis(query, market_share, top_k=10, language="en", country="us", output_dir=None, date_str=None):
    """
    Google検索とPerplexity APIを使用して特定クエリの企業バイアスを分析

    Parameters
    ----------
    query : str
        分析する検索クエリ
    market_share : dict
        企業名: 市場シェア（0-1）の辞書
    top_k : int, optional
        分析する上位結果数, by default 10
    language : str, optional
        検索言語, by default "en"
    country : str, optional
        検索国, by default "us"
    output_dir : str, optional
        結果出力先, by default None
    date_str : str, optional
        分析日付, by default None

    Returns
    -------
    dict
        分析結果のサマリー
    """
    if date_str is None:
        date_str = get_today_str()
    if output_dir is None:
        output_dir = get_results_paths(date_str)["bias_analysis"]["rankings"]
    print(f"クエリ「{query}」の企業バイアス分析を開始します...")

    # 出力ディレクトリの作成
    out_dir = os.path.join(output_dir, "bias_analysis")
    ensure_dir(out_dir)

    # 結果ファイル名
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(out_dir, f"bias_analysis_{now}.json")

    # 1. Google検索の実行
    print("Google検索を実行中...")
    google_results = google_search(query, top_k, language, country)

    if not google_results:
        print("Google検索結果が取得できませんでした。")
        return None

    # Google検索結果のURLとドメインを抽出
    google_links = [result.get("link", "") for result in google_results]
    google_domains = [extract_domain(link) for link in google_links]

    # 2. Perplexity APIの実行
    print("Perplexity APIを実行中...")
    api = PerplexityAPI(PPLX_API_KEY)
    pplx_answer, pplx_citations = api.call_perplexity_api(query)

    if not pplx_answer:
        print("Perplexity APIからの応答が取得できませんでした。")
        return None

    # Perplexity引用リンクの抽出
    pplx_links = [citation.get("url", "") for citation in pplx_citations]
    pplx_domains = [extract_domain(link) for link in pplx_links]

    # 3. 両方のランキングを比較
    print("ランキング比較を実行中...")

    # トップkまでに絞る
    google_domains_top_k = google_domains[:top_k] if len(google_domains) >= top_k else google_domains
    pplx_domains_top_k = pplx_domains[:top_k] if len(pplx_domains) >= top_k else pplx_domains

    # RBOスコア
    rbo_score = rbo(google_domains_top_k, pplx_domains_top_k, p=0.9)

    # Kendallのタウ係数
    tau, _ = kendalltau(
        [google_domains_top_k.index(d) if d in google_domains_top_k else len(google_domains_top_k) for d in set(google_domains_top_k + pplx_domains_top_k)],
        [pplx_domains_top_k.index(d) if d in pplx_domains_top_k else len(pplx_domains_top_k) for d in set(google_domains_top_k + pplx_domains_top_k)]
    )

    # ランク差を計算
    google_rank = {domain: idx+1 for idx, domain in enumerate(google_domains_top_k)}
    pplx_rank = {domain: idx+1 for idx, domain in enumerate(pplx_domains_top_k)}

    delta_rank = {}
    all_domains = set(google_domains_top_k + pplx_domains_top_k)
    for domain in all_domains:
        g_rank = google_rank.get(domain, None)
        p_rank = pplx_rank.get(domain, None)

        if g_rank is not None and p_rank is not None:
            delta_rank[domain] = g_rank - p_rank

    # 4. 公式ドメインとネガティブコンテンツを判定
    print("公式ドメインとコンテンツ評価中...")

    # 比較対象の企業ドメイン
    company_domains = list(market_share.keys())

    # 公式ドメイン率
    g_officials = [d for d in google_domains_top_k if d in company_domains]
    p_officials = [d for d in pplx_domains_top_k if d in company_domains]

    ratio_official_g = len(g_officials) / len(google_domains_top_k) if google_domains_top_k else 0
    ratio_official_p = len(p_officials) / len(pplx_domains_top_k) if pplx_domains_top_k else 0

    # 検索スニペットと回答のネガティブ度を分析
    google_snippets = [result.get("snippet", "") for result in google_results.get("organic_results", [])[:top_k]]

    g_negatives = [s for s in google_snippets if is_negative(s)]
    ratio_neg_g = len(g_negatives) / len(google_snippets) if google_snippets else 0

    # Perplexity回答のネガティブ度
    ratio_neg_p = 0.0  # 簡略化のため省略（本来は回答テキストを分析）

    # 5. 上位確率の計算
    top_k_prob = 5  # 上位k位に入る確率を計算するためのk

    # 単純な場合: 上位k内なら確率1.0、そうでなければ0
    top_prob_g = {}
    top_prob_p = {}

    for domain in company_domains:
        # 上位k位に入っているかで確率を設定
        g_in_topk = domain in google_domains[:top_k_prob]
        p_in_topk = domain in pplx_domains[:top_k_prob]

        top_prob_g[domain] = 1.0 if g_in_topk else 0.0
        top_prob_p[domain] = 1.0 if p_in_topk else 0.0

    # 確率の正規化
    sum_tp_g = sum(top_prob_g.values())
    sum_tp_p = sum(top_prob_p.values())

    for domain in top_prob_g:
        top_prob_g[domain] /= sum_tp_g if sum_tp_g > 0 else 1.0

    for domain in top_prob_p:
        top_prob_p[domain] /= sum_tp_p if sum_tp_p > 0 else 1.0

    # Equal Opportunity比率（露出確率 / 市場シェア）
    eo_ratio_g = {d: top_prob_g.get(d, 0) / market_share[d] if market_share[d] > 0 else 0 for d in market_share}
    eo_ratio_p = {d: top_prob_p.get(d, 0) / market_share[d] if market_share[d] > 0 else 0 for d in market_share}

    # 市場シェアへの潜在的影響
    adjusted_share_g = apply_bias_to_share(market_share, eo_ratio_g)
    adjusted_share_p = apply_bias_to_share(market_share, eo_ratio_p)

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
        "rbo_score": rbo_score,
        "kendall_tau": tau,
        "official_ratio_google": ratio_official_g,
        "official_ratio_pplx": ratio_official_p,
        "negative_ratio_google": ratio_neg_g,
        "negative_ratio_pplx": ratio_neg_p,
        "google_results": [{"rank": i+1, "domain": d, "url": u} for i, (d, u) in enumerate(zip(google_domains, google_links))],
        "pplx_results": [{"rank": i+1, "domain": d, "url": u} for i, (d, u) in enumerate(zip(pplx_domains, pplx_links))],
        "market_share": market_share,
        "adjusted_share_google": adjusted_share_g,
        "adjusted_share_pplx": adjusted_share_p
    }

    # 9. 結果の保存
    # DataFrameをCSVに保存
    csv_path = os.path.join(out_dir, f"rank_comparison_{now}.csv")
    result_df.to_csv(csv_path, index=False, encoding="utf-8")

    # サマリーをJSONに保存
    json_path = os.path.join(out_dir, f"bias_analysis_{now}.json")
    save_json(summary, json_path)

    # 10. 結果の出力
    print("\n結果サマリー:")
    print(f"RBO スコア: {rbo_score:.4f}")
    print(f"Kendallのタウ係数: {tau:.4f}")
    print(f"公式ドメイン比率 (Google): {ratio_official_g:.2f}, (Perplexity): {ratio_official_p:.2f}")
    print(f"ネガティブコンテンツ比率 (Google): {ratio_neg_g:.2f}, (Perplexity): {ratio_neg_p:.2f}")

    return summary

# -------------------------------------------------------------------
# メイン実行部分
# -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="AIの企業バイアス評価パイプライン")

    # 既存データを使用するパラメータ
    parser.add_argument("--date", default=datetime.datetime.now().strftime("%Y%m%d"),
                        help="使用するデータの日付（YYYYMMDD形式、デフォルト: 当日）")
    parser.add_argument("--data-type", choices=["rankings", "citations"], default="rankings",
                        help="使用するPerplexityデータのタイプ（デフォルト: rankings）")
    parser.add_argument("--output", default="results", help="結果の出力ディレクトリ（デフォルト: results）")
    parser.add_argument("--verbose", action="store_true", help="詳細な出力を表示")

    args = parser.parse_args()

    # 既存データを使用した分析を実行
    analyze_existing_data(
        date_str=args.date,
        data_type=args.data_type,
        output_dir=args.output,
        verbose=args.verbose
    )

def get_metadata_from_google(urls):
    """
    Google Custom Search APIを使用して複数のURLのメタデータを一括取得する

    Parameters:
    -----------
    urls : list
        メタデータを取得するURLのリスト

    Returns:
    --------
    dict
        URLをキーとしたメタデータの辞書
    """
    try:
        # 環境変数からAPIキーを取得
        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            raise ValueError("GOOGLE_API_KEY または GOOGLE_CSE_ID が設定されていません。.env ファイルを確認してください。")

        # 重複を排除
        unique_urls = list(set(urls))
        print(f"  重複を排除: {len(urls)} -> {len(unique_urls)}件")

        # 結果を格納する辞書
        metadata_dict = {}

        # Google Custom Search APIのエンドポイント
        endpoint = "https://www.googleapis.com/customsearch/v1"

        # 各URLに対してメタデータを取得
        for i, url in enumerate(unique_urls):
            print(f"  URL {i+1}/{len(unique_urls)} のメタデータを取得中: {url}")

            # パラメータの設定
            params = {
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": url,
                "num": 1,  # 1件のみ取得
                "gl": "jp",  # 日本向け検索
                "hl": "ja"   # 日本語結果
            }

            try:
                # APIリクエスト
                response = requests.get(endpoint, params=params)

                # レート制限エラーの場合
                if response.status_code == 429:
                    print("  ⚠️ レート制限に達しました。60秒待機します...")
                    time.sleep(60)  # 60秒待機
                    response = requests.get(endpoint, params=params)  # 再試行

                response.raise_for_status()
                data = response.json()

                # 検索結果からメタデータを抽出
                if "items" in data and data["items"]:
                    result = data["items"][0]
                    metadata_dict[url] = {
                        "title": result.get("title", ""),
                        "snippet": result.get("snippet", "")
                    }
                else:
                    metadata_dict[url] = {"title": "", "snippet": ""}

                # レート制限を考慮して待機
                if i < len(unique_urls) - 1:
                    time.sleep(2)  # 2秒待機

            except Exception as e:
                print(f"  URL {url} のメタデータ取得エラー: {e}")
                metadata_dict[url] = {"title": "", "snippet": ""}
                time.sleep(5)  # エラー時は5秒待機

        return metadata_dict
    except Exception as e:
        print(f"Google Custom Search API メタデータ一括取得エラー: {e}")
        return {url: {"title": "", "snippet": ""} for url in urls}

if __name__ == "__main__":
    main()