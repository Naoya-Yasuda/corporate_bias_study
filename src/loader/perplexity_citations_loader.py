#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIの引用リンクを取得するモジュール

Perplexity APIを呼び出し、回答に含まれる引用リンクを順番に取得します。
"""

import os
import datetime
import time
import argparse
import requests
import re
from typing import Dict, Any, List, Optional

# 共通ユーティリティをインポート
from ..utils import (
    extract_domain,
    get_results_paths
)
from ..utils.text_utils import is_official_domain
from ..utils.storage_utils import get_results_paths, save_results
from ..utils.storage_config import get_s3_key
from ..categories import get_categories, get_all_categories
from ..utils.perplexity_api import PerplexityAPI
from ..prompts.prompt_manager import PromptManager

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

# プロンプトマネージャーのインスタンスを作成
prompt_manager = PromptManager()


def extract_references_from_text(text):
    """
    テキストから[1][2][3]形式の引用参照を抽出する

    Parameters:
    -----------
    text : str
        引用参照を含むテキスト

    Returns:
    --------
    list
        抽出された引用参照の辞書リスト（順番と番号）
    """
    if not text:
        return []

    # より堅牢な[数字]パターンの検出 - 文の途中や行末などさまざまな状況に対応
    pattern = r'\[(\d+)\](?:\s|\.|,|;|:|\)|\]|$)'
    matches = re.findall(pattern, text)

    if not matches:
        # バックアップとして、単純な[数字]パターンも試す
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, text)

    if not matches:
        return []

    # 重複を排除せずに出現順に保存
    references = []
    seen = set()
    for ref_num in matches:
        ref_int = int(ref_num)
        # 順序情報を含めつつ重複を排除
        ref_item = {
            "ref_num": ref_int,
            "rank": len(references) + 1  # 1-indexedの順位
        }
        # 同じ参照番号は一度だけ追加
        if ref_int not in seen:
            references.append(ref_item)
            seen.add(ref_int)

    return references


def extract_references_with_context(text):
    """
    テキストから[数字]形式の引用参照とその前後の文脈を抽出する

    Parameters:
    -----------
    text : str
        引用参照を含むテキスト

    Returns:
    --------
    list
        引用参照とその文脈を含む辞書のリスト
    """
    if not text:
        return []

    # [数字] パターンの位置を検出
    pattern = r'\[(\d+)\]'
    matches = list(re.finditer(pattern, text))

    if not matches:
        return []

    references = []
    seen = set()

    for match in matches:
        ref_num = int(match.group(1))
        if ref_num in seen:
            continue

        # 参照の前後の文脈を抽出（最大100文字ずつ）
        start_pos = max(0, match.start() - 100)
        end_pos = min(len(text), match.end() + 100)

        # 文脈の中から文を切り出す試み
        context_before = text[start_pos:match.start()]
        context_after = text[match.end():end_pos]

        # 最も近い文の区切りを見つける
        if '。' in context_before:
            context_before = context_before[context_before.rindex('。')+1:]
        if '。' in context_after:
            context_after = context_after[:context_after.index('。')+1]

        # 参照項目を作成
        ref_item = {
            "ref_num": ref_num,
            "rank": len(references) + 1,
            "context": context_before + match.group(0) + context_after,
            "position": match.start()
        }

        references.append(ref_item)
        seen.add(ref_num)

    # 出現位置順にソート
    references.sort(key=lambda x: x["position"])

    return references


def get_metadata_from_serp(urls):
    """
    Google Custom Search APIを使用して複数のURLのメタデータを一括取得する
    感情分析のためにtitleとsnippetを取得する。
    Perplexity APIではURLのみが返されるため、後からGoogle Custom Search APIで
    ページのタイトルとスニペットを取得して感情分析の精度を向上させる。

    Parameters:
    -----------
    urls : list
        メタデータを取得するURLのリスト

    Returns:
    --------
    dict
        URLをキーとしたメタデータ(titleとsnippet)の辞書
    """
    try:
        # 環境変数からAPIキーを取得
        GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID")
        if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
            raise ValueError("GOOGLE_API_KEY または GOOGLE_CSE_ID が設定されていません。.env ファイルを確認してください。")

        # 重複を排除
        unique_urls = list(set(urls))
        print(f"  重複を排除: {len(urls)} -> {len(unique_urls)}件")

        # 結果を格納する辞書
        metadata_dict = {}

        # Google Custom Search APIのエンドポイント
        endpoint = "https://www.googleapis.com/customsearch/v1"

        # 各URLに対してメタデータを取得
        for i, url in enumerate(unique_urls):
            print(f"  URL {i+1}/{len(unique_urls)} のメタデータを取得中: {url}")

            # パラメータの設定
            params = {
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CSE_ID,
                "q": url,
                "num": 1,  # 1件のみ取得
                "gl": "jp",  # 日本向け検索
                "hl": "ja"   # 日本語結果
            }

            try:
                # APIリクエスト
                response = requests.get(endpoint, params=params)

                # レート制限エラーの場合
                if response.status_code == 429:
                    print("  ⚠️ レート制限に達しました。60秒待機します...")
                    time.sleep(60)  # 60秒待機
                    response = requests.get(endpoint, params=params)  # 再試行

                response.raise_for_status()
                data = response.json()

                # 検索結果からメタデータを抽出
                if "items" in data and data["items"]:
                    result = data["items"][0]
                    metadata_dict[url] = {
                        "title": result.get("title", ""),
                        "snippet": result.get("snippet", "")
                    }
                else:
                    metadata_dict[url] = {"title": "", "snippet": ""}

                # レート制限を考慮して待機
                if i < len(unique_urls) - 1:
                    time.sleep(0.1)

            except Exception as e:
                print(f"  URL {url} のメタデータ取得エラー: {e}")
                metadata_dict[url] = {"title": "", "snippet": ""}
                time.sleep(5)  # エラー時は5秒待機

        return metadata_dict
    except Exception as e:
        print(f"Google Custom Search API メタデータ一括取得エラー: {e}")
        return {url: {"title": "", "snippet": ""} for url in urls}


@handle_errors
def collect_citation_rankings(categories: Dict[str, Any]) -> Dict[str, Any]:
    """
    各カテゴリ・サブカテゴリごとに引用リンクのランキングを取得

    Args:
        categories: カテゴリとサービスの辞書

    Returns:
        dict: カテゴリごとの引用リンクランキング結果
    """
    # 結果の初期化 - 主要カテゴリの構造を作成
    results = {}
    for category in categories.keys():
        results[category] = {}

    total_categories = get_all_categories()
    processed = 0

    # 試すモデル（成功するまで順に試す）
    api = PerplexityAPI(api_config.get('perplexity_api_key', ''))
    models_to_try = api.get_models_to_try()

    # 全URLを収集するリスト（評判情報用のみ）
    reputation_urls = []

    log_data_operation("開始", "citations_analysis", data_size=len(categories))
    logger.info(f"引用リンク分析処理開始: {len(categories)}カテゴリ")

    for category, subcategories in categories.items():
        print(f"カテゴリ処理中: {category}")

        # カテゴリ名は日本語のまま使用
        target_category = category

        for subcategory, services in subcategories.items():
            processed += 1
            print(f"サブカテゴリ処理中 ({processed}/{total_categories}): {subcategory}, サービス数: {len(services)}")

            if not services or subcategory.startswith('#'):  # コメントアウトされたカテゴリは無視
                print(f"  サブカテゴリ {subcategory} はスキップします（コメントアウトまたは空）")
                continue

            # サブカテゴリごとにentitiesの構造を初期化
            entities_results = {}
            for service in services:
                entities_results[service] = {
                    "official_answer": None,
                    "official_results": [],
                    "reputation_answer": None,
                    "reputation_results": []
                }

            # 各サービスについて公式/非公式情報を取得
            for service in services:
                query = f"{service}"
                api = PerplexityAPI(PPLX_API_KEY)
                answer, citations = api.call_perplexity_api(query)
                if answer:
                    print(f"  Perplexityからの応答:\n{answer[:200]}...")
                    print(f"  サービス: {service} の citations: {citations}")
                    citation_data = []
                    if citations:
                        for i, citation in enumerate(citations):
                            if isinstance(citation, dict):
                                url = citation.get("url", "")
                            else:
                                url = citation
                            if url:
                                domain = extract_domain(url)
                                is_official = is_official_domain(domain, service, {service: services[service]})
                                citation_item = {
                                    "rank": i + 1,
                                    "url": url,
                                    "domain": domain,
                                    "is_official": is_official
                                }
                                citation_data.append(citation_item)
                                print(f"  引用情報を取得: URL={url}, ドメイン={domain}, 公式={is_official}")
                        print(f"  APIから引用情報を取得: {len(citation_data)}件")
                    if citation_data:
                        entities_results[service]["official_results"] = citation_data
                        entities_results[service]["official_answer"] = answer
                        entities_results[service]["official_prompt"] = query
                    print("  APIレート制限を考慮して待機中...")
                    time.sleep(1.25)

            for service in services:
                query = f"{service} 評判 口コミ"
                api = PerplexityAPI(PPLX_API_KEY)
                answer, citations = api.call_perplexity_api(query)
                if answer:
                    print(f"  Perplexityからの応答:\n{answer[:200]}...")
                    print(f"  サービス: {service} の citations: {citations}")
                    citation_data = []
                    if citations:
                        for i, citation in enumerate(citations):
                            if isinstance(citation, dict):
                                url = citation.get("url", "")
                            else:
                                url = citation
                            if url:
                                domain = extract_domain(url)
                                citation_item = {
                                    "rank": i + 1,
                                    "url": url,
                                    "domain": domain
                                }
                                citation_data.append(citation_item)
                                reputation_urls.append(url)
                                print(f"  引用情報を取得: URL={url}, ドメイン={domain}")
                        print(f"  APIから引用情報を取得: {len(citation_data)}件")
                    if citation_data:
                        entities_results[service]["reputation_results"] = citation_data
                        entities_results[service]["reputation_answer"] = answer
                        entities_results[service]["reputation_prompt"] = query
                    print("  APIレート制限を考慮して待機中...")
                    time.sleep(1.25)

            # 結果を統合
            if any(entities_results[s]["official_results"] or entities_results[s]["reputation_results"] for s in services):
                results[target_category][subcategory] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "category": category,
                    "subcategory": subcategory,
                    "entities": entities_results
                }

    # 評判情報用のURLのメタデータのみ一括取得
    print("\n評判情報用のURLのメタデータを一括取得中...")
    all_urls = list(set(reputation_urls))
    metadata_dict = get_metadata_from_serp(all_urls)

    # メタデータを評判結果にのみ追加
    for category in results:
        for subcategory in results[category]:
            data = results[category][subcategory]
            for entity, entity_data in data.get("entities", {}).items():
                for result in entity_data.get("reputation_results", []):
                    url = result.get("url")
                    if url and url in metadata_dict:
                        result.update(metadata_dict[url])

    return results


def generate_summary(subcategory, services, all_answers):
    """
    複数回の実行結果を要約する

    Args:
        subcategory: サブカテゴリ名
        services: サービスのリスト
        all_answers: 全実行の回答テキスト

    Returns:
        str: 要約テキスト
    """
    print(f"複数回の実行結果を要約中: {subcategory}")

    # プロンプトを取得
    prompt = prompt_manager.get_citations_summary_prompt(subcategory, services, all_answers)

    # APIで要約を生成
    try:
        api = PerplexityAPI(PPLX_API_KEY)
        summary, _ = api.call_perplexity_api(prompt)
        return summary
    except Exception as e:
        print(f"要約生成中にエラーが発生しました: {e}")
        return "要約生成中にエラーが発生しました。"


def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用して引用リンクデータを取得')
    parser.add_argument('--runs', type=int, default=1, help='実行回数（デフォルト: 1）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
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
    paths = get_results_paths(today_date)

    if args.runs > 1:
        print(f"Perplexity APIを使用して{args.runs}回の引用リンク取得を実行します")
    else:
        print("Perplexity APIを使用して単一実行引用リンク取得を実行します")

    if args.verbose:
        logging.info(f"{args.runs}回の実行を開始します")

    result = collect_citation_rankings(categories)
    file_name = f"citations_{args.runs}runs.json"
    local_path = os.path.join(paths["raw_data"]["perplexity"], file_name)
    s3_key = get_s3_key(file_name, today_date, "raw_data/perplexity")
    save_results(result, local_path, s3_key, verbose=args.verbose)

    print("引用リンク取得処理が完了しました")
    if args.verbose:
        logging.info("引用リンク取得処理が完了しました")


if __name__ == "__main__":
    main()