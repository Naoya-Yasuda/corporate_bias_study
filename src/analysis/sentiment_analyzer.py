#!/usr/bin/env python
# coding: utf-8

"""
感情分析モジュール
Perplexity APIを使用してテキストの感情分析を実行するモジュール

新しいPerplexity citationsデータ構造に対応：
- official_results: titleやsnippetがないため感情分析対象外
- reputation_results: titleとsnippetがあるため感情分析対象
"""

import os
import json
import datetime
import time
import argparse
import sys
from dotenv import load_dotenv
from tqdm import tqdm
import logging

# パスの設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.prompts.prompt_manager import PromptManager
from src.utils.storage_utils import save_results, get_results_paths
from src.utils.file_utils import load_json
from src.utils.storage_config import S3_BUCKET_NAME

# 環境変数の読み込み
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

# プロンプトマネージャーのインスタンスを作成
prompt_manager = PromptManager()

def analyze_sentiments(texts):
    """共通化されたPerplexity APIを使用して複数のテキストの感情分析を実行"""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    # 共通化されたPerplexity APIクラスを使用
    from src.utils.perplexity_api import PerplexityAPI

    try:
        # プロンプトを取得
        prompt = prompt_manager.get_sentiment_analysis_prompt(texts)

        # PerplexityAPIを初期化
        api = PerplexityAPI(PERPLEXITY_API_KEY)

        # API呼び出し（model引数のデフォルト値は "llama-3.1-sonar-large-128k-online" に統一）
        response_text, _ = api.call_perplexity_api(prompt, model="llama-3.1-sonar-large-128k-online")

        if response_text:
            sentiments = response_text.strip().lower().split(",")
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
    """Perplexityの結果ファイルを処理（新しいentities構造に対応）"""
    # 元のデータをそのまま使用
    results = data

    for category, subcategories in data.items():
        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            # 新しい構造: entities内の各サービスのreputation_resultsを処理
            entities = content.get("entities", {})

            for entity_name, entity_data in entities.items():
                # official_resultsは感情分析対象外（titleやsnippetがないため）
                # reputation_resultsのみ感情分析対象（titleとsnippetがある）
                reputation_results = entity_data.get("reputation_results", [])

                # titleとsnippetがあるもののみを対象とする（データ構造に基づく厳格なフィルタリング）
                valid_results = [
                    r for r in reputation_results
                    if r.get("title") and r.get("snippet") and
                    isinstance(r.get("title"), str) and isinstance(r.get("snippet"), str) and
                    r.get("title").strip() and r.get("snippet").strip()
                ]

                if valid_results:
                    print(f"  {entity_name}: {len(valid_results)}件の評判データを感情分析対象として処理")

                    # 5件ずつバッチ処理
                    for i in range(0, len(valid_results), 5):
                        batch = valid_results[i:i+5]
                        texts = [f"{result['title']} {result['snippet']}" for result in batch]
                        sentiments = analyze_sentiments(texts)

                        for result, sentiment in zip(batch, sentiments):
                            result["sentiment"] = sentiment

                        time.sleep(1)  # API制限対策
                else:
                    print(f"  {entity_name}: 感情分析対象のデータがありません（titleやsnippetが不足）")

    return results

