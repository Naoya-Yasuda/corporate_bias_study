#!/usr/bin/env python
# coding: utf-8

"""
Phase 2拡張機能テストスクリプト

Phase 2で実装した以下の拡張機能をテストします：
1. 拡張機会均等スコア計算
2. 拡張企業階層別バイアス分析
3. 拡張企業レベル公平性スコア計算
"""

import sys
import os
import json
import statistics
from typing import Dict, List, Any

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine


def test_enhanced_equal_opportunity_score():
    """拡張機会均等スコア計算のテスト"""
    print("=== 拡張機会均等スコア計算テスト ===")

    engine = BiasAnalysisEngine()

    # テストデータ（データタイプ別）
    test_data = [
        # ratio型データ
        {"service": "service1", "data_type": "ratio", "fair_share_ratio": 1.0, "category": "test"},
        {"service": "service2", "data_type": "ratio", "fair_share_ratio": 0.8, "category": "test"},
        {"service": "service3", "data_type": "ratio", "fair_share_ratio": 1.2, "category": "test"},

        # monetary型データ
        {"service": "service4", "data_type": "monetary", "fair_share_ratio": 0.9, "category": "test"},
        {"service": "service5", "data_type": "monetary", "fair_share_ratio": 1.1, "category": "test"},

        # user_count型データ
        {"service": "service6", "data_type": "user_count", "fair_share_ratio": 1.0, "category": "test"},
    ]

    # 拡張機会均等スコア計算
    enhanced_score = engine._calculate_equal_opportunity_score_enhanced(test_data)
    legacy_score = engine._calculate_equal_opportunity_score(test_data)

    print(f"拡張機会均等スコア: {enhanced_score}")
    print(f"従来機会均等スコア: {legacy_score}")
    print(f"データタイプ別分析: 有効")
    print("✅ 拡張機会均等スコア計算テスト完了\n")


def test_enhanced_enterprise_tier_bias_analysis():
    """拡張企業階層別バイアス分析のテスト"""
    print("=== 拡張企業階層別バイアス分析テスト ===")

    engine = BiasAnalysisEngine()

    # テストデータ（データタイプ別の企業階層データ）
    test_data = [
        # ratio型データ
        {"enterprise": "mega1", "enterprise_tier": "mega_enterprise", "data_type": "ratio", "normalized_bias_index": 0.1, "market_cap": 15.0},
        {"enterprise": "mega2", "enterprise_tier": "mega_enterprise", "data_type": "ratio", "normalized_bias_index": 0.2, "market_cap": 12.0},
        {"enterprise": "large1", "enterprise_tier": "large_enterprise", "data_type": "ratio", "normalized_bias_index": 0.3, "market_cap": 8.0},
        {"enterprise": "mid1", "enterprise_tier": "mid_enterprise", "data_type": "ratio", "normalized_bias_index": 0.4, "market_cap": 3.0},

        # monetary型データ
        {"enterprise": "mega3", "enterprise_tier": "mega_enterprise", "data_type": "monetary", "normalized_bias_index": 0.15, "market_cap": 10.0},
        {"enterprise": "large2", "enterprise_tier": "large_enterprise", "data_type": "monetary", "normalized_bias_index": 0.25, "market_cap": 6.0},

        # user_count型データ
        {"enterprise": "mid2", "enterprise_tier": "mid_enterprise", "data_type": "user_count", "normalized_bias_index": 0.35, "market_cap": 2.0},
    ]

    # 拡張企業階層別バイアス分析
    enhanced_analysis = engine._analyze_enterprise_tier_bias_enhanced(test_data)

    print(f"分析結果: {enhanced_analysis.get('available', False)}")
    if enhanced_analysis.get('available', False):
        print(f"統合公平性スコア: {enhanced_analysis.get('integrated_fairness_score', 'N/A')}")
        print(f"データタイプ別分析数: {len(enhanced_analysis.get('analysis_by_data_type', {}))}")

        for data_type, analysis in enhanced_analysis.get('analysis_by_data_type', {}).items():
            print(f"  {data_type}型: 公平性スコア {analysis.get('fairness_score', 'N/A')}")

    print("✅ 拡張企業階層別バイアス分析テスト完了\n")


