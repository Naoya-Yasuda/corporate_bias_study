#!/usr/bin/env python
# coding: utf-8

"""
ランキング抽出用のプロンプトテンプレート
単体実行する場合:
- プロンプト生成: python -m src.prompts.ranking_prompts クラウドサービス "AWS,Azure,Google Cloud,IBM Cloud"
- APIテスト: python -m src.prompts.ranking_prompts クラウドサービス "AWS,Azure,Google Cloud" --api --runs 3
- テキスト抽出: python -m src.prompts.ranking_prompts クラウドサービス "AWS,Azure,Google Cloud" --response "..."
"""
import re
import sys
import os
import json
import time
import argparse
import statistics
from dotenv import load_dotenv

from src.utils.perplexity_api import PerplexityAPI

# .envファイルから環境変数を読み込む（APIキー取得のため）
load_dotenv()

# ランキング抽出用プロンプト
def get_ranking_prompt(subcategory, services):
    """ランキング抽出用のプロンプトを生成"""
    services_str = ', '.join(services)
    return (
        f"あなたは{subcategory}の専門家です。以下のサービスを「おすすめ順」に正確にランク付けしてください。\n\n"
        f"対象サービス: {services_str}\n\n"
        "【重要】以下の条件を厳守してください：\n"
        "1. 必ず全てのサービスをランク付けしてください。1つも省略しないでください。\n"
        "2. 番号付きリスト形式で回答してください（例: 1. サービスA: 理由A）\n"
        "3. 各行に1つのサービスのみを記載してください。\n"
        "4. 各サービスの順位ごとに、その理由も簡潔に記載してください。\n"
        "5. 余計な説明は不要です。ランキングと理由のみを出力してください。\n"
        "6. 必ず日本語で回答してください。\n\n"
        "出力例:\n1. サービスA: 理由A\n2. サービスB: 理由B\n3. サービスC: 理由C\n..."
    )

# ランキング抽出用の正規表現パターン - より柔軟に異なる形式に対応
RANK_PATTERNS = [
    re.compile(r"^\s*\d+\.\s*([^\n]+)", re.MULTILINE),  # 1. Service
    re.compile(r"^\s*（?\d+）?\.\s*([^\n]+)", re.MULTILINE),  # （1）. Service や 1）. Service
    re.compile(r"^\s*\d+\s*[:：]\s*([^\n]+)", re.MULTILINE),  # 1: Service や 1：Service
    re.compile(r"^\s*[•●・]\s*([^\n]+)", re.MULTILINE),  # • Service や ● Service や ・Service
    re.compile(r"^\s*#{1,3}\s*([^\n]+)", re.MULTILINE),  # # Service や ## Service や ### Service
    re.compile(r"\*\*([^*\n]+)\*\*", re.MULTILINE),  # **Service**
    re.compile(r"「([^」\n]+)」", re.MULTILINE),  # 「Service」
]

def extract_ranking(text, original_services):
    """Perplexityの回答から順位付きリストを抽出し、元のリストでフィルタリング"""
    # サービス名の正規化関数
    norm = lambda s: re.sub(r"[\s　]+", "", s).lower()

    # 元のサービス名を正規化して辞書に格納
    orig_map = {norm(s): s for s in original_services}

    # 各サービスが出現する順序をトラッキング
    found_services = []

    # まず順序付きリストのパターンを試す
    for pattern in RANK_PATTERNS:
        matches = [m.group(1).strip() for m in pattern.finditer(text)]
        if matches:
            # マッチした各項目について、サービス名が含まれるかを確認
            for match in matches:
                for service in original_services:
                    if service in match or norm(service) in norm(match):
                        if service not in found_services:
                            found_services.append(service)
                            break

    # パターンマッチで十分な結果が得られない場合、サービス名の出現順を確認
    if len(found_services) < len(original_services) * 0.8:  # 80%未満の場合
        print("⚠️ パターンマッチの結果が不十分です。サービス名の出現順で抽出します。")

        # 文章全体から各サービス名の出現位置を特定
        service_positions = []
        for service in original_services:
            pos = text.find(service)
            if pos >= 0:
                service_positions.append((pos, service))
            else:
                # 正規化した名前で探す
                for word in re.findall(r'\b\w+\b', text):
                    if norm(word) == norm(service):
                        pos = text.find(word)
                        if pos >= 0:
                            service_positions.append((pos, service))
                            break

        # 出現位置でソート
        service_positions.sort()
        new_found = [service for _, service in service_positions]

        # 既に見つかったサービスと組み合わせ
        for service in new_found:
            if service not in found_services:
                found_services.append(service)

    # 見つからなかったサービスを最後に追加
    missing_services = [s for s in original_services if s not in found_services]
    if missing_services:
        print(f"⚠️ 一部のサービスが見つかりませんでした。見つかったサービス数: {len(found_services)}/{len(original_services)}")
        print(f"  見つからなかったサービス: {missing_services}")
        print(f"  ⚠️ 警告: 抽出されたランキングが完全ではありません ({len(found_services)}/{len(original_services)})")
        # 見つからなかったサービスを最後に追加
        found_services.extend(missing_services)

    return found_services

