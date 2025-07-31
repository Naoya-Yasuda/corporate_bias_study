#!/usr/bin/env python3
"""
シンプルなランキング分析のテストスクリプト
"""

import sys
import os
import json
from datetime import datetime
import numpy as np

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine, SimpleRanking

def test_simple_ranking_class():
    """SimpleRankingクラスのテスト"""
    print("=== SimpleRankingクラステスト ===")

    # テストケース1: 公式サイト
    ranking1 = SimpleRanking("aws.amazon.com", 1, "google", "AWS", "official")
    print(f"公式サイト: {ranking1}")

    # テストケース2: 評判サイト
    ranking2 = SimpleRanking("techcrunch.com", 3, "perplexity", "AWS", "reputation")
    print(f"評判サイト: {ranking2}")

    print()

def test_extract_simple_rankings():
    """シンプルな順位付きドメイン抽出のテスト"""
    print("=== シンプルな順位付きドメイン抽出テスト ===")

    engine = BiasAnalysisEngine()

    # テストデータ
    test_data = {
        "entities": {
            "AWS": {
                "official_results": [
                    {"domain": "aws.amazon.com", "url": "https://aws.amazon.com"},
                    {"domain": "amazon.com", "url": "https://amazon.com"}
                ],
                "reputation_results": [
                    {"domain": "techcrunch.com", "url": "https://techcrunch.com"},
                    {"domain": "zdnet.com", "url": "https://zdnet.com"}
                ]
            },
            "Azure": {
                "official_results": [
                    {"domain": "azure.microsoft.com", "url": "https://azure.microsoft.com"}
                ],
                "reputation_results": [
                    {"domain": "techcrunch.com", "url": "https://techcrunch.com"},
                    {"domain": "cnet.com", "url": "https://cnet.com"}
                ]
            }
        }
    }

    # 抽出テスト
    rankings = engine.extract_simple_rankings(test_data, "test")
    print(f"抽出されたランキング数: {len(rankings)}")

    for ranking in rankings:
        print(f"  {ranking}")

    print()

def test_simple_ranking_calculation():
    """シンプルな順位統合のテスト"""
    print("=== シンプルな順位統合テスト ===")

    engine = BiasAnalysisEngine()

    # テストデータ
    rankings = [
        SimpleRanking("aws.amazon.com", 1, "google", "AWS", "official"),
        SimpleRanking("techcrunch.com", 2, "google", "AWS", "reputation"),
        SimpleRanking("techcrunch.com", 1, "perplexity", "Azure", "reputation"),
        SimpleRanking("azure.microsoft.com", 3, "google", "Azure", "official"),
        SimpleRanking("aws.amazon.com", 2, "perplexity", "AWS", "official")
    ]

    # シンプルな順位統合
    result = engine.calculate_simple_ranking(rankings)
    print(f"統合結果: {result}")

    print()

def test_simple_ranking_metrics():
    """シンプルなランキングメトリクスのテスト"""
    print("=== シンプルなランキングメトリクステスト ===")

    engine = BiasAnalysisEngine()

    # テストデータ
    google_data = {
        "entities": {
            "AWS": {
                "official_results": [
                    {"domain": "aws.amazon.com", "url": "https://aws.amazon.com"},
                    {"domain": "amazon.com", "url": "https://amazon.com"}
                ],
                "reputation_results": [
                    {"domain": "techcrunch.com", "url": "https://techcrunch.com"}
                ]
            },
            "Azure": {
                "official_results": [
                    {"domain": "azure.microsoft.com", "url": "https://azure.microsoft.com"}
                ],
                "reputation_results": [
                    {"domain": "zdnet.com", "url": "https://zdnet.com"}
                ]
            }
        }
    }

    citations_data = {
        "entities": {
            "AWS": {
                "official_results": [
                    {"domain": "aws.amazon.com", "url": "https://aws.amazon.com"}
                ],
                "reputation_results": [
                    {"domain": "techcrunch.com", "url": "https://techcrunch.com"},
                    {"domain": "cnet.com", "url": "https://cnet.com"}
                ]
            },
            "Azure": {
                "official_results": [
                    {"domain": "azure.microsoft.com", "url": "https://azure.microsoft.com"}
                ],
                "reputation_results": [
                    {"domain": "techcrunch.com", "url": "https://techcrunch.com"}
                ]
            }
        }
    }

    # シンプルなメトリクス計算
    try:
        results = engine.compute_simple_ranking_metrics(google_data, citations_data)
        print("シンプルなメトリクス計算成功:")

        if "error" in results:
            print(f"エラー: {results['error']}")
        else:
            print(f"Kendall Tau: {results['kendall_tau']:.3f}")
            print(f"RBO Score: {results['rbo_score']:.3f}")
            print(f"Overlap Ratio: {results['overlap_ratio']:.3f}")
            print(f"Google Domains: {results['google_domains_count']}")
            print(f"Citations Domains: {results['citations_domains_count']}")
            print(f"Common Domains: {results['common_domains_count']}")
            print(f"共通ドメイン: {results['common_domains']}")

    except Exception as e:
        print(f"エラー: {e}")

    print()

