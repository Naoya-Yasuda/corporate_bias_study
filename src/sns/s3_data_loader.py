#!/usr/bin/env python
# coding: utf-8

"""
S3データ読み込みクラス

直前の分析データをS3から取得し、変化検知のための比較データを提供します。
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

    def get_previous_data(self, current_date: str) -> Optional[Dict]:
        """
        直前の分析データをS3から取得（今回の一つ前のデータ）

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）

        Returns:
        --------
        Optional[Dict]
            直前の分析データ。取得できない場合はNone
        """
        if not self.s3_enabled:
            logger.error("S3が無効のため、直前データを取得できません")
            return None

        try:
            # 直前データを取得（1日前から遡及）
            current_dt = datetime.strptime(current_date, "%Y%m%d")

            # 1日前から遡及して直前のデータを探す
            for days_back in range(1, self.fallback_days + 1):
                target_date = current_dt - timedelta(days=days_back)
                target_date_str = target_date.strftime("%Y%m%d")

                logger.info(f"直前データを取得中: {target_date_str} ({days_back}日前)")

                data = load_json_from_s3_integrated(target_date_str, "bias_analysis_results.json")

                if data:
                    logger.info(f"直前データ取得成功: {target_date_str}")
                    return data

            logger.warning(f"直前{self.fallback_days}日間でデータが見つかりません")
            return None

        except Exception as e:
            logger.error(f"直前データ取得エラー: {e}")
            return None

    def get_specific_previous_data(self, current_date: str, days_back: int) -> Optional[Dict]:
        """
        指定日前の分析データをS3から取得

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）
        days_back : int
            何日前のデータを取得するか

        Returns:
        --------
        Optional[Dict]
            指定日前の分析データ。取得できない場合はNone
        """
        if not self.s3_enabled:
            logger.error("S3が無効のため、過去データを取得できません")
            return None

        try:
            # 指定日前の日付を計算
            current_dt = datetime.strptime(current_date, "%Y%m%d")
            target_date = current_dt - timedelta(days=days_back)
            target_date_str = target_date.strftime("%Y%m%d")

            logger.info(f"{days_back}日前のデータを取得中: {target_date_str}")

            data = load_json_from_s3_integrated(target_date_str, "bias_analysis_results.json")

            if data:
                logger.info(f"{days_back}日前のデータ取得成功: {target_date_str}")
                return data
            else:
                logger.warning(f"{days_back}日前のデータが見つかりません: {target_date_str}")
                return self._get_fallback_data(current_date, days_back)

        except Exception as e:
            logger.error(f"{days_back}日前のデータ取得エラー: {e}")
            return self._get_fallback_data(current_date, days_back)

    def _get_fallback_data(self, current_date: str, target_days_back: int) -> Optional[Dict]:
        """
        フォールバックデータを取得（指定日付の前後で遡及）

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）
        target_days_back : int
            目標の遡及日数

        Returns:
        --------
        Optional[Dict]
            フォールバックデータ。取得できない場合はNone
        """
        current_dt = datetime.strptime(current_date, "%Y%m%d")

        # 目標日付の前後でデータを探す
        search_range = max(1, self.fallback_days // 2)

        for offset in range(-search_range, search_range + 1):
            days_back = target_days_back + offset
            if days_back < 1:
                continue

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

        logger.error(f"フォールバックデータを取得できませんでした（{target_days_back}日前の前後{search_range}日間）")
        return None

    def get_comparison_data(self, current_date: str, comparison_days: int = 1) -> Optional[Dict]:
        """
        比較用の過去データを取得

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）
        comparison_days : int
            比較対象の日数（デフォルト: 1日前）

        Returns:
        --------
        Optional[Dict]
            比較用データ。取得できない場合はNone
        """
        return self.get_specific_previous_data(current_date, comparison_days)

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

    def get_recent_available_dates(self, days: int = 7) -> List[str]:
        """
        直近の利用可能な日付のリストを取得

        Parameters:
        -----------
        days : int
            遡及する日数（デフォルト: 7日）

        Returns:
        --------
        List[str]
            直近の利用可能な日付のリスト
        """
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        return self.get_available_dates(start_date, end_date)

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