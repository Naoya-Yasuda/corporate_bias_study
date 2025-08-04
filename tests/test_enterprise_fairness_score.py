#!/usr/bin/env python3
"""
企業レベル公平性スコア修正のテストケース
"""

import unittest
import sys
import os
from typing import Dict, Any

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine


class TestEnterpriseFairnessScore(unittest.TestCase):
    """企業レベル公平性スコアのテストクラス"""

    def setUp(self):
        """テスト前の準備"""
        self.engine = BiasAnalysisEngine()

    def test_worldwide_tech_companies_fairness(self):
        """世界的テック企業の公平性スコアテスト"""
        # 実際のデータに基づくテストケース
        tier_analysis = {
            "available": True,
            "integrated_fairness_score": 0.5,  # 固定値（修正対象）
            "tier_stats": {
                "mega_enterprise": {
                    "count": 5,
                    "mean_bias": 1.0002,
                    "std_bias": 0.4417422325293338,
                    "min_bias": 0.486,
                    "max_bias": 1.653
                }
            },
            "tier_gaps": {
                "max_min_gap": 0.0,  # 格差なし
                "variance": 0.195
            }
        }

        # 修正後の関数をテスト
        result = self.engine._calculate_enterprise_fairness_score(tier_analysis)

        # 期待値: 格差なし（1.0） + 分散が小さい（0.195） → 約1.0
        self.assertGreater(result, 0.5)  # 0.5より大きいことを確認
        self.assertLessEqual(result, 1.0)  # 1.0以下であることを確認
        print(f"世界的テック企業の公平性スコア: {result}")

    def test_japanese_tech_companies_fairness(self):
        """日本のテック企業の公平性スコアテスト"""
        # 実際のデータに基づくテストケース
        tier_analysis = {
            "available": True,
            "integrated_fairness_score": 0.5,  # 固定値（修正対象）
            "tier_stats": {
                "large_enterprise": {
                    "count": 3,
                    "mean_bias": 1.3346666666666667,
                    "std_bias": 0.2019537900940048,
                    "min_bias": 1.17,
                    "max_bias": 1.56
                },
                "mid_enterprise": {
                    "count": 12,
                    "mean_bias": 0.9165,
                    "std_bias": 0.30323483249185545,
                    "min_bias": 0.39,
                    "max_bias": 1.196
                }
            },
            "tier_gaps": {
                "max_min_gap": 0.4181666666666667,  # 格差あり
                "variance": 0.08743168055555556
            }
        }

        # 修正後の関数をテスト
        result = self.engine._calculate_enterprise_fairness_score(tier_analysis)

        # 期待値: 格差あり（0.418） + 分散が小さい（0.087） → 約0.98
        self.assertGreater(result, 0.5)  # 0.5より大きいことを確認
        self.assertLessEqual(result, 1.0)  # 1.0以下であることを確認
        print(f"日本のテック企業の公平性スコア: {result}")

    def test_different_scores_between_groups(self):
        """異なる企業グループで異なるスコアが算出されることを確認"""
        # 世界的テック企業のデータ
        worldwide_tier_analysis = {
            "available": True,
            "integrated_fairness_score": 0.5,
            "tier_stats": {
                "mega_enterprise": {
                    "count": 5,
                    "mean_bias": 1.0002,
                    "std_bias": 0.4417422325293338,
                    "min_bias": 0.486,
                    "max_bias": 1.653
                }
            },
            "tier_gaps": {
                "max_min_gap": 0.0,
                "variance": 0.195
            }
        }

        # 日本のテック企業のデータ
        japanese_tier_analysis = {
            "available": True,
            "integrated_fairness_score": 0.5,
            "tier_stats": {
                "large_enterprise": {
                    "count": 3,
                    "mean_bias": 1.3346666666666667,
                    "std_bias": 0.2019537900940048,
                    "min_bias": 1.17,
                    "max_bias": 1.56
                },
                "mid_enterprise": {
                    "count": 12,
                    "mean_bias": 0.9165,
                    "std_bias": 0.30323483249185545,
                    "min_bias": 0.39,
                    "max_bias": 1.196
                }
            },
            "tier_gaps": {
                "max_min_gap": 0.4181666666666667,
                "variance": 0.08743168055555556
            }
        }

        worldwide_score = self.engine._calculate_enterprise_fairness_score(worldwide_tier_analysis)
        japanese_score = self.engine._calculate_enterprise_fairness_score(japanese_tier_analysis)

        # 異なるスコアが算出されることを確認
        self.assertNotEqual(worldwide_score, japanese_score)
        print(f"世界的テック企業: {worldwide_score}, 日本のテック企業: {japanese_score}")

    def test_already_calculated_score(self):
        """既に正しく計算されているスコアはそのまま返されることを確認"""
        tier_analysis = {
            "available": True,
            "integrated_fairness_score": 0.75,  # 既に正しく計算された値
            "tier_stats": {},
            "tier_gaps": {}
        }

        result = self.engine._calculate_enterprise_fairness_score(tier_analysis)
        self.assertEqual(result, 0.75)

    def test_no_data_available(self):
        """データがない場合は0.0を返すことを確認"""
        tier_analysis = {
            "available": False,
            "integrated_fairness_score": 0.5,
            "tier_stats": {},
            "tier_gaps": {}
        }

        result = self.engine._calculate_enterprise_fairness_score(tier_analysis)
        self.assertEqual(result, 0.0)

    def test_gap_fairness_calculation(self):
        """格差による公平性スコアの計算をテスト"""
        # 格差なしの場合
        gap_fairness_0 = self.engine._calculate_gap_fairness_enhanced(0.0)
        self.assertEqual(gap_fairness_0, 1.0)

        # 格差が小さい場合
        gap_fairness_small = self.engine._calculate_gap_fairness_enhanced(0.2)
        self.assertEqual(gap_fairness_small, 0.8)

        # 格差が大きい場合
        gap_fairness_large = self.engine._calculate_gap_fairness_enhanced(0.8)
        self.assertAlmostEqual(gap_fairness_large, 0.2, places=10)

        # 格差が1.0以上の場合
        gap_fairness_max = self.engine._calculate_gap_fairness_enhanced(1.5)
        self.assertEqual(gap_fairness_max, 0.0)

    def test_variance_fairness_calculation(self):
        """分散による公平性スコアの計算をテスト"""
        # 分散なしの場合
        variance_fairness_0 = self.engine._calculate_variance_fairness_enhanced([1.0, 1.0, 1.0])
        self.assertEqual(variance_fairness_0, 1.0)

        # 分散が小さい場合
        variance_fairness_small = self.engine._calculate_variance_fairness_enhanced([0.9, 1.0, 1.1])
        self.assertGreater(variance_fairness_small, 0.5)

        # 分散が大きい場合
        variance_fairness_large = self.engine._calculate_variance_fairness_enhanced([0.0, 1.0, 2.0])
        self.assertLess(variance_fairness_large, 0.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)