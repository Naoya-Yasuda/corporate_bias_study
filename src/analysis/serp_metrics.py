#!/usr/bin/env python
# coding: utf-8

"""
Google SERP とPerplexity の結果を比較して分析するためのメトリクスモジュール
"""

import os
import json
import matplotlib.pyplot as plt
from collections import defaultdict

# 共通ユーティリティをインポート
try:
    from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks
    RANK_UTILS_AVAILABLE = True
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"rank_utils インポートエラー: {e}")
    RANK_UTILS_AVAILABLE = False

    # フォールバック関数を定義
    def rbo(list1, list2, p=0.9):
        """RBOのフォールバック実装"""
        return 0.0

    def compute_tau(list1, list2):
        """Kendall's tauのフォールバック実装"""
        return 0.0

    def compute_delta_ranks(list1, list2):
        """Delta ranksのフォールバック実装"""
        return {}

from src.utils.storage_utils import ensure_dir, get_today_str
from src.utils.storage_utils import save_json, get_results_paths, get_s3_client, S3_BUCKET_NAME, get_s3_key_path

# -------------------------------------------------------------------
# 比較メトリクス
# -------------------------------------------------------------------
def compute_ranking_metrics(google_ranking, pplx_ranking, max_k=10):
    """
    エラーハンドリングを強化したランキングメトリクス計算

    Parameters
    ----------
    google_ranking : list
        Googleの検索結果ランキング（ドメインのリスト）
    pplx_ranking : list
        Perplexityの引用ランキング（ドメインのリスト）
    max_k : int
        比較する上位ランキング数

    Returns
    -------
    dict
        類似度メトリクス
    """
    try:
        # 入力検証
        if not google_ranking or not pplx_ranking:
            return {
                "rbo": 0.0, "kendall_tau": 0.0, "overlap_ratio": 0.0,
                "delta_ranks": {}, "google_domains": [], "pplx_domains": [],
                "error": "入力データが空です", "rank_utils_used": RANK_UTILS_AVAILABLE
            }

        # 上位k件に制限
        google_top_k = google_ranking[:max_k]
        pplx_top_k = pplx_ranking[:max_k]

        # 重複ドメインの削除（順序保持）
        google_unique = []
        seen = set()
        for domain in google_top_k:
            if domain not in seen and domain:
                google_unique.append(domain)
                seen.add(domain)

        pplx_unique = []
        seen = set()
        for domain in pplx_top_k:
            if domain not in seen and domain:
                pplx_unique.append(domain)
                seen.add(domain)

        # 重複率計算（常に実行可能）
        google_set = set(google_unique)
        pplx_set = set(pplx_unique)
        overlap = len(google_set & pplx_set)
        union = len(google_set | pplx_set)
        overlap_ratio = overlap / union if union > 0 else 0

        # rank_utils関数の安全な呼び出し
        if RANK_UTILS_AVAILABLE:
            rbo_score = rbo(google_unique, pplx_unique, p=0.9)
            kendall_tau_score = compute_tau(google_unique, pplx_unique)
            delta_ranks = compute_delta_ranks(google_unique, pplx_unique)
        else:
            # フォールバック処理
            rbo_score = 0.0
            kendall_tau_score = 0.0
            delta_ranks = {}

        return {
            "rbo": rbo_score,
            "kendall_tau": kendall_tau_score,
            "overlap_ratio": overlap_ratio,
            "delta_ranks": delta_ranks,
            "google_domains": google_unique,
            "pplx_domains": pplx_unique,
            "rank_utils_used": RANK_UTILS_AVAILABLE
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"compute_ranking_metrics実行エラー: {e}")

        # 最小限の結果を返す
        return {
            "rbo": None, "kendall_tau": None, "overlap_ratio": 0.0,
            "delta_ranks": {}, "google_domains": [], "pplx_domains": [],
            "error": str(e), "fallback_used": True, "rank_utils_used": RANK_UTILS_AVAILABLE
        }

