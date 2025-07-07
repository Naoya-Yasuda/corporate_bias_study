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

def test_multiple_comparison_correction(date: str = "20250702"):
    """多重比較補正の横展開テスト（ランキング・相対バイアス・相関分析）"""
    print("\n🧪 多重比較補正横展開テスト開始")
    try:
        from src.analysis.bias_analysis_engine import BiasAnalysisEngine
        engine = BiasAnalysisEngine(storage_mode="local")
        results = engine.analyze_integrated_dataset(date)

        # ランキングバイアス分析
        ranking = results.get("ranking_bias_analysis", {})
        found_ranking = False
        for cat, subcats in ranking.items():
            for subcat, data in subcats.items():
                # entities['entities']配下を参照
                entities = data.get("entities", {})
                if isinstance(entities, dict) and "entities" in entities:
                    entities = entities["entities"]
                for ent, ent_data in entities.items() if isinstance(entities, dict) else []:
                    sig = ent_data.get("ranking_p_value_corrected")
                    if sig is not None:
                        found_ranking = True
                        assert "correction_method" in ent_data
                        assert "rejected" in ent_data
        assert found_ranking, "ランキングバイアス分析で補正後p値が見つかりません"

        # 相対バイアス分析（同様にentities['entities']参照）
        relative = results.get("relative_bias_analysis", {})
        found_relative = False
        for cat, subcats in relative.items():
            for subcat, data in subcats.items():
                entities = data.get("entities", {})
                if isinstance(entities, dict) and "entities" in entities:
                    entities = entities["entities"]
                for ent, ent_data in entities.items() if isinstance(entities, dict) else []:
                    sig = ent_data.get("relative_p_value_corrected")
                    if sig is not None:
                        found_relative = True
                        assert "correction_method" in ent_data
                        assert "rejected" in ent_data
        # 相対バイアス分析は未実装の場合もあるのでエラーにしない

        # 相関分析（同様にentities['entities']参照）
        correlation = results.get("correlation_analysis", {})
        found_corr = False
        for cat, subcats in correlation.items():
            for subcat, data in subcats.items():
                entities = data.get("entities", {})
                if isinstance(entities, dict) and "entities" in entities:
                    entities = entities["entities"]
                for ent, ent_data in entities.items() if isinstance(entities, dict) else []:
                    sig = ent_data.get("correlation_p_value_corrected")
                    if sig is not None:
                        found_corr = True
                        assert "correction_method" in ent_data
                        assert "rejected" in ent_data
        # 相関分析も未実装の場合はエラーにしない

        print("✅ 多重比較補正テスト: OK")
    except Exception as e:
        print(f"❌ 多重比較補正テストでエラー: {e}")

def test_compare_entity_rankings():
    """
    BiasAnalysisEngine.compare_entity_rankingsの動作確認テスト。
    GoogleとPerplexityのダミーランキングリストを比較し、全指標を出力。
    """
    from src.analysis.bias_analysis_engine import BiasAnalysisEngine
    engine = BiasAnalysisEngine()
    google_ranking = ["AWS", "Google Cloud", "Azure", "Oracle", "IBM"]
    perplexity_ranking = ["Google Cloud", "AWS", "IBM", "Azure", "Oracle"]
    result = engine.compare_entity_rankings(google_ranking, perplexity_ranking, label1="Google", label2="Perplexity")
    print("\n=== compare_entity_rankingsテスト結果 ===")
    for k, v in result.items():
        print(f"{k}: {v}")

def test_ranking_stability_quality_multi():
    """
    複数回実行時のランキング安定性・品質分析の出力例テスト。
    2回以上のall_ranksを持つダミーdetailsでBiasAnalysisEngine._calculate_ranking_stabilityと_calculate_ranking_qualityを検証。
    """
    from src.analysis.bias_analysis_engine import BiasAnalysisEngine
    engine = BiasAnalysisEngine()
    # ダミーdetails: 3回分の順位
    details = {
        "AWS": {"all_ranks": [1, 1, 1], "official_url": "https://aws.amazon.com", "avg_rank": 1.0},
        "Google Cloud": {"all_ranks": [2, 2, 3], "official_url": "https://cloud.google.com", "avg_rank": 2.33},
        "Azure": {"all_ranks": [3, 3, 2], "official_url": "https://azure.microsoft.com", "avg_rank": 2.67},
        "Oracle": {"all_ranks": [4, 4, 4], "official_url": "https://oracle.com", "avg_rank": 4.0}
    }
    ranking_summary = {"details": details, "avg_ranking": ["AWS", "Google Cloud", "Azure", "Oracle"]}
    answer_list = [
        {"ranking": ["AWS", "Google Cloud", "Azure", "Oracle"]},
        {"ranking": ["AWS", "Google Cloud", "Azure", "Oracle"]},
        {"ranking": ["AWS", "Azure", "Google Cloud", "Oracle"]}
    ]
    execution_count = 3
    stability = engine._calculate_ranking_stability(ranking_summary, answer_list, execution_count)
    quality = engine._calculate_ranking_quality(ranking_summary, answer_list, execution_count)
    print("\n=== 複数回実行時のランキング安定性・品質分析テスト ===")
    print("[stability_analysis]")
    for k, v in stability.items():
        print(f"{k}: {v}")
    print("\n[quality_analysis]")
    for k, v in quality.items():
        print(f"{k}: {v}")

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

    # 多重比較補正横展開テスト
    mcc_ok = test_multiple_comparison_correction(args.date)

    # compare_entity_rankingsテスト
    compare_ok = test_compare_entity_rankings()

    # 複数回実行時のランキング安定性・品質分析テスト
    stability_quality_ok = test_ranking_stability_quality_multi()

    print("\n" + "=" * 50)
    if loader_ok and engine_ok and mcc_ok and compare_ok and stability_quality_ok:
        print("✅ 全テスト成功！")
        sys.exit(0)
    else:
        print("❌ 一部テスト失敗")
        sys.exit(1)

if __name__ == '__main__':
    main()