#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GitHub Actions用バイアス分析実行スクリプト

Usage:
    python scripts/run_bias_analysis.py --date 20250624
    python scripts/run_bias_analysis.py --date 20250624 --storage-mode s3
    python scripts/run_bias_analysis.py --date 20250624 --verbose
"""

import os
import sys
import argparse
import logging
import traceback
from datetime import datetime
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.bias_analysis_engine import BiasAnalysisEngine
from src.analysis.hybrid_data_loader import HybridDataLoader

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """ログレベルの設定"""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('src').setLevel(logging.DEBUG)


def run_bias_analysis(date: str, storage_mode: str = None, verbose: bool = False, runs: int = None) -> bool:
    """
    統合バイアス分析を実行
    """
    try:
        # 環境変数からストレージモードを取得（引数優先）
        if storage_mode is None:
            storage_mode = os.environ.get('STORAGE_MODE', 'auto')

        logger.info(f"🔧 ストレージモード: {storage_mode}")

        # HybridDataLoaderを初期化
        data_loader = HybridDataLoader(storage_mode=storage_mode)
        logger.info(f"📂 HybridDataLoader初期化完了: mode={storage_mode}")

        # バイアス分析エンジンを初期化
        engine = BiasAnalysisEngine(storage_mode=storage_mode)
        logger.info(f"🔬 BiasAnalysisEngine初期化完了")

        # 統合データセットの分析を実行
        logger.info(f"🚀 統合バイアス分析開始: {date}")
        # runsはrawデータ探索用。integratedデータは常にcorporate_bias_dataset.json
        results = engine.analyze_integrated_dataset(date, runs=runs)

        # 分析結果の概要をログ出力
        metadata = results.get('metadata', {})
        logger.info(f"📊 バイアス分析完了: 実行回数={metadata.get('execution_count', 'N/A')}")
        logger.info(f"📈 信頼性レベル: {metadata.get('reliability_level', 'N/A')}")

        sentiment_data = results.get('sentiment_bias_analysis', {})
        category_count = len(sentiment_data)
        logger.info(f"🎯 分析カテゴリ数: {category_count}")

        # 品質レポートの出力
        availability = results.get('data_availability_summary', {})
        available_metrics = sum(
            1 for m in availability.get('available_metrics', {}).values()
            if m.get('available', False)
        )
        total_metrics = len(availability.get('available_metrics', {}))
        logger.info(f"📋 利用可能指標: {available_metrics}/{total_metrics}")

        # データソース情報
        data_source = metadata.get('data_source', 'unknown')
        logger.info(f"💾 データソース: {data_source}")

        # 分析限界の警告
        limitations = results.get('analysis_limitations', {})
        if limitations:
            logger.warning("⚠️ 分析限界:")
            for key, value in limitations.items():
                if isinstance(value, list):
                    for item in value:
                        logger.warning(f"  - {item}")
                else:
                    logger.warning(f"  - {key}: {value}")

        logger.info("✅ 統合バイアス分析が正常に完了しました")
        return True

    except Exception as e:
        logger.error(f"❌ バイアス分析エラー: {e}")
        if verbose:
            logger.error(traceback.format_exc())
        return False


def print_summary_stats(results: dict):
    """分析結果の統計サマリーを出力"""

    print("\n" + "="*60)
    print("📊 バイアス分析結果サマリー")
    print("="*60)

    # メタデータ情報
    metadata = results.get('metadata', {})
    print(f"📅 分析日: {metadata.get('analysis_date', 'N/A')}")
    print(f"🔄 実行回数: {metadata.get('execution_count', 'N/A')}")
    print(f"📈 信頼性レベル: {metadata.get('reliability_level', 'N/A')}")
    print(f"💾 データソース: {metadata.get('data_source', 'N/A')}")

    # カテゴリ別結果
    sentiment_data = results.get('sentiment_bias_analysis', {})
    if sentiment_data:
        print(f"\n🎯 分析カテゴリ数: {len(sentiment_data)}")

        for category, subcategories in sentiment_data.items():
            print(f"\n📂 {category}:")
            for subcategory, data in subcategories.items():
                entities = data.get('entities', {})
                print(f"  └─ {subcategory}: {len(entities)}企業")

    # 利用可能指標
    availability = results.get('data_availability_summary', {})
    if availability:
        print(f"\n📋 指標利用可能性:")
        available_metrics = availability.get('available_metrics', {})
        for metric, info in available_metrics.items():
            status = "✅" if info.get('available', False) else "❌"
            print(f"  {status} {metric}")

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description='統合バイアス分析実行スクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python scripts/run_bias_analysis.py --date 20250624
  python scripts/run_bias_analysis.py --date 20250624 --storage-mode s3
  python scripts/run_bias_analysis.py --date 20250624 --verbose
        """
    )

    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='分析対象日付 (YYYYMMDD形式, デフォルト: 今日)'
    )

    parser.add_argument(
        '--storage-mode',
        choices=['local', 's3', 'auto'],
        help='ストレージモード (デフォルト: 環境変数STORAGE_MODE)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログ出力'
    )

    parser.add_argument(
        '--summary',
        action='store_true',
        help='結果サマリーを表示'
    )

    parser.add_argument(
        '--runs',
        type=int,
        default=None,
        help='Perplexity API実行回数（該当するruns付きファイルを優先的に探索）'
    )

    args = parser.parse_args()

    # ログ設定
    setup_logging(args.verbose)

    # バイアス分析実行
    success = run_bias_analysis(
        date=args.date,
        storage_mode=args.storage_mode,
        verbose=args.verbose,
        runs=args.runs
    )

    # 終了コード設定
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()