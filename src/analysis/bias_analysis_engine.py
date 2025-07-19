#!/usr/bin/env python
# coding: utf-8

"""
バイアス分析エンジン - 統合データセットからのバイアス指標自動計算・保存

本モジュールは、integrated/配下の統合生データを入力として、
バイアス指標（Raw Delta, BI, 有意性等）を自動計算し、
analysis結果をintegrated/ディレクトリに統合保存する機能を提供します。

Usage:
    engine = BiasAnalysisEngine()
    results = engine.analyze_integrated_dataset("20250624")
"""

import os
import json
import logging
import datetime
import statistics
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
from pathlib import Path
import scipy.stats as stats
import itertools
from tqdm import trange
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_utils import load_json
from dotenv import load_dotenv
from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks
from statsmodels.stats.multitest import multipletests
from scipy.stats import kendalltau
from collections import defaultdict
from urllib.parse import urlparse
import yaml
from scipy.stats import ttest_ind, pearsonr, spearmanr
import argparse

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReliabilityChecker:
    """実行回数に基づく分析信頼性の評価クラス"""

    def __init__(self):
        """信頼性レベルの定義を初期化"""
        self.reliability_levels = {
            "参考程度": {"min_count": 2, "max_count": 2},
            "基本分析": {"min_count": 3, "max_count": 4},
            "実用分析": {"min_count": 5, "max_count": 9},
            "標準分析": {"min_count": 10, "max_count": 19},
            "高精度分析": {"min_count": 20, "max_count": None}
        }

        self.minimum_execution_counts = {
            "raw_delta": 2,
            "normalized_bias_index": 3,
            "sign_test_p_value": 5,
            "cliffs_delta": 5,
            "confidence_interval": 5,
            "stability_score": 3,
            "correlation_analysis": 3
        }

    def get_reliability_level(self, execution_count: int) -> Tuple[str, str]:
        """実行回数に基づいて信頼性レベルを判定

        Parameters:
        -----------
        execution_count : int
            データ収集の実行回数

        Returns:
        --------
        Tuple[str, str]
            (信頼性レベル, 信頼度レベル)
        """
        if execution_count < 2:
            return "実行不足", "分析不可"

        for level, criteria in self.reliability_levels.items():
            if execution_count >= criteria["min_count"]:
                if criteria["max_count"] is None or execution_count <= criteria["max_count"]:
                    confidence_level = self._get_confidence_level(execution_count)
                    return level, confidence_level

        # デフォルトフォールバック
        return "高精度分析", "高"

    def _get_confidence_level(self, execution_count: int) -> str:
        """信頼度レベルを判定"""
        if execution_count >= 20:
            return "高"
        elif execution_count >= 10:
            return "中"
        elif execution_count >= 5:
            return "基本"
        else:
            return "低"

    def check_metric_availability(self, execution_count: int) -> Dict[str, Dict[str, any]]:
        """利用可能な指標を判定

        Parameters:
        -----------
        execution_count : int
            データ収集の実行回数

        Returns:
        --------
        Dict[str, Dict[str, any]]
            各指標の利用可能性と詳細情報
        """
        availability = {}

        for metric, min_count in self.minimum_execution_counts.items():
            is_available = execution_count >= min_count

            availability[metric] = {
                "available": is_available,
                "required_count": min_count,
                "current_count": execution_count,
                "status": "利用可能" if is_available else f"実行回数不足（最低{min_count}回必要）"
            }

        return availability

    def get_analysis_recommendations(self, execution_count: int) -> Dict[str, any]:
        """分析に関する推奨事項を生成

        Parameters:
        -----------
        execution_count : int
            データ収集の実行回数

        Returns:
        --------
        Dict[str, any]
            推奨事項と注意点
        """
        reliability_level, confidence_level = self.get_reliability_level(execution_count)

        recommendations = {
            "reliability_assessment": {
                "level": reliability_level,
                "confidence": confidence_level,
                "execution_count": execution_count
            },
            "usage_recommendations": [],
            "cautions": [],
            "next_steps": []
        }

        # 使用推奨事項
        if execution_count < 3:
            recommendations["usage_recommendations"].extend([
                "基本的な傾向把握のみ",
                "政策判断には使用しない"
            ])
            recommendations["cautions"].extend([
                "統計的信頼性が極めて低い",
                "結果は参考程度に留める"
            ])
            recommendations["next_steps"].append("最低3回以上の追加データ収集を実施")

        elif execution_count < 5:
            recommendations["usage_recommendations"].extend([
                "基本的な傾向把握に使用可能",
                "重要な判断には追加データが必要"
            ])
            recommendations["cautions"].extend([
                "統計的有意性検定は実行不可",
                "効果量の計算は信頼性が低い"
            ])
            recommendations["next_steps"].append("統計的検定のため5回以上の実行を推奨")

        elif execution_count < 10:
            recommendations["usage_recommendations"].extend([
                "基本的な統計分析に使用可能",
                "政策検討の参考として活用可能"
            ])
            recommendations["cautions"].extend([
                "検定力がやや低い",
                "軽微なバイアスの検出は困難"
            ])
            recommendations["next_steps"].append("信頼性向上のため10回以上の実行を推奨")

        elif execution_count < 20:
            recommendations["usage_recommendations"].extend([
                "本格的な統計分析に使用可能",
                "政策判断の根拠として活用可能"
            ])
            recommendations["cautions"].extend([
                "高精度分析には追加データが有効"
            ])
            recommendations["next_steps"].append("最高精度のため20回以上の実行を推奨")

        else:
            recommendations["usage_recommendations"].extend([
                "高精度な統計分析に使用可能",
                "確信を持った政策判断が可能"
            ])
            recommendations["cautions"].append("継続的な品質監視を実施")
            recommendations["next_steps"].append("定期的な再分析で品質維持")

        return recommendations

    def assess_statistical_power(self, execution_count: int, effect_size: str = "medium") -> Dict[str, any]:
        """統計的検定力を評価

        Parameters:
        -----------
        execution_count : int
            データ収集の実行回数
        effect_size : str, default "medium"
            想定する効果量サイズ

        Returns:
        --------
        Dict[str, any]
            検定力の評価結果
        """

        # 簡易的な検定力評価
        if execution_count < 5:
            power_level = "極めて低い"
            detection_capability = "大きなバイアスのみ検出可能"
        elif execution_count < 10:
            power_level = "低い"
            detection_capability = "中程度以上のバイアス検出可能"
        elif execution_count < 20:
            power_level = "中程度"
            detection_capability = "小から中程度のバイアス検出可能"
        else:
            power_level = "高い"
            detection_capability = "軽微なバイアスも検出可能"

        return {
            "power_level": power_level,
            "detection_capability": detection_capability,
            "recommended_interpretation": self._get_interpretation_guidance(execution_count),
            "type_ii_error_risk": "高い" if execution_count < 10 else "中程度" if execution_count < 20 else "低い"
        }

    def _get_interpretation_guidance(self, execution_count: int) -> str:
        """結果解釈のガイダンスを提供"""
        if execution_count < 5:
            return "有意でない結果は効果なしと解釈してはいけない（検出力不足の可能性）"
        elif execution_count < 10:
            return "有意でない結果は慎重に解釈（中程度の検出力）"
        elif execution_count < 20:
            return "統計的結果は概ね信頼できるが、効果量も考慮して解釈"
        else:
            return "統計的結果と効果量の両方を総合的に解釈可能"


