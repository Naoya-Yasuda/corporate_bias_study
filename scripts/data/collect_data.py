#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
データ収集スクリプト

Perplexity APIとGoogle検索を使用してデータを収集します。
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 相対インポートのため、sys.pathに追加
sys.path.insert(0, str(project_root / "scripts" / "utils"))
from config_manager import setup_logging, get_config_manager
# ローダーモジュールをインポート（関数ベースの実装）
import src.loader.perplexity_sentiment_loader as sentiment_loader
import src.loader.perplexity_ranking_loader as ranking_loader
import src.loader.perplexity_citations_loader as citations_loader
import src.loader.google_search_loader as google_loader

logger = logging.getLogger(__name__)


def collect_sentiment_data(runs: int = 3, verbose: bool = False) -> bool:
    """感情分析データを収集"""
    try:
        logger.info(f"感情分析データ収集開始 (実行回数: {runs})")

        # 関数ベースの実装を使用
        sentiment_loader.process_categories_with_multiple_runs(
            api_key=os.environ.get("PERPLEXITY_API_KEY"),
            categories=sentiment_loader.categories,
            num_runs=runs
        )

        logger.info("感情分析データ収集完了")
        return True

    except Exception as e:
        logger.error(f"感情分析データ収集エラー: {e}")
        return False


def collect_ranking_data(runs: int = 3, verbose: bool = False) -> bool:
    """ランキングデータを収集"""
    try:
        logger.info(f"ランキングデータ収集開始 (実行回数: {runs})")

        # 関数ベースの実装を使用
        ranking_loader.process_categories_with_multiple_runs(
            api_key=os.environ.get("PERPLEXITY_API_KEY"),
            categories=ranking_loader.categories,
            num_runs=runs
        )

        logger.info("ランキングデータ収集完了")
        return True

    except Exception as e:
        logger.error(f"ランキングデータ収集エラー: {e}")
        return False


def collect_citations_data(runs: int = 3, verbose: bool = False) -> bool:
    """引用データを収集"""
    try:
        logger.info(f"引用データ収集開始 (実行回数: {runs})")

        # 関数ベースの実装を使用
        citations_loader.process_categories_with_multiple_runs(
            api_key=os.environ.get("PERPLEXITY_API_KEY"),
            categories=citations_loader.categories,
            num_runs=runs
        )

        logger.info("引用データ収集完了")
        return True

    except Exception as e:
        logger.error(f"引用データ収集エラー: {e}")
        return False


def collect_google_data(verbose: bool = False) -> bool:
    """Google検索データを収集"""
    try:
        logger.info("Google検索データ収集開始")

        # 関数ベースの実装を使用
        google_loader.process_categories()

        logger.info("Google検索データ収集完了")
        return True

    except Exception as e:
        logger.error(f"Google検索データ収集エラー: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="データ収集スクリプト")
    parser.add_argument("--type", choices=["sentiment", "ranking", "citations", "google", "all"],
                       default="all", help="収集するデータタイプ")
    parser.add_argument("--runs", type=int, default=3, help="Perplexity API実行回数")
    parser.add_argument("--verbose", action="store_true", help="詳細ログ出力")

    args = parser.parse_args()

    # ログ設定
    setup_logging(args.verbose)

    logger.info("データ収集スクリプト開始")

    success_count = 0
    total_count = 0

    # 設定確認
    config_manager = get_config_manager()
    env_config = config_manager.get_env_config()
    logger.info(f"環境設定: {env_config}")

    # データタイプに応じて収集
    if args.type in ["sentiment", "all"]:
        total_count += 1
        if collect_sentiment_data(args.runs, args.verbose):
            success_count += 1

    if args.type in ["ranking", "all"]:
        total_count += 1
        if collect_ranking_data(args.runs, args.verbose):
            success_count += 1

    if args.type in ["citations", "all"]:
        total_count += 1
        if collect_citations_data(args.runs, args.verbose):
            success_count += 1

    if args.type in ["google", "all"]:
        total_count += 1
        if collect_google_data(args.verbose):
            success_count += 1

    # 結果報告
    logger.info(f"データ収集完了: {success_count}/{total_count} 成功")

    if success_count == total_count:
        logger.info("すべてのデータ収集が成功しました")
        return 0
    else:
        logger.error(f"{total_count - success_count}件のデータ収集が失敗しました")
        return 1


if __name__ == "__main__":
    exit(main())
