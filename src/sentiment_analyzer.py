#!/usr/bin/env python
# coding: utf-8

"""
感情分析モジュール
Perplexity APIを使用してテキストの感情分析を行うモジュール
"""

import os
import sys
import json
import datetime
import requests
import time
import argparse
from dotenv import load_dotenv
from tqdm import tqdm

# 共通ユーティリティをインポート
from src.utils.file_utils import ensure_dir, get_today_str
from src.utils.storage_utils import save_json
from src.utils.s3_utils import get_local_path, get_s3_client, get_s3_key_path, get_latest_file

# 環境変数の読み込み
load_dotenv()

# Perplexity API の設定
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
API_HOST = "api.perplexity.ai"

# S3 設定情報
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

def analyze_sentiments(texts):
    """Perplexity APIを使用して複数のテキストの感情分析を実行"""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    # テキストを番号付きで結合
    numbered_texts = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])

    prompt = f"""
    以下のテキストがそれぞれポジティブかネガティブかを判定してください。
    回答は必ず各テキストの番号に対応する「positive」または「negative」をカンマ区切りで返してください。
    理由は不要です。

    テキスト:
    {numbered_texts}
    """

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "mixtral-8x7b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(f"https://{API_HOST}/chat/completions", headers=headers, json=data)
        result = response.json()

        if "choices" in result and len(result["choices"]) > 0:
            sentiments = result["choices"][0]["message"]["content"].strip().lower().split(",")
            # 結果をブール値に変換
            return [sentiment.strip() == "positive" for sentiment in sentiments]
        return [None] * len(texts)
    except Exception as e:
        print(f"Perplexity API リクエストエラー: {e}")
        return [None] * len(texts)

def process_google_serp_results(data):
    """Google SERPの結果ファイルを処理"""
    results = {}

    for category, subcategories in data.items():
        results[category] = {}

        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            results[category][subcategory] = {
                "timestamp": datetime.datetime.now().isoformat(),
                "category": category,
                "subcategory": subcategory,
                "companies": content.get("companies", {}),
                "official_results": content.get("official_results", []),  # 感情分析なしでそのまま保持
                "reputation_results": []
            }

            # 評判情報の感情分析（5件ずつバッチ処理）
            reputation_results = content.get("reputation_results", [])
            for i in range(0, len(reputation_results), 5):
                batch = reputation_results[i:i+5]
                texts = [f"{result['title']} {result['snippet']}" for result in batch]
                sentiments = analyze_sentiments(texts)

                for result, sentiment in zip(batch, sentiments):
                    result["sentiment"] = sentiment
                    results[category][subcategory]["reputation_results"].append(result)

                time.sleep(1)  # API制限対策

    return results

def process_perplexity_results(data):
    """Perplexityの結果ファイルを処理"""
    results = {}

    for category, subcategories in data.items():
        results[category] = {}

        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            results[category][subcategory] = {
                "timestamp": datetime.datetime.now().isoformat(),
                "category": category,
                "subcategory": subcategory,
                "companies": content.get("companies", {}),
                "citations": []
            }

            # citationsの感情分析（5件ずつバッチ処理）
            citations = content.get("citations", [])
            for i in range(0, len(citations), 5):
                batch = citations[i:i+5]
                texts = [f"{citation['title']} {citation['snippet']}" for citation in batch]
                sentiments = analyze_sentiments(texts)

                for citation, sentiment in zip(batch, sentiments):
                    citation["sentiment"] = sentiment
                    results[category][subcategory]["citations"].append(citation)

                time.sleep(1)  # API制限対策

    return results

def process_results_file(file_path):
    """結果ファイルを読み込んで感情分析を実行"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ファイル読み込みエラー: {e}")
        return None

    # ファイル名からデータタイプを判定
    if "google_serp" in file_path:
        return process_google_serp_results(data)
    elif "perplexity" in file_path:
        return process_perplexity_results(data)
    else:
        print("不明なデータタイプです。ファイル名に'google_serp'または'perplexity'が含まれている必要があります。")
        return None

def save_results(results, type_str, local_path="results"):
    """結果を保存する（ローカルとS3）"""
    today = get_today_str()

    # ディレクトリがなければ作成
    ensure_dir(local_path)

    # ローカルに保存
    local_file = get_local_path(today, "sentiment_analysis", "sentiment")

    # JSONを保存
    save_json(results, local_file)
    print(f"結果を {local_file} に保存しました")

    # S3に保存
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        # S3のパス
        s3_path = f"results/sentiment_analysis/{today}/{os.path.basename(local_file)}"

        # storage_utilsのsave_jsonでS3保存
        result = save_json(results, local_file, s3_path)
        if result["s3"]:
            print(f"結果を S3 ({S3_BUCKET_NAME}/{s3_path}) に保存しました")

    return local_file

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Google SERPデータとPerplexityデータの感情分析を実行')
    parser.add_argument('--input-file', required=True, help='分析対象のJSONファイルパス')
    parser.add_argument('--date', help='分析対象の日付（YYYYMMDD形式）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # 感情分析を実行
    results = process_results_file(args.input_file)
    if results:
        # 結果を保存
        save_results(results, "sentiment_analysis")

if __name__ == "__main__":
    main()