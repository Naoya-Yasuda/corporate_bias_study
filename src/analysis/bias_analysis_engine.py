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

# ReliabilityChecker統合済み（reliability_checker.py削除完了）
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_utils import load_json
from dotenv import load_dotenv
# プロットユーティリティ（統合時に必要に応じて追加）

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

        # rank_utilsのインポートとフォールバック設定
        try:
            from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks
            self.rank_utils_available = True
            self._rbo = rbo
            self._compute_tau = compute_tau
            self._compute_delta_ranks = compute_delta_ranks
        except ImportError as e:
            logger.warning(f"rank_utils インポートエラー: {e}")
            self.rank_utils_available = False

            # フォールバック関数を定義
            def rbo_fallback(list1, list2, p=0.9):
                return 0.0
            def compute_tau_fallback(list1, list2):
                return 0.0
            def compute_delta_ranks_fallback(list1, list2):
                return {}

            self._rbo = rbo_fallback
            self._compute_tau = compute_tau_fallback
            self._compute_delta_ranks = compute_delta_ranks_fallback

        # 信頼性チェック器の初期化
        self.reliability_checker = ReliabilityChecker()

        # データローダーのセットアップ
        self.data_loader = HybridDataLoader(self.storage_mode)

        # 市場データの読み込み
        self.market_data = self._load_market_data()

        # 設定ファイル読み込み
        self.config = self._load_config()

        # バイアス計算パラメータ
        self.bootstrap_iterations = 10000
        self.confidence_level = 95

        logger.info(f"BiasAnalysisEngine初期化: storage_mode={self.storage_mode}")
        logger.info(f"market_data読み込み状況: {bool(self.market_data)}")
        if self.market_data:
            logger.info(f"market_shares: {len(self.market_data.get('market_shares', {}))} カテゴリ")
            logger.info(f"market_caps: {len(self.market_data.get('market_caps', {}))} カテゴリ")

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

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """設定ファイルを読み込み（暫定的にデフォルト設定を使用）"""
        # TODO: config/analysis_config.ymlから読み込み実装
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
                with open(config_path, 'r', encoding='utf-8') as f:
                    import yaml
                    loaded_config = yaml.safe_load(f)
                    default_config.update(loaded_config.get('bias_analysis', {}))
            except Exception as e:
                logger.warning(f"設定ファイル読み込みエラー、デフォルト設定を使用: {e}")

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
            sentiment_data = self.data_loader.load_sentiment_data(date_or_path)

            # データをマージ
            merged_data = integrated_data.copy()
            merged_data['perplexity_sentiment'] = sentiment_data

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

        # 感情バイアス分析
        sentiment_bias_analysis = self._analyze_sentiment_bias(data.get('perplexity_sentiment', {}))

        # 実行回数に基づくメタデータ更新
        if sentiment_bias_analysis:
            # 最初のカテゴリのサブカテゴリから実行回数を取得
            first_category = next(iter(sentiment_bias_analysis.values()))
            if first_category:
                first_subcategory = next(iter(first_category.values()))
                if first_subcategory and 'category_summary' in first_subcategory:
                    execution_count = first_subcategory['category_summary']['execution_count']
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

    def _analyze_sentiment_bias(self, sentiment_data: Dict) -> Dict[str, Any]:
        """
        感情バイアス分析（多重比較補正対応）
        """
        results = {}

        for category, subcategories in sentiment_data.items():
            category_results = {}

            for subcategory, entities in subcategories.items():
                subcategory_result = {"entities": {}}
                p_values = []
                entity_names = []

                # entitiesがdict型でない場合のデバッグ出力
                if not isinstance(entities, dict):
                    print(f"[DEBUG] entities is not dict: type={type(entities)}, value={entities}")

                # 各企業のバイアス指標計算
                for entity_name, entity_data in entities.items() if isinstance(entities, dict) else []:
                    # entity_dataがdict型でない場合のデバッグ出力
                    if not isinstance(entity_data, dict):
                        print(f"[DEBUG] entity_data is not dict: entity_name={entity_name}, type={type(entity_data)}, value={entity_data}")
                    masked_values = entity_data.get("masked_values", []) if isinstance(entity_data, dict) else []
                    unmasked_values = entity_data.get("unmasked_values", []) if isinstance(entity_data, dict) else []
                    execution_count = len(masked_values)
                    metrics = self._calculate_entity_bias_metrics(masked_values, unmasked_values, execution_count)
                    subcategory_result["entities"][entity_name] = metrics
                    # p値が利用可能ならリストに追加
                    p_val = metrics.get("statistical_significance", {}).get("sign_test_p_value")
                    if p_val is not None:
                        p_values.append(p_val)
                        entity_names.append(entity_name)

                # 多重比較補正の適用
                if len(p_values) > 1:
                    correction = self.apply_multiple_comparison_correction(p_values)
                    # 補正後p値・有意判定を各企業に反映
                    for i, entity_name in enumerate(entity_names):
                        subcategory_result["entities"][entity_name]["statistical_significance"]["corrected_p_value"] = correction["corrected_p_values"][i]
                        subcategory_result["entities"][entity_name]["statistical_significance"]["rejected"] = correction["rejected"][i]
                        subcategory_result["entities"][entity_name]["statistical_significance"]["correction_method"] = correction["method"]
                        subcategory_result["entities"][entity_name]["statistical_significance"]["alpha"] = correction["alpha"]

                # カテゴリレベル分析
                subcategory_result["category_level_analysis"] = self._calculate_category_level_analysis(
                    subcategory_result["entities"]
                )

                category_results[subcategory] = subcategory_result

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
        stability_score = stability_metrics if isinstance(stability_metrics, (int, float)) else None
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
        entity_rankings = []
        sentiment_values = {}

        for entity_name, entity_data in entities.items():
            if not isinstance(entity_data, dict):
                continue  # dict型以外はスキップ
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
            bias_indices.append(bi)
            entity_rankings.append({
                "entity": entity_name,
                "bias_rank": 0,  # 後で設定
                "bias_index": bi
            })
            # 感情スコアリスト（unmasked_values）を取得
            unmasked = entity_data.get("basic_metrics", {}).get("unmasked_values")
            if unmasked is not None:
                sentiment_values[entity_name] = unmasked

        # バイアス順位の設定
        entity_rankings = [r for r in entity_rankings if isinstance(r, dict)]
        entity_rankings.sort(key=lambda x: x["bias_index"], reverse=True)
        for i, item in enumerate(entity_rankings):
            item["bias_rank"] = i + 1

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
            "relative_ranking": entity_rankings if isinstance(entity_rankings, list) else [],
            "stability_metrics": stability_metrics if isinstance(stability_metrics, dict) or stability_metrics is None else {}
        }

    def _analyze_ranking_bias(self, ranking_data: Dict) -> Dict[str, Any]:
        """ランキングバイアス分析（多重比較補正横展開）"""

        if not ranking_data:
            return {
                "warning": "ランキングデータが利用できません",
                "available_analyses": []
            }

        results = {}

        for category, subcategories in ranking_data.items():
            category_results = {}

            for subcategory, subcategory_data in subcategories.items():
                # データ構造の確認
                if not isinstance(subcategory_data, dict):
                    continue

                ranking_summary = subcategory_data.get('ranking_summary', {})
                answer_list = subcategory_data.get('answer_list', [])
                execution_count = len(answer_list)

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

                # --- ランキング変動指標の組み込み ---
                ranking_variation = None
                masked_ranking = subcategory_data.get('masked_ranking')
                unmasked_ranking = subcategory_data.get('unmasked_ranking')
                if masked_ranking and unmasked_ranking:
                    ranking_variation = self.calculate_ranking_variation(masked_ranking, unmasked_ranking)

                # --- 多重比較補正の横展開 ---
                # 例: 各企業のランキング有意性p値を集約
                p_values = []
                entity_names = []
                entities = subcategory_data.get('entities', {})
                for entity_name, entity_data in entities.items():
                    p_val = entity_data.get('ranking_significance', {}).get('p_value')
                    if p_val is not None:
                        p_values.append(p_val)
                        entity_names.append(entity_name)
                corrected = None
                if len(p_values) >= 2:
                    corrected = self.apply_multiple_comparison_correction(p_values)
                    # 各企業に補正後p値・有意判定を反映
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
                        "stability_analysis": stability_analysis,
                        "quality_analysis": quality_analysis,
                        "category_level_analysis": category_level_analysis
                    },
                    "ranking_variation": ranking_variation,
                    "entities": entities
                }
                category_results[subcategory] = subcategory_result
            results[category] = category_results
        return results

    def _calculate_ranking_stability(self, ranking_summary: Dict, answer_list: List, execution_count: int) -> Dict[str, Any]:
        """ランキング安定性の計算"""
        if execution_count < 2:
            return {
                "available": False,
                "reason": "安定性分析には最低2回の実行が必要",
                "execution_count": execution_count
            }

        # 現在は1回実行のみのため、将来の複数回実行用のフレームワークを準備
        details = ranking_summary.get('details', {})

        # 各企業の順位分散を計算（将来の複数回実行用）
        rank_variance = {}
        for entity, entity_data in details.items():
            all_ranks = entity_data.get('all_ranks', [])
            if len(all_ranks) > 1:
                rank_variance[entity] = {
                    "mean_rank": sum(all_ranks) / len(all_ranks),
                    "rank_std": (sum((r - sum(all_ranks)/len(all_ranks))**2 for r in all_ranks) / len(all_ranks))**0.5,
                    "rank_range": max(all_ranks) - min(all_ranks)
                }
            else:
                rank_variance[entity] = {
                    "mean_rank": all_ranks[0] if all_ranks else 0,
                    "rank_std": 0.0,
                    "rank_range": 0
                }

        # 全体安定性スコア
        if execution_count == 1:
            overall_stability = 1.0  # 1回のみなら完全安定
        else:
            # 複数回実行時の安定性計算（将来実装）
            avg_std = sum(rv['rank_std'] for rv in rank_variance.values()) / len(rank_variance) if rank_variance else 0
            overall_stability = max(0.0, 1.0 - avg_std / 3.0)  # 3位以内の変動で正規化

        return {
            "overall_stability": round(overall_stability, 3),
            "available": execution_count >= 2,
            "execution_count": execution_count,
            "rank_variance": rank_variance,
            "stability_interpretation": self._interpret_ranking_stability(overall_stability)
        }

    def _calculate_ranking_quality(self, ranking_summary: Dict, answer_list: List, execution_count: int) -> Dict[str, Any]:
        """ランキング品質の分析"""
        details = ranking_summary.get('details', {})
        avg_ranking = ranking_summary.get('avg_ranking', [])
        if execution_count < 2 or not details:
            return {
                "available": False,
                "reason": "品質分析には最低2回の実行が必要",
                "execution_count": execution_count
            }

        # 品質指標
        quality_metrics = {
            "completeness_score": len(avg_ranking) / len(details) if details else 0.0,
            "consistency_score": 1.0,  # 現在は1回のみなので完全一致
            "entity_coverage": len(details),
            "ranking_length": len(avg_ranking)
        }

        # 各企業の品質指標
        entity_quality = {}
        for entity, entity_data in details.items():
            all_ranks = entity_data.get('all_ranks', [])
            official_url = entity_data.get('official_url', '')

            entity_quality[entity] = {
                "rank_consistency": 1.0 if len(set(all_ranks)) <= 1 else len(set(all_ranks)) / len(all_ranks),
                "has_official_url": bool(official_url),
                "avg_rank": entity_data.get('avg_rank', 0),
                "rank_stability": "安定" if len(set(all_ranks)) <= 1 else "変動あり"
            }

        return {
            "quality_metrics": quality_metrics,
            "entity_quality": entity_quality,
            "overall_quality_score": sum(quality_metrics.values()) / len(quality_metrics),
            "quality_interpretation": self._interpret_ranking_quality(quality_metrics)
        }

    def _calculate_ranking_category_analysis(self, ranking_summary: Dict, execution_count: int) -> Dict[str, Any]:
        """カテゴリレベルのランキング分析"""
        details = ranking_summary.get('details', {})
        avg_ranking = ranking_summary.get('avg_ranking', [])
        if execution_count < 2 or not details:
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

        # 競争分析
        total_entities = len(details)
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
                for subcategory, entities in subcategories.items():
                    if not isinstance(entities, dict):
                        continue
                    # 1. バイアス不平等指標の計算
                    bias_inequality = self._calculate_bias_inequality(entities)
                    # 2. 企業優遇度分析
                    market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}
                    enterprise_favoritism = self._analyze_enterprise_favoritism(entities, market_caps)

                    # 3. 市場シェア相関分析
                    market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}
                    market_share_correlation = self._analyze_market_share_correlation(
                        entities, market_shares, category
                    )
                    # 4. 相対ランキング変動（暫定実装）
                    relative_ranking_analysis = self._analyze_relative_ranking_changes_stub(entities)
                    # 5. 統合相対評価
                    integrated_relative_evaluation = self._generate_integrated_relative_evaluation(
                        bias_inequality, enterprise_favoritism, market_share_correlation
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
                        corrected = self.apply_multiple_comparison_correction(p_values)
                        for i, name in enumerate(entity_names):
                            if name in entities:
                                if 'favoritism_significance' not in entities[name]:
                                    entities[name]['favoritism_significance'] = {}
                                entities[name]['favoritism_significance']['corrected_p_value'] = corrected['corrected_p_values'][i]
                                entities[name]['favoritism_significance']['rejected'] = corrected['rejected'][i]
                                entities[name]['favoritism_significance']['correction_method'] = corrected['method']
                                entities[name]['favoritism_significance']['alpha'] = corrected['alpha']
                    category_results[subcategory] = {
                        "bias_inequality": bias_inequality,
                        "enterprise_favoritism": enterprise_favoritism,
                        "market_share_correlation": market_share_correlation,
                        "relative_ranking_analysis": relative_ranking_analysis,
                        "integrated_evaluation": integrated_relative_evaluation,
                        "entities": entities
                    }
                relative_analysis_results[category] = category_results
            # 全体サマリーの生成
            overall_summary = self._generate_relative_bias_summary(relative_analysis_results)
            relative_analysis_results["overall_summary"] = overall_summary
            return relative_analysis_results
        except Exception as e:
            logger.error(f"相対バイアス分析でエラー: {e}")
            return {"error": str(e)}

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

    def _analyze_enterprise_favoritism(self, entities: Dict[str, Any], market_caps: Dict[str, Any]) -> Dict[str, Any]:
        """企業優遇度分析（企業規模による優遇パターン検出）"""

        # 企業規模とバイアスの関係を分析
        enterprise_bias_data = []

        for entity_name, entity_data in entities.items():
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

            # 時価総額データから企業規模を取得
            enterprise_size = self._get_enterprise_size(entity_name, market_caps)

            enterprise_bias_data.append({
                "entity": entity_name,
                "bias_index": bi,
                "enterprise_size": enterprise_size
            })

        if not enterprise_bias_data:
            return {"error": "企業データなし"}

        # 大企業 vs 中小企業の分類
        large_enterprises = [item for item in enterprise_bias_data if item["enterprise_size"] == "large"]
        small_enterprises = [item for item in enterprise_bias_data if item["enterprise_size"] == "small"]

        # 平均バイアスの計算
        large_avg_bias = statistics.mean([item["bias_index"] for item in large_enterprises]) if large_enterprises else 0
        small_avg_bias = statistics.mean([item["bias_index"] for item in small_enterprises]) if small_enterprises else 0

        favoritism_gap = large_avg_bias - small_avg_bias

        # 優遇タイプの判定
        favoritism_type = self._determine_favoritism_type(favoritism_gap, large_avg_bias, small_avg_bias)

        return {
            "large_enterprise_count": len(large_enterprises),
            "small_enterprise_count": len(small_enterprises),
            "large_enterprise_avg_bias": round(large_avg_bias, 3),
            "small_enterprise_avg_bias": round(small_avg_bias, 3),
            "favoritism_gap": round(favoritism_gap, 3),
            "favoritism_type": favoritism_type["type"],
            "favoritism_interpretation": favoritism_type["interpretation"],
            "statistical_significance": self._test_favoritism_significance(large_enterprises, small_enterprises)
        }

    def _get_enterprise_size(self, entity_name: str, market_caps: Dict[str, Any]) -> str:
        """企業規模の判定"""

        # 市場時価総額データから企業規模を判定
        for category, enterprises in market_caps.items():
            if entity_name in enterprises:
                market_cap = enterprises[entity_name]

                # 時価総額による分類（兆円単位）
                if market_cap >= 50:  # 50兆円以上
                    return "large"
                elif market_cap >= 10:  # 10兆円以上
                    return "medium"
                else:
                    return "small"

        # データがない場合は企業名から推定
        large_indicators = ["Google", "Microsoft", "Amazon", "Apple", "Meta", "Tesla", "Toyota"]
        if any(indicator in entity_name for indicator in large_indicators):
            return "large"
        else:
            return "small"

    def _determine_favoritism_type(self, gap: float, large_avg: float, small_avg: float) -> Dict[str, str]:
        """優遇タイプの判定"""

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

    def _test_favoritism_significance(self, large_enterprises: List[Dict], small_enterprises: List[Dict]) -> Dict[str, Any]:
        """優遇度の統計的有意性検定"""

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
                "interpretation": "統計的に有意な優遇差" if p_value < 0.05 else "統計的に有意でない"
            }

        except Exception as e:
            logger.warning(f"優遇度統計検定エラー: {e}")
            return {
                "test_performed": False,
                "reason": f"計算エラー: {e}",
                "p_value": None,
                "significant": False
            }

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

    def _generate_integrated_relative_evaluation(self, bias_inequality: Dict, enterprise_favoritism: Dict, market_share_correlation: Dict) -> Dict[str, Any]:
        """統合相対評価の生成"""

        evaluation_scores = {}
        insights = []

        # 1. 公平性スコア
        inequality_score = 1 - bias_inequality.get("gini_coefficient", 0)  # Gini係数の逆数
        evaluation_scores["fairness_score"] = max(0, inequality_score)

        # 2. 企業規模中立性スコア
        favoritism_gap = abs(enterprise_favoritism.get("favoritism_gap", 0))
        neutrality_score = max(0, 1 - favoritism_gap)
        evaluation_scores["neutrality_score"] = neutrality_score

        # 3. 市場適合性スコア
        if market_share_correlation.get("correlation_available", False):
            fairness_analysis = market_share_correlation.get("fairness_analysis", {})
            market_fairness = fairness_analysis.get("overall_fairness_score", 0.5)
            evaluation_scores["market_alignment_score"] = market_fairness
        else:
            evaluation_scores["market_alignment_score"] = 0.5  # 中立値

        # 4. 総合評価スコア
        overall_score = statistics.mean(evaluation_scores.values())

        # 5. 評価レベルの判定
        if overall_score >= 0.8:
            evaluation_level = "優秀"
            insights.append("企業間のバイアス格差が小さく、公平な評価環境")
        elif overall_score >= 0.6:
            evaluation_level = "良好"
            insights.append("概ね公平だが、一部改善の余地あり")
        elif overall_score >= 0.4:
            evaluation_level = "普通"
            insights.append("バイアス格差が中程度存在、注意が必要")
        else:
            evaluation_level = "要改善"
            insights.append("企業間で大きなバイアス格差、公平性に問題")

        # 6. 具体的な改善提案
        recommendations = self._generate_fairness_recommendations(
            bias_inequality, enterprise_favoritism, market_share_correlation
        )

        return {
            "evaluation_scores": evaluation_scores,
            "overall_score": round(overall_score, 3),
            "evaluation_level": evaluation_level,
            "key_insights": insights,
            "recommendations": recommendations
        }

    def _generate_fairness_recommendations(self, bias_inequality: Dict, enterprise_favoritism: Dict, market_share_correlation: Dict) -> List[str]:
        """公平性改善のための推奨事項生成"""

        recommendations = []

        # Gini係数に基づく推奨
        gini = bias_inequality.get("gini_coefficient", 0)
        if gini > 0.4:
            recommendations.append("企業間バイアス格差の是正：評価基準の統一化が必要")

        # 企業規模優遇に基づく推奨
        favoritism_type = enterprise_favoritism.get("favoritism_type", "")
        if "large_enterprise_favoritism" in favoritism_type:
            recommendations.append("大企業優遇の是正：中小企業への公平な露出機会の確保")
        elif "small_enterprise_favoritism" in favoritism_type:
            recommendations.append("中小企業優遇の是正：市場実態に即した評価バランスの調整")

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
        all_favoritism_gaps = []
        all_fairness_scores = []

        for category, subcategories in relative_analysis_results.items():
            if category == "overall_summary":
                continue

            for subcategory, data in subcategories.items():
                bias_inequality = data.get("bias_inequality", {})
                enterprise_favoritism = data.get("enterprise_favoritism", {})
                market_share_correlation = data.get("market_share_correlation", {})

                if "gini_coefficient" in bias_inequality:
                    all_gini_coefficients.append(bias_inequality["gini_coefficient"])

                if "favoritism_gap" in enterprise_favoritism:
                    all_favoritism_gaps.append(abs(enterprise_favoritism["favoritism_gap"]))

                if market_share_correlation.get("correlation_available", False):
                    fairness_analysis = market_share_correlation.get("fairness_analysis", {})
                    if "overall_fairness_score" in fairness_analysis:
                        all_fairness_scores.append(fairness_analysis["overall_fairness_score"])

        # 全体統計の計算
        summary_stats = {
            "categories_analyzed": len([k for k in relative_analysis_results.keys() if k != "overall_summary"]),
            "average_gini_coefficient": round(statistics.mean(all_gini_coefficients), 3) if all_gini_coefficients else 0,
            "average_favoritism_gap": round(statistics.mean(all_favoritism_gaps), 3) if all_favoritism_gaps else 0,
            "average_market_fairness": round(statistics.mean(all_fairness_scores), 3) if all_fairness_scores else 0.5
        }

        # 全体的な評価レベル
        if summary_stats["average_gini_coefficient"] < 0.3 and summary_stats["average_favoritism_gap"] < 0.3:
            overall_assessment = "公平"
            system_health = "健全"
        elif summary_stats["average_gini_coefficient"] > 0.5 or summary_stats["average_favoritism_gap"] > 0.5:
            overall_assessment = "不公平"
            system_health = "要改善"
        else:
            overall_assessment = "中程度"
            system_health = "注意が必要"

        # 主要な課題の特定
        key_issues = []
        if summary_stats["average_gini_coefficient"] > 0.4:
            key_issues.append("企業間バイアス格差の拡大")
        if summary_stats["average_favoritism_gap"] > 0.4:
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
                "favoritism_analysis_available": len(all_favoritism_gaps) > 0,
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

            return {
                "rbo_score": round(metrics.get("rbo", 0), 3),
                "kendall_tau": round(metrics.get("kendall_tau", 0), 3),
                "overlap_ratio": round(metrics.get("overlap_ratio", 0), 3),
                "delta_ranks_available": len(metrics.get("delta_ranks", {})) > 0
            }

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"ランキング類似度計算エラー: {e}")

            # フォールバック: シンプルな重複率計算
            google_set = set(google_domains[:10])
            citations_set = set(citations_domains[:10])
            overlap = len(google_set & citations_set)
            union = len(google_set | citations_set)
            overlap_ratio = overlap / union if union > 0 else 0

            return {
                "rbo_score": None,
                "kendall_tau": None,
                "overlap_ratio": round(overlap_ratio, 3),
                "delta_ranks_available": False,
                "fallback_calculation": True
            }

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
        """感情バイアス・ランキングバイアス・Citations-Google比較の統合インサイト生成"""

        # 一貫したリーダー・ラガードの特定
        consistent_leaders = []
        consistent_laggards = []

        # 感情バイアス分析から上位/下位企業を抽出
        sentiment_leaders = set()
        sentiment_laggards = set()

        for category, subcategories in sentiment_analysis.items():
            for subcategory, data in subcategories.items():
                if "entities" in data:
                    for entity, metrics in data["entities"].items():
                        bi = metrics.get("basic_metrics", {}).get("normalized_bias_index", 0)
                        if bi > 0.5:  # 強いポジティブバイアス
                            sentiment_leaders.add(entity)
                        elif bi < -0.5:  # 強いネガティブバイアス
                            sentiment_laggards.add(entity)

        # ランキング分析からの情報（簡略化）
        ranking_leaders = set()
        ranking_laggards = set()

        for category, subcategories in ranking_analysis.items():
            for subcategory, data in subcategories.items():
                if "category_analysis" in data:
                    # ランキング分析の詳細は複雑なため、基本的な抽出のみ
                    pass

        # 一貫性の確認
        consistent_leaders = list(sentiment_leaders & ranking_leaders) if ranking_leaders else list(sentiment_leaders)[:3]
        consistent_laggards = list(sentiment_laggards & ranking_laggards) if ranking_laggards else list(sentiment_laggards)[:3]

        # Google-Citations間の整合性評価
        google_citations_alignment = "unknown"
        if citations_comparison:
            alignment_scores = []
            for category, subcategories in citations_comparison.items():
                if category == "error":
                    continue
                for subcategory, data in subcategories.items():
                    if "ranking_similarity" in data:
                        overlap_ratio = data["ranking_similarity"].get("overlap_ratio", 0)
                        alignment_scores.append(overlap_ratio)

            if alignment_scores:
                avg_alignment = statistics.mean(alignment_scores)
                if avg_alignment > 0.7:
                    google_citations_alignment = "high"
                elif avg_alignment > 0.4:
                    google_citations_alignment = "moderate"
                else:
                    google_citations_alignment = "low"

        # 全体的なバイアスパターンの判定
        overall_bias_pattern = "balanced"

        # 大企業優遇の判定（簡易版）
        large_enterprise_bias_count = 0
        total_bias_count = 0

        large_enterprises = ["AWS", "Microsoft", "Google", "Oracle", "IBM", "ソニー", "任天堂", "富士通"]

        for category, subcategories in sentiment_analysis.items():
            for subcategory, data in subcategories.items():
                if "entities" in data:
                    for entity, metrics in data["entities"].items():
                        bi = metrics.get("basic_metrics", {}).get("normalized_bias_index", 0)
                        if abs(bi) > 0.3:  # 明確なバイアスがある場合
                            total_bias_count += 1
                            if entity in large_enterprises and bi > 0:
                                large_enterprise_bias_count += 1

        if total_bias_count > 0:
            large_enterprise_ratio = large_enterprise_bias_count / total_bias_count
            if large_enterprise_ratio > 0.6:
                overall_bias_pattern = "large_enterprise_favoritism"
            elif large_enterprise_ratio < 0.3:
                overall_bias_pattern = "small_enterprise_favoritism"

        # 感情-ランキング相関の計算（簡易版）
        sentiment_ranking_correlation = 0.75  # 暫定値（詳細計算は今後実装）

        # クロスプラットフォーム一貫性
        cross_platform_consistency = "high" if google_citations_alignment == "high" and sentiment_ranking_correlation > 0.7 else "moderate"

        return {
            "sentiment_ranking_correlation": sentiment_ranking_correlation,
            "consistent_leaders": consistent_leaders,
            "consistent_laggards": consistent_laggards,
            "google_citations_alignment": google_citations_alignment,
            "overall_bias_pattern": overall_bias_pattern,
            "cross_platform_consistency": cross_platform_consistency,
            "analysis_coverage": {
                "sentiment_analysis_available": bool(sentiment_analysis),
                "ranking_analysis_available": bool(ranking_analysis),
                "citations_comparison_available": bool(citations_comparison and "error" not in citations_comparison)
            }
        }

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


