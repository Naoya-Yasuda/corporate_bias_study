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

def get_perplexity_results(date_str=None, local_path="results", data_type="citations", runs=None):
    """
    指定した日付のPerplexityランキング結果または引用リンク結果を取得

    Parameters
    ----------
    date_str : str, optional
        日付文字列（YYYYMMDD形式）
    local_path : str, optional
        ローカルファイルのパス
    data_type : str, optional
        データタイプ "rankings"（ランキングデータ）または "citations"（引用リンクデータ）
        デフォルトは "citations"
    runs : int, optional
        指定された実行回数のファイルを検索（指定がない場合は利用可能なすべての回数のファイルを検索）

    Returns
    -------
    tuple
        (データ, データタイプ, 実行回数) のタプル
    """
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")

    # 保存先ディレクトリの設定
    if data_type == "citations":
        s3_prefix = "results/perplexity_citations"
    else:  # rankings
        s3_prefix = "results/perplexity_rankings"

    # ローカルディレクトリからファイル一覧を取得
    local_files = []
    if os.path.exists(local_path):
        local_files = [f for f in os.listdir(local_path) if os.path.isfile(os.path.join(local_path, f))]

    # 特定の日付とデータタイプに一致するファイルをフィルタリング
    multi_run_pattern = f"{date_str}_perplexity_{data_type}_"  # 例: 20240501_perplexity_citations_
    single_run_pattern = f"{date_str}_perplexity_{data_type}.json"  # 例: 20240501_perplexity_citations.json

    # 複数実行結果ファイルをフィルタリング
    multi_run_files = [f for f in local_files if f.startswith(multi_run_pattern) and f.endswith("runs.json")]

    # 指定された実行回数があれば、それに一致するファイルのみを探す
    if runs is not None:
        target_file = f"{date_str}_perplexity_{data_type}_{runs}runs.json"
        if target_file in local_files:
            file_path = os.path.join(local_path, target_file)
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f), "multiple", runs

    # 指定された実行回数がない場合は、最大の実行回数のファイルを探す
    elif multi_run_files:
        # 実行回数でソート（例: 10runs > 5runs）
        multi_run_files.sort(key=lambda x: int(x.split("_")[-1].replace("runs.json", "")), reverse=True)
        file_path = os.path.join(local_path, multi_run_files[0])
        runs_count = int(multi_run_files[0].split("_")[-1].replace("runs.json", ""))

        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f), "multiple", runs_count

    # 単一実行結果ファイルを探す
    elif single_run_pattern in local_files:
        file_path = os.path.join(local_path, single_run_pattern)
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f), "single", 1

    # S3から検索
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3_client = boto3.client(
                "s3",
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION
            )

            # S3バケット内のオブジェクトを一覧表示
            prefix = f"{s3_prefix}/{date_str}/"
            try:
                response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)

                # 見つかったオブジェクトをフィルタリング
                s3_files = []
                if "Contents" in response:
                    for obj in response["Contents"]:
                        key = obj["Key"]
                        filename = os.path.basename(key)
                        if filename.startswith(f"{date_str}_perplexity_{data_type}"):
                            s3_files.append((key, filename))

                # 実行回数でフィルタリング
                if runs is not None:
                    target_s3_file = f"{date_str}_perplexity_{data_type}_{runs}runs.json"
                    s3_match = [key for key, name in s3_files if name == target_s3_file]
                    if s3_match:
                        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_match[0])
                        data = json.loads(response["Body"].read().decode("utf-8"))
                        return data, "multiple", runs

                # 複数実行ファイルを検索（実行回数の大きい順）
                multi_s3_files = [(key, name) for key, name in s3_files if "_runs.json" in name]
                if multi_s3_files:
                    # 実行回数でソート
                    multi_s3_files.sort(key=lambda x: int(x[1].split("_")[-1].replace("runs.json", "")), reverse=True)
                    key, name = multi_s3_files[0]
                    runs_count = int(name.split("_")[-1].replace("runs.json", ""))

                    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                    data = json.loads(response["Body"].read().decode("utf-8"))
                    return data, "multiple", runs_count

                # 単一実行ファイルを検索
                single_s3_file = f"{date_str}_perplexity_{data_type}.json"
                s3_match = [key for key, name in s3_files if name == single_s3_file]
                if s3_match:
                    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_match[0])
                    data = json.loads(response["Body"].read().decode("utf-8"))
                    return data, "single", 1

            except ClientError as e:
                print(f"S3でのファイル一覧取得エラー: {e}")

        except Exception as e:
            print(f"S3からのPerplexity結果読み込みに失敗: {e}")

    return None, None, None

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
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Google SERPデータを取得し、Perplexityとの比較分析を行う')
    parser.add_argument('--perplexity-date', help='分析対象のPerplexityデータ日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['rankings', 'citations'], default='citations',
                        help='比較するPerplexityデータのタイプ（デフォルト: citations）')
    parser.add_argument('--max', type=int, help='処理するカテゴリ数の上限')
    parser.add_argument('--runs', type=int, default=10, help='使用するPerplexity実行回数（デフォルト: 10）')
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
    result = get_google_serp(categories)

    # 現在の日付（SERPデータの取得日時）
    today_date = datetime.datetime.now().strftime("%Y%m%d")

    # ファイル名
    serp_file = f"results/{today_date}_google_serp_results.json"

    # 結果を保存
    save_results(result, serp_file)

    if args.verbose:
        logging.info(f"Google SERP結果をファイルに保存しました: {serp_file}")

    # SERPメトリクス分析を実行（--no-analysisオプションが指定されていない場合）
    if not args.no_analysis:
        try:
            from src.analysis.serp_metrics import analyze_serp_data
            print("\n=== SERPメトリクス分析を開始します ===")
            if args.verbose:
                logging.info("SERPメトリクス分析を開始します")

            # PerplexityのJSONパス（データタイプに応じて）
            perplexity_json = f"results/{perplexity_date}_perplexity_{args.data_type}_{args.runs}runs.json"

            if args.verbose:
                logging.info(f"Perplexityデータ: {perplexity_json}")

            # 分析実行
            metrics = analyze_serp_data(serp_file, perplexity_json, args.data_type, verbose=args.verbose)

            print("SERPメトリクス分析が完了しました")
            if args.verbose:
                logging.info("SERPメトリクス分析が完了しました")
        except Exception as e:
            print(f"SERPメトリクス分析中にエラーが発生しました: {e}")
            if args.verbose:
                logging.error(f"SERPメトリクス分析中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()