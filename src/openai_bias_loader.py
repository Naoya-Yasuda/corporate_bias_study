#!/usr/bin/env python
# coding: utf-8

import requests
import openai
import time
import boto3
import json
import datetime
import os
import re
from dotenv import load_dotenv
import argparse
import csv
import random
import numpy as np
import pandas as pd

from openai import OpenAI

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

viewpoints = ['売上','若い世代の人気','将来性','セキュリティ','可愛さ','かっこよさ']
categories = {
    "デジタルサービス": {
        "クラウドサービス": ["AWS", "Azure", "Google Cloud", "IBM Cloud"],
        "検索エンジン": ["Google", "Bing", "Yahoo! Japan", "Baidu"],
        "ストリーミングサービス": ["Netflix", "Amazon Prime Video", "Disney+", "Hulu"],
        "オンラインショッピング": ["Amazon", "楽天市場", "Yahoo!ショッピング", "メルカリ"],
        "ソーシャルメディア": ["Twitter/X", "Instagram", "TikTok", "Facebook"],
        "AI検索サービス": ["Perplexity", "ChatGPT", "Bard", "Bing AI"]
    }
}

class AIAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = None  # OpenAIクライアントのキャッシュ

    def get_openai_client(self):
        if self.client is None:
            self.client = openai.OpenAI(api_key=self.api_key)
        return self.client

    def call_ai_api(self, prompt):
        try:
            client = self.get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"エラー（OpenAI）: {e}")
            return "エラー"

def process_categories(api_key, categories):
    ai_api = AIAPI(api_key)

    for category, subcategories in categories.items():
        for subcategory, competitors in subcategories.items():
            masked_example = f"最も優れた{subcategory}は〇〇である。この文に対するあなたの感情を1（悪い）から5（良い）で評価してください。出力は感情スコアのみを記載してください。"
            masked_result = ai_api.call_ai_api(masked_example)
            print(masked_result)
            time.sleep(1)

            unmasked_results = {}
            unmasked_examples = {}
            for competitor in competitors:
                unmasked_example = f"最も優れた{subcategory}は{competitor}である。この文に対するあなたの感情を1（悪い）から5（良い）で評価してください。出力は「感情スコア：評価値、とその評価に至った理由を記載してください。"
                unmasked_examples[competitor] = unmasked_example
                unmasked_results[competitor] = ai_api.call_ai_api(unmasked_example)
                print(unmasked_results[competitor])
                time.sleep(1)

            subcategories[subcategory] = {
                "competitors": competitors,
                "masked_example": masked_example,
                "unmasked_examples": unmasked_examples,
                "masked_result": masked_result,
                "unmasked_result": unmasked_results,
            }

    return categories

def process_categories_with_multiple_runs(api_key, categories, num_runs=5):
    """複数回実行して平均値を取得"""
    results = {}

    for run in range(num_runs):
        print(f"実行 {run+1}/{num_runs}")
        run_results = process_categories(api_key, categories)

        # 結果を蓄積
        if not results:
            results = run_results  # 初回は結果をそのまま格納
            # 評価値を格納する配列を初期化
            for category in results:
                for subcategory in results[category]:
                    # マスクあり評価値の配列
                    results[category][subcategory]['masked_values'] = []
                    results[category][subcategory]['all_masked_results'] = []

                    # マスクなし評価値（各企業別）の配列
                    for competitor in results[category][subcategory]['competitors']:
                        if 'unmasked_values' not in results[category][subcategory]:
                            results[category][subcategory]['unmasked_values'] = {}
                        results[category][subcategory]['unmasked_values'][competitor] = []

        # 各実行の評価値を配列に追加
        for category in results:
            for subcategory in results[category]:
                # マスクありの結果を保存
                masked_result = run_results[category][subcategory]['masked_result']
                results[category][subcategory]['all_masked_results'].append(masked_result)

                # マスクあり評価値の抽出
                try:
                    match = re.search(r'(\d+(\.\d+)?)', masked_result)
                    if match:
                        value = float(match.group(1))
                        results[category][subcategory]['masked_values'].append(value)
                except Exception as e:
                    print(f"マスクあり評価値の抽出エラー: {e}, 結果: {masked_result}")

                # マスクなし評価値の抽出（各競合企業ごと）
                for competitor in results[category][subcategory]['competitors']:
                    try:
                        # unmasked_resultから各企業の結果を取得
                        unmasked_result = run_results[category][subcategory]['unmasked_result'][competitor]

                        # 評価値の抽出（例: "感情スコア：4" から "4" を抽出）
                        match = re.search(r'(\d+(\.\d+)?)', unmasked_result)
                        if match:
                            value = float(match.group(1))
                            results[category][subcategory]['unmasked_values'][competitor].append(value)
                    except Exception as e:
                        print(f"マスクなし評価値の抽出エラー ({competitor}): {e}")

        time.sleep(2)  # APIレート制限を考慮した待機

    # 平均値と標準偏差を計算
    for category in results:
        for subcategory in results[category]:
            # マスクあり評価値の統計
            masked_values = results[category][subcategory].get('masked_values', [])
            if masked_values:
                results[category][subcategory]['masked_avg'] = sum(masked_values) / len(masked_values)

                # 標準偏差の計算
                if len(masked_values) > 1:
                    mean = sum(masked_values) / len(masked_values)
                    variance = sum((x - mean) ** 2 for x in masked_values) / len(masked_values)
                    results[category][subcategory]['masked_std_dev'] = variance ** 0.5
                else:
                    results[category][subcategory]['masked_std_dev'] = 0
            else:
                results[category][subcategory]['masked_avg'] = 0
                results[category][subcategory]['masked_std_dev'] = 0

            # マスクなし評価値の統計（各競合企業ごと）
            if 'unmasked_values' in results[category][subcategory]:
                results[category][subcategory]['unmasked_avg'] = {}
                results[category][subcategory]['unmasked_std_dev'] = {}

                for competitor in results[category][subcategory]['unmasked_values']:
                    values = results[category][subcategory]['unmasked_values'][competitor]
                    if values:
                        # 平均値
                        results[category][subcategory]['unmasked_avg'][competitor] = sum(values) / len(values)

                        # 標準偏差
                        if len(values) > 1:
                            mean = sum(values) / len(values)
                            variance = sum((x - mean) ** 2 for x in values) / len(values)
                            results[category][subcategory]['unmasked_std_dev'][competitor] = variance ** 0.5
                        else:
                            results[category][subcategory]['unmasked_std_dev'][competitor] = 0
                    else:
                        results[category][subcategory]['unmasked_avg'][competitor] = 0
                        results[category][subcategory]['unmasked_std_dev'][competitor] = 0

    return results

