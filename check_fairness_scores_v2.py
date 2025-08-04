#!/usr/bin/env python3
"""
大学カテゴリ対応の公平性スコア確認スクリプト
"""

import json
import sys

def check_fairness_scores():
    """公平性スコアを確認"""

    try:
        # 分析結果を読み込み
        with open('corporate_bias_datasets/integrated/20250803/bias_analysis_results.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        print("=== 大学カテゴリ対応の公平性スコア確認 ===\n")

        # 各カテゴリの結果を確認
        for category, subcategories in data.items():
            print(f"📊 カテゴリ: {category}")

            for subcategory, subcat_data in subcategories.items():
                if not isinstance(subcat_data, dict):
                    continue

                print(f"  📋 サブカテゴリ: {subcategory}")

                # market_dominance_analysisの確認
                if 'market_dominance_analysis' in subcat_data:
                    market_data = subcat_data['market_dominance_analysis']

                    # enterprise_levelの確認
                    if 'enterprise_level' in market_data:
                        enterprise_data = market_data['enterprise_level']
                        enterprise_available = enterprise_data.get('available', False)
                        enterprise_reason = enterprise_data.get('reason', 'N/A')
                        enterprise_score = enterprise_data.get('fairness_score', 'N/A')

                        print(f"    🏢 enterprise_level:")
                        print(f"      - available: {enterprise_available}")
                        print(f"      - reason: {enterprise_reason}")
                        print(f"      - fairness_score: {enterprise_score}")

                    # service_levelの確認
                    if 'service_level' in market_data:
                        service_data = market_data['service_level']
                        service_available = service_data.get('available', False)
                        service_reason = service_data.get('reason', 'N/A')
                        service_score = service_data.get('equal_opportunity_score', 'N/A')

                        print(f"    🔧 service_level:")
                        print(f"      - available: {service_available}")
                        print(f"      - reason: {service_reason}")
                        print(f"      - equal_opportunity_score: {service_score}")

                    # integrated_fairnessの確認
                    if 'integrated_fairness' in market_data:
                        integrated_data = market_data['integrated_fairness']
                        integrated_score = integrated_data.get('integrated_score', 'N/A')
                        confidence = integrated_data.get('confidence', 'N/A')
                        interpretation = integrated_data.get('interpretation', 'N/A')

                        print(f"    🔗 integrated_fairness:")
                        print(f"      - integrated_score: {integrated_score}")
                        print(f"      - confidence: {confidence}")
                        print(f"      - interpretation: {interpretation}")

                    # analysis_typeの確認
                    analysis_type = market_data.get('analysis_type', 'N/A')
                    print(f"    📊 analysis_type: {analysis_type}")

                print()  # 空行

        print("=== 確認完了 ===")

    except FileNotFoundError:
        print("❌ 分析結果ファイルが見つかりません")
        sys.exit(1)
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    check_fairness_scores()