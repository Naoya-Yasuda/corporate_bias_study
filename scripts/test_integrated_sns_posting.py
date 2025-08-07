#!/usr/bin/env python
# coding: utf-8

"""
統合SNS投稿システムのテストスクリプト

S3DataLoaderを統合した投稿システムのテストを実行します。
実際のS3データを使用して変化検知→投稿の統合テストを行います。
"""

import sys
import os
import logging
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sns import IntegratedPostingSystem

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_system_initialization():
    """システム初期化テスト"""
    logger.info("=== システム初期化テスト ===")

    try:
        # 統合投稿システムを初期化
        posting_system = IntegratedPostingSystem(storage_mode="auto")

        # システム状態を取得
        status = posting_system.get_system_status()

        logger.info("システム状態:")
        logger.info(f"投稿有効: {status.get('posting_enabled')}")
        logger.info(f"X API認証: {status.get('twitter_authenticated')}")
        logger.info(f"ストレージモード: {status.get('storage_mode')}")
        logger.info(f"閾値設定: {status.get('thresholds')}")
        logger.info(f"最大変化数: {status.get('max_changes_per_post')}")

        return True

    except Exception as e:
        logger.error(f"システム初期化エラー: {e}")
        return False


def test_data_loading():
    """データ読み込みテスト"""
    logger.info("=== データ読み込みテスト ===")

    try:
        posting_system = IntegratedPostingSystem(storage_mode="auto")

        # 利用可能な日付を取得
        available_dates = posting_system.list_available_dates()
        logger.info(f"利用可能な分析日付: {len(available_dates)}件")

        if available_dates:
            logger.info(f"最新5件: {available_dates[:5]}")

            # 最新の分析日付を取得
            latest_date = posting_system.get_latest_analysis_date()
            logger.info(f"最新分析日付: {latest_date}")

            return True
        else:
            logger.warning("利用可能な分析日付が見つかりません")
            return False

    except Exception as e:
        logger.error(f"データ読み込みエラー: {e}")
        return False


def test_latest_changes_posting():
    """最新変化投稿テスト"""
    logger.info("=== 最新変化投稿テスト ===")

    try:
        posting_system = IntegratedPostingSystem(storage_mode="auto")

        # 最新の変化を検知して投稿
        result = posting_system.post_latest_changes(force_post=False)

        logger.info("投稿結果:")
        logger.info(f"成功: {result.get('success')}")
        logger.info(f"投稿済み: {result.get('posted')}")
        logger.info(f"ツイートID: {result.get('tweet_id')}")
        logger.info(f"変化数: {result.get('changes_count')}")
        logger.info(f"投稿タイプ: {result.get('post_type')}")
        logger.info(f"分析日付: {result.get('analysis_date')}")

        if result.get('simulation'):
            logger.info("シミュレーションモードで実行されました")

        return result.get('success', False)

    except Exception as e:
        logger.error(f"最新変化投稿エラー: {e}")
        return False


def test_specific_date_posting():
    """指定日付投稿テスト"""
    logger.info("=== 指定日付投稿テスト ===")

    try:
        posting_system = IntegratedPostingSystem(storage_mode="auto")

        # 利用可能な日付を取得
        available_dates = posting_system.list_available_dates()
        if not available_dates:
            logger.warning("利用可能な分析日付がないため、テストをスキップ")
            return True

        # 最新の日付を指定して投稿
        target_date = available_dates[0]  # 最新の日付
        logger.info(f"対象日付: {target_date}")

        result = posting_system.post_specific_date_changes(target_date, force_post=False)

        logger.info("指定日付投稿結果:")
        logger.info(f"成功: {result.get('success')}")
        logger.info(f"投稿済み: {result.get('posted')}")
        logger.info(f"ツイートID: {result.get('tweet_id')}")
        logger.info(f"変化数: {result.get('changes_count')}")
        logger.info(f"投稿タイプ: {result.get('post_type')}")
        logger.info(f"分析日付: {result.get('analysis_date')}")

        if result.get('simulation'):
            logger.info("シミュレーションモードで実行されました")

        return result.get('success', False)

    except Exception as e:
        logger.error(f"指定日付投稿エラー: {e}")
        return False


def test_force_posting():
    """強制投稿テスト"""
    logger.info("=== 強制投稿テスト ===")

    try:
        posting_system = IntegratedPostingSystem(storage_mode="auto")

        # 強制投稿フラグをTrueにして投稿
        result = posting_system.post_latest_changes(force_post=True)

        logger.info("強制投稿結果:")
        logger.info(f"成功: {result.get('success')}")
        logger.info(f"投稿済み: {result.get('posted')}")
        logger.info(f"投稿タイプ: {result.get('post_type')}")
        logger.info(f"分析日付: {result.get('analysis_date')}")

        if result.get('simulation'):
            logger.info("シミュレーションモードで実行されました")

        return result.get('success', False)

    except Exception as e:
        logger.error(f"強制投稿エラー: {e}")
        return False


def test_connection():
    """X API接続テスト"""
    logger.info("=== X API接続テスト ===")

    try:
        posting_system = IntegratedPostingSystem(storage_mode="auto")
        result = posting_system.test_connection()

        logger.info("接続テスト結果:")
        logger.info(f"成功: {result.get('success')}")

        if result.get('success'):
            user_info = result.get('user_info', {})
            logger.info(f"ユーザー名: {user_info.get('username')}")
            logger.info(f"表示名: {user_info.get('name')}")
        else:
            logger.info(f"エラー: {result.get('error')}")

        return result.get('success', False)

    except Exception as e:
        logger.error(f"接続テストエラー: {e}")
        return False


def main():
    """メイン実行関数"""
    logger.info("統合SNS投稿システムテストを開始")

    test_results = []

    try:
        # 1. システム初期化テスト
        test_results.append(("システム初期化", test_system_initialization()))

        # 2. データ読み込みテスト
        test_results.append(("データ読み込み", test_data_loading()))

        # 3. 最新変化投稿テスト
        test_results.append(("最新変化投稿", test_latest_changes_posting()))

        # 4. 指定日付投稿テスト
        test_results.append(("指定日付投稿", test_specific_date_posting()))

        # 5. 強制投稿テスト
        test_results.append(("強制投稿", test_force_posting()))

        # 6. X API接続テスト
        test_results.append(("X API接続", test_connection()))

        # 結果サマリー
        logger.info("=== テスト結果サマリー ===")
        success_count = 0
        for test_name, result in test_results:
            status = "✅ 成功" if result else "❌ 失敗"
            logger.info(f"{test_name}: {status}")
            if result:
                success_count += 1

        logger.info(f"成功率: {success_count}/{len(test_results)} ({success_count/len(test_results)*100:.1f}%)")

        if success_count == len(test_results):
            logger.info("🎉 全てのテストが成功しました！")
        else:
            logger.warning("⚠️ 一部のテストが失敗しました")

        return success_count == len(test_results)

    except Exception as e:
        logger.error(f"テスト実行中にエラーが発生しました: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)