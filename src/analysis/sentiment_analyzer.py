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
from src.utils.storage_utils import save_results, get_results_paths, load_json
from src.utils.storage_config import S3_BUCKET_NAME, get_s3_key

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
            # 結果を文字列値で返す（"positive"/"negative"/"unknown"）
            result = []
            for sentiment in sentiments:
                sentiment = sentiment.strip()
                if sentiment == "positive":
                    result.append("positive")
                elif sentiment == "negative":
                    result.append("negative")
                else:
                    result.append("unknown")  # 不明な場合
            return result
        return ["unknown"] * len(texts)
    except Exception as e:
        print(f"Perplexity API リクエストエラー: {e}")
        return ["unknown"] * len(texts)

def process_google_search_results(data):
    """Google検索結果ファイルを処理（entities構造に対応）"""
    # 元のデータをそのまま使用
    results = data

    for category, subcategories in data.items():
        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}"):
            # entities構造: 各サービスのreputation_resultsを処理
            entities = content.get("entities", {})

            for entity_name, entity_data in entities.items():
                # reputation_resultsのみ感情分析対象（titleとsnippetがある）
                reputation_results = entity_data.get("reputation_results", [])

                # titleとsnippetがあるもののみを対象とする（データ構造に基づく厳格なフィルタリング）
                valid_results = [
                    r for r in reputation_results
                    if r.get("title") and r.get("snippet") and
                    isinstance(r.get("title"), str) and isinstance(r.get("snippet"), str) and
                    r.get("title").strip() and r.get("snippet").strip()
                ]

                # titleやsnippetが空のエントリーはsentiment="unknown"に設定
                invalid_results = [
                    r for r in reputation_results
                    if not (r.get("title") and r.get("snippet") and
                    isinstance(r.get("title"), str) and isinstance(r.get("snippet"), str) and
                    r.get("title").strip() and r.get("snippet").strip())
                ]

                # titleやsnippetが空のエントリーにsentiment="unknown"を設定
                for result in invalid_results:
                    result["sentiment"] = "unknown"

                if valid_results:
                    print(f"  {entity_name}: {len(valid_results)}件の評判データを感情分析対象として処理")

                    # 5件ずつバッチ処理
                    for i in range(0, len(valid_results), 5):
                        batch = valid_results[i:i+5]
                        texts = [f"{result['title']} {result['snippet']}" for result in batch]
                        print(f"    [DEBUG] entity={entity_name}, batch={i//5}, texts数={len(texts)}, texts={texts}")
                        sentiments = analyze_sentiments(texts)
                        print(f"    [DEBUG] entity={entity_name}, batch={i//5}, sentiments数={len(sentiments)}, sentiments={sentiments}")

                        for result, sentiment in zip(batch, sentiments):
                            result["sentiment"] = sentiment

                        time.sleep(1)  # API制限対策

                if invalid_results:
                    print(f"  {entity_name}: {len(invalid_results)}件のエントリーをsentiment='unknown'に設定（titleやsnippetが不足）")

                if not valid_results and not invalid_results:
                    print(f"  {entity_name}: 感情分析対象のデータがありません")

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

                # titleやsnippetが空のエントリーはsentiment="unknown"に設定
                invalid_results = [
                    r for r in reputation_results
                    if not (r.get("title") and r.get("snippet") and
                    isinstance(r.get("title"), str) and isinstance(r.get("snippet"), str) and
                    r.get("title").strip() and r.get("snippet").strip())
                ]

                # titleやsnippetが空のエントリーにsentiment="unknown"を設定
                for result in invalid_results:
                    result["sentiment"] = "unknown"

                if valid_results:
                    print(f"  {entity_name}: {len(valid_results)}件の評判データを感情分析対象として処理")

                    # 5件ずつバッチ処理
                    for i in range(0, len(valid_results), 5):
                        batch = valid_results[i:i+5]
                        texts = [f"{result['title']} {result['snippet']}" for result in batch]
                        print(f"    [DEBUG] entity={entity_name}, batch={i//5}, texts数={len(texts)}, texts={texts}")
                        sentiments = analyze_sentiments(texts)
                        print(f"    [DEBUG] entity={entity_name}, batch={i//5}, sentiments数={len(sentiments)}, sentiments={sentiments}")

                        for result, sentiment in zip(batch, sentiments):
                            result["sentiment"] = sentiment

                        time.sleep(1)  # API制限対策

                if invalid_results:
                    print(f"  {entity_name}: {len(invalid_results)}件のエントリーをsentiment='unknown'に設定（titleやsnippetが不足）")

                if not valid_results and not invalid_results:
                    print(f"  {entity_name}: 感情分析対象のデータがありません")

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

                        # S3から読み込み試行（パス管理システムを使用）
            s3_key = get_s3_key(os.path.basename(file_path), date_str, args.data_type)

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
    if args.data_type == "google_search":
        if args.verbose:
            logging.info("Google検索データを処理しています...")
        return process_google_search_results(data)
    elif args.data_type == "perplexity_citations":
        if args.verbose:
            logging.info("Perplexity Citations（新構造）データを処理しています...")
        return process_perplexity_results(data)
    else:
        if args.verbose:
            logging.info(f"未対応のデータタイプです: {args.data_type}")
        return None

def main():
    """メイン関数"""
    # 引数処理
    parser = argparse.ArgumentParser(description='感情分析を実行し、結果を保存する')
    parser.add_argument('--date', help='分析対象の日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['perplexity_citations', 'google_search'], default='perplexity_citations',
                        help='分析対象のデータタイプ（デフォルト: perplexity_citations）')
    parser.add_argument('--runs', type=int, default=1, help='実行回数（ファイル名に含まれる、デフォルト: 1）')
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
        if args.data_type == "perplexity_citations":
            # perplexity_citationsの場合は実行回数を使用
            input_file = os.path.join(paths["perplexity_citations"], f"citations_{args.runs}runs.json")
        elif args.data_type == "google_search":
            # Google検索の場合は実行回数不要
            input_file = os.path.join(paths["google"], "custom_search.json")
        else:
            logging.error(f"未対応のデータタイプです: {args.data_type}")
            return

    if args.verbose:
        logging.info(f"対象ファイル: {input_file}")
        logging.info(f"期待するS3パス: s3://{S3_BUCKET_NAME}/results/{args.data_type}/{date_str}/{os.path.basename(input_file)}")

    # data_typeが対応しているかチェック
    if args.data_type not in ['google_search', 'perplexity_citations']:
        logging.error(f"未対応のデータタイプです: {args.data_type}")
        logging.info("対応データタイプ: google_search または perplexity_citations")
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

    if "google_search" in input_file:
        output_path = paths["google"]
    elif "perplexity_citations" in input_file:
        output_path = paths["perplexity_citations"]
    else:
        # その他のファイル
        output_path = paths["perplexity_sentiment"]

                # パス管理システムを使用した保存パス構築
    local_path = os.path.join(output_path, input_filename)

    s3_key = get_s3_key(input_filename, date_str, args.data_type)

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