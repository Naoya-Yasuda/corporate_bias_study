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

from src.analysis.reliability_checker import ReliabilityChecker
from src.analysis.metrics_calculator import MetricsCalculator
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_utils import load_json
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BiasAnalysisEngine:
    """バイアス指標計算のメインエンジン（ローカル・S3両対応）"""

    def __init__(self, config_path: str = None, storage_mode: str = None):
        """
        Parameters:
        -----------
        config_path : str, optional
            分析設定ファイルのパス
        storage_mode : str, optional
            ストレージモード指定（指定なしの場合は環境変数STORAGE_MODEを使用、デフォルト: "auto"）
            - "local": ローカルのみ読み込み・保存
            - "s3": S3のみ読み込み・保存
            - "both": ローカル・S3両方（推奨）
            - "auto": 自動選択（S3優先、フォールバックでローカル）
        """
        self.config = self._load_config(config_path)

        # ストレージモードを設定（統一）
        self.storage_mode = self._get_storage_mode(storage_mode)

        self.reliability_checker = ReliabilityChecker()
        self.metrics_calculator = MetricsCalculator()

        # データローダーのセットアップ
        self.data_loader = HybridDataLoader(self.storage_mode)

        logger.info(f"BiasAnalysisEngine初期化: storage_mode={self.storage_mode}")

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

                    # unmasked_values の確認（企業ごとに存在）
                    has_unmasked_data = False
                    for key, value in subcategory_data.items():
                        # 企業データ（masked_*以外のキー）をチェック
                        if (not key.startswith('masked_') and
                            not key in ['timestamp'] and
                            isinstance(value, dict) and
                            'unmasked_values' in value):
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

        # ランキングバイアス分析（完全実装）
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
        """感情バイアス分析を実行"""
        results = {}

        for category, subcategories in sentiment_data.items():
            category_results = {}

            for subcategory, subcategory_data in subcategories.items():
                # 実行回数の確認
                masked_values = subcategory_data.get('masked_values', [])
                execution_count = len(masked_values)

                # 企業データの抽出
                entities = {}
                for key, value in subcategory_data.items():
                    # 企業データ（masked_*以外のキー）をチェック
                    if (not key.startswith('masked_') and
                        not key in ['timestamp'] and
                        isinstance(value, dict) and
                        'unmasked_values' in value):
                        entities[key] = value['unmasked_values']

                # カテゴリサマリー
                subcategory_result = {
                    "category_summary": {
                        "total_entities": len(entities),
                        "execution_count": execution_count,
                        "category_reliability": self.reliability_checker.get_reliability_level(execution_count)[0],
                        "category_stability_score": None  # 後で計算
                    },
                    "entities": {}
                }

                # 企業別分析
                for entity_name, entity_unmasked_values in entities.items():
                    entity_result = self._calculate_entity_bias_metrics(
                        masked_values, entity_unmasked_values, execution_count
                    )
                    subcategory_result["entities"][entity_name] = entity_result

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
        raw_delta = self.metrics_calculator.calculate_raw_delta(masked_values, unmasked_values)

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
        stability_metrics = self.metrics_calculator.calculate_stability_score(unmasked_values)

        # 重篤度スコアの計算
        bi = normalized_bias_index
        cliffs_delta = effect_size.get('cliffs_delta')
        p_value = statistical_significance.get('sign_test_p_value')
        stability_score = stability_metrics if isinstance(stability_metrics, (int, float)) else None
        severity_score = None
        if cliffs_delta is not None and p_value is not None and stability_score is not None:
            severity_score = self.metrics_calculator.calculate_severity_score(bi, cliffs_delta, p_value, stability_score)

        # 解釈
        interpretation = self._generate_interpretation(
            raw_delta, normalized_bias_index, effect_size.get('cliffs_delta'),
            statistical_significance.get('sign_test_p_value'), execution_count
        )

        return {
            "basic_metrics": {
                "raw_delta": round(raw_delta, 3),
                "normalized_bias_index": round(normalized_bias_index, 3),
                "delta_values": [round(d, 3) for d in delta_values],
                "execution_count": execution_count
            },
            "statistical_significance": statistical_significance,
            "effect_size": effect_size,
            "confidence_interval": confidence_interval,
            "stability_metrics": stability_metrics,
            "severity_score": severity_score,
            "interpretation": interpretation
        }

    def _calculate_statistical_significance(self, pairs: List[Tuple[float, float]],
                                          execution_count: int) -> Dict[str, Any]:
        """統計的有意性を計算"""
        min_required = self.config["minimum_execution_counts"]["sign_test_p_value"]

        if execution_count < min_required:
            return {
                "sign_test_p_value": None,
                "available": False,
                "reason": f"実行回数不足（最低{min_required}回必要）",
                "required_count": min_required,
                "significance_level": "判定不可"
            }

        # 符号検定実行
        p_value = self.metrics_calculator.calculate_statistical_significance(pairs)

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
                "cliffs_delta": None,
                "available": False,
                "reason": f"実行回数不足（最低{min_required}回必要）",
                "required_count": min_required,
                "effect_magnitude": "判定不可"
            }

        # Cliff's Delta計算
        cliffs_delta = self.metrics_calculator.calculate_cliffs_delta(masked_values, unmasked_values)

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
                "ci_lower": None,
                "ci_upper": None,
                "available": False,
                "reason": f"実行回数不足（最低{min_required}回必要）",
                "confidence_level": 95
            }

        # ブートストラップ信頼区間計算
        ci_lower, ci_upper = self.metrics_calculator.calculate_confidence_interval(delta_values)

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
            bi = entity_data["basic_metrics"]["normalized_bias_index"]
            bias_indices.append(bi)
            entity_rankings.append({
                "entity": entity_name,
                "bias_rank": 0,  # 後で設定
                "bias_index": bi
            })
            # 感情スコアリスト（unmasked_values）を取得
            unmasked = entity_data["basic_metrics"].get("unmasked_values")
            if unmasked is not None:
                sentiment_values[entity_name] = unmasked

        # バイアス順位の設定
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
            stability_metrics = self.metrics_calculator.calculate_category_stability(sentiment_values)

        return {
            "bias_distribution": {
                "positive_bias_count": positive_bias_count,
                "negative_bias_count": negative_bias_count,
                "neutral_count": neutral_count,
                "bias_range": [min(bias_indices), max(bias_indices)] if bias_indices else [0, 0]
            },
            "relative_ranking": entity_rankings,
            "stability_metrics": stability_metrics
        }

    def _analyze_ranking_bias(self, ranking_data: Dict) -> Dict[str, Any]:
        """ランキングバイアス分析（完全実装）"""

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

                # 実行回数の確認
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

                # --- ここからランキング変動指標の組み込み ---
                ranking_variation = None
                masked_ranking = subcategory_data.get('masked_ranking')
                unmasked_ranking = subcategory_data.get('unmasked_ranking')
                if masked_ranking and unmasked_ranking:
                    ranking_variation = self.metrics_calculator.calculate_ranking_variation(masked_ranking, unmasked_ranking)

                subcategory_result = {
                    "category_summary": {
                        "total_entities": len(ranking_summary.get('details', {})),
                        "execution_count": execution_count,
                        "ranking_reliability": self.reliability_checker.get_reliability_level(execution_count)[0],
                        "stability_score": stability_analysis.get('overall_stability', 0.0)
                    },
                    "stability_analysis": stability_analysis,
                    "quality_analysis": quality_analysis,
                    "category_level_analysis": category_level_analysis,
                }
                if ranking_variation:
                    subcategory_result["ranking_variation"] = ranking_variation

                subcategory_result["future_extensions"] = {
                    "masked_vs_unmasked_ready": bool(ranking_variation),
                    "note": "masked/unmaskedランキング比較はranking_variationで出力"
                }

                category_results[subcategory] = subcategory_result

            results[category] = category_results

        return results

    def _calculate_ranking_stability(self, ranking_summary: Dict, answer_list: List, execution_count: int) -> Dict[str, Any]:
        """ランキング安定性の計算"""

        if execution_count < 2:
            return {
                "overall_stability": 1.0,  # 1回のみなので完全に安定
                "available": False,
                "reason": "安定性分析には最低2回の実行が必要",
                "pairwise_correlations": [],
                "rank_variance": {}
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

        if not details:
            return {}

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
        """相対バイアス分析の完全実装

        企業間のバイアス格差、不平等度、企業規模による優遇パターンを分析

        Parameters:
        -----------
        sentiment_analysis : Dict
            感情バイアス分析結果

        Returns:
        --------
        Dict[str, Any]
            相対バイアス分析結果
        """
        try:
            # 市場データの読み込み
            market_data = self._load_market_data()

            relative_analysis_results = {}

            # カテゴリごとの相対バイアス分析
            for category, subcategories in sentiment_analysis.items():
                category_results = {}

                for subcategory, subcategory_data in subcategories.items():
                    entities = subcategory_data.get("entities", {})

                    if not entities:
                        continue

                    # 1. バイアス不平等指標の計算
                    bias_inequality = self._calculate_bias_inequality(entities)

                    # 2. 企業優遇度分析
                    enterprise_favoritism = self._analyze_enterprise_favoritism(
                        entities, market_data.get("market_caps", {})
                    )

                    # 3. 市場シェア相関分析
                    market_share_correlation = self._analyze_market_share_correlation(
                        entities, market_data.get("market_shares", {}), category
                    )

                    # 4. 相対ランキング変動
                    relative_ranking_analysis = self._analyze_relative_ranking_changes(entities)

                    # 5. 統合相対評価
                    integrated_relative_evaluation = self._generate_integrated_relative_evaluation(
                        bias_inequality, enterprise_favoritism, market_share_correlation
                    )

                    category_results[subcategory] = {
                        "bias_inequality": bias_inequality,
                        "enterprise_favoritism": enterprise_favoritism,
                        "market_share_correlation": market_share_correlation,
                        "relative_ranking_analysis": relative_ranking_analysis,
                        "integrated_evaluation": integrated_relative_evaluation
                    }

                relative_analysis_results[category] = category_results

            # 全体サマリーの生成
            overall_summary = self._generate_relative_bias_summary(relative_analysis_results)
            relative_analysis_results["overall_summary"] = overall_summary

            return relative_analysis_results

        except Exception as e:
            logger.error(f"相対バイアス分析でエラー: {e}")
            return {
                "error": f"相対バイアス分析の実行に失敗しました: {str(e)}",
                "status": "failed"
            }

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
        return self.metrics_calculator.calculate_bias_inequality(bias_indices)

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
        """市場シェアとバイアスの相関分析"""

        # カテゴリマッピング（柔軟な照合）
        category_mapping = {
            "クラウドサービス": "クラウドサービス",
            "検索": "検索エンジン",
            "EC": "ECサイト",
            "動画配信": "ストリーミングサービス",
            "SNS": "SNS",
            "動画共有": "動画共有サイト"
        }

        mapped_category = category_mapping.get(category, category)
        category_market_data = market_shares.get(mapped_category, {})

        if not category_market_data:
            return {
                "correlation_available": False,
                "reason": f"市場シェアデータなし（カテゴリ: {category}）"
            }

        # バイアスと市場シェアのペア作成
        bias_share_pairs = []
        for entity_name, entity_data in entities.items():
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

            # 企業名の柔軟なマッチング
            market_share = self._find_market_share(entity_name, category_market_data)

            if market_share is not None:
                bias_share_pairs.append({
                    "entity": entity_name,
                    "bias_index": bi,
                    "market_share": market_share
                })

        if len(bias_share_pairs) < 3:
            return {
                "correlation_available": False,
                "reason": "相関分析に十分なデータなし（最低3社必要）"
            }

        # 相関係数の計算
        bias_values = [pair["bias_index"] for pair in bias_share_pairs]
        share_values = [pair["market_share"] for pair in bias_share_pairs]

        correlation_result = self._calculate_correlation(bias_values, share_values)

        # 公平性指標の計算
        fairness_analysis = self._analyze_market_fairness(bias_share_pairs)

        return {
            "correlation_available": True,
            "entity_pairs": bias_share_pairs,
            "correlation_coefficient": correlation_result["correlation"],
            "correlation_interpretation": correlation_result["interpretation"],
            "statistical_significance": correlation_result["significance"],
            "fairness_analysis": fairness_analysis
        }

    def _find_market_share(self, entity_name: str, market_data: Dict[str, float]) -> Optional[float]:
        """企業名の柔軟なマッチングで市場シェアを検索"""

        # 完全一致
        if entity_name in market_data:
            return market_data[entity_name]

        # 部分一致（企業名に含まれる主要キーワード）
        entity_keywords = entity_name.lower().split()

        for market_entity, share in market_data.items():
            market_keywords = market_entity.lower().split()

            # キーワードの一致をチェック
            if any(keyword in market_entity.lower() for keyword in entity_keywords):
                return share
            if any(keyword in entity_name.lower() for keyword in market_keywords):
                return share

        # 特別なマッピング
        special_mapping = {
            "aws": "AWS",
            "google cloud": "Google Cloud",
            "azure": "Azure",
            "microsoft": "Azure"
        }

        entity_lower = entity_name.lower()
        for key, mapped in special_mapping.items():
            if key in entity_lower and mapped in market_data:
                return market_data[mapped]

        return None

    def _calculate_correlation(self, bias_values: List[float], share_values: List[float]) -> Dict[str, Any]:
        """相関係数の計算と解釈"""

        try:
            import numpy as np
            from scipy.stats import pearsonr

            correlation, p_value = pearsonr(bias_values, share_values)

            # 相関の解釈
            if abs(correlation) < 0.1:
                interpretation = "相関なし"
            elif abs(correlation) < 0.3:
                interpretation = "弱い相関"
            elif abs(correlation) < 0.5:
                interpretation = "中程度の相関"
            elif abs(correlation) < 0.7:
                interpretation = "強い相関"
            else:
                interpretation = "非常に強い相関"

            direction = "正の" if correlation > 0 else "負の"
            full_interpretation = f"{direction}{interpretation}"

            return {
                "correlation": round(correlation, 3),
                "interpretation": full_interpretation,
                "significance": {
                    "p_value": round(p_value, 4),
                    "significant": p_value < 0.05,
                    "interpretation": "統計的に有意" if p_value < 0.05 else "統計的に有意でない"
                }
            }

        except Exception as e:
            logger.warning(f"相関計算エラー: {e}")
            return {
                "correlation": 0,
                "interpretation": "計算エラー",
                "significance": {"p_value": None, "significant": False, "interpretation": "計算不可"}
            }

    def _analyze_market_fairness(self, bias_share_pairs: List[Dict]) -> Dict[str, Any]:
        """市場公平性分析（Equal Opportunity指標）"""

        # Equal Opportunity比率の計算
        # 理想的には、AIの露出度が市場シェアに比例すべき

        fairness_scores = []
        for pair in bias_share_pairs:
            bias_index = pair["bias_index"]
            market_share = pair["market_share"]

            # バイアス指標を露出度の代理変数として使用
            # 正のバイアス = 過度な露出、負のバイアス = 過少な露出
            expected_bias = 0  # 公平な場合のバイアス

            # 公平性スコア（1に近いほど公平）
            if market_share > 0:
                # 市場シェアが高い企業ほど、多少の正のバイアスは許容される
                expected_bias_range = market_share * 0.5  # 市場シェアに応じた許容範囲

                if abs(bias_index) <= expected_bias_range:
                    fairness_score = 1.0
                else:
                    excess_bias = abs(bias_index) - expected_bias_range
                    fairness_score = max(0, 1 - excess_bias)
            else:
                fairness_score = 1.0 if bias_index == 0 else 0.5

            fairness_scores.append(fairness_score)

        # 全体的な公平性指標
        overall_fairness = statistics.mean(fairness_scores)

        # 最も不公平な企業
        min_fairness_idx = fairness_scores.index(min(fairness_scores))
        most_unfair_entity = bias_share_pairs[min_fairness_idx]["entity"]

        return {
            "overall_fairness_score": round(overall_fairness, 3),
            "fairness_level": self._interpret_fairness_level(overall_fairness),
            "entity_fairness_scores": [
                {
                    "entity": pair["entity"],
                    "fairness_score": round(score, 3),
                    "bias_index": pair["bias_index"],
                    "market_share": pair["market_share"]
                }
                for pair, score in zip(bias_share_pairs, fairness_scores)
            ],
            "most_unfair_entity": most_unfair_entity,
            "fairness_distribution": {
                "high_fairness_count": sum(1 for s in fairness_scores if s >= 0.8),
                "medium_fairness_count": sum(1 for s in fairness_scores if 0.5 <= s < 0.8),
                "low_fairness_count": sum(1 for s in fairness_scores if s < 0.5)
            }
        }

    def _interpret_fairness_level(self, fairness_score: float) -> str:
        """公平性レベルの解釈"""
        if fairness_score >= 0.9:
            return "非常に公平"
        elif fairness_score >= 0.8:
            return "公平"
        elif fairness_score >= 0.6:
            return "概ね公平"
        elif fairness_score >= 0.4:
            return "やや不公平"
        else:
            return "不公平"

    def _analyze_relative_ranking_changes(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """相対ランキング変動分析"""

        # 企業をバイアス指標でソート
        entity_rankings = []
        for entity_name, entity_data in entities.items():
            bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
            entity_rankings.append({
                "entity": entity_name,
                "bias_index": bi
            })

        # バイアス指標による順位付け
        entity_rankings.sort(key=lambda x: x["bias_index"], reverse=True)

        # 順位の設定
        for i, item in enumerate(entity_rankings):
            item["bias_rank"] = i + 1

        # ランキング集中度の分析
        ranking_concentration = self._analyze_ranking_concentration(entity_rankings)

        # 上位・下位の特徴分析
        tier_analysis = self._analyze_ranking_tiers(entity_rankings)

        return {
            "entity_rankings": entity_rankings,
            "ranking_concentration": ranking_concentration,
            "tier_analysis": tier_analysis,
            "ranking_stability": self._calculate_ranking_stability_metrics(entities)
        }

    def _analyze_ranking_concentration(self, rankings: List[Dict]) -> Dict[str, Any]:
        """ランキング集中度の分析"""

        bias_values = [item["bias_index"] for item in rankings]

        if not bias_values:
            return {"concentration_score": 0, "interpretation": "データなし"}

        # 上位企業への集中度
        if len(bias_values) >= 3:
            top3_sum = sum(bias_values[:3])
            total_sum = sum([abs(v) for v in bias_values])

            concentration_ratio = top3_sum / total_sum if total_sum > 0 else 0
        else:
            concentration_ratio = 1.0

        # 集中度の解釈
        if concentration_ratio > 0.8:
            interpretation = "非常に集中（少数企業への強い優遇）"
        elif concentration_ratio > 0.6:
            interpretation = "高い集中（上位企業への明確な優遇）"
        elif concentration_ratio > 0.4:
            interpretation = "中程度の集中"
        else:
            interpretation = "分散型（企業間格差小）"

        return {
            "concentration_ratio": round(concentration_ratio, 3),
            "top3_entities": [item["entity"] for item in rankings[:3]],
            "interpretation": interpretation
        }

    def _analyze_ranking_tiers(self, rankings: List[Dict]) -> Dict[str, Any]:
        """ランキング階層分析"""

        if not rankings:
            return {}

        # バイアス指標による階層分類
        tier1 = [item for item in rankings if item["bias_index"] > 0.5]  # 強い正のバイアス
        tier2 = [item for item in rankings if 0 <= item["bias_index"] <= 0.5]  # 軽微な正のバイアス
        tier3 = [item for item in rankings if -0.5 <= item["bias_index"] < 0]  # 軽微な負のバイアス
        tier4 = [item for item in rankings if item["bias_index"] < -0.5]  # 強い負のバイアス

        return {
            "tier1_strong_positive": {
                "entities": [item["entity"] for item in tier1],
                "count": len(tier1),
                "avg_bias": round(statistics.mean([item["bias_index"] for item in tier1]), 3) if tier1 else 0
            },
            "tier2_mild_positive": {
                "entities": [item["entity"] for item in tier2],
                "count": len(tier2),
                "avg_bias": round(statistics.mean([item["bias_index"] for item in tier2]), 3) if tier2 else 0
            },
            "tier3_mild_negative": {
                "entities": [item["entity"] for item in tier3],
                "count": len(tier3),
                "avg_bias": round(statistics.mean([item["bias_index"] for item in tier3]), 3) if tier3 else 0
            },
            "tier4_strong_negative": {
                "entities": [item["entity"] for item in tier4],
                "count": len(tier4),
                "avg_bias": round(statistics.mean([item["bias_index"] for item in tier4]), 3) if tier4 else 0
            }
        }

    def _calculate_ranking_stability_metrics(self, entities: Dict[str, Any]) -> Dict[str, Any]:
        """ランキング安定性指標の計算"""

        # 各企業の安定性スコアを集計
        stability_scores = []
        for entity_name, entity_data in entities.items():
            stability_score = entity_data.get("stability_score", 0)
            stability_scores.append(stability_score)

        if not stability_scores:
            return {"overall_stability": 0, "interpretation": "データなし"}

        overall_stability = statistics.mean(stability_scores)
        min_stability = min(stability_scores)
        max_stability = max(stability_scores)

        # 安定性の解釈
        if overall_stability >= 0.9:
            interpretation = "非常に安定"
        elif overall_stability >= 0.8:
            interpretation = "安定"
        elif overall_stability >= 0.7:
            interpretation = "やや安定"
        else:
            interpretation = "不安定"

        return {
            "overall_stability": round(overall_stability, 3),
            "min_stability": round(min_stability, 3),
            "max_stability": round(max_stability, 3),
            "stability_variance": round(statistics.variance(stability_scores), 3) if len(stability_scores) > 1 else 0,
            "interpretation": interpretation
        }

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


def main():
    """メイン実行関数（テスト用）"""
    engine = BiasAnalysisEngine()

    # テスト実行
    try:
        results = engine.analyze_integrated_dataset("20250624")
        print("バイアス分析が正常に完了しました")
        print(f"分析結果: {len(results)} つの指標を計算")
    except Exception as e:
        print(f"エラーが発生しました: {e}")


if __name__ == "__main__":
    main()