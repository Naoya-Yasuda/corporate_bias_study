#!/usr/bin/env python
# coding: utf-8

import time
import datetime
import os
from typing import Dict, Any, List
from ..categories import get_categories
from ..prompts.prompt_manager import PromptManager
from ..prompts.sentiment_prompts import extract_score
import numpy as np
import argparse
from ..utils.storage_utils import save_results, get_results_paths
from ..utils.storage_config import get_s3_key
from ..utils.perplexity_api import PerplexityAPI

# 新しいユーティリティをインポート
from ..utils import (
    get_config_manager, get_logger, setup_default_logging,
    handle_errors, log_api_call, log_data_operation,
    APIError, DataError
)

# ログ設定
logger = get_logger(__name__)

# 設定管理システムを使用
config_manager = get_config_manager()
api_config = config_manager.get_api_config()
storage_config = config_manager.get_storage_config()

# カテゴリとサービスの定義を取得
categories = get_categories()

# PromptManagerのインスタンスを作成
prompt_manager = PromptManager()

@handle_errors
def process_categories_with_multiple_runs(api_key: str, categories: Dict[str, Any], num_runs: int = 5) -> Dict[str, Any]:
    """複数回実行して平均値を取得（マスクあり・マスクなし両方とも各num_runs回ずつAPIを呼び出す）
    サービス名ごとにentities属性でまとめて出力する
    """
    api = PerplexityAPI(api_key)
    results = {}

    log_data_operation("開始", "sentiment_analysis", data_size=len(categories))
    logger.info(f"感情分析処理開始: {len(categories)}カテゴリ, {num_runs}回実行")
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
                "masked_prompt": prompt_manager.get_sentiment_prompt(subcategory, masked=True),
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
                masked_prompt = prompt_manager.get_sentiment_prompt(subcategory, masked=True)
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
                time.sleep(1.25)
    # マスクなし（各企業ごと） num_runs回
    for run in range(num_runs):
        print(f"マスクなし 実行 {run+1}/{num_runs}")
        for category, subcategories_data in categories.items():
            for subcategory, competitors in subcategories_data.items():
                for competitor in competitors:
                    unmasked_prompt = prompt_manager.get_sentiment_prompt(subcategory, masked=False, competitor=competitor)
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
                    time.sleep(1.25)
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
        setup_default_logging(verbose=True)
        logger.info("詳細ログモードが有効になりました")

    # APIキーの事前チェック
    perplexity_api_key = api_config.get('perplexity_api_key', '')
    if not perplexity_api_key or perplexity_api_key.startswith("your_"):
        print(f"エラー: 有効なPerplexity APIキーが設定されていません")
        print(f"現在の値: {perplexity_api_key}")
        print(f".envファイルでPERPLEXITY_API_KEYに実際のAPIキーを設定してください")
        exit(1)

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    paths = get_results_paths(today_date)

    if args.runs > 1:
        print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
        result = process_categories_with_multiple_runs(perplexity_api_key, categories, args.runs)
    else:
        print("Perplexity APIを使用して単一実行データを取得します")
        result = process_categories_with_multiple_runs(perplexity_api_key, categories, 1)

    file_name = f"sentiment_{args.runs}runs.json"
    local_path = os.path.join(paths["raw_data"]["perplexity"], file_name)
    # 環境変数STORAGE_MODEに基づいてS3保存を制御
    s3_key = get_s3_key(file_name, today_date, "raw_data/perplexity") if os.getenv('STORAGE_MODE') in ['s3', 'both', 'auto'] else None
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