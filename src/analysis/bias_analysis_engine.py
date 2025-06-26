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
        """カテゴリレベルの分析を実行"""

        if not entities:
            return {}

        # バイアス分布の計算
        bias_indices = []
        entity_rankings = []

        for entity_name, entity_data in entities.items():
            bi = entity_data["basic_metrics"]["normalized_bias_index"]
            bias_indices.append(bi)
            entity_rankings.append({
                "entity": entity_name,
                "bias_rank": 0,  # 後で設定
                "bias_index": bi
            })

        # バイアス順位の設定
        entity_rankings.sort(key=lambda x: x["bias_index"], reverse=True)
        for i, item in enumerate(entity_rankings):
            item["bias_rank"] = i + 1

        # バイアス分布統計
        positive_bias_count = sum(1 for bi in bias_indices if bi > 0.1)
        negative_bias_count = sum(1 for bi in bias_indices if bi < -0.1)
        neutral_count = len(bias_indices) - positive_bias_count - negative_bias_count

        return {
            "bias_distribution": {
                "positive_bias_count": positive_bias_count,
                "negative_bias_count": negative_bias_count,
                "neutral_count": neutral_count,
                "bias_range": [min(bias_indices), max(bias_indices)] if bias_indices else [0, 0]
            },
            "relative_ranking": entity_rankings
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
                    "future_extensions": {
                        "masked_vs_unmasked_ready": False,
                        "note": "masked/unmaskedランキング比較は将来実装予定"
                    }
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
        """相対バイアス分析（基本実装）"""
        # 今回は基本実装のため簡略化
        return {
            "placeholder": "相対バイアス分析は将来実装"
        }

    def _generate_cross_analysis_insights(self, sentiment_analysis: Dict, ranking_analysis: Dict, citations_google_comparison: Dict) -> Dict[str, Any]:
        """クロス分析インサイトを生成"""

        insights = []

        # データ利用可能性の確認
        has_sentiment = bool(sentiment_analysis)
        has_ranking = bool(ranking_analysis)
        has_comparison = bool(citations_google_comparison) and "warning" not in citations_google_comparison

        # 1. 感情バイアス × ランキングバイアス の一貫性分析
        if has_sentiment and has_ranking:
            sentiment_ranking_consistency = self._analyze_sentiment_ranking_consistency(
                sentiment_analysis, ranking_analysis
            )
            insights.append("感情バイアスとランキングバイアスの一貫性を確認")
        else:
            sentiment_ranking_consistency = None
            insights.append("実行回数不足により感情-ランキング相関分析は不可")

        # 2. 検索結果 vs AI引用 の系統的バイアス
        if has_comparison:
            search_vs_ai_pattern = self._extract_search_vs_ai_pattern(citations_google_comparison)
            insights.extend(search_vs_ai_pattern.get("insights", []))
        else:
            search_vs_ai_pattern = None
            insights.append("Google検索とAI引用の比較データが不足")

        # 3. 全体的なバイアス傾向の統合評価
        overall_bias_pattern = self._determine_overall_bias_pattern(
            sentiment_analysis, ranking_analysis, citations_google_comparison
        )

        return {
            "sentiment_ranking_consistency": sentiment_ranking_consistency,
            "search_vs_ai_pattern": search_vs_ai_pattern,
            "overall_bias_pattern": overall_bias_pattern,
            "data_coverage": {
                "sentiment_analysis_available": has_sentiment,
                "ranking_analysis_available": has_ranking,
                "comparison_analysis_available": has_comparison
            },
            "cross_analysis_insights": insights,
            "recommended_actions": self._generate_cross_analysis_recommendations(
                has_sentiment, has_ranking, has_comparison
            )
        }

    def _analyze_sentiment_ranking_consistency(self, sentiment_analysis: Dict, ranking_analysis: Dict) -> Dict[str, Any]:
        """感情バイアスとランキングバイアスの一貫性分析"""

        consistent_entities = []
        inconsistent_entities = []

        # カテゴリごとに一貫性をチェック
        for category in sentiment_analysis.keys():
            if category not in ranking_analysis:
                continue

            for subcategory in sentiment_analysis[category].keys():
                if subcategory not in ranking_analysis[category]:
                    continue

                sentiment_entities = sentiment_analysis[category][subcategory].get("entities", {})
                ranking_summary = ranking_analysis[category][subcategory].get("category_summary", {})

                # 感情バイアスで上位の企業がランキングでも上位かチェック
                for entity, entity_data in sentiment_entities.items():
                    bias_index = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

                    # 一貫性判定のロジック（簡易版）
                    if abs(bias_index) > 0.5:  # 強いバイアスがある場合
                        if bias_index > 0:
                            consistent_entities.append(f"{entity} (正のバイアス)")
                        else:
                            inconsistent_entities.append(f"{entity} (負のバイアス)")

        consistency_ratio = len(consistent_entities) / max(len(consistent_entities) + len(inconsistent_entities), 1)

        return {
            "consistency_ratio": round(consistency_ratio, 3),
            "consistent_entities": consistent_entities[:5],  # 上位5件
            "inconsistent_entities": inconsistent_entities[:5],  # 上位5件
            "interpretation": "高い一貫性" if consistency_ratio > 0.7 else "中程度の一貫性" if consistency_ratio > 0.4 else "低い一貫性"
        }

    def _extract_search_vs_ai_pattern(self, citations_google_comparison: Dict) -> Dict[str, Any]:
        """検索結果 vs AI引用のパターン抽出"""

        total_categories = 0
        google_favored = 0
        citations_favored = 0
        neutral = 0
        insights = []

        for category, subcategories in citations_google_comparison.items():
            for subcategory, data in subcategories.items():
                total_categories += 1

                bias_detection = data.get("bias_detection", {})
                systemic_bias = bias_detection.get("systemic_bias_direction", "")

                if "Google優遇" in systemic_bias:
                    google_favored += 1
                elif "Citations優遇" in systemic_bias:
                    citations_favored += 1
                else:
                    neutral += 1

        if total_categories > 0:
            if google_favored > citations_favored:
                pattern = "Google検索優遇型"
                insights.append("Google検索結果の方が企業露出度が高い傾向")
            elif citations_favored > google_favored:
                pattern = "AI引用優遇型"
                insights.append("AIシステムが特定企業を積極的に引用する傾向")
            else:
                pattern = "中立・バランス型"
                insights.append("検索結果とAI引用での企業露出度に大きな偏りなし")
        else:
            pattern = "分析データ不足"
            insights.append("比較分析のためのデータが不十分")

        return {
            "overall_pattern": pattern,
            "distribution": {
                "google_favored_categories": google_favored,
                "citations_favored_categories": citations_favored,
                "neutral_categories": neutral,
                "total_categories": total_categories
            },
            "insights": insights
        }

    def _determine_overall_bias_pattern(self, sentiment_analysis: Dict, ranking_analysis: Dict, citations_google_comparison: Dict) -> Dict[str, Any]:
        """全体的なバイアス傾向の統合判定"""

        patterns = []
        confidence_level = "低"

        # 感情バイアスのパターン
        if sentiment_analysis:
            sentiment_pattern = self._extract_sentiment_pattern(sentiment_analysis)
            patterns.append(f"感情面: {sentiment_pattern}")

        # ランキングバイアスのパターン
        if ranking_analysis:
            ranking_pattern = self._extract_ranking_pattern(ranking_analysis)
            patterns.append(f"ランキング面: {ranking_pattern}")

        # 検索 vs AI のパターン
        if citations_google_comparison and "warning" not in citations_google_comparison:
            search_ai_pattern = self._extract_search_vs_ai_pattern(citations_google_comparison)
            patterns.append(f"情報源選択面: {search_ai_pattern['overall_pattern']}")
            confidence_level = "中"

        # 統合判定
        if len(patterns) >= 2:
            confidence_level = "中"
        if len(patterns) >= 3:
            confidence_level = "高"

        return {
            "integrated_patterns": patterns,
            "confidence_level": confidence_level,
            "summary": " / ".join(patterns) if patterns else "分析データ不足により判定不可",
            "bias_complexity": "単純" if len(set(patterns)) <= 1 else "複合的"
        }

    def _extract_sentiment_pattern(self, sentiment_analysis: Dict) -> str:
        """感情バイアスの主要パターンを抽出"""

        positive_bias_count = 0
        negative_bias_count = 0
        total_entities = 0

        for category, subcategories in sentiment_analysis.items():
            for subcategory, data in subcategories.items():
                entities = data.get("entities", {})
                for entity, entity_data in entities.items():
                    total_entities += 1
                    bias_index = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

                    if bias_index > 0.3:
                        positive_bias_count += 1
                    elif bias_index < -0.3:
                        negative_bias_count += 1

        if total_entities == 0:
            return "データ不足"

        positive_ratio = positive_bias_count / total_entities
        negative_ratio = negative_bias_count / total_entities

        if positive_ratio > 0.6:
            return "全体的な正のバイアス傾向"
        elif negative_ratio > 0.6:
            return "全体的な負のバイアス傾向"
        elif positive_ratio > negative_ratio:
            return "軽微な正のバイアス傾向"
        elif negative_ratio > positive_ratio:
            return "軽微な負のバイアス傾向"
        else:
            return "中立的"

    def _extract_ranking_pattern(self, ranking_analysis: Dict) -> str:
        """ランキングバイアスの主要パターンを抽出"""

        high_stability_count = 0
        total_categories = 0

        for category, subcategories in ranking_analysis.items():
            for subcategory, data in subcategories.items():
                total_categories += 1
                stability_score = data.get("category_summary", {}).get("stability_score", 0)

                if stability_score > 0.8:
                    high_stability_count += 1

        if total_categories == 0:
            return "データ不足"

        stability_ratio = high_stability_count / total_categories

        if stability_ratio > 0.8:
            return "高安定性（一貫したランキング）"
        elif stability_ratio > 0.5:
            return "中程度安定性"
        else:
            return "低安定性（ランキング変動大）"

    def _generate_cross_analysis_recommendations(self, has_sentiment: bool, has_ranking: bool, has_comparison: bool) -> List[str]:
        """クロス分析に基づく推奨アクション"""

        recommendations = []

        if not has_sentiment:
            recommendations.append("感情バイアス分析のためのデータ収集を実行してください")

        if not has_ranking:
            recommendations.append("ランキングバイアス分析のためのデータ収集を実行してください")

        if not has_comparison:
            recommendations.append("Google検索とAI引用の比較分析のためのデータ収集を実行してください")

        if has_sentiment and has_ranking and has_comparison:
            recommendations.extend([
                "全分析データが揃っているため、詳細な相対バイアス分析の実装を推奨",
                "統計的有意性向上のため、実行回数の増加（最低5回）を推奨",
                "時系列分析による傾向変化の追跡を推奨"
            ])

        return recommendations

    def _generate_analysis_limitations(self, execution_count: int) -> Dict[str, Any]:
        """分析制限事項を生成"""
        min_statistical = self.config["minimum_execution_counts"]["sign_test_p_value"]

        limitations = {
            "execution_count_warning": f"実行回数が{execution_count}回のため、統計的検定は実行不可" if execution_count < min_statistical else None,
            "reliability_note": "結果は参考程度として扱ってください" if execution_count < 5 else None,
            "statistical_power": "低（軽微なバイアス検出困難）" if execution_count < 10 else "中程度",
            "recommended_actions": []
        }

        # 推奨アクション
        if execution_count < 5:
            limitations["recommended_actions"].extend([
                "統計的有意性判定には最低5回の実行が必要",
                "基本的な傾向把握には3回以上の実行を推奨"
            ])
        if execution_count < 10:
            limitations["recommended_actions"].append("信頼性の高い分析には10回以上の実行を推奨")
        if execution_count < 20:
            limitations["recommended_actions"].append("政策判断には15-20回の実行を強く推奨")

        return limitations

    def _analyze_citations_google_comparison(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
        """Citations vs Google比較分析（完全実装）"""

        if not google_data or not citations_data:
            return {
                "warning": "Google検索データまたはCitationsデータが利用できません",
                "available_analyses": [],
                "google_data_available": bool(google_data),
                "citations_data_available": bool(citations_data)
            }

        results = {}

        for category, google_subcategories in google_data.items():
            if category not in citations_data:
                continue

            citations_subcategories = citations_data[category]
            category_results = {}

            for subcategory, google_subcategory_data in google_subcategories.items():
                if subcategory not in citations_subcategories:
                    continue

                citations_subcategory_data = citations_subcategories[subcategory]

                # Google検索結果からドメイン抽出
                google_domains = self._extract_google_domains(google_subcategory_data)

                # Citations結果からドメイン抽出
                citations_domains = self._extract_citations_domains(citations_subcategory_data)

                # ランキング比較メトリクス
                ranking_comparison = self._compute_ranking_comparison_metrics(
                    google_domains, citations_domains
                )

                # コンテンツ品質比較
                content_comparison = self._compute_content_quality_comparison(
                    google_subcategory_data, citations_subcategory_data
                )

                # 企業別露出度分析
                entity_exposure_analysis = self._analyze_entity_exposure_difference(
                    google_subcategory_data, citations_subcategory_data
                )

                # バイアス検出分析
                bias_detection = self._detect_search_vs_citations_bias(
                    google_domains, citations_domains, entity_exposure_analysis
                )

                subcategory_result = {
                    "comparison_summary": {
                        "google_domains_count": len(google_domains),
                        "citations_domains_count": len(citations_domains),
                        "common_domains_count": len(set(google_domains) & set(citations_domains)),
                        "overlap_ratio": len(set(google_domains) & set(citations_domains)) / max(len(set(google_domains + citations_domains)), 1)
                    },
                    "ranking_comparison": ranking_comparison,
                    "content_quality_comparison": content_comparison,
                    "entity_exposure_analysis": entity_exposure_analysis,
                    "bias_detection": bias_detection,
                    "insights": self._generate_comparison_insights(
                        ranking_comparison, content_comparison, bias_detection
                    )
                }

                category_results[subcategory] = subcategory_result

            if category_results:
                results[category] = category_results

        return results

    def _extract_google_domains(self, google_data: Dict) -> List[str]:
        """Google検索結果からドメインリストを抽出"""
        domains = []

        # entities配下のofficial_results/reputation_resultsから抽出
        entities = google_data.get('entities', {})
        for entity_name, entity_data in entities.items():
            # official_results
            for result in entity_data.get('official_results', []):
                domain = result.get('domain')
                if domain:
                    domains.append(domain)

            # reputation_results
            for result in entity_data.get('reputation_results', []):
                domain = result.get('domain')
                if domain:
                    domains.append(domain)

        return domains

    def _extract_citations_domains(self, citations_data: Dict) -> List[str]:
        """Citations結果からドメインリストを抽出"""
        domains = []

        # entities配下のofficial_results/reputation_resultsから抽出
        entities = citations_data.get('entities', {})
        for entity_name, entity_data in entities.items():
            # official_results
            for result in entity_data.get('official_results', []):
                domain = result.get('domain')
                if domain:
                    domains.append(domain)

            # reputation_results
            for result in entity_data.get('reputation_results', []):
                domain = result.get('domain')
                if domain:
                    domains.append(domain)

        return domains

    def _compute_ranking_comparison_metrics(self, google_domains: List[str], citations_domains: List[str]) -> Dict[str, Any]:
        """ランキング比較メトリクスの計算"""

        # 共通ドメインの抽出
        common_domains = list(set(google_domains) & set(citations_domains))
        google_unique = list(set(google_domains) - set(citations_domains))
        citations_unique = list(set(citations_domains) - set(google_domains))

        # 順位相関の計算（共通ドメインがある場合のみ）
        kendall_tau = None
        spearman_rho = None

        if len(common_domains) >= 2:
            try:
                from scipy.stats import kendalltau, spearmanr

                # 共通ドメインの順位を抽出
                google_ranks = []
                citations_ranks = []

                for domain in common_domains:
                    google_rank = google_domains.index(domain) if domain in google_domains else len(google_domains)
                    citations_rank = citations_domains.index(domain) if domain in citations_domains else len(citations_domains)
                    google_ranks.append(google_rank)
                    citations_ranks.append(citations_rank)

                # 統計計算
                kendall_tau, _ = kendalltau(google_ranks, citations_ranks)
                spearman_rho, _ = spearmanr(google_ranks, citations_ranks)

            except Exception as e:
                logger.warning(f"順位相関計算エラー: {e}")

        return {
            "common_domains": common_domains,
            "google_unique_domains": google_unique,
            "citations_unique_domains": citations_unique,
            "overlap_count": len(common_domains),
            "total_unique_domains": len(set(google_domains + citations_domains)),
            "overlap_ratio": len(common_domains) / max(len(set(google_domains + citations_domains)), 1),
            "kendall_tau": round(kendall_tau, 3) if kendall_tau is not None else None,
            "spearman_rho": round(spearman_rho, 3) if spearman_rho is not None else None,
            "ranking_divergence": self._calculate_ranking_divergence(google_domains, citations_domains)
        }

    def _calculate_ranking_divergence(self, google_domains: List[str], citations_domains: List[str]) -> Dict[str, Any]:
        """ランキング乖離度の計算"""

        if not google_domains or not citations_domains:
            return {"divergence_score": 1.0, "interpretation": "完全乖離（一方のデータなし）"}

        # 上位N件での比較（N=min(10, データ数)）
        n = min(10, len(google_domains), len(citations_domains))
        google_top_n = google_domains[:n]
        citations_top_n = citations_domains[:n]

        # Jaccard類似度
        jaccard_similarity = len(set(google_top_n) & set(citations_top_n)) / len(set(google_top_n) | set(citations_top_n))
        divergence_score = 1 - jaccard_similarity

        # 解釈
        if divergence_score < 0.2:
            interpretation = "非常に類似（乖離度低）"
        elif divergence_score < 0.4:
            interpretation = "やや類似（軽微な乖離）"
        elif divergence_score < 0.6:
            interpretation = "中程度の乖離"
        elif divergence_score < 0.8:
            interpretation = "大きな乖離"
        else:
            interpretation = "完全乖離（ほぼ異なる結果）"

        return {
            "divergence_score": round(divergence_score, 3),
            "jaccard_similarity": round(jaccard_similarity, 3),
            "interpretation": interpretation,
            "top_n_analyzed": n
        }

    def _compute_content_quality_comparison(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
        """コンテンツ品質の比較分析"""

        # Google検索の品質指標
        google_quality = self._analyze_google_content_quality(google_data)

        # Citations の品質指標
        citations_quality = self._analyze_citations_content_quality(citations_data)

        return {
            "google_quality": google_quality,
            "citations_quality": citations_quality,
            "quality_comparison": {
                "official_ratio_diff": google_quality.get("official_ratio", 0) - citations_quality.get("official_ratio", 0),
                "snippet_availability_diff": google_quality.get("snippet_ratio", 0) - citations_quality.get("snippet_ratio", 0),
                "overall_quality_diff": google_quality.get("overall_score", 0) - citations_quality.get("overall_score", 0)
            }
        }

    def _analyze_google_content_quality(self, google_data: Dict) -> Dict[str, Any]:
        """Google検索コンテンツの品質分析"""

        total_results = 0
        official_count = 0
        with_snippet_count = 0

        entities = google_data.get('entities', {})
        for entity_name, entity_data in entities.items():
            # official_results
            official_results = entity_data.get('official_results', [])
            total_results += len(official_results)
            official_count += len(official_results)  # official_resultsは全て公式
            with_snippet_count += sum(1 for r in official_results if r.get('snippet'))

            # reputation_results
            reputation_results = entity_data.get('reputation_results', [])
            total_results += len(reputation_results)
            with_snippet_count += sum(1 for r in reputation_results if r.get('snippet'))

        if total_results == 0:
            return {"official_ratio": 0, "snippet_ratio": 0, "overall_score": 0}

        official_ratio = official_count / total_results
        snippet_ratio = with_snippet_count / total_results
        overall_score = (official_ratio + snippet_ratio) / 2

        return {
            "total_results": total_results,
            "official_count": official_count,
            "official_ratio": round(official_ratio, 3),
            "snippet_ratio": round(snippet_ratio, 3),
            "overall_score": round(overall_score, 3)
        }

    def _analyze_citations_content_quality(self, citations_data: Dict) -> Dict[str, Any]:
        """Citations コンテンツの品質分析"""

        total_results = 0
        official_count = 0
        with_snippet_count = 0

        entities = citations_data.get('entities', {})
        for entity_name, entity_data in entities.items():
            # official_results
            official_results = entity_data.get('official_results', [])
            total_results += len(official_results)
            official_count += sum(1 for r in official_results if r.get('is_official', False))
            with_snippet_count += sum(1 for r in official_results if r.get('snippet'))

            # reputation_results
            reputation_results = entity_data.get('reputation_results', [])
            total_results += len(reputation_results)
            with_snippet_count += sum(1 for r in reputation_results if r.get('snippet'))

        if total_results == 0:
            return {"official_ratio": 0, "snippet_ratio": 0, "overall_score": 0}

        official_ratio = official_count / total_results
        snippet_ratio = with_snippet_count / total_results
        overall_score = (official_ratio + snippet_ratio) / 2

        return {
            "total_results": total_results,
            "official_count": official_count,
            "official_ratio": round(official_ratio, 3),
            "snippet_ratio": round(snippet_ratio, 3),
            "overall_score": round(overall_score, 3)
        }

    def _analyze_entity_exposure_difference(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
        """企業別露出度差分の分析"""

        entity_analysis = {}

        # 全企業リストの取得
        google_entities = set(google_data.get('entities', {}).keys())
        citations_entities = set(citations_data.get('entities', {}).keys())
        all_entities = google_entities | citations_entities

        for entity in all_entities:
            google_entity_data = google_data.get('entities', {}).get(entity, {})
            citations_entity_data = citations_data.get('entities', {}).get(entity, {})

            # 露出度計算
            google_exposure = len(google_entity_data.get('official_results', [])) + len(google_entity_data.get('reputation_results', []))
            citations_exposure = len(citations_entity_data.get('official_results', [])) + len(citations_entity_data.get('reputation_results', []))

            exposure_diff = citations_exposure - google_exposure

            entity_analysis[entity] = {
                "google_exposure": google_exposure,
                "citations_exposure": citations_exposure,
                "exposure_difference": exposure_diff,
                "relative_change": round(exposure_diff / max(google_exposure, 1), 3),
                "bias_direction": "正のバイアス" if exposure_diff > 0 else "負のバイアス" if exposure_diff < 0 else "中立"
            }

        return entity_analysis

    def _detect_search_vs_citations_bias(self, google_domains: List[str], citations_domains: List[str], entity_exposure: Dict) -> Dict[str, Any]:
        """検索結果 vs 引用間のバイアス検出"""

        # システミックバイアスの検出
        total_entities = len(entity_exposure)
        positive_bias_count = sum(1 for e in entity_exposure.values() if e["exposure_difference"] > 0)
        negative_bias_count = sum(1 for e in entity_exposure.values() if e["exposure_difference"] < 0)
        neutral_count = total_entities - positive_bias_count - negative_bias_count

        # バイアス強度の計算
        exposure_diffs = [e["exposure_difference"] for e in entity_exposure.values()]
        avg_bias = sum(exposure_diffs) / len(exposure_diffs) if exposure_diffs else 0
        bias_variance = sum((d - avg_bias) ** 2 for d in exposure_diffs) / len(exposure_diffs) if exposure_diffs else 0

        # バイアス分類
        if abs(avg_bias) < 0.5:
            systemic_bias = "中立的"
        elif avg_bias > 0:
            systemic_bias = "Citations優遇（AI引用が検索結果より多い）"
        else:
            systemic_bias = "Google優遇（検索結果がAI引用より多い）"

        return {
            "systemic_bias_direction": systemic_bias,
            "average_bias_score": round(avg_bias, 3),
            "bias_variance": round(bias_variance, 3),
            "entity_bias_distribution": {
                "positive_bias_entities": positive_bias_count,
                "negative_bias_entities": negative_bias_count,
                "neutral_entities": neutral_count,
                "total_entities": total_entities
            },
            "bias_consistency": "一貫性あり" if bias_variance < 1.0 else "一貫性なし（企業により大きく異なる）",
            "statistical_significance": self._test_bias_significance(exposure_diffs)
        }

    def _test_bias_significance(self, exposure_diffs: List[float]) -> Dict[str, Any]:
        """バイアスの統計的有意性検定"""

        if len(exposure_diffs) < 3:
            return {
                "test_performed": False,
                "reason": "サンプル数不足（最低3企業必要）",
                "p_value": None,
                "significant": False
            }

        try:
            from scipy.stats import ttest_1samp

            # 0との差の検定（バイアスがないという帰無仮説）
            t_stat, p_value = ttest_1samp(exposure_diffs, 0)

            return {
                "test_performed": True,
                "test_type": "one_sample_t_test",
                "t_statistic": round(t_stat, 3),
                "p_value": round(p_value, 4),
                "significant": p_value < 0.05,
                "interpretation": "統計的に有意なバイアス" if p_value < 0.05 else "統計的に有意でない"
            }

        except Exception as e:
            logger.warning(f"統計検定エラー: {e}")
            return {
                "test_performed": False,
                "reason": f"計算エラー: {e}",
                "p_value": None,
                "significant": False
            }

    def _generate_comparison_insights(self, ranking_comparison: Dict, content_comparison: Dict, bias_detection: Dict) -> List[str]:
        """比較分析のインサイト生成"""

        insights = []

        # ランキング類似性のインサイト
        overlap_ratio = ranking_comparison.get("overlap_ratio", 0)
        if overlap_ratio > 0.7:
            insights.append("Google検索とAI引用の結果が高度に一致しており、情報源の一貫性が高い")
        elif overlap_ratio > 0.4:
            insights.append("Google検索とAI引用で中程度の一致があるが、一部の情報源に違いがある")
        else:
            insights.append("Google検索とAI引用で大きな違いがあり、情報源の選択基準が異なる可能性")

        # バイアス方向のインサイト
        systemic_bias = bias_detection.get("systemic_bias_direction", "")
        if "Citations優遇" in systemic_bias:
            insights.append("AIシステムが検索結果よりも特定企業を多く引用する傾向がある")
        elif "Google優遇" in systemic_bias:
            insights.append("Google検索の方がAIシステムよりも企業露出度が高い傾向がある")
        else:
            insights.append("検索結果とAI引用での企業露出度に大きな偏りは見られない")

        # 統計的有意性のインサイト
        if bias_detection.get("statistical_significance", {}).get("significant", False):
            insights.append("検出されたバイアスは統計的に有意であり、偶然ではない可能性が高い")

        # コンテンツ品質のインサイト
        quality_diff = content_comparison.get("quality_comparison", {}).get("overall_quality_diff", 0)
        if abs(quality_diff) > 0.2:
            if quality_diff > 0:
                insights.append("Google検索の方がコンテンツ品質（公式性・詳細度）が高い")
            else:
                insights.append("AI引用の方がコンテンツ品質（公式性・詳細度）が高い")

        return insights


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