def test_with_real_data():
    """実際のデータでのテスト"""
    print("=== 実際のデータでのテスト ===")

    # 20250721のデータを使用（Googleデータとcitationsデータの両方が利用可能）
    test_date = "20250721"
    data_dir = "corporate_bias_datasets/raw_data"

    print(f"使用するデータ日付: {test_date}")

    # ファイルパス
    google_file = os.path.join(data_dir, test_date, "google", "custom_search.json")
    citations_file = os.path.join(data_dir, test_date, "perplexity", "citations_2runs.json")

    if not os.path.exists(google_file) or not os.path.exists(citations_file):
        print("必要なデータファイルが見つかりません")
        print(f"Googleファイル: {google_file} - 存在: {os.path.exists(google_file)}")
        print(f"Citationsファイル: {citations_file} - 存在: {os.path.exists(citations_file)}")
        return

    # データ読み込み
    try:
        with open(google_file, 'r', encoding='utf-8') as f:
            google_data = json.load(f)

        with open(citations_file, 'r', encoding='utf-8') as f:
            citations_data = json.load(f)

        print("データ読み込み成功")
        print(f"Googleデータカテゴリ: {list(google_data.keys())}")
        print(f"Citationsデータカテゴリ: {list(citations_data.keys())}")

        # 分析実行
        engine = BiasAnalysisEngine()
        results = engine._analyze_citations_google_comparison(google_data, citations_data)

        print("\n分析結果:")
        for category, category_results in results.items():
            print(f"\nカテゴリ: {category}")
            for subcategory, subcategory_results in category_results.items():
                if "error" not in subcategory_results:
                    print(f"  サブカテゴリ: {subcategory}")

                    # シンプルなメトリクス
                    if "ranking_similarity" in subcategory_results:
                        ranking = subcategory_results["ranking_similarity"]
                        if "error" not in ranking:
                            print(f"    シンプルメトリクス: Kendall Tau={ranking['kendall_tau']:.3f}, RBO={ranking['rbo_score']:.3f}, Overlap={ranking['overlap_ratio']:.3f}")
                            print(f"    共通ドメイン数: {ranking['common_domains_count']}")
                        else:
                            print(f"    エラー: {ranking['error']}")

                    # 従来のメトリクス
                    if "legacy_ranking_similarity" in subcategory_results:
                        legacy = subcategory_results["legacy_ranking_similarity"]
                        print(f"    従来のメトリクス: Kendall Tau={legacy.get('kendall_tau', 0):.3f}, RBO={legacy.get('rbo_score', 0):.3f}")

                    # データ品質
                    if "data_quality" in subcategory_results:
                        quality = subcategory_results["data_quality"]
                        print(f"    データ品質: Google={quality.get('google_data_complete', False)}, Citations={quality.get('citations_data_complete', False)}")

    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

def main():
    """メイン関数"""
    print("シンプルなランキング分析のテスト開始")
    print(f"実行日時: {datetime.now()}")
    print("=" * 50)

    # 各テストを実行
    test_simple_ranking_class()
    test_extract_simple_rankings()
    test_simple_ranking_calculation()
    test_simple_ranking_metrics()
    test_with_real_data()

    print("=" * 50)
    print("テスト完了")

if __name__ == "__main__":
    main()