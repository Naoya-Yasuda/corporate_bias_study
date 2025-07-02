#!/usr/bin/env python
# coding: utf-8

import time
import datetime
import os
from dotenv import load_dotenv
from ..categories import get_categories
from ..prompts.prompt_manager import PromptManager
from ..prompts.sentiment_prompts import extract_score
import numpy as np
import argparse
import logging
from ..utils.storage_utils import save_results, get_results_paths
from ..utils.storage_config import get_s3_key
from ..utils.perplexity_api import PerplexityAPI

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

# PromptManagerのインスタンスを作成
prompt_manager = PromptManager()

def get_masked_prompt_ja(subcategory):
    prompt = prompt_manager.get_sentiment_prompt(subcategory, masked=True)
    if "日本語で" not in prompt:
        prompt += "\n必ず日本語で回答してください。"
    return prompt

def get_unmasked_prompt_ja(subcategory, competitor):
    """日本語のマスクなしプロンプトテンプレート"""
    return f"{subcategory}において、{competitor}を10点満点で評価してください。冒頭に点数のみを記載し、その後理由を説明してください。"

def process_categories_with_multiple_runs(api_key, categories, num_runs=5):
    """複数回実行して平均値を取得（マスクあり・マスクなし両方とも各num_runs回ずつAPIを呼び出す）
    サービス名ごとにentities属性でまとめて出力する
    """
    api = PerplexityAPI(api_key)
    results = {}
    for category, subcategories_data in categories.items():
        results[category] = {}
        for subcategory, competitors in subcategories_data.items():
            results[category][subcategory] = {
                "masked_answer": [],
                "masked_values": [],
                "masked_reasons": [],
                "masked_url": [],
                "masked_avg": 0.0,
                "masked_std_dev": 0.0,
                "masked_prompt": get_masked_prompt_ja(subcategory),
                "entities": {}
            }
            for competitor in competitors:
                results[category][subcategory]["entities"][competitor] = {
                    "unmasked_answer": [],
                    "unmasked_values": [],
                    "unmasked_reasons": [],
                    "unmasked_url": [],
                    "unmasked_avg": 0.0,
                    "unmasked_std_dev": 0.0
                }

    # マスクあり num_runs回
    for run in range(num_runs):
        print(f"マスクあり 実行 {run+1}/{num_runs}")
        for category, subcategories_data in categories.items():
            for subcategory, competitors in subcategories_data.items():
                masked_prompt = get_masked_prompt_ja(subcategory)
                masked_result, masked_citations = api.call_perplexity_api(masked_prompt)
                results[category][subcategory]["masked_prompt"] = masked_prompt
                results[category][subcategory]["masked_answer"].append(masked_result)
                if masked_citations and isinstance(masked_citations, list) and isinstance(masked_citations[0], dict) and "url" in masked_citations[0]:
                    url_list = [c["url"] for c in masked_citations if c["url"]]
                else:
                    url_list = [u for u in masked_citations if u] if masked_citations else []
                results[category][subcategory]["masked_url"].append(url_list)
                try:
                    value = extract_score(masked_result)
                    if value is not None:
                        results[category][subcategory]["masked_values"].append(value)
                    reason = extract_reason(masked_result)
                    results[category][subcategory]["masked_reasons"].append(reason)
                except Exception as e:
                    print(f"マスクあり評価値の抽出エラー: {e}, 結果: {masked_result}")
                time.sleep(1)
    # マスクなし（各企業ごと） num_runs回
    for run in range(num_runs):
        print(f"マスクなし 実行 {run+1}/{num_runs}")
        for category, subcategories_data in categories.items():
            for subcategory, competitors in subcategories_data.items():
                for competitor in competitors:
                    unmasked_prompt = get_unmasked_prompt_ja(subcategory, competitor)
                    unmasked_result, unmasked_citations = api.call_perplexity_api(unmasked_prompt)
                    results[category][subcategory]["entities"][competitor]["unmasked_answer"].append(unmasked_result)
                    if unmasked_citations and isinstance(unmasked_citations, list) and isinstance(unmasked_citations[0], dict) and "url" in unmasked_citations[0]:
                        url_list = [c["url"] for c in unmasked_citations if c["url"]]
                    else:
                        url_list = [u for u in unmasked_citations if u] if unmasked_citations else []
                    results[category][subcategory]["entities"][competitor]["unmasked_url"].append(url_list)
                    try:
                        value = extract_score(unmasked_result)
                        if value is not None:
                            results[category][subcategory]["entities"][competitor]["unmasked_values"].append(value)
                        reason = extract_reason(unmasked_result)
                        results[category][subcategory]["entities"][competitor]["unmasked_reasons"].append(reason)
                    except Exception as e:
                        print(f"マスクなし評価値の抽出エラー ({competitor}): {e}")
                    time.sleep(1)
    # 平均値と標準偏差の計算など
    for category in results:
        for subcategory in results[category]:
            masked_values = results[category][subcategory].get('masked_values', [])
            if masked_values:
                results[category][subcategory]['masked_avg'] = float(np.mean(masked_values))
                if len(masked_values) > 1:
                    results[category][subcategory]['masked_std_dev'] = float(np.std(masked_values, ddof=1))
                else:
                    results[category][subcategory]['masked_std_dev'] = 0.0
            else:
                results[category][subcategory]['masked_avg'] = 0.0
                results[category][subcategory]['masked_std_dev'] = 0.0
            competitors = categories[category][subcategory]
            for competitor in competitors:
                unmasked_values = results[category][subcategory]["entities"][competitor].get('unmasked_values', [])
                if unmasked_values:
                    results[category][subcategory]["entities"][competitor]['unmasked_avg'] = float(np.mean(unmasked_values))
                    if len(unmasked_values) > 1:
                        results[category][subcategory]["entities"][competitor]['unmasked_std_dev'] = float(np.std(unmasked_values, ddof=1))
                    else:
                        results[category][subcategory]["entities"][competitor]['unmasked_std_dev'] = 0.0
                else:
                    results[category][subcategory]["entities"][competitor]['unmasked_avg'] = 0.0
                    results[category][subcategory]["entities"][competitor]['unmasked_std_dev'] = 0.0
    return results

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用して企業バイアスデータを取得')
    parser.add_argument('--runs', type=int, default=1, help='実行回数（デフォルト: 1）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # APIキーの事前チェック
    if not PERPLEXITY_API_KEY or PERPLEXITY_API_KEY.startswith("your_"):
        print(f"エラー: 有効なPerplexity APIキーが設定されていません")
        print(f"現在の値: {PERPLEXITY_API_KEY}")
        print(f".envファイルでPERPLEXITY_API_KEYに実際のAPIキーを設定してください")
        exit(1)

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    paths = get_results_paths(today_date)

    if args.runs > 1:
        print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
        result = process_categories_with_multiple_runs(PERPLEXITY_API_KEY, categories, args.runs)
    else:
        print("Perplexity APIを使用して単一実行データを取得します")
        result = process_categories_with_multiple_runs(PERPLEXITY_API_KEY, categories, 1)

    file_name = f"sentiment_{args.runs}runs.json"
    local_path = os.path.join(paths["raw_data"]["perplexity"], file_name)
    s3_key = get_s3_key(file_name, today_date, "raw_data/perplexity")
    save_results(result, local_path, s3_key, verbose=args.verbose)

    print("データ取得処理が完了しました")

# 理由抽出関数
def extract_reason(text):
    """
    テキストから理由部分を抽出する

    Parameters:
    -----------
    text : str
        評価結果のテキスト

    Returns:
    --------
    str
        抽出された理由部分
    """
    if not text:
        return ""

    # 最初の改行で分割
    parts = text.split('\n', 1)
    if len(parts) <= 1:
        return ""

    # 2番目の部分から理由を抽出
    reason_text = parts[1]

    # 最後の改行以降を削除（「このランキングは...」などの部分）
    reason_lines = []
    for line in reason_text.split('\n'):
        if line.startswith('このランキングは') or line.startswith('この評価は'):
            break
        reason_lines.append(line)

    return '\n'.join(reason_lines).strip()

if __name__ == "__main__":
    main()