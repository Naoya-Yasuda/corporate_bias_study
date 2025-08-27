#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
データ統合スクリプト

収集したデータを統合して分析用データセットを作成します。
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 相対インポートのため、sys.pathに追加
sys.path.insert(0, str(project_root / "scripts" / "utils"))
from config_manager import setup_logging, get_config_manager
from src.integrator.dataset_integrator import DatasetIntegrator

logger = logging.getLogger(__name__)


def integrate_data(date: str, verbose: bool = False) -> bool:
    """データ統合を実行"""
    try:
        logger.info(f"データ統合開始: {date}")

        # 統合データセット作成
        integrator = DatasetIntegrator()
        result = integrator.create_integrated_dataset(force_recreate=False, verbose=verbose)

        if result.get('success'):
            logger.info("データ統合完了")
            logger.info(f"統合データセット: {result.get('integrated_dataset_path', 'N/A')}")
            return True
        else:
            logger.error(f"データ統合失敗: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        logger.error(f"データ統合エラー: {e}")
        return False


def validate_integrated_data(date: str, verbose: bool = False) -> bool:
    """統合データの検証"""
    try:
        logger.info(f"統合データ検証開始: {date}")

        # データ検証ロジックを実装
        # ここでは簡易的な検証のみ
        integrated_path = f"corporate_bias_datasets/integrated/{date}/corporate_bias_dataset.json"

        if os.path.exists(integrated_path):
            logger.info(f"統合データセットが存在します: {integrated_path}")
            return True
        else:
            logger.error(f"統合データセットが見つかりません: {integrated_path}")
            return False

    except Exception as e:
        logger.error(f"データ検証エラー: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="データ統合スクリプト")
    parser.add_argument("--date", type=str,
                       default=datetime.now().strftime("%Y%m%d"),
                       help="統合対象日付 (YYYYMMDD形式)")
    parser.add_argument("--verbose", action="store_true", help="詳細ログ出力")
    parser.add_argument("--validate", action="store_true", help="統合後にデータ検証を実行")

    args = parser.parse_args()

    # ログ設定
    setup_logging(args.verbose)

    logger.info("データ統合スクリプト開始")

    # 設定確認
    config_manager = get_config_manager()
    env_config = config_manager.get_env_config()
    logger.info(f"環境設定: {env_config}")

    # データ統合実行
    if integrate_data(args.date, args.verbose):
        logger.info("データ統合が成功しました")

        # 検証オプションが指定されている場合
        if args.validate:
            if validate_integrated_data(args.date, args.verbose):
                logger.info("データ検証が成功しました")
                return 0
            else:
                logger.error("データ検証が失敗しました")
                return 1
        else:
            return 0
    else:
        logger.error("データ統合が失敗しました")
        return 1


if __name__ == "__main__":
    exit(main())
