#!/usr/bin/env python
# coding: utf-8

"""
ハイブリッドデータローダー - ローカル・S3両対応の統合データ読み込み

本モジュールは、integrated/ディレクトリ（ローカル）またはS3から
統合データセットを読み込み、分析結果を適切な場所に保存する
ハイブリッド機能を提供します。

Usage:
    loader = HybridDataLoader("auto")
    data = loader.load_integrated_data("20250624")
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from src.utils.storage_utils import load_json
from src.utils.storage_utils import save_results, list_s3_files
from src.utils.storage_config import get_base_paths, S3_BUCKET_NAME
from dotenv import load_dotenv
from src.utils.storage_utils import load_json_from_s3_integrated

# 環境変数を読み込み
load_dotenv()

# ログ設定
logger = logging.getLogger(__name__)


class HybridDataLoader:
    """ローカル・S3両対応の統合データローダー"""

    def __init__(self, storage_mode: str = None):
        """
        Parameters:
        -----------
        storage_mode : str, optional
            ストレージモード指定（指定なしの場合は環境変数STORAGE_MODEを使用、デフォルト: "auto"）
            - "local": integrated/ディレクトリから読み込み
            - "s3": S3から直接読み込み
            - "both": 両方使用（優先順位あり）
            - "auto": 自動選択（S3優先、フォールバックでローカル）
        """
        # 環境変数からストレージモードを取得
        if storage_mode is None:
            storage_mode = os.getenv("STORAGE_MODE", "auto")
            logger.info(f"環境変数STORAGE_MODEから取得: {storage_mode}")

        self.storage_mode = storage_mode
        self.base_path = Path("corporate_bias_datasets")
        self.integrated_path = self.base_path / "integrated"

        logger.info(f"HybridDataLoader初期化: mode={storage_mode}")

    def load_integrated_data(self, date_or_path: str, runs: int = None) -> Dict[str, Any]:
        """統合データセットを読み込み（runs指定時はcorporate_bias_dataset_{runs}runs.jsonを優先）"""
        filename = None
        if runs is not None:
            filename = f"corporate_bias_dataset_{runs}runs.json"
        else:
            filename = "corporate_bias_dataset.json"
        if self.storage_mode == "local":
            return self._load_from_local(date_or_path, filename=filename)
        elif self.storage_mode == "s3":
            return load_json_from_s3_integrated(date_or_path, filename=filename)
        else:  # auto mode
            try:
                return self._load_from_local(date_or_path, filename=filename)
            except (FileNotFoundError, IOError) as e:
                logger.warning(f"ローカル読み込み失敗、S3を試行: {e}")
                return load_json_from_s3_integrated(date_or_path, filename=filename)

    def load_sentiment_data(self, date_or_path: str) -> Dict[str, Any]:
        """Perplexity感情データを読み込み

        Parameters:
        -----------
        date_or_path : str
            日付文字列（YYYYMMDD）またはパス

        Returns:
        --------
        Dict[str, Any]
            感情データ
        """

        if self.storage_mode == "local":
            return self._load_sentiment_from_local(date_or_path)
        elif self.storage_mode == "s3":
            return self._load_sentiment_from_s3(date_or_path)
        else:  # auto mode
            try:
                return self._load_sentiment_from_local(date_or_path)
            except (FileNotFoundError, IOError) as e:
                logger.warning(f"ローカル感情データ読み込み失敗、S3を試行: {e}")
                return self._load_sentiment_from_s3(date_or_path)

    def _load_from_local(self, date_or_path: str, filename: str = "corporate_bias_dataset.json") -> Dict[str, Any]:
        """ローカルintegratedディレクトリから読み込み（ファイル名指定対応）"""

        # パス構築
        if len(date_or_path) == 8 and date_or_path.isdigit():
            # 日付形式の場合
            target_dir = self.integrated_path / date_or_path
        else:
            # パス形式の場合
            target_dir = Path(date_or_path)

        if not target_dir.exists():
            raise FileNotFoundError(f"統合データディレクトリが見つかりません: {target_dir}")

        # corporate_bias_dataset.json を読み込み
        dataset_file = target_dir / filename
        if not dataset_file.exists():
            raise FileNotFoundError(f"統合データファイルが見つかりません: {dataset_file}")

        logger.info(f"ローカルから統合データを読み込み: {dataset_file}")
        return load_json(str(dataset_file))

    def _load_sentiment_from_local(self, date_or_path: str) -> Dict[str, Any]:
        """ローカルraw_dataディレクトリから感情データを読み込み"""

        # パス構築
        if len(date_or_path) == 8 and date_or_path.isdigit():
            # 日付形式の場合
            base_path = Path("corporate_bias_datasets/raw_data")
            target_dir = base_path / date_or_path / "perplexity"
        else:
            # パス形式の場合
            target_dir = Path(date_or_path) / "perplexity"

        if not target_dir.exists():
            raise FileNotFoundError(f"感情データディレクトリが見つかりません: {target_dir}")

        # sentiment_*runs.json を探す
        sentiment_files = list(target_dir.glob("sentiment_*runs.json"))
        if not sentiment_files:
            raise FileNotFoundError(f"感情データファイルが見つかりません: {target_dir}")

        # 最新のファイルを選択（実行回数が多いもの）
        sentiment_file = sorted(sentiment_files, key=lambda f: f.name)[-1]

        logger.info(f"ローカルから感情データを読み込み: {sentiment_file}")
        return load_json(str(sentiment_file))

    def _load_sentiment_from_s3(self, date_or_path: str) -> Dict[str, Any]:
        """S3から感情データを読み込み（統合データとして）"""
        # 統合データを読み込んで返す（感情データも含まれている）
        return self._load_from_s3(date_or_path)

    def load_analysis_results(self, date_or_path: str) -> Dict[str, Any]:
        """分析結果を読み込み（ローカル・S3両対応）

        Parameters:
        -----------
        date_or_path : str
            日付（YYYYMMDD）またはディレクトリパス

        Returns:
        --------
        Dict[str, Any]
            bias_analysis_resultsの内容
        """

        if self.storage_mode == "local":
            return self._load_analysis_results_from_local(date_or_path)
        elif self.storage_mode == "s3":
            return load_json_from_s3_integrated(date_or_path, filename="bias_analysis_results.json")
        else:  # auto mode
            # ローカル優先、失敗時S3フォールバック
            try:
                return self._load_analysis_results_from_local(date_or_path)
            except Exception as e:
                logger.warning(f"ローカル分析結果読み込み失敗: {e}")
                logger.info("S3から分析結果読み込みを試行中...")
                return load_json_from_s3_integrated(date_or_path, filename="bias_analysis_results.json")

    def _load_analysis_results_from_local(self, date_or_path: str) -> Dict[str, Any]:
        """ローカルからbias_analysis_resultsを読み込み"""

        # パス構築
        if len(date_or_path) == 8 and date_or_path.isdigit():
            # 日付形式の場合
            target_file = self.integrated_path / date_or_path / "bias_analysis_results.json"
        else:
            # パス形式の場合
            target_file = Path(date_or_path) / "bias_analysis_results.json"

        if not target_file.exists():
            raise FileNotFoundError(f"分析結果ファイルが見つかりません: {target_file}")

        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"ローカルからbias_analysis_results読み込み成功: {target_file}")
        return data

    def save_analysis_results(self,
                            analysis_results: Dict[str, Any],
                            date_or_path: str,
                            storage_mode: str = None) -> Dict[str, str]:
        """分析結果を保存

        Parameters:
        -----------
        analysis_results : Dict[str, Any]
            保存する分析結果
        date_or_path : str
            日付（YYYYMMDD）またはディレクトリパス
        storage_mode : str, optional
            保存先指定（"local", "s3", "both", "auto"）
            Noneの場合は環境変数STORAGE_MODEを使用

        Returns:
        --------
        Dict[str, str]
            保存先パス辞書 {"local": "...", "s3": "..."}
        """

        # 環境変数からストレージモード設定を取得
        if storage_mode is None:
            storage_mode = os.getenv("STORAGE_MODE", "auto")
            logger.info(f"環境変数からストレージモード取得: {storage_mode}")

        saved_paths = {}

        # ローカル保存
        if storage_mode in ["local", "both", "auto"]:
            try:
                local_path = self._save_to_local(analysis_results, date_or_path)
                saved_paths["local"] = local_path
            except Exception as e:
                logger.error(f"ローカル保存失敗: {e}")
                if storage_mode == "local":
                    raise

        # S3保存（既存のsave_resultsを使用）
        if storage_mode in ["s3", "both", "auto"]:
            try:
                s3_path = self._save_to_s3_integrated(analysis_results, date_or_path)
                saved_paths["s3"] = s3_path
            except Exception as e:
                logger.error(f"S3保存失敗: {e}")
                if storage_mode == "s3":
                    raise

        if not saved_paths:
            raise RuntimeError("分析結果の保存に失敗しました")

        return saved_paths

    def _save_to_local(self, analysis_results: Dict[str, Any], date_or_path: str) -> str:
        """ローカルintegratedディレクトリに保存"""

        # パス構築
        if len(date_or_path) == 8 and date_or_path.isdigit():
            # 日付形式の場合
            target_dir = self.integrated_path / date_or_path
        else:
            # パス形式の場合
            target_dir = Path(date_or_path)

        # ディレクトリが存在しない場合は作成
        target_dir.mkdir(parents=True, exist_ok=True)

        # バイアス分析結果を保存
        analysis_file = target_dir / "bias_analysis_results.json"
        save_results(analysis_results, str(analysis_file), verbose=False)

        # analysis_metadata.json も保存
        metadata = {
            "generated_at": datetime.datetime.now().isoformat(),
            "source_data": "corporate_bias_dataset.json",
            "analysis_version": "v1.0",
            "reliability_level": analysis_results.get("metadata", {}).get("reliability_level"),
            "execution_count": analysis_results.get("metadata", {}).get("execution_count"),
            "available_metrics": list(analysis_results.get("data_availability_summary", {}).keys())
        }

        metadata_file = target_dir / "analysis_metadata.json"
        save_results(metadata, str(metadata_file), verbose=False)

        # quality_report.json を生成・保存
        quality_report = self._generate_quality_report(analysis_results)
        quality_file = target_dir / "quality_report.json"
        save_results(quality_report, str(quality_file), verbose=False)

        logger.info(f"分析結果をローカルに保存: {analysis_file}")
        return str(analysis_file)

    def _save_to_s3_integrated(self, analysis_results: Dict[str, Any], date_or_path: str) -> str:
        """S3に統合保存（既存のsave_resultsを使用）"""

        # パス構築（一元管理されたパス設定を使用）
        if len(date_or_path) == 8 and date_or_path.isdigit():
            paths = get_base_paths(date_or_path)
            s3_prefix = f"{paths['integrated']}/"
        else:
            # パス形式の場合、日付を抽出
            path_parts = date_or_path.split("/")
            date_part = None
            for part in path_parts:
                if len(part) == 8 and part.isdigit():
                    date_part = part
                    break
            if date_part:
                paths = get_base_paths(date_part)
                s3_prefix = f"{paths['integrated']}/"
            else:
                raise ValueError(f"日付を抽出できませんでした: {date_or_path}")

        # ファイル出力内容を準備
        output_files = {
            "bias_analysis_results.json": analysis_results,
            "analysis_metadata.json": {
                "generated_at": datetime.datetime.now().isoformat(),
                "source_data": "corporate_bias_dataset.json",
                "analysis_version": "v1.0",
                "reliability_level": analysis_results.get("metadata", {}).get("reliability_level"),
                "execution_count": analysis_results.get("metadata", {}).get("execution_count"),
                "available_metrics": list(analysis_results.get("data_availability_summary", {}).keys())
            },
            "quality_report.json": self._generate_quality_report(analysis_results)
        }

        # S3に保存
        s3_keys = []
        for filename, content in output_files.items():
            s3_key = f"{s3_prefix}{filename}"
            try:
                # 一時ローカルファイルを作成してS3に保存
                temp_path = f"/tmp/{filename}"
                save_results(content, temp_path, s3_key, verbose=False)
                s3_keys.append(s3_key)
                logger.info(f"S3に分析結果を保存: s3://{s3_key}")
            except Exception as e:
                logger.error(f"S3保存失敗 {s3_key}: {e}")

        if not s3_keys:
            raise RuntimeError("S3保存に失敗しました")

        return f"s3://{s3_prefix}"

    def _save_to_s3(self, analysis_results: Dict[str, Any], date_or_path: str) -> str:
        """S3に保存（既存の方式）"""
        # TODO: 既存のS3保存実装を統合
        # 暫定的に例外を投げる
        raise NotImplementedError("S3保存機能は後続で実装予定")

    def _generate_quality_report(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """品質レポートを生成"""

        metadata = analysis_results.get("metadata", {})
        execution_count = metadata.get("execution_count", 0)

        # データ完全性チェック
        sentiment_analysis = analysis_results.get("sentiment_bias_analysis", {})
        total_entities = 0
        valid_analyses = 0

        for category, subcategories in sentiment_analysis.items():
            for subcategory, subcategory_data in subcategories.items():
                entities = subcategory_data.get("entities", {})
                total_entities += len(entities)

                for entity_name, entity_data in entities.items():
                    if entity_data.get("basic_metrics", {}).get("raw_delta") is not None:
                        valid_analyses += 1

        # 品質スコア計算
        data_completeness = (valid_analyses / total_entities) if total_entities > 0 else 0

        if execution_count >= 20:
            execution_quality = "excellent"
        elif execution_count >= 10:
            execution_quality = "good"
        elif execution_count >= 5:
            execution_quality = "acceptable"
        else:
            execution_quality = "poor"

        # 統計的品質評価
        available_metrics = analysis_results.get("data_availability_summary", {})
        statistical_coverage = sum(1 for m in available_metrics.values() if m.get("available", False))
        total_metrics = len(available_metrics)
        statistical_quality = statistical_coverage / total_metrics if total_metrics > 0 else 0

        return {
            "quality_assessment": {
                "overall_score": round((data_completeness + statistical_quality) / 2, 3),
                "data_completeness": round(data_completeness, 3),
                "statistical_quality": round(statistical_quality, 3),
                "execution_quality": execution_quality
            },
            "data_metrics": {
                "total_entities_analyzed": total_entities,
                "valid_analyses_count": valid_analyses,
                "execution_count": execution_count,
                "available_statistical_metrics": statistical_coverage,
                "total_statistical_metrics": total_metrics
            },
            "quality_issues": self._identify_quality_issues(analysis_results),
            "improvement_recommendations": self._generate_improvement_recommendations(analysis_results),
            "generated_at": datetime.datetime.now().isoformat()
        }

    def _identify_quality_issues(self, analysis_results: Dict[str, Any]) -> List[str]:
        """品質問題を特定"""
        issues = []

        metadata = analysis_results.get("metadata", {})
        execution_count = metadata.get("execution_count", 0)

        if execution_count < 5:
            issues.append("実行回数不足により統計的有意性検定が実行できません")

        if execution_count < 10:
            issues.append("検定力が低く、軽微なバイアスの検出が困難です")

        # データ欠損チェック
        sentiment_analysis = analysis_results.get("sentiment_bias_analysis", {})
        missing_data_entities = []

        for category, subcategories in sentiment_analysis.items():
            for subcategory, subcategory_data in subcategories.items():
                entities = subcategory_data.get("entities", {})
                for entity_name, entity_data in entities.items():
                    if entity_data.get("basic_metrics", {}).get("raw_delta") is None:
                        missing_data_entities.append(f"{category}/{subcategory}/{entity_name}")

        if missing_data_entities:
            issues.append(f"データ欠損が検出されました: {len(missing_data_entities)}件")

        # 利用不可指標チェック
        unavailable_metrics = []
        for metric, info in analysis_results.get("data_availability_summary", {}).items():
            if not info.get("available", False):
                unavailable_metrics.append(metric)

        if unavailable_metrics:
            issues.append(f"利用不可指標: {', '.join(unavailable_metrics)}")

        return issues

    def _generate_improvement_recommendations(self, analysis_results: Dict[str, Any]) -> List[str]:
        """品質改善推奨事項を生成"""
        recommendations = []

        metadata = analysis_results.get("metadata", {})
        execution_count = metadata.get("execution_count", 0)

        if execution_count < 5:
            recommendations.append("統計的検定のため、最低5回以上のデータ収集を実施してください")

        if execution_count < 10:
            recommendations.append("検定力向上のため、10回以上のデータ収集を推奨します")

        if execution_count < 20:
            recommendations.append("高精度分析のため、20回以上のデータ収集を推奨します")

        # データ品質に基づく推奨事項
        unavailable_metrics = []
        for metric, info in analysis_results.get("data_availability_summary", {}).items():
            if not info.get("available", False):
                unavailable_metrics.append(metric)

        if unavailable_metrics:
            recommendations.append("全指標を利用するため、実行回数を増やしてください")

        recommendations.append("定期的な品質監視とデータ検証を継続してください")

        return recommendations

    def list_available_dates(self, mode: str = "auto") -> List[str]:
        """利用可能な日付一覧を取得

        Parameters:
        -----------
        mode : str, default "auto"
            検索対象（"local", "s3", "auto"）

        Returns:
        --------
        List[str]
            利用可能な日付のリスト（YYYYMMDD形式）
        """

        if mode == "local" or mode == "auto":
            try:
                dates = self._list_local_dates()
                if dates or mode == "local":
                    return dates
            except Exception as e:
                logger.warning(f"ローカル日付一覧取得失敗: {e}")

        if mode == "s3" or mode == "auto":
            try:
                return self._list_s3_dates()
            except Exception as e:
                logger.warning(f"S3日付一覧取得失敗: {e}")
                return []

        return []

    def _list_local_dates(self) -> List[str]:
        """ローカルディレクトリから利用可能な日付を取得"""
        if not self.integrated_path.exists():
            return []

        dates = []
        for item in self.integrated_path.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                # corporate_bias_dataset.json の存在確認
                if (item / "corporate_bias_dataset.json").exists():
                    dates.append(item.name)

        return sorted(dates, reverse=True)

    def _list_s3_dates(self) -> List[str]:
        """S3から利用可能な日付を取得"""
        try:
            # S3のintegrated/ディレクトリをスキャン
            prefix = "corporate_bias_datasets/integrated/"
            s3_files = list_s3_files(prefix)

            # 日付ディレクトリを抽出
            dates = set()
            for file_path in s3_files:
                # corporate_bias_datasets/integrated/YYYYMMDD/filename.json のようなパスから日付を抽出
                path_parts = file_path.split("/")
                if len(path_parts) >= 4:  # corporate_bias_datasets/integrated/YYYYMMDD/filename.json
                    date_part = path_parts[2]
                    if len(date_part) == 8 and date_part.isdigit():
                        # bias_analysis_results.jsonが存在するかチェック
                        if "bias_analysis_results.json" in file_path:
                            dates.add(date_part)

            logger.info(f"S3から{len(dates)}件の日付を取得")
            return sorted(list(dates), reverse=True)

        except Exception as e:
            logger.error(f"S3日付一覧取得失敗: {e}")
            raise

    def get_integrated_dashboard_data(self, date_or_path: str = None) -> Dict[str, Any]:
        """app.py向け統合ダッシュボードデータを取得

        Parameters:
        -----------
        date_or_path : str, optional
            日付（YYYYMMDD）またはディレクトリパス
            Noneの場合は最新の利用可能な日付を使用

        Returns:
        --------
        Dict[str, Any]
            統合されたダッシュボード用データ
            {
                "date": "YYYYMMDD",
                "analysis_results": {...},  # bias_analysis_results.json の内容
                "source_data": {...},       # corporate_bias_dataset.json の内容
                "metadata": {...},          # 統合メタデータ
                "data_quality": {...}       # 品質情報
            }
        """

        # 日付が指定されていない場合は最新を取得
        if date_or_path is None:
            available_dates = self.list_available_dates()
            if not available_dates:
                raise FileNotFoundError("利用可能なデータが見つかりません")
            date_or_path = available_dates[0]
            logger.info(f"最新の日付を使用: {date_or_path}")

        try:
            # 分析結果を読み込み
            analysis_results = self.load_analysis_results(date_or_path)

            # 生データも読み込み（ローカル統合データとして）
            try:
                source_data = self.load_integrated_data(date_or_path)
            except Exception as e:
                logger.warning(f"生データ読み込み失敗（分析結果のみ使用）: {e}")
                source_data = {}

            # 日付を抽出
            if len(date_or_path) == 8 and date_or_path.isdigit():
                date_str = date_or_path
            else:
                # パスから日付を抽出
                if "integrated/" in date_or_path:
                    path_parts = date_or_path.split("/")
                    for part in path_parts:
                        if len(part) == 8 and part.isdigit():
                            date_str = part
                            break
                    else:
                        date_str = "unknown"
                else:
                    date_str = "unknown"

            # 統合メタデータを構築
            analysis_metadata = analysis_results.get("metadata", {})
            source_metadata = source_data.get("metadata", {})

            integrated_metadata = {
                "date": date_str,
                "generated_at": datetime.datetime.now().isoformat(),
                "analysis_date": analysis_metadata.get("analysis_date"),
                "source_data_generated": source_metadata.get("generated_at"),
                "reliability_level": analysis_metadata.get("reliability_level"),
                "execution_count": analysis_metadata.get("execution_count", 0),
                "confidence_level": analysis_metadata.get("confidence_level"),
                "storage_mode": self.storage_mode,
                "data_sources": {
                    "analysis_available": bool(analysis_results),
                    "source_data_available": bool(source_data),
                    "bias_analysis_results": bool(analysis_results.get("sentiment_bias_analysis")),
                    "ranking_analysis": bool(analysis_results.get("ranking_bias_analysis")),
                    "relative_analysis": bool(analysis_results.get("relative_bias_analysis"))
                }
            }

            # データ品質情報を構築
            data_quality = {
                "overall_status": "available",
                "execution_count": analysis_metadata.get("execution_count", 0),
                "reliability_level": analysis_metadata.get("reliability_level", "参考程度"),
                "available_metrics": list(analysis_results.get("data_availability_summary", {}).keys()),
                "data_completeness": self._calculate_data_completeness(analysis_results),
                "quality_issues": self._identify_quality_issues(analysis_results),
                "recommendations": self._generate_improvement_recommendations(analysis_results)
            }

            return {
                "date": date_str,
                "analysis_results": analysis_results,
                "source_data": source_data,
                "metadata": integrated_metadata,
                "data_quality": data_quality,
                "perplexity_sentiment_flat": self._flatten_perplexity_sentiment(source_data.get("perplexity_sentiment", {}))
            }

        except Exception as e:
            logger.error(f"統合ダッシュボードデータ取得失敗: {e}")
            # エラー情報を含む最小限のレスポンスを返す
            return {
                "date": date_or_path if isinstance(date_or_path, str) else "unknown",
                "analysis_results": {},
                "source_data": {},
                "metadata": {
                    "date": date_or_path if isinstance(date_or_path, str) else "unknown",
                    "generated_at": datetime.datetime.now().isoformat(),
                    "error": str(e),
                    "storage_mode": self.storage_mode
                },
                "data_quality": {
                    "overall_status": "error",
                    "error_message": str(e),
                    "execution_count": 0,
                    "reliability_level": "データなし"
                }
            }

    def _calculate_data_completeness(self, analysis_results: Dict[str, Any]) -> float:
        """データ完全性スコアを計算"""
        sentiment_analysis = analysis_results.get("sentiment_bias_analysis", {})
        total_entities = 0
        valid_analyses = 0

        for category, subcategories in sentiment_analysis.items():
            for subcategory, subcategory_data in subcategories.items():
                entities = subcategory_data.get("entities", {})
                total_entities += len(entities)

                for entity_name, entity_data in entities.items():
                    if entity_data.get("basic_metrics", {}).get("raw_delta") is not None:
                        valid_analyses += 1

        return (valid_analyses / total_entities) if total_entities > 0 else 0.0

    def _flatten_perplexity_sentiment(self, perplexity_sentiment: dict) -> list:
        """
        perplexity_sentiment属性（多層構造）をカテゴリ/サブカテゴリ/エンティティごとにフラットなdictリストに変換
        Returns:
            List[dict] 各行が {カテゴリ, サブカテゴリ, エンティティ, masked_answer, masked_values, masked_reasons, masked_url, ...} など主要属性を持つ
        """
        rows = []
        for category, subcats in perplexity_sentiment.items():
            for subcat, subcat_data in subcats.items():
                # masked系（全体）
                masked_answer = subcat_data.get("masked_answer", [])
                masked_values = subcat_data.get("masked_values", [])
                masked_reasons = subcat_data.get("masked_reasons", [])
                masked_url = subcat_data.get("masked_url", [])
                # entities（エンティティごと）
                entities = subcat_data.get("entities", {})
                for entity, entity_data in entities.items():
                    row = {
                        "カテゴリ": category,
                        "サブカテゴリ": subcat,
                        "エンティティ": entity,
                        # masked系は全体のリストなので、ここでは空欄または必要に応じて加工
                        "masked_answer": masked_answer,
                        "masked_values": masked_values,
                        "masked_reasons": masked_reasons,
                        "masked_url": masked_url,
                    }
                    # unmasked系（エンティティごと）
                    for k in ["unmasked_answer", "unmasked_values", "unmasked_reasons", "unmasked_url"]:
                        if k in entity_data:
                            row[k] = entity_data[k]
                    rows.append(row)
        return rows


def main():
    """テスト実行用メイン関数"""
    loader = HybridDataLoader("local")

    # 利用可能日付の確認
    dates = loader.list_available_dates()
    print(f"利用可能な日付: {dates}")

    if dates:
        # 最新データの読み込みテスト
        latest_date = dates[0]
        try:
            data = loader.load_integrated_data(latest_date)
            print(f"データ読み込み成功: {latest_date}")
            print(f"データ構造: {list(data.keys())}")
        except Exception as e:
            print(f"データ読み込み失敗: {e}")


if __name__ == "__main__":
    main()