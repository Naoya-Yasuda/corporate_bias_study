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

# 共通ユーティリティをインポート
from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks
from src.utils.plot_utils import plot_delta_ranks, plot_market_impact
from src.utils.file_utils import ensure_dir
from src.utils.metrics_utils import calculate_hhi, apply_bias_to_share
from src.utils.storage_utils import save_json, save_figure

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
    tau = compute_tau(g_top_k, p_top_k)

    # ΔRank計算（Google - PPLX）
    delta_ranks = compute_delta_ranks(g_top_k, p_top_k)

    # 共通アイテムを計算
    common_items = list(set(g_top_k).intersection(set(p_top_k)))

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
# 引用リンク (Citations) 分析関数
# -------------------------------------------------------------------
def analyze_citations_from_file(citations_file, output_dir=None, verbose=False):
    """
    引用リンク (Citations) データファイルを分析

    Parameters
    ----------
    citations_file : str
        引用リンクデータのJSONファイルパス
    output_dir : str, optional
        分析結果の出力ディレクトリ
    verbose : bool, optional
        詳細な出力を表示するかどうか

    Returns
    -------
    dict
        分析結果
    """
    if verbose:
        print(f"引用リンクデータファイル {citations_file} の分析を開始します")

    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = "results/analysis/citations"

    ensure_dir(output_dir)

    if verbose:
        print(f"出力ディレクトリ: {output_dir}")

    # ファイルの読み込み
    try:
        with open(citations_file, "r", encoding="utf-8") as f:
            citations_data = json.load(f)
            if verbose:
                print(f"引用リンクデータを読み込みました（サイズ: {len(json.dumps(citations_data))} バイト）")
    except Exception as e:
        print(f"引用リンクデータファイルの読み込みに失敗しました: {e}")
        return None

    # 分析結果を格納する辞書
    analysis_results = {}

    # カテゴリとサブカテゴリの分析
    for category, subcategories in citations_data.items():
        if verbose:
            print(f"カテゴリ {category} の分析を開始します")

        analysis_results[category] = {}

        for subcategory, data in subcategories.items():
            if verbose:
                print(f"  サブカテゴリ {subcategory} の分析を開始します")

            # サブカテゴリごとの分析結果
            subcategory_analysis = {
                "citation_metrics": {},
                "domain_distribution": {},
                "summary": {}
            }

            # 複数回実行の場合（all_runsキーがある場合）
            if "all_runs" in data:
                # ドメインごとの出現回数と平均順位を分析
                domain_stats = defaultdict(lambda: {"count": 0, "ranks": []})
                total_citations = 0
                successful_runs = 0

                for run in data["all_runs"]:
                    citations = run.get("citations", [])
                    if citations:
                        successful_runs += 1
                        total_citations += len(citations)

                        for citation in citations:
                            domain = citation.get("domain", "unknown")
                            rank = citation.get("rank", 0)
                            domain_stats[domain]["count"] += 1
                            domain_stats[domain]["ranks"].append(rank)

                # ドメイン分布の計算
                domain_distribution = []
                for domain, stats in domain_stats.items():
                    avg_rank = sum(stats["ranks"]) / len(stats["ranks"]) if stats["ranks"] else 0
                    frequency = stats["count"] / total_citations if total_citations > 0 else 0
                    domain_distribution.append({
                        "domain": domain,
                        "count": stats["count"],
                        "frequency": frequency,
                        "avg_rank": avg_rank
                    })

                # ドメイン分布を平均ランクでソート
                domain_distribution.sort(key=lambda x: x["avg_rank"])

                # メトリクスの計算
                citation_metrics = {
                    "total_citations": total_citations,
                    "successful_runs": successful_runs,
                    "avg_citations_per_run": total_citations / successful_runs if successful_runs > 0 else 0,
                    "unique_domains": len(domain_stats)
                }

                # 分析結果の保存
                subcategory_analysis["citation_metrics"] = citation_metrics
                subcategory_analysis["domain_distribution"] = domain_distribution
                subcategory_analysis["summary"] = {
                    "query": data.get("query", ""),
                    "top_domains": [d["domain"] for d in domain_distribution[:5]],
                    "run_success_rate": successful_runs / len(data["all_runs"]) if data["all_runs"] else 0
                }

                # ドメイン分布の可視化（上位10ドメイン）
                if domain_distribution:
                    top_domains = domain_distribution[:10]
                    domain_names = [d["domain"] for d in top_domains]
                    frequencies = [d["frequency"] * 100 for d in top_domains]  # パーセンテージに変換

                    plt.figure(figsize=(10, 6))
                    bars = plt.barh(domain_names, frequencies, color='skyblue')
                    plt.xlabel('引用頻度 (%)')
                    plt.ylabel('ドメイン')
                    plt.title(f'{subcategory} の引用ドメイン分布')
                    plt.tight_layout()

                    # 各バーに値をラベル付け
                    for i, bar in enumerate(bars):
                        plt.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                                f"{frequencies[i]:.1f}%", va='center')

                    # グラフを保存
                    plot_path = os.path.join(output_dir, f"{category}_{subcategory}_domain_distribution.png")
                    plt.savefig(plot_path, dpi=100)
                    plt.close()

                    subcategory_analysis["plots"] = {
                        "domain_distribution": plot_path
                    }

            # 単一実行の場合（runキーがある場合）
            elif "run" in data:
                run = data["run"]
                citations = run.get("citations", [])

                # ドメインカウントの計算
                domain_counts = {}
                for citation in citations:
                    domain = citation.get("domain", "unknown")
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1

                # ドメイン分布の作成
                domain_distribution = []
                total_citations = len(citations)
                for domain, count in domain_counts.items():
                    frequency = count / total_citations if total_citations > 0 else 0
                    domain_distribution.append({
                        "domain": domain,
                        "count": count,
                        "frequency": frequency
                    })

                # ドメイン分布をカウントでソート
                domain_distribution.sort(key=lambda x: x["count"], reverse=True)

                # メトリクスの計算
                citation_metrics = {
                    "total_citations": total_citations,
                    "unique_domains": len(domain_counts)
                }

                # 分析結果の保存
                subcategory_analysis["citation_metrics"] = citation_metrics
                subcategory_analysis["domain_distribution"] = domain_distribution
                subcategory_analysis["summary"] = {
                    "query": data.get("query", ""),
                    "top_domains": [d["domain"] for d in domain_distribution[:5]]
                }

            # サブカテゴリの分析結果を追加
            analysis_results[category][subcategory] = subcategory_analysis

    # 全体の分析結果をJSONに保存
    result_path = os.path.join(output_dir, "citations_analysis.json")
    save_json(analysis_results, result_path)
    if verbose:
        print(f"分析結果を {result_path} に保存しました")

    # 分析結果のサマリーを出力
    print("\n=== 引用リンク分析結果サマリー ===")
    for category, subcategories in analysis_results.items():
        print(f"\nカテゴリ: {category}")

        for subcategory, analysis in subcategories.items():
            metrics = analysis.get("citation_metrics", {})
            summary = analysis.get("summary", {})

            print(f"  サブカテゴリ: {subcategory}")
            print(f"    引用数: {metrics.get('total_citations', 0)}")
            print(f"    ユニークドメイン: {metrics.get('unique_domains', 0)}")

            if "top_domains" in summary and summary["top_domains"]:
                print(f"    トップドメイン: {', '.join(summary['top_domains'][:3])}")

            if "run_success_rate" in summary:
                print(f"    成功率: {summary['run_success_rate']*100:.1f}%")

    return analysis_results

