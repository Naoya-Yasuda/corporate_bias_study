#!/usr/bin/env python3
"""
企業レベル公平性スコア修正の実際のデータテスト
"""

import json
import sys
import os
from typing import Dict, Any

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine


def test_actual_data():
    """実際のデータで企業レベル公平性スコアをテスト"""

    # 分析エンジンを初期化
    engine = BiasAnalysisEngine()

    # 実際のデータファイルを読み込み
    data_file = "corporate_bias_datasets/integrated/20250803/bias_analysis_results.json"

    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"データファイルが見つかりません: {data_file}")
        return

    print("=== 企業レベル公平性スコア修正テスト ===\n")

    # relative_bias_analysisから企業レベル公平性スコアを抽出
    relative_bias_analysis = data.get("relative_bias_analysis", {})

    for category, category_data in relative_bias_analysis.items():
        print(f"カテゴリ: {category}")

        for subcategory, subcategory_data in category_data.items():
            if isinstance(subcategory_data, dict) and "market_dominance_analysis" in subcategory_data:
                market_dominance = subcategory_data["market_dominance_analysis"]

                if "enterprise_level" in market_dominance and isinstance(market_dominance["enterprise_level"], dict):
                    enterprise_analysis = market_dominance["enterprise_level"]

                    if enterprise_analysis.get("available", False):
                        # 修正前のスコア
                        old_score = enterprise_analysis.get("integrated_fairness_score", 0.0)

                        print(f"  {subcategory}:")
                        print(f"    修正前: {old_score}")

                        # 詳細情報を表示
                        tier_stats = enterprise_analysis.get("tier_stats", {})
                        tier_gaps = enterprise_analysis.get("tier_gaps", {})
                        correlation_data = enterprise_analysis.get("correlation_analysis", {})

                        print(f"    階層統計: {len(tier_stats)}階層")
                        for tier, stats in tier_stats.items():
                            print(f"      {tier}: {stats.get('count', 0)}社, 平均バイアス: {stats.get('mean_bias', 0):.3f}, min: {stats.get('min_bias', 0):.3f}, max: {stats.get('max_bias', 0):.3f}")

                        print(f"    格差情報:")
                        for gap_key, gap_value in tier_gaps.items():
                            print(f"      {gap_key}: {gap_value}")

                        # 実際の計算過程を確認
                        if tier_stats and tier_gaps:
                            print(f"    論文定義に基づく計算過程:")

                            # 各階層の平均バイアスを取得
                            tier_means = {}
                            for tier, stats in tier_stats.items():
                                if stats.get("count", 0) > 0:
                                    tier_means[tier] = stats["mean_bias"]
                                    print(f"      {tier}: 平均バイアス = {stats['mean_bias']:.3f}")

                            # 1. 大企業vs小企業格差による公平性スコア（35%）
                            mega_vs_mid_gap = 0.0
                            if "mega_enterprise" in tier_means and "mid_enterprise" in tier_means:
                                mega_vs_mid_gap = abs(tier_means["mega_enterprise"] - tier_means["mid_enterprise"])
                            elif "mega_enterprise" in tier_means and "large_enterprise" in tier_means:
                                mega_vs_mid_gap = abs(tier_means["mega_enterprise"] - tier_means["large_enterprise"])

                            mega_vs_mid_fairness = engine._calculate_gap_fairness_enhanced(mega_vs_mid_gap)
                            print(f"      大企業vs小企業格差: {mega_vs_mid_gap:.3f} → 公平性スコア: {mega_vs_mid_fairness:.3f} (重み35%)")

                            # 2. 中企業vs小企業格差による公平性スコア（35%）
                            large_vs_mid_gap = 0.0
                            if "large_enterprise" in tier_means and "mid_enterprise" in tier_means:
                                large_vs_mid_gap = abs(tier_means["large_enterprise"] - tier_means["mid_enterprise"])
                            elif "mega_enterprise" in tier_means and "large_enterprise" in tier_means:
                                large_vs_mid_gap = abs(tier_means["mega_enterprise"] - tier_means["large_enterprise"])

                            large_vs_mid_fairness = engine._calculate_gap_fairness_enhanced(large_vs_mid_gap)
                            print(f"      中企業vs小企業格差: {large_vs_mid_gap:.3f} → 公平性スコア: {large_vs_mid_fairness:.3f} (重み35%)")

                            # 3. 分散による公平性スコア計算（30%）
                            all_bias_values = []
                            for tier, stats in tier_stats.items():
                                if stats.get("count", 0) > 0:
                                    all_bias_values.extend([stats["mean_bias"]] * stats["count"])

                            variance_fairness = engine._calculate_variance_fairness_enhanced(all_bias_values)
                            print(f"      分散公平性スコア: {variance_fairness:.3f} (重み30%)")

                            # 重み付け計算
                            WEIGHTS = {"mega_vs_mid_gap": 0.35, "large_vs_mid_gap": 0.35, "variance_fairness": 0.30}
                            final_score = (
                                WEIGHTS["mega_vs_mid_gap"] * mega_vs_mid_fairness +
                                WEIGHTS["large_vs_mid_gap"] * large_vs_mid_fairness +
                                WEIGHTS["variance_fairness"] * variance_fairness
                            )
                            print(f"      最終スコア: {final_score:.3f}")

                        # 修正後のスコアを計算
                        new_score = engine._calculate_enterprise_fairness_score_enhanced(enterprise_analysis)
                        print(f"    修正後: {new_score}")

                        if old_score != new_score:
                            print(f"    ✅ 修正成功: {old_score} → {new_score}")
                        else:
                            print(f"    ℹ️  変更なし: {old_score}")

                        if correlation_data:
                            correlation = correlation_data.get("correlation_coefficient", 0.0)
                            print(f"    相関係数: {correlation:.3f}")

                        print()  # 空行を追加

    print("=== テスト完了 ===")


if __name__ == '__main__':
    test_actual_data()