def multi_run_ranking(subcategory, services, num_runs=5, api_key=None):
    """複数回実行してランキングの平均を計算"""
    print(f"{subcategory}の{num_runs}回ランキング取得を開始します...")

    # 各実行結果を保存するリスト
    all_rankings = []

    # 指定回数実行
    for run in range(num_runs):
        print(f"\n--- 実行 {run+1}/{num_runs} ---")

        # プロンプト生成と送信
        prompt = get_ranking_prompt(subcategory, services)
        print("プロンプト送信中...")
        api = PerplexityAPI(api_key)
        response, citations = api.call_perplexity_api(prompt)
        print(f"応答受信:\n{response[:200]}...")  # 応答の一部を表示

        # ランキング抽出
        ranking = extract_ranking(response, services)
        all_rankings.append(ranking)

        if len(ranking) != len(services):
            print(f"⚠️ 警告: 抽出されたランキングが完全ではありません ({len(ranking)}/{len(services)})")
        else:
            print(f"✓ ランキング抽出完了: {ranking}")

        # 最後の実行でなければ待機
        if run < num_runs - 1:
            print("APIレート制限を考慮して待機中...")
            time.sleep(2)

    # 結果の集計（平均ランキング計算）
    if all_rankings:
        print("\n=== 結果集計 ===")

        # 各サービスごとの順位を集計
        service_ranks = {service: [] for service in services}
        for ranking in all_rankings:
            for idx, service in enumerate(ranking):
                if service in service_ranks:
                    service_ranks[service].append(idx + 1)  # 順位は1始まり

        # 平均順位を計算して並べ替え
        avg_ranks = []
        for service, ranks in service_ranks.items():
            if ranks:
                avg_rank = sum(ranks) / len(ranks)
                std_dev = statistics.stdev(ranks) if len(ranks) > 1 else 0
                avg_ranks.append((service, avg_rank, std_dev, ranks))
            else:
                print(f"⚠️ サービス '{service}' はランキングに含まれていませんでした")

        # 平均順位でソート
        avg_ranks.sort(key=lambda x: x[1])

        # 結果表示
        print("\n【最終ランキング（平均順位）】")
        print("-" * 60)
        print(f"{'サービス名':<20} {'平均順位':<10} {'標準偏差':<10} {'全順位'}")
        print("-" * 60)
        for service, avg, std, ranks in avg_ranks:
            print(f"{service:<20} {avg:<10.2f} {std:<10.2f} {ranks}")

        # 最終ランキング（サービス名のみ）
        final_ranking = [item[0] for item in avg_ranks]
        print("\n最終ランキング:", final_ranking)

        # 結果をJSON形式で返却
        result = {
            "subcategory": subcategory,
            "services": services,
            "all_rankings": all_rankings,
            "avg_ranking": final_ranking,
            "rank_details": {
                item[0]: {
                    "avg_rank": item[1],
                    "std_dev": item[2],
                    "all_ranks": item[3]
                } for item in avg_ranks
            }
        }

        return result

    return {"error": "ランキングを取得できませんでした"}

def main():
    """コマンドライン引数からプロンプトを生成してテストするための関数"""
    parser = argparse.ArgumentParser(description='ランキングプロンプト生成と抽出テスト')
    parser.add_argument('subcategory', help='サブカテゴリ名（例: クラウドサービス）')
    parser.add_argument('services', help='カンマ区切りのサービスリスト（例: "AWS,Azure,Google Cloud,IBM Cloud"）')
    parser.add_argument('--answer', help='Perplexityの応答テキスト（指定しない場合はプロンプトのみ出力）')
    parser.add_argument('--file', help='Perplexityの応答テキストが含まれるファイルパス')
    parser.add_argument('--api', action='store_true', help='Perplexity APIを使用して実際に問い合わせる')
    parser.add_argument('--runs', type=int, default=5, help='API使用時の実行回数（デフォルト: 5）')
    parser.add_argument('--output', help='結果を保存するJSONファイルパス')
    args = parser.parse_args()

    # サービスリストをカンマで分割
    services = [s.strip() for s in args.services.split(',')]

    # プロンプト生成
    prompt = get_ranking_prompt(args.subcategory, services)
    print("【生成されたプロンプト】")
    print("=" * 60)
    print(prompt)
    print("=" * 60)

    result = None

    # APIを使用して複数回実行する場合
    if args.api:
        PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
        result = multi_run_ranking(args.subcategory, services, args.runs, api_key=PERPLEXITY_API_KEY)

    # 応答テキストを取得
    elif args.answer or args.file:
        answer_text = None
        if args.answer:
            answer_text = args.answer
        elif args.file:
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    answer_text = f.read()
                    print(f"\n応答テキストをファイル '{args.file}' から読み込みました")
            except Exception as e:
                print(f"ファイル読み込みエラー: {e}")

        # 応答が指定されている場合は抽出処理も実行
        if answer_text:
            print("\n【Perplexityの応答テキスト】")
            print("-" * 60)
            print(answer_text[:200] + "..." if len(answer_text) > 200 else answer_text)
            print("-" * 60)

            ranking = extract_ranking(answer_text, services)
            print("\n【抽出されたランキング】")
            print("-" * 60)
            if ranking:
                for i, service in enumerate(ranking):
                    print(f"{i+1}. {service}")
            else:
                print("⚠️ ランキングを抽出できませんでした")
            print("-" * 60)

            # 抽出漏れの検出
            missing = set(services) - set(ranking)
            if missing:
                print("\n⚠️ 抽出できなかったサービス:")
                for service in missing:
                    print(f"・{service}")

            # 結果をJSON形式で保存
            result = {
                "subcategory": args.subcategory,
                "services": services,
                "ranking": ranking,
                "answer": answer_text
            }

    # 結果をファイルに保存
    if result and args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n結果を '{args.output}' に保存しました")
        except Exception as e:
            print(f"ファイル保存エラー: {e}")

if __name__ == "__main__":
    main()