#!/usr/bin/env python
# coding: utf-8

"""
統合データセット作成CLIスクリプト

使用例:
python -m src.integrator.create_integrated_dataset --date 20250623 --verbose
python -m src.integrator.create_integrated_dataset --date 20250623 --force-recreate
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# プロジェクトルートの追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.integrator.dataset_integrator import DatasetIntegrator
from src.integrator.data_validator import DataValidator, ProcessingAbortedException


def setup_logging(verbose: bool = False):
    """ログ設定"""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def validate_date_format(date_str: str) -> bool:
    """日付形式の検証"""
    try:
        datetime.strptime(date_str, '%Y%m%d')
        return True
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="統合データセット作成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本的な統合データセット作成
  python -m src.integrator.create_integrated_dataset --date 20250623

  # 詳細ログ付きで実行
  python -m src.integrator.create_integrated_dataset --date 20250623 --verbose

  # 既存データを強制的に再作成
  python -m src.integrator.create_integrated_dataset --date 20250623 --force-recreate

  # 出力先ディレクトリを指定
  python -m src.integrator.create_integrated_dataset --date 20250623 --output-dir /path/to/output
        """
    )

    parser.add_argument(
        '--date',
        required=True,
        help='処理対象日付（YYYYMMDD形式）'
    )

    parser.add_argument(
        '--output-dir',
        default='corporate_bias_datasets',
        help='出力ベースディレクトリ（デフォルト: corporate_bias_datasets）'
    )

    parser.add_argument(
        '--force-recreate',
        action='store_true',
        help='既存の統合データセットを強制的に再作成'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細なログ出力を表示'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='実際の処理は行わず、処理予定の内容のみ表示'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='データ品質チェックのみ実行（統合データセットは作成しない）'
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
    logger = logging.getLogger(__name__)

    # 日付形式検証
    if not validate_date_format(args.date):
        logger.error(f"不正な日付形式です: {args.date} (YYYYMMDD形式で指定してください)")
        sys.exit(1)

    # ドライランモード
    if args.dry_run:
        logger.info("=== ドライランモード ===")
        logger.info(f"処理対象日付: {args.date}")
        # 出力ディレクトリはintegrator生成後にintegrator.integrated_dirで表示
        logger.info(f"強制再作成: {args.force_recreate}")
        logger.info(f"検証のみ: {args.validate_only}")
        logger.info(f"runs: {args.runs}")

        # 入力ファイルの存在確認
        integrator = DatasetIntegrator(args.date)
        raw_data = integrator._load_raw_data(verbose=True, runs=args.runs)

        if raw_data:
            logger.info(f"読み込み可能なデータソース: {list(raw_data.keys())}")
            logger.info("ドライラン完了")
        else:
            logger.warning("読み込み可能なデータが見つかりません")

        sys.exit(0)

    try:
        # 統合データセット作成実行
        logger.info("=== 統合データセット作成開始 ===")
        logger.info(f"処理対象日付: {args.date}")
        # 出力ディレクトリはintegrator生成後にintegrator.integrated_dirで表示

        integrator = DatasetIntegrator(args.date)

        # 1. 生データの読み込み
        raw_data = integrator._load_raw_data(verbose=args.verbose, runs=args.runs)
        if not raw_data:
            logger.error("読み込み可能な生データが見つかりません")
            sys.exit(1)

        # 2. バリデーション（必須フィールド存在チェック）
        validator = DataValidator()
        validation_results = validator.validate_all_data(raw_data)
        critical_errors = [e for e in validation_results if e.get("severity") == "CRITICAL"]
        missing_required = [
            e for e in validation_results
            if "必須フィールド" in e.get("message", "") and e.get("severity") in ("CRITICAL", "ERROR")
        ]
        if critical_errors or missing_required:
            logger.error("=== バリデーションエラーにより統合処理を中断します ===")
            for err in critical_errors + missing_required:
                logger.error(f"{err.get('message', '')} - {err.get('path', '')}")
            sys.exit(1)

        if args.validate_only:
            logger.info("データ品質チェックのみ実行")
            raw_data = integrator._load_raw_data(verbose=args.verbose)
            if raw_data:
                validation_results = integrator.validator.validate_all_data(raw_data)
                validation_summary = integrator.validator.get_validation_summary()

                logger.info("=== データ品質チェック結果 ===")
                logger.info(f"品質スコア: {validation_summary.get('validation_score', 0.0):.2f}")
                logger.info(f"致命的エラー: {validation_summary.get('critical_errors', 0)}件")
                logger.info(f"エラー: {validation_summary.get('errors', 0)}件")
                logger.info(f"警告: {validation_summary.get('warnings', 0)}件")

                if validation_summary.get('critical_errors', 0) > 0:
                    logger.error("致命的エラーが検出されました")
                    sys.exit(1)
                elif validation_summary.get('errors', 0) > 0:
                    logger.warning("エラーが検出されました")
                    sys.exit(0)
                else:
                    logger.info("データ品質チェック完了")
                    sys.exit(0)
            else:
                logger.error("読み込み可能なデータが見つかりません")
                sys.exit(1)

        # 既存ファイルの確認
        output_files = integrator.list_output_files()
        if output_files and not args.force_recreate:
            logger.warning("統合データセットが既に存在します:")
            for file_path in output_files:
                logger.warning(f"  {file_path}")
            logger.warning("再作成する場合は --force-recreate オプションを使用してください")
            sys.exit(0)

        # 統合データセット作成実行
        integrated_dataset = integrator.create_integrated_dataset(
            force_recreate=args.force_recreate,
            verbose=args.verbose
        )

        if integrated_dataset:
            logger.info("=== 統合データセット作成完了 ===")

            # 生成ファイルリスト表示
            output_files = integrator.list_output_files()
            logger.info("生成されたファイル:")
            for file_path in output_files:
                file_size = os.path.getsize(file_path) / 1024  # KB
                logger.info(f"  {file_path} ({file_size:.1f} KB)")

            # 統合メタデータ表示
            metadata = integrator.get_integration_metadata()
            logger.info(f"データ品質スコア: {metadata.get('data_quality_score', 0.0):.2f}")
            logger.info(f"処理ステータス: {metadata.get('processing_summary', {}).get('status', 'UNKNOWN')}")

            if 'schema_info' in metadata:
                schema_info = metadata['schema_info']
                logger.info(f"フィールド数: {schema_info.get('field_count', 0)}")
                logger.info(f"レコード数: {schema_info.get('record_count', 0)}")
                logger.info(f"データソース: {', '.join(schema_info.get('data_sources', []))}")

            logger.info("統合データセットは以下のディレクトリに保存されました:")
            logger.info(f"  {integrator.integrated_dir}")

        else:
            logger.error("統合データセットの作成に失敗しました")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("ユーザーによって処理が中断されました")
        sys.exit(130)

    except Exception as e:
        logger.error(f"統合データセット作成中にエラーが発生しました: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()