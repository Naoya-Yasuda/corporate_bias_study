#!/usr/bin/env python
# coding: utf-8

"""
GitHub Actions用SNS投稿スクリプト

GitHub Actions環境でS3DataLoader統合版のSimplePostingSystemを使用して
SNS投稿機能を実行します。
"""

import os
import sys
import logging
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sns import SimplePostingSystem

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """メイン関数"""
    try:
        logger.info("GitHub Actions SNS投稿機能開始")

        # 環境変数の確認
        twitter_enabled = os.getenv('TWITTER_POSTING_ENABLED', 'false').lower() == 'true'
        sns_monitoring_enabled = os.getenv('SNS_MONITORING_ENABLED', 'false').lower() == 'true'
        today_date = os.getenv('TODAY_DATE', '')

        logger.info(f"TWITTER_POSTING_ENABLED: {twitter_enabled}")
        logger.info(f"SNS_MONITORING_ENABLED: {sns_monitoring_enabled}")
        logger.info(f"TODAY_DATE: {today_date}")

        # SNS投稿機能が無効の場合はスキップ
        if not twitter_enabled and not sns_monitoring_enabled:
            logger.info("SNS投稿機能が無効のためスキップします")
            return 0

        # SimplePostingSystemを初期化（S3DataLoader統合版）
        logger.info("SimplePostingSystemを初期化中...")
        posting_system = SimplePostingSystem(storage_mode='auto')

        # システム状態を確認
        status = posting_system.get_system_status()
        logger.info(f"システム状態: {status}")

        # 利用可能な分析日付を確認
        available_dates = posting_system.get_available_dates()
        logger.info(f"利用可能な分析日付数: {len(available_dates)}")

        if available_dates:
            latest_date = posting_system.get_latest_analysis_date()
            logger.info(f"最新分析日付: {latest_date}")

            # 最新の分析結果の変化を検知して投稿
            logger.info("最新分析結果の変化検知・投稿処理を開始")
            result = posting_system.post_latest_changes(force_post=False)

            logger.info(f"投稿結果: {result}")

            if result.get('success'):
                if result.get('posted'):
                    logger.info(f"投稿成功: {result.get('tweet_id')}")
                    logger.info(f"変化数: {result.get('changes_count')}件")
                    logger.info(f"投稿タイプ: {result.get('post_type')}")

                    # シミュレーションモードかどうかを確認
                    if result.get('simulation'):
                        logger.info("シミュレーションモードで投稿されました")
                    else:
                        logger.info("実際のX APIで投稿されました")
                else:
                    logger.info(f"投稿スキップ: {result.get('reason')}")
                    logger.info(f"変化数: {result.get('changes_count')}件")
            else:
                logger.error(f"投稿失敗: {result.get('error')}")
                return 1
        else:
            logger.warning("利用可能な分析日付が見つかりません")
            return 1

        logger.info("GitHub Actions SNS投稿機能完了")
        return 0

    except Exception as e:
        logger.error(f"GitHub Actions SNS投稿機能エラー: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)