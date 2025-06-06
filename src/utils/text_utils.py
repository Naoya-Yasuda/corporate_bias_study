#!/usr/bin/env python
# coding: utf-8

'''
テキスト処理のユーティリティ関数

URLやテキスト処理の共通機能を提供します
'''

import re
from urllib.parse import urlparse

def extract_domain(url):
    '''
    URLからドメインを抽出（www.を除去）

    Parameters:
    -----------
    url : str
        対象URL

    Returns:
    --------
    str
        抽出されたドメイン
    '''
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""

def is_negative(title, snippet):
    """タイトルとスニペットからネガティブコンテンツかを判定"""
    # ネガティブキーワードリスト（簡易版）
    negative_keywords = [
        "問題", "障害", "失敗", "リスク", "欠陥", "批判", "炎上", "トラブル",
        "不具合", "バグ", "遅延", "停止", "故障", "危険", "脆弱性", "違反",
        "disadvantage", "problem", "issue", "bug", "risk", "fail", "error",
        "vulnerability", "outage", "down", "criticism", "negative", "trouble"
    ]

    combined_text = (title + " " + snippet).lower()

    for keyword in negative_keywords:
        if keyword in combined_text:
            return True

    return False

def ratio(lst, pred_func):
    '''
    リストに対して述語関数を適用し、True の割合を返す

    Parameters:
    -----------
    lst : list
        対象リスト
    pred_func : callable
        適用する述語関数

    Returns:
    --------
    float
        True の割合
    '''
    if not lst:
        return 0
    return sum(1 for x in lst if pred_func(x)) / len(lst)

def extract_companies_from_text(text, companies):
    '''
    テキストから企業名を抽出

    Parameters:
    -----------
    text : str
        対象テキスト
    companies : list
        抽出する企業名リスト

    Returns:
    --------
    list
        テキスト内に見つかった企業名のリスト
    '''
    found_companies = []
    for company in companies:
        # 企業名の前後に単語境界があるかを確認するための正規表現
        pattern = r'(?<!\w)' + re.escape(company) + r'(?!\w)'
        if re.search(pattern, text, re.IGNORECASE):
            found_companies.append(company)
    return found_companies

def is_official_domain(domain: str, company: str, companies_dict: dict) -> str:
    """
    指定ドメインが公式サイトかどうか判定する関数
    - domain: 判定対象（例 'blog.example.com'）
    - company: 企業名（例 'AWS'）
    - companies_dict: 企業名と公式ドメインのリストの辞書
    戻り値: 'official' / 'unofficial' / 'n/a'
    """
    if not domain or not company or not companies_dict:
        return "n/a"

    # ドメインの正規化
    domain = domain.lower().rstrip('.')  # 末尾ピリオドが付くケース対策

    # 企業名の正規化（小文字化、スペース除去）
    company = company.lower().replace(' ', '')

    # 全公式ドメインを収集して正規化
    official_domains = []
    for domains in companies_dict.values():
        official_domains.extend([od.lower().rstrip('.') for od in domains])

    # 企業名を含むドメインのパターン
    company_patterns = [
        company,                    # 完全一致
        company.replace('+', ''),   # '+'を除去
        company.replace('-', ''),   # '-'を除去
        company.replace('.', ''),   # '.'を除去
    ]

    # 判定ロジック
    for official_domain in official_domains:
        # ① 完全一致
        if domain == official_domain:
            return "official"

        # ② サブドメイン判定
        if domain.endswith("." + official_domain):
            # サブドメインの部分を取得
            subdomain = domain[:-len(official_domain)-1]

            # 一般的なサブドメインを許可
            allowed_subdomains = [
                'www', 'blog', 'docs', 'help', 'support', 'developer',
                'developers', 'api', 'status', 'community', 'forum',
                'news', 'media', 'press', 'about', 'jobs', 'careers'
            ]

            # 許可されたサブドメインまたは企業名を含む場合は公式と判定
            if subdomain in allowed_subdomains or any(pattern in subdomain for pattern in company_patterns):
                return "official"

            # その他のサブドメインは非公式と判定
            return "unofficial"

    # ③ 企業名を含むドメインの判定
    if any(pattern in domain for pattern in company_patterns):
        # 企業名を含むが、公式ドメインリストにない場合は非公式と判定
        return "unofficial"

    # ④ その他のドメインは非公式と判定
    return "unofficial"
