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
import logging
import re
from dotenv import load_dotenv
from tqdm import tqdm

from src.prompts.prompt_manager import PromptManager
from src.utils.storage_utils import save_results, load_json
from src.utils.storage_config import S3_BUCKET_NAME, get_s3_key, get_base_paths
from src.utils.perplexity_api import PerplexityAPI

# パスの設定
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 環境変数の読み込み
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

# プロンプトマネージャーのインスタンスを作成
prompt_manager = PromptManager()

def normalize_sentiment_response(response_text):
    """API応答を正規化して感情値のリストを返す"""
    if not response_text:
        return []

    # 改行で分割
    lines = response_text.strip().split('\n')
    sentiments = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # カンマ区切り形式を処理（番号付きも含む）
        if ',' in line:
            parts = line.split(',')
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # 番号付き形式 (例: "1. positive", "2. positive") を処理
                if re.match(r'^\d+\.\s*', part):
                    # 番号とドットを除去
                    sentiment = re.sub(r'^\d+\.\s*', '', part).strip()
                    sentiments.append(sentiment)
                else:
                    # 通常の感情値
                    sentiments.append(part)
        # 番号付き形式 (例: "1. positive") を処理（カンマなし）
        elif re.match(r'^\d+\.\s*', line):
            # 番号とドットを除去
            sentiment = re.sub(r'^\d+\.\s*', '', line).strip()
            sentiments.append(sentiment)
        else:
            # 単一の感情値
            sentiments.append(line)

    return sentiments

def extract_sentiment(sentiment_text):
    """感情値テキストからpositive/negative/unknownを抽出"""
    sentiment_text = sentiment_text.strip().lower()

    # より柔軟なマッチング
    if any(word in sentiment_text for word in ["positive", "pos", "good", "ポジティブ", "良い"]):
        return "positive"
    elif any(word in sentiment_text for word in ["negative", "neg", "bad", "ネガティブ", "悪い"]):
        return "negative"
    else:
        return "unknown"

def analyze_sentiments(texts: list[str], verbose: bool = False) -> list[str]:
    """PerplexityAPIクラスを使用して複数のテキストの感情分析を実行（loaderと同じ方式）"""
    if not PERPLEXITY_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    prompt = prompt_manager.get_sentiment_analysis_prompt(texts)
    model = os.environ.get("PERPLEXITY_DEFAULT_MODEL", "sonar")
    api = PerplexityAPI(PERPLEXITY_API_KEY)

    try:
        response_text, _ = api.call_perplexity_api(prompt, model=model)

        # DEBUG: API応答の生データを出力
        if verbose:
            print(f"    [DEBUG] API応答: '{response_text}'")

        if response_text:
            # 応答形式を正規化
            raw_sentiments = normalize_sentiment_response(response_text)

            # DEBUG: 正規化後の感情値を出力
            if verbose:
                print(f"    [DEBUG] 正規化後の感情値: {raw_sentiments}")

            result = []
            for sentiment in raw_sentiments:
                extracted_sentiment = extract_sentiment(sentiment)
                if verbose and extracted_sentiment == "unknown":
                    print(f"    [DEBUG] 認識できない感情値: '{sentiment}' -> 'unknown'に設定")
                result.append(extracted_sentiment)

            # 不足分を補完
            while len(result) < len(texts):
                if verbose:
                    print(f"    [DEBUG] 不足分を補完: texts数={len(texts)}, result数={len(result)}")
                result.append("unknown")

            return result
        else:
            if verbose:
                print(f"    [DEBUG] API応答が空のため、すべて'unknown'に設定")
            return ["unknown"] * len(texts)
    except Exception as e:
        print(f"Perplexity API リクエストエラー: {e}")
        return ["unknown"] * len(texts)

def process_google_search_results(data, args):
    """Google検索結果ファイルを処理（entities構造に対応）"""
    # 元のデータをそのまま使用
    results = data

    for category, subcategories in data.items():
        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}", disable=not args.verbose):
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

                # --- ログ出力をperplexityと完全に揃える ---
                if valid_results:
                    if args.verbose:
                        print(f"  {entity_name}: {len(valid_results)}件の評判データを感情分析対象として処理")

                    # 5件ずつバッチ処理
                    for i in range(0, len(valid_results), 5):
                        batch = valid_results[i:i+5]
                        texts = [f"{result['title']} {result['snippet']}" for result in batch]
                        if args.verbose:
                            print(f"    [DEBUG] entity={entity_name}, batch={i//5}, texts数={len(texts)}, texts={texts}")
                        sentiments = analyze_sentiments(texts, verbose=args.verbose)
                        if args.verbose:
                            print(f"    [DEBUG] entity={entity_name}, batch={i//5}, sentiments数={len(sentiments)}, sentiments={sentiments}")

                        for result, sentiment in zip(batch, sentiments):
                            result["sentiment"] = sentiment

                        time.sleep(1)  # API制限対策

                if invalid_results:
                    if args.verbose:
                        print(f"  {entity_name}: {len(invalid_results)}件のエントリーをsentiment='unknown'に設定（titleやsnippetが不足）")

                if not valid_results and not invalid_results:
                    if args.verbose:
                        print(f"  {entity_name}: 感情分析対象のデータがありません")

    return results

