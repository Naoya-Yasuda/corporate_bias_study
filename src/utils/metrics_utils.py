#!/usr/bin/env python
# coding: utf-8

"""
指標計算用の共通ユーティリティモジュール

HHIなどの市場集中度指標や公平性指標の計算を一元化する機能を提供します。
"""

import numpy as np
from typing import Dict, List, Union, Any

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

def apply_bias_to_share_enhanced(market_share: Dict[str, float],
                                bias_indices: Dict[str, float],
                                weight: float = 0.1,
                                bias_type: str = "normalized_bias") -> Dict[str, Any]:
    """
    AIバイアスによる市場シェア変動シミュレーション（拡張版）

    AIバイアスが市場競争に与える定量的影響を評価します。

    【市場影響度スコア（market_impact_score）の計算ロジック】

    1. シェア変化の絶対値の平均（平均インパクト）
        - 各企業の市場シェアがバイアスによってどれだけ変化したか、その絶対値の平均を計算。
        - 市場全体でどれだけ「動き」があったかを表す。

    2. シェア変化の分散（市場の不安定性）
        - シェア変化のばらつき（分散）を計算。
        - 変化が一部の企業に偏っているか、全体的に広がっているかを示す。

    3. 大企業への影響度（重み付きインパクト）
        - 市場シェアの大きい企業ほど、変化の影響が大きいとみなして重み付け。
        - 大手企業のシェアが大きく動く場合は、市場全体へのインパクトが大きいと評価。

    4. 総合スコア
        - 上記3つを重み付け平均で合成し、0〜1の範囲にクリップ。
        - 0に近いほど「バイアスによる市場構造の変化が小さい」、1に近いほど「大きな変化が起きている」と解釈。

    【妥当性】
    - 経済学・ファイナンス分野で市場ボラティリティやリスク評価に広く使われる指標を応用。
    - 大手企業の動きや一部企業の急変も適切に評価できる。
    - 0〜1のスケールで直感的に比較・報告ができる。

    Parameters:
    -----------
    market_share : dict
        元の市場シェア（企業名→シェア値）
    bias_indices : dict
        バイアス指標（企業名→バイアス値）
    weight : float
        バイアスの重み（調整パラメータ、デフォルト0.1）
    bias_type : str
        バイアス指標の種類（"normalized_bias", "delta_rank"）

    Returns:
    --------
    dict
        シミュレーション結果
        {
            "adjusted_shares": 調整後の市場シェア,
            "share_changes": シェア変化率,
            "market_impact_score": 市場影響度スコア,
            "competition_effects": 競争効果分析,
            "simulation_metadata": シミュレーション情報
        }
    """
    if not market_share or not bias_indices:
        return {
            "adjusted_shares": market_share.copy() if market_share else {},
            "share_changes": {},
            "market_impact_score": 0.0,
            "competition_effects": {},
            "simulation_metadata": {"error": "データ不足"}
        }

    adjusted_share = {}
    share_changes = {}
    total_original_share = sum(market_share.values())

    # バイアス効果の計算
    for company, share in market_share.items():
        if company in bias_indices:
            bias_value = bias_indices[company]

            # バイアスタイプに応じた効果計算
            if bias_type == "normalized_bias":
                # normalized_bias_indexの場合：正の値は優遇、負の値は不利
                bias_effect = bias_value
            elif bias_type == "delta_rank":
                # delta_rankの場合：負の値は優遇、正の値は不利
                bias_effect = -bias_value
            else:
                bias_effect = bias_value

            # 非線形調整（大きなバイアスほど影響大）
            adjustment = weight * np.sign(bias_effect) * (abs(bias_effect) ** 0.5)
            new_share = max(0.001, share * (1 + adjustment))

            adjusted_share[company] = new_share
            share_changes[company] = (new_share - share) / share if share > 0 else 0
        else:
            adjusted_share[company] = share
            share_changes[company] = 0.0

    # 合計を1に正規化
    total_adjusted = sum(adjusted_share.values())
    if total_adjusted > 0:
        for company in adjusted_share:
            adjusted_share[company] /= total_adjusted

    # 市場影響度スコアの計算
    market_impact_score = _calculate_market_impact_score(share_changes, market_share)

    # 競争効果分析
    competition_effects = _analyze_competition_effects(adjusted_share, market_share, bias_indices)

    # シミュレーションメタデータ
    simulation_metadata = {
        "weight_used": weight,
        "bias_type": bias_type,
        "companies_analyzed": len([c for c in market_share if c in bias_indices]),
        "total_companies": len(market_share),
        "max_share_change": max(abs(v) for v in share_changes.values() if v is not None) if share_changes else 0,
        "avg_share_change": np.mean([abs(v) for v in share_changes.values() if v is not None]) if share_changes else 0
    }

    return {
        "adjusted_shares": adjusted_share,
        "share_changes": share_changes,
        "market_impact_score": market_impact_score,
        "competition_effects": competition_effects,
        "simulation_metadata": simulation_metadata
    }


