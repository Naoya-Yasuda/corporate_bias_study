#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIを使用してサービスのランキングを抽出するモジュール
"""

import os
import json
import datetime
import time
import boto3
import argparse
from dotenv import load_dotenv
import re

from src.categories import get_categories, get_all_categories
from src.prompts.ranking_prompts import get_ranking_prompt, extract_ranking, RANK_PATTERNS
from src.analysis.ranking_metrics import extract_ranking_and_reasons
from src.perplexity_sentiment_loader import PerplexityAPI  # 既存のPerplexity API Clientを再利用

# 共通ユーティリティをインポート
from src.utils.file_utils import ensure_dir, get_today_str
from src.utils.storage_utils import save_json, get_local_path, get_results_paths, put_json_to_s3
from src.utils.text_utils import extract_domain, is_official_domain

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

def extract_domains_from_response(response, services, official_domains):
    """Perplexityの応答からドメインを抽出し、公式/非公式を判定"""
    # URLを抽出する正規表現パターン
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    urls = re.findall(url_pattern, response)

    domains = []
    for url in urls:
        domain = extract_domain(url)
        if domain:
            # 各サービスについてドメインが関連しているか確認
            for service in services:
                if service.lower() in domain.lower():
                    # 公式ドメインリストを使用して判定
                    is_official = is_official_domain(domain, service, official_domains.get(service, []))
                    domains.append({
                        "domain": domain,
                        "service": service,
                        "is_official": is_official
                    })
                    break

    return domains

def collect_rankings(api_key, categories, num_runs=1):
    """
    各カテゴリ・サブカテゴリごとにサービスランキングを取得

    Args:
        api_key: Perplexity API Key
        categories: カテゴリとサービスの辞書
        num_runs: 実行回数（複数回実行で平均を取る場合）

    Returns:
        dict: カテゴリごとのランキング結果
    """
    api = PerplexityAPI(api_key)
    results = {}

    total_categories = get_all_categories()
    processed = 0

    for category, subcategories in categories.items():
        print(f"カテゴリ処理中: {category}")
        results[category] = {}

        for subcategory, services in subcategories.items():
            processed += 1
            print(f"サブカテゴリ処理中 ({processed}/{total_categories}): {subcategory}, サービス数: {len(services)}")

            if not services or subcategory.startswith('#'):  # コメントアウトされたカテゴリは無視
                print(f"  サブカテゴリ {subcategory} はスキップします（コメントアウトまたは空）")
                continue

            subcategory_results = []
            subcategory_reasons = []  # 各実行ごとの理由配列
            all_responses = []  # 全ての応答テキストを保存
            all_domains = []  # 全てのドメイン情報を保存

            for run in range(num_runs):
                if num_runs > 1:
                    print(f"  実行 {run+1}/{num_runs}")

                # プロンプト生成と送信
                prompt = get_ranking_prompt(subcategory, services)
                response = api.call_ai_api(prompt)
                all_responses.append(response)  # 応答テキストを保存
                print(f"  Perplexityからの応答:\n{response[:200]}...")  # 応答の一部を表示

                # ドメイン情報を抽出（公式ドメインリストを使用して判定）
                domains = extract_domains_from_response(response, services, services)
                all_domains.append(domains)

                # ランキング・理由抽出
                ranking, reasons = extract_ranking_and_reasons(response)
                # サービス名の正規化・フィルタリングは従来通りextract_rankingで
                filtered_ranking = extract_ranking(response, services)
                # 理由もランキングと同じ順序でフィルタリング
                filtered_reasons = []
                for s in filtered_ranking:
                    try:
                        idx = ranking.index(s)
                        filtered_reasons.append(reasons[idx] if idx < len(reasons) else "")
                    except Exception:
                        filtered_reasons.append("")
                subcategory_results.append(filtered_ranking)
                subcategory_reasons.append(filtered_reasons)

                if len(filtered_ranking) != len(services):
                    print(f"  ⚠️ 警告: 抽出されたランキングが完全ではありません ({len(filtered_ranking)}/{len(services)})")
                else:
                    print(f"  ✓ ランキング抽出完了: {filtered_ranking}")

                # API制限を考慮した待機
                if run < num_runs - 1 or processed < total_categories:
                    print("  APIレート制限を考慮して待機中...")
                    time.sleep(2)

            # 結果の集計（複数回実行の場合）
            if num_runs > 1:
                # 各サービスごとの順位を集計
                service_ranks = {service: [] for service in services}
                for ranking in subcategory_results:
                    for idx, service in enumerate(ranking):
                        if service in service_ranks:
                            service_ranks[service].append(idx + 1)  # 順位は1始まり

                # 平均順位を計算して並べ替え
                avg_ranks = []
                for service, ranks in service_ranks.items():
                    # ランキングに現れた場合は平均順位を計算、そうでなければ特別な値を使用
                    if ranks:
                        avg_rank = sum(ranks) / len(ranks)
                    else:
                        # JSON互換の値を使用（Infinityは使わない）
                        avg_rank = -1  # または高い値（例: len(services) + 1）
                        print(f"  ⚠️ 警告: サービス '{service}' はどのランキングにも現れませんでした")

                    avg_ranks.append((service, avg_rank, ranks))

                # 平均順位でソート（未ランクのサービスは最後に）
                avg_ranks.sort(key=lambda x: (x[1] < 0, x[1]))

                # 最終ランキング
                final_ranking = [item[0] for item in avg_ranks]
                rank_details = {item[0]: {"avg_rank": item[1], "all_ranks": item[2]} for item in avg_ranks}

                results[category][subcategory] = {
                    "services": services,
                    "query": prompt,  # プロンプトをqueryプロパティとして保存
                    "all_rankings": subcategory_results,
                    "all_reasons": subcategory_reasons,
                    "all_responses": all_responses,  # 全ての応答テキストを保存
                    "all_domains": all_domains,  # 全てのドメイン情報を保存
                    "avg_ranking": final_ranking,
                    "rank_details": rank_details
                }
            else:
                # 単一実行の場合
                results[category][subcategory] = {
                    "services": services,
                    "query": prompt,  # プロンプトをqueryプロパティとして保存
                    "ranking": subcategory_results[0],
                    "reasons": subcategory_reasons[0] if subcategory_reasons else [],
                    "response": all_responses[0],  # 応答テキストを保存
                    "domains": all_domains[0]  # ドメイン情報を保存
                }

    return results

def save_results(result_data, run_type="single", num_runs=1):
    """結果をローカルとS3に保存"""
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    paths = get_results_paths(today_date)
    if run_type == "multiple":
        file_name = f"{today_date}_perplexity_rankings_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_perplexity_rankings.json"
    local_file = os.path.join(paths["perplexity_rankings"], file_name)
    save_json(result_data, local_file)
    print(f"ローカルに保存しました: {local_file}")
    aws_access_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret_key = os.environ.get("AWS_SECRET_KEY")
    s3_bucket_name = os.environ.get("S3_BUCKET_NAME")
    if aws_access_key and aws_secret_key and s3_bucket_name:
        try:
            s3_key = f"results/perplexity_rankings/{today_date}/{file_name}"
            result = put_json_to_s3(result_data, s3_key)
            if result:
                print(f"S3に保存完了: s3://{s3_bucket_name}/{s3_key}")
            else:
                print(f"S3への保存に失敗しました: 認証情報を確認してください")
        except Exception as e:
            print(f"S3保存中にエラーが発生しました: {e}")
    else:
        print("S3認証情報が不足しています。AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_BUCKET_NAMEを環境変数で設定してください。")
    return local_file

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用してランキングデータを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    parser.add_argument('--skip-openai', action='store_true', help='OpenAIの実行をスキップする（分析の一部として実行される場合）')
    parser.add_argument('--max-retries', type=int, default=3, help='ランキング抽出に失敗した場合の最大再試行回数')
    parser.add_argument('--save-responses', action='store_true', help='完全な応答テキストを保存する')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # カテゴリとサービスの取得
    categories = get_categories()

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")

    # 多重実行フラグがある場合は複数回実行
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
        if args.verbose:
            logging.info(f"{args.runs}回の実行を開始します")

        try:
            # collect_rankings関数呼び出し時に引数を追加
            result = collect_rankings(PERPLEXITY_API_KEY, categories, args.runs)

            # Infinity値を修正（平均順位が-1などの場合、JSONシリアライズ前に文字列に変換）
            for category in result:
                for subcategory in result[category]:
                    if 'rank_details' in result[category][subcategory]:
                        for service, details in result[category][subcategory]['rank_details'].items():
                            if details.get('avg_rank') == float('inf') or details.get('avg_rank') == -1:
                                details['avg_rank'] = "未ランク"  # InfinityをJSON対応文字列に変換

            result_file = get_local_path(today_date, "rankings", "perplexity")
            if not os.path.exists(result_file):
                result_file = get_local_path(today_date, "rankings", "perplexity").replace("_10runs.json", ".json")
            save_results(result, "multiple", args.runs)
        except Exception as e:
            print(f"ランキングデータ収集中にエラーが発生しました: {e}")
            if args.verbose:
                import traceback
                logging.error(f"詳細エラー情報: {traceback.format_exc()}")
            return
    else:
        print("Perplexity APIを使用して単一実行データを取得します")
        if args.verbose:
            logging.info("単一実行を開始します")

        try:
            # collect_rankings関数呼び出し時に引数を追加
            result = collect_rankings(PERPLEXITY_API_KEY, categories)

            # Infinity値を修正
            for category in result:
                for subcategory in result[category]:
                    if 'rank_details' in result[category][subcategory]:
                        for service, details in result[category][subcategory]['rank_details'].items():
                            if details.get('avg_rank') == float('inf') or details.get('avg_rank') == -1:
                                details['avg_rank'] = "未ランク"  # InfinityをJSON対応文字列に変換

            result_file = get_local_path(today_date, "rankings", "perplexity")
            if not os.path.exists(result_file):
                result_file = get_local_path(today_date, "rankings", "perplexity").replace("_10runs.json", ".json")
            save_results(result)
        except Exception as e:
            print(f"ランキングデータ収集中にエラーが発生しました: {e}")
            if args.verbose:
                import traceback
                logging.error(f"詳細エラー情報: {traceback.format_exc()}")
            return

    print("データ取得処理が完了しました")
    if args.verbose:
        logging.info("データ取得処理が完了しました")

    # 完了メッセージ
    print("\n処理が完了しました。")
    print(f"結果は {result_file} に保存されました。")
    print("分析を実行するには、以下のコマンドを実行してください：")
    print(f"python -m src.analysis.ranking_metrics {result_file}")

if __name__ == "__main__":
    main()