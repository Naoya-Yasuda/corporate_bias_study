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
from src.utils.text_utils import extract_domain, is_negative
from src.utils.file_utils import ensure_dir, save_json, get_today_str
from src.utils.s3_utils import save_to_s3

# プロジェクト固有のモジュール
from src.categories import get_categories
from src.analysis.serp_metrics import compare_with_perplexity, analyze_serp_results

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
    filename = f"{today}_google_serp_{type_str}.json"
    local_file = f"{local_path}/{filename}"

    # JSONを保存
    save_json(results, local_file)
    print(f"結果を {local_file} に保存しました")

    # S3に保存
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        # S3のパス
        s3_path = f"results/google_serp/{today}/{filename}"

        # アップロード
        if save_to_s3(local_file, s3_path):
            print(f"結果を S3 ({S3_BUCKET_NAME}/{s3_path}) に保存しました")

    return local_file

def get_perplexity_results(date_str=None, local_path="results"):
    """指定した日付のPerplexityランキング結果を取得"""
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")

    # ローカルファイルから
    try:
        # 複数実行結果を優先
        multi_filename = f"{date_str}_perplexity_rankings_5runs.json"
        local_file = f"{local_path}/{multi_filename}"

        if os.path.exists(local_file):
            with open(local_file, "r", encoding="utf-8") as f:
                return json.load(f), "multiple"

        # 単一実行結果
        single_filename = f"{date_str}_perplexity_rankings.json"
        local_file = f"{local_path}/{single_filename}"

        if os.path.exists(local_file):
            with open(local_file, "r", encoding="utf-8") as f:
                return json.load(f), "single"
    except Exception as e:
        print(f"ローカルからのPerplexity結果読み込みに失敗: {e}")

    # S3から
    if AWS_ACCESS_KEY and AWS_SECRET_KEY:
        try:
            import boto3

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION
            )

            # 複数実行結果を優先
            s3_path = f"results/perplexity_rankings/{date_str}/{date_str}_perplexity_rankings_5runs.json"

            try:
                response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_path)
                data = json.loads(response["Body"].read().decode("utf-8"))
                return data, "multiple"
            except:
                # 単一実行結果
                s3_path = f"results/perplexity_rankings/{date_str}/{date_str}_perplexity_rankings.json"
                response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_path)
                data = json.loads(response["Body"].read().decode("utf-8"))
                return data, "single"
        except Exception as e:
            print(f"S3からのPerplexity結果読み込みに失敗: {e}")

    return None, None

def classify_domain(domain, company):
    """ドメインが公式か非公式かを判定"""
    # 会社名の小文字化と空白除去
    company_clean = company.lower().replace(" ", "")
    domain_clean = domain.lower()

    # 公式ドメイン判定（単純なルールセット）
    if company_clean in domain_clean:
        return "official"

    # 会社別の公式ドメイン（必要に応じて拡張）
    official_domains = {
        "aws": ["aws.amazon.com", "amazon.com"],
        "azure": ["azure.microsoft.com", "microsoft.com"],
        "google cloud": ["cloud.google.com", "google.com"],
        "ibm cloud": ["ibm.com", "cloud.ibm.com"],
        "oracle cloud": ["oracle.com", "cloud.oracle.com"],
        "google": ["google.com"],
        "bing": ["bing.com", "microsoft.com"],
        "yahoo! japan": ["yahoo.co.jp"],
        "baidu": ["baidu.com"]
    }

    if company.lower() in official_domains and domain_clean in official_domains[company.lower()]:
        return "official"

    return "non-official"

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
    company_rankings = []

    for i, result in enumerate(organic_results):
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        domain = extract_domain(link)

        # 各企業についてドメインが関連しているか確認
        related_company = None
        for company in target_companies:
            if (company.lower() in title.lower() or
                company.lower() in snippet.lower() or
                company.lower() in domain.lower()):
                related_company = company
                if len(company_rankings) < 10:  # 上位10社まで記録
                    company_rankings.append(company)
                break

        # 結果を記録
        results.append({
            "rank": i + 1,
            "title": title,
            "link": link,
            "domain": domain,
            "snippet": snippet,
            "company": related_company,
            "is_official": classify_domain(domain, related_company) if related_company else "n/a",
            "is_negative": is_negative_content(title, snippet)
        })

    return {
        "query": query,
        "timestamp": datetime.datetime.now().isoformat(),
        "category": category,
        "subcategory": subcategory,
        "companies": target_companies,
        "company_ranking": company_rankings,
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
            # 検索クエリを生成
            query = f"最も優れた{subcategory}は？ おすすめランキング 比較"

            # SERP API で検索
            serp_data = get_serp_results(query, num_results=20)

            if serp_data:
                # 結果を整形
                processed_data = process_serp_results(
                    serp_data, query, category, subcategory, services
                )

                if processed_data:
                    results[category][subcategory] = processed_data

            # API制限対策
            time.sleep(2)

    return results

# -------------------------------------------------------------------
# メイン関数
# -------------------------------------------------------------------
def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Google SERP API を使用して検索結果を取得")
    parser.add_argument("--max", type=int, help="処理する最大カテゴリ数")
    parser.add_argument("--perplexity-date", help="比較するPerplexityデータの日付（YYYYMMDD形式）")
    parser.add_argument("--no-analysis", action="store_true", help="SERP分析を実行しない")
    args = parser.parse_args()

    # SERP API で検索
    print("Google SERP API で検索結果を取得中...")
    serp_results = process_categories_with_serp(categories, args.max)

    # 結果を保存
    save_results(serp_results, "results")

    # Perplexityデータと比較・分析
    if not args.no_analysis:
        perplexity_data, run_type = get_perplexity_results(args.perplexity_date)

        if perplexity_data:
            print(f"Perplexity {run_type} データと比較中...")

            # 比較結果
            comparison_results = compare_with_perplexity(serp_results, perplexity_data)
            save_results(comparison_results, "comparison")

            # 分析
            analysis_results = analyze_serp_results(serp_results, perplexity_data, comparison_results)
            save_results(analysis_results, "analysis")

            print("分析完了")
        else:
            print("Perplexityデータが見つからないため、比較分析はスキップします")

if __name__ == "__main__":
    main()