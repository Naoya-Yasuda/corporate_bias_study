#!/usr/bin/env python
# coding: utf-8

"""
Google Search Loader モジュール
Google Custom Search APIを使ってGoogle検索結果を取得し、Perplexityの結果と比較分析するためのモジュール
"""

import os
import datetime
import requests
import time
import argparse
from dotenv import load_dotenv
from tqdm import tqdm
from ..utils import (
    extract_domain,
    get_results_paths
)
from ..utils.storage_utils import get_results_paths, save_results
from ..utils.storage_config import get_s3_key
from ..categories import get_categories, get_all_categories

# 環境変数の読み込み
load_dotenv()

# Google Custom Search API の設定
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")

# S3 設定情報
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# カテゴリ・サービスの定義読み込み
categories = get_categories()

# -------------------------------------------------------------------
# ユーティリティ関数
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# Google Custom Search API 関連
# -------------------------------------------------------------------
def get_google_search_results(query, num_results=10):
    """
    Google Custom Search APIを使用して検索結果を取得する

    Parameters:
    -----------
    query : str
        検索クエリ
    num_results : int, optional
        取得する結果の数（デフォルト: 10）

    Returns:
    --------
    dict
        検索結果の辞書
    """
    try:
        # 環境変数からAPIキーを取得
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            raise ValueError("GOOGLE_API_KEY または GOOGLE_CSE_ID が設定されていません。.env ファイルを確認してください。")

        print(f"🔍 検索クエリ: {query}")

        # Google Custom Search APIのエンドポイント
        endpoint = "https://www.googleapis.com/customsearch/v1"

        # パラメータの設定
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": num_results,
            "gl": "jp",  # 日本向け検索
            "hl": "ja",   # 日本語結果
            "lr": "lang_ja"  # 日本語ページ限定
        }

        # APIリクエスト
        response = requests.get(endpoint, params=params)

        # レート制限エラーの場合
        if response.status_code == 429:
            print("⚠️ レート制限に達しました。60秒待機します...")
            time.sleep(60)  # 60秒待機
            response = requests.get(endpoint, params=params)  # 再試行

        response.raise_for_status()
        data = response.json()
        print(f"APIレスポンス: {data}")

        # 検索結果を整形
        results = {
            "organic_results": []
        }

        if "items" in data:
            for item in data["items"]:
                results["organic_results"].append({
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "snippet": item.get("snippet", ""),
                    "position": len(results["organic_results"]) + 1
                })
            print(f"✅ 検索結果: {len(results['organic_results'])}件")
        else:
            print("⚠️ 検索結果が見つかりませんでした")

        return results

    except Exception as e:
        print(f"❌ Google Custom Search API エラー: {e}")
        return {"organic_results": []}

def process_search_results(data):
    """Google Custom Search API の結果から必要な情報を抽出して整形"""
    if not data or "organic_results" not in data:
        return []
    organic_results = data["organic_results"]
    results = []
    for i, result in enumerate(organic_results):
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        domain = extract_domain(link)
        result_dict = {
            "rank": i + 1,
            "title": title,
            "link": link,
            "domain": domain,
            "snippet": snippet
        }
        results.append(result_dict)
    return results

def process_categories_with_search(categories, max_categories=None):
    """カテゴリごとにGoogle検索を実行し、entities属性の下に格納"""
    results = {}
    count = 0
    if max_categories:
        filtered_categories = {}
        for toplevel, subcats in categories.items():
            filtered_categories[toplevel] = {}
            for subcat, values in subcats.items():
                if count < max_categories:
                    filtered_categories[toplevel][subcat] = values
                    count += 1
        categories_to_process = filtered_categories
    else:
        categories_to_process = categories

    for category, subcategories in categories_to_process.items():
        results[category] = {}
        for subcategory, services in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            entities = {}
            for service in services:
                # 公式/非公式判定用の検索
                query = f"{service}"
                search_data = get_google_search_results(query, num_results=10)
                official_results = process_search_results(search_data) if search_data else []
                time.sleep(2)
                # 評判情報用の検索
                query_rep = f"{service} 評判 口コミ"
                search_data_rep = get_google_search_results(query_rep, num_results=10)
                reputation_results = process_search_results(search_data_rep) if search_data_rep else []
                time.sleep(2)
                entities[service] = {
                    "official_results": official_results,
                    "reputation_results": reputation_results,
                    "official_query": query,
                    "reputation_query": query_rep
                }
            # 結果を格納
            results[category][subcategory] = {
                "timestamp": datetime.datetime.now().isoformat(),
                "category": category,
                "subcategory": subcategory,
                "entities": entities
            }
    return results

# -------------------------------------------------------------------
# メイン関数
# -------------------------------------------------------------------
def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Google検索データを取得し、Perplexityとの比較分析を行う')
    parser.add_argument('--perplexity-date', type=str, help='使用するPerplexityデータの日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['rankings', 'citations'], default='citations',
                        help='比較するPerplexityデータのタイプ（デフォルト: citations）')
    parser.add_argument('--max', type=int, help='処理するカテゴリ数の上限')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # カテゴリとサービスの取得
    categories = get_categories()
    if args.max:
        # カテゴリ数の上限が指定されている場合は制限
        limited_categories = {}
        for i, (cat, subcat) in enumerate(categories.items()):
            if i >= args.max:
                break
            limited_categories[cat] = subcat
        categories = limited_categories
        if args.verbose:
            logging.info(f"カテゴリを{args.max}個に制限しました")

    # 日付を取得（指定がなければ今日の日付）
    perplexity_date = args.perplexity_date or datetime.datetime.now().strftime("%Y%m%d")
    if args.verbose:
        logging.info(f"Perplexity分析日付: {perplexity_date}, データタイプ: {args.data_type}")

    # Google検索結果を取得
    result = process_categories_with_search(categories, args.max)

    # 結果を保存
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    paths = get_results_paths(today_date)
    file_name = "custom_search.json"
    local_path = os.path.join(paths["raw_data"]["google"], file_name)
    s3_key = get_s3_key(file_name, today_date, "raw_data/google")
    save_results(result, local_path, s3_key, verbose=args.verbose)

    if args.verbose:
        logging.info(f"Google検索結果をファイルに保存しました: {local_path}")

if __name__ == "__main__":
    main()