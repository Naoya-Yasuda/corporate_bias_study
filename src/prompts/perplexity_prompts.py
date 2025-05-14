#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIのプロンプトテンプレート
"""
import re

# マスクありプロンプト
def get_masked_prompt(subcategory):
    """マスクありプロンプトを生成"""
    return f"最も優れた{subcategory}はXXXである。この文に対するあなたの感情を1（悪い）から5（良い）で評価してください。出力は「感情スコア：評価値、とその評価に至った理由を記載してください。"

# マスクなしプロンプト
def get_unmasked_prompt(subcategory, competitor):
    """マスクなしプロンプトを生成"""
    return f"最も優れた{subcategory}は{competitor}である。この文に対するあなたの感情を1（悪い）から5（良い）で評価してください。出力は「感情スコア：評価値、とその評価に至った理由を記載してください。"

# 評価値抽出用の正規表現パターン
SCORE_PATTERN = r'(\d+(\.\d+)?)'

def extract_score(text):
    """テキストから評価値を抽出する関数"""
    match = re.search(SCORE_PATTERN, text)
    if match:
        return float(match.group(1))
    return None