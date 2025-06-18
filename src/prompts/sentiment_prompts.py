#!/usr/bin/env python
# coding: utf-8

"""
Perplexity APIのプロンプトテンプレート
"""
import re
from .prompt_manager import PromptManager

# プロンプトマネージャーのインスタンスを作成
prompt_manager = PromptManager()

def get_masked_prompt(subcategory):
    """マスクありプロンプトを生成"""
    return prompt_manager.get_sentiment_prompt(subcategory, masked=True)

def get_unmasked_prompt(subcategory, competitor):
    """マスクなしプロンプトを生成"""
    return prompt_manager.get_sentiment_prompt(subcategory, masked=False, competitor=competitor)

# 評価値抽出用の正規表現パターン
SCORE_PATTERN = prompt_manager.get_score_pattern()

def extract_score(text):
    """テキストから評価値を抽出する関数"""
    if not text:
        return None

    # 主な抽出パターンを試す
    match = re.search(SCORE_PATTERN, text, re.IGNORECASE)
    if match:
        return float(match.group(2))

    # シンプルなパターンを試す (数字のみで回答されている場合)
    if text.strip().isdigit() and 1 <= int(text.strip()) <= 5:
        return float(text.strip())

    # 数字で始まるかチェック
    simple_match = re.match(r'^[\s]*([1-5](\.\d+)?)[\s.]*$', text.strip())
    if simple_match and 1 <= float(simple_match.group(1)) <= 5:
        return float(simple_match.group(1))

    # 「N」形式の回答
    n_pattern = re.search(r'[\s「]*([1-5])[\s」.]*$', text.strip())
    if n_pattern:
        return float(n_pattern.group(1))

    # 「感情スコアは N です」パターン
    is_pattern = re.search(r'は[\s]*([1-5])[\s]*(です|である|だ|になります)', text.strip())
    if is_pattern:
        return float(is_pattern.group(1))

    # 最後の手段：テキストから数値を抽出して1-5の範囲にあるものを探す
    all_numbers = re.findall(r'(\d+(\.\d+)?)', text)
    valid_scores = [float(num[0]) for num in all_numbers if 1 <= float(num[0]) <= 5]
    if valid_scores:
        return valid_scores[0]  # 最初に見つかった有効なスコアを返す

    return None