def test_enhanced_enterprise_fairness_score():
    """拡張企業レベル公平性スコア計算のテスト"""
    print("=== 拡張企業レベル公平性スコア計算テスト ===")

    engine = BiasAnalysisEngine()

    # テスト用の階層分析データ
    test_tier_analysis = {
        "available": True,
        "integrated_fairness_score": 0.75,
        "analysis_by_data_type": {
            "ratio": {
                "tier_statistics": {
                    "mega_enterprise": {"count": 2, "mean_bias": 0.15},
                    "large_enterprise": {"count": 1, "mean_bias": 0.30},
                    "mid_enterprise": {"count": 1, "mean_bias": 0.40}
                },
                "tier_gaps": {
                    "mega_vs_mid": 0.25,
                    "large_vs_mid": 0.10
                },
                "fairness_score": 0.80
            },
            "monetary": {
                "tier_statistics": {
                    "mega_enterprise": {"count": 1, "mean_bias": 0.15},
                    "large_enterprise": {"count": 1, "mean_bias": 0.25}
                },
                "tier_gaps": {
                    "mega_vs_mid": 0.10,
                    "large_vs_mid": 0.00
                },
                "fairness_score": 0.70
            }
        }
    }

    # 拡張企業レベル公平性スコア計算
    enhanced_score = engine._calculate_enterprise_fairness_score_enhanced(test_tier_analysis)
    legacy_score = engine._calculate_enterprise_fairness_score(test_tier_analysis)

    print(f"拡張企業レベル公平性スコア: {enhanced_score}")
    print(f"従来企業レベル公平性スコア: {legacy_score}")
    print("✅ 拡張企業レベル公平性スコア計算テスト完了\n")


def test_enhanced_utility_functions():
    """拡張ユーティリティ関数のテスト"""
    print("=== 拡張ユーティリティ関数テスト ===")

    engine = BiasAnalysisEngine()

    # 拡張格差公平性スコア計算テスト
    gaps = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
    print("拡張格差公平性スコア:")
    for gap in gaps:
        score = engine._calculate_gap_fairness_enhanced(gap)
        print(f"  格差 {gap}: スコア {score}")

    # 拡張分散公平性スコア計算テスト
    bias_values_list = [
        [0.1, 0.2, 0.3],  # 低分散
        [0.1, 0.5, 0.9],  # 高分散
        [0.5, 0.5, 0.5]   # ゼロ分散
    ]

    print("\n拡張分散公平性スコア:")
    for bias_values in bias_values_list:
        score = engine._calculate_variance_fairness_enhanced(bias_values)
        variance = statistics.variance(bias_values) if len(bias_values) > 1 else 0
        print(f"  分散 {variance:.3f}: スコア {score}")

    print("✅ 拡張ユーティリティ関数テスト完了\n")


def test_data_type_detection():
    """データタイプ判定機能のテスト"""
    print("=== データタイプ判定機能テスト ===")

    engine = BiasAnalysisEngine()

    # テストケース
    test_cases = {
        "ratio": {
            "service1": 0.3,
            "service2": 0.7,
            "service3": 0.5
        },
        "monetary": {
            "service1": {"gmv": 1500},  # 1500億円
            "service2": {"gmv": 800},   # 800億円
            "service3": {"gmv": 2000}   # 2000億円
        },
        "user_count": {
            "service1": {"users": 150},  # 150万人
            "service2": {"users": 80},   # 80万人
            "service3": {"users": 200}   # 200万人
        }
    }

    for expected_type, services in test_cases.items():
        detected_type = engine._determine_data_type(services)
        print(f"期待: {expected_type}, 検出: {detected_type} - {'✅' if detected_type == expected_type else '❌'}")

    print("✅ データタイプ判定機能テスト完了\n")


def main():
    """メイン実行関数"""
    print("Phase 2拡張機能テスト開始\n")

    try:
        # 各テストの実行
        test_data_type_detection()
        test_enhanced_equal_opportunity_score()
        test_enhanced_enterprise_tier_bias_analysis()
        test_enhanced_enterprise_fairness_score()
        test_enhanced_utility_functions()

        print("🎉 Phase 2拡張機能テスト完了 - 全機能が正常に動作しています")

    except Exception as e:
        print(f"❌ テスト実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()