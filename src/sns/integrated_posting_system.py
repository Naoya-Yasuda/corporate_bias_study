#!/usr/bin/env python
# coding: utf-8

"""
統合投稿システム

S3DataLoaderを統合して、実際の分析データを自動取得し、
変化検知→コンテンツ生成→投稿実行を行う統合システムです。
"""

import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

from .s3_data_loader import S3DataLoader
from .simple_change_detector import SimpleChangeDetector
from .simple_content_generator import SimpleContentGenerator
from .twitter_client import TwitterClient

logger = logging.getLogger(__name__)


class IntegratedPostingSystem:
    """統合投稿システム（S3DataLoader統合版）"""

    def __init__(self, storage_mode: str = "auto", thresholds: Optional[Dict] = None, max_changes_per_post: int = 5):
        """
        Parameters:
        -----------
        storage_mode : str
            ストレージモード（"local", "s3", "auto"）
        thresholds : Optional[Dict]
            変化検知の閾値設定
        max_changes_per_post : int
            1投稿あたりの最大変化数
        """
        # 各コンポーネントを初期化
        self.s3_loader = S3DataLoader(storage_mode)
        self.detector = SimpleChangeDetector(thresholds)
        self.generator = SimpleContentGenerator(max_changes_per_post)
        self.twitter_client = TwitterClient()

        # 投稿設定
        self.posting_enabled = os.getenv('TWITTER_POSTING_ENABLED', 'true').lower() == 'true'

        logger.info(f"統合投稿システムを初期化しました（ストレージモード: {storage_mode}, 投稿有効: {self.posting_enabled}）")

    def post_latest_changes(self, force_post: bool = False) -> Dict:
        """
        最新の分析結果の変化を検知して投稿

        Parameters:
        -----------
        force_post : bool
            強制投稿フラグ（変化がなくても投稿する場合）

        Returns:
        --------
        Dict
            投稿結果
        """
        try:
            logger.info("最新分析結果の変化検知・投稿処理を開始")

            # 1. 最新の分析日付を取得
            latest_date = self.s3_loader.get_latest_analysis_date()
            if not latest_date:
                logger.error("最新の分析日付が見つかりません")
                return {
                    "success": False,
                    "posted": False,
                    "error": "latest_analysis_date_not_found"
                }

            logger.info(f"最新分析日付: {latest_date}")

            # 2. 比較データを取得
            comparison_data = self.s3_loader.load_comparison_data(latest_date)
            if not comparison_data:
                logger.error(f"比較データの取得に失敗しました: {latest_date}")
                return {
                    "success": False,
                    "posted": False,
                    "error": "comparison_data_load_failed"
                }

            # 3. エンティティ指標を抽出
            previous_metrics = {}
            current_metrics = {}

            if comparison_data.get("previous"):
                previous_metrics = self.s3_loader.extract_entity_metrics(comparison_data["previous"])

            current_metrics = self.s3_loader.extract_entity_metrics(comparison_data["current"])

            logger.info(f"指標抽出完了: 前回{len(previous_metrics)}件, 今回{len(current_metrics)}件")

            # 4. 投稿実行
            return self._execute_posting(
                previous_metrics,
                current_metrics,
                latest_date,
                force_post
            )

        except Exception as e:
            logger.error(f"最新変化投稿処理エラー: {e}")
            return {
                "success": False,
                "posted": False,
                "error": str(e)
            }

    def post_specific_date_changes(self, target_date: str, force_post: bool = False) -> Dict:
        """
        指定日付の分析結果の変化を検知して投稿

        Parameters:
        -----------
        target_date : str
            対象日付（YYYYMMDD形式）
        force_post : bool
            強制投稿フラグ（変化がなくても投稿する場合）

        Returns:
        --------
        Dict
            投稿結果
        """
        try:
            logger.info(f"指定日付の変化検知・投稿処理を開始: {target_date}")

            # 1. 比較データを取得
            comparison_data = self.s3_loader.load_comparison_data(target_date)
            if not comparison_data:
                logger.error(f"比較データの取得に失敗しました: {target_date}")
                return {
                    "success": False,
                    "posted": False,
                    "error": "comparison_data_load_failed"
                }

            # 2. エンティティ指標を抽出
            previous_metrics = {}
            current_metrics = {}

            if comparison_data.get("previous"):
                previous_metrics = self.s3_loader.extract_entity_metrics(comparison_data["previous"])

            current_metrics = self.s3_loader.extract_entity_metrics(comparison_data["current"])

            logger.info(f"指標抽出完了: 前回{len(previous_metrics)}件, 今回{len(current_metrics)}件")

            # 3. 投稿実行
            return self._execute_posting(
                previous_metrics,
                current_metrics,
                target_date,
                force_post
            )

        except Exception as e:
            logger.error(f"指定日付変化投稿処理エラー: {e}")
            return {
                "success": False,
                "posted": False,
                "error": str(e)
            }

    def _execute_posting(self, previous_metrics: Dict, current_metrics: Dict,
                        analysis_date: str, force_post: bool) -> Dict:
        """
        投稿処理を実行

        Parameters:
        -----------
        previous_metrics : Dict
            前回のエンティティ指標
        current_metrics : Dict
            今回のエンティティ指標
        analysis_date : str
            分析日付
        force_post : bool
            強制投稿フラグ

        Returns:
        --------
        Dict
            投稿結果
        """
        try:
            # 1. 変化検知
            changes = self.detector.detect_changes(previous_metrics, current_metrics)
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
                    "changes_count": 0,
                    "analysis_date": analysis_date
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
                result = self._execute_actual_post(content, changes, post_type, analysis_date)
            else:
                result = self._execute_simulation_post(content, changes, post_type, analysis_date)

            # 4. 結果を記録
            self._log_posting_result(result, changes, post_type, analysis_date)

            return result

        except Exception as e:
            logger.error(f"投稿処理エラー: {e}")
            return {
                "success": False,
                "posted": False,
                "error": str(e)
            }

    def _execute_actual_post(self, content: str, changes: List[Dict], post_type: str, analysis_date: str) -> Dict:
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
        analysis_date : str
            分析日付

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
                    "analysis_date": analysis_date,
                    "posted_at": datetime.now()
                }
            else:
                logger.error(f"X API投稿失敗: {result.get('error')}")
                # 投稿失敗時はシミュレーションモードにフォールバック
                logger.info("シミュレーションモードにフォールバック")
                return self._execute_simulation_post(content, changes, post_type, analysis_date)

        except Exception as e:
            logger.error(f"実際の投稿実行エラー: {e}")
            # エラー時はシミュレーションモードにフォールバック
            return self._execute_simulation_post(content, changes, post_type, analysis_date)

    def _execute_simulation_post(self, content: str, changes: List[Dict], post_type: str, analysis_date: str) -> Dict:
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
        analysis_date : str
            分析日付

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
            "analysis_date": analysis_date,
            "simulation": True,
            "posted_at": datetime.now()
        }

    def _log_posting_result(self, result: Dict, changes: List[Dict], post_type: str, analysis_date: str):
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
        analysis_date : str
            分析日付
        """
        try:
            if result.get("success") and result.get("posted"):
                logger.info(f"投稿完了: {result.get('tweet_id')} ({post_type}) - 分析日: {analysis_date}")
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
            "storage_mode": self.s3_loader.get_storage_mode(),
            "thresholds": self.detector.get_thresholds(),
            "max_changes_per_post": self.generator.max_changes_per_post,
            "templates": self.generator.get_templates()
        }

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

    def list_available_dates(self) -> List[str]:
        """
        利用可能な分析日付のリストを取得

        Returns:
        --------
        List[str]
            利用可能な分析日付のリスト
        """
        return self.s3_loader.list_available_dates()

    def get_latest_analysis_date(self) -> Optional[str]:
        """
        最新の分析日付を取得

        Returns:
        --------
        Optional[str]
            最新の分析日付
        """
        return self.s3_loader.get_latest_analysis_date()