#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIを使用してサービスのランキングを抽出するモジュール
"""

import os
import datetime
import time
import argparse
from dotenv import load_dotenv
from ..categories import get_categories, get_all_categories, load_yaml_categories
from ..prompts.prompt_manager import PromptManager
from ..utils.text_utils import extract_ranking_and_reasons
from ..utils.perplexity_api import PerplexityAPI
from ..utils.storage_utils import save_results, get_results_paths
from ..utils.storage_config import get_s3_key
import logging
import sys
import pprint

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# PromptManagerのインスタンスを作成
prompt_manager = PromptManager()

def collect_rankings(api_key, categories, num_runs=1):
    """
    各カテゴリ・サブカテゴリごとにサービスランキングを取得
    新しいデータ形式（ranking_summary＋official_url＋response_list）で出力
    """
    api = PerplexityAPI(api_key)
    results = {}

    # YAMLから公式URL情報を取得
    _, yaml_categories = load_yaml_categories()

    total_categories = get_all_categories()
    processed = 0

    for category, subcategories in categories.items():
        print(f"カテゴリ処理中: {category}")
        results[category] = {}

        for subcategory, services in subcategories.items():
            processed += 1
            print(f"サブカテゴリ処理中 ({processed}/{total_categories}): {subcategory}, サービス数: {len(services)}")

            if not services or subcategory.startswith('#'):
                print(f"  サブカテゴリ {subcategory} はスキップします（コメントアウトまたは空）")
                continue

            # 公式URLリストを取得
            # yaml_categories[category][subcategory]はdict型
            service_url_dict = {}
            try:
                service_url_dict = yaml_categories[category][subcategory]
            except Exception:
                service_url_dict = {s: [] for s in services}

            # 公式URLを1つだけ official_url として使う（なければ空文字）
            official_url_map = {s: (service_url_dict.get(s, [""])[0] if service_url_dict.get(s) else "") for s in services}

            subcategory_results = []  # 各回のランキング
            all_responses = []        # 各回の応答全文
            response_list = []        # 新形式: 各回のresponse＋url

            for run in range(num_runs):
                if num_runs > 1:
                    print(f"  実行 {run+1}/{num_runs}")

                prompt = prompt_manager.get_ranking_prompt(subcategory, services)
                models_to_try = api.get_models_to_try()
                response = None
                citations = []
                for model in models_to_try:
                    response, citations = api.call_perplexity_api(prompt, model=model)
                    if response:
                        break
                all_responses.append(response)
                print(f"  Perplexityからの応答:\n{response[:200]}...")

                # 改良された抽出関数を使用
                ranking, _ = extract_ranking_and_reasons(response, original_services=services)
                subcategory_results.append(ranking)

                # citationsリストから各サービス名を含むURLをランキング順に抽出
                url_list = []
                for s in ranking:
                    for c in citations:
                        url = c["url"] if isinstance(c, dict) and "url" in c else c
                        if s.lower() in url.lower() and url and url not in url_list:
                            url_list.append(url)

                response_list.append({
                    "answer": response,
                    "url": url_list
                })

                if len(ranking) != len(services):
                    print(f"  ⚠️ 警告: 抽出されたランキングが完全ではありません ({len(ranking)}/{len(services)})")
                else:
                    print(f"  ✓ ランキング抽出完了: {ranking}")

                if run < num_runs - 1 or processed < total_categories:
                    print("  APIレート制限を考慮して待機中...")
                    time.sleep(2)

            # 各サービスごとの順位を集計
            service_ranks = {service: [] for service in services}
            for ranking in subcategory_results:
                for idx, service in enumerate(ranking):
                    if service in service_ranks:
                        service_ranks[service].append(idx + 1)

            # 平均順位を計算して並べ替え
            avg_ranks = []
            for service, ranks in service_ranks.items():
                if ranks:
                    avg_rank = sum(ranks) / len(ranks)
                else:
                    avg_rank = -1
                    print(f"  ⚠️ 警告: サービス '{service}' はどのランキングにも現れませんでした")
                avg_ranks.append((service, avg_rank, ranks))
            avg_ranks.sort(key=lambda x: (x[1] < 0, x[1]))
            final_ranking = [item[0] for item in avg_ranks]

            # entitiesを作成（旧detailsをentitiesにリネーム）
            entities = {}
            for service, avg_rank, all_ranks in avg_ranks:
                entities[service] = {
                    "official_url": official_url_map.get(service, ""),
                    "avg_rank": avg_rank if avg_rank != -1 else "未ランク",
                    "all_ranks": all_ranks
                }

            results[category][subcategory] = {
                "prompt": prompt,
                "ranking_summary": {
                    "avg_ranking": final_ranking,
                    "entities": entities
                },
                "answer_list": response_list
            }

    return results

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用して企業ランキングデータを取得')
    parser.add_argument('--runs', type=int, default=1, help='実行回数（デフォルト: 1）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    try:
        # カテゴリとサービスの取得
        categories = get_categories()

        # 結果を保存するファイルパス
        today_date = datetime.datetime.now().strftime("%Y%m%d")
        paths = get_results_paths(today_date)

        if args.runs > 1:
            print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
        else:
            print("Perplexity APIを使用して単一実行データを取得します")

        if args.verbose:
            logging.info(f"{args.runs}回の実行を開始します")

        result = collect_rankings(PERPLEXITY_API_KEY, categories, args.runs)

        # --- すべてのカテゴリ・サブカテゴリのentities構造をprintで確認 ---
        for cat in result:
            for subcat in result[cat]:
                print(f"[DEBUG] result['{cat}']['{subcat}'] = ")
                pprint.pprint(result[cat][subcat])
        # --------------------------------------

        file_name = f"rankings_{args.runs}runs.json"
        local_path = os.path.join(paths["raw_data"]["perplexity"], file_name)
        s3_key = get_s3_key(file_name, today_date, "raw_data/perplexity")
        save_results(result, local_path, s3_key, verbose=args.verbose)

        print("データ取得処理が完了しました")
        if args.verbose:
            logging.info("データ取得処理が完了しました")
        print(f"結果は {local_path} に保存されました。")

    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        if args.verbose:
            logging.error(f"エラーが発生しました: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()