#!/usr/bin/env python3
"""
企業中立性スコア修正のテストケース
"""

import unittest
import sys
import os
from typing import Dict, Any

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine


class TestEnterpriseNeutralityScoreFix(unittest.TestCase):
    """企業中立性スコア修正のテストクラス"""

    def setUp(self):
        """テスト前の準備"""
        self.engine = BiasAnalysisEngine()

    def test_enterprise_neutrality_no_comparison(self):
        """比較対象が存在しない場合のテスト"""
        tier_gaps = {}  # 空の格差データ

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNone(result)  # Noneが返されることを確認
        print(f"比較対象なしの場合: {result}")

    def test_enterprise_neutrality_single_tier(self):
        """単一階層のみの場合のテスト"""
        tier_gaps = {
            "max_min_gap": 0.0  # 格差なし
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNone(result)  # 比較対象がないためNone
        print(f"単一階層のみの場合: {result}")

    def test_enterprise_neutrality_multiple_tiers(self):
        """複数階層が存在する場合のテスト"""
        tier_gaps = {
            "large_vs_mid_gap": 0.418,
            "mega_vs_mid_gap": 0.583
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNotNone(result)  # スコアが算出される
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)
        print(f"複数階層が存在する場合: {result}")

    def test_enterprise_neutrality_zero_gaps(self):
        """全ての格差が0の場合のテスト"""
        tier_gaps = {
            "large_vs_mid_gap": 0.0,
            "mega_vs_mid_gap": 0.0
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNone(result)  # 有効な格差値がないためNone
        print(f"全ての格差が0の場合: {result}")

    def test_enterprise_neutrality_none_values(self):
        """None値が含まれる場合のテスト"""
        tier_gaps = {
            "large_vs_mid_gap": None,
            "mega_vs_mid_gap": 0.583
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNotNone(result)  # 有効な値があるためスコアが算出される
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)
        print(f"None値が含まれる場合: {result}")

    def test_enterprise_neutrality_all_none_values(self):
        """全ての値がNoneの場合のテスト"""
        tier_gaps = {
            "large_vs_mid_gap": None,
            "mega_vs_mid_gap": None
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNone(result)  # 有効な値がないためNone
        print(f"全ての値がNoneの場合: {result}")

    def test_enterprise_neutrality_worldwide_tech_companies(self):
        """世界的テック企業の実際のデータでのテスト"""
        # 世界的テック企業の実際のデータ（全5社がmega_enterpriseのみ）
        tier_gaps = {
            "max_min_gap": 0.0  # 格差なし（単一階層のため）
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNone(result)  # 比較対象がないためNone
        print(f"世界的テック企業の場合: {result}")

    def test_enterprise_neutrality_japanese_tech_companies(self):
        """日本のテック企業の実際のデータでのテスト"""
        # 日本のテック企業の実際のデータ（large_enterpriseとmid_enterpriseが存在）
        tier_gaps = {
            "large_vs_mid_gap": 0.4181666666666667,
            "mega_vs_mid_gap": 0.583
        }

        result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

        self.assertIsNotNone(result)  # スコアが算出される
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)
        print(f"日本のテック企業の場合: {result}")

    def test_enterprise_neutrality_edge_cases(self):
        """エッジケースのテスト"""
        # 最大格差の場合
        tier_gaps_max = {
            "large_vs_mid_gap": 1.0,
            "mega_vs_mid_gap": 1.0
        }

        result_max = self.engine._calculate_enterprise_neutrality_score(tier_gaps_max)
        self.assertEqual(result_max, 0.0)  # 最大格差の場合、スコアは0.0
        print(f"最大格差の場合: {result_max}")

        # 最小格差の場合
        tier_gaps_min = {
            "large_vs_mid_gap": 0.001,
            "mega_vs_mid_gap": 0.001
        }

        result_min = self.engine._calculate_enterprise_neutrality_score(tier_gaps_min)
        self.assertEqual(result_min, 0.999)  # 最小格差の場合、スコアは0.999（3桁に調整）
        print(f"最小格差の場合: {result_min}")

    def test_calculate_tier_gaps(self):
        """階層間格差計算のテスト"""
        # 複数階層の場合
        tier_stats = {
            "mega_enterprise": {
                "mean_bias": 1.069,
                "count": 5
            },
            "large_enterprise": {
                "mean_bias": 0.651,
                "count": 3
            },
            "mid_enterprise": {
                "mean_bias": 0.486,
                "count": 12
            }
        }

        result = self.engine._calculate_tier_gaps(tier_stats)

        # 期待される結果: 全階層間の組み合わせ（短縮形）
        expected_keys = [
            "mega_vs_large_gap",
            "mega_vs_mid_gap",
            "large_vs_mid_gap"
        ]

        for key in expected_keys:
            self.assertIn(key, result)
            self.assertGreaterEqual(result[key], 0.0)

        print(f"階層間格差計算結果: {result}")

    def test_calculate_tier_gaps_single_tier(self):
        """単一階層の場合の階層間格差計算テスト"""
        # 単一階層の場合
        tier_stats = {
            "mega_enterprise": {
                "mean_bias": 1.069,
                "count": 5
            }
        }

        result = self.engine._calculate_tier_gaps(tier_stats)

        # 単一階層の場合は空の辞書が返される
        self.assertEqual(result, {})
        print(f"単一階層の場合: {result}")

    def test_calculate_tier_gaps_empty(self):
        """空の階層統計の場合のテスト"""
        # 空の階層統計
        tier_stats = {}

        result = self.engine._calculate_tier_gaps(tier_stats)

        # 空の場合は空の辞書が返される
        self.assertEqual(result, {})
        print(f"空の階層統計の場合: {result}")


if __name__ == '__main__':
    unittest.main()