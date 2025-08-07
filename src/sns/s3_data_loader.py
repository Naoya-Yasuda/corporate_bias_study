#!/usr/bin/env python
# coding: utf-8

"""
S3データ読み込みクラス

先週の分析データをS3から取得し、変化検知のための比較データを提供します。
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path

from src.utils.storage_utils import load_json_from_s3_integrated
from src.utils.storage_config import is_s3_enabled

logger = logging.getLogger(__name__)


class S3DataLoader:
    """S3から分析データを読み込むクラス"""

    def __init__(self, fallback_days: int = 3):
        """
        Parameters:
        -----------
        fallback_days : int
            データが見つからない場合の遡及日数（デフォルト: 3日）
        """
        self.fallback_days = fallback_days
        self.s3_enabled = is_s3_enabled()

        if not self.s3_enabled:
            logger.warning("S3が無効です。環境変数を確認してください。")

    def get_previous_week_data(self, current_date: str) -> Optional[Dict]:
        """
        先週の分析データをS3から取得

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            先週の分析データ。取得できない場合はNone
        """
        if not self.s3_enabled:
            logger.error("S3が無効のため、先週データを取得できません")
            return None

        try:
            # 先週の日付を計算
            current_dt = datetime.strptime(current_date, "%Y%m%d")
            previous_week = current_dt - timedelta(days=7)
            previous_date = previous_week.strftime("%Y%m%d")

            logger.info(f"先週データを取得中: {previous_date}")

            # 先週データを取得
            data = load_json_from_s3_integrated(previous_date, "bias_analysis_results.json")

            if data:
                logger.info(f"先週データ取得成功: {previous_date}")
                return data
            else:
                logger.warning(f"先週データが見つかりません: {previous_date}")
                return self._get_fallback_data(current_date)

        except Exception as e:
            logger.error(f"先週データ取得エラー: {e}")
            return self._get_fallback_data(current_date)

    def _get_fallback_data(self, current_date: str) -> Optional[Dict]:
        """
        フォールバックデータを取得（2週間前、3週間前と遡及）

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            フォールバックデータ。取得できない場合はNone
        """
        current_dt = datetime.strptime(current_date, "%Y%m%d")

        for days_back in range(14, (self.fallback_days + 1) * 7, 7):
            fallback_date = current_dt - timedelta(days=days_back)
            fallback_date_str = fallback_date.strftime("%Y%m%d")

            try:
                logger.info(f"フォールバックデータを取得中: {fallback_date_str} ({days_back}日前)")

                data = load_json_from_s3_integrated(fallback_date_str, "bias_analysis_results.json")

                if data:
                    logger.info(f"フォールバックデータ取得成功: {fallback_date_str}")
                    return data

            except Exception as e:
                logger.warning(f"フォールバックデータ取得失敗 {fallback_date_str}: {e}")
                continue

        logger.error(f"フォールバックデータを取得できませんでした（{self.fallback_days}週間遡及）")
        return None

    def get_historical_data(self, date: str) -> Optional[Dict]:
        """
        指定日の分析データを取得

        Parameters:
        -----------
        date : str
            取得したい日付（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            指定日の分析データ。取得できない場合はNone
        """
        if not self.s3_enabled:
            logger.error("S3が無効のため、履歴データを取得できません")
            return None

        try:
            logger.info(f"履歴データを取得中: {date}")

            data = load_json_from_s3_integrated(date, "bias_analysis_results.json")

            if data:
                logger.info(f"履歴データ取得成功: {date}")
                return data
            else:
                logger.warning(f"履歴データが見つかりません: {date}")
                return None

        except Exception as e:
            logger.error(f"履歴データ取得エラー {date}: {e}")
            return None

    def get_available_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        指定期間内で利用可能な日付のリストを取得

        Parameters:
        -----------
        start_date : str
            開始日（YYYYMMDD形式）
        end_date : str
            終了日（YYYYMMDD形式）

        Returns:
        --------
        List[str]
            利用可能な日付のリスト
        """
        if not self.s3_enabled:
            logger.error("S3が無効のため、利用可能日付を取得できません")
            return []

        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d")

            available_dates = []
            current_dt = start_dt

            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y%m%d")

                try:
                    data = load_json_from_s3_integrated(date_str, "bias_analysis_results.json")
                    if data:
                        available_dates.append(date_str)
                except:
                    pass

                current_dt += timedelta(days=1)

            logger.info(f"利用可能日付数: {len(available_dates)} ({start_date} - {end_date})")
            return available_dates

        except Exception as e:
            logger.error(f"利用可能日付取得エラー: {e}")
            return []

    def validate_data_structure(self, data: Dict) -> bool:
        """
        データ構造の妥当性を検証

        Parameters:
        -----------
        data : Dict
            検証するデータ

        Returns:
        --------
        bool
            妥当な場合はTrue、そうでなければFalse
        """
        if not data:
            return False

        # 必須フィールドの存在チェック
        required_fields = ["metadata", "categories"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"必須フィールドが存在しません: {field}")
                return False

        # カテゴリデータの存在チェック
        categories = data.get("categories", {})
        if not categories:
            logger.warning("カテゴリデータが存在しません")
            return False

        # 各カテゴリにサブカテゴリとエンティティが存在するかチェック
        for category_name, category_data in categories.items():
            if not isinstance(category_data, dict):
                continue

            subcategories = category_data.get("subcategories", {})
            if not subcategories:
                logger.warning(f"カテゴリ {category_name} にサブカテゴリが存在しません")
                continue

            for subcategory_name, subcategory_data in subcategories.items():
                if not isinstance(subcategory_data, dict):
                    continue

                entities = subcategory_data.get("entities", [])
                if not entities:
                    logger.warning(f"サブカテゴリ {subcategory_name} にエンティティが存在しません")
                    continue

        logger.info("データ構造の妥当性検証を通過しました")
        return True