def process_results_file(file_path, date_str, args):
    """結果ファイルを読み込んで感情分析を実行（S3対応）"""
    data = None

    try:
        # ローカルファイル読み込み試行
        if os.path.exists(file_path):
            if args.verbose:
                logging.info(f"ローカルファイルから読み込み: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            if args.verbose:
                logging.info(f"ローカルファイルが見つかりません: {file_path}")

            # S3から読み込み試行
            s3_key = f"results/perplexity_citations/{date_str}/{os.path.basename(file_path)}"
            if "perplexity_rankings" in file_path:
                s3_key = f"results/perplexity_rankings/{date_str}/{os.path.basename(file_path)}"
            elif "google_serp" in file_path:
                s3_key = f"results/google_serp/{date_str}/{os.path.basename(file_path)}"

            if args.verbose:
                logging.info(f"S3からの読み込み試行: s3://{S3_BUCKET_NAME}/{s3_key}")

            # S3パスを使用してfile_utils.load_json()を呼び出し
            s3_full_path = f"s3://{S3_BUCKET_NAME}/{s3_key}"
            data = load_json(s3_full_path)

            if data and args.verbose:
                logging.info(f"S3読み込み成功: {len(data) if isinstance(data, dict) else 'データ取得'}件")

    except Exception as e:
        if args.verbose:
            logging.error(f"ファイル読み込みエラー: {e}")
        return None

    if not data:
        if args.verbose:
            logging.error(f"データが読み込めませんでした: {file_path}")
        return None

    # ファイル名からデータタイプを判定
    if "google_serp" in file_path:
        if args.verbose:
            logging.info("Google SERPデータを処理しています...")
        return process_google_serp_results(data)
    elif "perplexity_citations" in file_path:
        if args.verbose:
            logging.info("Perplexity Citations（新構造）データを処理しています...")
        return process_perplexity_results(data)
    else:
        if args.verbose:
            logging.info(f"感情分析対象外のファイルです: {os.path.basename(file_path)}")
        return None

def main():
    """メイン関数"""
    # 引数処理
    parser = argparse.ArgumentParser(description='感情分析を実行し、結果を保存する')
    parser.add_argument('--date', help='分析対象の日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['citations', 'google_serp'], default='citations',
                        help='分析対象のデータタイプ（デフォルト: citations）')
    parser.add_argument('--runs', type=int, help='実行回数（ファイル名に含まれる）')
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
        logging.info(f"=== 感情分析開始 ===")
        logging.info(f"分析日付: {date_str}, データタイプ: {args.data_type}")
        if args.runs:
            logging.info(f"実行回数: {args.runs}")

    # 結果の保存先パスを取得
    paths = get_results_paths(date_str)

    # 入力ファイルのパスを取得
    if args.input_file:
        input_file = args.input_file
    else:
        if args.data_type == "citations":
            # citationsの場合は実行回数が必要
            if not args.runs:
                logging.error("citationsの場合、--runs オプションが必要です")
                return
            input_file = os.path.join(paths["perplexity_citations"], f"{date_str}_perplexity_citations_{args.runs}runs.json")
        elif args.data_type == "google_serp":
            # Google SERPの場合は実行回数不要
            input_file = os.path.join(paths["google_serp"], f"{date_str}_google_serp_results.json")
        else:
            logging.error(f"未対応のデータタイプです: {args.data_type}")
            return

    if args.verbose:
        logging.info(f"対象ファイル: {input_file}")
        logging.info(f"期待するS3パス: s3://{S3_BUCKET_NAME}/results/{args.data_type}/{date_str}/{os.path.basename(input_file)}")

    # 入力ファイルが感情分析対象かチェック
    if not ("google_serp" in input_file or "perplexity_citations" in input_file):
        logging.error(f"感情分析対象外のファイルです: {os.path.basename(input_file)}")
        logging.info("対象ファイル: google_serp または perplexity_citations を含むファイル名")
        return

    # 感情分析を実行
    result = process_results_file(input_file, date_str, args)
    if result is None:
        logging.error(f"感情分析をスキップしました")
        return

    if args.verbose:
        logging.info("感情分析が完了しました")

        # 元のファイル名で上書き保存（パス管理システムを使用）
    input_filename = os.path.basename(input_file)

    if "google_serp" in input_file:
        output_path = paths["google_serp"]
    elif "perplexity_citations" in input_file:
        output_path = paths["perplexity_citations"]
    else:
        # その他のファイル
        output_path = paths["perplexity_sentiment"]

    # パス管理システムから相対パスを取得してS3キーを生成
    local_path = os.path.join(output_path, input_filename)
    # パス管理システムに合わせてS3キーを生成（resultsプレフィックスを除去）
    s3_key = local_path.replace("\\", "/")
    if s3_key.startswith("results/"):
        s3_key = s3_key[8:]  # "results/"を除去

    if args.verbose:
        logging.info(f"上書き保存: {input_filename}")
        logging.info(f"保存パス: {local_path}")
        logging.info(f"S3キー: {s3_key}")
    try:
        save_results(result, local_path, s3_key, verbose=args.verbose)
        if args.verbose:
            logging.info(f"=== 感情分析完了 ===")
    except Exception as e:
        logging.error(f"結果保存エラー: {e}")

if __name__ == "__main__":
    main()