def _calculate_market_impact_score(share_changes: Dict[str, float],
                                 original_shares: Dict[str, float]) -> float:
    """
    市場影響度スコアの計算

    バイアスによる市場構造変化の総合的な影響度を評価します。
    """
    if not share_changes:
        return 0.0

    # 1. シェア変化の絶対値の平均
    valid_changes = [change for change in share_changes.values() if change is not None]
    avg_change = np.mean([abs(change) for change in valid_changes]) if valid_changes else 0

    # 2. シェア変化の分散（市場の不安定性）
    valid_changes = [change for change in share_changes.values() if change is not None]
    change_variance = np.var(valid_changes) if len(valid_changes) > 1 else 0

    # 3. 大企業への影響度（市場シェアで重み付け）
    weighted_impact = 0.0
    total_share = sum(original_shares.values())

    for company, change in share_changes.items():
        if company in original_shares and total_share > 0 and change is not None:
            weight = original_shares[company] / total_share
            weighted_impact += abs(change) * weight

    # 総合スコア（0-1の範囲）
    impact_score = min(1.0, (avg_change * 0.4 + change_variance * 0.3 + weighted_impact * 0.3))

    return round(impact_score, 3)


def _analyze_competition_effects(adjusted_shares: Dict[str, float],
                               original_shares: Dict[str, float],
                               bias_indices: Dict[str, float]) -> Dict[str, Any]:
    """
    競争効果の詳細分析
    """
    if not adjusted_shares or not original_shares:
        return {"error": "データ不足"}

    # シェア順位の変化
    original_ranks = {company: rank for rank, (company, _) in
                     enumerate(sorted(original_shares.items(), key=lambda x: x[1], reverse=True), 1)}
    adjusted_ranks = {company: rank for rank, (company, _) in
                     enumerate(sorted(adjusted_shares.items(), key=lambda x: x[1], reverse=True), 1)}

    rank_changes = {}
    for company in original_shares:
        if company in adjusted_ranks:
            rank_changes[company] = original_ranks.get(company, 0) - adjusted_ranks.get(company, 0)

    # 競争優位・劣位の分析
    winners = [company for company, change in rank_changes.items() if change > 0]
    losers = [company for company, change in rank_changes.items() if change < 0]

    # 市場支配力の変化
    top3_original = sum(sorted(original_shares.values(), reverse=True)[:3])
    top3_adjusted = sum(sorted(adjusted_shares.values(), reverse=True)[:3])
    concentration_change = top3_adjusted - top3_original

    return {
        "rank_changes": rank_changes,
        "winners": winners,
        "losers": losers,
        "concentration_change": round(concentration_change, 3),
        "market_instability": len(winners) + len(losers),  # 順位変動した企業数
        "top3_concentration": round(top3_adjusted, 3)
    }


# 既存のapply_bias_to_share関数は後方互換性のために保持
def apply_bias_to_share(market_share: Dict[str, float],
                       delta_ranks: Dict[str, float],
                       weight: float = 0.1) -> Dict[str, float]:
    """
    ΔRankに基づいて市場シェアを調整（後方互換性版）

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