#!/usr/bin/env python3
import json

# 分析結果を読み込み
with open('corporate_bias_datasets/integrated/20250803/bias_analysis_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('=== 企業レベル公平性スコア算出状況調査 ===\n')

# relative_bias_analysisセクションを確認
if 'relative_bias_analysis' in data:
    relative_bias = data['relative_bias_analysis']
    for category in relative_bias:
        print(f'カテゴリ: {category}')
        for subcategory in relative_bias[category]:
            subcat_data = relative_bias[category][subcategory]
            if isinstance(subcat_data, dict) and 'market_dominance_analysis' in subcat_data:
                market_data = subcat_data['market_dominance_analysis']

                # enterprise_levelの確認
                if 'enterprise_level' in market_data:
                    enterprise_data = market_data['enterprise_level']
                    enterprise_available = enterprise_data.get('available', False)
                    enterprise_reason = enterprise_data.get('reason', 'N/A')
                    print(f'  {subcategory}:')
                    print(f'    enterprise_level: available={enterprise_available}, reason={enterprise_reason}')

                # service_levelの確認
                if 'service_level' in market_data:
                    service_data = market_data['service_level']
                    service_available = service_data.get('available', False)
                    service_reason = service_data.get('reason', 'N/A')
                    print(f'    service_level: available={service_available}, reason={service_reason}')

                # integrated_fairnessの確認
                if 'integrated_fairness' in market_data:
                    integrated_data = market_data['integrated_fairness']
                    integrated_score = integrated_data.get('integrated_score', 'N/A')
                    print(f'    integrated_fairness: score={integrated_score}')
        print()

print('=== 調査完了 ===')