# -------------------------------------------------------------------
# PerplexityとGoogle SERPの比較
# -------------------------------------------------------------------
def is_citations_data(pplx_data):
    """
    与えられたデータが引用リンク（citations）データかどうかを判定

    Parameters
    ----------
    pplx_data : dict
        Perplexityの結果データ

    Returns
    -------
    bool
        引用リンクデータならTrue、そうでなければFalse
    """
    # 引用リンクデータの特徴を確認
    if isinstance(pplx_data, dict):
        for subcategory, data in pplx_data.items():
            # 引用リンクデータは'citations'または'all_citations'を持つ
            if 'citations' in data or 'all_citations' in data or 'domain_rankings' in data:
                return True
    return False

def extract_domains_from_citations(citations_data, subcategory):
    """
    引用リンクデータからドメインのランキングを抽出

    Parameters
    ----------
    citations_data : dict
        引用リンクデータ
    subcategory : str
        サブカテゴリ名

    Returns
    -------
    list
        ドメインのリスト（順位順）
    """
    if subcategory not in citations_data:
        return []

    data = citations_data[subcategory]

    # 複数回実行の結果がある場合（domain_rankingsがある場合）
    if 'domain_rankings' in data:
        # 平均ランクでソート済みのドメインリストを使用
        return [item['domain'] for item in data['domain_rankings']]

    # 単一実行の場合
    elif 'citations' in data:
        # すでに順序付けされたcitationsからドメインを抽出
        domains = []
        for citation in data['citations']:
            domain = citation.get('domain')
            if domain and domain not in domains:
                domains.append(domain)
        return domains

    # 'domains'キーが直接ある場合
    elif 'domains' in data:
        return data['domains']

    return []