def compute_content_metrics(search_detailed_results, top_k=10):
    """
    検索の詳細結果から公式/非公式、ポジ/ネガ比率などを計算

    Parameters
    ----------
    search_detailed_results : list
        検索の詳細検索結果リスト
    top_k : int
        分析対象の上位結果数

    Returns
    -------
    dict
        コンテンツメトリクス
    """
    results = search_detailed_results[:top_k]

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
    引用リンクファイルから分析を実行

    Parameters
    ----------
    citations_file : str
        引用リンクファイルのパス
    output_dir : str, optional
        出力ディレクトリ
    verbose : bool, optional
        詳細ログの出力

    Returns
    -------
    dict
        分析結果
    """
    if verbose:
        print(f"引用リンク分析を開始: {citations_file}")

    # ファイル読み込み
    try:
        with open(citations_file, 'r', encoding='utf-8') as f:
            citations_data = json.load(f)
    except Exception as e:
        print(f"ファイル読み込みエラー: {e}")
        return None

    if verbose:
        print(f"データ読み込み完了: {len(citations_data)}カテゴリ")

    analysis_results = {}

    # カテゴリごとに分析
    for category, subcategories in citations_data.items():
        if verbose:
            print(f"カテゴリ分析中: {category}")

        category_results = {}

        for subcategory, data in subcategories.items():
            if verbose:
                print(f"  サブカテゴリ: {subcategory}")

            # 引用メトリクスの計算
            citation_metrics = compute_citation_metrics(data)
            category_results[subcategory] = citation_metrics

        analysis_results[category] = category_results

    # 結果の保存
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "citation_analysis.json")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)

        if verbose:
            print(f"分析結果を保存: {output_file}")

    return analysis_results

def process_perplexity_citations(citations_data, output_dir=None, verbose=False):
    """
    Perplexity引用データの処理と分析

    Parameters
    ----------
    citations_data : dict
        引用データ
    output_dir : str, optional
        出力ディレクトリ
    verbose : bool, optional
        詳細ログの出力

    Returns
    -------
    dict
        分析結果
    """
    if verbose:
        print("Perplexity引用データの処理を開始")

    analysis_results = {}

    # カテゴリごとに処理
    for category, subcategories in citations_data.items():
        if verbose:
            print(f"処理中: {category}")

        category_results = {}

        for subcategory, data in subcategories.items():
            # 引用メトリクスの計算
            metrics = compute_citation_metrics(data)
            category_results[subcategory] = metrics

        analysis_results[category] = category_results

    return analysis_results

def process_entities_citations(entities_data, output_dir=None, verbose=False):
    """
    Entitiesベースの引用データの処理

    Parameters
    ----------
    entities_data : dict
        entitiesベースの引用データ
    output_dir : str, optional
        出力ディレクトリ
    verbose : bool, optional
        詳細ログの出力

    Returns
    -------
    dict
        処理結果
    """
    if verbose:
        print("Entitiesベース引用データの処理を開始")

    processed_results = {}

    # カテゴリごとに処理
    for category, subcategories in entities_data.items():
        if verbose:
            print(f"処理中: {category}")

        category_results = {}

        for subcategory, content in subcategories.items():
            # entities構造の処理
            entities = content.get("entities", {})

            subcategory_results = {
                "timestamp": content.get("timestamp"),
                "category": content.get("category"),
                "subcategory": content.get("subcategory"),
                "entities_analysis": {}
            }

            for entity_name, entity_data in entities.items():
                # 各エンティティの引用分析
                official_results = entity_data.get("official_results", [])
                reputation_results = entity_data.get("reputation_results", [])

                entity_analysis = {
                    "official_count": len(official_results),
                    "reputation_count": len(reputation_results),
                    "total_results": len(official_results) + len(reputation_results),
                    "domains": {
                        "official": [r.get("domain") for r in official_results if r.get("domain")],
                        "reputation": [r.get("domain") for r in reputation_results if r.get("domain")]
                    }
                }

                subcategory_results["entities_analysis"][entity_name] = entity_analysis

            category_results[subcategory] = subcategory_results

        processed_results[category] = category_results

    return processed_results

# -------------------------------------------------------------------
# PerplexityとGoogle検索の比較
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
    引用データからドメインのランキングを抽出

    Parameters
    ----------
    citations_data : dict
        引用データ
    subcategory : str
        サブカテゴリ名

    Returns
    -------
    list
        ドメインのランキングリスト
    """
    if subcategory not in citations_data:
        return []

    data = citations_data[subcategory]

    # 複数回実行の場合
    if "all_runs" in data:
        domain_rankings = data.get("domain_rankings", [])
        return [item["domain"] for item in domain_rankings]

    # 単一実行の場合
    elif "run" in data:
        citations = data["run"].get("citations", [])
        return [citation["domain"] for citation in citations]

    return []

