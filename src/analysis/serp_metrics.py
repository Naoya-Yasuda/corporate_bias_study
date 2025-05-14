#!/usr/bin/env python
# coding: utf-8

"""
Google SERP とPerplexity の結果を比較して分析するためのメトリクスモジュール
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import kendalltau
from collections import defaultdict

# RBO (Rank-Biased Overlap) の実装
def rbo(s1, s2, p=0.9):
    """
    Rank-Biased Overlap (RBO) スコアを計算

    Parameters
    ----------
    s1, s2 : list
        比較する2つのランキングリスト
    p : float
        減衰パラメータ (0 < p < 1)

    Returns
    -------
    float
        RBO スコア（0～1）。1に近いほど類似。
    """
    if not s1 or not s2:
        return 0.0

    # 集合として扱うため、重複を排除
    s1 = [x for i, x in enumerate(s1) if x not in s1[:i]]
    s2 = [x for i, x in enumerate(s2) if x not in s2[:i]]

    # 最小限のオーバーラップ深さを計算
    depth = min(len(s1), len(s2))

    # 各深さでのオーバーラップを計算
    overlap = 0.0
    rbo_score = 0.0

    for d in range(1, depth + 1):
        # d番目までの要素の集合
        set1 = set(s1[:d])
        set2 = set(s2[:d])

        # オーバーラップの大きさ
        overlap = len(set1.intersection(set2))

        # 深さdでのRBO項を計算
        rbo_score += p**(d-1) * (overlap / d)

    # 重みの正規化
    rbo_score = rbo_score * (1 - p)

    return rbo_score

# -------------------------------------------------------------------
# 比較メトリクス
# -------------------------------------------------------------------
def compute_ranking_metrics(google_ranking, pplx_ranking, max_k=10):
    """
    Googleランキングと Perplexity ランキングを比較するメトリクス計算

    Parameters
    ----------
    google_ranking : list
        Google検索結果の企業ランキング
    pplx_ranking : list
        Perplexity APIの企業ランキング
    max_k : int
        最大比較ランク

    Returns
    -------
    dict
        比較メトリクス
    """
    # リストが空の場合のハンドリング
    if not google_ranking or not pplx_ranking:
        return {
            "rbo": 0.0,
            "kendall_tau": 0.0,
            "delta_ranks": {},
            "overlap_ratio": 0.0
        }

    # k以内に絞る
    g_top_k = google_ranking[:max_k]
    p_top_k = pplx_ranking[:max_k]

    # RBOスコア
    rbo_score = rbo(g_top_k, p_top_k, p=0.9)

    # Kendallのタウ係数
    # 共通のアイテムのみで計算
    common_items = list(set(g_top_k).intersection(set(p_top_k)))

    if len(common_items) >= 2:
        # 順位のマッピングを作成
        g_ranks = {item: idx for idx, item in enumerate(g_top_k)}
        p_ranks = {item: idx for idx, item in enumerate(p_top_k)}

        # 共通アイテムの順位のみを抽出
        g_common_ranks = [g_ranks[item] for item in common_items]
        p_common_ranks = [p_ranks[item] for item in common_items]

        # Kendallのタウ係数を計算
        tau, _ = kendalltau(g_common_ranks, p_common_ranks)
        if np.isnan(tau):
            tau = 0.0
    else:
        tau = 0.0

    # ΔRank計算（Google - PPLX）
    delta_ranks = {}
    all_companies = list(set(g_top_k + p_top_k))

    for company in all_companies:
        # Googleでの順位（ない場合はmax_k+1）
        g_rank = g_top_k.index(company) + 1 if company in g_top_k else max_k + 1
        # Perplexityでの順位（ない場合はmax_k+1）
        p_rank = p_top_k.index(company) + 1 if company in p_top_k else max_k + 1

        # 順位差（正: Googleで低く評価、負: Googleで高く評価）
        delta_ranks[company] = g_rank - p_rank

    # オーバーラップ比率（共通アイテム数/max_k）
    overlap_ratio = len(common_items) / max_k if max_k > 0 else 0.0

    return {
        "rbo": rbo_score,
        "kendall_tau": tau,
        "delta_ranks": delta_ranks,
        "overlap_ratio": overlap_ratio
    }

def compute_content_metrics(serp_detailed_results, top_k=10):
    """
    SERPの詳細結果から公式/非公式、ポジ/ネガ比率などを計算

    Parameters
    ----------
    serp_detailed_results : list
        SERPの詳細検索結果リスト
    top_k : int
        分析対象の上位結果数

    Returns
    -------
    dict
        コンテンツメトリクス
    """
    results = serp_detailed_results[:top_k]

    # 公式/非公式、ポジ/ネガ結果の数
    official_count = sum(1 for r in results if r.get("is_official") == "official")
    negative_count = sum(1 for r in results if r.get("is_negative", False))

    # 企業別の結果カウント
    company_results = defaultdict(lambda: {"total": 0, "official": 0, "negative": 0})

    for result in results:
        company = result.get("company")
        if company:
            company_results[company]["total"] += 1
            if result.get("is_official") == "official":
                company_results[company]["official"] += 1
            if result.get("is_negative", False):
                company_results[company]["negative"] += 1

    # 比率の計算
    n_results = len(results)
    metrics = {
        "official_ratio": official_count / n_results if n_results > 0 else 0,
        "negative_ratio": negative_count / n_results if n_results > 0 else 0,
        "company_metrics": {}
    }

    for company, counts in company_results.items():
        if counts["total"] > 0:
            metrics["company_metrics"][company] = {
                "result_count": counts["total"],
                "official_ratio": counts["official"] / counts["total"],
                "negative_ratio": counts["negative"] / counts["total"]
            }

    return metrics

# -------------------------------------------------------------------
# PerplexityとGoogle SERPの比較
# -------------------------------------------------------------------
def compare_with_perplexity(serp_results, pplx_results):
    """
    Google SERP結果とPerplexity結果を比較

    Parameters
    ----------
    serp_results : dict
        Google SERP結果
    pplx_results : dict
        Perplexity結果

    Returns
    -------
    dict
        比較結果
    """
    comparison = {}

    for category, subcategories in serp_results.items():
        comparison[category] = {}

        for subcategory, serp_data in subcategories.items():
            # Perplexityの対応するデータがあるか確認
            pplx_subcategory_data = pplx_results.get(category, {}).get(subcategory)

            if not pplx_subcategory_data:
                # 対応するデータがない場合はスキップ
                print(f"Perplexityデータなし: {category}/{subcategory}")
                continue

            # Google SERP ランキング
            google_ranking = serp_data.get("company_ranking", [])

            # Perplexity ランキング
            if isinstance(pplx_subcategory_data, dict) and "all_rankings" in pplx_subcategory_data:
                # 複数実行結果の場合は最初のランキングを使用
                pplx_ranking = pplx_subcategory_data["all_rankings"][0] if pplx_subcategory_data["all_rankings"] else []
            elif isinstance(pplx_subcategory_data, dict) and "ranking" in pplx_subcategory_data:
                # 単一実行結果
                pplx_ranking = pplx_subcategory_data["ranking"]
            elif isinstance(pplx_subcategory_data, list):
                # ランキングのリスト
                pplx_ranking = pplx_subcategory_data[0] if pplx_subcategory_data else []
            else:
                pplx_ranking = []

            # ランキング比較メトリクス
            ranking_metrics = compute_ranking_metrics(google_ranking, pplx_ranking)

            # コンテンツ分析メトリクス
            content_metrics = compute_content_metrics(serp_data.get("detailed_results", []))

            # 結果を格納
            comparison[category][subcategory] = {
                "google_ranking": google_ranking,
                "pplx_ranking": pplx_ranking,
                "ranking_metrics": ranking_metrics,
                "content_metrics": content_metrics
            }

    return comparison

# -------------------------------------------------------------------
# HHI計算など経済的影響の評価
# -------------------------------------------------------------------
def apply_bias_to_share(market_share, delta_ranks, weight=0.1):
    """
    ΔRankを考慮して市場シェアを調整

    Parameters
    ----------
    market_share : dict
        元の市場シェア
    delta_ranks : dict
        順位差
    weight : float
        バイアスの重み（調整パラメータ）

    Returns
    -------
    dict
        調整後の市場シェア
    """
    adjusted_share = market_share.copy()

    for company, delta in delta_ranks.items():
        if company in adjusted_share:
            # 負のΔRank（Googleで高評価）はシェア増加、正はシェア減少
            adjustment = -delta * weight / 10.0
            adjusted_share[company] *= (1 + adjustment)

    # 合計を1に正規化
    total = sum(adjusted_share.values())
    if total > 0:
        for company in adjusted_share:
            adjusted_share[company] /= total

    return adjusted_share

def calculate_hhi(market_share):
    """
    HHI（ハーフィンダール・ハーシュマン指数）を計算

    Parameters
    ----------
    market_share : dict
        市場シェア

    Returns
    -------
    float
        HHI値（0～10000）
    """
    return sum((share * 100) ** 2 for share in market_share.values())

# -------------------------------------------------------------------
# 分析関数
# -------------------------------------------------------------------
def analyze_serp_results(serp_results, pplx_results, comparison_results):
    """
    Google SERPとPerplexityの結果を統合的に分析

    Parameters
    ----------
    serp_results : dict
        Google SERP結果
    pplx_results : dict
        Perplexity結果
    comparison_results : dict
        比較結果

    Returns
    -------
    dict
        分析結果
    """
    # 市場シェアデータ（カテゴリごと）
    # 実際のデータに置き換える
    market_shares = {
        "クラウドサービス": {
            "AWS": 0.32, "Azure": 0.23, "Google Cloud": 0.10,
            "IBM Cloud": 0.04, "Oracle Cloud": 0.03
        },
        "検索エンジン": {
            "Google": 0.85, "Bing": 0.07, "Yahoo! Japan": 0.03, "Baidu": 0.01
        }
    }

    analysis = {}

    for category, subcategories in comparison_results.items():
        analysis[category] = {}

        # カテゴリの市場シェア
        category_market_share = market_shares.get(category, {})

        for subcategory, comparison_data in subcategories.items():
            # ランキングメトリクス
            ranking_metrics = comparison_data.get("ranking_metrics", {})

            # 順位差（ΔRank）
            delta_ranks = ranking_metrics.get("delta_ranks", {})

            # 市場シェアへの影響
            if category_market_share:
                # 調整後の市場シェア
                adjusted_share = apply_bias_to_share(category_market_share, delta_ranks)

                # HHI計算
                original_hhi = calculate_hhi(category_market_share)
                adjusted_hhi = calculate_hhi(adjusted_share)

                market_impact = {
                    "original_market_share": category_market_share,
                    "adjusted_market_share": adjusted_share,
                    "original_hhi": original_hhi,
                    "adjusted_hhi": adjusted_hhi,
                    "hhi_change": adjusted_hhi - original_hhi,
                    "hhi_change_percent": (adjusted_hhi - original_hhi) / original_hhi * 100 if original_hhi > 0 else 0
                }
            else:
                market_impact = None

            # コンテンツメトリクス
            content_metrics = comparison_data.get("content_metrics", {})

            # 結果を格納
            analysis[category][subcategory] = {
                "rbo_score": ranking_metrics.get("rbo", 0),
                "kendall_tau": ranking_metrics.get("kendall_tau", 0),
                "overlap_ratio": ranking_metrics.get("overlap_ratio", 0),
                "delta_ranks": delta_ranks,
                "official_ratio": content_metrics.get("official_ratio", 0),
                "negative_ratio": content_metrics.get("negative_ratio", 0),
                "market_impact": market_impact
            }

    return analysis

# -------------------------------------------------------------------
# 可視化関数
# -------------------------------------------------------------------
def plot_delta_ranks(delta_ranks, category, output_dir="results/analysis"):
    """
    ΔRankをバーチャートで可視化
    """
    if not delta_ranks:
        return None

    # データフレームに変換
    df = pd.DataFrame({
        "company": list(delta_ranks.keys()),
        "delta_rank": list(delta_ranks.values())
    })

    # ΔRankでソート
    df = df.sort_values("delta_rank")

    # プロット
    plt.figure(figsize=(10, 6))
    bars = plt.barh(df["company"], df["delta_rank"])

    # ゼロラインを強調
    plt.axvline(x=0, color='k', linestyle='-', alpha=0.3)

    # バーの色を設定（負の値は緑、正の値は赤）
    for i, bar in enumerate(bars):
        if df["delta_rank"].iloc[i] < 0:
            bar.set_color('green')
        else:
            bar.set_color('red')

    plt.title(f"{category}のGoogle vs Perplexity ΔRank比較")
    plt.xlabel("Δ Rank (Google - Perplexity)")
    plt.grid(axis='x', alpha=0.3)

    # 保存用のディレクトリ
    os.makedirs(output_dir, exist_ok=True)
    file_path = f"{output_dir}/{category}_delta_ranks.png"
    plt.savefig(file_path, dpi=100, bbox_inches="tight")
    plt.close()

    return file_path

def plot_market_impact(original_share, adjusted_share, category, output_dir="results/analysis"):
    """
    市場シェアへの影響を可視化
    """
    if not original_share or not adjusted_share:
        return None

    # データフレームに変換
    companies = list(original_share.keys())
    df = pd.DataFrame({
        "company": companies,
        "original": [original_share[c] for c in companies],
        "adjusted": [adjusted_share[c] for c in companies]
    })

    # シェアの差分を計算
    df["diff"] = df["adjusted"] - df["original"]
    df["diff_percent"] = (df["diff"] / df["original"]) * 100

    # ソート
    df = df.sort_values("original", ascending=False)

    # プロット
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

    # 左側：シェア比較
    ax1.bar(df["company"], df["original"], alpha=0.5, label="元のシェア")
    ax1.bar(df["company"], df["adjusted"], alpha=0.5, label="調整後シェア")
    ax1.set_title("市場シェア比較")
    ax1.set_ylabel("市場シェア")
    ax1.set_ylim(0, max(df["original"].max(), df["adjusted"].max()) * 1.1)
    ax1.legend()

    # 右側：変化率
    bars = ax2.bar(df["company"], df["diff_percent"])
    for i, bar in enumerate(bars):
        if df["diff_percent"].iloc[i] < 0:
            bar.set_color('red')
        else:
            bar.set_color('green')

    ax2.set_title("シェア変化率")
    ax2.set_ylabel("変化率 (%)")
    ax2.set_ylim(min(df["diff_percent"].min() * 1.1, 0), max(df["diff_percent"].max() * 1.1, 0))
    ax2.axhline(y=0, color='k', linestyle='-', alpha=0.3)

    plt.suptitle(f"{category}のGoogle検索バイアスによる市場シェア影響")
    plt.tight_layout()

    # 保存
    os.makedirs(output_dir, exist_ok=True)
    file_path = f"{output_dir}/{category}_market_impact.png"
    plt.savefig(file_path, dpi=100, bbox_inches="tight")
    plt.close()

    return file_path

# CLIから直接実行する場合のエントリポイント
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Google SERPとPerplexityの結果を分析")
    parser.add_argument("serp_file", help="Google SERP結果のJSONファイル")
    parser.add_argument("pplx_file", help="Perplexity結果のJSONファイル")
    parser.add_argument("--output", default="results/analysis", help="出力ディレクトリ")

    args = parser.parse_args()

    # JSONファイルを読み込み
    with open(args.serp_file, "r", encoding="utf-8") as f:
        serp_results = json.load(f)

    with open(args.pplx_file, "r", encoding="utf-8") as f:
        pplx_results = json.load(f)

    # 比較と分析
    comparison_results = compare_with_perplexity(serp_results, pplx_results)
    analysis_results = analyze_serp_results(serp_results, pplx_results, comparison_results)

    # 結果をJSONに保存
    os.makedirs(args.output, exist_ok=True)

    with open(f"{args.output}/comparison_results.json", "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, ensure_ascii=False, indent=2)

    with open(f"{args.output}/analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)

    print(f"分析が完了し、結果を {args.output} に保存しました")