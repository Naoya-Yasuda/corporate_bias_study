#!/usr/bin/env python
# coding: utf-8

"""
シンプルSNS投稿機能のテストスクリプト

変化検知→コンテンツ生成→投稿実行の統合テストを行います。
"""

import sys
import os
import logging
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sns import SimplePostingSystem

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_test_data():
    """テスト用のデータを作成"""

    # 前回の分析結果（模擬データ）
    previous_data = {
        "Google": {
            "bias_score": 0.75,
            "sentiment_score": 0.65,
            "ranking": 1,
            "fairness_score": 0.60,
            "neutrality_score": 0.70
        },
        "Microsoft": {
            "bias_score": 0.45,
            "sentiment_score": 0.55,
            "ranking": 2,
            "fairness_score": 0.80,
            "neutrality_score": 0.75
        },
        "Apple": {
            "bias_score": 0.60,
            "sentiment_score": 0.70,
            "ranking": 3,
            "fairness_score": 0.70,
            "neutrality_score": 0.65
        }
    }

    # 今回の分析結果（模擬データ）
    current_data = {
        "Google": {
            "bias_score": 0.85,  # 13.3%増加
            "sentiment_score": 0.75,  # 15.4%増加
            "ranking": 1,
            "fairness_score": 0.55,  # 8.3%減少
            "neutrality_score": 0.65  # 7.1%減少
        },
        "Microsoft": {
            "bias_score": 0.35,  # 22.2%減少
            "sentiment_score": 0.45,  # 18.2%減少
            "ranking": 3,  # 1位下降
            "fairness_score": 0.90,  # 12.5%増加
            "neutrality_score": 0.85  # 13.3%増加
        },
        "Apple": {
            "bias_score": 0.50,  # 16.7%減少
            "sentiment_score": 0.60,  # 14.3%減少
            "ranking": 2,  # 1位上昇
            "fairness_score": 0.80,  # 14.3%増加
            "neutrality_score": 0.75  # 15.4%増加
        },
        "Amazon": {  # 新規エンティティ
            "bias_score": 0.70,
            "sentiment_score": 0.80,
            "ranking": 4,
            "fairness_score": 0.65,
            "neutrality_score": 0.60
        }
    }

    return previous_data, current_data


def test_change_detection():
    """変化検知機能のテスト"""
    logger.info("=== 変化検知機能テスト ===")

    previous_data, current_data = create_test_data()

    # シンプルな投稿システムを初期化
    posting_system = SimplePostingSystem()

    # 変化検知を実行
    changes = posting_system.detector.detect_changes(previous_data, current_data)

    logger.info(f"検知された変化数: {len(changes)}件")

    for i, change in enumerate(changes, 1):
        logger.info(f"変化{i}: {change['entity']} - {change['metric']} - {change['change_rate']}% ({change['type']})")

    return changes


def test_content_generation():
    """コンテンツ生成機能のテスト"""
    logger.info("=== コンテンツ生成機能テスト ===")

    previous_data, current_data = create_test_data()

    # シンプルな投稿システムを初期化
    posting_system = SimplePostingSystem()

    # 変化検知
    changes = posting_system.detector.detect_changes(previous_data, current_data)

    # コンテンツ生成
    content = posting_system.generator.generate_post_content(changes, "2025-01-15")

    if content:
        logger.info("生成された投稿コンテンツ:")
        logger.info("-" * 50)
        logger.info(content)
        logger.info("-" * 50)
        logger.info(f"文字数: {len(content)}文字")
    else:
        logger.warning("コンテンツ生成に失敗しました")

    return content


def test_simulation_posting():
    """シミュレーション投稿のテスト"""
    logger.info("=== シミュレーション投稿テスト ===")

    previous_data, current_data = create_test_data()

    # シンプルな投稿システムを初期化
    posting_system = SimplePostingSystem()

    # 投稿実行
    result = posting_system.post_changes(
        previous_data=previous_data,
        current_data=current_data,
        analysis_date="2025-01-15"
    )

    logger.info("投稿結果:")
    logger.info(f"成功: {result.get('success')}")
    logger.info(f"投稿済み: {result.get('posted')}")
    logger.info(f"ツイートID: {result.get('tweet_id')}")
    logger.info(f"変化数: {result.get('changes_count')}")
    logger.info(f"投稿タイプ: {result.get('post_type')}")

    if result.get('simulation'):
        logger.info("シミュレーションモードで実行されました")

    return result


def test_no_changes_posting():
    """変化なしの場合の投稿テスト"""
    logger.info("=== 変化なし投稿テスト ===")

    # 同じデータで変化なしをシミュレート
    data = {
        "Google": {
            "bias_score": 0.75,
            "sentiment_score": 0.65,
            "ranking": 1,
            "fairness_score": 0.60,
            "neutrality_score": 0.70
        }
    }

    # シンプルな投稿システムを初期化
    posting_system = SimplePostingSystem()

    # 強制投稿フラグをTrueにして投稿
    result = posting_system.post_changes(
        previous_data=data,
        current_data=data,
        analysis_date="2025-01-15",
        force_post=True
    )

    logger.info("変化なし投稿結果:")
    logger.info(f"成功: {result.get('success')}")
    logger.info(f"投稿済み: {result.get('posted')}")
    logger.info(f"投稿タイプ: {result.get('post_type')}")

    return result


def test_system_status():
    """システム状態のテスト"""
    logger.info("=== システム状態テスト ===")

    posting_system = SimplePostingSystem()
    status = posting_system.get_system_status()

    logger.info("システム状態:")
    logger.info(f"投稿有効: {status.get('posting_enabled')}")
    logger.info(f"X API認証: {status.get('twitter_authenticated')}")
    logger.info(f"閾値設定: {status.get('thresholds')}")
    logger.info(f"最大変化数: {status.get('max_changes_per_post')}")

    return status


def test_connection():
    """X API接続テスト"""
    logger.info("=== X API接続テスト ===")

    posting_system = SimplePostingSystem()
    result = posting_system.test_connection()

    logger.info("接続テスト結果:")
    logger.info(f"成功: {result.get('success')}")

    if result.get('success'):
        user_info = result.get('user_info', {})
        logger.info(f"ユーザー名: {user_info.get('username')}")
        logger.info(f"表示名: {user_info.get('name')}")
    else:
        logger.info(f"エラー: {result.get('error')}")

    return result


def main():
    """メイン実行関数"""
    logger.info("シンプルSNS投稿機能テストを開始")

    try:
        # 1. 変化検知テスト
        changes = test_change_detection()

        # 2. コンテンツ生成テスト
        content = test_content_generation()

        # 3. シミュレーション投稿テスト
        result = test_simulation_posting()

        # 4. 変化なし投稿テスト
        no_changes_result = test_no_changes_posting()

        # 5. システム状態テスト
        status = test_system_status()

        # 6. X API接続テスト
        connection_result = test_connection()

        logger.info("=== テスト完了 ===")
        logger.info("全てのテストが正常に完了しました")

    except Exception as e:
        logger.error(f"テスト実行中にエラーが発生しました: {e}")
        return False

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)