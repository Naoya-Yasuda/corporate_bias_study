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

        # ランキングバイアス分析（今回は基本実装のため簡略化）
        ranking_bias_analysis = self._analyze_ranking_bias(data.get('perplexity_rankings', {}))

        # 相対バイアス分析（今回は基本実装のため簡略化）
        relative_bias_analysis = self._analyze_relative_bias(sentiment_bias_analysis)

        # クロス分析インサイト
        cross_analysis_insights = self._generate_cross_analysis_insights(
            sentiment_bias_analysis, ranking_bias_analysis
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
        """ランキングバイアス分析（基本実装）"""
        # 今回は基本実装のため簡略化
        return {
            "placeholder": "ランキングバイアス分析は将来実装"
        }

    def _analyze_relative_bias(self, sentiment_analysis: Dict) -> Dict[str, Any]:
        """相対バイアス分析（基本実装）"""
        # 今回は基本実装のため簡略化
        return {
            "placeholder": "相対バイアス分析は将来実装"
        }

    def _generate_cross_analysis_insights(self, sentiment_analysis: Dict, ranking_analysis: Dict) -> Dict[str, Any]:
        """クロス分析インサイトを生成"""
        return {
            "sentiment_ranking_correlation": None,
            "consistent_leaders": [],
            "consistent_laggards": [],
            "volatility_concerns": ["実行回数不足により詳細分析は不可"],
            "overall_bias_pattern": "要追加データ"
        }

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