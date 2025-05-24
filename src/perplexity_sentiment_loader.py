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
import numpy as np
import argparse
import logging
from src.utils.file_utils import ensure_dir, get_today_str
from src.utils.storage_utils import save_json
from src.utils.s3_utils import save_to_s3, put_json_to_s3, get_local_path

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

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
    """複数回実行して平均値を取得（マスクあり・マスクなし両方とも各num_runs回ずつAPIを呼び出す）"""
    results = {}
    for category, subcategories_data in categories.items():
        results[category] = {}
        for subcategory, competitors in subcategories_data.items():
            results[category][subcategory] = {
                "competitors": competitors,
                "masked_example": get_masked_prompt(subcategory),
                "unmasked_examples": {competitor: get_unmasked_prompt(subcategory, competitor) for competitor in competitors},
                "masked_result": "",
                "unmasked_result": {competitor: "" for competitor in competitors},
                "masked_values": [],
                "all_masked_results": [],
                "unmasked_values": {competitor: [] for competitor in competitors},
                "masked_reasons": [],
                "unmasked_reasons": {competitor: [] for competitor in competitors}
            }
            print(f"評価対象: カテゴリ={category}, サブカテゴリ={subcategory}, サービス={competitors}")

    api = PerplexityAPI(api_key)
    # マスクあり num_runs回
    for run in range(num_runs):
        print(f"マスクあり 実行 {run+1}/{num_runs}")
        for category, subcategories_data in categories.items():
            for subcategory, competitors in subcategories_data.items():
                masked_example = get_masked_prompt(subcategory)
                masked_result = api.call_ai_api(masked_example)
                results[category][subcategory]['masked_result'] = masked_result
                results[category][subcategory]['all_masked_results'].append(masked_result)
                try:
                    value = extract_score(masked_result)
                    if value is not None:
                        results[category][subcategory]['masked_values'].append(value)
                    else:
                        print(f"警告: マスクあり評価値が抽出できませんでした: {masked_result}")
                    reason = extract_reason(masked_result)
                    results[category][subcategory]['masked_reasons'].append(reason)
                except Exception as e:
                    print(f"マスクあり評価値の抽出エラー: {e}, 結果: {masked_result}")
                time.sleep(1)
    # マスクなし（各企業ごと） num_runs回
    for run in range(num_runs):
        print(f"マスクなし 実行 {run+1}/{num_runs}")
        for category, subcategories_data in categories.items():
            for subcategory, competitors in subcategories_data.items():
                for competitor in competitors:
                    unmasked_example = get_unmasked_prompt(subcategory, competitor)
                    unmasked_result = api.call_ai_api(unmasked_example)
                    results[category][subcategory]['unmasked_result'][competitor] = unmasked_result
                    try:
                        value = extract_score(unmasked_result)
                        if value is not None:
                            results[category][subcategory]['unmasked_values'][competitor].append(value)
                        else:
                            print(f"警告: {competitor}の評価値が抽出できませんでした: {unmasked_result}")
                        reason = extract_reason(unmasked_result)
                        results[category][subcategory]['unmasked_reasons'][competitor].append(reason)
                    except Exception as e:
                        print(f"マスクなし評価値の抽出エラー ({competitor}): {e}")
                    time.sleep(1)
    # 平均値と標準偏差の計算などは従来通り
    for category in results:
        for subcategory in results[category]:
            masked_values = results[category][subcategory].get('masked_values', [])
            if masked_values:
                results[category][subcategory]['masked_avg'] = np.mean(masked_values)
                print(f"マスクあり評価値: {masked_values}, 平均: {results[category][subcategory]['masked_avg']}")
                if len(masked_values) > 1:
                    results[category][subcategory]['masked_std_dev'] = np.std(masked_values, ddof=1)
                else:
                    results[category][subcategory]['masked_std_dev'] = 0
            else:
                results[category][subcategory]['masked_avg'] = 0
                results[category][subcategory]['masked_std_dev'] = 0
            if 'unmasked_values' in results[category][subcategory]:
                results[category][subcategory]['unmasked_avg'] = {}
                results[category][subcategory]['unmasked_std_dev'] = {}
                for competitor in results[category][subcategory]['unmasked_values']:
                    values = results[category][subcategory]['unmasked_values'][competitor]
                    if values:
                        results[category][subcategory]['unmasked_avg'][competitor] = np.mean(values)
                        print(f"{competitor}の評価値: {values}, 平均: {results[category][subcategory]['unmasked_avg'][competitor]}")
                        if len(values) > 1:
                            results[category][subcategory]['unmasked_std_dev'][competitor] = np.std(values, ddof=1)
                        else:
                            results[category][subcategory]['unmasked_std_dev'][competitor] = 0
                    else:
                        results[category][subcategory]['unmasked_avg'][competitor] = 0
                        results[category][subcategory]['unmasked_std_dev'][competitor] = 0
            if 'masked_result' in results[category][subcategory]:
                masked_result = results[category][subcategory]['masked_result']
                references = extract_references(masked_result)
                results[category][subcategory]['masked_references'] = references
            if 'unmasked_result' in results[category][subcategory]:
                results[category][subcategory]['unmasked_references'] = {}
                for competitor, result_text in results[category][subcategory]['unmasked_result'].items():
                    references = extract_references(result_text)
                    results[category][subcategory]['unmasked_references'][competitor] = references
    return results

