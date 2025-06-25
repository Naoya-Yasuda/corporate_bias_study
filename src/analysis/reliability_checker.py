#!/usr/bin/env python
# coding: utf-8

"""
信頼性チェッカー - 実行回数に基づく分析信頼性の評価

本モジュールは、データ収集の実行回数に基づいて
統計分析の信頼性レベルを判定し、利用可能な指標を
決定する機能を提供します。

Usage:
    checker = ReliabilityChecker()
    level = checker.get_reliability_level(execution_count)
"""

import logging
from typing import Dict, Tuple, List

# ログ設定
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


def main():
    """テスト実行用メイン関数"""
    checker = ReliabilityChecker()

    # テストケース
    test_counts = [1, 3, 5, 10, 15, 25]

    for count in test_counts:
        print(f"\n実行回数: {count}")
        level, confidence = checker.get_reliability_level(count)
        print(f"信頼性レベル: {level} ({confidence})")

        availability = checker.check_metric_availability(count)
        available_metrics = [k for k, v in availability.items() if v["available"]]
        print(f"利用可能指標: {available_metrics}")

        recommendations = checker.get_analysis_recommendations(count)
        print(f"推奨事項: {recommendations['usage_recommendations']}")


if __name__ == "__main__":
    main()