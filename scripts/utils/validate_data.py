#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
データ検証スクリプト

収集・統合されたデータの品質を検証します。
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 相対インポートのため、sys.pathに追加
sys.path.insert(0, str(project_root / "scripts" / "utils"))
from config_manager import setup_logging, get_config_manager

logger = logging.getLogger(__name__)


def validate_raw_data(date: str, verbose: bool = False) -> bool:
    """生データの検証"""
    try:
        logger.info(f"生データ検証開始: {date}")

        raw_data_dir = f"corporate_bias_datasets/raw_data/{date}"
        if not os.path.exists(raw_data_dir):
            logger.error(f"生データディレクトリが見つかりません: {raw_data_dir}")
            return False

        # 生データファイルの確認
        required_files = [
            "perplexity_sentiment_data.json",
            "perplexity_ranking_data.json",
            "perplexity_citations_data.json",
            "google_search_data.json"
        ]

        missing_files = []
        for file_name in required_files:
            file_path = os.path.join(raw_data_dir, file_name)
            if not os.path.exists(file_path):
                missing_files.append(file_name)
            else:
                # ファイルサイズの確認
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    logger.warning(f"空のファイル: {file_name}")
                else:
                    logger.info(f"✓ {file_name} ({file_size} bytes)")

        if missing_files:
            logger.error(f"不足している生データファイル: {missing_files}")
            return False

        logger.info("生データ検証完了")
        return True

    except Exception as e:
        logger.error(f"生データ検証エラー: {e}")
        return False


def validate_integrated_data(date: str, verbose: bool = False) -> bool:
    """統合データの検証"""
    try:
        logger.info(f"統合データ検証開始: {date}")

        integrated_file = f"corporate_bias_datasets/integrated/{date}/corporate_bias_dataset.json"
        if not os.path.exists(integrated_file):
            logger.error(f"統合データファイルが見つかりません: {integrated_file}")
            return False

        # 統合データの構造確認
        with open(integrated_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 必須フィールドの確認
        required_fields = ['metadata', 'sentiment_data', 'ranking_data', 'citations_data']
        missing_fields = []

        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
            else:
                logger.info(f"✓ {field} フィールド存在")

        if missing_fields:
            logger.error(f"不足しているフィールド: {missing_fields}")
            return False

        # メタデータの確認
        metadata = data.get('metadata', {})
        logger.info(f"データ収集日: {metadata.get('collection_date', 'N/A')}")
        logger.info(f"データソース数: {len(metadata.get('data_sources', []))}")

        # データ量の確認
        sentiment_count = len(data.get('sentiment_data', {}))
        ranking_count = len(data.get('ranking_data', {}))
        citations_count = len(data.get('citations_data', {}))

        logger.info(f"感情分析データ: {sentiment_count} 件")
        logger.info(f"ランキングデータ: {ranking_count} 件")
        logger.info(f"引用データ: {citations_count} 件")

        if sentiment_count == 0 and ranking_count == 0 and citations_count == 0:
            logger.warning("すべてのデータが空です")
            return False

        logger.info("統合データ検証完了")
        return True

    except Exception as e:
        logger.error(f"統合データ検証エラー: {e}")
        return False


def validate_analysis_results(date: str, verbose: bool = False) -> bool:
    """分析結果の検証"""
    try:
        logger.info(f"分析結果検証開始: {date}")

        analysis_dir = f"corporate_bias_datasets/integrated/{date}"
        if not os.path.exists(analysis_dir):
            logger.warning(f"分析結果ディレクトリが見つかりません: {analysis_dir}")
            return True  # 分析結果は必須ではない

        # 分析結果ファイルの確認
        result_files = [
            "bias_analysis_results.json",
            "analysis_metadata.json"
        ]

        found_files = []
        for file_name in result_files:
            file_path = os.path.join(analysis_dir, file_name)
            if os.path.exists(file_path):
                found_files.append(file_name)
                logger.info(f"✓ {file_name}")

        if found_files:
            logger.info(f"分析結果ファイル: {len(found_files)} 件")
        else:
            logger.info("分析結果ファイルは見つかりませんでした")

        logger.info("分析結果検証完了")
        return True

    except Exception as e:
        logger.error(f"分析結果検証エラー: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="データ検証スクリプト")
    parser.add_argument("--date", type=str,
                       default=datetime.now().strftime("%Y%m%d"),
                       help="検証対象日付 (YYYYMMDD形式)")
    parser.add_argument("--type", choices=["raw", "integrated", "analysis", "all"],
                       default="all", help="検証するデータタイプ")
    parser.add_argument("--verbose", action="store_true", help="詳細ログ出力")

    args = parser.parse_args()

    # ログ設定
    setup_logging(args.verbose)

    logger.info("データ検証スクリプト開始")

    # 設定確認
    config_manager = get_config_manager()
    env_config = config_manager.get_env_config()
    logger.info(f"環境設定: {env_config}")

    # 検証実行
    validation_results = []

    if args.type in ["raw", "all"]:
        validation_results.append(("生データ", validate_raw_data(args.date, args.verbose)))

    if args.type in ["integrated", "all"]:
        validation_results.append(("統合データ", validate_integrated_data(args.date, args.verbose)))

    if args.type in ["analysis", "all"]:
        validation_results.append(("分析結果", validate_analysis_results(args.date, args.verbose)))

    # 結果報告
    success_count = sum(1 for _, result in validation_results if result)
    total_count = len(validation_results)

    logger.info(f"検証結果: {success_count}/{total_count} 成功")

    for name, result in validation_results:
        status = "✓" if result else "✗"
        logger.info(f"{status} {name}")

    if success_count == total_count:
        logger.info("すべてのデータ検証が成功しました")
        return 0
    else:
        logger.error(f"{total_count - success_count}件のデータ検証が失敗しました")
        return 1


if __name__ == "__main__":
    exit(main())
