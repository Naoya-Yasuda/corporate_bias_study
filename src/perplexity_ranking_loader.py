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

from src.categories import get_categories, get_all_categories
from src.prompts.ranking_prompts import get_ranking_prompt, extract_ranking, RANK_PATTERNS
from src.perplexity_bias_loader import PerplexityAPI  # 既存のPerplexity API Clientを再利用

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")

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

            for run in range(num_runs):
                if num_runs > 1:
                    print(f"  実行 {run+1}/{num_runs}")

                # プロンプト生成と送信
                prompt = get_ranking_prompt(subcategory, services)
                response = api.call_ai_api(prompt)
                print(f"  Perplexityからの応答:\n{response[:200]}...")  # 応答の一部を表示

                # ランキング抽出
                ranking = extract_ranking(response, services)
                subcategory_results.append(ranking)

                if len(ranking) != len(services):
                    print(f"  ⚠️ 警告: 抽出されたランキングが完全ではありません ({len(ranking)}/{len(services)})")
                else:
                    print(f"  ✓ ランキング抽出完了: {ranking}")

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
                    avg_rank = sum(ranks) / len(ranks) if ranks else float('inf')
                    avg_ranks.append((service, avg_rank, ranks))

                # 平均順位でソート
                avg_ranks.sort(key=lambda x: x[1])

                # 最終ランキング
                final_ranking = [item[0] for item in avg_ranks]
                rank_details = {item[0]: {"avg_rank": item[1], "all_ranks": item[2]} for item in avg_ranks}

                results[category][subcategory] = {
                    "services": services,
                    "all_rankings": subcategory_results,
                    "avg_ranking": final_ranking,
                    "rank_details": rank_details
                }
            else:
                # 単一実行の場合
                results[category][subcategory] = {
                    "services": services,
                    "ranking": subcategory_results[0]
                }

    return results

def save_results(result_data, run_type="single", num_runs=1):
    """結果をローカルとS3に保存"""
    # AWS認証情報を環境変数から取得
    aws_access_key = os.environ.get("AWS_ACCESS_KEY")
    aws_secret_key = os.environ.get("AWS_SECRET_KEY")
    aws_region = os.environ.get("AWS_REGION", "ap-northeast-1")

    # 日付を取得
    today_date = datetime.datetime.now().strftime("%Y%m%d")

    # ローカルに保存
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)

    # ファイル名の生成
    if run_type == "multiple":
        file_name = f"{today_date}_perplexity_rankings_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_perplexity_rankings.json"

    # ローカルに保存
    with open(f"{output_dir}/{file_name}", 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=4)

    print(f"ローカルに保存しました: {output_dir}/{file_name}")

    # S3に保存（認証情報がある場合のみ）
    if aws_access_key and aws_secret_key:
        try:
            # S3クライアントを作成
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )

            # S3バケット名を環境変数から取得
            s3_bucket_name = os.environ.get("S3_BUCKET_NAME")

            # JSONデータを文字列に変換
            json_data = json.dumps(result_data, ensure_ascii=False, indent=4)

            # S3のパスを設定 (results/perplexity_rankings/日付/ファイル名)
            s3_key = f"results/perplexity_rankings/{today_date}/{file_name}"

            # S3にアップロード
            s3_client.put_object(
                Bucket=s3_bucket_name,
                Key=s3_key,
                Body=json_data,
                ContentType="application/json"
            )

            print(f"S3に保存完了: s3://{s3_bucket_name}/{s3_key}")
        except Exception as e:
            print(f"S3へのアップロードエラー: {e}")

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用してサービスランキングデータを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--no-analysis', action='store_true', help='将来的なランキング分析を実行しない')
    args = parser.parse_args()

    # カテゴリとサービスの取得
    categories = get_categories()

    # 結果を保存するファイルパス
    today_date = datetime.datetime.now().strftime("%Y%m%d")
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回のランキング取得を実行します")
        result = collect_rankings(PERPLEXITY_API_KEY, categories, args.runs)
        result_file = f"results/{today_date}_perplexity_rankings_{args.runs}runs.json"
        save_results(result, "multiple", args.runs)
    else:
        print("Perplexity APIを使用して単一実行ランキング取得を実行します")
        result = collect_rankings(PERPLEXITY_API_KEY, categories)
        result_file = f"results/{today_date}_perplexity_rankings.json"
        save_results(result)

    print("ランキングデータ取得処理が完了しました")

    # 将来的にはランキングデータの分析もここに実装予定
    # ランキングデータはバイアス指標とは異なる分析が必要なため、現在は実装されていません
    if not args.no_analysis:
        print("\n注: 現在のバージョンではランキングデータの自動分析は実装されていません。")
        print("将来のバージョンで、市場シェアとの相関分析やランキングバイアス指標の計算が追加される予定です。")

if __name__ == "__main__":
    main()