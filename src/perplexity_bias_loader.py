#!/usr/bin/env python
# coding: utf-8

import requests
import time
import boto3
import json
import datetime
import os
import re
from dotenv import load_dotenv
from src.categories import get_categories, get_viewpoints
from src.prompts.perplexity_prompts import get_masked_prompt, get_unmasked_prompt, extract_score, SCORE_PATTERN

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

# カテゴリとサービスの定義を取得
categories = get_categories()

class PerplexityAPI:
    def __init__(self, api_key, base_url="https://api.perplexity.ai/chat/completions"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def call_ai_api(self, prompt):
        try:
            payload = {
                "model": "llama-3.1-sonar-large-128k-online",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
                "temperature": 0.0,
                "stream": False
            }
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"].strip()
            else:
                raise Exception(f"Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"エラー（Perplexity）: {e}")
            return "エラー"

def process_categories(api_key, categories):
    """各カテゴリ、サブカテゴリを処理"""
    api = PerplexityAPI(api_key)
    results = {}

    for category, subcategories_data in categories.items():
        print(f"カテゴリ処理中: {category}")
        results[category] = {}

        for subcategory, competitors in subcategories_data.items():
            print(f"サブカテゴリ処理中: {subcategory}, 対象サービス: {competitors}")

            # プロンプトを生成
            masked_example = get_masked_prompt(subcategory)

            masked_result = api.call_ai_api(masked_example)
            print(f"マスク評価結果: {masked_result}")
            time.sleep(1)

            unmasked_results = {}
            unmasked_examples = {}
            for competitor in competitors:
                print(f"  サービス評価中: {competitor}")

                # プロンプトを生成
                unmasked_example = get_unmasked_prompt(subcategory, competitor)

                unmasked_examples[competitor] = unmasked_example
                unmasked_results[competitor] = api.call_ai_api(unmasked_example)
                print(f"  {competitor}の評価結果: {unmasked_results[competitor]}")
                time.sleep(1)

            results[category][subcategory] = {
                "competitors": competitors,
                "masked_example": masked_example,
                "unmasked_examples": unmasked_examples,
                "masked_result": masked_result,
                "unmasked_result": unmasked_results,
            }

    return results

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
                    print(f"カテゴリ: {category}, サブカテゴリ: {subcategory}, サービス: {results[category][subcategory]['competitors']}")
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
                print(f"処理中: カテゴリ={category}, サブカテゴリ={subcategory}")
                # マスクありの結果を保存
                masked_result = run_results[category][subcategory]['masked_result']
                results[category][subcategory]['all_masked_results'].append(masked_result)

                # マスクあり評価値の抽出
                try:
                    value = extract_score(masked_result)
                    if value is not None:
                        results[category][subcategory]['masked_values'].append(value)
                except Exception as e:
                    print(f"マスクあり評価値の抽出エラー: {e}, 結果: {masked_result}")

                # マスクなし評価値の抽出（各競合企業ごと）
                for competitor in results[category][subcategory]['competitors']:
                    try:
                        print(f"  サービス評価中: {competitor}")
                        # unmasked_resultから各企業の結果を取得
                        unmasked_result = run_results[category][subcategory]['unmasked_result'][competitor]

                        # 評価値の抽出
                        value = extract_score(unmasked_result)
                        if value is not None:
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
        file_name = f"{today_date}_perplexity_results_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_perplexity_results.json"

    # ローカルに保存
    output_dir = "results"
    ensure_dir(output_dir)
    local_file = f"{output_dir}/{file_name}"

    # JSONを保存
    save_json(result_data, local_file)
    print(f"ローカルに保存しました: {local_file}")

    # S3に保存（認証情報がある場合のみ）
    if aws_access_key and aws_secret_key and s3_bucket_name:
        # S3のパスを設定 (results/perplexity/日付/ファイル名)
        s3_key = f"results/perplexity/{today_date}/{file_name}"

        # S3にアップロード
        if put_json_to_s3(result_data, s3_key):
            print(f"S3に保存完了: s3://{s3_bucket_name}/{s3_key}")

    return local_file

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    import argparse
    parser = argparse.ArgumentParser(description='Perplexityを使用して企業バイアスデータを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--no-analysis', action='store_true', help='バイアス分析を実行しない')
    args = parser.parse_args()

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
        result = process_categories_with_multiple_runs(PERPLEXITY_API_KEY, categories, args.runs)
        result_file = f"results/{today_date}_perplexity_results_{args.runs}runs.json"
        save_results(result, "multiple", args.runs)
    else:
        print("Perplexity APIを使用して単一実行データを取得します")
        result = process_categories(PERPLEXITY_API_KEY, categories)
        result_file = f"results/{today_date}_perplexity_results.json"
        save_results(result)

    print("データ取得処理が完了しました")

    # バイアス分析を実行（--no-analysisオプションが指定されていない場合）
    if not args.no_analysis:
        try:
            from src.analysis.bias_metrics import analyze_bias_from_file
            print("\n=== バイアス分析を開始します ===")

            # 分析出力ディレクトリ
            analysis_dir = f"results/analysis/perplexity/{today_date}"

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
                            s3_key = f"results/analysis/perplexity/{today_date}/{filename}"

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