def process_perplexity_results(data, args):
    """Perplexityの結果ファイルを処理（新しいentities構造に対応）"""
    # 元のデータをそのまま使用
    results = data

    for category, subcategories in data.items():
        for subcategory, content in tqdm(subcategories.items(), desc=f"処理中: {category}", disable=not args.verbose):
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
                    if args.verbose:
                        print(f"  {entity_name}: {len(valid_results)}件の評判データを感情分析対象として処理")

                    # 5件ずつバッチ処理
                    for i in range(0, len(valid_results), 5):
                        batch = valid_results[i:i+5]
                        texts = [f"{result['title']} {result['snippet']}" for result in batch]
                        if args.verbose:
                            print(f"    [DEBUG] entity={entity_name}, batch={i//5}, texts数={len(texts)}, texts={texts}")
                        sentiments = analyze_sentiments(texts, verbose=args.verbose)
                        if args.verbose:
                            print(f"    [DEBUG] entity={entity_name}, batch={i//5}, sentiments数={len(sentiments)}, sentiments={sentiments}")

                        for result, sentiment in zip(batch, sentiments):
                            result["sentiment"] = sentiment

                        time.sleep(1)  # API制限対策

                if invalid_results:
                    if args.verbose:
                        print(f"  {entity_name}: {len(invalid_results)}件のエントリーをsentiment='unknown'に設定（titleやsnippetが不足）")

                if not valid_results and not invalid_results:
                    if args.verbose:
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
    if args.data_type == "raw_data/google":
        if args.verbose:
            logging.info("Google検索データを処理しています...")
        return process_google_search_results(data, args)
    elif args.data_type == "raw_data/perplexity":
        if args.verbose:
            logging.info("Perplexityデータを処理しています...")
        return process_perplexity_results(data, args)
    else:
        if args.verbose:
            logging.info(f"未対応のデータタイプです: {args.data_type}")
        return None

def main():
    """メイン関数"""
    # 引数処理
    parser = argparse.ArgumentParser(description='感情分析を実行し、結果を保存する')
    parser.add_argument('--date', help='分析対象の日付（YYYYMMDD形式）')
    parser.add_argument('--data-type', choices=['perplexity', 'google'], default='perplexity',
                        help='分析対象のデータタイプ（perplexity または google）')
    parser.add_argument('--runs', type=int, default=1, help='実行回数（ファイル名に含まれる、デフォルト: 1）')
    parser.add_argument('--input-file', help='入力ファイルのパス')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # 日付を取得（指定がなければ今日の日付）
    date_str = args.date or datetime.datetime.now().strftime("%Y%m%d")

    # 処理開始メッセージは常に表示
    print(f"=== 感情分析開始 ===")
    print(f"分析日付: {date_str}, データタイプ: {args.data_type}")
    if args.runs:
        print(f"実行回数: {args.runs}")

    if args.verbose:
        logging.info(f"=== 感情分析開始 ===")
        logging.info(f"分析日付: {date_str}, データタイプ: {args.data_type}")
        if args.runs:
            logging.info(f"実行回数: {args.runs}")

    # 結果の保存先パスを取得
    paths = get_base_paths(date_str)

    # data_typeを内部用に変換
    if args.data_type == 'google':
        internal_data_type = 'raw_data/google'
    elif args.data_type == 'perplexity':
        internal_data_type = 'raw_data/perplexity'
    else:
        logging.error(f"未対応のデータタイプです: {args.data_type}")
        return

    # 入力ファイルのパスを取得
    if args.input_file:
        input_file = args.input_file
    else:
        if internal_data_type == "raw_data/perplexity":
            input_file = os.path.join(paths["raw_data"]["perplexity"], f"citations_{args.runs}runs.json")
        elif internal_data_type == "raw_data/google":
            input_file = os.path.join(paths["raw_data"]["google"], "custom_search.json")
        else:
            logging.error(f"未対応のデータタイプです: {internal_data_type}")
            return

    if args.verbose:
        logging.info(f"対象ファイル: {input_file}")

    # data_typeが対応しているかチェック
    if internal_data_type not in ['raw_data/google', 'raw_data/perplexity']:
        logging.error(f"未対応のデータタイプです: {internal_data_type}")
        logging.info("対応データタイプ: raw_data/google または raw_data/perplexity")
        return

    # 万一google_searchやgoogleが指定された場合は明示的にエラー
    if internal_data_type in ['google_search', 'google']:
        logging.error(f"data_typeは'raw_data/google'を指定してください（指定値: {internal_data_type}）")
        return

    # 感情分析を実行
    result = process_results_file(input_file, date_str, argparse.Namespace(**{**vars(args), 'data_type': internal_data_type}))
    if result is None:
        logging.error(f"感情分析をスキップしました")
        return

    if args.verbose:
        logging.info("感情分析が完了しました")

        # 元のファイル名で上書き保存（パス管理システムを使用）
    input_filename = os.path.basename(input_file)

    # data_typeによる正確な保存パス判定
    if internal_data_type == "raw_data/google":
        output_path = paths["raw_data"]["google"]
    elif internal_data_type == "raw_data/perplexity":
        output_path = paths["raw_data"]["perplexity"]
    else:
        output_path = paths["perplexity_sentiment"]

    # パス管理システムを使用した保存パス構築
    local_path = os.path.join(output_path, input_filename)

    s3_key = get_s3_key(input_filename, date_str, internal_data_type)

    if args.verbose:
        logging.info(f"上書き保存: {input_filename}")
        logging.info(f"保存パス: {local_path}")
        logging.info(f"S3キー: {s3_key}")

    try:
        save_results(result, local_path, s3_key, verbose=args.verbose)
        print(f"=== 感情分析完了 ===")
        if args.verbose:
            logging.info(f"=== 感情分析完了 ===")
    except Exception as e:
        print(f"結果保存エラー: {e}")
        logging.error(f"結果保存エラー: {e}")

if __name__ == "__main__":
    main()