#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ローカル環境でのバイアス分析テスト用スクリプト

Usage:
    python scripts/test_local.py
    python scripts/test_local.py --date 20250624
"""

import os
import sys
import argparse
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_hybrid_data_loader(date: str = "20250624"):
    """HybridDataLoaderの動作テスト"""

    print("🔍 HybridDataLoader動作テスト開始")

    try:
        from src.analysis.hybrid_data_loader import HybridDataLoader

        # ローカルモードでテスト
        print("📂 ローカルモードテスト...")
        loader_local = HybridDataLoader(storage_mode="local")

        try:
            data = loader_local.load_analysis_results(date)
            print(f"✅ ローカル読み込み成功: {len(data)} 項目")
        except Exception as e:
            print(f"❌ ローカル読み込み失敗: {e}")

        # autoモードでテスト
        print("🔄 autoモードテスト...")
        loader_auto = HybridDataLoader(storage_mode="auto")

        try:
            data = loader_auto.load_analysis_results(date)
            print(f"✅ auto読み込み成功: {len(data)} 項目")
        except Exception as e:
            print(f"❌ auto読み込み失敗: {e}")

        print("✅ HybridDataLoaderテスト完了")
        return True

    except ImportError as e:
        print(f"❌ モジュールインポートエラー: {e}")
        return False

def test_bias_analysis_engine(date: str = "20250624"):
    """BiasAnalysisEngineの動作テスト"""

    print("\n🔬 BiasAnalysisEngine動作テスト開始")

    try:
        from src.analysis.bias_analysis_engine import BiasAnalysisEngine

        # エンジン初期化
        engine = BiasAnalysisEngine(storage_mode="local")
        print("✅ BiasAnalysisEngine初期化完了")

        return True

    except ImportError as e:
        print(f"❌ BiasAnalysisEngineインポートエラー: {e}")
        return False
    except Exception as e:
        print(f"❌ BiasAnalysisEngine初期化エラー: {e}")
        return False

def check_data_availability(date: str = "20250624"):
    """データファイルの存在確認"""

    print(f"\n📊 データ存在確認: {date}")

    base_path = f"corporate_bias_datasets/integrated/{date}/"

    files_to_check = [
        "corporate_bias_dataset.json",
        "bias_analysis_results.json",
        "collection_summary.json"
    ]

    for filename in files_to_check:
        filepath = f"{base_path}{filename}"
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"✅ {filename}: {size:,}バイト")
        else:
            print(f"❌ {filename}: 見つかりません")

def main():
    parser = argparse.ArgumentParser(description='ローカル環境テストスクリプト')
    parser.add_argument('--date', default='20250624', help='テスト対象日付 (YYYYMMDD)')

    args = parser.parse_args()

    print("🧪 ローカル環境テスト開始")
    print("=" * 50)

    # データ存在確認
    check_data_availability(args.date)

    # HybridDataLoaderテスト
    loader_ok = test_hybrid_data_loader(args.date)

    # BiasAnalysisEngineテスト
    engine_ok = test_bias_analysis_engine(args.date)

    print("\n" + "=" * 50)
    if loader_ok and engine_ok:
        print("✅ 全テスト成功！")
        sys.exit(0)
    else:
        print("❌ 一部テスト失敗")
        sys.exit(1)

if __name__ == '__main__':
    main()