def compare_with_perplexity(serp_results, pplx_results):
    """
    Google検索結果とPerplexity APIの結果を比較
    ランキングデータと引用リンク（citations）データの両方に対応

    Parameters
    ----------
    serp_results : dict
        Google検索結果の辞書
    pplx_results : dict
        Perplexity APIの結果辞書

    Returns
    -------
    dict
        比較結果
    """
    # 結果を保存する辞書
    comparison = {}

    # Perplexityデータの種類を判定
    is_citations = is_citations_data(pplx_results)

    print(f"Perplexityデータタイプ: {'引用リンク(citations)' if is_citations else 'ランキング'}")

    # カテゴリごとに比較
    categories = set(serp_results.keys()) & set(pplx_results.keys())

    for category in categories:
        google_data = serp_results[category]
        pplx_data = pplx_results[category]

        # Googleからランキングを抽出
        google_ranking = [r.get("company") for r in google_data.get("results", [])]

        # Perplexityからランキングを抽出
        if is_citations:
            # 引用リンクデータからドメインランキングを抽出
            pplx_domains = extract_domains_from_citations(pplx_data, list(pplx_data.keys())[0] if pplx_data else "")
            pplx_ranking = pplx_domains
        else:
            # 通常のランキングデータを処理
            pplx_rankings = []
            for run in pplx_data.get("runs", []):
                run_ranking = []
                for rank_entry in run.get("ranking", []):
                    company = rank_entry.get("company")
                    if company:
                        run_ranking.append(company)
                if run_ranking:
                    pplx_rankings.append(run_ranking)

            # 複数実行の場合は最初のランキングを使用
            pplx_ranking = pplx_rankings[0] if pplx_rankings else []

        # ランキング比較メトリクスを計算
        metrics = compute_ranking_metrics(google_ranking, pplx_ranking)

        # GoogleとPerplexityのコンテンツメトリクスを計算
        google_content = compute_content_metrics(google_data.get("results", []))
        pplx_content = {}  # Perplexityにはコンテンツ情報がない場合が多い

        # 結果を保存
        comparison[category] = {
            "google_ranking": google_ranking,
            "pplx_ranking": pplx_ranking,
            "ranking_metrics": metrics,
            "google_content_metrics": google_content,
            "pplx_content_metrics": pplx_content,
            "data_type": "citations" if is_citations else "rankings"
        }

    return comparison

# -------------------------------------------------------------------
# 分析実行関数
# -------------------------------------------------------------------
def analyze_serp_results(serp_results, pplx_results, comparison_results):
    """
    Google SERP結果とPerplexity結果の比較分析を実行

    Parameters
    ----------
    serp_results : dict
        Google検索結果
    pplx_results : dict
        Perplexity API結果
    comparison_results : dict
        比較結果

    Returns
    -------
    dict
        分析結果
    """
    analysis = {}

    # 市場シェアデータの読み込み
    try:
        market_shares_path = "src/data/market_shares.json"
        if os.path.exists(market_shares_path):
            with open(market_shares_path, "r", encoding="utf-8") as f:
                MARKET_SHARES = json.load(f)
                print(f"市場シェアデータを {market_shares_path} から読み込みました")
        else:
            # ranking_metrics.pyからインポート（フォールバック）
            from src.analysis.ranking_metrics import MARKET_SHARES
            print("ranking_metrics.pyから市場シェアデータを使用します")
    except Exception as e:
        print(f"市場シェアデータの読み込みに失敗しました: {e}")
        # ranking_metrics.pyからインポート（フォールバック）
        from src.analysis.ranking_metrics import MARKET_SHARES
        print("エラーのため、ranking_metrics.pyから市場シェアデータを使用します")

    # カテゴリごとに分析
    categories = set(comparison_results.keys()) & set(MARKET_SHARES.keys())

    for category in categories:
        comp_data = comparison_results[category]
        market_share = MARKET_SHARES.get(category, {})

        if not market_share:
            print(f"カテゴリ {category} の市場シェアデータがありません。スキップします。")
            continue

        delta_ranks = comp_data["ranking_metrics"]["delta_ranks"]

        # 市場シェアへの影響をシミュレーション
        adjusted_share = apply_bias_to_share(market_share, delta_ranks)

        # ΔRankと市場影響度の集計
        impact_data = []
        for company in set(market_share.keys()) & set(delta_ranks.keys()):
            impact_data.append({
                "company": company,
                "delta_rank": delta_ranks.get(company, 0),
                "market_share_before": market_share.get(company, 0) * 100,
                "market_share_after": adjusted_share.get(company, 0) * 100,
                "share_change_pct": (adjusted_share.get(company, 0) / market_share.get(company, 0) - 1) * 100 if market_share.get(company, 0) > 0 else 0
            })

        impact_df = pd.DataFrame(impact_data)

        # グラフの生成と保存
        output_dir = "results/analysis"
        ensure_dir(output_dir)

        # delta_ranksグラフ（上位10社）
        delta_plot_path = plot_delta_ranks(delta_ranks, output_path=f"{output_dir}/{category}_delta_ranks.png")

        # 市場影響グラフ
        market_plot_path = plot_market_impact(market_share, adjusted_share, output_path=f"{output_dir}/{category}_market_impact.png")

        # 分析結果の保存
        analysis[category] = {
            "ranking_similarity": {
                "rbo": comp_data["ranking_metrics"]["rbo"],
                "kendall_tau": comp_data["ranking_metrics"]["kendall_tau"],
                "overlap_ratio": comp_data["ranking_metrics"]["overlap_ratio"]
            },
            "content_comparison": {
                "google_official_ratio": comp_data["google_content_metrics"]["official_ratio"],
                "google_negative_ratio": comp_data["google_content_metrics"]["negative_ratio"]
            },
            "market_impact": {
                "market_share": market_share,
                "adjusted_share": adjusted_share,
                "delta_ranks": delta_ranks,
                "impact_data": impact_data
            },
            "plots": {
                "delta_ranks_plot": delta_plot_path,
                "market_impact_plot": market_plot_path
            }
        }

    return analysis

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