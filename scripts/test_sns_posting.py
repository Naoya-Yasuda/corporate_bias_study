#!/usr/bin/env python
# coding: utf-8

"""
SNS投稿機能テストスクリプト

バイアス変化監視とSNS投稿機能のテストを実行します。
"""

import os
import sys
import logging
import yaml
from datetime import datetime, timedelta
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sns import BiasMonitor, S3DataLoader, ContentGenerator, PostingManager
from src.analysis.hybrid_data_loader import HybridDataLoader

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/test_sns_posting.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def load_config():
    """設定ファイルを読み込み"""
    config_path = project_root / "config" / "sns_monitoring_config.yml"

    if not config_path.exists():
        logger.error(f"設定ファイルが見つかりません: {config_path}")
        return None

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config.get("sns_monitoring", {})


def create_test_data():
    """テスト用の分析データを作成"""
    # 現在の日付
    current_date = datetime.now().strftime("%Y%m%d")

    # 先週の日付
    last_week = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

    # テスト用の分析データ
    current_data = {
        "metadata": {
            "analysis_date": current_date,
            "execution_count": 5,
            "reliability_level": "実用分析"
        },
        "categories": {
            "クラウドサービス": {
                "service_level_fairness_score": 0.85,
                "enterprise_level_fairness_score": 0.78,
                "subcategories": {
                    "クラウドコンピューティング": {
                        "entities": [
                            {
                                "name": "AWS",
                                "category": "クラウドサービス",
                                "normalized_bias_index": 1.8,  # 大幅に上昇
                                "sign_test_p_value": 0.02,
                                "cliffs_delta": 0.45,
                                "google_rank": 1,
                                "perplexity_rank": 2
                            },
                            {
                                "name": "Azure",
                                "category": "クラウドサービス",
                                "normalized_bias_index": 0.5,
                                "sign_test_p_value": 0.15,
                                "cliffs_delta": 0.25,
                                "google_rank": 3,
                                "perplexity_rank": 1
                            }
                        ]
                    }
                }
            }
        }
    }

    # 先週のデータ（変化を検知するための比較データ）
    previous_data = {
        "metadata": {
            "analysis_date": last_week,
            "execution_count": 5,
            "reliability_level": "実用分析"
        },
        "categories": {
            "クラウドサービス": {
                "service_level_fairness_score": 0.95,  # 大幅に低下
                "enterprise_level_fairness_score": 0.88,
                "subcategories": {
                    "クラウドコンピューティング": {
                        "entities": [
                            {
                                "name": "AWS",
                                "category": "クラウドサービス",
                                "normalized_bias_index": 1.2,  # 変化あり
                                "sign_test_p_value": 0.03,
                                "cliffs_delta": 0.38,
                                "google_rank": 2,  # 順位変化あり
                                "perplexity_rank": 3
                            },
                            {
                                "name": "Azure",
                                "category": "クラウドサービス",
                                "normalized_bias_index": 0.5,
                                "sign_test_p_value": 0.15,
                                "cliffs_delta": 0.25,
                                "google_rank": 3,
                                "perplexity_rank": 1
                            }
                        ]
                    }
                }
            }
        }
    }

    return current_data, previous_data


def test_s3_data_loader():
    """S3DataLoaderのテスト"""
    logger.info("=== S3DataLoaderテスト開始 ===")

    try:
        loader = S3DataLoader()

        # 利用可能日付の取得テスト
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        available_dates = loader.get_available_dates(start_date, end_date)

        logger.info(f"利用可能日付数: {len(available_dates)}")

        # データ構造検証テスト
        test_data, _ = create_test_data()
        is_valid = loader.validate_data_structure(test_data)
        logger.info(f"データ構造検証結果: {is_valid}")

        logger.info("S3DataLoaderテスト完了")
        return True

    except Exception as e:
        logger.error(f"S3DataLoaderテストエラー: {e}")
        return False


def test_content_generator():
    """ContentGeneratorのテスト"""
    logger.info("=== ContentGeneratorテスト開始 ===")

    try:
        generator = ContentGenerator()

        # テスト用の変化データ
        test_change = {
            "type": "nbi_change",
            "entity": "AWS",
            "category": "クラウドサービス",
            "change_rate": 25.5,
            "current_value": 1.8,
            "previous_value": 1.2,
            "direction": "up",
            "p_value": 0.02,
            "cliffs_delta": 0.45
        }

        current_date = datetime.now().strftime("%Y%m%d")

        # コンテンツ生成テスト
        content = generator.generate_content(test_change, current_date)
        logger.info(f"生成されたコンテンツ:\n{content}")

        # サマリーコンテンツ生成テスト
        changes = [test_change]
        summary_content = generator.generate_summary_content(changes, current_date)
        logger.info(f"生成されたサマリーコンテンツ:\n{summary_content}")

        logger.info("ContentGeneratorテスト完了")
        return True

    except Exception as e:
        logger.error(f"ContentGeneratorテストエラー: {e}")
        return False


