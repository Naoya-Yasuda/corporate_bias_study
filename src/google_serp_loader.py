#!/usr/bin/env python
# coding: utf-8

"""
Google SERP Loader モジュール
SerpAPIを使ってGoogle検索結果を取得し、Perplexityの結果と比較分析するためのモジュール
"""

import os
import sys
import json
import datetime
import requests
import time
import argparse
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from tqdm import tqdm
from urllib.parse import urlparse
import tldextract

# 共通ユーティリティをインポート
from src.utils.text_utils import (
    extract_domain,
    is_negative,
    is_official_domain
)
from src.utils.file_utils import ensure_dir, get_today_str
from src.utils.storage_utils import save_json, get_local_path, get_s3_client, get_s3_key_path, get_latest_file, put_json_to_s3, get_results_paths

# プロジェクト固有のモジュール
from src.categories import get_categories

# 環境変数の読み込み
load_dotenv()

# SERP API の設定
SERP_API_KEY = os.environ.get("SERP_API_KEY")
API_HOST = "serpapi.com"

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
def save_results(results, type_str, local_path="results"):
    """結果を保存する（ローカルとS3）"""
    today = get_today_str()
    paths = get_results_paths(today)
    file_name = f"{today}_google_serp_results.json"
    local_file = os.path.join(paths["google_serp"], file_name)
    save_json(results, local_file)
    print(f"結果を {local_file} に保存しました")
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        s3_path = os.path.join(paths["google_serp"], file_name)
        if put_json_to_s3(results, s3_path):
            print(f"結果を S3 ({S3_BUCKET_NAME}/{s3_path}) に保存しました")
        else:
            print(f"S3への保存に失敗しました")
    return local_file

# -------------------------------------------------------------------
# SERP API 関連
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
        検索結果の辞書（SERP APIと互換性のある形式）
    """
    try:
        # 環境変数からAPIキーを取得
        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
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
            "hl": "ja"   # 日本語結果
            # 日本語ページのみに限定すると英語の有用な情報も除外されてしまうため、言語指定は行わない
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

        # 検索結果を整形（SERP APIと互換性のある形式に変換）
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

def process_serp_results(data):
    """SERP API の結果から必要な情報を抽出して整形（company判定は行わない）"""
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

def process_categories_with_serp(categories, max_categories=None):
    """カテゴリごとにSERP検索を実行し、companies属性の下に格納"""
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
            companies = {}
            for service in services:
                # 公式/非公式判定用の検索
                query = f"{service}"
                serp_data = get_google_search_results(query, num_results=10)
                official_results = process_serp_results(serp_data) if serp_data else []
                time.sleep(2)
                # 評判情報用の検索
                query_rep = f"{service} 評判 口コミ"
                serp_data_rep = get_google_search_results(query_rep, num_results=10)
                reputation_results = process_serp_results(serp_data_rep) if serp_data_rep else []
                time.sleep(2)
                companies[service] = {
                    "official_results": official_results,
                    "reputation_results": reputation_results
                }
            # 結果を格納
            results[category][subcategory] = {
                "timestamp": datetime.datetime.now().isoformat(),
                "category": category,
                "subcategory": subcategory,
                "companies": companies
            }
    return results

# -------------------------------------------------------------------
# メイン関数
# -------------------------------------------------------------------
def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Google SERPデータを取得し、Perplexityとの比較分析を行う')
    parser.add_argument('--perplexity-date', help='分析対象のPerplexityデータ日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['rankings', 'citations'], default='citations',
                        help='比較するPerplexityデータのタイプ（デフォルト: citations）')
    parser.add_argument('--max', type=int, help='処理するカテゴリ数の上限')
    parser.add_argument('--no-analysis', action='store_true', help='SERPメトリクス分析を実行しない')
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

    # Google SERP結果を取得
    result = process_categories_with_serp(categories, args.max)

    # 現在の日付（SERPデータの取得日時）
    today_date = datetime.datetime.now().strftime("%Y%m%d")

    # 結果を保存
    serp_file = save_results(result, "results")

    if args.verbose:
        logging.info(f"Google SERP結果をファイルに保存しました: {serp_file}")

if __name__ == "__main__":
    main()