#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
環境セットアップスクリプト

プロジェクトの実行環境をセットアップします。
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

logger = logging.getLogger(__name__)


def check_required_directories() -> bool:
    """必要なディレクトリの存在確認"""
    try:
        required_dirs = [
            "corporate_bias_datasets",
            "corporate_bias_datasets/raw_data",
            "corporate_bias_datasets/integrated",
            "logs",
            "tmp"
        ]

        missing_dirs = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing_dirs.append(dir_path)

        if missing_dirs:
            logger.warning(f"不足しているディレクトリ: {missing_dirs}")
            return False
        else:
            logger.info("すべての必要なディレクトリが存在します")
            return True

    except Exception as e:
        logger.error(f"ディレクトリ確認エラー: {e}")
        return False


def create_missing_directories() -> bool:
    """不足しているディレクトリを作成"""
    try:
        required_dirs = [
            "corporate_bias_datasets",
            "corporate_bias_datasets/raw_data",
            "corporate_bias_datasets/integrated",
            "logs",
            "tmp"
        ]

        created_dirs = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                created_dirs.append(dir_path)
                logger.info(f"ディレクトリを作成しました: {dir_path}")

        if created_dirs:
            logger.info(f"作成したディレクトリ: {created_dirs}")
        else:
            logger.info("すべてのディレクトリが既に存在します")

        return True

    except Exception as e:
        logger.error(f"ディレクトリ作成エラー: {e}")
        return False


def check_config_files() -> bool:
    """設定ファイルの存在確認"""
    try:
        config_manager = get_config_manager()

        # 必須設定ファイルの確認
        required_configs = [
            ("analysis_config.yml", config_manager.get_analysis_config),
            ("analysis/categories.yml", config_manager.get_categories_config),
            ("data/market_shares.json", config_manager.get_market_shares),
            ("data/market_caps.json", config_manager.get_market_caps),
        ]

        missing_configs = []
        for config_name, config_func in required_configs:
            config = config_func()
            if not config:
                missing_configs.append(config_name)

        if missing_configs:
            logger.warning(f"不足している設定ファイル: {missing_configs}")
            return False
        else:
            logger.info("すべての必須設定ファイルが存在します")
            return True

    except Exception as e:
        logger.error(f"設定ファイル確認エラー: {e}")
        return False


def check_environment_variables() -> bool:
    """環境変数の確認"""
    try:
        config_manager = get_config_manager()
        env_config = config_manager.get_env_config()

        logger.info("環境変数設定:")
        for key, value in env_config.items():
            logger.info(f"  {key}: {value}")

        # 重要な環境変数の確認
        important_vars = [
            'STORAGE_MODE',
            'TWITTER_POSTING_ENABLED',
            'SNS_MONITORING_ENABLED'
        ]

        missing_vars = []
        for var in important_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.warning(f"設定されていない環境変数: {missing_vars}")
            logger.info("これらの変数はデフォルト値が使用されます")

        return True

    except Exception as e:
        logger.error(f"環境変数確認エラー: {e}")
        return False


def validate_python_modules() -> bool:
    """Pythonモジュールの検証"""
    try:
        required_modules = [
            'src.analysis.bias_analysis_engine',
            'src.loader.perplexity_sentiment_loader',
            'src.loader.perplexity_ranking_loader',
            'src.loader.perplexity_citations_loader',
            'src.loader.google_search_loader',
            'src.sns.integrated_posting_system',
        ]

        missing_modules = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)

        if missing_modules:
            logger.error(f"不足しているPythonモジュール: {missing_modules}")
            return False
        else:
            logger.info("すべての必要なPythonモジュールが利用可能です")
            return True

    except Exception as e:
        logger.error(f"モジュール検証エラー: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="環境セットアップスクリプト")
    parser.add_argument("--create-dirs", action="store_true",
                       help="不足しているディレクトリを作成")
    parser.add_argument("--verbose", action="store_true", help="詳細ログ出力")

    args = parser.parse_args()

    # ログ設定
    setup_logging(args.verbose)

    logger.info("環境セットアップスクリプト開始")

    # 各チェック項目の実行
    checks = [
        ("ディレクトリ確認", check_required_directories),
        ("設定ファイル確認", check_config_files),
        ("環境変数確認", check_environment_variables),
        ("Pythonモジュール確認", validate_python_modules),
    ]

    failed_checks = []

    for check_name, check_func in checks:
        logger.info(f"=== {check_name} ===")
        if not check_func():
            failed_checks.append(check_name)

    # ディレクトリ作成オプション
    if args.create_dirs:
        logger.info("=== ディレクトリ作成 ===")
        create_missing_directories()

    # 結果報告
    if failed_checks:
        logger.error(f"セットアップ失敗: {failed_checks}")
        return 1
    else:
        logger.info("環境セットアップが完了しました")
        return 0


if __name__ == "__main__":
    exit(main())