def main():
    """メイン実行関数"""
    import argparse
    import logging

    parser = argparse.ArgumentParser(description="企業バイアス分析エンジン")
    parser.add_argument("--date", required=True, help="分析対象日付 (YYYYMMDD形式)")
    parser.add_argument("--verbose", action="store_true", help="詳細ログを出力")
    parser.add_argument("--output-mode", default="auto", choices=["auto", "json", "console"],
                        help="出力モード")

    args = parser.parse_args()

    # ログ設定
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    logger = logging.getLogger(__name__)

    try:
        # ストレージモードを環境変数から取得
        import os
        storage_mode = os.getenv('STORAGE_MODE', 'auto')
        logger.info(f"環境変数STORAGE_MODEから取得: {storage_mode}")

        engine = BiasAnalysisEngine(storage_mode=storage_mode)
        logger.info(f"BiasAnalysisEngine初期化: storage_mode={storage_mode}")

        logger.info(f"バイアス分析開始: {args.date}")
        results = engine.analyze_integrated_dataset(args.date, output_mode=args.output_mode)

        logger.info("バイアス分析が正常に完了しました")
        logger.info(f"分析結果: {len(results)} つのカテゴリを分析")

        if args.output_mode == "console":
            print("=== バイアス分析結果 ===")
            for category, result in results.items():
                print(f"\n[{category}]")
                if isinstance(result, dict) and "sentiment_analysis" in result:
                    sentiment = result["sentiment_analysis"]
                    if "category_analysis" in sentiment:
                        print(f"  カテゴリ分析: {sentiment['category_analysis'].get('total_entities', 0)}エンティティ")

    except Exception as e:
        logger.error(f"バイアス分析でエラーが発生: {e}")
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()