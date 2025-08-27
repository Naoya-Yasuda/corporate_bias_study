#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
統合設定管理モジュール

src/内のモジュールで使用する設定読み込み機能を提供します。
環境変数、設定ファイル、API設定を一元管理します。
"""

import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

logger = logging.getLogger(__name__)


class ConfigManager:
    """統合設定管理クラス"""

    def __init__(self):
        # プロジェクトルートの設定
        current_dir = Path(__file__).parent
        self.project_root = current_dir.parent.parent
        self.config_dir = self.project_root / "config"

        # 設定キャッシュ
        self._cache = {}

    def load_yaml_config(self, config_path: str, use_cache: bool = True) -> Dict[str, Any]:
        """YAML設定ファイルを読み込み"""
        if use_cache and config_path in self._cache:
            return self._cache[config_path]

        try:
            full_path = self.config_dir / config_path
            if not full_path.exists():
                logger.warning(f"設定ファイルが見つかりません: {full_path}")
                return {}

            with open(full_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if use_cache:
                self._cache[config_path] = config or {}

            logger.debug(f"設定ファイルを読み込みました: {full_path}")
            return config or {}

        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            return {}

    def load_json_config(self, config_path: str, use_cache: bool = True) -> Dict[str, Any]:
        """JSON設定ファイルを読み込み"""
        if use_cache and config_path in self._cache:
            return self._cache[config_path]

        try:
            full_path = self.config_dir / config_path
            if not full_path.exists():
                logger.warning(f"設定ファイルが見つかりません: {full_path}")
                return {}

            with open(full_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if use_cache:
                self._cache[config_path] = config or {}

            logger.debug(f"設定ファイルを読み込みました: {full_path}")
            return config or {}

        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            return {}

    def get_env(self, key: str, default: Any = None) -> Any:
        """環境変数を取得"""
        return os.getenv(key, default)

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

    def get_api_config(self) -> Dict[str, str]:
        """API設定を取得"""
        return {
            'perplexity_api_key': self.get_env('PERPLEXITY_API_KEY', ''),
            'google_api_key': self.get_env('GOOGLE_API_KEY', ''),
            'google_cse_id': self.get_env('GOOGLE_CSE_ID', ''),
            'twitter_api_key': self.get_env('TWITTER_API_KEY', ''),
            'twitter_api_secret': self.get_env('TWITTER_API_SECRET', ''),
            'twitter_bearer_token': self.get_env('TWITTER_BEARER_TOKEN', ''),
            'twitter_access_token': self.get_env('TWITTER_ACCESS_TOKEN', ''),
            'twitter_access_token_secret': self.get_env('TWITTER_ACCESS_TOKEN_SECRET', ''),
        }

    def get_storage_config(self) -> Dict[str, str]:
        """ストレージ設定を取得"""
        return {
            'storage_mode': self.get_env('STORAGE_MODE', 'auto'),
            'aws_access_key': self.get_env('AWS_ACCESS_KEY', ''),
            'aws_secret_key': self.get_env('AWS_SECRET_KEY', ''),
            'aws_region': self.get_env('AWS_REGION', 'ap-northeast-1'),
            's3_bucket_name': self.get_env('S3_BUCKET_NAME', ''),
        }

    def get_sns_config(self) -> Dict[str, str]:
        """SNS設定を取得"""
        return {
            'twitter_posting_enabled': self.get_env('TWITTER_POSTING_ENABLED', 'false'),
            'sns_monitoring_enabled': self.get_env('SNS_MONITORING_ENABLED', 'false'),
            'today_date': self.get_env('TODAY_DATE', ''),
        }

    def validate_config(self, config_type: str) -> bool:
        """設定の妥当性を検証"""
        try:
            if config_type == 'api':
                api_config = self.get_api_config()
                required_keys = ['perplexity_api_key', 'google_api_key', 'google_cse_id']
                return all(api_config.get(key) for key in required_keys)

            elif config_type == 'storage':
                storage_config = self.get_storage_config()
                if storage_config['storage_mode'] == 's3':
                    required_keys = ['aws_access_key', 'aws_secret_key', 's3_bucket_name']
                    return all(storage_config.get(key) for key in required_keys)
                return True

            elif config_type == 'categories':
                categories = self.get_categories_config()
                return bool(categories.get('categories') and categories.get('viewpoints'))

            return True

        except Exception as e:
            logger.error(f"設定検証エラー: {e}")
            return False

    def clear_cache(self) -> None:
        """設定キャッシュをクリア"""
        self._cache.clear()


# グローバルインスタンス
_config_manager = None


def get_config_manager() -> ConfigManager:
    """設定管理インスタンスを取得（シングルトン）"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def setup_logging(verbose: bool = False) -> None:
    """ログ設定を初期化"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