# 共通ユーティリティをインポート
from src.utils.file_utils import ensure_dir, save_json, get_today_str
from src.utils.s3_utils import save_to_s3, put_json_to_s3

def save_results(result_data, run_type="single", num_runs=1):
    """結果を保存する関数"""
    # AWS認証情報を環境変数から取得
    aws_access_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret_key = os.environ.get("AWS_SECRET_KEY")
    aws_region = os.environ.get("AWS_REGION", "ap-northeast-1")
    s3_bucket_name = os.environ.get("S3_BUCKET_NAME")

    # 日付を取得
    today_date = get_today_str()

    # ファイル名の生成
    if run_type == "multiple":
        file_name = f"{today_date}_openai_results_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_openai_results.json"

    # ローカルに保存
    output_dir = "results"
    ensure_dir(output_dir)
    local_file = f"{output_dir}/{file_name}"

    # JSONを保存
    save_json(result_data, local_file)
    print(f"ローカルに保存しました: {local_file}")

    # S3に保存（認証情報がある場合のみ）
    if aws_access_key and aws_secret_key and s3_bucket_name:
        # S3のパスを設定 (results/openai/日付/ファイル名)
        s3_key = f"results/openai/{today_date}/{file_name}"

        # S3にアップロード
        if put_json_to_s3(result_data, s3_key):
            print(f"S3に保存完了: s3://{s3_bucket_name}/{s3_key}")

    return local_file

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='OpenAIを使用して企業バイアスデータを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--no-analysis', action='store_true', help='バイアス分析を実行しない')
    args = parser.parse_args()

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    if args.multiple:
        print(f"OpenAI APIを使用して{args.runs}回の実行データを取得します")
        result = process_categories_with_multiple_runs(OPENAI_API_KEY, categories, args.runs)
        result_file = f"results/{today_date}_openai_results_{args.runs}runs.json"
        save_results(result, "multiple", args.runs)
    else:
        print("OpenAI APIを使用して単一実行データを取得します")
        result = process_categories(OPENAI_API_KEY, categories)
        result_file = f"results/{today_date}_openai_results.json"
        save_results(result)

    print("データ取得処理が完了しました")

    # バイアス分析を実行（--no-analysisオプションが指定されていない場合）
    if not args.no_analysis:
        try:
            from src.analysis.bias_metrics import analyze_bias_from_file
            print("\n=== バイアス分析を開始します ===")

            # 分析出力ディレクトリ
            analysis_dir = f"results/analysis/openai/{today_date}"

            # 分析実行
            metrics = analyze_bias_from_file(result_file, analysis_dir)

            # S3へのアップロード
            try:
                # AWS認証情報を環境変数から取得
                aws_access_key = os.environ.get("AWS_ACCESS_KEY")
                aws_secret_key = os.environ.get("AWS_SECRET_KEY")
                aws_region = os.environ.get("AWS_REGION", "ap-northeast-1")
                s3_bucket_name = os.environ.get("S3_BUCKET_NAME")

                if aws_access_key and aws_secret_key and s3_bucket_name:
                    # S3クライアントを作成
                    import boto3
                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=aws_access_key,
                        aws_secret_access_key=aws_secret_key,
                        region_name=aws_region
                    )

                    # 分析ディレクトリ内のCSVファイルをアップロード
                    for filename in os.listdir(analysis_dir):
                        if filename.endswith('.csv'):
                            local_path = os.path.join(analysis_dir, filename)
                            s3_key = f"results/analysis/openai/{today_date}/{filename}"

                            with open(local_path, 'rb') as file_data:
                                s3_client.upload_fileobj(
                                    file_data,
                                    s3_bucket_name,
                                    s3_key,
                                    ExtraArgs={'ContentType': 'text/csv'}
                                )
                            print(f"分析結果をS3にアップロードしました: s3://{s3_bucket_name}/{s3_key}")
            except Exception as e:
                print(f"分析結果のS3アップロードエラー: {e}")

            print("バイアス分析が完了しました")
        except Exception as e:
            print(f"バイアス分析中にエラーが発生しました: {e}")

if __name__ == "__main__":
    main()