#!/usr/bin/env python
# coding: utf-8

"""
シンプルな統合投稿システム

変化検知→コンテンツ生成→投稿実行を統合します。
"""

import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

from .simple_change_detector import SimpleChangeDetector
from .simple_content_generator import SimpleContentGenerator
from .twitter_client import TwitterClient

logger = logging.getLogger(__name__)


class SimplePostingSystem:
    """シンプルな統合投稿システム"""

    def __init__(self, thresholds: Optional[Dict] = None, max_changes_per_post: int = 5):
        """
        Parameters:
        -----------
        thresholds : Optional[Dict]
            変化検知の閾値設定
        max_changes_per_post : int
            1投稿あたりの最大変化数
        """
        # 各コンポーネントを初期化
        self.detector = SimpleChangeDetector(thresholds)
        self.generator = SimpleContentGenerator(max_changes_per_post)
        self.twitter_client = TwitterClient()

        # 投稿設定
        self.posting_enabled = os.getenv('TWITTER_POSTING_ENABLED', 'true').lower() == 'true'

        logger.info(f"統合投稿システムを初期化しました（投稿有効: {self.posting_enabled}）")

    def post_changes(self, previous_data: Dict, current_data: Dict,
                    analysis_date: Optional[str] = None, force_post: bool = False) -> Dict:
        """
        変化を検知して投稿

        Parameters:
        -----------
        previous_data : Dict
            前回の分析結果データ
        current_data : Dict
            今回の分析結果データ
        analysis_date : Optional[str]
            分析日付（省略時は現在日時）
        force_post : bool
            強制投稿フラグ（変化がなくても投稿する場合）

        Returns:
        --------
        Dict
            投稿結果
        """
        try:
            logger.info("変化検知・投稿処理を開始")

            # 1. 変化検知
            changes = self.detector.detect_changes(previous_data, current_data)
            logger.info(f"変化検知結果: {len(changes)}件の変化を検出")

            # 2. コンテンツ生成
            if changes:
                content = self.generator.generate_post_content(changes, analysis_date)
                post_type = "changes"
            elif force_post:
                content = self.generator.generate_no_changes_content(analysis_date)
                post_type = "no_changes"
            else:
                logger.info("変化が検知されず、強制投稿も指定されていないため投稿をスキップ")
                return {
                    "success": True,
                    "posted": False,
                    "reason": "no_changes_detected",
                    "changes_count": 0
                }

            if not content:
                logger.error("コンテンツ生成に失敗しました")
                return {
                    "success": False,
                    "posted": False,
                    "error": "content_generation_failed"
                }

            # 3. 投稿実行
            if self.posting_enabled and self.twitter_client.is_authenticated:
                result = self._execute_actual_post(content, changes, post_type)
            else:
                result = self._execute_simulation_post(content, changes, post_type)

            # 4. 結果を記録
            self._log_posting_result(result, changes, post_type)

            return result

        except Exception as e:
            logger.error(f"投稿処理エラー: {e}")
            return {
                "success": False,
                "posted": False,
                "error": str(e)
            }

    def _execute_actual_post(self, content: str, changes: List[Dict], post_type: str) -> Dict:
        """
        実際のX API投稿を実行

        Parameters:
        -----------
        content : str
            投稿コンテンツ
        changes : List[Dict]
            検知された変化
        post_type : str
            投稿タイプ

        Returns:
        --------
        Dict
            投稿結果
        """
        try:
            logger.info("実際のX API投稿を実行")

            # X API投稿を実行
            result = self.twitter_client.post_text(content)

            if result.get("success"):
                logger.info(f"X API投稿成功: {result.get('tweet_id')}")
                return {
                    "success": True,
                    "posted": True,
                    "tweet_id": result.get("tweet_id"),
                    "content": content,
                    "changes_count": len(changes),
                    "post_type": post_type,
                    "posted_at": datetime.now()
                }
            else:
                logger.error(f"X API投稿失敗: {result.get('error')}")
                # 投稿失敗時はシミュレーションモードにフォールバック
                logger.info("シミュレーションモードにフォールバック")
                return self._execute_simulation_post(content, changes, post_type)

        except Exception as e:
            logger.error(f"実際の投稿実行エラー: {e}")
            # エラー時はシミュレーションモードにフォールバック
            return self._execute_simulation_post(content, changes, post_type)

    def _execute_simulation_post(self, content: str, changes: List[Dict], post_type: str) -> Dict:
        """
        シミュレーション投稿を実行

        Parameters:
        -----------
        content : str
            投稿コンテンツ
        changes : List[Dict]
            検知された変化
        post_type : str
            投稿タイプ

        Returns:
        --------
        Dict
            投稿結果
        """
        logger.info("シミュレーション投稿を実行")
        logger.info(f"投稿コンテンツ:\n{content}")
        logger.info(f"検知された変化: {len(changes)}件")

        return {
            "success": True,
            "posted": True,
            "tweet_id": f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "content": content,
            "changes_count": len(changes),
            "post_type": post_type,
            "simulation": True,
            "posted_at": datetime.now()
        }

    def _log_posting_result(self, result: Dict, changes: List[Dict], post_type: str):
        """
        投稿結果をログに記録

        Parameters:
        -----------
        result : Dict
            投稿結果
        changes : List[Dict]
            検知された変化
        post_type : str
            投稿タイプ
        """
        try:
            if result.get("success") and result.get("posted"):
                logger.info(f"投稿完了: {result.get('tweet_id')} ({post_type})")
                logger.info(f"変化数: {len(changes)}件")

                # 重要な変化をログに記録
                if changes:
                    logger.info("検知された主要な変化:")
                    for i, change in enumerate(changes[:3], 1):  # 上位3件のみ
                        entity = change.get("entity", "不明")
                        metric = change.get("metric", "不明")
                        change_rate = change.get("change_rate", 0)
                        logger.info(f"  {i}. {entity} - {metric}: {change_rate}%")
            else:
                logger.warning(f"投稿失敗: {result.get('error', 'unknown_error')}")

        except Exception as e:
            logger.error(f"投稿結果ログ記録エラー: {e}")

    def test_connection(self) -> Dict:
        """
        X API接続テスト

        Returns:
        --------
        Dict
            テスト結果
        """
        try:
            if not self.twitter_client.is_authenticated:
                return {
                    "success": False,
                    "error": "X API認証情報が設定されていません"
                }

            # X API接続テストを実行
            test_result = self.twitter_client.test_connection()

            if test_result.get("success"):
                logger.info("X API接続テスト成功")
                return {
                    "success": True,
                    "message": "X API接続テスト成功",
                    "user_info": test_result.get("user_info")
                }
            else:
                logger.error(f"X API接続テスト失敗: {test_result.get('error')}")
                return test_result

        except Exception as e:
            logger.error(f"接続テストエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_system_status(self) -> Dict:
        """
        システム状態を取得

        Returns:
        --------
        Dict
            システム状態
        """
        return {
            "posting_enabled": self.posting_enabled,
            "twitter_authenticated": self.twitter_client.is_authenticated,
            "thresholds": self.detector.get_thresholds(),
            "max_changes_per_post": self.generator.max_changes_per_post,
            "templates": self.generator.get_templates()
        }

    def update_thresholds(self, new_thresholds: Dict):
        """
        閾値を更新

        Parameters:
        -----------
        new_thresholds : Dict
            新しい閾値設定
        """
        self.detector.update_thresholds(new_thresholds)
        logger.info("閾値を更新しました")

    def update_templates(self, new_templates: Dict):
        """
        テンプレートを更新

        Parameters:
        -----------
        new_templates : Dict
            新しいテンプレート設定
        """
        self.generator.update_templates(new_templates)
        logger.info("テンプレートを更新しました")

    def update_metric_names(self, new_names: Dict):
        """
        指標名マッピングを更新

        Parameters:
        -----------
        new_names : Dict
            新しい指標名マッピング
        """
        self.generator.update_metric_names(new_names)
        logger.info("指標名マッピングを更新しました")

    def update_change_types(self, new_types: Dict):
        """
        変化タイプマッピングを更新

        Parameters:
        -----------
        new_types : Dict
            新しい変化タイプマッピング
        """
        self.generator.update_change_types(new_types)
        logger.info("変化タイプマッピングを更新しました")