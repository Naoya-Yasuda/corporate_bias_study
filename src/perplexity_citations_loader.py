#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIの引用リンクを取得するモジュール

Perplexity APIを呼び出し、回答に含まれる引用リンクを順番に取得します。
"""

import os
import json
import datetime
import time
import argparse
from dotenv import load_dotenv
from urllib.parse import urlparse
from collections import defaultdict

# 共通ユーティリティをインポート
from src.utils import (
    extract_domain,
    ensure_dir,
    save_json_data,
    get_today_str,
    is_s3_enabled,
    get_storage_config,
    get_results_paths
)
from src.categories import get_categories, get_all_categories

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PPLX_API_KEY = os.environ.get("PERPLEXITY_API_KEY")


def perplexity_api(query, model="llama-3.1-sonar-large-128k-online"):
    """
    Perplexity APIを使用して回答と引用を取得

    Parameters:
    -----------
    query : str
        検索クエリ
    model : str
        使用するモデル (sonar-small-chatなど)

    Returns:
    --------
    tuple (str, list)
        (回答テキスト, 引用のリスト)
    """
    import requests

    if not PPLX_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "あなたは役立つアシスタントです。引用元のリンクを含めて回答してください。"},
            {"role": "user", "content": query}
        ],
        "temperature": 0.0
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
        citations = data.get("choices", [{}])[0].get("message", {}).get("citations", [])

        return answer, citations
    except Exception as e:
        print(f"Perplexity API 呼び出しエラー: {e}")
        return None, []


def collect_citation_rankings(categories, num_runs=1):
    """
    各カテゴリ・サブカテゴリごとに引用リンクのランキングを取得

    Args:
        categories: カテゴリとサービスの辞書
        num_runs: 実行回数（複数回実行で平均を取る場合）

    Returns:
        dict: カテゴリごとの引用リンクランキング結果
    """
    results = {}

    total_categories = get_all_categories()
    processed = 0

    for category, subcategories in categories.items():
        print(f"カテゴリ処理中: {category}")
        results[category] = {}

        for subcategory, services in subcategories.items():
            processed += 1
            print(f"サブカテゴリ処理中 ({processed}/{total_categories}): {subcategory}, サービス数: {len(services)}")

            if not services or subcategory.startswith('#'):  # コメントアウトされたカテゴリは無視
                print(f"  サブカテゴリ {subcategory} はスキップします（コメントアウトまたは空）")
                continue

            subcategory_results = []

            # 検索クエリの生成
            query = f"日本における{subcategory}の主要な{len(services)}社について、それぞれの特徴や強み、提供サービスについて詳しく教えてください。"

            for run in range(num_runs):
                if num_runs > 1:
                    print(f"  実行 {run+1}/{num_runs}")

                # API呼び出し
                print(f"  検索クエリ: {query}")
                answer, citations = perplexity_api(query)

                if not answer:
                    print("  ⚠️ 警告: APIからの応答が取得できませんでした")
                    continue

                print(f"  Perplexityからの応答:\n{answer[:200]}...")  # 応答の一部を表示

                # 引用リンクの処理
                citation_data = []

                for i, citation in enumerate(citations):
                    url = citation.get("url", "")
                    if url:
                        domain = extract_domain(url)
                        citation_data.append({
                            "rank": i + 1,  # 1-indexed
                            "url": url,
                            "domain": domain,
                            "title": citation.get("title", "")
                        })

                if citation_data:
                    subcategory_results.append(citation_data)
                    print(f"  ✓ 引用リンク抽出完了: {len(citation_data)}件")

                    # 抽出したドメインのリストを表示
                    domains = [item["domain"] for item in citation_data]
                    print(f"  抽出ドメイン: {domains}")
                else:
                    print("  ⚠️ 警告: 引用リンクが見つかりませんでした")

                # API制限を考慮した待機
                if run < num_runs - 1 or processed < total_categories:
                    print("  APIレート制限を考慮して待機中...")
                    time.sleep(3)

            # 複数回実行の場合の集計
            if num_runs > 1 and subcategory_results:
                # ドメインごとの出現回数と平均順位を集計
                domain_stats = defaultdict(lambda: {"appearances": 0, "rank_sum": 0, "ranks": []})

                for run_result in subcategory_results:
                    for citation in run_result:
                        domain = citation["domain"]
                        rank = citation["rank"]
                        domain_stats[domain]["appearances"] += 1
                        domain_stats[domain]["rank_sum"] += rank
                        domain_stats[domain]["ranks"].append(rank)

                # 平均順位を計算
                domain_rankings = []
                for domain, stats in domain_stats.items():
                    avg_rank = stats["rank_sum"] / stats["appearances"]
                    appearance_ratio = stats["appearances"] / num_runs
                    domain_rankings.append({
                        "domain": domain,
                        "avg_rank": avg_rank,
                        "appearance_ratio": appearance_ratio,
                        "appearances": stats["appearances"],
                        "all_ranks": stats["ranks"]
                    })

                # 平均順位でソート
                domain_rankings.sort(key=lambda x: x["avg_rank"])

                results[category][subcategory] = {
                    "query": query,
                    "all_citations": subcategory_results,
                    "domain_rankings": domain_rankings
                }
            elif subcategory_results:  # 単一実行の場合
                # ドメインのランキングを抽出
                domains = []
                for citation in subcategory_results[0]:
                    domain = citation["domain"]
                    if domain not in domains:
                        domains.append(domain)

                results[category][subcategory] = {
                    "query": query,
                    "citations": subcategory_results[0],
                    "domains": domains
                }

    return results


def save_results(result_data, run_type="single", num_runs=1):
    """結果をローカルとS3に保存（新しいストレージAPI使用）"""
    # 日付を取得
    today_date = get_today_str()

    # ファイル名の生成
    if run_type == "multiple":
        file_name = f"{today_date}_perplexity_citations_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_perplexity_citations.json"

    # パスの取得
    local_path, s3_path = get_results_paths("perplexity_citations", today_date, file_name)

    # ストレージ設定の取得（デバッグ用）
    storage_config = get_storage_config()
    print(f"ストレージ設定: {storage_config}")

    # 保存
    result = save_json_data(result_data, local_path, s3_path)

    if result["local"]:
        print(f"ローカルに保存しました: {local_path}")
    if result["s3"]:
        print(f"S3に保存しました: s3://{s3_path}")

    return local_path


def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexity APIを使用して引用リンクのランキングを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--no-analysis', action='store_true', help='ランキング分析を実行しない')
    args = parser.parse_args()

    # カテゴリとサービスの取得
    categories = get_categories()

    # 引用リンクのランキングを取得
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回の引用リンク取得を実行します")
        result = collect_citation_rankings(categories, args.runs)
        save_results(result, "multiple", args.runs)
    else:
        print("Perplexity APIを使用して単一実行の引用リンク取得を実行します")
        result = collect_citation_rankings(categories)
        save_results(result)

    print("引用リンク取得処理が完了しました")

    # 将来的には引用リンクの分析もここに実装予定
    if not args.no_analysis:
        print("\n注: 現在のバージョンでは引用リンクの自動分析は実装されていません。")


if __name__ == "__main__":
    main()