#!/usr/bin/env python
# coding: utf-8

"""
S3データローダー

SNS投稿機能で使用するためのS3データ読み込み機能を提供します。
既存のHybridDataLoaderを活用してS3から分析結果を読み込みます。
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from src.analysis.hybrid_data_loader import HybridDataLoader

logger = logging.getLogger(__name__)


class S3DataLoader:
    """S3データローダー（SNS投稿機能用）"""

    def __init__(self, storage_mode: str = "auto"):
        """
        Parameters:
        -----------
        storage_mode : str
            ストレージモード（"local", "s3", "auto"）
        """
        self.hybrid_loader = HybridDataLoader(storage_mode)
        self.storage_mode = storage_mode

        logger.info(f"S3DataLoader初期化: mode={storage_mode}")

    def load_analysis_results(self, date: str) -> Optional[Dict]:
        """
        指定日付の分析結果を読み込み

        Parameters:
        -----------
        date : str
            日付（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            分析結果データ（読み込み失敗時はNone）
        """
        try:
            results = self.hybrid_loader.load_analysis_results(date)
            logger.info(f"分析結果読み込み成功: {date}")
            return results
        except Exception as e:
            logger.error(f"分析結果読み込み失敗: {date}, エラー: {e}")
            return None

    def load_integrated_data(self, date: str) -> Optional[Dict]:
        """
        指定日付の統合データを読み込み

        Parameters:
        -----------
        date : str
            日付（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            統合データ（読み込み失敗時はNone）
        """
        try:
            data = self.hybrid_loader.load_integrated_data(date)
            logger.info(f"統合データ読み込み成功: {date}")
            return data
        except Exception as e:
            logger.error(f"統合データ読み込み失敗: {date}, エラー: {e}")
            return None

    def list_available_dates(self) -> List[str]:
        """
        利用可能な日付のリストを取得

        Returns:
        --------
        List[str]
            利用可能な日付のリスト（YYYYMMDD形式）
        """
        try:
            dates = self.hybrid_loader.list_available_dates()
            logger.info(f"利用可能日付数: {len(dates)}件")
            return dates
        except Exception as e:
            logger.error(f"利用可能日付取得失敗: {e}")
            return []

    def get_latest_analysis_date(self) -> Optional[str]:
        """
        最新の分析日付を取得

        Returns:
        --------
        Optional[str]
            最新の分析日付（YYYYMMDD形式、取得失敗時はNone）
        """
        try:
            dates = self.list_available_dates()
            if dates:
                latest_date = max(dates)
                logger.info(f"最新分析日付: {latest_date}")
                return latest_date
            else:
                logger.warning("利用可能な分析日付が見つかりません")
                return None
        except Exception as e:
            logger.error(f"最新分析日付取得失敗: {e}")
            return None

    def get_previous_analysis_date(self, current_date: str) -> Optional[str]:
        """
        指定日付の前回の分析日付を取得

        Parameters:
        -----------
        current_date : str
            現在の日付（YYYYMMDD形式）

        Returns:
        --------
        Optional[str]
            前回の分析日付（YYYYMMDD形式、取得失敗時はNone）
        """
        try:
            dates = self.list_available_dates()
            if not dates:
                return None

            # 現在日付より前の日付をフィルタリング
            previous_dates = [d for d in dates if d < current_date]

            if previous_dates:
                previous_date = max(previous_dates)
                logger.info(f"前回分析日付: {previous_date} (現在: {current_date})")
                return previous_date
            else:
                logger.info(f"前回の分析日付が見つかりません: {current_date}")
                return None

        except Exception as e:
            logger.error(f"前回分析日付取得失敗: {e}")
            return None

    def load_comparison_data(self, current_date: str) -> Optional[Dict]:
        """
        比較用のデータ（前回と今回）を読み込み

        Parameters:
        -----------
        current_date : str
            現在の分析日付（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            比較データ {"previous": {...}, "current": {...}}
        """
        try:
            # 現在のデータを読み込み
            current_data = self.load_analysis_results(current_date)
            if not current_data:
                logger.error(f"現在の分析結果を読み込めません: {current_date}")
                return None

            # 前回の日付を取得
            previous_date = self.get_previous_analysis_date(current_date)
            if not previous_date:
                logger.info(f"前回の分析日付が見つからないため、比較データなし: {current_date}")
                return {
                    "previous": None,
                    "current": current_data
                }

            # 前回のデータを読み込み
            previous_data = self.load_analysis_results(previous_date)
            if not previous_data:
                logger.warning(f"前回の分析結果を読み込めません: {previous_date}")
                return {
                    "previous": None,
                    "current": current_data
                }

            logger.info(f"比較データ読み込み成功: {previous_date} → {current_date}")
            return {
                "previous": previous_data,
                "current": current_data,
                "previous_date": previous_date,
                "current_date": current_date
            }

        except Exception as e:
            logger.error(f"比較データ読み込み失敗: {e}")
            return None

    def extract_entity_metrics(self, analysis_results: Dict) -> Dict:
        """
        分析結果からエンティティ別の指標を抽出

        Parameters:
        -----------
        analysis_results : Dict
            分析結果データ

        Returns:
        --------
        Dict
            エンティティ別指標データ
        """
        try:
            entity_metrics = {}

            # 分析結果からエンティティ別データを抽出
            if "entity_analysis" in analysis_results:
                for entity, data in analysis_results["entity_analysis"].items():
                    metrics = {}

                    # バイアススコア
                    if "bias_score" in data:
                        metrics["bias_score"] = data["bias_score"]

                    # センチメントスコア
                    if "sentiment_score" in data:
                        metrics["sentiment_score"] = data["sentiment_score"]

                    # ランキング
                    if "ranking" in data:
                        metrics["ranking"] = data["ranking"]

                    # 公平性スコア
                    if "fairness_score" in data:
                        metrics["fairness_score"] = data["fairness_score"]

                    # 中立性スコア
                    if "neutrality_score" in data:
                        metrics["neutrality_score"] = data["neutrality_score"]

                    if metrics:
                        entity_metrics[entity] = metrics

            logger.info(f"エンティティ指標抽出: {len(entity_metrics)}件")
            return entity_metrics

        except Exception as e:
            logger.error(f"エンティティ指標抽出失敗: {e}")
            return {}

    def get_storage_mode(self) -> str:
        """
        現在のストレージモードを取得

        Returns:
        --------
        str
            ストレージモード
        """
        return self.storage_mode