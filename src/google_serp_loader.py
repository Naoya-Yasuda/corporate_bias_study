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
from src.utils.storage_utils import save_json
from src.utils.s3_utils import get_local_path, get_s3_client, get_s3_key_path, get_latest_file

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

    # ディレクトリがなければ作成
    ensure_dir(local_path)

    # ローカルに保存
    local_file = get_local_path(today, "google_serp", "google")

    # JSONを保存
    save_json(results, local_file)
    print(f"結果を {local_file} に保存しました")

    # S3に保存
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        # S3のパス
        s3_path = f"results/google_serp/{today}/{os.path.basename(local_file)}"

        # storage_utilsのsave_jsonでS3保存
        result = save_json(results, local_file, s3_path)
        if result["s3"]:
            print(f"結果を S3 ({S3_BUCKET_NAME}/{s3_path}) に保存しました")

    return local_file

def is_negative_content(title, snippet):
    """タイトルとスニペットからネガティブコンテンツかを判定"""
    # ネガティブキーワードリスト（簡易版）
    negative_keywords = [
        "問題", "障害", "失敗", "リスク", "欠陥", "批判", "炎上", "トラブル",
        "不具合", "バグ", "遅延", "停止", "故障", "危険", "脆弱性", "違反",
        "disadvantage", "problem", "issue", "bug", "risk", "fail", "error",
        "vulnerability", "outage", "down", "criticism", "negative", "trouble"
    ]

    combined_text = (title + " " + snippet).lower()

    for keyword in negative_keywords:
        if keyword in combined_text:
            return True

    return False

# -------------------------------------------------------------------
# SERP API 関連
# -------------------------------------------------------------------
def get_serp_results(query, num_results=10):
    """SERP API を使用してGoogle検索結果を取得"""
    if not SERP_API_KEY:
        raise ValueError("SERP_API_KEY が設定されていません。.env ファイルを確認してください。")

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERP_API_KEY,
        "num": num_results,
        "hl": "ja",  # 日本語で検索
        "gl": "jp"   # 日本から検索
    }

    try:
        url = f"https://{API_HOST}/search.json"
        response = requests.get(url, params=params)
        data = response.json()

        if "error" in data:
            print(f"API エラー: {data['error']}")
            return None

        return data
    except Exception as e:
        print(f"SERP API リクエストエラー: {e}")
        return None

def process_serp_results(data, query, category, subcategory, target_companies):
    """SERP API の結果から必要な情報を抽出して整形"""
    if not data or "organic_results" not in data:
        print(f"有効な検索結果がありません: {query}")
        return None

    organic_results = data["organic_results"]

    # 検索結果を解析
    results = []
    search_result_companies = []  # 検索結果の順序に基づく企業名のリスト（categories.ymlで定義された企業名）

    for i, result in enumerate(organic_results):
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        domain = extract_domain(link)

        # 各企業についてドメインが関連しているか確認（categories.ymlで定義された企業名と照合）
        related_company = None
        for company in target_companies:
            if (company.lower() in title.lower() or
                company.lower() in snippet.lower() or
                company.lower() in domain.lower()):
                related_company = company
                if len(search_result_companies) < 10:  # 上位10件まで記録
                    search_result_companies.append(company)
                break

        # 公式ドメインリストを使用して判定（サブカテゴリ内の全企業の公式ドメインと照合）
        is_official = is_official_domain(domain, related_company, target_companies)

        # 結果を記録
        results.append({
            "rank": i + 1,
            "title": title,
            "link": link,
            "domain": domain,
            "snippet": snippet,
            "company": related_company,  # categories.ymlで定義された企業名
            "is_official": is_official,
            "is_negative": is_negative_content(title, snippet)
        })

    return {
        "query": query,
        "timestamp": datetime.datetime.now().isoformat(),
        "category": category,
        "subcategory": subcategory,
        "companies": target_companies,  # categories.ymlで定義された企業名と公式ドメインのマッピング
        "search_result_companies": search_result_companies,  # 検索結果で見つかった企業名のリスト
        "detailed_results": results
    }

def process_categories_with_serp(categories, max_categories=None):
    """カテゴリごとにSERP検索を実行"""
    results = {}
    count = 0

    # 処理するカテゴリの絞り込み
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
            # 検索クエリを生成（より自然な検索クエリに修正）
            query = f"{subcategory} おすすめ 人気 比較"

            # SERP API で検索
            serp_data = get_serp_results(query, num_results=20)

            if serp_data:
                # 結果を整形
                processed_data = process_serp_results(
                    serp_data, query, category, subcategory, services
                )

                if processed_data:
                    results[category][subcategory] = processed_data

            # API制限対策（1秒待機）
            time.sleep(1)

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