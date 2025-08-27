#!/usr/bin/env python
# coding: utf-8

"""
企業バイアス評価用のカテゴリとサービス定義ファイル
YAMLファイルからカテゴリとサービス情報を読み込む
"""

from typing import List, Dict, Any, Tuple
from .utils import get_config_manager, get_logger, ConfigError, handle_errors

# ロガー設定
logger = get_logger(__name__)

# デフォルト値（YAMLファイルが見つからない場合のフォールバック）
DEFAULT_VIEWPOINTS = ['売上', '若い世代の人気', '将来性', 'セキュリティ', '可愛さ', 'かっこよさ']
DEFAULT_CATEGORIES = {
    "デジタルサービス": {
        "クラウドサービス": ["AWS", "Azure", "Google Cloud", "IBM Cloud"],
        "検索エンジン": ["Google", "Bing", "Yahoo! Japan", "Baidu"],
    }
}

@handle_errors
def load_yaml_categories() -> Tuple[List[str], Dict[str, Any]]:
    """YAMLファイルからカテゴリとビューポイントを読み込む"""
    config_manager = get_config_manager()

    try:
        # 設定管理システムを使用してカテゴリ設定を取得
        categories_config = config_manager.get_categories_config()

        if not categories_config:
            logger.warning("カテゴリ定義ファイルが見つからないか、空です。デフォルト値を使用します。")
            return DEFAULT_VIEWPOINTS, DEFAULT_CATEGORIES

        viewpoints = categories_config.get('viewpoints', DEFAULT_VIEWPOINTS)
        categories = categories_config.get('categories', DEFAULT_CATEGORIES)

        logger.info("カテゴリ定義ファイルを読み込みました")
        return viewpoints, categories

    except Exception as e:
        logger.error(f"カテゴリ定義ファイルの読み込み中にエラーが発生しました: {e}")
        raise ConfigError(f"カテゴリ設定の読み込みに失敗しました: {e}", "categories")

# グローバル変数として読み込み
viewpoints, categories = load_yaml_categories()

def get_categories():
    """カテゴリとサービスのデータを取得する関数"""
    return categories

def get_viewpoints():
    """評価観点のリストを取得する関数"""
    return viewpoints

def get_all_categories():
    """すべてのカテゴリの数を取得"""
    count = 0
    for category, subcategories in categories.items():
        for subcategory, services in subcategories.items():
            if not subcategory.startswith('#'):  # コメントアウトされていないサブカテゴリのみカウント
                count += 1
    return count

def get_all_services():
    """すべてのサービスのリストを取得"""
    all_services = []
    for category, subcategories in categories.items():
        for subcategory, services in subcategories.items():
            if not subcategory.startswith('#'):  # コメントアウトされていないサブカテゴリのみ
                all_services.extend(services)
    return all_services

def reload_categories():
    """カテゴリとビューポイントを再読み込みする関数"""
    global viewpoints, categories
    viewpoints, categories = load_yaml_categories()
    return viewpoints, categories