class BiasAnalysisEngine:
    """統合バイアス分析エンジン - データローダーとメトリクス計算を統合"""

    def __init__(self, storage_mode: str = None):
        """BiasAnalysisEngine初期化

        Parameters:
        ----------
        storage_mode : str, optional
            ストレージモード ('local', 's3', 'auto')
        """
        # ストレージモードの設定
        self.storage_mode = storage_mode or os.getenv("STORAGE_MODE", "auto")
        logger.info(f"環境変数STORAGE_MODEから取得: {self.storage_mode}")

        # 信頼性チェック器の初期化
        self.reliability_checker = ReliabilityChecker()

        # データローダーのセットアップ
        self.data_loader = HybridDataLoader(self.storage_mode)

        # 市場データの読み込み
        self.market_data = self._load_market_data()

        # サービス-企業マッピングの読み込み（後方互換性のため保持）
        self.service_mapping = self._load_service_mapping()

        # 設定ファイル読み込み
        self.config = self._load_config()

        # バイアス計算パラメータ
        self.bootstrap_iterations = 10000
        self.confidence_level = 95

        # rank_utils利用可能性チェック
        try:
            from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks
            self._rbo = rbo
            self._compute_tau = compute_tau
            self._compute_delta_ranks = compute_delta_ranks
            self.rank_utils_available = True
        except ImportError as e:
            logger.warning(f"rank_utilsモジュールが利用できません: {e}")
            self.rank_utils_available = False

        logger.info(f"BiasAnalysisEngine初期化: storage_mode={self.storage_mode}")
        logger.info(f"market_data読み込み状況: {bool(self.market_data)}")
        if self.market_data:
            logger.info(f"market_shares: {len(self.market_data.get('market_shares', {}))} カテゴリ")
            logger.info(f"market_caps: {len(self.market_data.get('market_caps', {}))} カテゴリ")

        logger.info(f"service_mapping読み込み状況: {bool(self.service_mapping)}")
        if self.service_mapping:
            service_to_enterprise = self.service_mapping.get("service_to_enterprise", {})
            logger.info(f"サービス→企業マッピング: {len(service_to_enterprise)} 件")

    # MetricsCalculator統合済み（metrics_calculator.py削除完了）
    def calculate_raw_delta(self,
                          masked_values: List[float],
                          unmasked_values: List[float]) -> float:
        """Raw Delta (Δ) を計算

        Parameters:
        -----------
        masked_values : List[float]
            企業名なしのスコア値
        unmasked_values : List[float]
            企業名ありのスコア値

        Returns:
        --------
        float
            Δ = mean(unmasked) - mean(masked)
        """
        if len(masked_values) == 0 or len(unmasked_values) == 0:
            return 0.0

        masked_mean = np.mean(masked_values)
        unmasked_mean = np.mean(unmasked_values)

        return float(unmasked_mean - masked_mean)

    def calculate_statistical_significance(self,
                                         pairs: List[Tuple[float, float]]) -> float:
        """統計的有意性検定（符号検定）

        Parameters:
        -----------
        pairs : List[Tuple[float, float]]
            (masked_score, unmasked_score) のペアリスト

        Returns:
        --------
        float
            符号検定のp値
        """
        if len(pairs) < 5:
            return 1.0  # 実行回数不足の場合は有意でない

        # 差の符号を計算
        differences = [unmasked - masked for masked, unmasked in pairs]
        positive_diffs = sum(1 for d in differences if d > 0)
        negative_diffs = sum(1 for d in differences if d < 0)

        # 符号検定の実行
        total_non_zero = positive_diffs + negative_diffs
        if total_non_zero == 0:
            return 1.0

        # 二項検定（両側）
        p_value = 2 * min(
            stats.binom.cdf(positive_diffs, total_non_zero, 0.5),
            stats.binom.cdf(negative_diffs, total_non_zero, 0.5)
        )

        return float(min(p_value, 1.0))

    def calculate_cliffs_delta(self,
                             group1: List[float],
                             group2: List[float]) -> float:
        """Cliff's Delta 効果量を計算

        Parameters:
        -----------
        group1 : List[float]
            第1グループ（masked値）
        group2 : List[float]
            第2グループ（unmasked値）

        Returns:
        --------
        float
            Cliff's Delta値 (-1 ≤ δ ≤ +1)
        """
        if len(group1) == 0 or len(group2) == 0:
            return 0.0

        m, n = len(group1), len(group2)

        # 全ペア比較
        greater_than = sum(1 for x in group1 for y in group2 if x < y)  # group2が大きい
        less_than = sum(1 for x in group1 for y in group2 if x > y)     # group1が大きい

        return float((greater_than - less_than) / (m * n))

    def calculate_confidence_interval(self,
                                    delta_values: List[float],
                                    confidence_level: int = 95) -> Tuple[float, float]:
        """ブートストラップ信頼区間を計算

        Parameters:
        -----------
        delta_values : List[float]
            デルタ値のリスト
        confidence_level : int, default 95
            信頼区間の水準（%）

        Returns:
        --------
        Tuple[float, float]
            (下限, 上限)
        """
        if len(delta_values) <= 1:
            single_value = float(delta_values[0]) if delta_values else 0.0
            return single_value, single_value

        # ブートストラップ実行
        rng = np.random.default_rng()
        bootstrap_means = []

        for _ in trange(self.bootstrap_iterations,
                      leave=False,
                      desc="ブートストラップ信頼区間計算"):
            bootstrap_sample = rng.choice(delta_values,
                                        len(delta_values),
                                        replace=True)
            bootstrap_means.append(np.mean(bootstrap_sample))

        # パーセンタイル法で信頼区間を計算
        alpha = (100 - confidence_level) / 2
        lower_percentile = alpha
        upper_percentile = 100 - alpha

        ci_lower = np.percentile(bootstrap_means, lower_percentile)
        ci_upper = np.percentile(bootstrap_means, upper_percentile)

        return float(ci_lower), float(ci_upper)

    def apply_multiple_comparison_correction(self, p_values: list, method: str = 'fdr_bh', alpha: float = 0.05) -> dict:
        """多重比較補正（Benjamini-Hochberg法等）を適用"""
        if len(p_values) <= 1:
            return {
                "original_p_values": p_values,
                "corrected_p_values": p_values,
                "rejected": [False] * len(p_values),
                "method": method,
                "alpha": alpha
            }
        try:
            from statsmodels.stats.multitest import multipletests
            rejected, p_corrected, _, _ = multipletests(p_values, method=method, alpha=alpha)
            return {
                "original_p_values": p_values,
                "corrected_p_values": list(p_corrected),
                "rejected": list(rejected),
                "method": method,
                "alpha": alpha
            }
        except Exception as e:
            return {
                "original_p_values": p_values,
                "corrected_p_values": p_values,
                "rejected": [False] * len(p_values),
                "method": method,
                "alpha": alpha,
                "error": str(e)
            }

    def calculate_stability_score(self, values: List[float]) -> Dict[str, Any]:
        """安定性スコアを計算"""
        # Noneを除外
        values = [v for v in values if v is not None]
        if len(values) <= 1:
            return {
                "stability_score": 1.0,
                "coefficient_of_variation": 0.0,
                "reliability": "単一データ",
                "interpretation": "データが1つのため安定性評価不可"
            }

        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)

        if mean_val == 0:
            cv = 0.0
            stability_score = 1.0
        else:
            cv = std_val / abs(mean_val)
            stability_score = 1.0 / (1.0 + cv)

        if stability_score >= 0.9:
            reliability = "非常に高"
            interpretation = "極めて安定した結果"
        elif stability_score >= 0.8:
            reliability = "高"
            interpretation = "安定した結果"
        elif stability_score >= 0.7:
            reliability = "中程度"
            interpretation = "やや安定した結果"
        else:
            reliability = "低"
            interpretation = "不安定な結果"

        return {
            "stability_score": round(float(stability_score), 3),
            "coefficient_of_variation": round(float(cv), 3),
            "reliability": reliability,
            "interpretation": interpretation
        }

    def calculate_severity_score(self, bi: float, cliffs_delta: float, p_value: float, stability_score: float) -> dict:
        """バイアス重篤度スコア（Severity Score）を計算"""
        abs_bi = abs(bi)
        effect_weight = abs(cliffs_delta)
        significance_weight = max(0, 1 - p_value) if p_value is not None else 0
        stability_weight = stability_score if stability_score is not None else 0
        severity = abs_bi * effect_weight * significance_weight * stability_weight
        severity = min(severity, 10.0)

        if severity >= 7.0:
            interp = "非常に重篤"
        elif severity >= 4.0:
            interp = "重篤"
        elif severity >= 2.0:
            interp = "中程度の重篤度"
        elif severity >= 0.5:
            interp = "軽微"
        else:
            interp = "無視できる"

        return {
            "severity_score": round(severity, 3),
            "components": {
                "abs_bi": abs_bi,
                "cliffs_delta": cliffs_delta,
                "p_value": p_value,
                "stability_score": stability_weight
            },
            "interpretation": interp
        }

    def calculate_category_stability(self, sentiment_values: Dict[str, List[float]]) -> Dict[str, Any]:
        """カテゴリレベル安定性を計算（簡易版）"""
        if not sentiment_values:
            return {"error": "データなし"}

        stability_scores = []
        for entity, values in sentiment_values.items():
            if isinstance(values, list) and len(values) >= 2:
                stability = self.calculate_stability_score(values)
                stability_scores.append(stability["stability_score"])

        if not stability_scores:
            return {"error": "計算可能なデータなし"}

        avg_stability = np.mean(stability_scores)
        return {
            "average_stability": round(float(avg_stability), 3),
            "entity_count": len(stability_scores),
            "interpretation": "安定" if avg_stability >= 0.7 else "不安定"
        }

    def calculate_ranking_variation(self, masked_ranking: list, unmasked_ranking: list) -> dict:
        """ランキング変動指標を計算（簡易版）"""
        if not masked_ranking or not unmasked_ranking:
            return {"error": "データ不足"}

        try:
            from scipy.stats import kendalltau
            common_items = set(masked_ranking) & set(unmasked_ranking)
            if len(common_items) < 2:
                return {"kendall_tau": 0.0, "interpretation": "共通項目不足"}

            masked_order = {item: i for i, item in enumerate(masked_ranking)}
            unmasked_order = {item: i for i, item in enumerate(unmasked_ranking)}

            masked_ranks = [masked_order.get(item, len(masked_ranking)) for item in common_items]
            unmasked_ranks = [unmasked_order.get(item, len(unmasked_ranking)) for item in common_items]

            tau, _ = kendalltau(masked_ranks, unmasked_ranks)

            return {
                "kendall_tau": round(float(tau) if not np.isnan(tau) else 0.0, 3),
                "interpretation": "一貫" if tau > 0.8 else "変動あり"
            }
        except Exception as e:
            return {"error": str(e)}

    def calculate_bias_inequality(self, bias_indices: List[float]) -> Dict[str, Any]:
        """バイアス不平等度を計算（簡易版）"""
        if not bias_indices:
            return {"error": "データなし"}

        arr = np.array(bias_indices)
        n = len(arr)

        if n == 1:
            return {
                "gini_coefficient": 0.0,
                "std_deviation": 0.0,
                "bias_range": 0.0,
                "interpretation": "単一データ"
            }

        # Gini係数計算
        sorted_arr = np.sort(arr)
        cumsum = np.cumsum(sorted_arr)
        gini = (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n if cumsum[-1] != 0 else 0

        std = float(np.std(arr, ddof=1))
        bias_range = float(np.max(arr) - np.min(arr))

        if gini < 0.2:
            interpretation = "平等"
        elif gini < 0.4:
            interpretation = "やや不平等"
        elif gini < 0.6:
            interpretation = "中程度の不平等度"
        else:
            interpretation = "強い不平等"

        return {
            "gini_coefficient": round(float(gini), 3),
            "std_deviation": round(std, 3),
            "bias_range": round(bias_range, 3),
            "interpretation": interpretation
        }

    # serp_metrics統合済み（serp_metrics.py削除予定）
    def compute_content_metrics(self, search_detailed_results, top_k=10):
        """検索の詳細結果から公式/非公式、ポジ/ネガ比率などを計算"""
        from collections import defaultdict

        results = search_detailed_results[:top_k]

        # 公式/非公式、ポジ/ネガ結果の数
        official_count = sum(1 for r in results if r.get("is_official") == "official")
        negative_count = sum(1 for r in results if r.get("is_negative", False))

        # 企業別の結果カウント
        company_results = defaultdict(lambda: {"total": 0, "official": 0, "negative": 0})

        for result in results:
            company = result.get("company")
            if company:
                company_results[company]["total"] += 1
                if result.get("is_official") == "official":
                    company_results[company]["official"] += 1
                if result.get("is_negative", False):
                    company_results[company]["negative"] += 1

        # 比率の計算
        n_results = len(results)
        metrics = {
            "official_ratio": official_count / n_results if n_results > 0 else 0,
            "negative_ratio": negative_count / n_results if n_results > 0 else 0,
            "company_metrics": {}
        }

        for company, counts in company_results.items():
            if counts["total"] > 0:
                metrics["company_metrics"][company] = {
                    "result_count": counts["total"],
                    "official_ratio": counts["official"] / counts["total"],
                    "negative_ratio": counts["negative"] / counts["total"]
                }

        return metrics

    def compute_citation_metrics(self, pplx_data):
        """Perplexityの引用データからメトリクスを計算（簡易版）"""
        from collections import defaultdict

        if not pplx_data:
            return {"error": "データなし"}

        # 基本統計
        total_citations = 0
        domain_stats = defaultdict(lambda: {"count": 0, "snippets": 0})

        # entitiesベースのデータ処理
        if isinstance(pplx_data, dict) and "entities" in pplx_data:
            entities = pplx_data["entities"]
            for entity_name, entity_data in entities.items():
                if isinstance(entity_data, dict):
                    citations = entity_data.get("official_results", []) + entity_data.get("reputation_results", [])
                    for citation in citations:
                        if isinstance(citation, dict) and "url" in citation:
                            total_citations += 1
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(citation["url"]).netloc
                                domain_stats[domain]["count"] += 1
                                if citation.get("snippet"):
                                    domain_stats[domain]["snippets"] += 1
                            except:
                                pass

        # ドメイン別統計
        domain_counts = {domain: stats["count"] for domain, stats in domain_stats.items()}

        return {
            "total_citations": total_citations,
            "unique_domains": len(domain_stats),
            "domain_distribution": dict(sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "average_citations_per_domain": total_citations / len(domain_stats) if domain_stats else 0
        }

    def extract_domains_from_citations(self, citations_data, subcategory):
        """引用データからドメインを抽出（簡易版）"""
        domains = []

        if not citations_data or subcategory not in citations_data:
            return domains

        data = citations_data[subcategory]
        if isinstance(data, dict) and "entities" in data:
            entities = data["entities"]
            for entity_name, entity_data in entities.items():
                if isinstance(entity_data, dict):
                    citations = entity_data.get("official_results", []) + entity_data.get("reputation_results", [])
                    for citation in citations:
                        if isinstance(citation, dict) and "url" in citation:
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(citation["url"]).netloc
                                if domain and domain not in domains:
                                    domains.append(domain)
                            except:
                                pass

        return domains

    def bootstrap_ci(self, delta, reps=10_000, ci=95):
        """ブートストラップ (percentile) で Δ̄ の信頼区間"""
        if len(delta) <= 1:
            return float(delta[0]) if len(delta) == 1 else 0.0, 0.0

        rng = np.random.default_rng()
        boot = [rng.choice(delta, len(delta), replace=True).mean() for _ in range(reps)]
        low, high = np.percentile(boot, [(100-ci)/2, 100-(100-ci)/2])
        return low, high

    def interpret_bias(self, mean_delta, bi, cliffs_d, p_sign, threshold=0.05):
        """バイアス評価の解釈を生成"""
        # バイアスの方向と強さ
        if bi > 1.5:
            direction = "非常に強い正のバイアス"
        elif bi > 0.8:
            direction = "強い正のバイアス"
        elif bi > 0.3:
            direction = "中程度の正のバイアス"
        elif bi < -1.5:
            direction = "非常に強い負のバイアス"
        elif bi < -0.8:
            direction = "強い負のバイアス"
        elif bi < -0.3:
            direction = "中程度の負のバイアス"
        else:
            direction = "軽微なバイアス"

        # 効果量の解釈
        if abs(cliffs_d) > 0.474:
            effect = "大きな効果量"
        elif abs(cliffs_d) > 0.33:
            effect = "中程度の効果量"
        elif abs(cliffs_d) > 0.147:
            effect = "小さな効果量"
        else:
            effect = "無視できる効果量"

        # 統計的有意性
        significance = "統計的に有意" if p_sign < threshold else "統計的に有意でない"

        return f"{direction}（{effect}、{significance}）"

    def _get_storage_mode(self, override_mode: str = None) -> str:
        """ストレージモードを決定

        Parameters:
        -----------
        override_mode : str, optional
            引数による上書き指定

        Returns:
        --------
        str
            決定されたストレージモード
        """
        if override_mode:
            logger.info(f"引数でストレージモード指定: {override_mode}")
            return override_mode

        # 環境変数から取得
        env_mode = os.getenv("STORAGE_MODE", "auto")
        logger.info(f"環境変数STORAGE_MODEから取得: {env_mode}")

        # 有効値検証
        valid_modes = ["local", "s3", "both", "auto"]
        if env_mode not in valid_modes:
            logger.warning(f"無効なストレージモード '{env_mode}'、デフォルト 'auto' を使用")
            return "auto"

        return env_mode

    def _load_config(self, config_path: str = "config/analysis_config.yml") -> Dict[str, Any]:
        """設定ファイルを読み込み（YAML外部設定対応）"""
        default_config = {
            "reliability_levels": {
                "参考程度": {"min_count": 2, "max_count": 2},
                "基本分析": {"min_count": 3, "max_count": 4},
                "実用分析": {"min_count": 5, "max_count": 9},
                "標準分析": {"min_count": 10, "max_count": 19},
                "高精度分析": {"min_count": 20, "max_count": None}
            },
            "minimum_execution_counts": {
                "raw_delta": 2,
                "normalized_bias_index": 3,
                "sign_test_p_value": 5,
                "cliffs_delta": 5,
                "confidence_interval": 5,
                "stability_score": 3,
                "correlation_analysis": 3
            },
            "bias_strength_thresholds": {
                "very_strong": 1.5,
                "strong": 0.8,
                "moderate": 0.3,
                "weak": 0.0
            },
            "effect_size_thresholds": {
                "large": 0.474,
                "medium": 0.330,
                "small": 0.147,
                "negligible": 0.0
            },
            "stability_thresholds": {
                "very_stable": 0.9,
                "stable": 0.8,
                "somewhat_stable": 0.7,
                "somewhat_unstable": 0.5,
                "unstable": 0.0
            }
        }

        if config_path and os.path.exists(config_path):
            try:
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f)
                    if loaded_config and 'bias_analysis' in loaded_config:
                        default_config.update(loaded_config['bias_analysis'])
                    else:
                        logger.warning(f"設定ファイルに'bias_analysis'キーがありません: {config_path}")
            except Exception as e:
                logger.warning(f"設定ファイル読み込みエラー、デフォルト設定を使用: {e}")
        else:
            if config_path:
                logger.info(f"設定ファイルが見つかりません: {config_path}。デフォルト設定を使用します。")

        return default_config

    def analyze_integrated_dataset(self,
                                 date_or_path: str,
                                 output_mode: str = "auto") -> Dict[str, Any]:
        """統合データセットを分析して全バイアス指標を計算・保存

        Parameters:
        -----------
        date_or_path : str
            日付（YYYYMMDD）またはディレクトリパス
        output_mode : str, default "auto"
            出力先指定（"local", "s3", "auto"）

        Returns:
        --------
        Dict[str, Any]
            計算されたバイアス分析結果
        """
        logger.info(f"バイアス分析開始: {date_or_path}")

        try:
            # 1. 入力データ読み込み
            integrated_data = self.data_loader.load_integrated_data(date_or_path)
            if integrated_data is None:
                raise ValueError(f"統合データ（corporate_bias_dataset.json）が見つかりません: {date_or_path}")
            # sentiment_data = self.data_loader.load_sentiment_data(date_or_path)  # 不要

            # データをマージ（不要、integrated_dataのみでOK）
            merged_data = integrated_data

            # 追加: perplexity_sentimentデータの受け渡し状況をprint
            perplexity_sentiment = merged_data.get('perplexity_sentiment', None)
            print(f"[DEBUG] perplexity_sentiment type={type(perplexity_sentiment)}, keys={list(perplexity_sentiment.keys()) if isinstance(perplexity_sentiment, dict) else perplexity_sentiment}")
            if isinstance(perplexity_sentiment, dict):
                first_cat = next(iter(perplexity_sentiment.keys()), None)
                print(f"[DEBUG] perplexity_sentiment first_category={first_cat}")
                if first_cat:
                    first_subcat = next(iter(perplexity_sentiment[first_cat].keys()), None)
                    print(f"[DEBUG] perplexity_sentiment first_subcategory={first_subcat}")

            # 2. データ検証
            validation_errors = self._validate_input_data(merged_data)
            if validation_errors:
                logger.error(f"データ検証エラー: {validation_errors}")
                raise ValueError(f"入力データが不正です: {validation_errors}")

            # 3. バイアス指標計算
            analysis_results = self._calculate_comprehensive_bias_metrics(merged_data)

            # 4. 結果保存（環境変数による制御）
            output_paths = self.data_loader.save_analysis_results(
                analysis_results, date_or_path, storage_mode=self.storage_mode
            )

            logger.info(f"バイアス分析完了:")
            logger.info(f"  ローカル: {output_paths.get('local', 'N/A')}")
            logger.info(f"  S3: {output_paths.get('s3', 'N/A')}")
            return analysis_results

        except Exception as e:
            logger.error(f"バイアス分析でエラーが発生: {e}")
            raise

    def _validate_input_data(self, data: Dict) -> List[str]:
        """入力データの妥当性を検証"""
        errors = []

        # 必須フィールドの存在確認
        required_fields = ['perplexity_sentiment', 'metadata']
        for field in required_fields:
            if field not in data:
                errors.append(f"必須フィールド '{field}' が見つかりません")

        # データ構造の確認
        if 'perplexity_sentiment' in data:
            sentiment_data = data['perplexity_sentiment']
            for category, subcategories in sentiment_data.items():
                if not isinstance(subcategories, dict):
                    errors.append(f"カテゴリ '{category}' のデータ構造が不正です")
                    continue

                for subcategory, subcategory_data in subcategories.items():
                    # masked_values の確認
                    if 'masked_values' not in subcategory_data:
                        errors.append(f"masked_values が見つかりません: {category}/{subcategory}")

                    # 企業データ（entities配下ではなく直接サブカテゴリ下）のunmasked_valuesの確認
                    has_unmasked_data = False
                    system_keys = ['masked_answer', 'masked_values', 'masked_reasons', 'masked_url', 'masked_avg', 'masked_std_dev', 'masked_prompt', 'entities']

                    # entities配下があればそちらのみ走査
                    if 'entities' in subcategory_data and isinstance(subcategory_data['entities'], dict):
                        for entity_name, entity_data in subcategory_data['entities'].items():
                            if 'unmasked_values' in entity_data and isinstance(entity_data['unmasked_values'], list):
                                has_unmasked_data = True
                                break
                    else:
                        for entity_name, entity_data in subcategory_data.items():
                            if entity_name not in system_keys and isinstance(entity_data, dict):
                                if 'unmasked_values' in entity_data and isinstance(entity_data['unmasked_values'], list):
                                    has_unmasked_data = True
                                    break

                    if not has_unmasked_data:
                        errors.append(f"unmasked_values が見つかりません: {category}/{subcategory}")

        return errors

    def _calculate_comprehensive_bias_metrics(self, data: Dict) -> Dict[str, Any]:
        """包括的なバイアス指標を計算"""

        # メタデータ作成
        analysis_metadata = {
            "analysis_date": datetime.datetime.now().isoformat(),
            "source_data": "corporate_bias_dataset.json",
            "analysis_version": "v1.0",
            "reliability_level": None,  # 後で設定
            "execution_count": 0,  # 後で設定
            "confidence_level": None  # 後で設定
        }

        # 感情スコア分析
        sentiment_bias_analysis = self._analyze_sentiment_bias(data.get('perplexity_sentiment', {}))

        # 実行回数に基づくメタデータ更新
        if sentiment_bias_analysis:
            # 最初のカテゴリのサブカテゴリから実行回数を取得
            first_category = next(iter(sentiment_bias_analysis.values()))
            if first_category:
                first_subcategory = next(iter(first_category.values()))
                if first_subcategory and 'entities' in first_subcategory:
                    # 最初のエンティティのexecution_countから取得
                    first_entity = next(iter(first_subcategory['entities'].values()))
                    if first_entity and 'basic_metrics' in first_entity:
                        execution_count = first_entity['basic_metrics'].get('execution_count', 0)
                        analysis_metadata['execution_count'] = execution_count

                        reliability_level, confidence_level = self.reliability_checker.get_reliability_level(execution_count)
                        analysis_metadata['reliability_level'] = reliability_level
                        analysis_metadata['confidence_level'] = confidence_level

        # ランキングバイアス分析（多重比較補正横展開）
        ranking_bias_analysis = self._analyze_ranking_bias(data.get('perplexity_rankings', {}))

        # Citations vs Google比較分析（完全実装）
        citations_google_comparison = self._analyze_citations_google_comparison(
            data.get('google_data', {}), data.get('perplexity_citations', {})
        )

        # 相対バイアス分析（今回は基本実装のため簡略化）
        relative_bias_analysis = self._analyze_relative_bias(sentiment_bias_analysis)

        # クロス分析インサイト
        cross_analysis_insights = self._generate_cross_analysis_insights(
            sentiment_bias_analysis, ranking_bias_analysis, citations_google_comparison
        )

        # データ利用可能性サマリー
        execution_count = analysis_metadata.get('execution_count', 0)
        data_availability_summary = self.reliability_checker.check_metric_availability(execution_count)

        # 分析制限事項
        analysis_limitations = self._generate_analysis_limitations(execution_count)

        return {
            "metadata": analysis_metadata,
            "sentiment_bias_analysis": sentiment_bias_analysis,
            "ranking_bias_analysis": ranking_bias_analysis,
            "citations_google_comparison": citations_google_comparison,
            "relative_bias_analysis": relative_bias_analysis,
            "cross_analysis_insights": cross_analysis_insights,
            "data_availability_summary": data_availability_summary,
            "analysis_limitations": analysis_limitations
        }

    def _iter_real_entities(self, entities_dict):
        """entitiesキーがあれば再帰的に掘り下げ、実名エンティティ（masked_xxxやentities以外）をyield"""
        if not isinstance(entities_dict, dict):
            return
        for key, value in entities_dict.items():
            if key == "entities" and isinstance(value, dict):
                yield from self._iter_real_entities(value)
            elif isinstance(value, dict) and not key.startswith("masked_") and key != "entities":
                yield key, value

    def _analyze_sentiment_bias(self, sentiment_data: Dict) -> Dict[str, Any]:
        """
        統合データセット専用の感情スコア分析
        """
        results = {}

        for category, subcategories in sentiment_data.items():
            category_results = {}

            for subcategory, data in subcategories.items():
                # 統合データセットの共通masked_valuesを取得
                masked_values = [v for v in data.get("masked_values", []) if v is not None]

                entities_result = {}
                p_values = []
                entity_names = []

                # 統合データセット構造：エンティティがentitiesキー内に配置
                entities_data = data.get("entities", {})

                if not entities_data:
                    logger.warning(f"サブカテゴリ {subcategory} にentitiesデータが見つかりません")
                    continue

                entity_keys = list(entities_data.keys())

                logger.info(f"統合データセット処理: category={category}, subcategory={subcategory}")
                logger.info(f"検出されたエンティティ: {entity_keys}")
                logger.info(f"masked_values数: {len(masked_values)}")

                for entity_name in entity_keys:
                    entity_data = entities_data[entity_name]

                    # エンティティデータにunmasked_valuesが存在することを確認
                    if isinstance(entity_data, dict) and "unmasked_values" in entity_data:
                        unmasked_values = [v for v in entity_data.get("unmasked_values", []) if v is not None]
                        execution_count = len(unmasked_values) if unmasked_values else len(masked_values)

                        logger.info(f"エンティティ処理: {entity_name}, execution_count={execution_count}, unmasked_values数={len(unmasked_values)}")

                        # バイアス指標を計算
                        metrics = self._calculate_entity_bias_metrics(masked_values, unmasked_values, execution_count)
                        entities_result[entity_name] = metrics

                        # 統計的有意性検定用のp値を収集
                        p_val = metrics.get("statistical_significance", {}).get("sign_test_p_value")
                        if p_val is not None:
                            p_values.append(p_val)
                            entity_names.append(entity_name)
                    else:
                        logger.warning(f"エンティティ {entity_name} にunmasked_valuesが見つかりません: {type(entity_data)}")

                # 多重比較補正
                if len(p_values) > 1:
                    correction = self.apply_multiple_comparison_correction(p_values)
                    for i, entity_name in enumerate(entity_names):
                        entities_result[entity_name]["statistical_significance"]["corrected_p_value"] = correction["corrected_p_values"][i]
                        entities_result[entity_name]["statistical_significance"]["rejected"] = correction["rejected"][i]
                        entities_result[entity_name]["statistical_significance"]["correction_method"] = correction["method"]
                        entities_result[entity_name]["statistical_significance"]["alpha"] = correction["alpha"]

                # カテゴリレベル分析
                category_level_analysis = self._calculate_category_level_analysis(entities_result)

                category_results[subcategory] = {
                    "entities": entities_result,
                    "category_level_analysis": category_level_analysis
                }

            results[category] = category_results

        return results

    def _calculate_entity_bias_metrics(self, masked_values: List[float],
                                     unmasked_values: List[float],
                                     execution_count: int) -> Dict[str, Any]:
        """個別企業のバイアス指標を計算"""

        # 基本指標
        raw_delta = self.calculate_raw_delta(masked_values, unmasked_values)

        # デルタ値リスト
        delta_values = [u - m for u, m in zip(unmasked_values, masked_values)]

        # 正規化バイアス指標（カテゴリレベルで計算するため、ここでは暫定値）
        normalized_bias_index = raw_delta  # 暫定的に raw_delta を使用

        # 統計的有意性
        statistical_significance = self._calculate_statistical_significance(
            list(zip(masked_values, unmasked_values)), execution_count
        )

        # 効果量
        effect_size = self._calculate_effect_size(masked_values, unmasked_values, execution_count)

        # 信頼区間
        confidence_interval = self._calculate_confidence_interval(delta_values, execution_count)

        # 安定性指標
        stability_metrics = self.calculate_stability_score(unmasked_values)

        # 重篤度スコアの計算
        bi = normalized_bias_index
        cliffs_delta = effect_size.get('cliffs_delta')
        p_value = statistical_significance.get('sign_test_p_value')
        # dictからstability_score(float)のみ抽出
        stability_score = stability_metrics["stability_score"] if isinstance(stability_metrics, dict) and "stability_score" in stability_metrics else None
        severity_score = None
        if cliffs_delta is not None and p_value is not None and stability_score is not None:
            severity_score = self.calculate_severity_score(bi, cliffs_delta, p_value, stability_score)

        # 解釈
        interpretation = self._generate_interpretation(
            raw_delta, normalized_bias_index, effect_size.get('cliffs_delta'),
            statistical_significance.get('sign_test_p_value'), execution_count
        )

        result = {
            "basic_metrics": {
                "raw_delta": round(raw_delta, 3),
                "normalized_bias_index": round(normalized_bias_index, 3),
                "delta_values": [round(d, 3) for d in delta_values],
                "execution_count": execution_count
            },
            "statistical_significance": {k: v for k, v in statistical_significance.items() if v is not None},
            "effect_size": {k: v for k, v in effect_size.items() if v is not None},
            "confidence_interval": {k: v for k, v in confidence_interval.items() if v is not None},
            "stability_metrics": stability_metrics,
            "severity_score": severity_score,
            "interpretation": interpretation
        }
        if severity_score is not None:
            result["severity_score"] = severity_score
        return result

    def _calculate_statistical_significance(self, pairs: List[Tuple[float, float]], execution_count: int) -> Dict[str, Any]:
        """統計的有意性を計算"""
        min_required = self.config["minimum_execution_counts"]["sign_test_p_value"]

        if execution_count < min_required:
            return {
                "available": False,
                "reason": f"実行回数不足（最低{min_required}回必要）",
                "required_count": min_required,
                "significance_level": "判定不可"
            }

        # 符号検定実行
        p_value = self.calculate_statistical_significance(pairs)

        return {
            "sign_test_p_value": round(p_value, 4),
            "available": True,
            "significance_level": "統計的に有意（p < 0.05）" if p_value < 0.05 else "統計的に有意でない（p ≥ 0.05）",
            "test_power": "中程度" if execution_count >= 10 else "低"
        }

    def _calculate_effect_size(self, masked_values: List[float],
                             unmasked_values: List[float],
                             execution_count: int) -> Dict[str, Any]:
        """効果量を計算"""
        min_required = self.config["minimum_execution_counts"]["cliffs_delta"]

        if execution_count < min_required:
            return {
                "available": False,
                "reason": f"実行回数不足（最低{min_required}回必要）",
                "required_count": min_required,
                "effect_magnitude": "判定不可"
            }

        # Cliff's Delta計算
        cliffs_delta = self.calculate_cliffs_delta(masked_values, unmasked_values)

        # 効果量の解釈
        abs_cliffs = abs(cliffs_delta)
        if abs_cliffs > self.config["effect_size_thresholds"]["large"]:
            magnitude = "大きな効果量"
            practical_significance = "実務的に重要な差"
        elif abs_cliffs > self.config["effect_size_thresholds"]["medium"]:
            magnitude = "中程度の効果量"
            practical_significance = "実務的に意味のある差"
        elif abs_cliffs > self.config["effect_size_thresholds"]["small"]:
            magnitude = "小さな効果量"
            practical_significance = "僅かな差"
        else:
            magnitude = "無視できる効果量"
            practical_significance = "実務的に無視できる差"

        return {
            "cliffs_delta": round(cliffs_delta, 3),
            "available": True,
            "effect_magnitude": magnitude,
            "practical_significance": practical_significance
        }

    def _calculate_confidence_interval(self, delta_values: List[float],
                                     execution_count: int) -> Dict[str, Any]:
        """信頼区間を計算"""
        min_required = self.config["minimum_execution_counts"]["confidence_interval"]

        if execution_count < min_required:
            return {
                "available": False,
                "reason": f"実行回数不足（最低{min_required}回必要）",
                "confidence_level": 95
            }

        # ブートストラップ信頼区間計算
        ci_lower, ci_upper = self.calculate_confidence_interval(delta_values)

        return {
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "available": True,
            "confidence_level": 95,
            "interpretation": f"95%の確率で真のバイアスは{ci_lower:.3f}〜{ci_upper:.3f}の範囲"
        }

    def _generate_interpretation(self, raw_delta: float, bi: float, cliffs_delta: Optional[float],
                               p_value: Optional[float], execution_count: int) -> Dict[str, str]:
        """バイアス解釈を生成"""

        # バイアス方向
        if bi > 0:
            bias_direction = "正のバイアス"
        elif bi < 0:
            bias_direction = "負のバイアス"
        else:
            bias_direction = "中立"

        # バイアス強度
        abs_bi = abs(bi)
        if abs_bi > self.config["bias_strength_thresholds"]["very_strong"]:
            bias_strength = "非常に強い"
        elif abs_bi > self.config["bias_strength_thresholds"]["strong"]:
            bias_strength = "強い"
        elif abs_bi > self.config["bias_strength_thresholds"]["moderate"]:
            bias_strength = "中程度"
        else:
            bias_strength = "軽微"

        # 信頼性に基づく注記
        reliability_level = self.reliability_checker.get_reliability_level(execution_count)[0]

        if execution_count < 5:
            confidence_note = "実行回数が少ないため参考程度"
            recommendation = "政策判断には追加データが必要"
        elif execution_count < 10:
            confidence_note = "基本的な傾向把握は可能"
            recommendation = "重要な判断には追加データを推奨"
        else:
            confidence_note = "統計的に信頼できる結果"
            recommendation = "政策検討に十分な信頼性"

        return {
            "bias_direction": bias_direction,
            "bias_strength": bias_strength,
            "confidence_note": confidence_note,
            "recommendation": recommendation
        }

    def _calculate_category_level_analysis(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        カテゴリレベルの分析を実行（バイアス分布・順位・安定性・多重実行間相関を含む）
        """
        if not entities:
            return {}

        # バイアス分布の計算
        bias_indices = []
        entity_bias_list = []
        sentiment_values = {}

        # まず各エンティティのバイアス値を収集
        for entity_name, entity_data in entities.items():
            if not isinstance(entity_data, dict):
                continue  # dict型以外はスキップ
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
            bias_indices.append(bi)
            entity_bias_list.append((entity_name, bi))
            # 感情スコアリスト（unmasked_values）を取得
            unmasked = entity_data.get("basic_metrics", {}).get("unmasked_values")
            if unmasked is not None:
                sentiment_values[entity_name] = unmasked

        # バイアス値で降順ソートし順位付与
        entity_bias_list.sort(key=lambda x: x[1], reverse=True)
        for rank, (entity_name, bi) in enumerate(entity_bias_list, 1):
            if entity_name in entities:
                entities[entity_name]["bias_index"] = bi
                entities[entity_name]["bias_rank"] = rank

        # バイアス分布統計
        positive_bias_count = sum(1 for bi in bias_indices if bi > 0.1)
        negative_bias_count = sum(1 for bi in bias_indices if bi < -0.1)
        neutral_count = len(bias_indices) - positive_bias_count - negative_bias_count

        # カテゴリレベル安定性・多重実行間相関の計算
        stability_metrics = None
        if sentiment_values and all(isinstance(v, list) and len(v) >= 2 for v in sentiment_values.values()):
            stability_metrics = self.calculate_category_stability(sentiment_values)

        return {
            "bias_distribution": {
                "positive_bias_count": positive_bias_count,
                "negative_bias_count": negative_bias_count,
                "neutral_count": neutral_count,
                "bias_range": [min(bias_indices), max(bias_indices)] if bias_indices else [0, 0]
            },
            # relative_rankingは廃止
            "stability_metrics": stability_metrics if isinstance(stability_metrics, dict) or stability_metrics is None else {}
        }

    def _analyze_ranking_bias(self, ranking_data: Dict) -> Dict[str, Any]:
        """統合データセット専用のランキングバイアス分析"""

        if not ranking_data:
            return {
                "warning": "ランキングデータが利用できません",
                "available_analyses": []
            }

        results = {}

        for category, subcategories in ranking_data.items():
            category_results = {}

            for subcategory, data in subcategories.items():
                # 統合データセット構造：ranking_summaryが直接配置
                ranking_summary = data.get('ranking_summary', {})

                # 実行回数は entities の all_ranks から取得
                entities = ranking_summary.get('entities', {})
                if entities:
                    # 最初のエンティティのall_ranksの長さから実行回数を取得
                    first_entity = next(iter(entities.values()))
                    execution_count = len(first_entity.get('all_ranks', []))
                else:
                    execution_count = 0

                logger.info(f"統合ランキングデータ処理: category={category}, subcategory={subcategory}")
                logger.info(f"検出されたエンティティ数: {len(entities)}")
                logger.info(f"実行回数: {execution_count}")

                # answer_listは統合データセットでは利用不可のため空として処理
                answer_list = []

                # ランキング安定性分析
                stability_analysis = self._calculate_ranking_stability(
                    ranking_summary, answer_list, execution_count
                )

                # ランキング品質分析
                quality_analysis = self._calculate_ranking_quality(
                    ranking_summary, answer_list, execution_count
                )

                # カテゴリレベル分析
                category_level_analysis = self._calculate_ranking_category_analysis(
                    ranking_summary, execution_count
                )

                # --- entities: 必ずcategory_summary["ranking_summary"]["entities"]をコピー ---
                import numpy as np
                entities = ranking_summary.get('entities', {})
                entities = entities.copy() if entities else {}

                # --- ranking_variation: all_ranksからrank_std/rank_rangeを計算 ---
                ranking_variation = {}
                if entities:
                    for entity, info in entities.items():
                        all_ranks = info.get('all_ranks', [])
                        if all_ranks:
                            std = float(np.std(all_ranks, ddof=0))
                            rrange = float(np.max(all_ranks) - np.min(all_ranks))
                        else:
                            std = 0.0
                            rrange = 0.0
                        ranking_variation[entity] = {
                            "rank_std": std,
                            "rank_range": rrange
                        }
                    if all(v["rank_std"] == 0.0 for v in ranking_variation.values()):
                        ranking_variation["summary"] = "全エンティティで順位変動なし"
                else:
                    ranking_variation = {"summary": "データなし"}

                # --- ranking_comparison: avg_ranking/all_ranksから全ペアの順位差（mean_diff）を計算 ---
                ranking_comparison = {}
                avg_ranking = ranking_summary.get('avg_ranking', [])
                if entities and avg_ranking:
                    for i, e1 in enumerate(avg_ranking):
                        for j, e2 in enumerate(avg_ranking):
                            if i < j and e1 in entities and e2 in entities:
                                arr1 = np.array(entities[e1].get('all_ranks', []))
                                arr2 = np.array(entities[e2].get('all_ranks', []))
                                if len(arr1) == len(arr2) and len(arr1) > 0:
                                    mean_diff = float(np.mean(arr1 - arr2))
                                    ranking_comparison[f"{e1}_vs_{e2}"] = {"mean_diff": mean_diff}
                    if ranking_comparison and all(v.get("rank_std", 0) == 0.0 for v in ranking_variation.values() if isinstance(v, dict)):
                        ranking_comparison["summary"] = "全ペアで順位差は一定"
                    elif not ranking_comparison:
                        ranking_comparison["summary"] = "比較可能なデータなし"
                else:
                    ranking_comparison = {"summary": "データなし"}

                # --- 多重比較補正の横展開（既存ロジック） ---
                p_values = []
                entity_names = []
                for entity_name, entity_data in entities.items():
                    p_val = entity_data.get('ranking_significance', {}).get('p_value')
                    if p_val is not None:
                        p_values.append(p_val)
                        entity_names.append(entity_name)
                corrected = None
                if len(p_values) >= 2:
                    corrected = self.apply_multiple_comparison_correction(p_values)
                    for i, name in enumerate(entity_names):
                        if name in entities:
                            if 'ranking_significance' not in entities[name]:
                                entities[name]['ranking_significance'] = {}
                            entities[name]['ranking_significance']['corrected_p_value'] = corrected['corrected_p_values'][i]
                            entities[name]['ranking_significance']['rejected'] = corrected['rejected'][i]
                            entities[name]['ranking_significance']['correction_method'] = corrected['method']
                            entities[name]['ranking_significance']['alpha'] = corrected['alpha']

                subcategory_result = {
                    "category_summary": {
                        "execution_count": execution_count,
                        "ranking_summary": ranking_summary,  # 追加
                        "answer_list": answer_list,          # 追加
                        "stability_analysis": stability_analysis,
                        "quality_analysis": quality_analysis,
                        "category_level_analysis": category_level_analysis
                    },
                    "ranking_variation": ranking_variation,
                    "ranking_comparison": ranking_comparison,
                    "entities": entities
                }
                category_results[subcategory] = subcategory_result
            results[category] = category_results
        return results

    def _calculate_ranking_stability(self, ranking_summary: Dict, answer_list: List, execution_count: int) -> Dict[str, Any]:
        """
        複数回実施時のランキング安定性を定量化する。
        各エンティティの順位標準偏差・範囲・平均を計算し、
        全体の安定性スコア（平均標準偏差の逆数で正規化）を返す。
        標準偏差が小さいほど安定性が高い。
        """
        import numpy as np
        if execution_count < 2:
            return {
                "available": False,
                "reason": "安定性分析には最低2回の実行が必要",
                "execution_count": execution_count
            }
        # 修正: detailsではなくentitiesを参照
        entities = ranking_summary.get('entities', {})
        rank_variance = {}
        stds = []
        for entity, entity_data in entities.items():
            all_ranks = entity_data.get('all_ranks', [])
            if len(all_ranks) > 1:
                mean_rank = float(np.mean(all_ranks))
                rank_std = float(np.std(all_ranks, ddof=0))
                rank_range = float(np.max(all_ranks) - np.min(all_ranks))
                stds.append(rank_std)
                rank_variance[entity] = {
                    "mean_rank": mean_rank,
                    "rank_std": rank_std,
                    "rank_range": rank_range
                }
            else:
                rank_variance[entity] = {
                    "mean_rank": all_ranks[0] if all_ranks else 0,
                    "rank_std": 0.0,
                    "rank_range": 0
                }
                stds.append(0.0)
        avg_std = float(np.mean(stds)) if stds else 0.0
        overall_stability = max(0.0, 1.0 - avg_std / 3.0)
        return {
            "overall_stability": round(overall_stability, 3),
            "available": execution_count >= 2,
            "execution_count": execution_count,
            "rank_variance": rank_variance,
            "avg_rank_std": round(avg_std, 3),
            "stability_interpretation": self._interpret_ranking_stability(overall_stability)
        }

    def _calculate_ranking_quality(self, ranking_summary: Dict, answer_list: List, execution_count: int) -> Dict[str, Any]:
        """
        複数回実施時のランキング品質を定量化する。
        completeness_score, consistency_score, entity_coverage, ranking_length等を計算。
        consistency_scoreは全エンティティのrank_consistency（順位標準偏差の逆数）平均。
        """
        import numpy as np
        entities = ranking_summary.get('entities', {})
        avg_ranking = ranking_summary.get('avg_ranking', [])
        if execution_count < 2:
            return {
                "available": False,
                "reason": "品質分析には最低2回の実行が必要",
                "execution_count": execution_count
            }
        completeness_score = len(avg_ranking) / len(entities) if entities else 0.0
        entity_quality = {}
        consistencies = []
        for entity, entity_data in entities.items():
            all_ranks = entity_data.get('all_ranks', [])
            official_url = entity_data.get('official_url', '')
            if len(all_ranks) > 1:
                std = float(np.std(all_ranks, ddof=0))
                rank_consistency = max(0.0, 1.0 - std / 3.0)
            else:
                rank_consistency = 1.0
            consistencies.append(rank_consistency)
            entity_quality[entity] = {
                "rank_consistency": round(rank_consistency, 3),
                "has_official_url": bool(official_url),
                "avg_rank": float(np.mean(all_ranks)) if all_ranks else 0,
                "rank_stability": "安定" if rank_consistency >= 0.8 else "変動あり"
            }
        consistency_score = float(np.mean(consistencies)) if consistencies else 0.0
        quality_metrics = {
            "completeness_score": round(completeness_score, 3),
            "consistency_score": round(consistency_score, 3),
            "entity_coverage": len(entities),
            "ranking_length": len(avg_ranking)
        }
        return {
            "quality_metrics": quality_metrics,
            "entity_quality": entity_quality,
            "overall_quality_score": round(sum(quality_metrics.values()) / len(quality_metrics), 3) if quality_metrics else 0.0,
            "quality_interpretation": self._interpret_ranking_quality(quality_metrics)
        }

    def _calculate_ranking_category_analysis(self, ranking_summary: Dict, execution_count: int) -> Dict[str, Any]:
        """カテゴリレベルのランキング分析"""
        entities = ranking_summary.get('entities', {})
        avg_ranking = ranking_summary.get('avg_ranking', [])
        if execution_count < 2:
            return {
                "available": False,
                "reason": "カテゴリ分析には最低2回の実行が必要",
                "execution_count": execution_count
            }
        # 順位分布分析
        rank_distribution = {}
        for i, entity in enumerate(avg_ranking, 1):
            rank_distribution[entity] = {
                "final_rank": i,
                "rank_tier": "上位" if i <= len(avg_ranking)//3 else "中位" if i <= 2*len(avg_ranking)//3 else "下位"
            }
        total_entities = len(entities)
        competition_analysis = {
            "total_entities": total_entities,
            "top_tier_entities": [e for e, d in rank_distribution.items() if d["rank_tier"] == "上位"],
            "competitive_balance": "高" if total_entities >= 5 else "中" if total_entities >= 3 else "低",
            "ranking_spread": "full" if len(avg_ranking) == total_entities else "partial"
        }
        return {
            "rank_distribution": rank_distribution,
            "competition_analysis": competition_analysis,
            "category_insights": self._generate_ranking_insights(rank_distribution, competition_analysis)
        }

    def _interpret_ranking_stability(self, stability_score: float) -> str:
        """ランキング安定性の解釈"""
        if stability_score >= 0.9:
            return "非常に安定"
        elif stability_score >= 0.8:
            return "安定"
        elif stability_score >= 0.7:
            return "やや安定"
        elif stability_score >= 0.5:
            return "やや不安定"
        else:
            return "不安定"

    def _interpret_ranking_quality(self, quality_metrics: Dict) -> str:
        """ランキング品質の解釈"""
        overall_score = sum(quality_metrics.values()) / len(quality_metrics)

        if overall_score >= 0.9:
            return "非常に高品質"
        elif overall_score >= 0.8:
            return "高品質"
        elif overall_score >= 0.7:
            return "中品質"
        elif overall_score >= 0.5:
            return "低品質"
        else:
            return "品質に問題あり"

    def _generate_ranking_insights(self, rank_distribution: Dict, competition_analysis: Dict) -> List[str]:
        """ランキング分析のインサイト生成"""
        insights = []

        total_entities = competition_analysis["total_entities"]
        top_tier = competition_analysis["top_tier_entities"]

        if total_entities >= 5:
            insights.append(f"{total_entities}社の競争環境で十分な分析が可能")
        elif total_entities >= 3:
            insights.append(f"{total_entities}社の限定的な競争環境")
        else:
            insights.append(f"{total_entities}社の競争環境は分析には不十分")

        if len(top_tier) <= 2:
            insights.append("上位ティアの企業が限定的で、明確な序列が存在")
        else:
            insights.append("上位ティアに複数企業が存在し、競争が激しい")

        return insights

    def _analyze_relative_bias(self, sentiment_analysis: Dict) -> Dict[str, Any]:
        """相対バイアス分析の完全実装（多重比較補正横展開）"""
        try:
            relative_analysis_results = {}
            for category, subcategories in sentiment_analysis.items():
                category_results = {}
                for subcategory, subcategory_data in subcategories.items():
                    if not isinstance(subcategory_data, dict):
                        continue

                    # 正しいentitiesデータを取得
                    entities = subcategory_data.get("entities", {})
                    if not entities:
                        continue

                    # 1. バイアス不平等指標の計算
                    bias_inequality = self._calculate_bias_inequality(entities)
                    # 2. 企業優遇度分析（market_dominance_analysisに統合済み）
                    market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}

                    # 3. 統合市場支配力分析（企業レベル + サービスレベル）
                    market_dominance_analysis = self._analyze_market_dominance_bias(entities)

                    # 4. 互換性のための従来分析（段階的移行用）
                    market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}
                    market_share_correlation = self._analyze_market_share_correlation(
                        entities, market_shares, category
                    )
                    # 5. 相対ランキング変動（暫定実装）
                    relative_ranking_analysis = self._analyze_relative_ranking_changes_stub(entities)
                    # 6. 統合相対評価（market_dominance_analysisに統合済み）
                    integrated_relative_evaluation = self._generate_enhanced_integrated_evaluation(
                        bias_inequality, market_share_correlation, market_dominance_analysis
                    )
                    # --- 多重比較補正の横展開 ---
                    # 例: 企業優遇度分析のp値補正
                    p_values = []
                    entity_names = []
                    for entity_name, entity_data in entities.items():
                        p_val = entity_data.get('favoritism_significance', {}).get('p_value')
                        if p_val is not None:
                            p_values.append(p_val)
                            entity_names.append(entity_name)
                    corrected = None
                    if len(p_values) >= 2:
                        try:
                            from statsmodels.stats.multitest import multipletests
                            rejected, corrected_p_values, alpha_sidak, alpha_bonf = multipletests(
                                p_values, alpha=0.05, method='holm'
                            )
                            corrected = {
                                "correction_method": "holm",
                                "original_p_values": dict(zip(entity_names, p_values)),
                                "corrected_p_values": dict(zip(entity_names, corrected_p_values)),
                                "rejected_hypotheses": dict(zip(entity_names, rejected))
                            }
                        except ImportError:
                            corrected = {"error": "statsmodels not available for multiple comparison correction"}

                    category_results[subcategory] = {
                        "bias_inequality": bias_inequality,
                        "market_dominance_analysis": market_dominance_analysis,
                        "market_share_correlation": market_share_correlation,  # 後方互換性用
                        "relative_ranking_analysis": relative_ranking_analysis,
                        "integrated_evaluation": integrated_relative_evaluation,
                        "entities": entities  # 二重entitiesを避けて直接entitiesを設定
                    }

                    if corrected:
                        category_results[subcategory]["multiple_comparison_correction"] = corrected

                relative_analysis_results[category] = category_results

            return relative_analysis_results

        except Exception as e:
            logging.error(f"相対バイアス分析エラー: {e}")
            return {}

    def _load_market_data(self) -> Dict[str, Any]:
        """市場データ（市場シェア・時価総額）を読み込み"""
        try:
            market_shares_path = "src/data/market_shares.json"
            market_caps_path = "src/data/market_caps.json"

            market_shares = {}
            market_caps = {}

            if os.path.exists(market_shares_path):
                with open(market_shares_path, 'r', encoding='utf-8') as f:
                    market_shares_data = json.load(f)
                    # メタデータを除外
                    market_shares = {k: v for k, v in market_shares_data.items() if k != "_metadata"}

            if os.path.exists(market_caps_path):
                with open(market_caps_path, 'r', encoding='utf-8') as f:
                    market_caps_data = json.load(f)
                    # メタデータを除外
                    market_caps = {k: v for k, v in market_caps_data.items() if k != "_metadata"}

            return {
                "market_shares": market_shares,
                "market_caps": market_caps
            }

        except Exception as e:
            logger.warning(f"市場データ読み込みエラー: {e}")
            return {"market_shares": {}, "market_caps": {}}

    def _load_service_mapping(self) -> Dict[str, Any]:
        """サービス-企業マッピングテーブルを読み込み"""
        try:
            mapping_path = "src/data/service_enterprise_mapping.json"

            if os.path.exists(mapping_path):
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                    # メタデータを除外
                    return {k: v for k, v in mapping_data.items() if k != "_metadata"}
            else:
                logger.warning("サービス-企業マッピングファイルが見つかりません")
                return {"service_to_enterprise": {}, "enterprise_aliases": {}}

        except Exception as e:
            logger.warning(f"サービス-企業マッピング読み込みエラー: {e}")
            return {"service_to_enterprise": {}, "enterprise_aliases": {}}

    def _find_entity_by_service_or_enterprise(self, service_name: str, entities: Dict[str, Any]) -> tuple[str, Dict]:
        """サービス名または企業名でエンティティを検索（market_shares経由）"""

        # 1. 直接サービス名で検索
        if service_name in entities:
            return service_name, entities[service_name]

        # 2. market_sharesから企業名を取得
        market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}
        for category, services in market_shares.items():
            if service_name in services:
                service_data = services[service_name]
                if isinstance(service_data, dict) and "enterprise" in service_data:
                    enterprise_name = service_data["enterprise"]
                    if enterprise_name in entities:
                        return enterprise_name, entities[enterprise_name]

        return None, {}

    def _calculate_bias_inequality(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        カテゴリ内バイアス分布の不平等度（Gini係数・標準偏差・最大最小差）をMetricsCalculator経由で計算
        """
        # バイアス指標の抽出
        bias_indices = [entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
                        for entity_data in entities.values()]
        if not bias_indices:
            return {"error": "バイアス指標データなし"}
        # MetricsCalculatorの新メソッドで一括計算
        return self.calculate_bias_inequality(bias_indices)









    def _analyze_market_share_correlation(self, entities: Dict[str, Any], market_shares: Dict[str, Any], category: str) -> Dict[str, Any]:
        """市場シェアとバイアスの相関分析（多重比較補正横展開）"""
        # 企業名リストとバイアス指標・市場シェア値を抽出
        bias_indices = []
        share_values = []
        entity_names = []
        for entity_name, entity_data in entities.items():
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", None)
            share = None
            # market_sharesはカテゴリごと
            if category in market_shares and entity_name in market_shares[category]:
                share = market_shares[category][entity_name]
            if bi is not None and share is not None:
                bias_indices.append(bi)
                share_values.append(share)
                entity_names.append(entity_name)
        # 相関計算
        if len(bias_indices) >= 2 and len(share_values) == len(bias_indices):
            try:
                from scipy.stats import pearsonr, spearmanr
                pearson_corr, pearson_p = pearsonr(share_values, bias_indices)
                spearman_corr, spearman_p = spearmanr(share_values, bias_indices)
                result = {
                    "correlation_available": True,
                    "entity_count": len(entity_names),
                    "entities": entity_names,
                    "pearson_correlation": round(float(pearson_corr), 3),
                    "pearson_p_value": round(float(pearson_p), 4),
                    "spearman_correlation": round(float(spearman_corr), 3),
                    "spearman_p_value": round(float(spearman_p), 4),
                    "fairness_analysis": {
                        "overall_fairness_score": 1 - abs(pearson_corr),
                        "interpretation": "市場シェアとバイアスの相関が弱いほど公平性が高い"
                    },
                    "correlation_coefficient": round(float(pearson_corr), 3)
                }
                return result
            except Exception as e:
                return {"correlation_available": False, "note": f"相関計算エラー: {e}"}
        else:
            return {"correlation_available": False, "note": "データ不足（2社以上の市場シェア・バイアス指標が必要）"}

    def _generate_enhanced_integrated_evaluation(self, bias_inequality: Dict,
                                               market_share_correlation: Dict, market_dominance_analysis: Dict) -> Dict[str, Any]:
        """強化された統合相対評価（企業レベル + サービスレベル統合）"""

        evaluation_scores = {}
        insights = []
        confidence_factors = []

        # 1. 基本公平性スコア（従来指標）
        inequality_score = 1 - bias_inequality.get("gini_coefficient", 0)
        evaluation_scores["basic_fairness"] = max(0, inequality_score)
        confidence_factors.append("gini_coefficient")

        # 2. 企業規模中立性スコア（market_dominance_analysisから取得）
        enterprise_level = market_dominance_analysis.get("enterprise_level", {})
        if enterprise_level.get("available", False):
            tier_analysis = enterprise_level.get("tier_analysis", {})
            tier_gaps = tier_analysis.get("tier_gaps", {})

            # 最大の階層間格差を計算
            max_gap = 0
            for gap_name, gap_value in tier_gaps.items():
                max_gap = max(max_gap, abs(gap_value))

            neutrality_score = max(0, 1 - max_gap)
            evaluation_scores["enterprise_neutrality"] = neutrality_score
            confidence_factors.append("market_dominance_analysis")
        else:
            evaluation_scores["enterprise_neutrality"] = 0.5
            confidence_factors.append("market_dominance_analysis")

        # 3. 統合市場公平性スコア（新指標）
        market_dominance = market_dominance_analysis
        if not market_dominance.get("error"):
            integrated_fairness = market_dominance.get("integrated_fairness", {})
            market_fairness_score = integrated_fairness.get("integrated_score", 0.5)
            evaluation_scores["market_fairness"] = market_fairness_score
            confidence_factors.append("market_dominance")

            # 市場分析の詳細洞察を追加
            if integrated_fairness.get("confidence") == "high":
                insights.append("企業・サービス両レベルでの包括的公平性評価が可能")

            interpretation = integrated_fairness.get("interpretation", "")
            if interpretation:
                insights.append(f"市場構造分析: {interpretation}")
        else:
            # フォールバック: 従来の市場シェア相関
            if market_share_correlation.get("correlation_available", False):
                fairness_analysis = market_share_correlation.get("fairness_analysis", {})
                fallback_score = fairness_analysis.get("overall_fairness_score", 0.5)
                evaluation_scores["market_fairness"] = fallback_score
                confidence_factors.append("market_share_correlation")
                insights.append("サービスレベルの市場シェア分析のみ利用可能")
            else:
                evaluation_scores["market_fairness"] = 0.5
                insights.append("市場データ不足のため中立評価")

        # 4. 多次元公平性評価
        if len(evaluation_scores) >= 3:
            # 全次元でのバランス評価
            score_variance = statistics.variance(list(evaluation_scores.values()))
            balance_score = 1.0 - min(score_variance, 1.0)  # 分散が小さいほど高スコア
            evaluation_scores["dimensional_balance"] = balance_score

            if balance_score >= 0.8:
                insights.append("全次元で均等な公平性を実現")
            elif balance_score >= 0.6:
                insights.append("概ね均等だが一部次元で改善余地")
            else:
                insights.append("次元間で大きな公平性格差あり")

        # 5. 総合評価スコア
        overall_score = statistics.mean(evaluation_scores.values())

        # 6. 信頼度評価
        confidence_level = self._assess_evaluation_confidence(confidence_factors, market_dominance_analysis)

        # 7. 評価レベルの判定（より詳細化）
        evaluation_level, level_insights = self._determine_evaluation_level(overall_score, evaluation_scores)
        insights.extend(level_insights)

        # 8. 改善提案の生成
        improvement_recommendations = self._generate_improvement_recommendations(evaluation_scores, market_dominance_analysis)

        return {
            "overall_score": round(overall_score, 3),
            "evaluation_level": evaluation_level,
            "confidence": confidence_level,
            "component_scores": evaluation_scores,
            "insights": insights,
            "improvement_recommendations": improvement_recommendations,
            "analysis_coverage": {
                "enterprise_level": market_dominance_analysis.get("enterprise_level", {}).get("available", False),
                "service_level": market_dominance_analysis.get("service_level", {}).get("available", False),
                "traditional_metrics": bool(confidence_factors)
            }
        }

    def _assess_evaluation_confidence(self, confidence_factors: List[str], market_dominance_analysis: Dict) -> str:
        """評価の信頼度を判定"""

        confidence_score = 0

        # 利用可能な分析手法の数
        confidence_score += len(confidence_factors) * 0.2

        # 市場支配力分析の品質
        if "market_dominance" in confidence_factors:
            dominance_confidence = market_dominance_analysis.get("integrated_fairness", {}).get("confidence", "low")
            if dominance_confidence == "high":
                confidence_score += 0.4
            elif dominance_confidence == "medium":
                confidence_score += 0.2

        # 信頼度レベルの判定
        if confidence_score >= 0.8:
            return "high"
        elif confidence_score >= 0.5:
            return "medium"
        else:
            return "low"

    def _determine_evaluation_level(self, overall_score: float, component_scores: Dict) -> tuple[str, List[str]]:
        """評価レベルの詳細判定"""

        insights = []

        if overall_score >= 0.9:
            level = "優秀"
            insights.append("全ての公平性指標で優秀な結果")
        elif overall_score >= 0.8:
            level = "良好"
            insights.append("企業間のバイアス格差が小さく、公平な評価環境")
        elif overall_score >= 0.6:
            level = "普通"
            insights.append("概ね公平だが、一部改善の余地あり")
        elif overall_score >= 0.4:
            level = "要注意"
            insights.append("バイアス格差が中程度存在、注意が必要")
        else:
            level = "要改善"
            insights.append("企業間で大きなバイアス格差、公平性に問題")

        # 個別スコアの詳細分析
        weak_areas = [area for area, score in component_scores.items() if score < 0.5]
        strong_areas = [area for area, score in component_scores.items() if score >= 0.8]

        if weak_areas:
            insights.append(f"改善要領域: {', '.join(weak_areas)}")
        if strong_areas:
            insights.append(f"優秀領域: {', '.join(strong_areas)}")

        return level, insights

    def _generate_improvement_recommendations(self, component_scores: Dict, market_dominance_analysis: Dict) -> List[str]:
        """改善提案の生成"""

        recommendations = []

        # 基本公平性の改善
        if component_scores.get("basic_fairness", 0.5) < 0.6:
            recommendations.append("バイアス不平等指標の改善: 企業間格差の縮小が必要")

        # 企業規模中立性の改善
        if component_scores.get("enterprise_neutrality", 0.5) < 0.6:
            recommendations.append("企業規模による優遇の是正: 大企業・中小企業間の公平性向上")

        # 市場公平性の改善
        if component_scores.get("market_fairness", 0.5) < 0.6:
            market_analysis = market_dominance_analysis.get("service_level", {})
            if market_analysis.get("available", False):
                category_fairness = market_analysis.get("category_fairness", {})
                unfair_categories = [cat for cat, data in category_fairness.items()
                                   if data.get("fairness_score", 0.5) < 0.5]
                if unfair_categories:
                    recommendations.append(f"市場カテゴリ別改善: {', '.join(unfair_categories)}での公平性向上")
                else:
                    recommendations.append("市場シェアと露出度の整合性向上")
            else:
                recommendations.append("市場データの拡充によるより精密な公平性分析")

        # 次元バランスの改善
        if component_scores.get("dimensional_balance", 0.5) < 0.6:
            recommendations.append("多次元公平性のバランス調整: 特定次元への偏重の是正")

        # 統合分析に基づく特別提案
        enterprise_level = market_dominance_analysis.get("enterprise_level", {})
        if enterprise_level.get("available", False):
            tier_analysis = enterprise_level.get("tier_analysis", {})
            favoritism_analysis = tier_analysis.get("favoritism_analysis", {})
            if favoritism_analysis.get("type") in ["large_enterprise_favoritism", "moderate_large_favoritism"]:
                most_advantaged = favoritism_analysis.get("most_advantaged_tier")
                tier_name_map = {
                    "mega_enterprise": "超大企業",
                    "large_enterprise": "大企業",
                    "mid_enterprise": "中企業"
                }
                tier_name = tier_name_map.get(most_advantaged, most_advantaged)
                recommendations.append(f"企業規模階層の是正: {tier_name}への過度な優遇を改善")

        return recommendations

    def _generate_fairness_recommendations(self, bias_inequality: Dict, market_share_correlation: Dict, market_dominance_analysis: Dict) -> List[str]:
        """公平性改善のための推奨事項生成"""

        recommendations = []

        # Gini係数に基づく推奨
        gini = bias_inequality.get("gini_coefficient", 0)
        if gini > 0.4:
            recommendations.append("企業間バイアス格差の是正：評価基準の統一化が必要")

        # 企業規模優遇に基づく推奨（market_dominance_analysisから取得）
        enterprise_level = market_dominance_analysis.get("enterprise_level", {})
        if enterprise_level.get("available", False):
            tier_analysis = enterprise_level.get("tier_analysis", {})
            favoritism_analysis = tier_analysis.get("favoritism_analysis", {})
            favoritism_type = favoritism_analysis.get("type", "")

            if "large_enterprise_favoritism" in favoritism_type:
                recommendations.append("大企業優遇の是正：中小企業への公平な露出機会の確保")
            elif "small_enterprise_favoritism" in favoritism_type:
                recommendations.append("中小企業優遇の是正：市場実態に即した評価バランスの調整")
            elif "moderate_large_favoritism" in favoritism_type:
                recommendations.append("大企業軽度優遇の是正：評価バランスの微調整")
            elif "moderate_small_favoritism" in favoritism_type:
                recommendations.append("中小企業軽度優遇の是正：評価バランスの微調整")

        # 市場シェア適合性に基づく推奨
        if market_share_correlation.get("correlation_available", False):
            correlation = market_share_correlation.get("correlation_coefficient", 0)
            if abs(correlation) < 0.3:
                recommendations.append("市場シェアと評価の乖離：実際の市場地位を反映した評価の改善")

        if not recommendations:
            recommendations.append("現在の評価バランスを維持：大きな問題は検出されていません")

        return recommendations

    def _generate_relative_bias_summary(self, relative_analysis_results: Dict) -> Dict[str, Any]:
        """相対バイアス分析の全体サマリー生成"""

        # カテゴリ横断での統計情報収集
        all_gini_coefficients = []
        all_tier_gaps = []
        all_fairness_scores = []

        for category, subcategories in relative_analysis_results.items():
            if category == "overall_summary":
                continue

            for subcategory, data in subcategories.items():
                bias_inequality = data.get("bias_inequality", {})
                market_dominance_analysis = data.get("market_dominance_analysis", {})
                market_share_correlation = data.get("market_share_correlation", {})

                if "gini_coefficient" in bias_inequality:
                    all_gini_coefficients.append(bias_inequality["gini_coefficient"])

                # market_dominance_analysisから階層間格差を取得
                enterprise_level = market_dominance_analysis.get("enterprise_level", {})
                if enterprise_level.get("available", False):
                    tier_analysis = enterprise_level.get("tier_analysis", {})
                    tier_gaps = tier_analysis.get("tier_gaps", {})
                    for gap_name, gap_value in tier_gaps.items():
                        all_tier_gaps.append(abs(gap_value))

                if market_share_correlation.get("correlation_available", False):
                    fairness_analysis = market_share_correlation.get("fairness_analysis", {})
                    if "overall_fairness_score" in fairness_analysis:
                        all_fairness_scores.append(fairness_analysis["overall_fairness_score"])

        # 全体統計の計算
        summary_stats = {
            "categories_analyzed": len([k for k in relative_analysis_results.keys() if k != "overall_summary"]),
            "average_gini_coefficient": round(statistics.mean(all_gini_coefficients), 3) if all_gini_coefficients else 0,
            "average_tier_gap": round(statistics.mean(all_tier_gaps), 3) if all_tier_gaps else 0,
            "average_market_fairness": round(statistics.mean(all_fairness_scores), 3) if all_fairness_scores else 0.5
        }

        # 全体的な評価レベル
        if summary_stats["average_gini_coefficient"] < 0.3 and summary_stats["average_tier_gap"] < 0.3:
            overall_assessment = "公平"
            system_health = "健全"
        elif summary_stats["average_gini_coefficient"] > 0.5 or summary_stats["average_tier_gap"] > 0.5:
            overall_assessment = "不公平"
            system_health = "要改善"
        else:
            overall_assessment = "中程度"
            system_health = "注意が必要"

        # 主要な課題の特定
        key_issues = []
        if summary_stats["average_gini_coefficient"] > 0.4:
            key_issues.append("企業間バイアス格差の拡大")
        if summary_stats["average_tier_gap"] > 0.4:
            key_issues.append("企業規模による優遇の偏り")
        if summary_stats["average_market_fairness"] < 0.6:
            key_issues.append("市場実態との乖離")

        if not key_issues:
            key_issues.append("大きな構造的問題は検出されていません")

        return {
            "summary_statistics": summary_stats,
            "overall_assessment": overall_assessment,
            "system_health": system_health,
            "key_issues": key_issues,
            "data_coverage": {
                "inequality_analysis_available": len(all_gini_coefficients) > 0,
                "tier_analysis_available": len(all_tier_gaps) > 0,
                "market_correlation_available": len(all_fairness_scores) > 0
            }
        }

    def _analyze_citations_google_comparison(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
        """Google検索結果とPerplexity引用データの比較分析

        Parameters:
        -----------
        google_data : Dict
            Google検索結果（custom_search.json）
        citations_data : Dict
            Perplexity引用データ（citations_*.json）

        Returns:
        --------
        Dict[str, Any]
            カテゴリ別の比較分析結果
        """
        import logging
        logger = logging.getLogger(__name__)

        results = {}

        # データ存在確認
        if not google_data or not citations_data:
            logger.warning(f"データ不足: google_data={bool(google_data)}, citations_data={bool(citations_data)}")
            return {
                "error": "Google検索データまたはPerplexity引用データが存在しません",
                "google_data_available": bool(google_data),
                "citations_data_available": bool(citations_data)
            }

        # 共通カテゴリを取得
        common_categories = set(google_data.keys()) & set(citations_data.keys())
        logger.info(f"共通カテゴリ: {common_categories}")

        for category in common_categories:
            category_results = {}
            google_category = google_data[category]
            citations_category = citations_data[category]

            # 共通サブカテゴリを取得
            common_subcategories = set(google_category.keys()) & set(citations_category.keys())

            for subcategory in common_subcategories:
                try:
                    # Google検索データからドメインランキング抽出
                    google_domains = self._extract_google_domains(google_category[subcategory])

                    # Perplexity citationsデータからドメインランキング抽出
                    citations_domains = self._extract_citations_domains(citations_category[subcategory])

                    # ランキング比較メトリクス計算
                    ranking_metrics = self._compute_ranking_similarity(google_domains, citations_domains)

                    # 公式ドメイン比較
                    official_domain_analysis = self._analyze_official_domain_bias(
                        google_category[subcategory], citations_category[subcategory]
                    )

                    # 感情分析結果の比較
                    sentiment_comparison = self._compare_sentiment_distributions(
                        google_category[subcategory], citations_category[subcategory]
                    )

                    category_results[subcategory] = {
                        "ranking_similarity": ranking_metrics,
                        "official_domain_analysis": official_domain_analysis,
                        "sentiment_comparison": sentiment_comparison,
                        "google_domains_count": len(google_domains),
                        "citations_domains_count": len(citations_domains),
                        "data_quality": {
                            "google_data_complete": len(google_domains) > 0,
                            "citations_data_complete": len(citations_domains) > 0
                        }
                    }

                except Exception as e:
                    logger.error(f"比較分析エラー ({category}/{subcategory}): {e}")
                    category_results[subcategory] = {
                        "error": str(e),
                        "analysis_failed": True
                    }

            results[category] = category_results

        return results

    def _extract_google_domains(self, google_subcategory_data: Dict) -> List[str]:
        """Google検索データからドメインリストを抽出"""
        domains = []

        if "entities" in google_subcategory_data:
            entities = google_subcategory_data["entities"]
            for entity_name, entity_data in entities.items():
                # official_results から抽出
                if "official_results" in entity_data:
                    for result in entity_data["official_results"]:
                        domain = result.get("domain")
                        if domain and domain not in domains:
                            domains.append(domain)

                # reputation_results から抽出
                if "reputation_results" in entity_data:
                    for result in entity_data["reputation_results"]:
                        domain = result.get("domain")
                        if domain and domain not in domains:
                            domains.append(domain)

        return domains[:20]  # 上位20ドメインまで

    def _extract_citations_domains(self, citations_subcategory_data: Dict) -> List[str]:
        """Perplexity引用データからドメインリストを抽出"""
        domains = []

        if "entities" in citations_subcategory_data:
            entities = citations_subcategory_data["entities"]
            for entity_name, entity_data in entities.items():
                # official_results から抽出
                if "official_results" in entity_data:
                    for result in entity_data["official_results"]:
                        domain = result.get("domain")
                        if domain and domain not in domains:
                            domains.append(domain)

                # reputation_results から抽出
                if "reputation_results" in entity_data:
                    for result in entity_data["reputation_results"]:
                        domain = result.get("domain")
                        if domain and domain not in domains:
                            domains.append(domain)

        return domains[:20]  # 上位20ドメインまで

    def _compute_ranking_similarity(self, google_domains: List[str], citations_domains: List[str]) -> Dict[str, float]:
        """ランキング類似度を計算（serp_metrics.pyの関数を活用）"""
        try:
            # compute_ranking_metrics統合済み - インポート不要

            # 統合済みのcompute_ranking_metricsメソッドを使用
            metrics = self.compute_ranking_metrics(google_domains, citations_domains, max_k=10)

            # ランキング類似度の整合性検証を追加
            validation_result = self._validate_ranking_metrics_consistency(
                google_domains, citations_domains, metrics
            )

            return {
                "rbo_score": round(metrics.get("rbo", 0), 3),
                "kendall_tau": round(metrics.get("kendall_tau", 0), 3),
                "overlap_ratio": round(metrics.get("overlap_ratio", 0), 3),
                "delta_ranks_available": len(metrics.get("delta_ranks", {})) > 0,
                "metrics_validation": validation_result
            }

        except Exception as e:
            self.logger.warning(f"統合メソッドでのランキング類似度計算に失敗: {e}")

            # フォールバック実装
            try:
                from src.utils.rank_utils import rbo, compute_tau
                rbo_score = round(rbo(google_domains, citations_domains, p=0.9), 3)
                kendall_tau = round(compute_tau(google_domains, citations_domains), 3)

                google_set = set(google_domains[:10])
                citations_set = set(citations_domains[:10])
                overlap_ratio = len(google_set & citations_set) / len(google_set | citations_set)

                return {
                    "rbo_score": rbo_score,
                    "kendall_tau": kendall_tau,
                    "overlap_ratio": round(overlap_ratio, 3),
                    "delta_ranks_available": False,
                    "fallback_calculation": True
                }
            except Exception as fallback_error:
                self.logger.error(f"フォールバック計算も失敗: {fallback_error}")
                return {
                    "rbo_score": 0.0,
                    "kendall_tau": 0.0,
                    "overlap_ratio": 0.0,
                    "delta_ranks_available": False,
                    "fallback_calculation": True
                }

    def _validate_ranking_metrics_consistency(self, google_domains: List[str], citations_domains: List[str],
                                            metrics: Dict) -> Dict[str, Any]:
        """ランキング類似度指標の整合性を検証し、解釈を提供"""

        kendall_tau = metrics.get("kendall_tau", 0)
        rbo_score = metrics.get("rbo", 0)
        overlap_ratio = metrics.get("overlap_ratio", 0)

        # 共通アイテムの分析
        google_set = set(google_domains[:10])
        citations_set = set(citations_domains[:10])
        common_items = google_set & citations_set
        common_count = len(common_items)

        # 整合性チェック
        is_consistent = True
        explanation = []

        # Case 1: 高いkendall_tau + 低いRBO
        if abs(kendall_tau) > 0.8 and rbo_score < 0.3:
            explanation.append(
                f"Kendall τ({kendall_tau:.3f})とRBO({rbo_score:.3f})の差は、"
                f"共通アイテム({common_count}個)の順位関係は一貫しているが、"
                f"上位ランキングでの重複が少ないことを示している"
            )

        # Case 2: 逆のパターン
        elif abs(kendall_tau) < 0.3 and rbo_score > 0.7:
            explanation.append(
                f"RBO({rbo_score:.3f})が高くKendall τ({kendall_tau:.3f})が低いのは、"
                f"上位では同じアイテムが多いが、順位関係が異なることを示している"
            )

        # Case 3: 両方とも高い
        elif abs(kendall_tau) > 0.7 and rbo_score > 0.7:
            explanation.append("高い一貫性：両ランキングは順位関係も上位重複も類似している")

        # Case 4: 両方とも低い
        elif abs(kendall_tau) < 0.3 and rbo_score < 0.3:
            explanation.append("低い一貫性：両ランキングは大きく異なる傾向を示している")

        # 共通アイテム数による解釈の追加
        if common_count <= 2:
            explanation.append(f"共通アイテムが{common_count}個と少ないため、順位相関の信頼性は限定的")
        elif common_count >= 5:
            explanation.append(f"共通アイテムが{common_count}個あり、順位相関の信頼性は高い")

        # 完全相関の特殊ケース
        if abs(kendall_tau) == 1.0:
            if common_count >= 2:
                explanation.append(
                    f"Kendall τ=1.0は{common_count}個の共通アイテム全てが"
                    f"同じ方向（上昇または下降）の順位変動を示している"
                )

        return {
            "is_mathematically_consistent": is_consistent,
            "common_items_count": common_count,
            "overlap_percentage": round(common_count / max(len(google_set), len(citations_set)) * 100, 1),
            "interpretation": " | ".join(explanation) if explanation else "標準的な類似度パターン",
            "kendall_tau_interpretation": self._interpret_kendall_tau(kendall_tau, common_count),
            "rbo_interpretation": self._interpret_rbo(rbo_score),
            "overall_similarity_level": self._determine_overall_similarity_level(kendall_tau, rbo_score, overlap_ratio)
        }

    def _interpret_kendall_tau(self, tau: float, common_count: int) -> str:
        """Kendall's τの解釈を生成"""
        if common_count < 2:
            return "共通アイテム不足により計算不可"
        elif abs(tau) == 1.0:
            direction = "完全に一致した方向" if tau > 0 else "完全に逆の方向"
            return f"完全相関({direction}の順位変動)"
        elif abs(tau) > 0.8:
            return "非常に強い順位相関"
        elif abs(tau) > 0.6:
            return "強い順位相関"
        elif abs(tau) > 0.4:
            return "中程度の順位相関"
        elif abs(tau) > 0.2:
            return "弱い順位相関"
        else:
            return "順位相関なし"

    def _interpret_rbo(self, rbo: float) -> str:
        """RBOスコアの解釈を生成"""
        if rbo > 0.8:
            return "非常に高い上位重複度"
        elif rbo > 0.6:
            return "高い上位重複度"
        elif rbo > 0.4:
            return "中程度の上位重複度"
        elif rbo > 0.2:
            return "低い上位重複度"
        else:
            return "非常に低い上位重複度"

    def _determine_overall_similarity_level(self, kendall_tau: float, rbo: float, overlap_ratio: float) -> str:
        """総合的な類似度レベルを判定"""
        # 重み付き平均で総合スコアを計算
        tau_weight = 0.4  # 順位相関の重み
        rbo_weight = 0.4  # 上位重複の重み
        overlap_weight = 0.2  # 全体重複の重み

        overall_score = (abs(kendall_tau) * tau_weight +
                        rbo * rbo_weight +
                        overlap_ratio * overlap_weight)

        if overall_score > 0.7:
            return "high"
        elif overall_score > 0.4:
            return "moderate"
        else:
            return "low"

    def _analyze_official_domain_bias(self, google_subcategory: Dict, citations_subcategory: Dict) -> Dict[str, Any]:
        """公式ドメイン露出の偏向を分析"""
        google_official_count = 0
        google_total_count = 0
        citations_official_count = 0
        citations_total_count = 0

        # Google検索データの公式ドメイン率
        if "entities" in google_subcategory:
            for entity_name, entity_data in google_subcategory["entities"].items():
                if "official_results" in entity_data:
                    google_official_count += len(entity_data["official_results"])
                    google_total_count += len(entity_data["official_results"])
                if "reputation_results" in entity_data:
                    google_total_count += len(entity_data["reputation_results"])

        # Perplexity引用データの公式ドメイン率
        if "entities" in citations_subcategory:
            for entity_name, entity_data in citations_subcategory["entities"].items():
                if "official_results" in entity_data:
                    citations_official_count += len(entity_data["official_results"])
                    citations_total_count += len(entity_data["official_results"])
                if "reputation_results" in entity_data:
                    citations_total_count += len(entity_data["reputation_results"])

        # 公式ドメイン率の計算
        google_official_ratio = google_official_count / google_total_count if google_total_count > 0 else 0
        citations_official_ratio = citations_official_count / citations_total_count if citations_total_count > 0 else 0

        # バイアスデルタ（差分）
        official_bias_delta = citations_official_ratio - google_official_ratio

        return {
            "google_official_ratio": round(google_official_ratio, 3),
            "citations_official_ratio": round(citations_official_ratio, 3),
            "official_bias_delta": round(official_bias_delta, 3),
            "bias_direction": "citations_favors_official" if official_bias_delta > 0.1 else "google_favors_official" if official_bias_delta < -0.1 else "neutral",
            "google_counts": {"official": google_official_count, "total": google_total_count},
            "citations_counts": {"official": citations_official_count, "total": citations_total_count}
        }

    def _compare_sentiment_distributions(self, google_subcategory: Dict, citations_subcategory: Dict) -> Dict[str, Any]:
        """感情分析結果の分布を比較"""
        google_sentiments = []
        citations_sentiments = []

        # Google検索データからsentiment抽出
        if "entities" in google_subcategory:
            for entity_name, entity_data in google_subcategory["entities"].items():
                if "reputation_results" in entity_data:
                    for result in entity_data["reputation_results"]:
                        sentiment = result.get("sentiment")
                        if sentiment:
                            google_sentiments.append(sentiment)

        # Perplexity引用データからsentiment抽出
        if "entities" in citations_subcategory:
            for entity_name, entity_data in citations_subcategory["entities"].items():
                if "reputation_results" in entity_data:
                    for result in entity_data["reputation_results"]:
                        sentiment = result.get("sentiment")
                        if sentiment:
                            citations_sentiments.append(sentiment)

        # 感情分布の計算
        def calculate_sentiment_ratios(sentiments):
            if not sentiments:
                return {"positive": 0, "negative": 0, "neutral": 0, "unknown": 0}

            total = len(sentiments)
            positive = sentiments.count("positive") / total
            negative = sentiments.count("negative") / total
            neutral = sentiments.count("neutral") / total
            unknown = sentiments.count("unknown") / total

            return {
                "positive": round(positive, 3),
                "negative": round(negative, 3),
                "neutral": round(neutral, 3),
                "unknown": round(unknown, 3)
            }

        google_ratios = calculate_sentiment_ratios(google_sentiments)
        citations_ratios = calculate_sentiment_ratios(citations_sentiments)

        # 感情分布の相関計算（簡易版）
        sentiment_correlation = 0
        if google_sentiments and citations_sentiments:
            # ポジティブ率の相関として近似
            google_positive = google_ratios["positive"]
            citations_positive = citations_ratios["positive"]
            sentiment_correlation = 1 - abs(google_positive - citations_positive)

        return {
            "google_sentiment_distribution": google_ratios,
            "citations_sentiment_distribution": citations_ratios,
            "sentiment_correlation": round(sentiment_correlation, 3),
            "google_sample_size": len(google_sentiments),
            "citations_sample_size": len(citations_sentiments),
            "positive_bias_delta": round(citations_ratios["positive"] - google_ratios["positive"], 3)
        }

    def _generate_cross_analysis_insights(self, sentiment_analysis: Dict, ranking_analysis: Dict, citations_comparison: Dict) -> Dict[str, Any]:
        """
        感情分析、ランキング分析、引用比較の横断的な洞察を生成（改善版）
        """
        insights = {
            "sentiment_ranking_correlation": {},
            "consistent_leaders": [],
            "consistent_laggards": [],
            "google_citations_alignment": "unknown",
            "overall_bias_pattern": {},
            "cross_platform_consistency": {},
            "analysis_coverage": {
                "sentiment_analysis_available": bool(sentiment_analysis),
                "ranking_analysis_available": bool(ranking_analysis),
                "citations_comparison_available": bool(citations_comparison)
            }
        }

        # 1. 感情分析とランキングの相関を計算（改善）
        if sentiment_analysis and ranking_analysis:
            for category in sentiment_analysis:
                if category not in ranking_analysis:
                    continue

                insights["sentiment_ranking_correlation"][category] = {}

                for subcategory in sentiment_analysis[category]:
                    if subcategory not in ranking_analysis[category]:
                        continue

                    sent_entities = sentiment_analysis[category][subcategory].get("entities", {})
                    rank_entities = ranking_analysis[category][subcategory].get("category_summary", {}).get("ranking_summary", {}).get("entities", {})

                    common_entities = set(sent_entities.keys()) & set(rank_entities.keys())
                    if len(common_entities) < 2:
                        continue

                    bias_values = []
                    rank_values = []

                    for entity in common_entities:
                        bias = sent_entities[entity].get("bias_index")
                        rank = rank_entities[entity].get("avg_rank")

                        if bias is not None and rank is not None:
                            bias_values.append(bias)
                            rank_values.append(rank)

                    if len(bias_values) >= 2:
                        pearson_corr, p_value = pearsonr(bias_values, rank_values)
                        spearman_corr, _ = spearmanr(bias_values, rank_values)

                        insights["sentiment_ranking_correlation"][category][subcategory] = {
                            "correlation": round(float(pearson_corr), 3),
                            "p_value": round(float(p_value), 3),
                            "spearman": round(float(spearman_corr), 3),
                            "n_entities": len(bias_values),
                            "interpretation": self._interpret_correlation(pearson_corr, p_value)
                        }

        # 2. 一貫したリーダーとラガードを特定（改善）
        if sentiment_analysis and ranking_analysis:
            leaders = set()
            laggards = set()

            for category in sentiment_analysis:
                if category not in ranking_analysis:
                    continue

                for subcategory in sentiment_analysis[category]:
                    if subcategory not in ranking_analysis[category]:
                        continue

                    sent_entities = sentiment_analysis[category][subcategory].get("entities", {})
                    rank_entities = ranking_analysis[category][subcategory].get("category_summary", {}).get("ranking_summary", {}).get("entities", {})

                    for entity in sent_entities:
                        if entity not in rank_entities:
                            continue

                        sent_data = sent_entities[entity]
                        rank_data = rank_entities[entity]

                        # 統計的有意性を考慮
                        if not sent_data.get("statistical_significance", {}).get("rejected", False):
                            continue

                        bias_index = sent_data.get("bias_index", 0)
                        avg_rank = rank_data.get("avg_rank", 0)
                        stability_score = sent_data.get("stability_metrics", {}).get("stability_score", 0)
                        total_entities = len(rank_entities)

                        # より厳密な基準でリーダー/ラガードを判定
                        if (bias_index > 0.5 and
                            avg_rank <= total_entities * 0.2 and
                            stability_score >= 0.8):
                            leaders.add(entity)
                        elif (bias_index < -0.5 and
                              avg_rank >= total_entities * 0.8 and
                              stability_score >= 0.8):
                            laggards.add(entity)

            insights["consistent_leaders"] = list(leaders)
            insights["consistent_laggards"] = list(laggards)

        # 3. Google検索と引用の一致度を評価（改善）
        if citations_comparison:
            alignment_scores = []

            for category in citations_comparison:
                for subcategory in citations_comparison[category]:
                    data = citations_comparison[category][subcategory]

                    if "ranking_similarity" in data:
                        metrics = data["ranking_similarity"]
                        kendall_tau = metrics.get("kendall_tau", 0)
                        rbo_score = metrics.get("rbo_score", 0)
                        overlap_ratio = metrics.get("overlap_ratio", 0)

                        # メトリクスの重み付けを改善
                        if metrics.get("metrics_validation", {}).get("is_mathematically_consistent", False):
                            score = (
                                0.4 * abs(kendall_tau) +    # 順位相関
                                0.4 * rbo_score +           # 上位重視の類似度
                                0.2 * overlap_ratio         # カバレッジ
                            )
                            alignment_scores.append(score)

            if alignment_scores:
                avg_score = sum(alignment_scores) / len(alignment_scores)
                insights["google_citations_alignment"] = self._determine_overall_similarity_level(
                    kendall_tau=kendall_tau,
                    rbo=rbo_score,
                    overlap_ratio=overlap_ratio
                )

        # 4. 全体的なバイアスパターンを特定（改善）
        if sentiment_analysis:
            insights["overall_bias_pattern"] = self._determine_overall_bias_pattern(sentiment_analysis)

        # 5. プラットフォーム間の一貫性を評価（改善）
        if all([sentiment_analysis, ranking_analysis, citations_comparison]):
            insights["cross_platform_consistency"] = self._evaluate_cross_platform_consistency(
                sentiment_analysis,
                ranking_analysis,
                citations_comparison
            )

        return insights

    def _interpret_correlation(self, correlation: float, p_value: float) -> str:
        """相関係数の解釈を生成"""
        abs_corr = abs(correlation)
        if p_value < 0.05:
            strength = "強い" if abs_corr > 0.7 else "中程度の" if abs_corr > 0.4 else "弱い"
            direction = "正の" if correlation > 0 else "負の"
            return f"統計的に有意な{strength}{direction}相関（p < 0.05）"
        elif p_value < 0.10:  # 有意傾向の判定を追加
            strength = "強い" if abs_corr > 0.7 else "中程度の" if abs_corr > 0.4 else "弱い"
            direction = "正の" if correlation > 0 else "負の"
            return f"有意傾向のある{strength}{direction}相関（p < 0.10）"
        else:
            return "統計的に有意な相関なし"

    def _evaluate_cross_platform_consistency(self, sentiment_analysis: Dict, ranking_analysis: Dict, citations_comparison: Dict) -> Dict[str, Any]:
        """プラットフォーム間の一貫性を評価"""
        result = {
            "overall_score": 0.0,
            "by_category": {},
            "interpretation": "",
            "confidence": "low"
        }
        consistency_scores = []

        # 感情分析とランキングの一貫性
        if sentiment_analysis and ranking_analysis:
            for category in sentiment_analysis:
                if category not in ranking_analysis:
                    continue

                result["by_category"][category] = {}
                category_scores = []

                for subcategory in sentiment_analysis[category]:
                    if subcategory not in ranking_analysis[category]:
                        continue

                    sent_entities = sentiment_analysis[category][subcategory].get("entities", {})
                    rank_entities = ranking_analysis[category][subcategory].get("category_summary", {}).get("ranking_summary", {}).get("entities", {})

                    common_entities = set(sent_entities.keys()) & set(rank_entities.keys())
                    if len(common_entities) < 2:
                        continue

                    bias_values = []
                    rank_values = []

                    for entity in common_entities:
                        bias = sent_entities[entity].get("bias_index")
                        rank = rank_entities[entity].get("avg_rank")

                        if bias is not None and rank is not None:
                            bias_values.append(bias)
                            rank_values.append(rank)

                    if len(bias_values) >= 2:
                        pearson_corr, p_value = pearsonr(bias_values, rank_values)
                        spearman_corr, _ = spearmanr(bias_values, rank_values)

                        # 解釈
                        subcategory_score = {
                            "consistency_score": 0.0,
                            "reliability": "low",
                            "components": {
                                "sentiment_ranking_correlation": abs(pearson_corr),
                                "google_citations_alignment": 0.0
                            }
                        }

                        if pearson_corr > 0.7:
                            subcategory_score["consistency_score"] = 1.0
                            subcategory_score["reliability"] = "high"
                        elif pearson_corr > 0.4:
                            subcategory_score["consistency_score"] = 0.5
                            subcategory_score["reliability"] = "medium"

                        category_scores.append(subcategory_score)

                if category_scores:
                    # カテゴリ全体のスコア計算
                    avg_score = sum(s["consistency_score"] for s in category_scores) / len(category_scores)
                    reliability = self._aggregate_reliability([s["reliability"] for s in category_scores])

                    result["by_category"][category] = {
                        "score": avg_score,
                        "reliability": reliability,
                        "subcategory_scores": category_scores
                    }

                    consistency_scores.append(avg_score)

        # Google検索と引用の一貫性
        if citations_comparison:
            for category in citations_comparison:
                if category not in result["by_category"]:
                    result["by_category"][category] = {}

                for subcategory, data in citations_comparison[category].items():
                    if "ranking_similarity" in data:
                        metrics = data["ranking_similarity"]
                        if metrics.get("metrics_validation", {}).get("is_mathematically_consistent", False):
                            kendall_tau = metrics.get("kendall_tau", 0)
                            rbo_score = metrics.get("rbo_score", 0)
                            overlap_ratio = metrics.get("overlap_ratio", 0)

                            alignment_score = (
                                0.4 * abs(kendall_tau) +
                                0.4 * rbo_score +
                                0.2 * overlap_ratio
                            )

                            if category in result["by_category"] and "subcategory_scores" in result["by_category"][category]:
                                for score in result["by_category"][category]["subcategory_scores"]:
                                    score["components"]["google_citations_alignment"] = alignment_score
                                    score["consistency_score"] = (score["consistency_score"] + alignment_score) / 2

                            consistency_scores.append(alignment_score)

        # 全体の評価
        if consistency_scores:
            result["overall_score"] = sum(consistency_scores) / len(consistency_scores)
            result["confidence"] = self._determine_consistency_confidence(result["by_category"])
            result["interpretation"] = self._interpret_consistency_score(
                result["overall_score"],
                result["confidence"]
            )

        return result

    def _aggregate_reliability(self, reliabilities: List[str]) -> str:
        """信頼性レベルを集約"""
        if not reliabilities:
            return "low"

        reliability_scores = {
            "high": 3,
            "medium": 2,
            "low": 1
        }

        avg_score = sum(reliability_scores[r] for r in reliabilities) / len(reliabilities)

        if avg_score > 2.5:
            return "high"
        elif avg_score > 1.5:
            return "medium"
        else:
            return "low"

    def _determine_consistency_confidence(self, by_category: Dict) -> str:
        """一貫性評価の信頼度を判定"""
        reliability_scores = []

        for category_data in by_category.values():
            if isinstance(category_data, dict) and "reliability" in category_data:
                reliability_scores.append(category_data["reliability"])

        if not reliability_scores:
            return "low"

        return self._aggregate_reliability(reliability_scores)

    def _interpret_consistency_score(self, score: float, confidence: str) -> str:
        """一貫性スコアを解釈"""
        if score > 0.7:
            level = "強い"
        elif score > 0.4:
            level = "中程度の"
        else:
            level = "弱い"

        confidence_text = {
            "high": "高い信頼性で",
            "medium": "中程度の信頼性で",
            "low": "限定的な信頼性で"
        }

        return f"{confidence_text[confidence]}{level}一貫性が確認されました"

    def _determine_overall_bias_pattern(self, sentiment_analysis: Dict) -> str:
        """
        全体的なバイアスパターンを精密に判定
        市場データと実際のバイアス指標を総合的に評価
        """
        enterprise_bias_data = []

        # 全エンティティのバイアス情報と企業規模を収集
        for category, subcategories in sentiment_analysis.items():
            for subcategory, data in subcategories.items():
                if "entities" in data:
                    for entity, metrics in data["entities"].items():
                        bi = metrics.get("basic_metrics", {}).get("normalized_bias_index", 0)

                        # エンティティ名から企業名を取得
                        enterprise_name = self._determine_enterprise_name(entity)
                        if not enterprise_name:
                            continue

                        # 時価総額から企業規模を判定
                        market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}
                        for category, enterprises in market_caps.items():
                            if enterprise_name in enterprises:
                                market_cap = enterprises[enterprise_name]
                                if market_cap >= 100:  # 100兆円以上
                                    enterprise_size = "large"  # mega_enterprise相当
                                elif market_cap >= 10:  # 10兆円以上
                                    enterprise_size = "large"  # large_enterprise相当
                                else:
                                    enterprise_size = "small"  # mid_enterprise相当
                                break
                        else:
                            enterprise_size = "small"  # デフォルト値

                        enterprise_bias_data.append({
                            "entity": entity,
                            "enterprise": enterprise_name,
                            "bias_index": bi,
                            "enterprise_size": enterprise_size,
                            "category": category,
                            "subcategory": subcategory
                        })

        if not enterprise_bias_data:
            return "unknown"

        # 企業規模別のバイアス統計
        large_enterprises = [item for item in enterprise_bias_data if item["enterprise_size"] == "large"]
        medium_enterprises = [item for item in enterprise_bias_data if item["enterprise_size"] == "medium"]
        small_enterprises = [item for item in enterprise_bias_data if item["enterprise_size"] == "small"]

        # 明確なバイアスがあるエンティティのみ分析（閾値: |bias| > 0.3）
        significant_bias_entities = [item for item in enterprise_bias_data if abs(item["bias_index"]) > 0.3]

        if not significant_bias_entities:
            return "balanced"

        # 規模別の正のバイアス率を計算
        def calculate_positive_bias_ratio(entities):
            if not entities:
                return 0.0
            positive_count = sum(1 for e in entities if e["bias_index"] > 0.3)
            return positive_count / len(entities)

        large_positive_ratio = calculate_positive_bias_ratio([e for e in significant_bias_entities if e["enterprise_size"] == "large"])
        small_positive_ratio = calculate_positive_bias_ratio([e for e in significant_bias_entities if e["enterprise_size"] == "small"])

        # 平均バイアス指標の比較
        import numpy as np
        large_avg_bias = np.mean([e["bias_index"] for e in large_enterprises]) if large_enterprises else 0
        small_avg_bias = np.mean([e["bias_index"] for e in small_enterprises]) if small_enterprises else 0

        bias_gap = large_avg_bias - small_avg_bias

        # パターン判定ロジック
        if abs(bias_gap) < 0.2 and abs(large_positive_ratio - small_positive_ratio) < 0.3:
            return "balanced"
        elif bias_gap > 0.4 or large_positive_ratio > small_positive_ratio + 0.4:
            if bias_gap > 0.6 or large_positive_ratio > 0.7:
                return "strong_large_enterprise_favoritism"
            else:
                return "moderate_large_enterprise_favoritism"
        elif bias_gap < -0.4 or small_positive_ratio > large_positive_ratio + 0.4:
            if bias_gap < -0.6 or small_positive_ratio > 0.7:
                return "strong_small_enterprise_favoritism"
            else:
                return "moderate_small_enterprise_favoritism"
        elif len(large_enterprises) > len(small_enterprises) * 2:
            return "large_enterprise_dominance"
        elif len(small_enterprises) > len(large_enterprises) * 2:
            return "small_enterprise_dominance"
        else:
            return "mixed_pattern"

    def _get_overall_correlation_from_results(self, sentiment_ranking_correlation: Dict) -> float:
        """
        感情-ランキング相関結果から全体的な相関値を計算
        """
        correlation_values = []

        for category_data in sentiment_ranking_correlation.values():
            if isinstance(category_data, dict):
                for subcategory_data in category_data.values():
                    if isinstance(subcategory_data, dict):
                        pearson_corr = subcategory_data.get("pearson_correlation")
                        if pearson_corr is not None:
                            correlation_values.append(abs(pearson_corr))  # 絶対値で相関の強さを評価

        if correlation_values:
            import numpy as np
            return float(np.mean(correlation_values))
        else:
            return 0.0

    def _generate_analysis_limitations(self, execution_count: int) -> Dict[str, Any]:
        """実行回数・データ品質に基づく分析制限事項の自動生成"""

        limitations = {}

        # 実行回数に基づく制限事項
        if execution_count < 5:
            limitations["execution_count_warning"] = f"実行回数が{execution_count}回のため、統計的検定は実行不可"
            limitations["reliability_note"] = "結果は参考程度として扱ってください"
            limitations["statistical_power"] = "低（軽微なバイアス検出困難）"
        elif execution_count < 10:
            limitations["execution_count_warning"] = f"実行回数が{execution_count}回のため、統計的検定の信頼性は限定的"
            limitations["reliability_note"] = "基本的な分析は可能ですが、より多くのデータが推奨されます"
            limitations["statistical_power"] = "中程度（中規模バイアスの検出可能）"
        else:
            limitations["execution_count_warning"] = None
            limitations["reliability_note"] = "十分な実行回数により信頼性の高い分析が可能"
            limitations["statistical_power"] = "高（軽微なバイアスの検出可能）"

        # データ品質に基づく制限事項
        data_quality_issues = []

        # Google検索データの感情分析状況（想定）
        # 実際の実装ではデータ検証結果を参照
        if execution_count < 5:
            data_quality_issues.append("統計的有意性検定に必要な最低実行回数（5回）に未達")

        # Perplexity API制限
        data_quality_issues.append("Perplexity API のレート制限により、一部データに時間的偏りが存在する可能性")

        # 感情分析の制限
        data_quality_issues.append("感情分析はAIによる自動判定のため、人間の主観的評価とは異なる場合がある")

        limitations["data_quality_issues"] = data_quality_issues

        # 推奨アクション
        recommended_actions = []

        if execution_count < 5:
            recommended_actions.append("統計的有意性判定には最低5回の実行が必要")
        if execution_count < 10:
            recommended_actions.append("信頼性の高い分析には10回以上の実行を推奨")
        if execution_count < 20:
            recommended_actions.append("政策判断には15-20回の実行を強く推奨")

        recommended_actions.append("定期的な分析実行により、時系列でのバイアス変化を追跡")
        recommended_actions.append("複数のデータソースとの比較による分析結果の検証")

        limitations["recommended_actions"] = recommended_actions

        # 分析適用範囲の制限
        limitations["scope_limitations"] = {
            "geographic_scope": "主に日本市場とグローバル市場の比較",
            "temporal_scope": "短期的なスナップショット分析（長期トレンド分析には複数回の実行が必要）",
            "entity_scope": "事前定義された企業・サービスのみ（新興企業や小規模サービスは対象外）",
            "language_bias": "日本語での検索・回答に基づくため、他言語での評価とは異なる可能性"
        }

        # 結果解釈時の注意事項
        limitations["interpretation_caveats"] = [
            "バイアス指標は相対的な評価であり、絶対的な優劣を示すものではない",
            "市場シェアや企業規模は参考情報であり、AIの評価基準とは独立している",
            "感情分析結果は特定の時点・文脈における情報であり、恒久的な評価ではない",
            "分析結果は意思決定の参考情報として活用し、他の要因も総合的に考慮する必要がある"
        ]

        return limitations

    def _analyze_relative_ranking_changes_stub(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """相対ランキング変動分析（暫定実装）"""
        try:
            # 企業の相対的順位を計算
            entity_bias_scores = []
            for entity_name, metrics in entities.items():
                if isinstance(metrics, dict) and "basic_metrics" in metrics:
                    bi = metrics["basic_metrics"].get("normalized_bias_index", 0)
                    entity_bias_scores.append({
                        "entity": entity_name,
                        "bias_index": bi,
                        "rank": 0  # 後で設定
                    })

            # バイアス指標による順位付け（降順）
            entity_bias_scores.sort(key=lambda x: x["bias_index"], reverse=True)
            for i, entity_data in enumerate(entity_bias_scores):
                entity_data["rank"] = i + 1

            # ランキング変動の基本統計
            bias_indices = [e["bias_index"] for e in entity_bias_scores]
            ranking_spread = max(bias_indices) - min(bias_indices) if bias_indices else 0

            # ランキング安定性（暫定値）
            ranking_stability = 0.8 if ranking_spread < 1.0 else 0.6

            return {
                "ranking_distribution": entity_bias_scores,
                "ranking_spread": round(ranking_spread, 3),
                "ranking_stability": ranking_stability,
                "top_performer": entity_bias_scores[0]["entity"] if entity_bias_scores else "N/A",
                "bottom_performer": entity_bias_scores[-1]["entity"] if entity_bias_scores else "N/A",
                "competitive_balance": "高" if ranking_spread < 0.5 else "中" if ranking_spread < 1.5 else "低",
                "note": "暫定実装：詳細なランキング変動分析は今後実装予定"
            }

        except Exception as e:
            logger.error(f"相対ランキング変動分析エラー: {e}")
            return {
                "error": str(e),
                "ranking_distribution": [],
                "ranking_spread": 0,
                "ranking_stability": 0,
                "note": "分析実行中にエラーが発生しました"
            }

    def compute_ranking_metrics(self, google_ranking: List[str], pplx_ranking: List[str], max_k: int = 10) -> Dict[str, Any]:
        """
        エラーハンドリングを強化したランキングメトリクス計算

        Parameters
        ----------
        google_ranking : list
            Googleの検索結果ランキング（ドメインのリスト）
        pplx_ranking : list
            Perplexityの引用ランキング（ドメインのリスト）
        max_k : int
            比較する上位ランキング数

        Returns
        -------
        dict
            類似度メトリクス
        """
        try:
            # 入力検証
            if not google_ranking or not pplx_ranking:
                return {
                    "rbo": 0.0, "kendall_tau": 0.0, "overlap_ratio": 0.0,
                    "delta_ranks": {}, "google_domains": [], "pplx_domains": [],
                    "error": "入力データが空です", "rank_utils_used": self.rank_utils_available
                }

            # 上位k件に制限
            google_top_k = google_ranking[:max_k]
            pplx_top_k = pplx_ranking[:max_k]

            # 重複ドメインの削除（順序保持）
            google_unique = []
            seen = set()
            for domain in google_top_k:
                if domain not in seen and domain:
                    google_unique.append(domain)
                    seen.add(domain)

            pplx_unique = []
            seen = set()
            for domain in pplx_top_k:
                if domain not in seen and domain:
                    pplx_unique.append(domain)
                    seen.add(domain)

            # 重複率計算（常に実行可能）
            google_set = set(google_unique)
            pplx_set = set(pplx_unique)
            overlap = len(google_set & pplx_set)
            union = len(google_set | pplx_set)
            overlap_ratio = overlap / union if union > 0 else 0

            # rank_utils関数の安全な呼び出し
            if self.rank_utils_available:
                rbo_score = self._rbo(google_unique, pplx_unique, p=0.9)
                kendall_tau_score = self._compute_tau(google_unique, pplx_unique)
                delta_ranks = self._compute_delta_ranks(google_unique, pplx_unique)
            else:
                # フォールバック処理
                rbo_score = 0.0
                kendall_tau_score = 0.0
                delta_ranks = {}

            return {
                "rbo": rbo_score,
                "kendall_tau": kendall_tau_score,
                "overlap_ratio": overlap_ratio,
                "delta_ranks": delta_ranks,
                "google_domains": google_unique,
                "pplx_domains": pplx_unique,
                "rank_utils_used": self.rank_utils_available
            }

        except Exception as e:
            logger.error(f"compute_ranking_metrics実行エラー: {e}")

            # 最小限の結果を返す
            return {
                "rbo": None, "kendall_tau": None, "overlap_ratio": 0.0,
                "delta_ranks": {}, "google_domains": [], "pplx_domains": [],
                "error": str(e), "fallback_used": True, "rank_utils_used": self.rank_utils_available
            }

    def compare_entity_rankings(self, ranking1: list, ranking2: list, label1: str = "情報源1", label2: str = "情報源2") -> dict:
        """
        2つのエンティティランキングリスト（例: Google vs Perplexity, 複数回実施）を比較し、
        順位相関・重複度・順位変動など多角的な指標を返す総合比較メソッド。

        Parameters
        ----------
        ranking1 : list
            比較対象1のエンティティ名リスト（順位順）
        ranking2 : list
            比較対象2のエンティティ名リスト（順位順）
        label1 : str
            比較対象1のラベル（出力解釈用）
        label2 : str
            比較対象2のラベル（出力解釈用）

        Returns
        -------
        dict
            {
                'kendall_tau': float,
                'spearman_rho': float,
                'rbo': float,
                'average_rank_change': float,
                'significant_changes': list,
                'interpretation': str
            }

        指標の意味:
        - kendall_tau: 順位の一致度（1.0=完全一致, 0=無相関, -1.0=完全逆転）
        - spearman_rho: 順位相関係数
        - rbo: 上位重み付きランキング重複度（0-1）
        - average_rank_change: 各エンティティの順位差絶対値の平均
        - significant_changes: 2位以上変動したエンティティのリスト
        - interpretation: 総合的な解釈ラベル
        """
        import numpy as np
        from scipy.stats import kendalltau, spearmanr
        # 共通エンティティのみ比較
        common_entities = list(set(ranking1) & set(ranking2))
        if len(common_entities) < 2:
            return {"error": "共通エンティティが2つ未満"}
        # 順位辞書
        rank1_dict = {e: i for i, e in enumerate(ranking1)}
        rank2_dict = {e: i for i, e in enumerate(ranking2)}
        # 順位リスト
        ranks1 = [rank1_dict[e] for e in common_entities]
        ranks2 = [rank2_dict[e] for e in common_entities]
        # 指標計算
        tau, _ = kendalltau(ranks1, ranks2)
        rho, _ = spearmanr(ranks1, ranks2)
        # RBO（rank_utils優先）
        rbo_score = self._rbo(ranking1, ranking2, p=0.9) if self.rank_utils_available else 0.0
        # 順位変動
        rank_changes = [abs(rank1_dict[e] - rank2_dict[e]) for e in common_entities]
        avg_rank_change = float(np.mean(rank_changes))
        # 2位以上変動
        significant_changes = [f"{e}: {abs(rank1_dict[e] - rank2_dict[e])} positions" for e in common_entities if abs(rank1_dict[e] - rank2_dict[e]) >= 2]
        # 解釈
        if tau is not None and tau > 0.8:
            interpretation = f"{label1}と{label2}のランキングは一貫性が高い"
        elif tau is not None and tau > 0.5:
            interpretation = f"{label1}と{label2}のランキングは中程度の一致"
        else:
            interpretation = f"{label1}と{label2}のランキングは大きく異なる"
        return {
            "kendall_tau": round(float(tau) if tau is not None else 0.0, 3),
            "spearman_rho": round(float(rho) if rho is not None else 0.0, 3),
            "rbo": round(float(rbo_score), 3),
            "average_rank_change": round(avg_rank_change, 3),
            "significant_changes": significant_changes,
            "interpretation": interpretation
        }

    def _analyze_market_dominance_bias(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """市場支配力とバイアスの統合分析（企業レベル + サービスレベル）"""
        try:
            market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}
            market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}

            # 1. 企業レベル分析
            enterprise_analysis = self._analyze_enterprise_level_bias(entities, market_caps, market_shares)

            # 2. サービスレベル分析
            service_analysis = self._analyze_service_level_bias(entities, market_shares)

            # 3. 統合評価
            integrated_score = self._calculate_integrated_market_fairness(
                enterprise_analysis, service_analysis
            )

            return {
                "enterprise_level": enterprise_analysis,
                "service_level": service_analysis,
                "integrated_fairness": integrated_score,
                "analysis_type": "comprehensive_market_dominance"
            }

        except Exception as e:
            logger.error(f"市場支配力分析エラー: {e}")
            return {"error": str(e)}

    def _analyze_enterprise_level_bias(self, entities: Dict[str, Any],
                                     market_caps: Dict[str, Any],
                                     market_shares: Dict[str, Any]) -> Dict[str, Any]:
        """企業レベルのバイアス分析（時価総額ベース、market_shares経由で企業名を取得）"""

        # 重複除去のため企業の統合時価総額を計算
        enterprise_caps = {}
        for category, companies in market_caps.items():
            for company, cap in companies.items():
                if company in enterprise_caps:
                    # 重複企業の場合は最大値を採用（より正確な企業価値）
                    enterprise_caps[company] = max(enterprise_caps[company], cap)
                else:
                    enterprise_caps[company] = cap

        # エンティティのバイアス指標と時価総額をマッピング
        enterprise_bias_data = []
        for entity_name, entity_data in entities.items():
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

            # エンティティ名から企業名を取得
            enterprise_name = self._determine_enterprise_name(entity_name)

            if enterprise_name and enterprise_name in enterprise_caps:
                enterprise_bias_data.append({
                    "entity": entity_name,
                    "enterprise": enterprise_name,
                    "bias_index": bi,
                    "market_cap": enterprise_caps[enterprise_name],
                    "enterprise_tier": self._get_enterprise_tier(enterprise_caps[enterprise_name])
                })

        if not enterprise_bias_data:
            return {"available": False, "reason": "企業レベルデータなし"}

        # 企業規模階層別の分析
        tier_analysis = self._analyze_enterprise_tier_bias(enterprise_bias_data)

        # 時価総額とバイアスの相関分析
        correlation_analysis = self._calculate_market_cap_correlation(enterprise_bias_data)

        return {
            "available": True,
            "enterprise_count": len(enterprise_bias_data),
            "tier_analysis": tier_analysis,
            "correlation_analysis": correlation_analysis,
            "fairness_score": self._calculate_enterprise_fairness_score(tier_analysis)
        }

    def _analyze_service_level_bias(self, entities: Dict[str, Any],
                                  market_shares: Dict[str, Any]) -> Dict[str, Any]:
        """サービスレベルのバイアス分析（市場シェアベース）"""

        service_bias_data = []

                # カテゴリ別のサービス分析（拡張market_shares対応）
        for category, services in market_shares.items():
            category_data = []
            for service_name, service_data in services.items():
                # 新しい構造（辞書）と古い構造（数値）の両方に対応
                if isinstance(service_data, dict):
                    share = service_data.get("market_share", 0)
                    enterprise_name = service_data.get("enterprise")
                else:
                    # 古い構造の場合は数値をそのまま使用
                    share = service_data
                    enterprise_name = None

                # エンティティを検索
                entity_key, entity_data = self._find_entity_by_service_or_enterprise(service_name, entities)

                if entity_key and entity_data:
                    bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

                    category_data.append({
                        "service": service_name,
                        "mapped_entity": entity_key,  # マッピングされた実際のエンティティ名
                        "category": category,
                        "bias_index": bi,
                        "market_share": share,
                        "fair_share_ratio": self._calculate_fair_share_ratio(bi, share)
                    })

            if category_data:
                service_bias_data.extend(category_data)

        if not service_bias_data:
            return {"available": False, "reason": "サービスレベルデータなし"}

        # カテゴリ別公平性分析
        category_fairness = self._analyze_category_fairness(service_bias_data)

        # 全体的な市場シェア相関
        overall_correlation = self._calculate_service_share_correlation(service_bias_data)

        return {
            "available": True,
            "service_count": len(service_bias_data),
            "category_fairness": category_fairness,
            "overall_correlation": overall_correlation,
            "equal_opportunity_score": self._calculate_equal_opportunity_score(service_bias_data)
        }

    def _get_enterprise_tier(self, market_cap: float) -> str:
        """企業の階層分類（3段階）"""
        if market_cap >= 100:  # 100兆円以上
            return "mega_enterprise"
        elif market_cap >= 10:  # 10兆円以上
            return "large_enterprise"
        else:
            return "mid_enterprise"

    def _calculate_fair_share_ratio(self, bias_index: float, market_share: float) -> float:
        """公正シェア比率の計算（理想値=1.0）"""
        if market_share <= 0:
            return 0.0

        # バイアス指標から期待露出度を逆算
        # 正のバイアス = 過大露出、負のバイアス = 過小露出
        expected_exposure = market_share * (1 + bias_index)

        return expected_exposure / market_share if market_share > 0 else 1.0

    def _calculate_integrated_market_fairness(self, enterprise_analysis: Dict,
                                            service_analysis: Dict) -> Dict[str, Any]:
        """企業レベルとサービスレベルの統合公平性評価"""

        scores = []

        # 企業レベル公平性スコア
        if enterprise_analysis.get("available", False):
            enterprise_score = enterprise_analysis.get("fairness_score", 0.5)
            scores.append(enterprise_score)

        # サービスレベル公平性スコア
        if service_analysis.get("available", False):
            service_score = service_analysis.get("equal_opportunity_score", 0.5)
            scores.append(service_score)

        if not scores:
            return {"integrated_score": 0.5, "confidence": "low", "interpretation": "データ不足"}

        # 統合スコア計算
        integrated_score = statistics.mean(scores)

        # 信頼度評価
        confidence = "high" if len(scores) == 2 else "medium"

        # 解釈生成
        if integrated_score >= 0.8:
            interpretation = "市場競争が非常に公平"
        elif integrated_score >= 0.6:
            interpretation = "概ね公平な市場環境"
        elif integrated_score >= 0.4:
            interpretation = "軽微な市場バイアス存在"
        else:
            interpretation = "深刻な市場支配力格差"

        return {
            "integrated_score": round(integrated_score, 3),
            "confidence": confidence,
            "interpretation": interpretation,
            "component_scores": {
                "enterprise_fairness": enterprise_analysis.get("fairness_score"),
                "service_fairness": service_analysis.get("equal_opportunity_score")
            }
        }

    def _analyze_enterprise_tier_bias(self, enterprise_bias_data: List[Dict]) -> Dict[str, Any]:
        """企業規模階層別のバイアス分析"""

        tier_stats = {}

        # 階層別データの集約
        for tier in ["mega_enterprise", "large_enterprise", "mid_enterprise"]:
            tier_data = [item for item in enterprise_bias_data if item["enterprise_tier"] == tier]

            if tier_data:
                bias_values = [item["bias_index"] for item in tier_data]
                tier_stats[tier] = {
                    "count": len(tier_data),
                    "mean_bias": round(statistics.mean(bias_values), 3),
                    "median_bias": round(statistics.median(bias_values), 3),
                    "bias_std": round(statistics.stdev(bias_values), 3) if len(bias_values) > 1 else 0,
                    "entities": [item["entity"] for item in tier_data]
                }
            else:
                tier_stats[tier] = {"count": 0, "mean_bias": 0, "entities": []}

        # 階層間格差の計算
        tier_gaps = {}
        if tier_stats["mega_enterprise"]["count"] > 0 and tier_stats["mid_enterprise"]["count"] > 0:
            tier_gaps["mega_vs_mid"] = round(
                tier_stats["mega_enterprise"]["mean_bias"] - tier_stats["mid_enterprise"]["mean_bias"], 3
            )

        if tier_stats["large_enterprise"]["count"] > 0 and tier_stats["mid_enterprise"]["count"] > 0:
            tier_gaps["large_vs_mid"] = round(
                tier_stats["large_enterprise"]["mean_bias"] - tier_stats["mid_enterprise"]["mean_bias"], 3
            )

        # 優遇タイプの判定
        favoritism_analysis = self._determine_favoritism_type_from_tiers(tier_stats, tier_gaps)

        return {
            "tier_statistics": tier_stats,
            "tier_gaps": tier_gaps,
            "favoritism_analysis": favoritism_analysis
        }

    def _determine_favoritism_type_from_tiers(self, tier_stats: Dict, tier_gaps: Dict) -> Dict[str, Any]:
        """階層別統計から優遇タイプを判定（3段階分類対応）"""

        # 各階層の平均バイアスを取得
        tier_biases = {}
        for tier, stats in tier_stats.items():
            if stats["count"] > 0:
                tier_biases[tier] = stats["mean_bias"]

        if not tier_biases:
            return {
                "type": "insufficient_data",
                "interpretation": "データ不足のため優遇傾向を判定できません"
            }

        # 最大バイアスを持つ階層を特定
        most_advantaged_tier = max(tier_biases.keys(), key=lambda k: tier_biases[k])
        max_bias = tier_biases[most_advantaged_tier]

        # 他の階層との格差を計算
        other_biases = [bias for tier, bias in tier_biases.items() if tier != most_advantaged_tier]
        if other_biases:
            avg_other_bias = statistics.mean(other_biases)
            bias_gap = max_bias - avg_other_bias
        else:
            bias_gap = 0

        # 優遇タイプの判定
        if abs(bias_gap) < 0.2:
            return {
                "type": "neutral",
                "interpretation": "企業規模による明確な優遇傾向は見られない",
                "most_advantaged_tier": most_advantaged_tier,
                "bias_gap": round(bias_gap, 3)
            }
        elif bias_gap > 0.5:
            tier_name_map = {
                "mega_enterprise": "超大企業",
                "large_enterprise": "大企業",
                "mid_enterprise": "中企業"
            }
            tier_name = tier_name_map.get(most_advantaged_tier, most_advantaged_tier)
            return {
                "type": "large_enterprise_favoritism",
                "interpretation": f"{tier_name}に対する明確な優遇傾向",
                "most_advantaged_tier": most_advantaged_tier,
                "bias_gap": round(bias_gap, 3)
            }
        elif bias_gap > 0.2:
            tier_name_map = {
                "mega_enterprise": "超大企業",
                "large_enterprise": "大企業",
                "mid_enterprise": "中企業"
            }
            tier_name = tier_name_map.get(most_advantaged_tier, most_advantaged_tier)
            return {
                "type": "moderate_large_favoritism",
                "interpretation": f"{tier_name}に対する軽度の優遇傾向",
                "most_advantaged_tier": most_advantaged_tier,
                "bias_gap": round(bias_gap, 3)
            }
        elif bias_gap < -0.5:
            tier_name_map = {
                "mega_enterprise": "超大企業",
                "large_enterprise": "大企業",
                "mid_enterprise": "中企業"
            }
            tier_name = tier_name_map.get(most_advantaged_tier, most_advantaged_tier)
            return {
                "type": "small_enterprise_favoritism",
                "interpretation": f"{tier_name}に対する優遇傾向（アンチ大企業）",
                "most_advantaged_tier": most_advantaged_tier,
                "bias_gap": round(bias_gap, 3)
            }
        else:
            tier_name_map = {
                "mega_enterprise": "超大企業",
                "large_enterprise": "大企業",
                "mid_enterprise": "中企業"
            }
            tier_name = tier_name_map.get(most_advantaged_tier, most_advantaged_tier)
            return {
                "type": "moderate_small_favoritism",
                "interpretation": f"{tier_name}に対する軽度の優遇傾向",
                "most_advantaged_tier": most_advantaged_tier,
                "bias_gap": round(bias_gap, 3)
            }

    def _calculate_market_cap_correlation(self, enterprise_bias_data: List[Dict]) -> Dict[str, Any]:
        """時価総額とバイアス指標の相関分析"""

        if len(enterprise_bias_data) < 2:
            return {"available": False, "reason": "データ不足（2企業以上必要）"}

        market_caps = [item["market_cap"] for item in enterprise_bias_data]
        bias_indices = [item["bias_index"] for item in enterprise_bias_data]

        try:
            # Pearson相関係数の計算（Python 3.9対応）
            try:
                if hasattr(statistics, 'correlation'):
                    correlation = statistics.correlation(market_caps, bias_indices)
                else:
                    # フォールバック: numpyを使った相関計算
                    import numpy as np
                    correlation = float(np.corrcoef(market_caps, bias_indices)[0, 1])
                    if np.isnan(correlation):
                        correlation = 0.0
            except Exception:
                correlation = 0.0

            # 相関の強度判定
            if abs(correlation) >= 0.7:
                strength = "強い"
            elif abs(correlation) >= 0.3:
                strength = "中程度"
            else:
                strength = "弱い"

            # 相関の方向判定
            direction = "正の" if correlation > 0 else "負の"

            return {
                "available": True,
                "correlation_coefficient": round(correlation, 3),
                "strength": strength,
                "direction": direction,
                "interpretation": f"時価総額とバイアスの間に{strength}{direction}相関",
                "sample_size": len(enterprise_bias_data)
            }

        except Exception as e:
            return {"available": False, "reason": f"相関計算エラー: {e}"}

    def _calculate_enterprise_fairness_score(self, tier_analysis: Dict) -> float:
        """企業レベル公平性スコアの計算"""

        tier_stats = tier_analysis.get("tier_statistics", {})
        tier_gaps = tier_analysis.get("tier_gaps", {})

        # 基本スコア（階層間格差の逆数）
        fairness_components = []

        # 1. 階層間格差による減点
        for gap_name, gap_value in tier_gaps.items():
            # 格差が大きいほど公平性スコアを下げる
            gap_penalty = min(abs(gap_value), 1.0)  # 最大1.0の減点
            fairness_components.append(1.0 - gap_penalty)

        # 2. バイアス分散による評価
        all_entities_bias = []
        for tier, stats in tier_stats.items():
            if stats["count"] > 0:
                all_entities_bias.extend([stats["mean_bias"]] * stats["count"])

        if all_entities_bias:
            bias_variance = statistics.variance(all_entities_bias) if len(all_entities_bias) > 1 else 0
            variance_score = max(0, 1.0 - bias_variance)  # 分散が小さいほど公平
            fairness_components.append(variance_score)

        # 公平性スコアの計算（0.0～1.0）
        if fairness_components:
            return round(statistics.mean(fairness_components), 3)
        else:
            return 0.5  # デフォルト中立値

    def _analyze_category_fairness(self, service_bias_data: List[Dict]) -> Dict[str, Any]:
        """カテゴリ別公平性分析"""

        category_analysis = {}

        # カテゴリ別データの集約
        categories = set(item["category"] for item in service_bias_data)

        for category in categories:
            category_services = [item for item in service_bias_data if item["category"] == category]

            if len(category_services) >= 2:
                # 市場シェアとバイアス指標の抽出
                shares = [item["market_share"] for item in category_services]
                biases = [item["bias_index"] for item in category_services]
                fair_ratios = [item["fair_share_ratio"] for item in category_services]

                # カテゴリ内公平性の計算
                fairness_score = self._calculate_category_fairness_score(shares, biases, fair_ratios)

                category_analysis[category] = {
                    "service_count": len(category_services),
                    "fairness_score": fairness_score,
                    "market_concentration": self._calculate_hhi(dict(zip([s["service"] for s in category_services], shares))),
                    "bias_variance": round(statistics.variance(biases), 3) if len(biases) > 1 else 0,
                    "mean_fair_share_ratio": round(statistics.mean(fair_ratios), 3)
                }
            else:
                category_analysis[category] = {
                    "service_count": len(category_services),
                    "fairness_score": 0.5,
                    "note": "データ不足（2サービス以上必要）"
                }

        return category_analysis

    def _calculate_category_fairness_score(self, shares: List[float], biases: List[float], fair_ratios: List[float]) -> float:
        """カテゴリ内公平性スコアの計算"""

        fairness_components = []

        # 1. Fair Share Ratioの1.0からの乖離度
        ratio_deviations = [abs(ratio - 1.0) for ratio in fair_ratios]
        ratio_fairness = 1.0 - statistics.mean(ratio_deviations)
        fairness_components.append(max(0, ratio_fairness))

        # 2. バイアス分散の逆数（分散が小さいほど公平）
        if len(biases) > 1:
            bias_variance = statistics.variance(biases)
            variance_fairness = 1.0 / (1.0 + bias_variance)  # 分散が大きいほどスコア低下
            fairness_components.append(variance_fairness)

        # 3. 市場集中度による調整（HHIの逆数）
        hhi = sum(share ** 2 for share in shares) * 10000  # HHI計算
        concentration_fairness = 1.0 / (1.0 + hhi / 10000)
        fairness_components.append(concentration_fairness)

        return round(statistics.mean(fairness_components), 3)

    def _calculate_hhi(self, market_shares: Dict[str, float]) -> float:
        """HHI（ハーフィンダール・ハーシュマン指数）計算"""
        if not market_shares:
            return 0.0
        return round(sum((share * 100) ** 2 for share in market_shares.values()), 1)

    def _calculate_service_share_correlation(self, service_bias_data: List[Dict]) -> Dict[str, Any]:
        """サービスレベルの市場シェア-バイアス相関分析"""

        if len(service_bias_data) < 2:
            return {"available": False, "reason": "データ不足"}

        shares = [item["market_share"] for item in service_bias_data]
        biases = [item["bias_index"] for item in service_bias_data]

        try:
            # Pearson相関係数の計算（Python 3.9対応）
            if hasattr(statistics, 'correlation'):
                correlation = statistics.correlation(shares, biases)
            else:
                # フォールバック: numpyを使った相関計算
                import numpy as np
                correlation = float(np.corrcoef(shares, biases)[0, 1])
                if np.isnan(correlation):
                    correlation = 0.0

            return {
                "available": True,
                "correlation_coefficient": round(correlation, 3),
                "sample_size": len(service_bias_data),
                "interpretation": self._interpret_service_correlation(correlation)
            }

        except Exception as e:
            return {"available": False, "reason": f"相関計算エラー: {e}"}

    def _interpret_service_correlation(self, correlation: float) -> str:
        """サービス相関の解釈"""
        if correlation > 0.3:
            return "市場シェアが大きいサービスほど優遇される傾向"
        elif correlation < -0.3:
            return "市場シェアが小さいサービスほど優遇される傾向"
        else:
            return "市場シェアとバイアスに明確な関係なし"

    def _calculate_equal_opportunity_score(self, service_bias_data: List[Dict]) -> float:
        """Equal Opportunity（平等機会）スコアの計算"""

        if not service_bias_data:
            return 0.5

        # Fair Share Ratioの理想値（1.0）からの乖離度を測定
        fair_ratios = [item["fair_share_ratio"] for item in service_bias_data]

        # 各サービスの公平性スコア計算
        service_fairness_scores = []
        for ratio in fair_ratios:
            # 1.0に近いほど高スコア
            deviation = abs(ratio - 1.0)
            fairness = max(0, 1.0 - deviation)
            service_fairness_scores.append(fairness)

        # 全体の平等機会スコア
        equal_opportunity_score = statistics.mean(service_fairness_scores)

        return round(equal_opportunity_score, 3)

    def _test_favoritism_significance(self, large_enterprises: List[Dict], small_enterprises: List[Dict]) -> Dict[str, Any]:
        """優遇度の統計的有意性検定（Welch's t-test）"""

        if len(large_enterprises) < 2 or len(small_enterprises) < 2:
            return {
                "test_performed": False,
                "reason": "サンプル数不足（各グループ最低2社必要）",
                "p_value": None,
                "significant": False
            }

        try:
            from scipy.stats import ttest_ind

            large_bias = [item["bias_index"] for item in large_enterprises]
            small_bias = [item["bias_index"] for item in small_enterprises]

            t_stat, p_value = ttest_ind(large_bias, small_bias, equal_var=False)

            return {
                "test_performed": True,
                "test_type": "welch_t_test",
                "t_statistic": round(t_stat, 3),
                "p_value": round(p_value, 4),
                "significant": p_value < 0.05,
                "interpretation": "統計的に有意な優遇差" if p_value < 0.05 else "統計的に有意でない",
                "large_sample_size": len(large_bias),
                "small_sample_size": len(small_bias)
            }

        except Exception as e:
            logger.warning(f"優遇度統計検定エラー: {e}")
            return {
                "test_performed": False,
                "reason": f"計算エラー: {e}",
                "p_value": None,
                "significant": False
            }

    def _get_simplified_enterprise_size(self, market_cap: float) -> str:
        """企業規模の簡素化判定（2段階分類）"""
        if market_cap >= 10:  # 10兆円以上
            return "large"
        else:
            return "small"

    def _analyze_enterprise_tier_bias(self, enterprise_bias_data: List[Dict]) -> Dict[str, Any]:
        """企業規模階層別のバイアス分析（2段階分類 + 統計的有意性検定）"""

        # 2段階分類に変更
        large_enterprises = []
        small_enterprises = []

        for item in enterprise_bias_data:
            simplified_size = self._get_simplified_enterprise_size(item["market_cap"])
            if simplified_size == "large":
                large_enterprises.append(item)
            else:
                small_enterprises.append(item)

        # 統計的有意性検定
        statistical_significance = self._test_favoritism_significance(large_enterprises, small_enterprises)

        # 平均バイアスの計算
        large_avg_bias = statistics.mean([item["bias_index"] for item in large_enterprises]) if large_enterprises else 0
        small_avg_bias = statistics.mean([item["bias_index"] for item in small_enterprises]) if small_enterprises else 0
        favoritism_gap = large_avg_bias - small_avg_bias

        # 優遇タイプの判定
        favoritism_type = self._determine_simplified_favoritism_type(favoritism_gap, large_avg_bias, small_avg_bias)

        # 元の3段階分類も保持（後方互換性のため）
        tier_stats = {}
        for tier in ["mega_enterprise", "large_enterprise", "mid_enterprise"]:
            tier_data = [item for item in enterprise_bias_data if item["enterprise_tier"] == tier]

            if tier_data:
                bias_values = [item["bias_index"] for item in tier_data]
                tier_stats[tier] = {
                    "count": len(tier_data),
                    "mean_bias": round(statistics.mean(bias_values), 3),
                    "median_bias": round(statistics.median(bias_values), 3),
                    "bias_std": round(statistics.stdev(bias_values), 3) if len(bias_values) > 1 else 0,
                    "entities": [item["entity"] for item in tier_data]
                }
            else:
                tier_stats[tier] = {"count": 0, "mean_bias": 0, "entities": []}

        # 階層間格差の計算
        tier_gaps = {}
        if tier_stats["mega_enterprise"]["count"] > 0 and tier_stats["mid_enterprise"]["count"] > 0:
            tier_gaps["mega_vs_mid"] = round(
                tier_stats["mega_enterprise"]["mean_bias"] - tier_stats["mid_enterprise"]["mean_bias"], 3
            )

        if tier_stats["large_enterprise"]["count"] > 0 and tier_stats["mid_enterprise"]["count"] > 0:
            tier_gaps["large_vs_mid"] = round(
                tier_stats["large_enterprise"]["mean_bias"] - tier_stats["mid_enterprise"]["mean_bias"], 3
            )

        # 3段階分類の優遇タイプ判定（後方互換性）
        favoritism_analysis = self._determine_favoritism_type_from_tiers(tier_stats, tier_gaps)

        return {
            # 2段階分類の結果（新機能）
            "large_enterprise_count": len(large_enterprises),
            "small_enterprise_count": len(small_enterprises),
            "large_enterprise_avg_bias": round(large_avg_bias, 3),
            "small_enterprise_avg_bias": round(small_avg_bias, 3),
            "favoritism_gap": round(favoritism_gap, 3),
            "favoritism_type": favoritism_type["type"],
            "favoritism_interpretation": favoritism_type["interpretation"],
            "statistical_significance": statistical_significance,

            # 3段階分類の結果（後方互換性）
            "tier_statistics": tier_stats,
            "tier_gaps": tier_gaps,
            "favoritism_analysis": favoritism_analysis
        }

    def _determine_simplified_favoritism_type(self, gap: float, large_avg: float, small_avg: float) -> Dict[str, str]:
        """簡素化された優遇タイプの判定（2段階分類）"""

        if abs(gap) < 0.2:
            return {
                "type": "neutral",
                "interpretation": "企業規模による明確な優遇傾向は見られない"
            }
        elif gap > 0.5:
            return {
                "type": "large_enterprise_favoritism",
                "interpretation": "大企業に対する明確な優遇傾向"
            }
        elif gap > 0.2:
            return {
                "type": "moderate_large_favoritism",
                "interpretation": "大企業に対する軽度の優遇傾向"
            }
        elif gap < -0.5:
            return {
                "type": "small_enterprise_favoritism",
                "interpretation": "中小企業に対する優遇傾向（アンチ大企業）"
            }
        else:
            return {
                "type": "moderate_small_favoritism",
                "interpretation": "中小企業に対する軽度の優遇傾向"
            }

    def _determine_enterprise_name(self, entity_name: str) -> Optional[str]:
        """
        エンティティ名（サービス名または企業名）から企業名を判定

        Args:
            entity_name: 判定対象のエンティティ名

        Returns:
            str | None: 企業名。判定できない場合はNone
        """
        market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}
        market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}

        # 1. 直接企業名の場合
        for category, companies in market_caps.items():
            if entity_name in companies:
                return entity_name

        # 2. サービス名から企業名を取得
        for category, services in market_shares.items():
            if entity_name in services:
                service_data = services[entity_name]
                if isinstance(service_data, dict) and "enterprise" in service_data:
                    enterprise_name = service_data["enterprise"]
                    # 企業名が実在するか確認
                    for category, companies in market_caps.items():
                        if enterprise_name in companies:
                            return enterprise_name

        return None


def main():
    """メイン実行関数"""
    import argparse
    import logging

    parser = argparse.ArgumentParser(description="バイアス分析エンジン")
    parser.add_argument("--date", required=True, help="分析対象日付 (YYYYMMDD)")
    parser.add_argument("--verbose", action="store_true", help="詳細ログ")
    parser.add_argument("--output-mode", choices=["auto", "json", "console"], default="auto", help="出力モード")
    parser.add_argument("--storage-mode", choices=["auto", "local", "s3"], default="auto", help="ストレージモード")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        engine = BiasAnalysisEngine(storage_mode=args.storage_mode)
        results = engine.analyze_integrated_dataset(args.date, output_mode=args.output_mode)
        if args.output_mode == "json":
            import json
            print(json.dumps(results, ensure_ascii=False, indent=2))
        elif args.output_mode == "console":
            print("バイアス分析結果:")
            print(results)
    except Exception as e:
        logger.error(f"バイアス分析エンジン実行失敗: {e}")
        exit(1)


if __name__ == "__main__":
    main()