#!/usr/bin/env python
# coding: utf-8

"""
企業バイアス評価用のカテゴリとサービス定義ファイル
YAMLファイルからカテゴリとサービス情報を読み込む
"""

import os
import yaml
import logging

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 相対パスの定義
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
CATEGORIES_YAML = os.path.join(PROJECT_ROOT, "config", "analysis", "categories.yml")

# デフォルト値（YAMLファイルが見つからない場合のフォールバック）
DEFAULT_VIEWPOINTS = ['売上', '若い世代の人気', '将来性', 'セキュリティ', '可愛さ', 'かっこよさ']
DEFAULT_CATEGORIES = {
    "デジタルサービス": {
        "クラウドサービス": ["AWS", "Azure", "Google Cloud", "IBM Cloud"],
        "検索エンジン": ["Google", "Bing", "Yahoo! Japan", "Baidu"],
    }
}

def load_yaml_categories():
    """YAMLファイルからカテゴリとビューポイントを読み込む"""
    try:
        if not os.path.exists(CATEGORIES_YAML):
            logger.warning(f"カテゴリ定義ファイルが見つかりません: {CATEGORIES_YAML}")
            return DEFAULT_VIEWPOINTS, DEFAULT_CATEGORIES

        with open(CATEGORIES_YAML, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        viewpoints = data.get('viewpoints', DEFAULT_VIEWPOINTS)
        categories = data.get('categories', DEFAULT_CATEGORIES)

        logger.info(f"カテゴリ定義ファイルを読み込みました: {CATEGORIES_YAML}")
        return viewpoints, categories

    except Exception as e:
        logger.error(f"カテゴリ定義ファイルの読み込み中にエラーが発生しました: {e}")
        return DEFAULT_VIEWPOINTS, DEFAULT_CATEGORIES

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