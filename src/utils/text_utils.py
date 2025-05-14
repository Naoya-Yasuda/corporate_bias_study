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

def is_negative(url, title="", snippet=""):
    '''
    ネガティブコンテンツかどうかを簡易判定

    Parameters:
    -----------
    url : str
        対象URL
    title : str, optional
        タイトル
    snippet : str, optional
        スニペット

    Returns:
    --------
    bool
        ネガティブコンテンツの場合True
    '''
    negative_keywords = [
        "lawsuit", "scam", "problem", "issue", "reddit", "complaint",
        "negative", "review", "bad", "worst", "fail", "down", "outage",
        "trouble", "vs", "versus", "alternative", "risk", "danger",
        "問題", "障害", "失敗", "リスク", "欠陥", "批判", "炎上", "トラブル"
    ]

    combined_text = (url + " " + title + " " + snippet).lower()
    return any(keyword in combined_text for keyword in negative_keywords)

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