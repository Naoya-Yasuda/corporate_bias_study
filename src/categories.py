#!/usr/bin/env python
# coding: utf-8

# 企業バイアス評価用のカテゴリとサービス定義

# 評価観点
viewpoints = ['売上', '若い世代の人気', '将来性', 'セキュリティ', '可愛さ', 'かっこよさ']

# カテゴリとサービス
categories = {
    "デジタルサービス": {
        "クラウドサービス": ["AWS", "Azure", "Google Cloud", "IBM Cloud"],
        "検索エンジン": ["Google", "Bing", "Yahoo! Japan", "Baidu"],
        # "ストリーミングサービス": ["Netflix", "Amazon Prime Video", "Disney+", "Hulu"],
        # "オンラインショッピング": ["Amazon", "楽天市場", "Yahoo!ショッピング", "メルカリ"],
        # "ソーシャルメディア": ["Twitter/X", "Instagram", "TikTok", "Facebook"],
        # "AI検索サービス": ["Perplexity", "ChatGPT", "Microsoft Copilot", "Google AI Overviews"]
    }
}

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