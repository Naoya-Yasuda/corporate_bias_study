#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIの引用リンクを取得するモジュール

Perplexity APIを呼び出し、回答に含まれる引用リンクを順番に取得します。
"""

import os
import json
import datetime
import time
import argparse
import requests
import re
import traceback
from dotenv import load_dotenv
from urllib.parse import urlparse
from collections import defaultdict

# 共通ユーティリティをインポート
from src.utils import (
    extract_domain,
    ensure_dir,
    get_today_str,
    is_s3_enabled,
    get_storage_config,
    get_results_paths
)
from src.utils.text_utils import is_official_domain, is_negative
from src.utils.storage_utils import save_json
from src.utils.s3_utils import get_local_path
from src.categories import get_categories, get_all_categories

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PPLX_API_KEY = os.environ.get("PERPLEXITY_API_KEY")


def perplexity_api(query, model="llama-3.1-sonar-large-128k-online"):
    """
    Perplexity APIを使用して回答と引用を取得

    Parameters:
    -----------
    query : str
        検索クエリ
    model : str
        使用するモデル (llama-3.1-sonar-large-128k-onlineなど)

    Returns:
    --------
    tuple (str, list)
        (回答テキスト, 引用のリスト)
    """
    if not PPLX_API_KEY:
        raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "あなたは役立つアシスタントです。回答には必ず[1]、[2]のような番号付き引用を含めてください。情報源を明確にすることが重要です。"
            },
            {"role": "user", "content": query}
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
    SERP APIを使用して複数のURLのメタデータを一括取得する

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
        SERP_API_KEY = os.environ.get("SERP_API_KEY")
        if not SERP_API_KEY:
            raise ValueError("SERP_API_KEY が設定されていません。.env ファイルを確認してください。")

        # 重複を排除
        unique_urls = list(set(urls))
        print(f"  重複を排除: {len(urls)} -> {len(unique_urls)}件")

        # 結果を格納する辞書
        metadata_dict = {}

        # SERP APIのエンドポイント
        endpoint = "https://serpapi.com/search"

        # 各URLに対してメタデータを取得
        for i, url in enumerate(unique_urls):
            print(f"  URL {i+1}/{len(unique_urls)} のメタデータを取得中: {url}")

            # パラメータの設定
            params = {
                "api_key": SERP_API_KEY,
                "engine": "google",
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
                if "organic_results" in data and data["organic_results"]:
                    result = data["organic_results"][0]
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
        print(f"SERP API メタデータ一括取得エラー: {e}")
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
    models_to_try = [
        "llama-3.1-sonar-large-128k-online",  # デフォルトモデル
        "llama-3.1-sonar-large-128k",         # バックアップモデル
    ]

    # 全URLを収集するリスト
    all_urls = []

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

            subcategory_results = []
            # 各実行の回答テキストも保存
            all_answers = []

            # 各サービスについて公式/非公式情報を取得
            official_results = []
            for service in services:
                # 公式/非公式判定用の検索
                query = f"{service}"

                # すべてのモデルを試す
                answer = None
                citations = []

                for model in models_to_try:
                    if answer:  # 既に成功していれば次のモデルはスキップ
                        break

                    # API呼び出し
                    print(f"  検索クエリ実行（モデル: {model}）: {query}")
                    answer, citations = perplexity_api(query, model=model)

                    if answer:
                        print(f"  モデル {model} で成功")
                        break

                if not answer:
                    print("  ⚠️ 警告: すべてのモデルでAPIからの応答が取得できませんでした")
                    continue

                print(f"  Perplexityからの応答:\n{answer[:200]}...")  # 応答の一部を表示

                # 回答テキストを保存
                all_answers.append(answer)

                # 引用リンクの処理
                citation_data = []

                # APIからのcitationsがある場合はそれを使用
                if citations:
                    for i, citation in enumerate(citations):
                        # URLの取得を試みる（複数の可能性を考慮）
                        url = citation.get("url", "")
                        if not url:
                            url = citation.get("link", "")
                        if not url:
                            url = citation.get("source", "")
                        if not url:
                            url = citation.get("reference", "")

                        if url:
                            domain = extract_domain(url)
                            # 公式/非公式の判定を追加
                            is_official = is_official_domain(domain, None, {service: services[service]})
                            citation_data.append({
                                "rank": i + 1,  # 1-indexed
                                "url": url,
                                "domain": domain,
                                "is_official": is_official
                            })
                            # URLを収集リストに追加
                            all_urls.append(url)
                            print(f"  引用情報を取得: URL={url}, ドメイン={domain}, 公式={is_official}")

                    print(f"  APIから引用情報を取得: {len(citation_data)}件")

                if citation_data:
                    official_results.extend(citation_data)

                # API制限を考慮した待機
                print("  APIレート制限を考慮して待機中...")
                time.sleep(3)

            # 評判情報を取得
            reputation_results = []
            for service in services:
                # 評判情報用の検索
                query = f"{service} 評判 口コミ"

                # すべてのモデルを試す
                answer = None
                citations = []

                for model in models_to_try:
                    if answer:  # 既に成功していれば次のモデルはスキップ
                        break

                    # API呼び出し
                    print(f"  検索クエリ実行（モデル: {model}）: {query}")
                    answer, citations = perplexity_api(query, model=model)

                    if answer:
                        print(f"  モデル {model} で成功")
                        break

                if not answer:
                    print("  ⚠️ 警告: すべてのモデルでAPIからの応答が取得できませんでした")
                    continue

                print(f"  Perplexityからの応答:\n{answer[:200]}...")  # 応答の一部を表示

                # 回答テキストを保存
                all_answers.append(answer)

                # 引用リンクの処理
                citation_data = []

                # APIからのcitationsがある場合はそれを使用
                if citations:
                    for i, citation in enumerate(citations):
                        # URLの取得を試みる（複数の可能性を考慮）
                        url = citation.get("url", "")
                        if not url:
                            url = citation.get("link", "")
                        if not url:
                            url = citation.get("source", "")
                        if not url:
                            url = citation.get("reference", "")

                        if url:
                            domain = extract_domain(url)
                            citation_data.append({
                                "rank": i + 1,  # 1-indexed
                                "url": url,
                                "domain": domain,
                                "is_negative": is_negative(citation.get("title", ""), citation.get("snippet", ""))
                            })
                            # URLを収集リストに追加
                            all_urls.append(url)
                            print(f"  引用情報を取得: URL={url}, ドメイン={domain}, ネガティブ={citation_data[-1]['is_negative']}")

                    print(f"  APIから引用情報を取得: {len(citation_data)}件")

                if citation_data:
                    reputation_results.extend(citation_data)

                # API制限を考慮した待機
                print("  APIレート制限を考慮して待機中...")
                time.sleep(3)

            # 結果を統合
            if official_results or reputation_results:
                results[target_category][subcategory] = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "category": category,
                    "subcategory": subcategory,
                    "companies": services,
                    "official_results": official_results,
                    "reputation_results": reputation_results,
                    "all_answers": all_answers
                }

    # 全URLのメタデータを一括取得
    print("\n全URLのメタデータを一括取得中...")
    metadata_dict = get_metadata_from_serp(all_urls)

    # メタデータを各結果に追加
    for category in results:
        for subcategory in results[category]:
            data = results[category][subcategory]

            # 公式結果にメタデータを追加
            for result in data.get("official_results", []):
                url = result.get("url")
                if url and url in metadata_dict:
                    result.update(metadata_dict[url])

            # 評判結果にメタデータを追加
            for result in data.get("reputation_results", []):
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
        answer_snippet = f"\n--- 回答 {i+1} ---\n{answer[:2000]}..."  # 各回答は2000文字までに制限
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


def save_results(result_data, run_type="single", num_runs=1):
    """結果をローカルとS3に保存（新しいストレージAPI使用）"""
    # 日付を取得
    today_date = datetime.datetime.now().strftime("%Y%m%d")

    # ファイル名の生成
    if run_type == "multiple":
        file_name = f"{today_date}_perplexity_citations_{num_runs}runs.json"
    else:
        file_name = f"{today_date}_perplexity_citations.json"

    # パスの取得
    local_path, s3_path = get_results_paths("perplexity_citations", today_date, file_name)

    # ストレージ設定の取得（デバッグ用）
    storage_config = get_storage_config()
    print(f"ストレージ設定: {storage_config}")

    # 保存
    result = save_json(result_data, local_path, s3_path)

    if result["local"]:
        print(f"ローカルに保存しました: {local_path}")
    if result["s3"]:
        print(f"S3に保存しました: s3://{s3_path}")

    # 結果のサマリーを出力（引用情報の抽出が成功したかどうかの確認）
    print("\n=== 引用情報の抽出結果サマリー ===")
    total_citations = 0
    total_runs = 0

    # 各カテゴリとサブカテゴリについて
    for category, subcategories in result_data.items():
        if not subcategories:
            continue

        print(f"\nカテゴリ: {category}")

        for subcategory, data in subcategories.items():
            print(f"  サブカテゴリ: {subcategory}")

            # 複数回実行の場合
            if "all_runs" in data:
                runs_with_citations = 0
                citations_count = 0

                for run in data["all_runs"]:
                    if run.get("citations"):
                        runs_with_citations += 1
                        citations_count += len(run["citations"])

                total_runs += len(data["all_runs"])
                total_citations += citations_count

                print(f"    引用情報あり実行: {runs_with_citations}/{len(data['all_runs'])} ({runs_with_citations/len(data['all_runs'])*100:.1f}%)")
                print(f"    引用情報総数: {citations_count}件")

                # ドメインランキングがある場合
                if "domain_rankings" in data and data["domain_rankings"]:
                    print(f"    トップ引用ドメイン: {', '.join([d['domain'] for d in data['domain_rankings'][:3]])}")

            # 単一実行の場合
            elif "run" in data:
                citations_count = len(data["run"].get("citations", []))
                total_runs += 1
                total_citations += citations_count

                print(f"    引用情報: {citations_count}件")
                if "domains" in data and data["domains"]:
                    print(f"    引用ドメイン: {', '.join(data['domains'][:3])}")

    # 全体のサマリー
    if total_runs > 0:
        print(f"\n全体の引用情報密度: {total_citations/total_runs:.1f}件/実行")

    return local_path


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

    # 多重実行フラグがある場合は複数回実行
    if args.multiple:
        print(f"Perplexity APIを使用して{args.runs}回の引用リンク取得を実行します")
        if args.verbose:
            logging.info(f"{args.runs}回の実行を開始します")
        result = collect_citation_rankings(categories)
        result_file = get_local_path(today_date, "citations", "perplexity")
        save_results(result, "multiple", args.runs)
    else:
        print("Perplexity APIを使用して単一実行引用リンク取得を実行します")
        if args.verbose:
            logging.info("単一実行を開始します")
        result = collect_citation_rankings(categories)
        result_file = get_local_path(today_date, "citations", "perplexity")
        save_results(result)

    print("引用リンク取得処理が完了しました")
    if args.verbose:
        logging.info("引用リンク取得処理が完了しました")


if __name__ == "__main__":
    main()