def compare_with_perplexity(search_search, pplx_results):
    """
    Google検索結果とPerplexity APIの結果を比較
    引用リンク（citations）データを使用

    Parameters
    ----------
    search_search : dict
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

    # カテゴリごとに比較
    categories = set(search_search.keys()) & set(pplx_results.keys())

    for category in categories:
        google_data = search_search[category]
        pplx_data = pplx_results[category]

        # Googleからドメインランキングを抽出
        google_domains = [r.get("domain") for r in google_data.get("results", [])]

        # Perplexityからドメインランキングを抽出
        pplx_domains = []
        if "all_runs" in pplx_data:
            # 複数回実行の場合
            domain_rankings = pplx_data.get("domain_rankings", [])
            pplx_domains = [item["domain"] for item in domain_rankings]
        elif "run" in pplx_data:
            # 単一実行の場合
            citations = pplx_data["run"].get("citations", [])
            pplx_domains = [citation["domain"] for citation in citations]

        # ランキング比較メトリクスを計算
        metrics = compute_ranking_metrics(google_domains, pplx_domains)

        # GoogleとPerplexityのコンテンツメトリクスを計算
        google_content = compute_content_metrics(google_data.get("results", []))

        # Perplexityの引用メトリクスを計算
        pplx_content = compute_citation_metrics(pplx_data)

        # 結果を保存
        comparison[category] = {
            "google_domains": google_domains,
            "pplx_domains": pplx_domains,
            "ranking_metrics": metrics,
            "google_content_metrics": google_content,
            "pplx_content_metrics": pplx_content,
            "data_type": "citations"
        }

    return comparison

def compute_citation_metrics(pplx_data):
    """
    Perplexityの引用データからメトリクスを計算

    Parameters
    ----------
    pplx_data : dict
        Perplexityの引用データ

    Returns
    -------
    dict
        引用メトリクス
    """
    metrics = {
        "total_citations": 0,
        "unique_domains": 0,
        "citation_quality": {
            "with_snippet": 0,
            "with_last_modified": 0,
            "with_context": 0
        },
        "domain_distribution": []
    }

    # 複数回実行の場合
    if "all_runs" in pplx_data:
        all_citations = []
        for run_data in pplx_data["all_runs"]:
            citations = run_data.get("citations", [])
            all_citations.extend(citations)

        metrics["total_citations"] = len(all_citations)
        metrics["unique_domains"] = len(set(c.get("domain", "unknown") for c in all_citations))
        metrics["citation_quality"]["with_snippet"] = sum(1 for c in all_citations if c.get("snippet"))
        metrics["citation_quality"]["with_last_modified"] = sum(1 for c in all_citations if c.get("last_modified"))
        metrics["citation_quality"]["with_context"] = sum(1 for c in all_citations if c.get("context"))

        # ドメイン分布の作成
        domain_stats = defaultdict(lambda: {"count": 0, "snippets": 0, "last_modified": 0})
        for citation in all_citations:
            domain = citation.get("domain", "unknown")
            domain_stats[domain]["count"] += 1
            if citation.get("snippet"):
                domain_stats[domain]["snippets"] += 1
            if citation.get("last_modified"):
                domain_stats[domain]["last_modified"] += 1

        for domain, stats in domain_stats.items():
            metrics["domain_distribution"].append({
                "domain": domain,
                "count": stats["count"],
                "snippet_ratio": stats["snippets"] / stats["count"] if stats["count"] > 0 else 0,
                "last_modified_ratio": stats["last_modified"] / stats["count"] if stats["count"] > 0 else 0
            })

    elif "run" in pplx_data:
        # 単一実行の場合
        citations = pplx_data["run"].get("citations", [])
        metrics["total_citations"] = len(citations)
        metrics["unique_domains"] = len(set(c.get("domain", "unknown") for c in citations))
        metrics["citation_quality"]["with_snippet"] = sum(1 for c in citations if c.get("snippet"))
        metrics["citation_quality"]["with_last_modified"] = sum(1 for c in citations if c.get("last_modified"))
        metrics["citation_quality"]["with_context"] = sum(1 for c in citations if c.get("context"))

        # ドメイン分布の作成
        domain_counts = defaultdict(int)
        for citation in citations:
            domain = citation.get("domain", "unknown")
            domain_counts[domain] += 1

        for domain, count in domain_counts.items():
            metrics["domain_distribution"].append({
                "domain": domain,
                "count": count
            })

    return metrics

# -------------------------------------------------------------------
# 分析実行関数
# -------------------------------------------------------------------
def analyze_search_results(search_search, pplx_results, comparison_results):
    """
    Google検索結果とPerplexity結果の比較分析を実行

    Parameters
    ----------
    search_search : dict
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
            from src.analysis.ranking_metrics import get_market_shares
            MARKET_SHARES = get_market_shares()
            print("ranking_metrics.pyから市場シェアデータを使用します")
    except Exception as e:
        print(f"市場シェアデータの読み込みに失敗しました: {e}")
        # ranking_metrics.pyからインポート（フォールバック）
        from src.analysis.ranking_metrics import get_market_shares
        MARKET_SHARES = get_market_shares()
        print("エラーのため、ranking_metrics.pyから市場シェアデータを使用します")

    # カテゴリごとに分析
    for category in comparison_results.keys():
        comp_data = comparison_results[category]
        delta_ranks = comp_data["ranking_metrics"]["delta_ranks"]

        # 引用メトリクスの分析
        pplx_metrics = comp_data["pplx_content_metrics"]
        google_metrics = comp_data["google_content_metrics"]

        # 分析結果の保存
        analysis[category] = {
            "ranking_similarity": {
                "rbo": comp_data["ranking_metrics"]["rbo"],
                "kendall_tau": comp_data["ranking_metrics"]["kendall_tau"],
                "overlap_ratio": comp_data["ranking_metrics"]["overlap_ratio"]
            },
            "citation_analysis": {
                "total_citations": pplx_metrics["total_citations"],
                "unique_domains": pplx_metrics["unique_domains"],
                "citation_quality": pplx_metrics["citation_quality"],
                "top_domains": [d["domain"] for d in pplx_metrics["domain_distribution"][:5]]
            },
            "content_comparison": {
                "google_official_ratio": google_metrics["official_ratio"],
                "google_negative_ratio": google_metrics["negative_ratio"]
            }
        }

        # グラフの生成と保存
        output_dir = "results/perplexity_analysis"
        ensure_dir(output_dir)

        # ドメイン分布の可視化
        if pplx_metrics["domain_distribution"]:
            plt.figure(figsize=(10, 6))
            top_domains = pplx_metrics["domain_distribution"][:10]
            domains = [d["domain"] for d in top_domains]
            counts = [d["count"] for d in top_domains]

            plt.barh(domains, counts)
            plt.xlabel('引用回数')
            plt.ylabel('ドメイン')
            plt.title(f'{category} の引用ドメイン分布')
            plt.tight_layout()

            plot_path = f"{output_dir}/{category}_citation_distribution.png"
            plt.savefig(plot_path)
            plt.close()

            analysis[category]["plots"] = {
                "citation_distribution": plot_path
            }

    return analysis

