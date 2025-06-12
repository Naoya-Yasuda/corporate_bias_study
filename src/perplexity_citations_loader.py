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
import traceback
from dotenv import load_dotenv

# 共通ユーティリティをインポート
from src.utils import (
    extract_domain,
    get_storage_config,
    get_results_paths
)
from src.utils.text_utils import is_official_domain
from src.utils.storage_utils import get_results_paths, save_results
from src.categories import get_categories, get_all_categories
from src.utils.perplexity_api import PerplexityAPI

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PPLX_API_KEY = os.environ.get("PERPLEXITY_API_KEY")


def perplexity_api(prompt, model=None):
    """
    Perplexity APIを使用して回答と引用を取得

    Parameters:
    -----------
    prompt : str
        プロンプト
    model : str
        使用するモデル (llama-3.1-sonar-large-128k-onlineなど)

    Returns:
    --------
    tuple (str, list)
        (回答テキスト, 引用のリスト)
    """
    if not PPLX_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    if model is None:
        model = PerplexityAPI.get_models_to_try()[0]

    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "あなたは役立つアシスタントです。回答には必ず[1]、[2]のような番号付き引用を含めてください。情報源を明確にすることが重要です。引用元は日本語ページ（.jpドメインや日本語サイト）を優先してください。"
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "include_citations": True,  # 引用情報を明示的に要求（パラメータ名修正）
        "stream": False  # 必ずストリーミングを無効化
    }

    try:
        print(f"  リクエスト送信中: {payload['model']}")
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            json=payload,
            headers=headers
        )

        # デバッグ: ステータスコードの確認
        print(f"  API ステータスコード: {response.status_code}")

        # レスポンスの解析
        try:
            data = response.json()
        except Exception as e:
            print(f"  JSONパース失敗: {e}")
            print(f"  レスポンス本文: {response.text[:500]}")
            return None, []

        # レスポンス全体の詳細デバッグ（機密情報に注意）
        print(f"  レスポンスの構造: {list(data.keys())}")
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            print(f"  choiceの構造: {list(choice.keys())}")
            if "message" in choice:
                message = choice["message"]
                print(f"  messageの構造: {list(message.keys())}")

                # CitationDataがある場合の処理
                if "citation_data" in message:
                    print(f"  citation_dataが見つかりました")
                    print(f"  citation_dataの内容: {message['citation_data']}")
                elif "citations" in message:
                    print(f"  citationsが見つかりました")
                    print(f"  citationsの内容: {message['citations']}")

                # リンクの検索
                if "content" in message:
                    content_preview = message["content"][:100]
                    links_exist = "[1]" in message["content"] or "[2]" in message["content"]
                    print(f"  回答に引用リンクあり: {links_exist}, プレビュー: {content_preview}...")

        if "error" in data:
            print(f"API エラー: {data['error']}")
            return None, []

        # 回答テキストを取得
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # 引用情報の検索 - citationsプロパティから直接取得
        citations = data.get("citations", [])
        if citations:
            print(f"  citationsプロパティから{len(citations)}件の引用情報を取得")
            print("\n参照URL:")
            # citationsが文字列のリストの場合、辞書のリストに変換
            if citations and isinstance(citations[0], str):
                citations = [{"url": url} for url in citations]

            for i, citation in enumerate(citations):
                url = citation.get("url", "") if isinstance(citation, dict) else citation
                print(f"{i+1}. {url}")

        # 引用情報が見つからない場合
        if not citations:
            print("  APIレスポンスから引用情報を取得できませんでした")
            print(f"  利用可能なプロパティ: {list(data.keys())}")

        return answer, citations
    except Exception as e:
        print(f"Perplexity API 呼び出しエラー: {e}")
        print(f"  スタックトレース: {traceback.format_exc()}")
        return None, []


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

    Parameters:
    -----------
    urls : list
        メタデータを取得するURLのリスト

    Returns:
    --------
    dict
        URLをキーとしたメタデータの辞書
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
                    time.sleep(2)  # 2秒待機

            except Exception as e:
                print(f"  URL {url} のメタデータ取得エラー: {e}")
                metadata_dict[url] = {"title": "", "snippet": ""}
                time.sleep(5)  # エラー時は5秒待機

        return metadata_dict
    except Exception as e:
        print(f"Google Custom Search API メタデータ一括取得エラー: {e}")
        return {url: {"title": "", "snippet": ""} for url in urls}


