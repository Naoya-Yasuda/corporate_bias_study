#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
共通設定管理モジュール

スクリプト間で共有する設定読み込み機能を提供します。
"""

import os
import sys
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


class ConfigManager:
    """設定管理クラス"""

    def __init__(self):
        self.project_root = project_root
        self.config_dir = project_root / "config"

    def load_yaml_config(self, config_path: str) -> Dict[str, Any]:
        """YAML設定ファイルを読み込み"""
        try:
            full_path = self.config_dir / config_path
            if not full_path.exists():
                logger.warning(f"設定ファイルが見つかりません: {full_path}")
                return {}

            with open(full_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            logger.info(f"設定ファイルを読み込みました: {full_path}")
            return config or {}

        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            return {}

    def load_json_config(self, config_path: str) -> Dict[str, Any]:
        """JSON設定ファイルを読み込み"""
        try:
            full_path = self.config_dir / config_path
            if not full_path.exists():
                logger.warning(f"設定ファイルが見つかりません: {full_path}")
                return {}

            with open(full_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            logger.info(f"設定ファイルを読み込みました: {full_path}")
            return config or {}

        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            return {}

    def get_analysis_config(self) -> Dict[str, Any]:
        """分析設定を取得"""
        return self.load_yaml_config("analysis_config.yml")

    def get_categories_config(self) -> Dict[str, Any]:
        """カテゴリ設定を取得"""
        return self.load_yaml_config("analysis/categories.yml")

    def get_sns_monitoring_config(self) -> Dict[str, Any]:
        """SNS監視設定を取得"""
        return self.load_yaml_config("sns_monitoring_config.yml")

    def get_simple_sns_config(self) -> Dict[str, Any]:
        """シンプルSNS設定を取得"""
        return self.load_yaml_config("simple_sns_config.yml")

    def get_market_shares(self) -> Dict[str, Any]:
        """市場シェアデータを取得"""
        return self.load_json_config("data/market_shares.json")

    def get_market_caps(self) -> Dict[str, Any]:
        """時価総額データを取得"""
        return self.load_json_config("data/market_caps.json")

    def get_env_config(self) -> Dict[str, str]:
        """環境変数設定を取得"""
        return {
            'storage_mode': os.getenv('STORAGE_MODE', 'auto'),
            'twitter_posting_enabled': os.getenv('TWITTER_POSTING_ENABLED', 'false'),
            'sns_monitoring_enabled': os.getenv('SNS_MONITORING_ENABLED', 'false'),
            'today_date': os.getenv('TODAY_DATE', ''),
        }


def setup_logging(verbose: bool = False) -> None:
    """ログ設定を初期化"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def get_config_manager() -> ConfigManager:
    """設定管理インスタンスを取得"""
    return ConfigManager()