# CLIから直接実行する場合のエントリポイント
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google検索とPerplexityの結果を分析")
    parser.add_argument("--date", required=True, help="分析対象の日付（YYYYMMDD形式）")
    parser.add_argument("--runs", type=int, default=10, help="Perplexity API実行回数（デフォルト: 10）")
    parser.add_argument("--output", default="results/perplexity_analysis", help="出力ディレクトリ")
    args = parser.parse_args()

    date_str = args.date
    runs = args.runs

    # Google検索ファイルパス
    def resolve_path(date_str, data_type, file_type, runs=None):
        # ファイル名生成
        if data_type == "google_search" or data_type == "google":
            file_name = f"{date_str}_custom_search.json"
        elif data_type == "citations":
            if runs and runs > 1:
                file_name = f"{date_str}_perplexity_citations_{runs}runs.json"
            else:
                file_name = f"{date_str}_perplexity_citations.json"
        else:
            raise ValueError("未対応のdata_type")
        local_path = get_local_path(date_str, data_type, file_type)
        if os.path.exists(local_path):
            return local_path
        s3_key = get_s3_key_path(date_str, data_type, file_type)
        try:
            s3_client = get_s3_client()
            response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(response["Body"].read())
            print(f"S3からダウンロード: {local_path}")
            return local_path
        except Exception as e:
            print(f"ファイルが見つかりません: {local_path} / S3: {s3_key}")
            raise e

    search_file = resolve_path(date_str, "google_search", "google")
    pplx_file = resolve_path(date_str, "citations", "perplexity", runs)

    # JSONファイルを読み込み
    with open(search_file, "r", encoding="utf-8") as f:
        search_search = json.load(f)
    with open(pplx_file, "r", encoding="utf-8") as f:
        pplx_results = json.load(f)

    # 比較と分析
    comparison_results = compare_with_perplexity(search_search, pplx_results)
    analysis_results = analyze_search_results(search_search, pplx_results, comparison_results)

    # 結果をJSONに保存
    os.makedirs(args.output, exist_ok=True)
    with open(f"{args.output}/comparison_results.json", "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, ensure_ascii=False, indent=2)
    with open(f"{args.output}/analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2)
    print(f"分析が完了し、結果を {args.output} に保存しました")

def analyze_citations(citations_data, output_dir=None, date_str=None):
    if date_str is None:
        date_str = get_today_str()
    if output_dir is None:
        output_dir = get_results_paths(date_str)["analysis"]["citations"]

def analyze_s3_rankings(date_str=None, api_type="perplexity", output_dir=None, upload_results=True, verbose=False):
    if date_str is None:
        date_str = get_today_str()
    if output_dir is None:
        output_dir = get_results_paths(date_str)["perplexity_analysis"]