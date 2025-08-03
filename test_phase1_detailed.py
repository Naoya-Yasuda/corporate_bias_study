#!/usr/bin/env python
# coding: utf-8

"""
Phase 1基盤機能詳細テストスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine

def test_share_value_extraction():
    """シェア値抽出機能のテスト"""
    print("=== シェア値抽出機能テスト ===")

    engine = BiasAnalysisEngine()

    # テストケース1: market_share
    service_data = {"market_share": 0.8954, "enterprise": "Google"}
    value = engine._extract_share_value(service_data)
    print(f"market_share抽出結果: {value}")
    assert value == 0.8954

    # テストケース2: gmv
    service_data = {"gmv": 67937, "enterprise": "Amazon"}
    value = engine._extract_share_value(service_data)
    print(f"gmv抽出結果: {value}")
    assert value == 67937

    # テストケース3: users
    service_data = {"users": 9800, "enterprise": "LINE"}
    value = engine._extract_share_value(service_data)
    print(f"users抽出結果: {value}")
    assert value == 9800

    # テストケース4: utilization_rate
    service_data = {"utilization_rate": 0.662, "enterprise": "Amazon"}
    value = engine._extract_share_value(service_data)
    print(f"utilization_rate抽出結果: {value}")
    assert value == 0.662

    print("✅ シェア値抽出機能テスト完了\n")

def test_data_type_normalization():
    """データタイプ別正規化のテスト"""
    print("=== データタイプ別正規化テスト ===")

    engine = BiasAnalysisEngine()

    # テストケース1: 比率系データ
    ratio_services = {
        "Google": {"market_share": 0.8954, "enterprise": "Google"},
        "Bing": {"market_share": 0.0402, "enterprise": "Microsoft"},
        "Yandex": {"market_share": 0.022, "enterprise": "Yandex"}
    }

    normalized = engine._normalize_by_data_type(ratio_services, "ratio")
    print(f"比率系正規化結果: {normalized}")
    assert normalized == {"Google": 0.8954, "Bing": 0.0402, "Yandex": 0.022}

    # テストケース2: 金額系データ
    monetary_services = {
        "Amazon": {"gmv": 67937, "enterprise": "Amazon"},
        "楽天市場": {"gmv": 56301, "enterprise": "楽天"},
        "Yahoo!ショッピング": {"gmv": 17547, "enterprise": "Yahoo"}
    }

    normalized = engine._normalize_by_data_type(monetary_services, "monetary")
    print(f"金額系正規化結果: {normalized}")
    assert len(normalized) == 3
    assert all(0 <= v <= 1 for v in normalized.values())

    print("✅ データタイプ別正規化テスト完了\n")

def test_enhanced_fair_share_ratio():
    """拡張Fair Share Ratio計算のテスト"""
    print("=== 拡張Fair Share Ratio計算テスト ===")

    engine = BiasAnalysisEngine()

    # テストケース1: 正常なケース
    ratio = engine._calculate_fair_share_ratio_enhanced(0.1, 0.5)
    print(f"正常ケース結果: {ratio}")
    assert 0.1 <= ratio <= 10.0

    # テストケース2: バイアスなし
    ratio = engine._calculate_fair_share_ratio_enhanced(0.0, 0.5)
    print(f"バイアスなし結果: {ratio}")
    assert ratio == 1.0

    # テストケース3: 正のバイアス
    ratio = engine._calculate_fair_share_ratio_enhanced(0.5, 0.5)
    print(f"正のバイアス結果: {ratio}")
    assert ratio > 1.0

    # テストケース4: 負のバイアス
    ratio = engine._calculate_fair_share_ratio_enhanced(-0.5, 0.5)
    print(f"負のバイアス結果: {ratio}")
    assert ratio < 1.0

    print("✅ 拡張Fair Share Ratio計算テスト完了\n")

def test_ratio_data_normalization():
    """比率系データ正規化のテスト"""
    print("=== 比率系データ正規化テスト ===")

    engine = BiasAnalysisEngine()

    # テストケース1: 正常範囲
    normalized = engine._normalize_ratio_data(0.5)
    print(f"正常範囲結果: {normalized}")
    assert normalized == 0.5

    # テストケース2: 範囲外（負の値）
    normalized = engine._normalize_ratio_data(-0.1)
    print(f"負の値結果: {normalized}")
    assert normalized == 0.0

    # テストケース3: 範囲外（1.0より大きい値）
    normalized = engine._normalize_ratio_data(1.5)
    print(f"1.0より大きい値結果: {normalized}")
    assert normalized == 1.0

    print("✅ 比率系データ正規化テスト完了\n")

def test_normalization_edge_cases():
    """正規化のエッジケーステスト"""
    print("=== 正規化エッジケーステスト ===")

    engine = BiasAnalysisEngine()

    # テストケース1: 空配列
    normalized = engine._normalize_absolute_data([], "min_max")
    print(f"空配列正規化結果: {normalized}")
    assert normalized == []

    # テストケース2: 同じ値の配列
    normalized = engine._normalize_absolute_data([100, 100, 100], "min_max")
    print(f"同じ値配列正規化結果: {normalized}")
    assert all(v == 0.5 for v in normalized)

    # テストケース3: 単一値
    normalized = engine._normalize_absolute_data([100], "min_max")
    print(f"単一値正規化結果: {normalized}")
    assert normalized == [0.5]

    print("✅ 正規化エッジケーステスト完了\n")

def main():
    """メイン実行関数"""
    print("Phase 1基盤機能詳細テスト開始\n")

    try:
        test_share_value_extraction()
        test_data_type_normalization()
        test_enhanced_fair_share_ratio()
        test_ratio_data_normalization()
        test_normalization_edge_cases()

        print("🎉 全てのPhase 1基盤機能詳細テストが成功しました！")

    except Exception as e:
        print(f"❌ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit(main())