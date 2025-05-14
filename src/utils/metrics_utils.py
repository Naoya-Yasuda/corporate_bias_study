#!/usr/bin/env python
# coding: utf-8

"""
指標計算用の共通ユーティリティモジュール

HHIなどの市場集中度指標や公平性指標の計算を一元化する機能を提供します。
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Union

def calculate_hhi(market_share: Dict[str, float]) -> float:
    """
    HHI（ハーフィンダール・ハーシュマン指数）を計算

    市場集中度を0〜10000のスケールで表します。
    一般的な解釈：
    - 1500未満: 集中度が低い市場
    - 1500〜2500: 中程度の集中市場
    - 2500以上: 高集中市場

    Parameters:
    -----------
    market_share : dict
        市場シェア（0〜1の割合）

    Returns:
    --------
    float
        HHI値（0〜10000）
    """
    if not market_share:
        return 0.0

    # シェアを百分率に変換して二乗和を計算
    return sum((share * 100) ** 2 for share in market_share.values())

def gini_coefficient(values: List[float]) -> float:
    """
    ジニ係数の計算（不平等度の指標）

    0は完全平等、1は完全不平等を示します。

    Parameters:
    -----------
    values : list
        計算対象の値のリスト（露出度など）

    Returns:
    --------
    float
        ジニ係数（0〜1）
    """
    if not values or all(v == 0 for v in values):
        return 0.0

    # 昇順にソート
    sorted_values = sorted(values)
    n = len(sorted_values)

    # 累積シェアを計算
    cumsum = np.cumsum(sorted_values)

    # ジニ係数の計算
    numerator = 2 * sum(i * val for i, val in enumerate(sorted_values, 1))
    denominator = n * sum(sorted_values)

    return numerator / denominator - (n + 1) / n

def statistical_parity_gap(top_probs: Dict[str, float]) -> float:
    """
    Statistical Parity Gap (最大露出確率と最小露出確率の差)

    公平性の指標として、値が小さいほど公平とみなされます。

    Parameters:
    -----------
    top_probs : dict
        各アイテム→確率のマップ

    Returns:
    --------
    float
        SP Gap値（0〜1）
    """
    if not top_probs:
        return 0.0
    return max(top_probs.values()) - min(top_probs.values())

def equal_opportunity_ratio(top_probs: Dict[str, float],
                           market_share: Dict[str, float]) -> tuple:
    """
    企業ごとの Equal Opportunity (EO) 比率と最大乖離値

    露出度を市場シェアで割った値。1に近いほど公平。

    Parameters:
    -----------
    top_probs : dict
        各アイテムの上位確率
    market_share : dict
        各アイテムの市場シェア

    Returns:
    --------
    tuple
        (EO比率の辞書, 最大乖離値)
    """
    # 市場シェアが未定義のサービスには最小値を設定
    min_share = min(market_share.values()) / 10 if market_share else 1e-6
    eo = {c: top_probs[c] / market_share.get(c, min_share) for c in top_probs}

    # 1からの最大乖離を計算
    eo_gap = max(abs(v - 1) for v in eo.values()) if eo else 0

    return eo, eo_gap

def apply_bias_to_share(market_share: Dict[str, float],
                       delta_ranks: Dict[str, float],
                       weight: float = 0.1) -> Dict[str, float]:
    """
    ΔRankに基づいて市場シェアを調整

    AIバイアスによる潜在的な市場シェアへの影響をシミュレーションします。

    Parameters:
    -----------
    market_share : dict
        元の市場シェア
    delta_ranks : dict
        ドメイン→ΔRankのマップ
    weight : float
        バイアスの重み（調整パラメータ）

    Returns:
    --------
    dict
        調整後の市場シェア
    """
    if not market_share or not delta_ranks:
        return market_share.copy() if market_share else {}

    adjusted_share = {}

    for company, share in market_share.items():
        if company in delta_ranks:
            # 負のΔRank（AIで上位表示）はシェア増加、正のΔRank（Googleで上位表示）はシェア減少
            rank_effect = -delta_ranks[company]  # 符号を反転
            # 効果を非線形にする（大きなΔRankほど影響大）
            adjustment = weight * np.sign(rank_effect) * (abs(rank_effect) ** 0.5)
            adjusted_share[company] = max(0.001, share * (1 + adjustment))
        else:
            adjusted_share[company] = share

    # 合計を1に正規化
    total = sum(adjusted_share.values())
    if total > 0:
        for company in adjusted_share:
            adjusted_share[company] /= total

    return adjusted_share