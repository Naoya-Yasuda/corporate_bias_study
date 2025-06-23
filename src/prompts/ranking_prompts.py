#!/usr/bin/env python
# coding: utf-8

"""
ランキング抽出用のプロンプトテンプレート
単体実行する場合:
- プロンプト生成: python -m src.prompts.ranking_prompts クラウドサービス "AWS,Azure,Google Cloud,IBM Cloud"
- テキスト抽出: python -m src.prompts.ranking_prompts クラウドサービス "AWS,Azure,Google Cloud" --answer "..."
"""
import re
import os
import json
import argparse
from dotenv import load_dotenv

from .prompt_manager import PromptManager
from src.utils.text_utils import extract_ranking_and_reasons

# .envファイルから環境変数を読み込む（APIキー取得のため）
load_dotenv()

# プロンプトマネージャーのインスタンスを作成
prompt_manager = PromptManager()

# ランキング抽出用プロンプト
def get_ranking_prompt(subcategory, services):
    """ランキング抽出用のプロンプトを生成"""
    return prompt_manager.get_ranking_prompt(subcategory, services)

def extract_ranking(text, services):
    """
    テキストからランキングを抽出する関数
    ranking_metricsのextract_ranking_and_reasons関数を使用
    """
    ranking, _ = extract_ranking_and_reasons(text, original_services=services)
    return ranking



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
        print("⚠️ API実行機能は perplexity_ranking_loader.py を使用してください")
        print("例: python -m src.loader.perplexity_ranking_loader --runs 3 --verbose")

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

            result = {
                "subcategory": args.subcategory,
                "services": services,
                "ranking": ranking,
                "missing_services": list(missing) if missing else []
            }

    # 結果をJSONファイルに保存
    if result and args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n結果を {args.output} に保存しました")
        except Exception as e:
            print(f"ファイル保存エラー: {e}")

if __name__ == "__main__":
    main()