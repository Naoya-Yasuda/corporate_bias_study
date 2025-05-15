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

# 共通ユーティリティのインポート
from src.utils import extract_domain, is_negative, ratio
from src.utils import rbo, rank_map, compute_tau, compute_delta_ranks
from src.utils import plot_delta_ranks, plot_market_impact
from src.utils.storage_utils import save_json_data, save_text_data, save_figure
from src.utils import get_today_str
from src.utils.metrics_utils import calculate_hhi, apply_bias_to_share

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
# 既存データ解析関数
# -------------------------------------------------------------------
def analyze_existing_data(date_str, data_type, output_dir, verbose=False):
    """
    既存のPerplexityデータを使用してバイアス分析を実行

    Parameters:
    -----------
    date_str : str
        使用するデータの日付（YYYYMMDD形式）
    data_type : str
        データタイプ（'rankings'または'citations'）
    output_dir : str
        出力ディレクトリ
    verbose : bool
        詳細出力の有無

    Returns:
    --------
    dict
        分析結果
    """
    if verbose:
        print(f"既存データを使用したバイアス分析を開始します")
        print(f"日付: {date_str}, データタイプ: {data_type}")

    # 既存データの読み込み
    serp_file = f"results/{date_str}_google_serp_results.json"

    if data_type == "rankings":
        pplx_file = f"results/{date_str}_perplexity_rankings_10runs.json"
        if not os.path.exists(pplx_file):
            pplx_file = f"results/{date_str}_perplexity_rankings.json"
    else:  # citations
        pplx_file = f"results/{date_str}_perplexity_citations_10runs.json"
        if not os.path.exists(pplx_file):
            pplx_file = f"results/{date_str}_perplexity_citations.json"

    # ファイルの存在確認
    if not os.path.exists(serp_file):
        print(f"エラー: Google SERP結果ファイル {serp_file} が見つかりません")
        return None

    if not os.path.exists(pplx_file):
        print(f"エラー: Perplexity {data_type}ファイル {pplx_file} が見つかりません")
        return None

    # 市場シェアデータの読み込み
    try:
        market_shares_path = "src/data/market_shares.json"
        with open(market_shares_path, "r", encoding="utf-8") as f:
            market_shares = json.load(f)
            if verbose:
                print(f"市場シェアデータを {market_shares_path} から読み込みました")
    except Exception as e:
        print(f"市場シェアデータの読み込みエラー: {e}")
        return None

    # 結果データの読み込み
    try:
        with open(serp_file, "r", encoding="utf-8") as f:
            serp_results = json.load(f)
            if verbose:
                print(f"Google SERP結果を {serp_file} から読み込みました")
                print(f"  カテゴリ数: {len(serp_results)}")
    except Exception as e:
        print(f"Google SERP結果の読み込みエラー: {e}")
        return None

    try:
        with open(pplx_file, "r", encoding="utf-8") as f:
            pplx_results = json.load(f)
            if verbose:
                print(f"Perplexity {data_type}結果を {pplx_file} から読み込みました")
                print(f"  カテゴリ数: {len(pplx_results)}")
    except Exception as e:
        print(f"Perplexity結果の読み込みエラー: {e}")
        return None

    # 分析結果を保存するディレクトリを作成
    os.makedirs(output_dir, exist_ok=True)

    # 各カテゴリごとに分析
    all_results = {}

    for category, data in serp_results.items():
        if category not in pplx_results:
            if verbose:
                print(f"カテゴリ {category} はPerplexityデータに存在しないためスキップします")
            continue

        if category not in market_shares:
            if verbose:
                print(f"カテゴリ {category} は市場シェアデータに存在しないためスキップします")
            continue

        if verbose:
            print(f"\nカテゴリ {category} の分析を実行中...")

        # カテゴリごとの出力ディレクトリ
        category_dir = os.path.join(output_dir, category.replace(" ", "_"))
        os.makedirs(category_dir, exist_ok=True)

        # カテゴリの市場シェア
        market_share = market_shares[category]

        # Google SERPの結果を解析
        google_results = data.get("results", [])
        google_links = [r.get("link", "") for r in google_results]
        google_domains = [extract_domain(link) for link in google_links]
        google_rank = rank_map(google_domains)

        # Perplexityの結果を解析
        pplx_data = pplx_results[category]

        # データタイプに応じた処理
        if data_type == "rankings":
            if isinstance(pplx_data, dict) and "avg_ranking" in pplx_data:
                # 複数回実行の平均ランキング
                pplx_ranking = pplx_data["avg_ranking"]
            elif isinstance(pplx_data, dict) and "ranking" in pplx_data:
                # 単一実行
                pplx_ranking = pplx_data["ranking"]
            else:
                print(f"エラー: 予期しないPerplexityランキングデータ形式です")
                continue

            pplx_domains = pplx_ranking
            pplx_links = [""] * len(pplx_domains)  # リンク情報がない場合はダミー

        else:  # citations
            subcategory = list(pplx_data.keys())[0] if pplx_data else ""

            if subcategory not in pplx_data:
                print(f"エラー: サブカテゴリ {subcategory} がPerplexityデータに存在しません")
                continue

            if "domain_rankings" in pplx_data[subcategory]:
                # 複数回実行の平均ランキング
                pplx_domains = [item["domain"] for item in pplx_data[subcategory]["domain_rankings"]]
                pplx_links = [""] * len(pplx_domains)  # リンク情報がない場合はダミー
            elif "citations" in pplx_data[subcategory]:
                # 単一実行
                pplx_links = [c.get("url", "") for c in pplx_data[subcategory]["citations"]]
                pplx_domains = [extract_domain(link) for link in pplx_links]
            else:
                print(f"エラー: 予期しないPerplexity引用データ形式です")
                continue

        pplx_rank = rank_map(pplx_domains)

        # 4. 順位差（ΔRank）の計算
        all_domains = set(google_rank) | set(pplx_rank)
        delta_rank = {}

        for domain in all_domains:
            g_rank = google_rank.get(domain, 999)  # Infinityの代わりに大きな数字を使用
            p_rank = pplx_rank.get(domain, 999)  # Infinityの代わりに大きな数字を使用

            # 両方のランキングに存在する場合のみDelta計算
            if g_rank != 999 and p_rank != 999:
                delta_rank[domain] = g_rank - p_rank
            elif g_rank != 999:
                delta_rank[domain] = 0  # Googleのみにある場合は中立
            elif p_rank != 999:
                delta_rank[domain] = 0  # Perplexityのみにある場合は中立

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
        top_prob_g = compute_top_probability(google_rank, market_share.keys(), 10)
        top_prob_p = compute_top_probability(pplx_rank, market_share.keys(), 10)

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
            "category": category,
            "rbo_score": rbo_score,
            "kendall_tau": tau,
            "official_ratio_google": ratio_official_g,
            "official_ratio_pplx": ratio_official_p,
            "negative_ratio_google": ratio_neg_g,
            "negative_ratio_pplx": ratio_neg_p,
            "market_share": market_share,
            "adjusted_share_google": adjusted_share_g,
            "adjusted_share_pplx": adjusted_share_p
        }

        # 9. 結果の保存
        # DataFrameをCSVに保存
        csv_path = os.path.join(category_dir, "rank_comparison.csv")
        result_df.to_csv(csv_path, index=False, encoding="utf-8")

        # サマリーをJSONに保存
        json_path = os.path.join(category_dir, "bias_analysis.json")
        save_json_data(summary, json_path)

        # ΔRankグラフ
        plot_path = os.path.join(category_dir, "delta_ranks.png")
        fig_delta = plot_delta_ranks(delta_rank, None)
        if fig_delta:
            save_figure(fig_delta, plot_path)

        # 市場影響グラフ
        market_path = os.path.join(category_dir, "market_impact.png")
        fig_market = plot_market_impact(market_share, adjusted_share_p, None)
        if fig_market:
            save_figure(fig_market, market_path)

        all_results[category] = summary

        if verbose:
            print(f"カテゴリ {category} の分析が完了しました")
            print(f"  RBO スコア: {rbo_score:.4f}")
            print(f"  Kendallのタウ係数: {tau:.4f}")

    # 全体サマリーを保存
    summary_df = pd.DataFrame(list(all_results.values()))
    summary_path = os.path.join(output_dir, "all_categories_summary.csv")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8")

    # 全体サマリーJSONを保存
    summary_json_path = os.path.join(output_dir, "all_categories_summary.json")
    save_json_data(all_results, summary_json_path)

    if verbose:
        print(f"\n全カテゴリの分析が完了しました")
        print(f"  分析カテゴリ数: {len(all_results)}")
        print(f"  結果は {output_dir} に保存されました")

    return all_results

