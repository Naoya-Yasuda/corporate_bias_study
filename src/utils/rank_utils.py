#!/usr/bin/env python
# coding: utf-8

'''
ランキング操作のユーティリティ関数

ランキングの比較や計算に関する共通機能を提供します
'''

import math
import numpy as np
from scipy.stats import kendalltau

def rbo(s1, s2, p=0.9):
    '''
    Rank-Biased Overlap (RBO) スコアを計算

    Parameters:
    -----------
    s1, s2 : list
        比較する2つのランキングリスト
    p : float
        減衰パラメータ (0 < p < 1)

    Returns:
    --------
    float
        RBO スコア (0～1)。1に近いほど類似。
    '''
    if not s1 or not s2:
        return 0.0

    # 集合として扱うため、重複を排除
    s1 = [x for i, x in enumerate(s1) if x not in s1[:i]]
    s2 = [x for i, x in enumerate(s2) if x not in s2[:i]]

    # 最小限のオーバーラップ深さを計算
    depth = min(len(s1), len(s2))

    # 各深さでのオーバーラップを計算
    rbo_score = 0.0

    for d in range(1, depth + 1):
        # d番目までの要素の集合
        set1 = set(s1[:d])
        set2 = set(s2[:d])

        # オーバーラップの大きさ
        overlap = len(set1.intersection(set2))

        # 深さdでのRBO項を計算
        rbo_score += p**(d-1) * (overlap / d)

    # 重みの正規化
    rbo_score = rbo_score * (1 - p)

    return rbo_score

def rank_map(dom_list):
    '''
    リストから順位マップを作成

    Parameters:
    -----------
    dom_list : list
        順位付けするリスト

    Returns:
    --------
    dict
        アイテム→順位のマップ
    '''
    m = {}
    for idx, d in enumerate(dom_list, 1):
        if d not in m:
            m[d] = idx
    return m

def compute_tau(ranking1, ranking2):
    '''
    Kendallのタウ係数を計算

    Parameters:
    -----------
    ranking1, ranking2 : list
        比較する2つのランキングリスト

    Returns:
    --------
    float
        タウ係数
    '''
    # 共通のアイテムのみで計算
    common_items = list(set(ranking1).intersection(set(ranking2)))

    if len(common_items) >= 2:
        # 順位のマッピングを作成
        ranks1 = {item: idx for idx, item in enumerate(ranking1)}
        ranks2 = {item: idx for idx, item in enumerate(ranking2)}

        # 共通アイテムの順位のみを抽出
        common_ranks1 = [ranks1[item] for item in common_items]
        common_ranks2 = [ranks2[item] for item in common_items]

        # Kendallのタウ係数を計算
        tau, _ = kendalltau(common_ranks1, common_ranks2)
        if np.isnan(tau):
            tau = 0.0
    else:
        tau = 0.0

    return tau

def compute_delta_ranks(ranking1, ranking2):
    '''
    2つのランキング間の順位差（ΔRank）を計算

    Parameters:
    -----------
    ranking1, ranking2 : list
        比較する2つのランキングリスト

    Returns:
    --------
    dict
        アイテム→順位差のマップ
    '''
    # 順位マップを作成
    rank1 = rank_map(ranking1)
    rank2 = rank_map(ranking2)

    # すべてのアイテムの集合を取得
    all_items = set(rank1.keys()) | set(rank2.keys())

    # 各アイテムの順位差を計算
    delta_rank = {}
    for item in all_items:
        r1 = rank1.get(item, math.inf)
        r2 = rank2.get(item, math.inf)

        # 両方のランキングに存在する場合のみ差を計算
        if r1 != math.inf and r2 != math.inf:
            delta_rank[item] = r2 - r1
        else:
            delta_rank[item] = np.nan

    return delta_rank