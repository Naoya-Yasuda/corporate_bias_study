#!/usr/bin/env python
# coding: utf-8

"""
感情分析モジュール
Perplexity APIを使用してテキストの感情分析を実行するモジュール
"""

import os
import json
import datetime
import requests
import time
import argparse
from dotenv import load_dotenv
from tqdm import tqdm
from ..prompts.prompt_manager import PromptManager

# 共通ユーティリティをインポート
from src.utils.storage_utils import save_results, get_results_paths
from src.utils.storage_config import S3_BUCKET_NAME

# 環境変数の読み込み
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
API_HOST = "api.perplexity.ai"

# S3 設定情報
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# プロンプトマネージャーのインスタンスを作成
prompt_manager = PromptManager()

def analyze_sentiments(texts):
    """Perplexity APIを使用して複数のテキストの感情分析を実行"""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    # プロンプトを取得
    prompt = prompt_manager.get_sentiment_analysis_prompt(texts)

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

def main():
    """メイン関数"""
    # 引数処理
    parser = argparse.ArgumentParser(description='感情分析を実行し、結果を保存する')
    parser.add_argument('--date', help='分析対象の日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['rankings', 'citations'], default='citations',
                        help='分析対象のデータタイプ（デフォルト: citations）')
    parser.add_argument('--input-file', help='入力ファイルのパス')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # 日付を取得（指定がなければ今日の日付）
    date_str = args.date or datetime.datetime.now().strftime("%Y%m%d")
    if args.verbose:
        logging.info(f"分析日付: {date_str}, データタイプ: {args.data_type}")

    # 結果の保存先パスを取得
    paths = get_results_paths(date_str)

    # 入力ファイルのパスを取得
    if args.input_file:
        input_file = args.input_file
    else:
        if args.data_type == "citations":
            input_file = os.path.join(paths["perplexity_citations"], f"{date_str}_perplexity_citations.json")
        else:
            input_file = os.path.join(paths["perplexity_rankings"], f"{date_str}_perplexity_rankings.json")

    if args.verbose:
        logging.info(f"入力ファイル: {input_file}")

    # 感情分析を実行
    result = process_results_file(input_file)
    if result is None:
        print(f"感情分析の実行に失敗しました")
        return

    # 出力ファイル名を生成
    if "google_serp" in input_file:
        output_path = paths["google_serp"]
        output_filename = f"{date_str}_sentiment_analysis_google_serp_results.json"
        s3_key = f"results/google_serp/{date_str}/{output_filename}"
    else:
        output_path = paths["perplexity_sentiment"]
        output_filename = f"{date_str}_sentiment_analysis_{os.path.basename(input_file)}"
        s3_key = f"results/perplexity_sentiment/{date_str}/{output_filename}"

    # 結果を保存
    local_path = os.path.join(output_path, output_filename)
    save_results(result, local_path, s3_key, verbose=args.verbose)

if __name__ == "__main__":
    main()