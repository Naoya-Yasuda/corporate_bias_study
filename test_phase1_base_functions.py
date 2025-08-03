#!/usr/bin/env python
# coding: utf-8

"""
Phase 1基盤機能テストスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine

def test_data_type_determination():
    """データタイプ判定機能のテスト"""
    print("=== データタイプ判定機能テスト ===")

    engine = BiasAnalysisEngine()

    # テストケース1: 比率系データ
    ratio_services = {
        "Google": {"market_share": 0.8954, "enterprise": "Google"},
        "Bing": {"market_share": 0.0402, "enterprise": "Microsoft"}
    }

    data_type = engine._determine_data_type(ratio_services)
    print(f"比率系データ判定結果: {data_type}")
    assert data_type == "ratio"

    # テストケース2: 金額系データ
    monetary_services = {
        "Amazon": {"gmv": 67937, "enterprise": "Amazon"},
        "楽天市場": {"gmv": 56301, "enterprise": "楽天"}
    }

    data_type = engine._determine_data_type(monetary_services)
    print(f"金額系データ判定結果: {data_type}")
    assert data_type == "monetary"

    print("✅ データタイプ判定機能テスト完了\n")

def test_normalization_functions():
    """正規化関数群のテスト"""
    print("=== 正規化関数群テスト ===")

    engine = BiasAnalysisEngine()

    # テストデータ
    test_values = [100, 500, 1000, 2000, 5000]

    # min_max正規化
    normalized = engine._normalize_absolute_data(test_values, "min_max")
    print(f"min_max正規化結果: {normalized}")
    assert min(normalized) == 0.0
    assert max(normalized) == 1.0

    print("✅ 正規化関数群テスト完了\n")

def main():
    """メイン実行関数"""
    print("Phase 1基盤機能テスト開始\n")

    try:
        test_data_type_determination()
        test_normalization_functions()
        print("🎉 Phase 1基盤機能テストが成功しました！")

    except Exception as e:
        print(f"❌ テスト失敗: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())