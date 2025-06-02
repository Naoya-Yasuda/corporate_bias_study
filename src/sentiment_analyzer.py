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
from src.utils.storage_utils import save_json, get_storage_config, get_results_paths, get_s3_client
from src.utils.storage_config import is_s3_enabled, S3_BUCKET_NAME

# 環境変数の読み込み
load_dotenv()

# Perplexity API の設定
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
API_HOST = "api.perplexity.ai"

# S3 設定情報
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

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
    # 元のデータをそのまま使用
    results = data

    for category, subcategories in data.items():
        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            # 評判情報の感情分析（5件ずつバッチ処理）
            reputation_results = content.get("reputation_results", [])
            for i in range(0, len(reputation_results), 5):
                batch = reputation_results[i:i+5]
                texts = [f"{result['title']} {result['snippet']}" for result in batch]
                sentiments = analyze_sentiments(texts)

                for result, sentiment in zip(batch, sentiments):
                    result["sentiment"] = sentiment

                time.sleep(1)  # API制限対策

    return results

def process_perplexity_results(data):
    """Perplexityの結果ファイルを処理"""
    # 元のデータをそのまま使用
    results = data

    for category, subcategories in data.items():
        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            # citationsの感情分析（5件ずつバッチ処理）
            citations = content.get("citations", [])
            for i in range(0, len(citations), 5):
                batch = citations[i:i+5]
                texts = [f"{citation['title']} {citation['snippet']}" for citation in batch]
                sentiments = analyze_sentiments(texts)

                for citation, sentiment in zip(batch, sentiments):
                    citation["sentiment"] = sentiment

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

def save_results(results, file_path):
    """結果を元のファイルに保存"""
    try:
        # 元のファイルに保存
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"結果を {file_path} に保存しました")

        # S3に保存（認証情報がある場合のみ）
        if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
            s3_client = get_s3_client()
            s3_key = file_path.replace("results/", "")
            try:
                with open(file_path, 'rb') as f:
                    s3_client.upload_fileobj(f, S3_BUCKET_NAME, s3_key)
                print(f"結果を S3 ({S3_BUCKET_NAME}/{s3_key}) に保存しました")
            except Exception as e:
                print(f"S3への保存に失敗しました: {e}")

    except Exception as e:
        print(f"ファイル保存エラー: {e}")
        return None

    return file_path

def main():
    """メイン関数"""
    # 引数処理
    parser = argparse.ArgumentParser(description='感情分析を実行')
    parser.add_argument('--date', type=str, help='日付（YYYYMMDD形式）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 日付の設定
    if args.date:
        date_str = args.date
    else:
        date_str = datetime.datetime.now().strftime("%Y%m%d")

    # データタイプの設定
    data_type = "google_serp"
    input_filename = f"{date_str}_google_serp_results.json"

    # パスの取得
    local_path, s3_path = get_results_paths(data_type, date_str, input_filename)

    # 入力ファイルの読み込み
    try:
        with open(local_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"入力ファイルの読み込みエラー: {e}")
        return

    # 感情分析の実行
    result = process_google_serp_results(data)

    # ストレージ設定の取得（デバッグ用）
    storage_config = get_storage_config()
    print(f"ストレージ設定: {storage_config}")

    # 保存
    result = save_json(result, local_path, s3_path)

    if result["local"]:
        print(f"ローカルに保存しました: {local_path}")
    if result["s3"]:
        print(f"S3に保存しました: s3://{s3_path}")

    print("感情分析が完了しました")

if __name__ == "__main__":
    main()