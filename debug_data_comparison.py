#!/usr/bin/env python3
"""
データ比較デバッグスクリプト
分析エンジンとUIの計算結果を比較して、値が異なる原因を特定する
"""

import json
import sys
import os
sys.path.append('src')

from analysis.bias_analysis_engine import BiasAnalysisEngine

def debug_data_comparison(date_or_path):
    """データの比較デバッグ"""

    # 分析エンジンでデータを読み込み
    engine = BiasAnalysisEngine()
    analysis_result = engine.analyze_integrated_dataset(date_or_path, output_mode="dict")

    print("=== データ比較デバッグ ===")
    print(f"分析対象: {date_or_path}")
    print()

    # perplexity_sentiment_flatデータを詳しく確認
    print("=== perplexity_sentiment_flatデータ詳細確認 ===")
    perplexity_sentiment_flat = analysis_result.get("perplexity_sentiment_flat", [])

    print(f"perplexity_sentiment_flatの長さ: {len(perplexity_sentiment_flat)}")

    if perplexity_sentiment_flat:
        print("最初のrowの構造:")
        first_row = perplexity_sentiment_flat[0]
        for key, value in first_row.items():
            if key in ["masked_values", "unmasked_values"]:
                print(f"  {key}: {value}")
                print(f"  {key}の型: {type(value)}")
                print(f"  {key}の長さ: {len(value) if isinstance(value, list) else 'N/A'}")
            else:
                print(f"  {key}: {value}")

    # AWSのデータを特定
    aws_data = None
    for row in perplexity_sentiment_flat:
        if (row.get("カテゴリ") == "デジタルサービス" and
            row.get("サブカテゴリ") == "クラウドサービス" and
            row.get("エンティティ") == "AWS"):
            aws_data = row
            break

    if aws_data:
        print("\n=== AWSデータ詳細 ===")
        print(f"masked_values: {aws_data.get('masked_values')}")
        print(f"unmasked_values: {aws_data.get('unmasked_values')}")

        # 手動計算
        masked_values = aws_data.get("masked_values", [])
        unmasked_values = aws_data.get("unmasked_values", [])

        if masked_values and unmasked_values:
            masked_avg = sum(masked_values) / len(masked_values)
            unmasked_avg = sum(unmasked_values) / len(unmasked_values)
            manual_delta = unmasked_avg - masked_avg

            print(f"手動計算結果:")
            print(f"  masked_avg: {masked_avg}")
            print(f"  unmasked_avg: {unmasked_avg}")
            print(f"  manual_delta: {manual_delta}")

    # sentiment_bias_analysisからAWSの結果を取得
    sentiment_analysis = analysis_result.get("sentiment_bias_analysis", {})
    aws_analysis = None

    for category, subcategories in sentiment_analysis.items():
        for subcategory, data in subcategories.items():
            if (category == "デジタルサービス" and subcategory == "クラウドサービス"):
                entities_data = data.get("entities", {})
                if "AWS" in entities_data:
                    aws_analysis = entities_data["AWS"]
                    break

    if aws_analysis:
        print("\n=== 分析エンジン結果（AWS） ===")
        basic_metrics = aws_analysis.get("basic_metrics", {})
        print(f"raw_delta: {basic_metrics.get('raw_delta')}")
        print(f"normalized_bias_index: {basic_metrics.get('normalized_bias_index')}")
        print(f"delta_values: {basic_metrics.get('delta_values')}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使用方法: python debug_data_comparison.py <date_or_path>")
        sys.exit(1)

    date_or_path = sys.argv[1]
    debug_data_comparison(date_or_path)