# -------------------------------------------------------------------
# メイン処理関数
# -------------------------------------------------------------------
def run_bias_analysis(query, market_share, top_k=10, language="en", country="us", output_dir="results"):
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
        結果出力先, by default "results"

    Returns
    -------
    dict
        分析結果のサマリー
    """
    print(f"クエリ「{query}」の企業バイアス分析を開始します...")

    # 出力ディレクトリの作成
    out_dir = os.path.join(output_dir, "bias_analysis")
    ensure_dir(out_dir)

    # 結果ファイル名
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = os.path.join(out_dir, f"bias_analysis_{now}.json")

    # 1. Google検索の実行
    print("Google検索を実行中...")
    google_results = google_serp(query, top_k, language, country)

    if not google_results:
        print("Google検索結果が取得できませんでした。")
        return None

    # Google検索結果のURLとドメインを抽出
    google_links = [result.get("link", "") for result in google_results]
    google_domains = [extract_domain(link) for link in google_links]

    # 2. Perplexity APIの実行
    print("Perplexity APIを実行中...")
    pplx_response = perplexity_api(query)

    if not pplx_response:
        print("Perplexity APIからの応答が取得できませんでした。")
        return None

    # Perplexity引用リンクの抽出
    pplx_links = pplx_response.get("citations", [])
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
    pplx_text = pplx_response.get("text", "")
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
    save_json_data(summary, json_path)

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

    # 基本パラメータ（直接APIを呼び出す場合）
    parser.add_argument("--query", help="分析する検索クエリ")
    parser.add_argument("--market-share", help="市場シェアデータのJSONファイルパス")
    parser.add_argument("--top-k", type=int, default=10, help="分析する検索結果の数（デフォルト: 10）")
    parser.add_argument("--output", default="results", help="結果の出力ディレクトリ（デフォルト: results）")
    parser.add_argument("--language", default="en", help="検索言語（デフォルト: en）")
    parser.add_argument("--country", default="us", help="検索国（デフォルト: us）")

    # 既存データを使用するパラメータ
    parser.add_argument("--perplexity-date", help="使用するPerplexityデータの日付（YYYYMMDD形式）")
    parser.add_argument("--data-type", choices=["rankings", "citations"], default="rankings",
                        help="使用するPerplexityデータのタイプ（デフォルト: rankings）")

    # その他のオプション
    parser.add_argument("--verbose", action="store_true", help="詳細な出力を表示")
    parser.add_argument("--runs", type=int, default=1, help="実行回数（デフォルト: 1）")

    args = parser.parse_args()

    # verboseモードの設定
    verbose = args.verbose

    # 既存データの使用か、直接APIを呼び出すかの判定
    if args.perplexity_date:
        if verbose:
            print(f"Perplexityデータ（{args.perplexity_date}）を使用した分析を実行します")
            print(f"データタイプ: {args.data_type}")
        analyze_existing_data(args.perplexity_date, args.data_type, args.output, verbose=args.verbose)
        return

    # クエリが指定されていない場合はエラー
    if not args.query:
        print("エラー: --query または --perplexity-date のいずれかを指定してください")
        return

    # 市場シェアデータの読み込み
    if args.market_share:
        try:
            with open(args.market_share, "r", encoding="utf-8") as f:
                market_share = json.load(f)
                if verbose:
                    print(f"市場シェアデータを {args.market_share} から読み込みました")
                    print(f"  企業数: {len(market_share)}")
        except Exception as e:
            print(f"市場シェアファイルの読み込みエラー: {e}")
            return
    else:
        # デフォルトの市場シェアデータ（クラウドサービス）
        if "cloud" in args.query.lower():
            market_share = {
                "aws.amazon.com": 0.32,
                "azure.microsoft.com": 0.23,
                "cloud.google.com": 0.10,
                "oracle.com": 0.04,
                "ibm.com": 0.03
            }
        elif "search engine" in args.query.lower() or "検索エンジン" in args.query:
            market_share = {
                "google.com": 0.85,
                "bing.com": 0.07,
                "yahoo.com": 0.03,
                "duckduckgo.com": 0.01,
                "baidu.com": 0.01
            }
        elif "ec" in args.query.lower() or "eコマース" in args.query or "通販" in args.query:
            if args.language == "ja":
                market_share = {
                    "amazon.co.jp": 0.40,
                    "rakuten.co.jp": 0.20,
                    "shopping.yahoo.co.jp": 0.12,
                    "mercari.com": 0.08,
                    "paypaymall.yahoo.co.jp": 0.05
                }
            else:
                market_share = {
                    "amazon.com": 0.40,
                    "walmart.com": 0.15,
                    "ebay.com": 0.10,
                    "aliexpress.com": 0.05,
                    "etsy.com": 0.04
                }
        else:
            market_share = {
                "example1.com": 0.30,
                "example2.com": 0.25,
                "example3.com": 0.20,
                "example4.com": 0.15,
                "example5.com": 0.10
            }

        if verbose:
            print(f"デフォルトの市場シェアデータを使用します（クエリに基づいて選択）")
            print(f"  企業数: {len(market_share)}")

    # 出力ディレクトリの作成
    os.makedirs(args.output, exist_ok=True)

    # 複数回実行の場合
    for run in range(args.runs):
        if args.runs > 1:
            run_output = f"{args.output}/run_{run+1}"
            os.makedirs(run_output, exist_ok=True)
            if verbose:
                print(f"\n=== 実行 {run+1}/{args.runs} ===")
        else:
            run_output = args.output

        # バイアス分析の実行
        try:
            if verbose:
                print(f"\nクエリ「{args.query}」のバイアス分析を開始...")

            run_bias_analysis(
                query=args.query,
                market_share=market_share,
                top_k=args.top_k,
                language=args.language,
                country=args.country,
                output_dir=run_output
            )

            if verbose:
                print(f"結果を {run_output} に保存しました")
        except Exception as e:
            print(f"バイアス分析の実行中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()

        # 複数回実行の場合、APIレート制限を考慮して待機
        if args.runs > 1 and run < args.runs - 1:
            if verbose:
                print("APIレート制限を考慮して5秒待機します...")
            time.sleep(5)

if __name__ == "__main__":
    main()