def collect_citation_rankings(categories):
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
    models_to_try = PerplexityAPI.get_models_to_try()

    # 全URLを収集するリスト（評判情報用のみ）
    reputation_urls = []

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
                answer = None
                citations = []
                for model in models_to_try:
                    if answer:
                        break
                    print(f"  検索クエリ実行（モデル: {model}）: {query}")
                    answer, citations = perplexity_api(query, model=model)
                    if answer:
                        print(f"  モデル {model} で成功")
                        break
                if not answer:
                    print("  ⚠️ 警告: すべてのモデルでAPIからの応答が取得できませんでした")
                    continue
                print(f"  Perplexityからの応答:\n{answer[:200]}...")
                print(f"  サービス: {service} の citations: {citations}")
                citation_data = []
                if citations:
                    for i, citation in enumerate(citations):
                        url = citation.get("url", "")
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
                print("  APIレート制限を考慮して待機中...")
                time.sleep(3)

            for service in services:
                query = f"{service} 評判 口コミ"
                answer = None
                citations = []
                for model in models_to_try:
                    if answer:
                        break
                    print(f"  検索クエリ実行（モデル: {model}）: {query}")
                    answer, citations = perplexity_api(query, model=model)
                    if answer:
                        print(f"  モデル {model} で成功")
                        break
                if not answer:
                    print("  ⚠️ 警告: すべてのモデルでAPIからの応答が取得できませんでした")
                    continue
                print(f"  Perplexityからの応答:\n{answer[:200]}...")
                print(f"  サービス: {service} の citations: {citations}")
                citation_data = []
                if citations:
                    for i, citation in enumerate(citations):
                        url = citation.get("url", "")
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
                print("  APIレート制限を考慮して待機中...")
                time.sleep(3)

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

    # 要約用のプロンプトを作成
    prompt = f"""
あなたは以下の{len(all_answers)}回分の回答を要約する専門家です。
日本における{subcategory}の主要企業（{', '.join(services)}）についての情報を要約してください。

各企業について:
1. 主な特徴と強み
2. 提供サービスの特色
3. 市場での位置づけ

これらをコンパクトにまとめてください。以下が要約対象の回答です:

"""

    # 全回答を追加（文字数制限に注意）
    max_length = 16000  # 安全のため適切な文字数に制限
    current_length = len(prompt)

    for i, answer in enumerate(all_answers):
        answer_snippet = f"\n--- 回答 {i+1} ---\n{answer['answer'][:2000]}..."  # 各回答は2000文字までに制限
        if current_length + len(answer_snippet) > max_length:
            prompt += "\n(回答の一部は長さの制限のため省略されました)"
            break
        prompt += answer_snippet
        current_length += len(answer_snippet)

    # 要約の指示を追加
    prompt += "\n\n上記の回答に基づいて、各企業の特徴、強み、サービスについて簡潔に要約してください。矛盾点があれば、より一般的な見解を優先してください。"

    # APIで要約を生成
    try:
        summary, _ = perplexity_api(prompt)
        return summary
    except Exception as e:
        print(f"要約生成中にエラーが発生しました: {e}")
        return "要約生成中にエラーが発生しました。"


def main():
    """メイン関数"""
    # 引数処理（コマンドライン引数があれば使用）
    parser = argparse.ArgumentParser(description='Perplexityを使用して引用リンクデータを取得')
    parser.add_argument('--multiple', action='store_true', help='複数回実行して平均を取得')
    parser.add_argument('--runs', type=int, default=5, help='実行回数（--multipleオプション使用時）')
    parser.add_argument('--no-analysis', action='store_true', help='引用分析を実行しない')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    parser.add_argument('--skip-openai', action='store_true', help='OpenAIの実行をスキップする（分析の一部として実行される場合）')
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
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回の引用リンク取得を実行します")
        if args.verbose:
            logging.info(f"{args.runs}回の実行を開始します")
        result = collect_citation_rankings(categories)
        file_name = f"{today_date}_perplexity_citations_{args.runs}runs.json"
        local_path = os.path.join(paths["perplexity_citations"], file_name)
        s3_key = f"results/perplexity_citations/{today_date}/{file_name}"
        save_results(result, local_path, s3_key, verbose=args.verbose)
    else:
        print("Perplexity APIを使用して単一実行引用リンク取得を実行します")
        if args.verbose:
            logging.info("単一実行を開始します")
        result = collect_citation_rankings(categories)
        file_name = f"{today_date}_perplexity_citations.json"
        local_path = os.path.join(paths["perplexity_citations"], file_name)
        s3_key = f"results/perplexity_citations/{today_date}/{file_name}"
        save_results(result, local_path, s3_key, verbose=args.verbose)

    print("引用リンク取得処理が完了しました")
    if args.verbose:
        logging.info("引用リンク取得処理が完了しました")


if __name__ == "__main__":
    main()