def save_results(result_data, run_type="single", num_runs=1):
    """結果を保存する関数"""
    # 日付を取得
    today_date = get_today_str()

    # ファイル名の生成
    if run_type == "multiple":
        file_name = f"{today_date}_perplexity_sentiment_results_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_perplexity_sentiment_results.json"

    # ローカルに保存
    output_dir = "results"
    ensure_dir(output_dir)
    local_file = f"{output_dir}/{file_name}"

    # JSONを保存
    save_json(result_data, local_file)
    print(f"ローカルに保存しました: {local_file}")

    # S3に保存（認証情報がある場合のみ）
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        try:
            # S3のパスを設定 (results/perplexity_sentiment/日付/ファイル名)
            s3_key = f"results/perplexity_sentiment/{today_date}/{file_name}"

            # src.utils.storage_utilsのsave_jsonを使用してS3に保存
            result = save_json(result_data, local_file, s3_key)
            if result["s3"]:
                print(f"S3に保存完了: s3://{S3_BUCKET_NAME}/{s3_key}")
            else:
                print(f"S3への保存に失敗しました: 認証情報を確認してください")
                print(f"  バケット名: {S3_BUCKET_NAME}")
                print(f"  AWS認証キーの設定状態: ACCESS_KEY={'設定済み' if AWS_ACCESS_KEY else '未設定'}, SECRET_KEY={'設定済み' if AWS_SECRET_KEY else '未設定'}")
                print(f"  リージョン: {AWS_REGION}")
        except Exception as e:
            print(f"S3保存中にエラーが発生しました: {e}")
    else:
        print("S3認証情報が不足しています。AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_BUCKET_NAMEを環境変数で設定してください。")

    return local_file

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用して企業バイアスデータを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--no-analysis', action='store_true', help='バイアス分析を実行しない')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    parser.add_argument('--skip-openai', action='store_true', help='OpenAIの実行をスキップする（分析の一部として実行される場合）')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
        result = process_categories_with_multiple_runs(PERPLEXITY_API_KEY, categories, args.runs)
        result_file = get_local_path(today_date, "sentiment", "perplexity")
        save_results(result, "multiple", args.runs)
    else:
        print("Perplexity APIを使用して単一実行データを取得します")
        result = process_categories(PERPLEXITY_API_KEY, categories)
        result_file = get_local_path(today_date, "sentiment", "perplexity")
        save_results(result)

    print("データ取得処理が完了しました")

# 参照リンクを抽出する関数
def extract_references(text):
    """
    テキストから [数字] パターンを抽出する

    Parameters:
    -----------
    text : str
        参照リンクを含むテキスト

    Returns:
    --------
    list
        抽出された参照リンク番号のリスト
    """
    if not text:
        return []

    # 正規表現で [数字] パターンを抽出
    pattern = r'\[(\d+)\]'
    matches = re.findall(pattern, text)

    # 重複を排除して数値順にソート
    references = sorted(set(int(m) for m in matches))

    return references

# 理由抽出関数
def extract_reason(text):
    if not text:
        return ""
    parts = text.split('\n', 1)
    return parts[1].strip() if len(parts) > 1 else ""

if __name__ == "__main__":
    main()