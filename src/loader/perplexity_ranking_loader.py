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
from ..prompts.ranking_prompts import extract_ranking
from ..analysis.ranking_metrics import extract_ranking_and_reasons
from ..utils.perplexity_api import PerplexityAPI
from ..utils.storage_utils import save_results, get_results_paths
from ..utils.text_utils import extract_domain, is_official_domain
import logging
import sys

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
                models_to_try = PerplexityAPI.get_models_to_try()
                response = None
                citations = []
                for model in models_to_try:
                    response, citations = api.call_perplexity_api(prompt, model=model)
                    if response:
                        break
                all_responses.append(response)
                print(f"  Perplexityからの応答:\n{response[:200]}...")

                ranking, _ = extract_ranking_and_reasons(response, original_services=services)
                filtered_ranking = extract_ranking(response, services)
                subcategory_results.append(filtered_ranking)

                # citationsリストから各サービス名を含むURLをランキング順に抽出
                url_list = []
                for s in filtered_ranking:
                    for c in citations:
                        url = c["url"] if isinstance(c, dict) and "url" in c else c
                        if s.lower() in url.lower() and url and url not in url_list:
                            url_list.append(url)

                response_list.append({
                    "answer": response,
                    "url": url_list
                })

                if len(filtered_ranking) != len(services):
                    print(f"  ⚠️ 警告: 抽出されたランキングが完全ではありません ({len(filtered_ranking)}/{len(services)})")
                else:
                    print(f"  ✓ ランキング抽出完了: {filtered_ranking}")

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

            # ranking_summary.detailsを作成
            details = {}
            for service, avg_rank, all_ranks in avg_ranks:
                details[service] = {
                    "official_url": official_url_map.get(service, ""),
                    "avg_rank": avg_rank if avg_rank != -1 else "未ランク",
                    "all_ranks": all_ranks
                }

            results[category][subcategory] = {
                "prompt": prompt,
                "ranking_summary": {
                    "avg_ranking": final_ranking,
                    "details": details,
                    "all_rankings": subcategory_results
                },
                "answer_list": response_list
            }

    return results

def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用して企業ランキングデータを取得')
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

    try:
        # カテゴリとサービスの取得
        categories = get_categories()

        # 結果を保存するファイルパス
        today_date = datetime.datetime.now().strftime("%Y%m%d")
        paths = get_results_paths(today_date)

        if args.multiple:
            print(f"Perplexity APIを使用して{args.runs}回の実行データを取得します")
            if args.verbose:
                logging.info(f"{args.runs}回の実行を開始します")
            result = collect_rankings(PERPLEXITY_API_KEY, categories, args.runs)
            file_name = f"{today_date}_perplexity_ranking_results_{args.runs}runs.json"
            local_path = os.path.join(paths["perplexity_rankings"], file_name)
            from src.utils.storage_config import get_s3_key
            s3_key = get_s3_key(file_name, today_date, "perplexity_rankings")
            save_results(result, local_path, s3_key, verbose=args.verbose)
        else:
            print("Perplexity APIを使用して単一実行データを取得します")
            result = process_categories(PERPLEXITY_API_KEY, categories)
            file_name = f"{today_date}_perplexity_ranking_results.json"
            local_path = os.path.join(paths["perplexity_rankings"], file_name)
            s3_key = get_s3_key(file_name, today_date, "perplexity_rankings")
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