def test_posting_manager():
    """PostingManagerのテスト"""
    logger.info("=== PostingManagerテスト開始 ===")

    try:
        manager = PostingManager()

        # 日次制限チェックテスト
        can_post = manager.check_daily_limit()
        logger.info(f"日次制限チェック結果: {can_post}")

        # 重複チェックテスト
        is_duplicate = manager.check_duplicate("AWS", "nbi_change")
        logger.info(f"重複チェック結果: {is_duplicate}")

        # 投稿履歴取得テスト
        history = manager.get_post_history(days=7)
        logger.info(f"投稿履歴件数: {len(history)}")

        # 日次統計取得テスト
        stats = manager.get_daily_stats()
        logger.info(f"日次統計: {stats}")

        logger.info("PostingManagerテスト完了")
        return True

    except Exception as e:
        logger.error(f"PostingManagerテストエラー: {e}")
        return False


def test_bias_monitor():
    """BiasMonitorのテスト"""
    logger.info("=== BiasMonitorテスト開始 ===")

    try:
        # 設定を読み込み
        config = load_config()
        if not config:
            logger.error("設定ファイルの読み込みに失敗しました")
            return False

        # テストデータを作成
        current_data, previous_data = create_test_data()

        # BiasMonitorを初期化
        monitor = BiasMonitor(config)

        # 直前データをS3DataLoaderに設定（テスト用）
        monitor.s3_loader._test_previous_data = previous_data

        # 変化監視テスト
        current_date = datetime.now().strftime("%Y%m%d")
        changes = monitor.monitor_changes(current_date, current_data)

        logger.info(f"検知された変化数: {len(changes)}")
        for i, change in enumerate(changes):
            logger.info(f"変化 {i+1}: {change}")

        logger.info("BiasMonitorテスト完了")
        return True

    except Exception as e:
        logger.error(f"BiasMonitorテストエラー: {e}")
        return False


def test_integration():
    """統合テスト"""
    logger.info("=== 統合テスト開始 ===")

    try:
        # 設定を読み込み
        config = load_config()
        if not config:
            logger.error("設定ファイルの読み込みに失敗しました")
            return False

        # テストデータを作成
        current_data, previous_data = create_test_data()

        # BiasMonitorを初期化
        monitor = BiasMonitor(config)

        # 直前データをS3DataLoaderに設定（テスト用）
        monitor.s3_loader._test_previous_data = previous_data

        # 統合テスト実行
        current_date = datetime.now().strftime("%Y%m%d")
        changes = monitor.monitor_changes(current_date, current_data)

        logger.info(f"統合テスト結果: {len(changes)}件の変化を検知")

        # 投稿履歴を確認
        history = monitor.posting_manager.get_post_history(days=1)
        logger.info(f"今日の投稿数: {len(history)}")

        logger.info("統合テスト完了")
        return True

    except Exception as e:
        logger.error(f"統合テストエラー: {e}")
        return False


def main():
    """メイン関数"""
    logger.info("SNS投稿機能テスト開始")

    # ログディレクトリを作成
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # 各テストを実行
    tests = [
        ("S3DataLoader", test_s3_data_loader),
        ("ContentGenerator", test_content_generator),
        ("PostingManager", test_posting_manager),
        ("BiasMonitor", test_bias_monitor),
        ("統合テスト", test_integration)
    ]

    results = {}

    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"{test_name}テスト開始")
        logger.info(f"{'='*50}")

        try:
            result = test_func()
            results[test_name] = result
            status = "成功" if result else "失敗"
            logger.info(f"{test_name}テスト: {status}")
        except Exception as e:
            logger.error(f"{test_name}テストで例外が発生: {e}")
            results[test_name] = False

    # 結果サマリー
    logger.info(f"\n{'='*50}")
    logger.info("テスト結果サマリー")
    logger.info(f"{'='*50}")

    for test_name, result in results.items():
        status = "成功" if result else "失敗"
        logger.info(f"{test_name}: {status}")

    success_count = sum(results.values())
    total_count = len(results)

    logger.info(f"\n総合結果: {success_count}/{total_count} テスト成功")

    if success_count == total_count:
        logger.info("🎉 全てのテストが成功しました！")
    else:
        logger.warning("⚠️ 一部のテストが失敗しました")

    logger.info("SNS投稿機能テスト終了")


if __name__ == "__main__":
    main()