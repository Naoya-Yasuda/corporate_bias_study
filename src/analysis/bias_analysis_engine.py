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
from datetime import datetime
import statistics
import math
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
import warnings

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleRanking:
    """シンプルな順位情報を保持するクラス"""

    def __init__(self, domain: str, rank: int, source: str, entity: str, result_type: str):
        self.domain = domain
        self.rank = rank
        self.source = source  # "google" or "perplexity"
        self.entity = entity  # "AWS", "Azure", etc.
        self.result_type = result_type  # "official" or "reputation"

    def __repr__(self):
        return f"SimpleRanking(domain='{self.domain}', rank={self.rank}, source='{self.source}', entity='{self.entity}', result_type='{self.result_type}')"


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

        # Phase 1: 基盤機能 - データタイプ判定と正規化機能の初期化
        logger.info("Phase 1基盤機能: データタイプ判定と正規化機能を初期化")

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
        elif severity >= 1.0:
            interp = "中程度の重篤度"
        elif severity >= 0.3:
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
                                 output_mode: str = "auto",
                                 runs: int = None) -> Dict[str, Any]:
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
            "analysis_date": datetime.now().isoformat(),
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
        # カテゴリレベル分析で後から正規化されるため、ここではraw_deltaをそのまま使用
        normalized_bias_index = raw_delta

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

        # バイアス強度（統計的有意性を考慮）
        abs_bi = abs(bi)

        # 統計的に有意でない場合（p_value >= 0.05）は「無視できる」とする
        if p_value is not None and p_value >= 0.05:
            bias_strength = "無視できる"
        elif abs_bi > self.config["bias_strength_thresholds"]["very_strong"]:
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
        raw_deltas = []  # 正規化計算用のraw_deltaリスト

        # まず各エンティティのバイアス値を収集
        for entity_name, entity_data in entities.items():
            if not isinstance(entity_data, dict):
                continue  # dict型以外はスキップ

            # raw_deltaを取得（正規化前の値）
            raw_delta = entity_data.get("basic_metrics", {}).get("raw_delta", 0)
            raw_deltas.append(raw_delta)

            # 現在のnormalized_bias_indexを取得（後で更新）
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
            bias_indices.append(bi)
            entity_bias_list.append((entity_name, bi))

            # 感情スコアリスト（unmasked_values）を取得
            unmasked = entity_data.get("basic_metrics", {}).get("unmasked_values")
            if unmasked is not None:
                sentiment_values[entity_name] = unmasked

        # 正規化バイアス指標の計算
        if raw_deltas:
            # カテゴリ内平均|Δ|を計算
            avg_abs_delta = sum(abs(delta) for delta in raw_deltas) / len(raw_deltas)

            # 各エンティティのnormalized_bias_indexを更新
            for i, (entity_name, _) in enumerate(entity_bias_list):
                if entity_name in entities and avg_abs_delta > 0:
                    # BI = Δ / カテゴリ内平均|Δ|
                    normalized_bi = raw_deltas[i] / avg_abs_delta

                    # basic_metricsのnormalized_bias_indexを更新
                    if "basic_metrics" in entities[entity_name]:
                        entities[entity_name]["basic_metrics"]["normalized_bias_index"] = round(normalized_bi, 3)

                    # bias_indicesリストも更新
                    bias_indices[i] = normalized_bi
                    entity_bias_list[i] = (entity_name, normalized_bi)

        # バイアス値で降順ソートし順位付与
        entity_bias_list.sort(key=lambda x: x[1], reverse=True)
        for rank, (entity_name, bi) in enumerate(entity_bias_list, 1):
            if entity_name in entities:
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
        """相対バイアス分析の完全実装（多重比較補正横展開 + HHI分析機能追加）"""
        try:
            relative_analysis_results = {}

            # 市場データの読み込み
            market_data = self._load_market_data()
            market_shares = market_data.get("market_shares", {})
            market_caps = market_data.get("market_caps", {})

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
                    # 3. 統合市場支配力分析（カテゴリ別適応版）
                    market_dominance_analysis = self._analyze_market_dominance_bias(entities, category, subcategory)

                    # 4. 互換性のための従来分析（段階的移行用）
                    market_share_correlation = self._analyze_market_share_correlation(
                        entities, market_shares, category
                    )

                    # 5. 相対ランキング変動（暫定実装）
                    relative_ranking_analysis = self._analyze_relative_ranking_changes_stub(entities)

                    # 6. 統合相対評価（market_dominance_analysisに統合済み）
                    integrated_relative_evaluation = self._generate_enhanced_integrated_evaluation(
                        bias_inequality, market_share_correlation, market_dominance_analysis,
                        entities, market_shares
                    )

                    # 7. 市場集中度分析（HHI分析機能追加）
                    market_concentration_analysis = self._analyze_market_concentration(
                        market_shares, market_caps, category, subcategory, entities
                    )

                    category_results[subcategory] = {
                        "bias_inequality": bias_inequality,
                        "market_dominance_analysis": market_dominance_analysis,
                        "market_share_correlation": market_share_correlation,  # 後方互換性用
                        "relative_ranking_analysis": relative_ranking_analysis,
                        "integrated_evaluation": integrated_relative_evaluation,
                        "market_concentration_analysis": market_concentration_analysis,  # 新規追加
                        "entities": entities  # 二重entitiesを避けて直接entitiesを設定
                    }

                relative_analysis_results[category] = category_results

            return relative_analysis_results

        except Exception as e:
            import traceback
            logging.error(f"相対バイアス分析エラー: {e}")
            logging.error(f"スタックトレース: {traceback.format_exc()}")
            return {}

    def _analyze_market_concentration(self, market_shares: Dict[str, Any], market_caps: Dict[str, Any],
                                    category: str, subcategory: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """
        市場集中度分析（HHI分析）- カテゴリ別最適化版

        Parameters:
        -----------
        market_shares : Dict[str, Any]
            市場シェアデータ
        market_caps : Dict[str, Any]
            時価総額データ
        category : str
            カテゴリ名
        subcategory : str
            サブカテゴリ名
        entities : Dict[str, Any]
            エンティティデータ

        Returns:
        --------
        Dict[str, Any]
            市場集中度分析結果
        """
        try:
            # カテゴリ名とサブカテゴリ名のマッピング
            # データセットのカテゴリ名を市場データのカテゴリ名に変換
            market_category = self._map_category_to_market_data(category, subcategory)

            # カテゴリに応じて適切なHHI分析を実行
            if category == "デジタルサービス":
                # デジタルサービスカテゴリ: サービスレベルHHI分析のみ
                service_hhi = self._calculate_service_hhi(market_shares, market_category, subcategory)
                enterprise_hhi = self._create_empty_hhi_result("サービスカテゴリのため企業レベルHHI分析は不要")
            elif category == "企業" or category == "大学" or subcategory == "日本の大学":
                # 企業・大学カテゴリ: 企業レベルHHI分析のみ
                service_hhi = self._create_empty_hhi_result("企業カテゴリのためサービスレベルHHI分析は不要")
                enterprise_hhi = self._calculate_enterprise_hhi(market_caps, market_category, subcategory)
            else:
                # その他のカテゴリ: どちらも実行しない
                service_hhi = self._create_empty_hhi_result(f"{category}カテゴリのためサービスレベルHHI分析は不要")
                enterprise_hhi = self._create_empty_hhi_result(f"{category}カテゴリのため企業レベルHHI分析は不要")

            # 集中度-バイアス相関分析（カテゴリ別最適化版）
            concentration_correlation = self._analyze_concentration_bias_correlation_optimized(
                service_hhi, enterprise_hhi, entities, category
            )

            # 市場構造インサイト生成（カテゴリ別最適化版）
            market_insights = self._generate_market_structure_insights_optimized(
                service_hhi, enterprise_hhi, category
            )

            return {
                "service_hhi": service_hhi,
                "enterprise_hhi": enterprise_hhi,
                "concentration_bias_correlation": concentration_correlation,
                "market_structure_insights": market_insights
            }

        except Exception as e:
            logging.error(f"市場集中度分析エラー: {e}")
            return self._create_empty_market_concentration_result(f"分析エラー: {str(e)}")

    def _calculate_service_hhi(self, market_shares: Dict[str, Any], category: str, subcategory: str) -> Dict[str, Any]:
        """
        サービスレベルでのHHIを算出

        Parameters:
        -----------
        market_shares : Dict[str, Any]
            市場シェアデータ（src/data/market_shares.json）
        category : str
            カテゴリ名
        subcategory : str
            サブカテゴリ名

        Returns:
        --------
        Dict[str, Any]
            HHI分析結果
        """
        try:
            # 1. 対象カテゴリ・サブカテゴリの市場シェアデータを抽出
            # 市場シェアデータは直接カテゴリ名でアクセス
            subcategory_data = market_shares.get(category, {})

            if not subcategory_data:
                return self._create_empty_hhi_result("サービス市場シェアデータが不足")

            # 2. 市場シェアデータの構造を確認して適切に処理
            shares = {}
            for service, data in subcategory_data.items():
                if isinstance(data, dict) and 'market_share' in data:
                    # 新しい構造: {service: {"market_share": value, "enterprise": name}}
                    share_value = data['market_share']
                    if isinstance(share_value, (int, float)) and share_value > 0:
                        shares[service] = float(share_value)  # 既に小数形式
                elif isinstance(data, (int, float)) and data > 0:
                    # 古い構造: {service: value} (パーセンテージ形式)
                    shares[service] = float(data) / 100.0  # パーセンテージを小数に変換

            if not shares:
                return self._create_empty_hhi_result("有効な市場シェアデータがありません")

            # 3. HHI計算: Σ(市場シェア_i)^2 * 10000
            hhi_score = sum(share ** 2 for share in shares.values()) * 10000

            # 4. 集中度レベル判定
            concentration_level = self._interpret_hhi_level(hhi_score)

            # 5. 上位サービス抽出（シェア順）
            sorted_services = sorted(shares.items(), key=lambda x: x[1], reverse=True)
            top_services = []
            for i, (service, share) in enumerate(sorted_services[:5], 1):  # 上位5社
                top_services.append({
                    "service": service,
                    "share": round(share * 100, 1),  # パーセンテージで表示
                    "rank": i
                })

            # 6. 市場構造分類
            market_structure = self._classify_market_structure(hhi_score, top_services)

            # 7. 公平性への影響評価
            fairness_implications = self._assess_fairness_implications(hhi_score, concentration_level, top_services)

            # 8. 計算詳細
            calculation_details = {
                "total_services": len(shares),
                "effective_competitors": self._count_effective_competitors(shares),
                "largest_share": round(max(shares.values()) * 100, 1),
                "smallest_share": round(min(shares.values()) * 100, 1),
                "share_variance": round(np.var(list(shares.values())) * 10000, 2) if len(shares) > 1 else 0
            }

            return {
                "hhi_score": round(hhi_score, 1),
                "concentration_level": concentration_level,
                "market_structure": market_structure,
                "top_services": top_services,
                "fairness_implications": fairness_implications,
                "calculation_details": calculation_details
            }

        except Exception as e:
            return self._create_empty_hhi_result(f"HHI計算エラー: {str(e)}")

    def _calculate_enterprise_hhi(self, market_caps: Dict[str, Any], category: str, subcategory: str) -> Dict[str, Any]:
        """
        企業レベルでのHHIを算出

        Parameters:
        -----------
        market_caps : Dict[str, Any]
            時価総額データ（src/data/market_caps.json）
        category : str
            カテゴリ名
        subcategory : str
            サブカテゴリ名

        Returns:
        --------
        Dict[str, Any]
            企業HHI分析結果
        """
        try:
            # 1. 対象カテゴリ・サブカテゴリの時価総額データを抽出
            # 時価総額データは直接カテゴリ名でアクセス
            subcategory_data = market_caps.get(category, {})

            if not subcategory_data:
                return self._create_empty_hhi_result("企業時価総額データが不足")

            # 2. 有効な時価総額データを抽出
            caps = {}
            for enterprise, cap in subcategory_data.items():
                if isinstance(cap, (int, float)) and cap > 0:
                    caps[enterprise] = float(cap)

            if not caps:
                return self._create_empty_hhi_result("有効な時価総額データがありません")

            # 3. 時価総額を市場シェアに変換
            total_market_cap = sum(caps.values())
            shares = {enterprise: cap / total_market_cap for enterprise, cap in caps.items()}

            # 4. HHI計算
            hhi_score = sum(share ** 2 for share in shares.values()) * 10000

            # 5. 集中度レベル判定
            concentration_level = self._interpret_hhi_level(hhi_score)

            # 6. 企業規模別シェア計算
            enterprise_tiers = self._calculate_enterprise_tiers(caps, subcategory)

            # 7. 市場支配力分析
            market_power_analysis = self._analyze_market_power(hhi_score, enterprise_tiers)

            # 8. バイアスリスク評価
            bias_risk_assessment = self._assess_bias_risk_from_concentration(hhi_score, concentration_level)

            # 9. 計算詳細
            if subcategory == "日本の大学":
                # 大学用の計算詳細（億円単位）
                calculation_details = {
                    "total_enterprises": len(caps),
                    "large_enterprises": len([cap for cap in caps.values() if cap >= 1000]),  # 1000億円以上
                    "total_market_cap": round(total_market_cap, 2),  # 億円単位
                    "largest_market_cap": round(max(caps.values()), 2),
                    "smallest_market_cap": round(min(caps.values()), 2)
                }
            else:
                # 企業用の計算詳細（兆円単位）
                calculation_details = {
                    "total_enterprises": len(caps),
                    "large_enterprises": len([cap for cap in caps.values() if cap >= 10]),  # 10兆円以上
                    "total_market_cap": round(total_market_cap, 2),  # 兆円単位
                    "largest_market_cap": round(max(caps.values()), 2),
                    "smallest_market_cap": round(min(caps.values()), 2)
                }

            return {
                "hhi_score": round(hhi_score, 1),
                "concentration_level": concentration_level,
                "enterprise_tiers": enterprise_tiers,
                "market_power_analysis": market_power_analysis,
                "bias_risk_assessment": bias_risk_assessment,
                "calculation_details": calculation_details
            }

        except Exception as e:
            return self._create_empty_hhi_result(f"企業HHI計算エラー: {str(e)}")

    def _analyze_concentration_bias_correlation_optimized(self,
                                                        service_hhi: Dict[str, Any],
                                                        enterprise_hhi: Dict[str, Any],
                                                        entities: Dict[str, Any],
                                                        category: str) -> Dict[str, Any]:
        """
        集中度-バイアス相関分析

        Parameters:
        -----------
        service_hhi : Dict[str, Any]
            サービスHHI分析結果
        enterprise_hhi : Dict[str, Any]
            企業HHI分析結果
        entities : Dict[str, Any]
            エンティティデータ

        Returns:
        --------
        Dict[str, Any]
            相関分析結果
        """
        try:
            # 1. バイアス指標の抽出
            bias_indices = self._extract_bias_indices(entities)

            if not bias_indices:
                return self._create_empty_correlation_result("バイアス指標データが不足")

            # 2. サービスHHI-バイアス相関計算
            service_hhi_score = service_hhi.get("hhi_score", 0)
            service_correlation = self._calculate_hhi_bias_correlation(service_hhi_score, bias_indices)

            # 3. 企業HHI-バイアス相関計算
            enterprise_hhi_score = enterprise_hhi.get("hhi_score", 0)
            enterprise_correlation = self._calculate_hhi_bias_correlation(enterprise_hhi_score, bias_indices)

            # 4. 相関の有意性判定
            correlation_significance = self._determine_correlation_significance(
                service_correlation, enterprise_correlation
            )

            # 5. 解釈生成
            interpretation = self._generate_correlation_interpretation(
                service_correlation, enterprise_correlation, correlation_significance
            )

            # 6. 集中度レベル別分析（カテゴリ別最適化版）
            concentration_level_analysis = self._analyze_by_concentration_level_optimized(
                service_hhi, enterprise_hhi, bias_indices, category
            )

            return {
                "correlation_analysis": {
                    "service_hhi_bias_correlation": round(service_correlation, 3),
                    "enterprise_hhi_bias_correlation": round(enterprise_correlation, 3),
                    "correlation_significance": correlation_significance,
                    "interpretation": interpretation
                },
                "concentration_level_analysis": concentration_level_analysis
            }

        except Exception as e:
            return self._create_empty_correlation_result(f"相関分析エラー: {str(e)}")

    def _generate_market_structure_insights_optimized(self,
                                                    service_hhi: Dict[str, Any],
                                                    enterprise_hhi: Dict[str, Any],
                                                    category: str) -> List[str]:
        """
        市場構造インサイト生成

        Parameters:
        -----------
        service_hhi : Dict[str, Any]
            サービスHHI分析結果
        enterprise_hhi : Dict[str, Any]
            企業HHI分析結果

        Returns:
        --------
        List[str]
            市場構造インサイトリスト
        """
        try:
            insights = []

            # カテゴリに応じて適切な分析のみを実行
            if category == "デジタルサービス":
                # デジタルサービスカテゴリ: サービスレベルHHI分析からのインサイトのみ
                service_score = service_hhi.get("hhi_score", 0)
                service_level = service_hhi.get("concentration_level", "不明")

                if service_score >= 2500:
                    insights.append("サービス市場の高集中により競争制限的なバイアスが発生")
                elif service_score >= 1500:
                    insights.append("サービス市場の中程度集中により一部企業へのバイアスが観察される")
                else:
                    insights.append("サービス市場の集中度は低いが、他の要因によるバイアスが存在")

                if service_score >= 2500:
                    insights.append("サービス市場の寡占構造が特定サービスへの露出を促進")
                if service_score >= 2000:
                    insights.append("サービス市場集中度の低下によりバイアス軽減が期待される")

            elif category == "企業" or category == "大学" or subcategory == "日本の大学":
                # 企業・大学カテゴリ: 企業レベルHHI分析からのインサイトのみ
                enterprise_score = enterprise_hhi.get("hhi_score", 0)
                enterprise_level = enterprise_hhi.get("concentration_level", "不明")

                if enterprise_score >= 2500:
                    insights.append("企業市場の高集中により大企業優遇のリスク")
                elif enterprise_score >= 1500:
                    insights.append("企業市場の中程度集中により企業規模による市場支配力が観察される")
                else:
                    insights.append("企業市場の集中度は低いが、他の要因によるバイアスが存在")

                if enterprise_score >= 2500:
                    insights.append("大企業の市場支配力が検索結果の偏りを助長")
                elif enterprise_score >= 1500:
                    insights.append("企業規模による市場支配力がバイアスに影響")
                if enterprise_score >= 2000:
                    insights.append("企業市場集中度の低下によりバイアス軽減が期待される")
            else:
                # その他のカテゴリ: インサイトなし
                pass

            return insights if insights else ["市場集中度分析から特筆すべきインサイトは見つかりませんでした"]

        except Exception as e:
            return [f"市場構造インサイト生成エラー: {str(e)}"]

    # ヘルパーメソッド群
    def _interpret_hhi_level(self, hhi_score: float) -> str:
        """
        HHI値から集中度レベルを判定

        Parameters:
        -----------
        hhi_score : float
            HHI値

        Returns:
        --------
        str
            集中度レベル
        """
        if hhi_score < 1500:
            return "非集中市場"
        elif hhi_score < 2500:
            return "中程度集中市場"
        else:
            return "高集中市場"

    def _classify_market_structure(self, hhi_score: float, top_services: List[Dict]) -> str:
        """
        市場構造を分類

        Parameters:
        -----------
        hhi_score : float
            HHI値
        top_services : List[Dict]
            上位サービスリスト

        Returns:
        --------
        str
            市場構造分類
        """
        if hhi_score >= 3000:
            return "独占的寡占市場"
        elif hhi_score >= 2500:
            return "寡占市場"
        elif hhi_score >= 1500:
            return "寡占的競争市場"
        else:
            return "競争市場"

    def _calculate_enterprise_tiers(self, market_caps: Dict[str, float], subcategory: str = "企業") -> Dict[str, float]:
        """
        企業・大学規模別シェアを計算

        Parameters:
        -----------
        market_caps : Dict[str, float]
            企業別時価総額または大学別年間予算
        subcategory : str
            サブカテゴリ名（"日本の大学"の場合は大学用閾値を使用）

        Returns:
        --------
        Dict[str, float]
            規模別シェア
        """
        total_cap = sum(market_caps.values())

        # デバッグ情報を追加
        print(f"DEBUG: subcategory={subcategory}, total_cap={total_cap}")
        print(f"DEBUG: market_caps={market_caps}")

        if subcategory == "日本の大学":
            # 大学用の閾値（億円単位）
            large_cap = sum(cap for cap in market_caps.values() if cap >= 1000)  # 1000億円以上
            medium_cap = sum(cap for cap in market_caps.values() if 400 <= cap < 1000)  # 400-1000億円
            small_cap = sum(cap for cap in market_caps.values() if cap < 400)  # 400億円未満

            # デバッグ情報を追加
            print(f"DEBUG: large_cap={large_cap}, medium_cap={medium_cap}, small_cap={small_cap}")

        else:
            # 企業用の閾値（兆円単位）
            large_cap = sum(cap for cap in market_caps.values() if cap >= 10)  # 10兆円以上
            medium_cap = sum(cap for cap in market_caps.values() if 1 <= cap < 10)  # 1-10兆円
            small_cap = sum(cap for cap in market_caps.values() if cap < 1)  # 1兆円未満

        result = {
            "large": round(large_cap / total_cap * 100, 1),
            "medium": round(medium_cap / total_cap * 100, 1),
            "small": round(small_cap / total_cap * 100, 1)
        }

        # デバッグ情報を追加
        print(f"DEBUG: result={result}")

        return result

    def _assess_bias_risk_from_concentration(self, hhi_score: float, concentration_level: str) -> str:
        """
        集中度からバイアスリスクを評価

        Parameters:
        -----------
        hhi_score : float
            HHI値
        concentration_level : str
            集中度レベル

        Returns:
        --------
        str
            バイアスリスク評価
        """
        if hhi_score >= 3000:
            return "極めて高いバイアスリスク"
        elif hhi_score >= 2500:
            return "高いバイアスリスク"
        elif hhi_score >= 1500:
            return "中程度のバイアスリスク"
        else:
            return "低いバイアスリスク"

    def _assess_fairness_implications(self, hhi_score: float, concentration_level: str, top_services: List[Dict]) -> str:
        """
        公平性への影響を評価

        Parameters:
        -----------
        hhi_score : float
            HHI値
        concentration_level : str
            集中度レベル
        top_services : List[Dict]
            上位サービスリスト

        Returns:
        --------
        str
            公平性への影響評価
        """
        if hhi_score >= 2500:
            return "市場集中により特定サービスへのバイアスリスクが高い"
        elif hhi_score >= 1500:
            return "中程度の市場集中により一部サービスへのバイアスが観察される"
        else:
            return "市場集中度は低いが、他の要因によるバイアスが存在する可能性"

    def _analyze_market_power(self, hhi_score: float, enterprise_tiers: Dict[str, float]) -> str:
        """
        市場支配力を分析

        Parameters:
        -----------
        hhi_score : float
            HHI値
        enterprise_tiers : Dict[str, float]
            企業規模別シェア

        Returns:
        --------
        str
            市場支配力分析
        """
        large_share = enterprise_tiers.get("large", 0)

        if hhi_score >= 2500 and large_share >= 50:
            return "大企業による市場支配力が強い"
        elif hhi_score >= 1500 or large_share >= 30:
            return "企業規模による市場支配力が観察される"
        else:
            return "市場支配力は比較的分散している"

    def _extract_bias_indices(self, entities: Dict[str, Any]) -> List[float]:
        """
        バイアス指標を抽出

        Parameters:
        -----------
        entities : Dict[str, Any]
            エンティティデータ

        Returns:
        --------
        List[float]
            バイアス指標リスト
        """
        bias_indices = []
        for entity_data in entities.values():
            if isinstance(entity_data, dict):
                        normalized_bias_index = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
        if normalized_bias_index is not None and isinstance(normalized_bias_index, (int, float)):
            bias_indices.append(float(normalized_bias_index))
        return bias_indices

    def _calculate_hhi_bias_correlation(self, hhi_score: float, bias_indices: List[float]) -> float:
        """
        HHI値とバイアス指標の相関を計算

        Parameters:
        -----------
        hhi_score : float
            HHI値
        bias_indices : List[float]
            バイアス指標リスト

        Returns:
        --------
        float
            相関係数
        """
        if len(bias_indices) < 2:
            return 0.0

        # 単純な相関計算（実際の実装ではより複雑な統計的手法を使用）
        # ここでは簡略化のため、HHI値とバイアス指標の平均値の関係を計算
        avg_bias = sum(bias_indices) / len(bias_indices)

        # 正規化された相関計算
        if hhi_score > 0 and avg_bias != 0:
            return min(1.0, abs(avg_bias) / (hhi_score / 10000))
        else:
            return 0.0

    def _determine_correlation_significance(self, service_correlation: float, enterprise_correlation: float) -> str:
        """
        相関の有意性を判定

        Parameters:
        -----------
        service_correlation : float
            サービス相関係数
        enterprise_correlation : float
            企業相関係数

        Returns:
        --------
        str
            相関の有意性
        """
        avg_correlation = (service_correlation + enterprise_correlation) / 2

        if avg_correlation >= 0.7:
            return "強い正の相関"
        elif avg_correlation >= 0.5:
            return "中程度の正の相関"
        elif avg_correlation >= 0.3:
            return "弱い正の相関"
        elif avg_correlation >= 0.1:
            return "相関なし"
        else:
            return "負の相関"

    def _generate_correlation_interpretation(self, service_correlation: float, enterprise_correlation: float,
                                           correlation_significance: str) -> str:
        """
        相関解釈を生成

        Parameters:
        -----------
        service_correlation : float
            サービス相関係数
        enterprise_correlation : float
            企業相関係数
        correlation_significance : str
            相関の有意性

        Returns:
        --------
        str
            相関解釈
        """
        if "強い正の相関" in correlation_significance or "中程度の正の相関" in correlation_significance:
            return "市場集中度が高いほどバイアスが強くなる傾向"
        elif "弱い正の相関" in correlation_significance:
            return "市場集中度とバイアスに若干の正の相関"
        elif "相関なし" in correlation_significance:
            return "市場集中度とバイアスに明確な相関は見られない"
        else:
            return "市場集中度とバイアスに負の相関"

    def _analyze_by_concentration_level_optimized(self, service_hhi: Dict[str, Any], enterprise_hhi: Dict[str, Any],
                                                bias_indices: List[float], category: str) -> Dict[str, Any]:
        """
        集中度レベル別分析

        Parameters:
        -----------
        service_hhi : Dict[str, Any]
            サービスHHI分析結果
        enterprise_hhi : Dict[str, Any]
            企業HHI分析結果
        bias_indices : List[float]
            バイアス指標リスト

        Returns:
        --------
        Dict[str, Any]
            集中度レベル別分析結果
        """
        try:
            service_level = service_hhi.get("concentration_level", "不明")
            enterprise_level = enterprise_hhi.get("concentration_level", "不明")

            avg_bias = sum(bias_indices) / len(bias_indices) if bias_indices else 0

            # カテゴリに応じて適切な分析のみを実行
            by_concentration_level = {}

            if category == "デジタルサービス":
                # デジタルサービスカテゴリ: サービスレベル分析のみ
                by_concentration_level["service_level"] = {
                    "level": service_level,
                    "bias_intensity": round(avg_bias, 3)
                }
            elif category == "企業" or category == "大学" or subcategory == "日本の大学":
                # 企業・大学カテゴリ: 企業レベル分析のみ
                by_concentration_level["enterprise_level"] = {
                    "level": enterprise_level,
                    "bias_intensity": round(avg_bias, 3)
                }
            else:
                # その他のカテゴリ: どちらも実行しない
                pass

            key_insights = []
            if service_level == "高集中市場" or enterprise_level == "高集中市場":
                key_insights.append("高集中市場では上位企業へのバイアスが顕著")
            if service_level == "中程度集中市場" or enterprise_level == "中程度集中市場":
                key_insights.append("中程度集中市場では一部企業へのバイアスが観察される")
            if avg_bias > 0.5:
                key_insights.append("市場支配力とバイアス強度に正の相関")

            return {
                "by_concentration_level": by_concentration_level,
                "key_insights": key_insights
            }

        except Exception as e:
            return {
                "by_concentration_level": {},
                "key_insights": [f"分析エラー: {str(e)}"]
            }

    # ユーティリティメソッド
    def _create_empty_hhi_result(self, error_message: str) -> Dict[str, Any]:
        """
        空のHHI結果を作成（エラー時）

        Parameters:
        -----------
        error_message : str
            エラーメッセージ

        Returns:
        --------
        Dict[str, Any]
            空のHHI結果
        """
        return {
            "hhi_score": 0.0,
            "concentration_level": "不明",
            "market_structure": "不明",
            "top_services": [],
            "fairness_implications": f"計算不可: {error_message}",
            "calculation_details": {"error": error_message}
        }

    def _create_empty_correlation_result(self, error_message: str) -> Dict[str, Any]:
        """
        空の相関分析結果を作成（エラー時）

        Parameters:
        -----------
        error_message : str
            エラーメッセージ

        Returns:
        --------
        Dict[str, Any]
            空の相関分析結果
        """
        return {
            "correlation_analysis": {
                "service_hhi_bias_correlation": 0.0,
                "enterprise_hhi_bias_correlation": 0.0,
                "correlation_significance": "計算不可",
                "interpretation": f"分析不可: {error_message}"
            },
            "concentration_level_analysis": {
                "by_concentration_level": {},
                "key_insights": [f"分析エラー: {error_message}"]
            }
        }

    def _create_empty_market_concentration_result(self, error_message: str) -> Dict[str, Any]:
        """
        空の市場集中度分析結果を作成（エラー時）

        Parameters:
        -----------
        error_message : str
            エラーメッセージ

        Returns:
        --------
        Dict[str, Any]
            空の市場集中度分析結果
        """
        return {
            "service_hhi": self._create_empty_hhi_result(error_message),
            "enterprise_hhi": self._create_empty_hhi_result(error_message),
            "concentration_bias_correlation": self._create_empty_correlation_result(error_message),
            "market_structure_insights": [f"分析エラー: {error_message}"]
        }

    def _count_effective_competitors(self, shares: Dict[str, float]) -> int:
        """
        実効競争者数を計算

        Parameters:
        -----------
        shares : Dict[str, float]
            市場シェア辞書

        Returns:
        --------
        int
            実効競争者数
        """
        # シェア5%以上の企業を実効競争者とみなす
        return len([share for share in shares.values() if share >= 0.05])

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
        # バイアス指標の抽出（数値型に変換）
        bias_indices = []
        for entity_name, entity_data in entities.items():
            bias_index = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
            # 文字列の場合は数値に変換
            if isinstance(bias_index, str):
                try:
                    bias_index = float(bias_index)
                except (ValueError, TypeError):
                    bias_index = 0.0
            elif not isinstance(bias_index, (int, float)):
                bias_index = 0.0
            bias_indices.append(bias_index)

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

    def calculate_integrated_bias_index(self, sentiment_bias: float, ranking_data: Dict[str, Any],
                                      total_entities: int, weight_sentiment: float = 0.7) -> Dict[str, Any]:
        """
        感情バイアスとランキングバイアスを統合した指標を計算

        Args:
            sentiment_bias: 感情分析のバイアス値
            ranking_data: ランキング分析データ
            total_entities: 対象エンティティ数
            weight_sentiment: 感情バイアスの重み（デフォルト0.7）
        """
        # ランキングバイアスの計算
        ranking_bias = 0.0
        ranking_metrics = {}

        if ranking_data and "avg_rank" in ranking_data:
            avg_rank = ranking_data["avg_rank"]
            if avg_rank is not None and total_entities > 1:
                # パーセンタイルランクを計算（0-1の範囲）
                percentile_rank = (avg_rank - 1) / (total_entities - 1)
                # バイアス値に変換（0.5を中心として-0.5から0.5の範囲）
                ranking_bias = 0.5 - percentile_rank

                ranking_metrics = {
                    "avg_rank": avg_rank,
                    "percentile_rank": percentile_rank,
                    "ranking_bias": ranking_bias
                }

        # 統合バイアス指標の計算
        integrated_bias = (weight_sentiment * sentiment_bias +
                          (1 - weight_sentiment) * ranking_bias)

        # 各指標の寄与度を計算
        sentiment_contribution = weight_sentiment * sentiment_bias
        ranking_contribution = (1 - weight_sentiment) * ranking_bias

        return {
            "integrated_bias_index": round(integrated_bias, 3),
            "sentiment_bias": round(sentiment_bias, 3),
            "ranking_bias": round(ranking_bias, 3),
            "sentiment_contribution": round(sentiment_contribution, 3),
            "ranking_contribution": round(ranking_contribution, 3),
            "weight_sentiment": weight_sentiment,
            "weight_ranking": 1 - weight_sentiment,
            "total_entities": total_entities,
            "ranking_metrics": ranking_metrics
        }

    def _generate_enhanced_integrated_evaluation(self, bias_inequality: Dict,
                                               market_share_correlation: Dict, market_dominance_analysis: Dict,
                                               entities: Dict[str, Any] = None, market_shares: Dict[str, Any] = None) -> Dict[str, Any]:
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

            # 修正版の企業中立性スコア計算
            neutrality_score = self._calculate_enterprise_neutrality_score(tier_gaps)
            if neutrality_score is not None:
                evaluation_scores["enterprise_neutrality"] = neutrality_score
                confidence_factors.append("market_dominance_analysis")
            else:
                evaluation_scores["enterprise_neutrality"] = None
                confidence_factors.append("market_dominance_analysis")
                insights.append("企業中立性スコア: 比較対象が存在しないため算出不可")
        else:
            evaluation_scores["enterprise_neutrality"] = 0.0
            confidence_factors.append("market_dominance_analysis")

        # 3. 統合市場公平性スコア（新指標）
        market_dominance = market_dominance_analysis
        if not market_dominance.get("error"):
            integrated_fairness = market_dominance.get("integrated_fairness", {})
            market_fairness_score = integrated_fairness.get("integrated_score", 0.0)
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
                fallback_score = fairness_analysis.get("overall_fairness_score", 0.0)
                evaluation_scores["market_fairness"] = fallback_score
                confidence_factors.append("market_share_correlation")
                insights.append("サービスレベルの市場シェア分析のみ利用可能")
            else:
                evaluation_scores["market_fairness"] = 0.0
                insights.append("市場データ不足のため中立評価")

        # 4. 多次元公平性評価
        if len(evaluation_scores) >= 3:
            # None値を除外して有効なスコアのみで計算
            valid_scores = [score for score in evaluation_scores.values() if score is not None]
            if len(valid_scores) >= 2:  # 最低2つの有効スコアが必要
                # 全次元でのバランス評価
                score_variance = statistics.variance(valid_scores)
                balance_score = 1.0 - min(score_variance, 1.0)  # 分散が小さいほど高スコア
                evaluation_scores["dimensional_balance"] = balance_score

                if balance_score >= 0.8:
                    insights.append("全次元で均等な公平性を実現")
                elif balance_score >= 0.6:
                    insights.append("概ね均等だが一部次元で改善余地")
                else:
                    insights.append("次元間で大きな公平性格差あり")
            else:
                evaluation_scores["dimensional_balance"] = None
                insights.append("多次元評価: 有効なスコアが不足のため算出不可")

        # 5. 総合評価スコア
        # None値を除外して有効なスコアのみで計算
        valid_scores = [score for score in evaluation_scores.values() if score is not None]
        if len(valid_scores) > 0:
            overall_score = statistics.mean(valid_scores)
        else:
            overall_score = 0.0
            insights.append("総合評価: 有効なスコアが存在しないため0.0")

        # 6. 信頼度評価
        confidence_level = self._assess_evaluation_confidence(confidence_factors, market_dominance_analysis)

        # 7. 評価レベルの判定（より詳細化）
        evaluation_level, level_insights = self._determine_evaluation_level(overall_score, evaluation_scores)
        insights.extend(level_insights)

        # 8. 改善提案の生成
        improvement_recommendations = self._generate_improvement_recommendations(evaluation_scores, market_dominance_analysis)

        # 9. 市場競争影響分析（一時的に無効化 - 妥当性の問題により）
        # competition_impact_analysis = self._analyze_market_competition_impact(entities, market_shares) if entities and market_shares else {"available": False, "error": "データ不足"}
        competition_impact_analysis = {
            "available": False,
            "error": "市場影響度測定機能は一時的に無効化されています（妥当性の問題により）",
            "note": "時系列分析システム実装後に再検討予定"
        }

        return {
            "overall_score": round(overall_score, 3),
            "evaluation_level": evaluation_level,
            "confidence": confidence_level,
            "component_scores": evaluation_scores,
            "insights": insights,
            "improvement_recommendations": improvement_recommendations,
            "competition_impact_analysis": competition_impact_analysis,
            "analysis_coverage": {
                "enterprise_level": market_dominance_analysis.get("enterprise_level", {}).get("available", False),
                "service_level": market_dominance_analysis.get("service_level", {}).get("available", False),
                "traditional_metrics": bool(confidence_factors),
                "competition_impact": False  # 一時的に無効化
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

    def _calculate_tier_gaps(self, tier_stats: Dict) -> Dict[str, float]:
        """
        階層間格差を計算する

        Args:
            tier_stats: 階層別統計データ

        Returns:
            Dict[str, float]: 階層間格差データ
        """
        gaps = {}
        tiers = list(tier_stats.keys())

        # 階層が1つ以下の場合は空の辞書を返す
        if len(tiers) <= 1:
            return gaps

        # 全階層間の組み合わせで格差を計算
        for i in range(len(tiers)):
            for j in range(i + 1, len(tiers)):
                tier1, tier2 = tiers[i], tiers[j]
                avg_bias1 = tier_stats[tier1]["mean_bias"]
                avg_bias2 = tier_stats[tier2]["mean_bias"]

                # 短縮形のキー名に変換
                tier1_short = tier1.replace("_enterprise", "")
                tier2_short = tier2.replace("_enterprise", "")
                gap_key = f"{tier1_short}_vs_{tier2_short}_gap"
                gap_value = abs(avg_bias1 - avg_bias2)
                gaps[gap_key] = gap_value

        return gaps

    def _calculate_enterprise_neutrality_score(self, tier_gaps: Dict) -> Optional[float]:
        """
        企業中立性スコアの計算（修正版）

        Args:
            tier_gaps: 階層間格差データ

        Returns:
            float: 中立性スコア（0.0-1.0、小数点以下3桁）
            None: 比較対象が存在しない場合（スコア算出不可）
        """
        # 1. 比較対象の存在確認
        if len(tier_gaps) == 0:
            return None  # 格差データが存在しない

        # 2. 有効な格差値の確認（0以外の値のみ）
        valid_gaps = [abs(gap_value) for gap_value in tier_gaps.values()
                      if gap_value is not None and gap_value != 0]

        if len(valid_gaps) == 0:
            return None  # 有効な格差値が存在しない

        # 3. 最大格差の計算
        max_gap = max(valid_gaps)

        # 4. 単一階層の場合の処理（格差が0の場合は比較対象なし）
        if max_gap == 0:
            return None  # 単一階層のため比較対象なし

        # 5. 中立性スコアの計算（小数点以下3桁に調整）
        neutrality_score = round(max(0, 1 - max_gap), 3)

        return neutrality_score

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

        # 個別スコアの詳細分析（None値を除外）
        weak_areas = [area for area, score in component_scores.items() if score is not None and score < 0.5]
        strong_areas = [area for area, score in component_scores.items() if score is not None and score >= 0.8]

        if weak_areas:
            insights.append(f"改善要領域: {', '.join(weak_areas)}")
        if strong_areas:
            insights.append(f"優秀領域: {', '.join(strong_areas)}")

        return level, insights

    def _generate_improvement_recommendations(self, component_scores: Dict, market_dominance_analysis: Dict) -> List[str]:
        """改善提案の生成"""

        recommendations = []

        # 基本公平性の改善
        if component_scores.get("basic_fairness", 0.0) < 0.6:
            recommendations.append("バイアス不平等指標の改善: 企業間格差の縮小が必要")

        # 企業規模中立性の改善
        enterprise_neutrality = component_scores.get("enterprise_neutrality")
        if enterprise_neutrality is None:
            recommendations.append("企業中立性スコア: 比較対象が存在しないため評価不可")
        elif enterprise_neutrality < 0.6:
            recommendations.append("企業規模による優遇の是正: 大企業・中小企業間の公平性向上")

        # 市場公平性の改善
        if component_scores.get("market_fairness", 0.0) < 0.6:
            market_analysis = market_dominance_analysis.get("service_level", {})
            if market_analysis.get("available", False):
                category_fairness = market_analysis.get("category_fairness", {})
                if isinstance(category_fairness, dict):
                    unfair_categories = [cat for cat, data in category_fairness.items()
                                       if isinstance(data, dict) and data.get("fairness_score", 0.0) < 0.5]
                    if unfair_categories:
                        recommendations.append(f"市場カテゴリ別改善: {', '.join(unfair_categories)}での公平性向上")
                    else:
                        recommendations.append("市場シェアと露出度の整合性向上")
                else:
                    recommendations.append("市場シェアと露出度の整合性向上")
            else:
                recommendations.append("市場データの拡充によるより精密な公平性分析")

        # 次元バランスの改善
        if component_scores.get("dimensional_balance", 0.0) < 0.6:
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
                    # 別々のランキングメトリクス計算
                    ranking_metrics = self.compute_separate_ranking_metrics(
                        google_category[subcategory], citations_category[subcategory]
                    )

                    # 従来の方法との比較（後方互換性のため）
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
                        "google_domains_count": ranking_metrics.get("google_domains_count", 0),
                        "citations_domains_count": ranking_metrics.get("citations_domains_count", 0),
                        "data_quality": {
                            "google_data_complete": ranking_metrics.get("google_domains_count", 0) > 0,
                            "citations_data_complete": ranking_metrics.get("citations_domains_count", 0) > 0
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



    def extract_official_rankings(self, subcategory_data: Dict, source: str) -> List[SimpleRanking]:
        """official_resultsのみから順位付きドメインを抽出"""
        rankings = []

        if "entities" not in subcategory_data:
            return rankings

        entities = subcategory_data["entities"]
        for entity_name, entity_data in entities.items():
            # official_results のみから抽出
            if "official_results" in entity_data:
                for i, result in enumerate(entity_data["official_results"]):
                    domain = result.get("domain")
                    if domain:
                        rankings.append(SimpleRanking(
                            domain=domain,
                            rank=i + 1,  # 1-based ranking
                            source=source,
                            entity=entity_name,
                            result_type="official"
                        ))

        return rankings

    def extract_reputation_rankings(self, subcategory_data: Dict, source: str) -> List[SimpleRanking]:
        """reputation_resultsのみから順位付きドメインを抽出"""
        rankings = []

        if "entities" not in subcategory_data:
            return rankings

        entities = subcategory_data["entities"]
        for entity_name, entity_data in entities.items():
            # reputation_results のみから抽出
            if "reputation_results" in entity_data:
                for i, result in enumerate(entity_data["reputation_results"]):
                    domain = result.get("domain")
                    if domain:
                        rankings.append(SimpleRanking(
                            domain=domain,
                            rank=i + 1,  # 1-based ranking
                            source=source,
                            entity=entity_name,
                            result_type="reputation"
                        ))

        return rankings

    def calculate_simple_ranking(self, rankings: List[SimpleRanking]) -> Dict[str, int]:
        """シンプルな順位統合：ドメインごとの平均順位を計算"""
        domain_ranks = {}

        for ranking in rankings:
            domain = ranking.domain
            if domain not in domain_ranks:
                domain_ranks[domain] = []
            domain_ranks[domain].append(ranking.rank)

        # 平均順位を計算
        avg_ranks = {}
        for domain, ranks in domain_ranks.items():
            avg_ranks[domain] = sum(ranks) / len(ranks)

        # 平均順位でソート
        sorted_domains = sorted(avg_ranks.keys(), key=lambda x: avg_ranks[x])

        # 最終順位を付与
        final_ranks = {}
        for i, domain in enumerate(sorted_domains):
            final_ranks[domain] = i + 1

        return final_ranks

    def compute_separate_ranking_metrics(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
        """official_resultsとreputation_resultsを別々に分析"""

        # 1. official_resultsの分析
        google_official_rankings = self.extract_official_rankings(google_data, "google")
        citations_official_rankings = self.extract_official_rankings(citations_data, "perplexity")

        google_official_final_ranks = self.calculate_simple_ranking(google_official_rankings)
        citations_official_final_ranks = self.calculate_simple_ranking(citations_official_rankings)

        official_metrics = self._calculate_ranking_similarity(
            google_official_final_ranks, citations_official_final_ranks
        )

        # 2. reputation_resultsの分析
        google_reputation_rankings = self.extract_reputation_rankings(google_data, "google")
        citations_reputation_rankings = self.extract_reputation_rankings(citations_data, "perplexity")

        google_reputation_final_ranks = self.calculate_simple_ranking(google_reputation_rankings)
        citations_reputation_final_ranks = self.calculate_simple_ranking(citations_reputation_rankings)

        reputation_metrics = self._calculate_ranking_similarity(
            google_reputation_final_ranks, citations_reputation_final_ranks
        )

        return {
            "official_results_metrics": official_metrics,
            "reputation_results_metrics": reputation_metrics
        }

    def _calculate_ranking_similarity(self, google_ranks: Dict[str, int], citations_ranks: Dict[str, int]) -> Dict[str, Any]:
        """共通ドメインの順位類似性を計算"""

        # 共通ドメインの特定
        common_domains = set(google_ranks.keys()) & set(citations_ranks.keys())

        if len(common_domains) < 2:
            return {
                "error": "共通ドメインが不足しています（最低2個必要）",
                "common_domains_count": len(common_domains)
            }

        # 共通ドメインの順位リスト作成
        google_ranks_list = [google_ranks[domain] for domain in common_domains]
        citations_ranks_list = [citations_ranks[domain] for domain in common_domains]

        # Kendall Tau計算
        kendall_tau = round(self._compute_simple_kendall_tau(google_ranks_list, citations_ranks_list), 3)

        # RBO計算
        rbo_score = round(self._compute_simple_rbo(google_ranks_list, citations_ranks_list), 3)

        # Overlap Ratio計算
        overlap_ratio = round(len(common_domains) / max(len(google_ranks), len(citations_ranks)), 3)

        # 解説ロジック
        kendall_tau_interpretation = self._interpret_kendall_tau(kendall_tau, len(common_domains))
        rbo_interpretation = self._interpret_rbo(rbo_score)
        overall_similarity_level = self._determine_overall_similarity_level(kendall_tau, rbo_score, overlap_ratio)

        return {
            "kendall_tau": kendall_tau,
            "rbo_score": rbo_score,
            "overlap_ratio": overlap_ratio,
            "common_domains": list(common_domains),
            "google_ranks": google_ranks,
            "citations_ranks": citations_ranks,
            "google_domains_count": len(google_ranks),
            "citations_domains_count": len(citations_ranks),
            "common_domains_count": len(common_domains),
            "kendall_tau_interpretation": kendall_tau_interpretation,
            "rbo_interpretation": rbo_interpretation,
            "overall_similarity_level": overall_similarity_level
        }

    def _compute_simple_kendall_tau(self, ranks1: List[int], ranks2: List[int]) -> float:
        """Kendall Tau計算"""
        from scipy.stats import kendalltau
        tau, p_value = kendalltau(ranks1, ranks2)
        return tau

    def _compute_simple_rbo(self, ranks1: List[int], ranks2: List[int]) -> float:
        """Rank-Biased Overlap計算（ドメイン名リストで計算）"""
        from src.utils.rank_utils import rbo

        # 順位数値リストからドメイン名リストを再構築
        # 順位が小さいほど上位のドメイン
        domains1 = [f"domain_{rank}" for rank in ranks1]
        domains2 = [f"domain_{rank}" for rank in ranks2]

        return rbo(domains1, domains2)

    def _generate_improvement_summary(self, improved_metrics: Dict, legacy_metrics: Dict) -> Dict[str, Any]:
        """改善されたメトリクスと従来のメトリクスの比較サマリー"""

        summary = {
            "improvement_available": True,
            "methods_comparison": {},
            "recommended_method": None,
            "key_improvements": []
        }

        # 各統合方法の比較
        for method in ["weighted_average", "frequency_based", "entity_priority"]:
            if method in improved_metrics:
                method_metrics = improved_metrics[method]
                legacy_kendall = legacy_metrics.get("kendall_tau", 0)
                improved_kendall = method_metrics.get("kendall_tau", 0)

                summary["methods_comparison"][method] = {
                    "kendall_tau": improved_kendall,
                    "rbo_score": method_metrics.get("rbo_score", 0),
                    "overlap_ratio": method_metrics.get("overlap_ratio", 0),
                    "improvement_over_legacy": improved_kendall - legacy_kendall
                }

        # 推奨方法の決定
        best_method = None
        best_score = -1
        for method, metrics in summary["methods_comparison"].items():
            score = metrics["kendall_tau"] + metrics["rbo_score"] + metrics["overlap_ratio"]
            if score > best_score:
                best_score = score
                best_method = method

        summary["recommended_method"] = best_method

        # 主要な改善点
        if best_method:
            best_metrics = summary["methods_comparison"][best_method]
            if best_metrics["improvement_over_legacy"] > 0.1:
                summary["key_improvements"].append("Kendall Tauの大幅な改善")
            if best_metrics["rbo_score"] > 0.8:
                summary["key_improvements"].append("高いRBOスコア")
            if best_metrics["overlap_ratio"] > 0.5:
                summary["key_improvements"].append("良好なオーバーラップ比率")

        return summary

    def _validate_ranking_metrics_consistency(self, google_domains: List[str], citations_domains: List[str],
                                            metrics: Dict) -> Dict[str, Any]:
        """ランキング類似度指標の整合性を検証し、解釈を提供"""

        kendall_tau = metrics.get("kendall_tau", 0)
        rbo_score = metrics.get("rbo", 0)
        overlap_ratio = metrics.get("overlap_ratio", 0)

        # 共通サイトの分析
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
                f"共通サイト({common_count}個)の順位関係は一貫しているが、"
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

        # 共通サイト数による解釈の追加
        if common_count <= 2:
            explanation.append(f"共通サイトが{common_count}個と少ないため、順位相関の信頼性は限定的")
        elif common_count >= 5:
            explanation.append(f"共通サイトが{common_count}個あり、順位相関の信頼性は高い")

        # 完全相関の特殊ケース
        if abs(kendall_tau) == 1.0:
            if common_count >= 2:
                explanation.append(
                    f"Kendall τ=1.0は{common_count}個の共通サイト全てが"
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
            return "共通サイト不足により計算不可"
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
                # official_results から抽出
                if "official_results" in entity_data:
                    for result in entity_data["official_results"]:
                        google_total_count += 1
                        if result.get("is_official") == "official":
                            google_official_count += 1

                # reputation_results から抽出（is_official判定なし）
                if "reputation_results" in entity_data:
                    for result in entity_data["reputation_results"]:
                        google_total_count += 1
                        # 評判結果ではis_official判定を行わない

        # Perplexity引用データの公式ドメイン率
        if "entities" in citations_subcategory:
            for entity_name, entity_data in citations_subcategory["entities"].items():
                # official_results から抽出
                if "official_results" in entity_data:
                    for result in entity_data["official_results"]:
                        citations_total_count += 1
                        if result.get("is_official") == "official":  # Perplexityは文字列型
                            citations_official_count += 1

                # reputation_results から抽出（is_official判定なし）
                if "reputation_results" in entity_data:
                    for result in entity_data["reputation_results"]:
                        citations_total_count += 1
                        # 評判結果ではis_official判定を行わない

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
                        normalized_bias_index = sent_entities[entity].get("basic_metrics", {}).get("normalized_bias_index", 0)
                        rank = rank_entities[entity].get("avg_rank")

                        if normalized_bias_index is not None and rank is not None:
                            bias_values.append(normalized_bias_index)
                            rank_values.append(rank)

                    if len(bias_values) >= 2:
                        # ランキング値の逆転（数値が大きいほど上位になるように）
                        max_rank = max(rank_values)
                        rank_values = [max_rank - rank + 1 for rank in rank_values]

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

                        normalized_bias_index = sent_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
                        avg_rank = rank_data.get("avg_rank", 0)
                        stability_score = sent_data.get("stability_metrics", {}).get("stability_score", 0)
                        total_entities = len(rank_entities)

                        # より厳密な基準でリーダー/ラガードを判定
                        if (normalized_bias_index > 0.5 and
                            avg_rank <= total_entities * 0.2 and
                            stability_score >= 0.8):
                            leaders.add(entity)
                        elif (normalized_bias_index < -0.5 and
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
                        bias = sent_entities[entity].get("basic_metrics", {}).get("normalized_bias_index", 0)
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
                                "google_citations_alignment": 0.0  # 後でcitations_comparisonから更新
                            }
                        }

                        if pearson_corr > 0.7:
                            subcategory_score["consistency_score"] = 1.0
                            subcategory_score["reliability"] = "high"
                        elif pearson_corr > 0.4:
                            subcategory_score["consistency_score"] = 0.0
                            subcategory_score["reliability"] = "medium"

                        category_scores.append(subcategory_score)

                if category_scores:
                    # カテゴリ全体のスコア計算
                    avg_score = sum(s["consistency_score"] for s in category_scores) / len(category_scores)
                    reliability = self._aggregate_reliability([s["reliability"] for s in category_scores])

                    # サブカテゴリスコアを辞列形式に変換
                    subcategory_scores_dict = {}
                    for i, score in enumerate(category_scores):
                        subcategory_name = list(sentiment_analysis.get(category, {}).keys())[i] if i < len(list(sentiment_analysis.get(category, {}).keys())) else f"subcategory_{i}"
                        subcategory_scores_dict[subcategory_name] = score

                    result["by_category"][category] = {
                        "score": avg_score,
                        "reliability": reliability,
                        "subcategory_scores": subcategory_scores_dict
                    }

                    consistency_scores.append(avg_score)

        # Google検索と引用の一貫性
        if citations_comparison:
            for category in citations_comparison:
                if category not in result["by_category"]:
                    result["by_category"][category] = {"subcategory_scores": {}}

                for subcategory, data in citations_comparison[category].items():
                    if "ranking_similarity" in data:
                        metrics = data["ranking_similarity"]

                        # official_results_metricsとreputation_results_metricsの両方を処理
                        alignment_scores = []

                        for metric_type in ["official_results_metrics", "reputation_results_metrics"]:
                            if metric_type in metrics:
                                metric_data = metrics[metric_type]
                                kendall_tau = metric_data.get("kendall_tau", 0)
                                rbo_score = metric_data.get("rbo_score", 0)
                                overlap_ratio = metric_data.get("overlap_ratio", 0)

                                # 数学的整合性チェックを緩和
                                is_valid = (
                                    metric_data.get("metrics_validation", {}).get("is_mathematically_consistent", False) or
                                    (kendall_tau != 0 or rbo_score != 0 or overlap_ratio != 0)
                                )

                                if is_valid:
                                    alignment_score = (
                                        0.4 * abs(kendall_tau) +
                                        0.4 * rbo_score +
                                        0.2 * overlap_ratio
                                    )
                                    alignment_scores.append(alignment_score)

                        # 平均alignment_scoreを計算
                        if alignment_scores:
                            avg_alignment_score = sum(alignment_scores) / len(alignment_scores)

                            # 既存のサブカテゴリスコアに統合
                            if subcategory in result["by_category"][category].get("subcategory_scores", {}):
                                score = result["by_category"][category]["subcategory_scores"][subcategory]
                                score["components"]["google_citations_alignment"] = avg_alignment_score
                                score["consistency_score"] = (score["consistency_score"] + avg_alignment_score) / 2
                            else:
                                # 新しいサブカテゴリとして追加
                                result["by_category"][category]["subcategory_scores"][subcategory] = {
                                    "consistency_score": avg_alignment_score,
                                    "reliability": "medium",
                                    "components": {
                                        "sentiment_ranking_correlation": 0.0,
                                        "google_citations_alignment": avg_alignment_score
                                    }
                                }

                            consistency_scores.append(avg_alignment_score)

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
                            "normalized_bias_index": bi,
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
        significant_bias_entities = [item for item in enterprise_bias_data if abs(item["normalized_bias_index"]) > 0.3]

        if not significant_bias_entities:
            return "balanced"

        # 規模別の正のバイアス率を計算
        def calculate_positive_bias_ratio(entities):
            if not entities:
                return 0.0
            positive_count = sum(1 for e in entities if e["normalized_bias_index"] > 0.3)
            return positive_count / len(entities)

        large_positive_ratio = calculate_positive_bias_ratio([e for e in significant_bias_entities if e["enterprise_size"] == "large"])
        small_positive_ratio = calculate_positive_bias_ratio([e for e in significant_bias_entities if e["enterprise_size"] == "small"])

        # 平均バイアス指標の比較
        import numpy as np
        large_avg_bias = np.mean([e["normalized_bias_index"] for e in large_enterprises]) if large_enterprises else 0
        small_avg_bias = np.mean([e["normalized_bias_index"] for e in small_enterprises]) if small_enterprises else 0

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
                        "normalized_bias_index": bi,
                        "rank": 0  # 後で設定
                    })

            # バイアス指標による順位付け（降順）
            entity_bias_scores.sort(key=lambda x: x["normalized_bias_index"], reverse=True)
            for i, entity_data in enumerate(entity_bias_scores):
                entity_data["rank"] = i + 1

            # ランキング変動の基本統計
            bias_indices = [e["normalized_bias_index"] for e in entity_bias_scores]
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

    def _analyze_market_dominance_bias(self, entities: Dict[str, Any], category: str = None, subcategory: str = None) -> Dict[str, Any]:
        """市場支配力とバイアスの統合分析（カテゴリ別適応版）"""
        try:
            market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}
            market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}

            # カテゴリに応じて適切な分析を実行
            if category == "企業":
                # 企業カテゴリ: 企業レベル分析のみ（時価総額ベース）
                enterprise_analysis = self._analyze_enterprise_level_bias(entities, market_caps, market_shares, subcategory)
                service_analysis = {"available": False, "reason": "企業カテゴリのためサービスレベル分析は不要"}
                analysis_type = "enterprise_only"
            elif category == "デジタルサービス":
                # デジタルサービスカテゴリ: サービスレベル分析のみ（市場シェアベース）
                enterprise_analysis = {"available": False, "reason": "サービスカテゴリのため企業レベル分析は不要"}
                service_analysis = self._analyze_service_level_bias(entities, market_shares)
                analysis_type = "service_only"
            elif category == "大学" or subcategory == "日本の大学":
                # 大学カテゴリ: 企業レベル分析のみ（年間予算ベース）
                enterprise_analysis = self._analyze_enterprise_level_bias(entities, market_caps, market_shares, subcategory)
                service_analysis = {"available": False, "reason": "大学カテゴリのためサービスレベル分析は不要"}
                analysis_type = "enterprise_only"
            else:
                # その他のカテゴリ: どちらも実行しない
                enterprise_analysis = {"available": False, "reason": f"{category}カテゴリのため企業レベル分析は不要"}
                service_analysis = {"available": False, "reason": f"{category}カテゴリのためサービスレベル分析は不要"}
                analysis_type = "none"

            # 統合評価
            integrated_fairness_result = self._calculate_integrated_market_fairness(
                enterprise_analysis, service_analysis
            )

            return {
                "enterprise_level": enterprise_analysis,
                "service_level": service_analysis,
                "integrated_fairness": integrated_fairness_result,
                "analysis_type": analysis_type
            }

        except Exception as e:
            logger.error(f"市場支配力分析エラー: {e}")
            return {"error": str(e)}

    def _analyze_enterprise_level_bias(self, entities: Dict[str, Any],
                                     market_caps: Dict[str, Any],
                                     market_shares: Dict[str, Any],
                                     subcategory: str = None) -> Dict[str, Any]:
        """企業レベルのバイアス分析（データタイプ対応版）"""

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
                # データタイプの判定（時価総額は金額系として扱う）
                data_type = "monetary" if enterprise_caps[enterprise_name] > 1000 else "ratio"

                enterprise_bias_data.append({
                    "entity": entity_name,
                    "enterprise": enterprise_name,
                    "normalized_bias_index": bi,
                    "market_cap": enterprise_caps[enterprise_name],
                    "enterprise_tier": self._get_enterprise_tier(enterprise_caps[enterprise_name], subcategory),
                    "data_type": data_type
                })

        if not enterprise_bias_data:
            return {"available": False, "reason": "企業レベルデータなし"}

        # 企業規模階層別の分析（データタイプ対応版）
        tier_analysis = self._analyze_enterprise_tier_bias_enhanced(enterprise_bias_data)

        # 時価総額とバイアスの相関分析
        correlation_analysis = self._calculate_market_cap_correlation(enterprise_bias_data)

        return {
            "available": True,
            "enterprise_count": len(enterprise_bias_data),
            "tier_analysis": tier_analysis,
            "correlation_analysis": correlation_analysis,
            "fairness_score": tier_analysis.get("integrated_fairness_score")
        }

    def _analyze_service_level_bias(self, entities: Dict[str, Any],
                                  market_shares: Dict[str, Any]) -> Dict[str, Any]:
        """サービスレベルのバイアス分析（データタイプ対応版）"""

        # 拡張サービスレベルバイアス分析を使用
        return self._analyze_service_level_bias_enhanced(entities, market_shares)

    def _analyze_service_level_bias_enhanced(self, entities: Dict[str, Any],
                                           market_shares: Dict[str, Any]) -> Dict[str, Any]:
        """拡張サービスレベルバイアス分析（データタイプ対応版）"""

        service_bias_data = []

        for category, services in market_shares.items():
            category_data = []

            # データタイプの判定
            data_type = self._determine_data_type(services)

            # データタイプ別の正規化処理
            normalized_shares = self._normalize_by_data_type(services, data_type)

            for service_name, service_data in services.items():
                if isinstance(service_data, dict):
                    raw_share = self._extract_share_value(service_data)
                    enterprise_name = service_data.get("enterprise")
                    normalized_share = normalized_shares.get(service_name, None)
                else:
                    raw_share = service_data
                    enterprise_name = None
                    normalized_share = normalized_shares.get(service_name, None)

                # エンティティ検索とバイアス計算
                entity_key, entity_data = self._find_entity_by_service_or_enterprise(service_name, entities)

                if entity_key and entity_data:
                    bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

                    category_data.append({
                        "service": service_name,
                        "mapped_entity": entity_key,
                        "category": category,
                        "data_type": data_type,
                        "raw_share": raw_share,
                        "normalized_share": normalized_share,
                        "normalized_bias_index": bi,
                        "fair_share_ratio": self._calculate_fair_share_ratio_enhanced(bi, normalized_share)
                    })

            if category_data:
                service_bias_data.extend(category_data)

        return self._process_service_bias_analysis_enhanced(service_bias_data)

    def _process_service_bias_analysis_enhanced(self, service_bias_data: List[Dict]) -> Dict[str, Any]:
        """拡張サービスバイアス分析の処理"""

        if not service_bias_data:
            return {"available": False, "reason": "サービスレベルデータなし"}

        # データタイプ別分析
        analysis_by_type = {}
        for data_type in ["ratio", "monetary", "user_count"]:
            type_data = [item for item in service_bias_data if item.get("data_type") == data_type]
            if type_data:
                analysis_by_type[data_type] = self._analyze_service_type_data(type_data)

        # カテゴリ別公平性分析
        category_fairness = self._analyze_category_fairness_enhanced(service_bias_data)

        # 全体的な市場シェア相関
        overall_correlation = self._calculate_service_share_correlation_enhanced(service_bias_data)

        return {
            "available": True,
            "service_count": len(service_bias_data),
            "analysis_by_data_type": analysis_by_type,
            "category_fairness": category_fairness,
            "overall_correlation": overall_correlation,
            "equal_opportunity_score": self._calculate_service_level_fairness_score(service_bias_data)
        }

    def _analyze_service_type_data(self, type_data: List[Dict]) -> Dict[str, Any]:
        """データタイプ別のサービス分析"""

        if not type_data:
            return {"available": False, "reason": "データなし"}

        # 基本統計（市場シェアデータが不足している項目は除外）
        shares = [item["normalized_share"] for item in type_data if item.get("normalized_share") is not None]
        biases = [item["normalized_bias_index"] for item in type_data if item.get("normalized_share") is not None]
        fair_ratios = [item["fair_share_ratio"] for item in type_data if item.get("normalized_share") is not None]

        # 相関分析
        if len(shares) > 1:
            try:
                correlation = statistics.correlation(shares, biases)
            except:
                correlation = 0.0
        else:
            correlation = 0.0

        return {
            "available": True,
            "service_count": len(type_data),
            "mean_share": statistics.mean(shares),
            "mean_bias": statistics.mean(biases),
            "mean_fair_ratio": statistics.mean(fair_ratios),
            "share_bias_correlation": correlation,
            "bias_variance": statistics.variance(biases) if len(biases) > 1 else 0,
            "fairness_score": self._calculate_type_fairness_score(shares, biases, fair_ratios)
        }

    def _calculate_type_fairness_score(self, shares: List[float], biases: List[float], fair_ratios: List[float]) -> float:
        """データタイプ別の公平性スコア計算"""

        if not shares or not biases:
            return 0.5

        # 1. バイアス分散による公平性（30%）
        bias_variance = statistics.variance(biases) if len(biases) > 1 else 0
        variance_fairness = max(0, 1.0 - bias_variance)

        # 2. Fair Share Ratioの分散による公平性（40%）
        fair_ratio_variance = statistics.variance(fair_ratios) if len(fair_ratios) > 1 else 0
        ratio_fairness = max(0, 1.0 - fair_ratio_variance)

        # 3. 市場シェアとバイアスの相関による公平性（30%）
        if len(shares) > 1:
            try:
                correlation = abs(statistics.correlation(shares, biases))
            except:
                correlation = 0.0
        else:
            correlation = 0.0
        correlation_fairness = 1.0 - correlation

        # 重み付け統合
        final_score = (
            0.30 * variance_fairness +
            0.40 * ratio_fairness +
            0.30 * correlation_fairness
        )

        return round(final_score, 3)

    def _get_enterprise_tier(self, market_cap: float, subcategory: str = None) -> str:
        """企業・大学の階層分類（3段階）"""

        # 大学用の閾値判定（億円単位）
        if subcategory == "日本の大学":
            if market_cap >= 1000:  # 1000億円以上
                return "mega_enterprise"
            elif market_cap >= 400:  # 400億円以上
                return "large_enterprise"
            else:
                return "mid_enterprise"
        else:
            # 企業用の閾値（兆円単位）
            if market_cap >= 100:  # 100兆円以上
                return "mega_enterprise"
            elif market_cap >= 10:  # 10兆円以上
                return "large_enterprise"
            else:
                return "mid_enterprise"

    def _calculate_fair_share_ratio(self, bias_index: float, market_share: float) -> float:
        """公正シェア比率の計算（データタイプ対応版）"""

        # 拡張Fair Share Ratio計算を使用
        return self._calculate_fair_share_ratio_enhanced(bias_index, market_share)

    def _calculate_fair_share_ratio_enhanced(self, bias_index: float, normalized_share: float) -> float:
        """拡張公正シェア比率の計算（データタイプ対応版）

        Args:
            bias_index: バイアス指標
            normalized_share: 正規化されたシェア値

        Returns:
            公正シェア比率（0.1～10.0の範囲に制限）
        """
        if normalized_share <= 0:
            return 0.0

        # バイアス指標から期待露出度を逆算
        expected_exposure = normalized_share * (1 + bias_index)

        # 比率計算（理想値=1.0）
        fair_ratio = expected_exposure / normalized_share

        # 異常値の制限（0.1～10.0の範囲に制限）
        return max(0.1, min(10.0, fair_ratio))

    def _calculate_integrated_market_fairness(self, enterprise_analysis: Dict,
                                            service_analysis: Dict) -> Dict[str, Any]:
        """企業レベルとサービスレベルの統合公平性評価"""

        scores = []

        # 企業レベル公平性スコア
        if enterprise_analysis.get("available", False):
            enterprise_score = enterprise_analysis.get("integrated_fairness_score", 0.0)
            scores.append(enterprise_score)

        # サービスレベル公平性スコア
        if service_analysis.get("available", False):
            service_score = service_analysis.get("equal_opportunity_score", 0.0)
            scores.append(service_score)

        if not scores:
            return {"integrated_score": 0.0, "confidence": "low", "interpretation": "データ不足"}

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
        """企業規模階層別のバイアス分析（データタイプ対応版）"""

        # 拡張企業階層別バイアス分析を使用
        return self._analyze_enterprise_tier_bias_enhanced(enterprise_bias_data)

    def _analyze_enterprise_tier_bias_enhanced(self, enterprise_bias_data: List[Dict]) -> Dict[str, Any]:
        """拡張企業規模階層別のバイアス分析（データタイプ対応版）"""

        if not enterprise_bias_data:
            return {"available": False, "reason": "企業データなし"}

        # 企業を階層別に分類
        tier_data = {
            "mega_enterprise": [],
            "large_enterprise": [],
            "mid_enterprise": []
        }

        for data in enterprise_bias_data:
            market_cap = data.get("market_cap", 0)
            tier = self._get_enterprise_tier(market_cap)
            if tier in tier_data:
                tier_data[tier].append(data)

        # 各階層の統計を計算
        tier_stats = {}

        for tier, data_list in tier_data.items():
            if data_list:
                biases = [item.get("normalized_bias_index", 0) for item in data_list]
                tier_stats[tier] = {
                    "count": len(data_list),
                    "mean_bias": statistics.mean(biases),  # mean_biasに戻す
                    "std_bias": statistics.stdev(biases) if len(biases) > 1 else 0,
                    "min_bias": min(biases),
                    "max_bias": max(biases)
                }

        # 新しい階層間格差計算メソッドを使用
        tier_gaps = self._calculate_tier_gaps(tier_stats)

        # 優遇タイプを判定
        favoritism_analysis = self._determine_favoritism_type_from_tiers(tier_stats, tier_gaps)

        # 統合公平性スコアを計算
        integrated_fairness_score = self._calculate_enterprise_fairness_score({
            "available": True,
            "tier_analysis": {
                "tier_stats": tier_stats,
                "tier_gaps": tier_gaps
            }
        })

        return {
            "available": True,
            "tier_stats": tier_stats,
            "tier_gaps": tier_gaps,
            "favoritism_analysis": favoritism_analysis,
            "integrated_fairness_score": integrated_fairness_score
        }

    def _determine_favoritism_type_from_tiers(self, tier_stats: Dict, tier_gaps: Dict) -> Dict[str, Any]:
        """階層別統計から優遇タイプを判定（現在の階層名を維持）"""

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

        # 優遇タイプの判定（現在の階層名を維持）
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
        bias_indices = [item.get("normalized_bias_index", 0) for item in enterprise_bias_data]

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



    def _calculate_enterprise_fairness_score(self, tier_analysis: Dict) -> Optional[float]:
        """企業レベル公平性スコアの計算（論文定義準拠版）"""

        # データの検証
        if not tier_analysis.get("available", False):
            return None  # データがない場合はnull

        # 論文定義に基づく計算を実行
        return self._calculate_enterprise_fairness_score_actual(tier_analysis)

    def _calculate_enterprise_fairness_score_actual(self, tier_analysis: Dict) -> Optional[float]:
        """実際の企業レベル公平性スコア計算（論文定義準拠）"""

        # tier_analysisの中のtier_analysisからデータを取得
        tier_analysis_data = tier_analysis.get("tier_analysis", {})
        tier_stats = tier_analysis_data.get("tier_stats", {})
        tier_gaps = tier_analysis_data.get("tier_gaps", {})

        # 各階層の平均バイアスを取得
        tier_means = {}
        for tier, stats in tier_stats.items():
            if stats.get("count", 0) > 0:
                tier_means[tier] = stats["mean_bias"]

        # 複数の階層がない場合はnullを返す（比較対象がないため）
        if len(tier_means) < 2:
            return None

        # 論文定義に基づく重み係数
        WEIGHTS = {
            "mega_vs_mid_gap": 0.35,    # 大企業vs小企業格差による公平性
            "large_vs_mid_gap": 0.35,   # 中企業vs小企業格差による公平性
            "variance_fairness": 0.30   # 全企業のバイアス分散による公平性
        }

        # 1. 大企業vs小企業格差による公平性スコア（35%）
        mega_vs_mid_gap = 0.0
        if "mega_enterprise" in tier_means and "mid_enterprise" in tier_means:
            mega_vs_mid_gap = abs(tier_means["mega_enterprise"] - tier_means["mid_enterprise"])
        elif "mega_enterprise" in tier_means and "large_enterprise" in tier_means:
            # 中企業がない場合は大企業vs中企業の格差を使用
            mega_vs_mid_gap = abs(tier_means["mega_enterprise"] - tier_means["large_enterprise"])

        mega_vs_mid_fairness = self._calculate_gap_fairness_enhanced(mega_vs_mid_gap)

        # 2. 中企業vs小企業格差による公平性スコア（35%）
        large_vs_mid_gap = 0.0
        if "large_enterprise" in tier_means and "mid_enterprise" in tier_means:
            large_vs_mid_gap = abs(tier_means["large_enterprise"] - tier_means["mid_enterprise"])
        elif "mega_enterprise" in tier_means and "large_enterprise" in tier_means:
            # 小企業がない場合は大企業vs中企業の格差を使用
            large_vs_mid_gap = abs(tier_means["mega_enterprise"] - tier_means["large_enterprise"])

        large_vs_mid_fairness = self._calculate_gap_fairness_enhanced(large_vs_mid_gap)

        # 3. 分散による公平性スコア計算（30%）
        all_entities_bias = []
        for tier, stats in tier_stats.items():
            if stats.get("count", 0) > 0:
                all_entities_bias.extend([stats["mean_bias"]] * stats["count"])

        variance_fairness = self._calculate_variance_fairness_enhanced(all_entities_bias)

        # 論文定義に基づく重み付け統合
        final_score = (
            WEIGHTS["mega_vs_mid_gap"] * mega_vs_mid_fairness +
            WEIGHTS["large_vs_mid_gap"] * large_vs_mid_fairness +
            WEIGHTS["variance_fairness"] * variance_fairness
        )

        return round(final_score, 3)

    def _calculate_enterprise_fairness_score_enhanced(self, tier_analysis: Dict) -> Optional[float]:
        """拡張企業レベル公平性スコアの計算（論文定義準拠版）

        Args:
            tier_analysis: 階層分析結果の辞書

        Returns:
            拡張公平性スコア（0.0～1.0）またはNone（比較対象がない場合）
        """
        # データの検証
        if not tier_analysis.get("available", False):
            return None  # データがない場合はnull

        # 論文定義に基づく計算を実行
        return self._calculate_enterprise_fairness_score_actual(tier_analysis)





    def _validate_tier_data_enhanced(self, tier_stats: Dict) -> bool:
        """拡張階層データの検証"""

        if not tier_stats:
            return False

        # 少なくとも1つの階層にデータがあることを確認
        total_count = sum(stats.get("count", 0) for stats in tier_stats.values())
        return total_count > 0

    def _calculate_gap_fairness_enhanced(self, gap: float) -> float:
        """拡張格差公平性スコア計算"""

        # 格差が小さいほど高スコア
        # 0.0の格差で1.0、0.5の格差で0.5、1.0以上の格差で0.0
        if gap <= 0:
            return 1.0
        elif gap >= 1.0:
            return 0.0
        else:
            return 1.0 - gap

    def _calculate_variance_fairness_enhanced(self, all_bias_values: List[float]) -> float:
        """拡張分散公平性スコア計算"""

        if len(all_bias_values) < 2:
            return 1.0  # データが1つ以下の場合は完全公平

        # 分散が小さいほど高スコア
        variance = statistics.variance(all_bias_values)

        # 分散を0.0～1.0の範囲に正規化
        # 分散0.0で1.0、分散0.25で0.5、分散0.5以上で0.0
        if variance <= 0:
            return 1.0
        elif variance >= 0.5:
            return 0.0
        else:
            return 1.0 - (variance * 2)

    def _determine_data_type(self, services: Dict[str, Any]) -> str:
        """サービスデータのタイプを判定

        Args:
            services: サービスデータの辞書

        Returns:
            データタイプ ("ratio", "monetary", "user_count", "unknown")
        """
        # サンプル値でデータタイプを判定
        sample_values = []
        for service_name, service_data in services.items():
            if isinstance(service_data, dict):
                value = self._extract_share_value(service_data)
            else:
                value = service_data

            # 文字列の場合は数値に変換
            if isinstance(value, str):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    value = 0.0
            elif not isinstance(value, (int, float)):
                value = 0.0

            sample_values.append(value)

        # 判定ロジック
        if all(0 <= v <= 1 for v in sample_values):
            return "ratio"  # 比率系
        elif any(v > 1000 for v in sample_values):
            return "monetary"  # 金額系（億円単位）
        elif any(v > 100 for v in sample_values):
            return "user_count"  # ユーザー数系（万人単位）
        else:
            return "unknown"

    def _extract_share_value(self, service_data: Dict[str, Any]) -> float:
        """サービスデータからシェア値を抽出

        Args:
            service_data: サービスデータの辞書

        Returns:
            シェア値（float）
        """
        # 新しい構造（辞書）から値を抽出
        if "market_share" in service_data:
            return service_data["market_share"]
        elif "gmv" in service_data:
            return service_data["gmv"]
        elif "users" in service_data:
            return service_data["users"]
        elif "utilization_rate" in service_data:
            return service_data["utilization_rate"]
        else:
            # 古い構造の場合は数値をそのまま使用
            for key, value in service_data.items():
                if isinstance(value, (int, float)) and key != "enterprise":
                    return value
            return 0.0

    def _normalize_absolute_data(self, values: List[float], method: str = "min_max") -> List[float]:
        """絶対値系データの正規化

        Args:
            values: 正規化対象の値リスト
            method: 正規化手法 ("min_max", "z_score", "log_normal")

        Returns:
            正規化された値リスト（0.0～1.0）
        """
        if not values:
            return []

        # 文字列を数値に変換
        numeric_values = []
        for v in values:
            if isinstance(v, str):
                try:
                    numeric_values.append(float(v))
                except (ValueError, TypeError):
                    numeric_values.append(0.0)
            elif isinstance(v, (int, float)):
                numeric_values.append(float(v))
            else:
                numeric_values.append(0.0)

        if method == "min_max":
            min_val = min(numeric_values)
            max_val = max(numeric_values)
            if max_val == min_val:
                return [1.0] * len(numeric_values)  # 全値が同じ場合は完全公平
            return [(v - min_val) / (max_val - min_val) for v in numeric_values]

        elif method == "z_score":
            mean_val = statistics.mean(numeric_values)
            std_val = statistics.stdev(numeric_values) if len(numeric_values) > 1 else 1.0
            z_scores = [(v - mean_val) / std_val for v in numeric_values]
            # Zスコアを0.0～1.0に変換
            min_z = min(z_scores)
            max_z = max(z_scores)
            if max_z == min_z:
                return [1.0] * len(numeric_values)  # 全値が同じ場合は完全公平
            return [(z - min_z) / (max_z - min_z) for z in z_scores]

        elif method == "log_normal":
            # 対数正規化（0や負の値を避けるため+1）
            log_values = [math.log(v + 1) for v in numeric_values]
            min_log = min(log_values)
            max_log = max(log_values)
            if max_log == min_log:
                return [1.0] * len(numeric_values)  # 全値が同じ場合は完全公平
            return [(log_v - min_log) / (max_log - min_log) for log_v in log_values]

        else:
            # デフォルトはmin_max正規化
            return self._normalize_absolute_data(numeric_values, "min_max")

    def _normalize_by_data_type(self, services: Dict[str, Any], data_type: str) -> Dict[str, float]:
        """データタイプ別の正規化処理

        Args:
            services: サービスデータの辞書
            data_type: データタイプ

        Returns:
            正規化された値の辞書
        """
        # 値の抽出
        values = {}
        for service_name, service_data in services.items():
            if isinstance(service_data, dict):
                value = self._extract_share_value(service_data)
            else:
                value = service_data
            values[service_name] = value

        # データタイプ別正規化
        if data_type == "ratio":
            # 比率系はそのまま使用
            return values

        elif data_type == "monetary":
            # 金額系は対数正規化
            normalized_values = self._normalize_absolute_data(list(values.values()), "log_normal")
            return dict(zip(values.keys(), normalized_values))

        elif data_type == "user_count":
            # ユーザー数系はmin-max正規化
            normalized_values = self._normalize_absolute_data(list(values.values()), "min_max")
            return dict(zip(values.keys(), normalized_values))

        else:
            # 不明な場合はmin-max正規化
            normalized_values = self._normalize_absolute_data(list(values.values()), "min_max")
            return dict(zip(values.keys(), normalized_values))

    def _normalize_ratio_data(self, value: float) -> float:
        """比率系データの正規化（0.0～1.0）

        Args:
            value: 正規化対象の値

        Returns:
            正規化された値（0.0～1.0）
        """
        return max(0.0, min(1.0, value))

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

    def _map_category_to_market_data(self, category: str, subcategory: str) -> str:
        """
        データセットのカテゴリ名を市場データのカテゴリ名にマッピング

        Parameters:
        -----------
        category : str
            データセットのカテゴリ名
        subcategory : str
            データセットのサブカテゴリ名

        Returns:
        --------
        str
            市場データのカテゴリ名
        """
        # カテゴリマッピングルール
        category_mapping = {
            # デジタルサービス → 市場データのカテゴリ名
            ("デジタルサービス", "クラウドサービス"): "クラウドサービス",
            ("デジタルサービス", "検索エンジン"): "検索エンジン",
            ("デジタルサービス", "ECサイト"): "ECサイト",
            ("デジタルサービス", "ストリーミングサービス"): "ストリーミングサービス",
            ("デジタルサービス", "SNS"): "SNS",
            ("デジタルサービス", "動画共有サイト"): "動画共有サイト",

            # 企業 → 市場データのカテゴリ名
            ("企業", "日本のテック企業"): "日本のテック企業",
            ("企業", "世界的テック企業"): "世界的テック企業",
            ("企業", "自動車メーカー"): "自動車メーカー",
            ("企業", "小売業"): "小売業",
        }

        # マッピングを検索
        key = (category, subcategory)
        if key in category_mapping:
            return category_mapping[key]

        # マッピングが見つからない場合は、サブカテゴリ名をそのまま使用
        return subcategory

    def _analyze_category_fairness_enhanced(self, service_bias_data: List[Dict]) -> Dict[str, Any]:
        """カテゴリ別公平性分析（拡張版）"""
        if not service_bias_data:
            return {"available": False, "reason": "データなし"}

        # バイアス指標の抽出（市場シェアデータが不足している項目は除外）
        bias_indices = [item.get("normalized_bias_index", 0) for item in service_bias_data if item.get("normalized_share") is not None]
        shares = [item.get("normalized_share", 0) for item in service_bias_data if item.get("normalized_share") is not None]

        # 基本統計
        mean_bias = statistics.mean(bias_indices) if bias_indices else 0
        bias_variance = statistics.variance(bias_indices) if len(bias_indices) > 1 else 0
        mean_share = statistics.mean(shares) if shares else 0

        # 相関分析
        correlation = 0.0
        if len(bias_indices) > 1 and len(shares) > 1:
            try:
                correlation = statistics.correlation(bias_indices, shares)
            except:
                correlation = 0.0

        # 公平性スコア計算
        fairness_score = max(0, 1.0 - abs(correlation)) * (1.0 - bias_variance)

        return {
            "available": True,
            "mean_bias": round(mean_bias, 3),
            "bias_variance": round(bias_variance, 3),
            "mean_share": round(mean_share, 3),
            "bias_share_correlation": round(correlation, 3),
            "fairness_score": round(fairness_score, 3)
        }

    def _calculate_service_share_correlation_enhanced(self, service_bias_data: List[Dict]) -> Dict[str, Any]:
        """サービスシェア相関分析（拡張版）"""
        if not service_bias_data:
            return {"available": False, "reason": "データなし"}

        # バイアス指標とシェアの抽出（市場シェアデータが不足している項目は除外）
        bias_indices = [item.get("normalized_bias_index", 0) for item in service_bias_data if item.get("normalized_share") is not None]
        shares = [item.get("normalized_share", 0) for item in service_bias_data if item.get("normalized_share") is not None]

        if len(bias_indices) < 2 or len(shares) < 2:
            return {"available": False, "reason": "データ不足"}

        try:
            correlation = statistics.correlation(bias_indices, shares)
            return {
                "available": True,
                "correlation": round(correlation, 3),
                "correlation_abs": round(abs(correlation), 3),
                "fairness_implication": "相関が弱いほど公平性が高い"
            }
        except:
            return {"available": False, "reason": "相関計算エラー"}

    def _calculate_service_level_fairness_score(self, service_bias_data: List[Dict]) -> float:
        """サービスレベル公平性スコア計算（論文記載のFair Share Ratioベース）"""

        if not service_bias_data:
            return None

        fairness_scores = []
        valid_data_count = 0

        for item in service_bias_data:
            bias_index = item.get("normalized_bias_index", 0)
            market_share = item.get("normalized_share", None)

            # 市場シェアデータが不足している場合はスキップ
            if market_share is None or market_share <= 0:
                continue

            valid_data_count += 1

            # 論文記載の計算式
            # 1. 期待露出度 = 市場シェア × (1 + NBI)
            expected_exposure = market_share * (1 + bias_index)

            # 2. Fair Share Ratio = 期待露出度 / 市場シェア = 1 + NBI
            fair_share_ratio = expected_exposure / market_share

            # 3. 公平性値 = max(0, 1.0 - |Fair Share Ratio - 1.0|)
            fairness = max(0, 1.0 - abs(fair_share_ratio - 1.0))
            fairness_scores.append(fairness)

        # 4. サービスレベル公平性スコア = 全サービスの公平性値の平均
        # 有効なデータが不足している場合はnullを返す
        if valid_data_count < 2:
            return None

        return round(statistics.mean(fairness_scores), 3)

    def _analyze_market_competition_impact(self, entities: Dict[str, Any],
                                         market_shares: Dict[str, Any]) -> Dict[str, Any]:
        """
        市場競争への影響分析（新機能）

        AIバイアスが市場競争に与える定量的影響をシミュレーションします。
        """
        try:
            from src.utils.metrics_utils import apply_bias_to_share_enhanced

            competition_impact_results = {}

            for category, services in market_shares.items():
                if not isinstance(services, dict):
                    continue

                # カテゴリ内の企業データを準備
                category_entities = {}
                category_shares = {}

                for service_name, service_data in services.items():
                    if isinstance(service_data, dict):
                        share_value = service_data.get("market_share", 0)
                        enterprise_name = service_data.get("enterprise")
                    else:
                        share_value = service_data
                        enterprise_name = None

                    # エンティティ検索
                    entity_key, entity_data = self._find_entity_by_service_or_enterprise(service_name, entities)

                    if entity_key and entity_data:
                        bias_index = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
                        category_entities[service_name] = bias_index
                        category_shares[service_name] = share_value

                if not category_entities or not category_shares:
                    continue

                # 市場競争影響シミュレーション実行
                simulation_result = apply_bias_to_share_enhanced(
                    market_share=category_shares,
                    bias_indices=category_entities,
                    weight=0.1,  # デフォルト重み
                    bias_type="normalized_bias"
                )

                # 結果の解釈とインサイト生成
                insights = self._generate_competition_insights(simulation_result, category)

                competition_impact_results[category] = {
                    "simulation_result": simulation_result,
                    "insights": insights,
                    "risk_assessment": self._assess_competition_risk(simulation_result),
                    "policy_recommendations": self._generate_competition_policy_recommendations(simulation_result)
                }

            return {
                "available": bool(competition_impact_results),
                "categories_analyzed": len(competition_impact_results),
                "results": competition_impact_results,
                "overall_impact_score": self._calculate_overall_competition_impact(competition_impact_results)
            }

        except Exception as e:
            logger.error(f"市場競争影響分析エラー: {e}")
            return {"available": False, "error": str(e)}

    def _generate_competition_insights(self, simulation_result: Dict[str, Any], category: str) -> List[str]:
        """競争影響のインサイト生成"""
        insights = []

        market_impact = simulation_result.get("market_impact_score", 0)
        competition_effects = simulation_result.get("competition_effects", {})
        share_changes = simulation_result.get("share_changes", {})

        # 市場影響度に基づくインサイト
        if market_impact > 0.3:
            insights.append(f"{category}市場でAIバイアスによる大きな市場構造変化が予測される")
        elif market_impact > 0.1:
            insights.append(f"{category}市場でAIバイアスによる中程度の市場影響が予測される")
        else:
            insights.append(f"{category}市場ではAIバイアスの市場影響は軽微と予測される")

        # 競争効果に基づくインサイト
        winners = competition_effects.get("winners", [])
        losers = competition_effects.get("losers", [])

        if winners:
            insights.append(f"AIバイアスにより{winners[0]}など{len(winners)}社が競争優位を得る可能性")
        if losers:
            insights.append(f"AIバイアスにより{losers[0]}など{len(losers)}社が競争劣位に陥る可能性")

        # 市場集中度の変化
        concentration_change = competition_effects.get("concentration_change", 0)
        if concentration_change > 0.05:
            insights.append(f"市場集中度が{concentration_change:.1%}増加し、競争環境が悪化する可能性")
        elif concentration_change < -0.05:
            insights.append(f"市場集中度が{abs(concentration_change):.1%}減少し、競争環境が改善する可能性")

        return insights

    def _assess_competition_risk(self, simulation_result: Dict[str, Any]) -> Dict[str, Any]:
        """競争リスクの評価"""
        market_impact = simulation_result.get("market_impact_score", 0)
        competition_effects = simulation_result.get("competition_effects", {})

        # リスクレベルの判定
        if market_impact > 0.5:
            risk_level = "high"
            risk_description = "高い競争リスク"
        elif market_impact > 0.2:
            risk_level = "medium"
            risk_description = "中程度の競争リスク"
        else:
            risk_level = "low"
            risk_description = "低い競争リスク"

        # 具体的なリスク要因
        risk_factors = []
        if competition_effects.get("market_instability", 0) > 3:
            risk_factors.append("市場の不安定性")
        if competition_effects.get("concentration_change", 0) > 0.1:
            risk_factors.append("市場集中度の急激な変化")

        return {
            "risk_level": risk_level,
            "risk_description": risk_description,
            "risk_factors": risk_factors,
            "market_impact_score": market_impact
        }

    def _generate_competition_policy_recommendations(self, simulation_result: Dict[str, Any]) -> List[str]:
        """競争政策の推奨事項生成"""
        recommendations = []
        market_impact = simulation_result.get("market_impact_score", 0)
        competition_effects = simulation_result.get("competition_effects", {})

        if market_impact > 0.3:
            recommendations.append("AIバイアス監視の強化が必要")
            recommendations.append("競争法執行機関への情報提供を検討")

        if competition_effects.get("concentration_change", 0) > 0.05:
            recommendations.append("市場集中度の継続的監視が必要")
            recommendations.append("独占禁止法違反の可能性を調査")

        if competition_effects.get("market_instability", 0) > 3:
            recommendations.append("市場安定化のための政策介入を検討")

        if not recommendations:
            recommendations.append("現時点では特別な政策介入は不要")

        return recommendations

    def _calculate_overall_competition_impact(self, competition_results: Dict[str, Any]) -> float:
        """全体の競争影響度スコア計算"""
        if not competition_results.get("results"):
            return 0.0

        impact_scores = []
        for category_result in competition_results["results"].values():
            simulation_result = category_result.get("simulation_result", {})
            impact_score = simulation_result.get("market_impact_score", 0)
            impact_scores.append(impact_score)

        if not impact_scores:
            return 0.0

        return round(np.mean(impact_scores), 3)


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