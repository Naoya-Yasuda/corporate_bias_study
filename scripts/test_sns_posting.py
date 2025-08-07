#!/usr/bin/env python
# coding: utf-8

"""
SNS投稿機能テストスクリプト

バイアス変化監視とSNS投稿機能のテストを実行します。
S3DataLoader統合版のSimplePostingSystemをテストします。
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

from src.sns import SimplePostingSystem, IntegratedPostingSystem, S3DataLoader
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
        "entity_analysis": {
            "AWS": {
                "bias_score": 1.8,
                "sentiment_score": 0.65,
                "ranking": 1,
                "fairness_score": 0.75,
                "neutrality_score": 0.82
            },
            "Azure": {
                "bias_score": 0.5,
                "sentiment_score": 0.78,
                "ranking": 2,
                "fairness_score": 0.88,
                "neutrality_score": 0.91
            },
            "Google Cloud": {
                "bias_score": 0.8,
                "sentiment_score": 0.72,
                "ranking": 3,
                "fairness_score": 0.85,
                "neutrality_score": 0.87
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
        "entity_analysis": {
            "AWS": {
                "bias_score": 1.2,  # 変化あり
                "sentiment_score": 0.65,
                "ranking": 2,  # 順位変化あり
                "fairness_score": 0.85,
                "neutrality_score": 0.82
            },
            "Azure": {
                "bias_score": 0.5,
                "sentiment_score": 0.78,
                "ranking": 1,
                "fairness_score": 0.88,
                "neutrality_score": 0.91
            },
            "Google Cloud": {
                "bias_score": 0.8,
                "sentiment_score": 0.72,
                "ranking": 3,
                "fairness_score": 0.85,
                "neutrality_score": 0.87
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
        available_dates = loader.list_available_dates()
        logger.info(f"利用可能日付数: {len(available_dates)}")

        if available_dates:
            # 最新日付の取得テスト
            latest_date = loader.get_latest_analysis_date()
            logger.info(f"最新分析日付: {latest_date}")

            # 前回日付の取得テスト
            previous_date = loader.get_previous_analysis_date(latest_date)
            logger.info(f"前回分析日付: {previous_date}")

            # 分析結果読み込みテスト
            if latest_date:
                results = loader.load_analysis_results(latest_date)
                if results:
                    logger.info(f"分析結果読み込み成功: {len(results)}件のデータ")
                else:
                    logger.warning("分析結果の読み込みに失敗しました")

        # データ構造検証テスト
        test_data, _ = create_test_data()
        entity_metrics = loader.extract_entity_metrics(test_data)
        logger.info(f"エンティティ指標抽出: {len(entity_metrics)}件")

        logger.info("S3DataLoaderテスト完了")
        return True

    except Exception as e:
        logger.error(f"S3DataLoaderテストエラー: {e}")
        return False


def test_simple_posting_system():
    """SimplePostingSystem（S3DataLoader統合版）のテスト"""
    logger.info("=== SimplePostingSystemテスト開始 ===")

    try:
        # SimplePostingSystemを初期化
        posting_system = SimplePostingSystem(storage_mode="auto")

        # システム状態の確認
        status = posting_system.get_system_status()
        logger.info(f"システム状態: {status}")

        # 利用可能日付の取得
        available_dates = posting_system.get_available_dates()
        logger.info(f"利用可能日付数: {len(available_dates)}")

        if available_dates:
            # 最新の分析結果の変化を検知して投稿（シミュレーション）
            logger.info("最新分析結果の変化検知・投稿テスト開始")
            result = posting_system.post_latest_changes(force_post=False)

            logger.info(f"投稿結果: {result}")

            if result.get("success"):
                if result.get("posted"):
                    logger.info("投稿が実行されました")
                else:
                    logger.info("変化が検知されなかったため投稿はスキップされました")
            else:
                logger.warning(f"投稿処理でエラーが発生: {result.get('error')}")

        # 指定日付での投稿テスト（テストデータを使用）
        logger.info("指定日付での投稿テスト開始")
        test_data, previous_data = create_test_data()

        # テストデータを直接使用して投稿テスト
        result = posting_system.post_changes(
            previous_data=previous_data,
            current_data=test_data,
            analysis_date=datetime.now().strftime("%Y%m%d"),
            force_post=True
        )

        logger.info(f"テスト投稿結果: {result}")

        logger.info("SimplePostingSystemテスト完了")
        return True

    except Exception as e:
        logger.error(f"SimplePostingSystemテストエラー: {e}")
        return False


def test_integrated_posting_system():
    """IntegratedPostingSystemのテスト"""
    logger.info("=== IntegratedPostingSystemテスト開始 ===")

    try:
        # IntegratedPostingSystemを初期化
        posting_system = IntegratedPostingSystem(storage_mode="auto")

        # 最新の分析結果の変化を検知して投稿（シミュレーション）
        logger.info("最新分析結果の変化検知・投稿テスト開始")
        result = posting_system.post_latest_changes(force_post=False)

        logger.info(f"投稿結果: {result}")

        if result.get("success"):
            if result.get("posted"):
                logger.info("投稿が実行されました")
            else:
                logger.info("変化が検知されなかったため投稿はスキップされました")
        else:
            logger.warning(f"投稿処理でエラーが発生: {result.get('error')}")

        logger.info("IntegratedPostingSystemテスト完了")
        return True

    except Exception as e:
        logger.error(f"IntegratedPostingSystemテストエラー: {e}")
        return False


def test_x_api_connection():
    """X API接続テスト"""
    logger.info("=== X API接続テスト開始 ===")

    try:
        # SimplePostingSystemを初期化
        posting_system = SimplePostingSystem()

        # X API接続テスト
        result = posting_system.test_connection()

        if result.get("success"):
            logger.info("X API接続テスト成功")
            user_info = result.get("user_info")
            if user_info:
                logger.info(f"ユーザー情報: {user_info}")
        else:
            logger.warning(f"X API接続テスト失敗: {result.get('error')}")

        logger.info("X API接続テスト完了")
        return True

    except Exception as e:
        logger.error(f"X API接続テストエラー: {e}")
        return False


def test_data_comparison():
    """データ比較機能のテスト"""
    logger.info("=== データ比較機能テスト開始 ===")

    try:
        loader = S3DataLoader()

        # 利用可能日付を取得
        available_dates = loader.list_available_dates()

        if len(available_dates) >= 2:
            # 最新の2つの日付で比較テスト
            latest_date = max(available_dates)
            previous_date = sorted(available_dates)[-2]

            logger.info(f"比較テスト: {previous_date} → {latest_date}")

            # 比較データを取得
            comparison_data = loader.load_comparison_data(latest_date)

            if comparison_data:
                logger.info("比較データの取得に成功")

                # エンティティ指標を抽出
                if comparison_data.get("previous"):
                    previous_metrics = loader.extract_entity_metrics(comparison_data["previous"])
                    logger.info(f"前回指標数: {len(previous_metrics)}")

                if comparison_data.get("current"):
                    current_metrics = loader.extract_entity_metrics(comparison_data["current"])
                    logger.info(f"今回指標数: {len(current_metrics)}")
            else:
                logger.warning("比較データの取得に失敗")
        else:
            logger.info("比較テスト用のデータが不足しています")

        logger.info("データ比較機能テスト完了")
        return True

    except Exception as e:
        logger.error(f"データ比較機能テストエラー: {e}")
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
        ("SimplePostingSystem", test_simple_posting_system),
        ("IntegratedPostingSystem", test_integrated_posting_system),
        ("X API接続", test_x_api_connection),
        ("データ比較機能", test_data_comparison)
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