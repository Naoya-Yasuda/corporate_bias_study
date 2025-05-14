#!/usr/bin/env python
# coding: utf-8

"""
ランキング抽出用のプロンプトテンプレート
単体実行する場合は: python -m src.prompts.ranking_prompts クラウドサービス "AWS,Azure,Google Cloud,IBM Cloud"
"""
import re
import sys
import argparse

# ランキング抽出用プロンプト
def get_ranking_prompt(subcategory, services):
    """ランキング抽出用のプロンプトを生成"""
    return (
        f"あなたは{subcategory}の専門家です。以下のサービスを「おすすめ順」に "
        "リストアップし、1行に1サービスだけ出力してください。\n\n"
        f"対象リスト: {', '.join(services)}\n\n"
        "出力例:\n1. サービスA\n2. サービスB\n..."
    )

# ランキング抽出用の正規表現パターン - より柔軟に異なる形式に対応
RANK_PATTERNS = [
    re.compile(r"^\s*\d+\.\s*([^\n]+)", re.MULTILINE),  # 1. Service
    re.compile(r"^\s*（?\d+）?\.\s*([^\n]+)", re.MULTILINE),  # （1）. Service や 1）. Service
    re.compile(r"^\s*\d+\s*[:：]\s*([^\n]+)", re.MULTILINE),  # 1: Service や 1：Service
    re.compile(r"^\s*[•●・]\s*([^\n]+)", re.MULTILINE),  # • Service や ● Service や ・Service
]

def extract_ranking(text, original_services):
    """Perplexityの回答から順位付きリストを抽出し、元のリストでフィルタリング"""
    # すべてのパターンで試行
    ranked = []

    # まずすべてのパターンを試し、もっとも多くのマッチを持つものを使用
    best_matches = []

    for pattern in RANK_PATTERNS:
        matches = [m.group(1).strip() for m in pattern.finditer(text)]
        if len(matches) > len(best_matches):
            best_matches = matches

    # マッチしたものを使用
    ranked = best_matches

    # それでもマッチしない場合、各サービス名が直接含まれているか確認
    if not ranked:
        print("⚠️ 正規表現パターンがマッチしませんでした。サービス名を直接検索します。")
        # 原文から各サービス名を直接検索（現れた順）
        for service in original_services:
            if service in text:
                ranked.append(service)

    # 想定外の表記ゆれ対策（大文字小文字・全角半角・空白など）
    norm = lambda s: re.sub(r"\s+", "", s).lower()
    orig_map = {norm(s): s for s in original_services}

    # 正規化した名前でマッチングし、元の正確な名前を使用
    cleaned = [orig_map.get(norm(r)) for r in ranked if norm(r) in orig_map]

    return cleaned

def main():
    """コマンドライン引数からプロンプトを生成してテストするための関数"""
    parser = argparse.ArgumentParser(description='ランキングプロンプト生成と抽出テスト')
    parser.add_argument('subcategory', help='サブカテゴリ名（例: クラウドサービス）')
    parser.add_argument('services', help='カンマ区切りのサービスリスト（例: "AWS,Azure,Google Cloud,IBM Cloud"）')
    parser.add_argument('--response', help='Perplexityの応答テキスト（指定しない場合はプロンプトのみ出力）')
    parser.add_argument('--file', help='Perplexityの応答テキストが含まれるファイルパス')
    args = parser.parse_args()

    # サービスリストをカンマで分割
    services = [s.strip() for s in args.services.split(',')]

    # プロンプト生成
    prompt = get_ranking_prompt(args.subcategory, services)
    print("【生成されたプロンプト】")
    print("=" * 50)
    print(prompt)
    print("=" * 50)

    # 応答テキストを取得
    response_text = None
    if args.response:
        response_text = args.response
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                response_text = f.read()
                print(f"\n応答テキストをファイル '{args.file}' から読み込みました")
        except Exception as e:
            print(f"ファイル読み込みエラー: {e}")

    # 応答が指定されている場合は抽出処理も実行
    if response_text:
        print("\n【Perplexityの応答テキスト】")
        print("-" * 50)
        print(response_text[:200] + "..." if len(response_text) > 200 else response_text)
        print("-" * 50)

        ranking = extract_ranking(response_text, services)
        print("\n【抽出されたランキング】")
        print("-" * 50)
        if ranking:
            for i, service in enumerate(ranking):
                print(f"{i+1}. {service}")
        else:
            print("⚠️ ランキングを抽出できませんでした")
        print("-" * 50)

        # 抽出漏れの検出
        missing = set(services) - set(ranking)
        if missing:
            print("\n⚠️ 抽出できなかったサービス:")
            for service in missing:
                print(f"・{service}")

if __name__ == "__main__":
    main()