"""
統合データセット作成メインモジュール

複数APIの生データを統合し、品質チェックを行い、
統合データセットと関連メタデータを生成する。
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import copy

from .data_validator import DataValidator, ProcessingAbortedException
from .schema_generator import SchemaGenerator
from ..utils.storage_utils import save_results
from ..utils.storage_config import get_base_paths, get_s3_key

logger = logging.getLogger(__name__)


class DatasetIntegrator:
    """統合データセット作成クラス"""

    def __init__(self, date_str: str):
        self.date_str = date_str
        self.validator = DataValidator()
        self.schema_generator = SchemaGenerator()

        # 出力パス設定
        self.paths = get_base_paths(date_str)
        self.integrated_dir = self.paths["integrated"]

        # 統合データセット用ディレクトリ作成
        os.makedirs(self.integrated_dir, exist_ok=True)

        # 処理結果記録
        self.integration_metadata = {
            "start_time": None,
            "end_time": None,
            "input_files": [],
            "processing_summary": {},
            "validation_results": [],
            "schema_info": {},
            "data_quality_score": 0.0
        }

    def create_integrated_dataset(self, force_recreate: bool = False, verbose: bool = True, runs: int = None) -> Dict[str, Any]:
        """統合データセット作成メイン処理"""
        self.integration_metadata["start_time"] = datetime.now().isoformat()

        if verbose:
            logger.info(f"統合データセット作成開始: {self.date_str}")

        try:
            # 1. 生データの読み込み
            raw_data = self._load_raw_data(verbose, runs)
            if not raw_data:
                logger.error("読み込み可能な生データが見つかりません")
                return {}

            # 2. データ品質チェックと処理継続制御
            if verbose:
                logger.info("データ品質チェック実行中...")
                logger.info(f"生データのキー: {list(raw_data.keys())}")

            try:
                cleaned_data, validation_results = self.validator.process_data_with_validation(raw_data)
                self.integration_metadata["validation_results"] = validation_results
                self.integration_metadata["data_quality_score"] = self.validator.get_validation_summary().get("validation_score", 0.0)

                if verbose:
                    logger.info(f"検証後のデータキー: {list(cleaned_data.keys())}")
                    logger.info(f"検証結果: {len(validation_results)}件")

                if verbose:
                    validation_summary = self.validator.get_validation_summary()
                    logger.info(f"品質チェック完了 - スコア: {validation_summary.get('validation_score', 0.0):.2f}, "
                               f"エラー: {validation_summary.get('errors', 0)}件, "
                               f"警告: {validation_summary.get('warnings', 0)}件")

            except ProcessingAbortedException as e:
                logger.critical(f"致命的エラーにより処理を中断します: {e}")
                self.integration_metadata["processing_summary"]["status"] = "ABORTED"
                return {}

            # 3. 統合データセット作成
            if verbose:
                logger.info("統合データセット作成中...")

            integrated_dataset = self._create_integrated_structure(cleaned_data)

            # 4. スキーマ生成（変更検知ベース）
            if verbose:
                logger.info("データセットスキーマ生成チェック中...")

            if self._should_regenerate_schema(integrated_dataset):
                if verbose:
                    logger.info("データ構造の変化を検知 - スキーマを再生成します")
                dataset_schema = self.schema_generator.generate_schema(integrated_dataset)
                schema_regenerated = True
            else:
                if verbose:
                    logger.info("データ構造に変化なし - 既存スキーマを使用します")
                dataset_schema = self._load_existing_schema()
                schema_regenerated = False

            self.integration_metadata["schema_info"] = {
                "field_count": dataset_schema["metadata"]["field_count"],
                "record_count": dataset_schema["metadata"]["record_count"],
                "data_sources": dataset_schema["metadata"]["data_sources"],
                "schema_regenerated": schema_regenerated
            }

            # 5. 統合データセットとメタデータの保存
            if verbose:
                logger.info("ファイル保存中...")

            self._save_integrated_files(integrated_dataset, dataset_schema, verbose)

            # 6. 収集サマリー生成
            collection_summary = self._create_collection_summary(raw_data, cleaned_data)
            self._save_collection_summary(collection_summary)

            # 7. データ品質情報は統合メタデータに含まれるため個別レポートは不要

            self.integration_metadata["end_time"] = datetime.now().isoformat()
            self.integration_metadata["processing_summary"]["status"] = "COMPLETED"

            if verbose:
                logger.info(f"統合データセット作成完了: {self.integrated_dir}/corporate_bias_dataset.json")
                logger.info(f"処理時間: {self._calculate_processing_time():.2f}秒")

            return integrated_dataset

        except Exception as e:
            logger.error(f"統合データセット作成中にエラーが発生しました: {e}")
            self.integration_metadata["end_time"] = datetime.now().isoformat()
            self.integration_metadata["processing_summary"]["status"] = "ERROR"
            raise

    def _extract_run_number(self, filename: str, prefix: str) -> int:
        """ファイル名からrun数を抽出

        Args:
            filename: ファイル名（例: "sentiment_5runs.json"）
            prefix: プレフィックス（例: "sentiment_"）

        Returns:
            run数（抽出できない場合は0）
        """
        try:
            # prefix_Nruns.jsonからNを抽出
            if filename.startswith(prefix) and filename.endswith("runs.json"):
                run_part = filename[len(prefix):-9]  # "runs.json"を除去
                return int(run_part)
        except (ValueError, IndexError):
            pass
        return 0

    def _find_latest_run_file(self, directory: str, prefix: str) -> Optional[str]:
        """指定ディレクトリで最新のrunファイルを取得

        Args:
            directory: 検索対象ディレクトリ
            prefix: ファイル名プレフィックス（例: "sentiment_"）

        Returns:
            最新（最大run数）のファイルパス、見つからない場合はNone
        """
        if not os.path.exists(directory):
            return None

        max_runs = 0
        latest_file = None

        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith("runs.json"):
                run_count = self._extract_run_number(filename, prefix)
                if run_count > max_runs:
                    max_runs = run_count
                    latest_file = filename

        return os.path.join(directory, latest_file) if latest_file else None

    def _load_raw_data(self, verbose: bool = True, runs: int = None) -> Dict[str, Any]:
        from src.utils.storage_utils import load_json
        from src.utils.storage_config import get_s3_key
        import glob
        raw_data = {}

        # Google検索データ
        google_local = os.path.join(self.paths["raw_data"]["google"], "custom_search.json")
        google_data = None
        found_local = os.path.exists(google_local)
        found_s3 = False
        google_s3 = get_s3_key("custom_search.json", self.date_str, "raw_data/google")
        # ローカルはcustom_search.jsonのみ
        if found_local:
            google_data = load_json(google_local, None)
        # S3 fallback: custom_search.json
        if not google_data:
            google_data = load_json(None, google_s3)
            if google_data:
                found_s3 = True
        if google_data:
            raw_data["google_data"] = google_data
            self.integration_metadata["input_files"].append(google_local)
            if verbose:
                logger.info(f"Google検索データを読み込みました: {google_local} または S3:{google_s3}")
        else:
            if verbose:
                if found_local:
                    logger.error(f"Googleデータがローカルに存在するが読み込み失敗: {google_local}")
                elif found_s3:
                    logger.warning(f"Googleデータがローカルに存在しませんが、S3から取得しました")
                else:
                    logger.warning(f"Googleデータがローカル・S3ともに取得できません: {google_local} / S3:{google_s3}")

        # Perplexity感情データ
        sentiment_local = os.path.join(self.paths["raw_data"]["perplexity"], "sentiment.json")
        sentiment_data = None
        found_local = os.path.exists(sentiment_local)
        found_s3 = False
        sentiment_s3 = get_s3_key("sentiment.json", self.date_str, "raw_data/perplexity")
        # ローカル: sentiment_{runs}runs.json → sentiment.json
        if runs is not None:
            sentiment_local_runs = os.path.join(self.paths["raw_data"]["perplexity"], f"sentiment_{runs}runs.json")
            exists_local_runs = os.path.exists(sentiment_local_runs)
            if exists_local_runs:
                sentiment_data = load_json(sentiment_local_runs, None)
        if not sentiment_data and found_local:
            sentiment_data = load_json(sentiment_local, None)
        # S3: runs付き優先
        if not sentiment_data and runs is not None:
            sentiment_s3_runs = get_s3_key(f"sentiment_{runs}runs.json", self.date_str, "raw_data/perplexity")
            sentiment_data = load_json(None, sentiment_s3_runs)
            if sentiment_data:
                found_s3 = True
        # S3 fallback: sentiment.json
        if not sentiment_data:
            sentiment_data = load_json(None, sentiment_s3)
            if sentiment_data:
                found_s3 = True
        if sentiment_data:
            raw_data["perplexity_sentiment"] = sentiment_data
            self.integration_metadata["input_files"].append(sentiment_local)
            if verbose:
                logger.info(f"Perplexity感情データを読み込みました: {sentiment_local} または S3:{sentiment_s3}")
        else:
            if verbose:
                if found_local:
                    logger.error(f"Perplexity感情データがローカルに存在するが読み込み失敗: {sentiment_local}")
                elif found_s3:
                    logger.warning(f"Perplexity感情データがローカルに存在しませんが、S3から取得しました")
                else:
                    logger.warning(f"Perplexity感情データがローカル・S3ともに取得できません: {sentiment_local} / S3:{sentiment_s3}")

        # Perplexityランキングデータ
        rankings_local = os.path.join(self.paths["raw_data"]["perplexity"], "rankings.json")
        rankings_data = None
        found_local = os.path.exists(rankings_local)
        found_s3 = False
        rankings_s3 = get_s3_key("rankings.json", self.date_str, "raw_data/perplexity")
        # ローカル: rankings_{runs}runs.json → rankings.json
        if runs is not None:
            rankings_local_runs = os.path.join(self.paths["raw_data"]["perplexity"], f"rankings_{runs}runs.json")
            exists_local_runs = os.path.exists(rankings_local_runs)
            if exists_local_runs:
                rankings_data = load_json(rankings_local_runs, None)
        if not rankings_data and found_local:
            rankings_data = load_json(rankings_local, None)
        # S3: runs付き優先
        if not rankings_data and runs is not None:
            rankings_s3_runs = get_s3_key(f"rankings_{runs}runs.json", self.date_str, "raw_data/perplexity")
            rankings_data = load_json(None, rankings_s3_runs)
            if rankings_data:
                found_s3 = True
        # S3 fallback: rankings.json
        if not rankings_data:
            rankings_data = load_json(None, rankings_s3)
            if rankings_data:
                found_s3 = True
        if rankings_data:
            raw_data["perplexity_rankings"] = rankings_data
            self.integration_metadata["input_files"].append(rankings_local)
            if verbose:
                logger.info(f"Perplexityランキングデータを読み込みました: {rankings_local} または S3:{rankings_s3}")
        else:
            if verbose:
                if found_local:
                    logger.error(f"Perplexityランキングデータがローカルに存在するが読み込み失敗: {rankings_local}")
                elif found_s3:
                    logger.warning(f"Perplexityランキングデータがローカルに存在しませんが、S3から取得しました")
                else:
                    logger.warning(f"Perplexityランキングデータがローカル・S3ともに取得できません: {rankings_local} / S3:{rankings_s3}")

        # Perplexity引用データ
        citations_local = os.path.join(self.paths["raw_data"]["perplexity"], "citations.json")
        citations_data = None
        found_local = os.path.exists(citations_local)
        found_s3 = False
        citations_s3 = get_s3_key("citations.json", self.date_str, "raw_data/perplexity")
        # ローカル: citations_{runs}runs.json → citations.json
        if runs is not None:
            citations_local_runs = os.path.join(self.paths["raw_data"]["perplexity"], f"citations_{runs}runs.json")
            exists_local_runs = os.path.exists(citations_local_runs)
            if exists_local_runs:
                citations_data = load_json(citations_local_runs, None)
        if not citations_data and found_local:
            citations_data = load_json(citations_local, None)
        # S3: runs付き優先
        if not citations_data and runs is not None:
            citations_s3_runs = get_s3_key(f"citations_{runs}runs.json", self.date_str, "raw_data/perplexity")
            citations_data = load_json(None, citations_s3_runs)
            if citations_data:
                found_s3 = True
        # S3 fallback: citations.json
        if not citations_data:
            citations_data = load_json(None, citations_s3)
            if citations_data:
                found_s3 = True
        if citations_data:
            raw_data["perplexity_citations"] = citations_data
            self.integration_metadata["input_files"].append(citations_local)
            if verbose:
                logger.info(f"Perplexity引用データを読み込みました: {citations_local} または S3:{citations_s3}")
        else:
            if verbose:
                if found_local:
                    logger.error(f"Perplexity引用データがローカルに存在するが読み込み失敗: {citations_local}")
                elif found_s3:
                    logger.warning(f"Perplexity引用データがローカルに存在しませんが、S3から取得しました")
                else:
                    logger.warning(f"Perplexity引用データがローカル・S3ともに取得できません: {citations_local} / S3:{citations_s3}")

        return raw_data

    def _create_integrated_structure(self, cleaned_data: Dict[str, Any]) -> Dict[str, Any]:
        """統合データ構造の作成"""
        integrated_dataset = {
            "metadata": {
                "dataset_name": "Corporate Bias Integrated Dataset",
                "version": "1.0",
                "created_at": datetime.now().isoformat(),
                "collection_date": self.date_str,
                "description": "企業優遇バイアス研究用の統合データセット（生データのみ）",
                "data_sources": list(cleaned_data.keys()),
                "api_neutral_structure": True,
                "research_ready": True
            }
        }

        # 各データソースをそのまま統合（生データとして保持）
        for data_type, data_content in cleaned_data.items():
            integrated_dataset[data_type] = data_content

        return integrated_dataset

    def _save_integrated_files(self, integrated_dataset: Dict[str, Any], dataset_schema: Dict[str, Any], verbose: bool = True):
        """統合データセットとスキーマの保存"""
        # メインの統合データセット保存
        dataset_path = os.path.join(self.integrated_dir, "corporate_bias_dataset.json")
        dataset_s3_key = get_s3_key("corporate_bias_dataset.json", self.date_str, "integrated")
        save_results(integrated_dataset, dataset_path, dataset_s3_key, verbose)

        # スキーマ保存（再生成された場合のみ）
        schema_regenerated = self.integration_metadata.get("schema_info", {}).get("schema_regenerated", True)
        if schema_regenerated:
            schema_path = os.path.join(self.integrated_dir, "dataset_schema.json")
            schema_s3_key = get_s3_key("dataset_schema.json", self.date_str, "integrated")
            save_results(dataset_schema, schema_path, schema_s3_key, verbose)
            if verbose:
                logger.info(f"スキーマ保存: {schema_path}")
        else:
            if verbose:
                logger.info("スキーマは既存ファイルを使用（保存をスキップ）")

        # 統合メタデータ保存（品質情報も含む）
        comprehensive_metadata = self._create_comprehensive_metadata()
        metadata_path = os.path.join(self.integrated_dir, "integration_metadata.json")
        metadata_s3_key = get_s3_key("integration_metadata.json", self.date_str, "integrated")
        save_results(comprehensive_metadata, metadata_path, metadata_s3_key, verbose)

        if verbose:
            logger.info(f"統合データセット保存: {dataset_path}")
            logger.info(f"統合メタデータ保存: {metadata_path}")

    def _create_comprehensive_metadata(self) -> Dict[str, Any]:
        """統合メタデータの作成（品質情報も含む包括的版）"""
        validation_summary = self.validator.get_validation_summary()

        comprehensive_metadata = {
            "processing_metadata": {
                "start_time": self.integration_metadata["start_time"],
                "end_time": self.integration_metadata["end_time"],
                "processing_time_seconds": self._calculate_processing_time(),
                "input_files": self.integration_metadata["input_files"],
                "processing_summary": self.integration_metadata.get("processing_summary", {}),
                "schema_info": self.integration_metadata.get("schema_info", {})
            },
            "data_quality": {
                "report_created_at": datetime.now().isoformat(),
                "collection_date": self.date_str,
                "overall_quality_score": validation_summary.get("validation_score", 0.0),
                "quality_assessment": "EXCELLENT" if validation_summary.get("validation_score", 0.0) >= 0.95 else
                                     "GOOD" if validation_summary.get("validation_score", 0.0) >= 0.80 else
                                     "ACCEPTABLE" if validation_summary.get("validation_score", 0.0) >= 0.60 else
                                     "POOR",
                "validation_summary": validation_summary,
                "detailed_checks": self.integration_metadata.get("validation_results", []),
                "recommendations": self._generate_recommendations(validation_summary)
            }
        }

        return comprehensive_metadata

    def _generate_recommendations(self, validation_summary: Dict[str, Any]) -> List[str]:
        """推奨事項の生成"""
        recommendations = []

        if validation_summary.get("critical_errors", 0) > 0:
            recommendations.append("致命的エラーが検出されました。データ収集プロセスの緊急確認が必要です。")

        if validation_summary.get("errors", 0) > 0:
            recommendations.append(f"{validation_summary['errors']}件のエラーによりデータが除外されました。")

        if validation_summary.get("warnings", 0) > 0:
            recommendations.append(f"{validation_summary['warnings']}件の品質注意があります。分析時に注意してください。")

        if validation_summary.get("validation_score", 0.0) >= 0.95:
            recommendations.append("高品質なデータセットです。研究・分析に適用可能です。")

        return recommendations

    def _create_collection_summary(self, raw_data: Dict[str, Any], cleaned_data: Dict[str, Any]) -> Dict[str, Any]:
        """収集サマリーの作成"""
        summary = {
            "collection_date": self.date_str,
            "summary_created_at": datetime.now().isoformat(),
            "data_sources": {
                "available": list(raw_data.keys()),
                "processed": list(cleaned_data.keys()),
                "excluded": list(set(raw_data.keys()) - set(cleaned_data.keys()))
            },
            "record_counts": {},
            "coverage_analysis": {},
            "data_completeness": {}
        }

        # 各データソースのレコード数カウント
        for data_type, data_content in cleaned_data.items():
            if data_type == "google_data":
                total_results = 0
                entity_count = 0
                for category_data in data_content.values():
                    for subcategory_data in category_data.values():
                        if "entities" in subcategory_data:
                            for entity_data in subcategory_data["entities"].values():
                                entity_count += 1
                                total_results += len(entity_data.get("official_results", []))
                                total_results += len(entity_data.get("reputation_results", []))

                summary["record_counts"]["google_search_results"] = total_results
                summary["record_counts"]["google_entities"] = entity_count

            elif data_type == "perplexity_sentiment":
                category_count = 0
                score_count = 0
                for category_data in data_content.values():
                    for subcategory_data in category_data.values():
                        category_count += 1
                        score_count += len(subcategory_data.get("masked_values", []))
                        if "unmasked_values" in subcategory_data:
                            for entity_scores in subcategory_data["unmasked_values"].values():
                                score_count += len(entity_scores)

                summary["record_counts"]["sentiment_categories"] = category_count
                summary["record_counts"]["sentiment_scores"] = score_count

        return summary

    def _save_collection_summary(self, summary: Dict[str, Any]):
        """収集サマリーの保存"""
        summary_path = os.path.join(self.integrated_dir, "collection_summary.json")
        summary_s3_key = get_s3_key("collection_summary.json", self.date_str, "integrated")
        save_results(summary, summary_path, summary_s3_key, verbose=True)
        logger.info(f"収集サマリー保存: {summary_path}")

    def _calculate_processing_time(self) -> float:
        """処理時間の計算"""
        if self.integration_metadata["start_time"] and self.integration_metadata["end_time"]:
            start = datetime.fromisoformat(self.integration_metadata["start_time"])
            end = datetime.fromisoformat(self.integration_metadata["end_time"])
            return (end - start).total_seconds()
        return 0.0

    def get_integration_metadata(self) -> Dict[str, Any]:
        """統合処理メタデータの取得"""
        return self.integration_metadata

    def list_output_files(self) -> List[str]:
        """生成されたファイルのリストを取得"""
        output_files = []

        files_to_check = [
            "corporate_bias_dataset.json",
            "dataset_schema.json",
            "collection_summary.json",
            "integration_metadata.json"
        ]

        for filename in files_to_check:
            filepath = os.path.join(self.integrated_dir, filename)
            if os.path.exists(filepath):
                output_files.append(filepath)

        return output_files

    def _should_regenerate_schema(self, integrated_dataset: Dict[str, Any]) -> bool:
        """スキーマの再生成が必要かチェック"""
        schema_path = os.path.join(self.integrated_dir, "dataset_schema.json")

        # ファイルが存在しない場合は生成が必要
        if not os.path.exists(schema_path):
            logger.info("既存スキーマファイルが見つかりません - 新規生成します")
            return True

        try:
            existing_schema = self._load_existing_schema()

            # データソースの変化検知
            current_sources = set(integrated_dataset.keys()) - {"metadata"}  # metadata除外
            schema_sources = set(existing_schema.get("properties", {}).keys())

            if current_sources != schema_sources:
                logger.info(f"データソースの変化を検知: {schema_sources} → {current_sources}")
                return True

            # 各データソース内の構造変化検知（簡易版）
            for source in current_sources:
                if source in integrated_dataset:
                    current_structure = self._get_data_structure_signature(integrated_dataset[source])

                    # 既存スキーマから期待される構造を取得
                    if "properties" in existing_schema and source in existing_schema["properties"]:
                        expected_structure = self._get_schema_structure_signature(existing_schema["properties"][source])

                        # デバッグログ追加
                        logger.debug(f"{source} - 現在の構造: {current_structure}")
                        logger.debug(f"{source} - 期待される構造: {expected_structure}")

                        if current_structure != expected_structure:
                            logger.info(f"{source}のデータ構造変化を検知")
                            logger.info(f"  現在: {current_structure}")
                            logger.info(f"  期待: {expected_structure}")
                            return True

            logger.info("データ構造に変化は検知されませんでした")
            return False

        except Exception as e:
            logger.warning(f"スキーマ変更検知中にエラー: {e} - 安全のため再生成します")
            return True

    def _load_existing_schema(self) -> Dict[str, Any]:
        """既存のスキーマファイルを読み込み"""
        schema_path = os.path.join(self.integrated_dir, "dataset_schema.json")

        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"既存スキーマの読み込みに失敗: {e}")
            raise

    def _get_data_structure_signature(self, data: Any, max_depth: int = 2) -> str:
        """データ構造のシグネチャを生成（変更検知用）- 構造のみに焦点、値の変化は無視"""
        if max_depth <= 0:
            return "deep"

        if isinstance(data, dict):
            if not data:
                return "empty_dict"

            # 辞書のキー構造のみチェック（値の内容は無視）
            keys = sorted(data.keys())
            return f"dict[{','.join(keys)}]"

        elif isinstance(data, list):
            if not data:
                return "empty_list"

            # リストの最初の要素の型のみチェック（構造のみ）
            first_item = data[0]
            if isinstance(first_item, dict):
                return "list[dict]"
            elif isinstance(first_item, list):
                return "list[list]"
            else:
                return f"list[{type(first_item).__name__}]"

        else:
            return type(data).__name__

    def _get_schema_structure_signature(self, schema: Dict[str, Any]) -> str:
        """スキーマからデータ構造シグネチャを推測"""
        if "type" not in schema:
            return "unknown"

        schema_type = schema["type"]

        if schema_type == "object":
            if "properties" in schema:
                prop_keys = sorted(schema["properties"].keys())
                return f"dict[{','.join(prop_keys)}]"
            elif "patternProperties" in schema:
                return "dict[pattern]"
            else:
                return "empty_dict"

        elif schema_type == "array":
            if "items" in schema and isinstance(schema["items"], dict):
                item_type = schema["items"].get("type", "unknown")
                if item_type == "object":
                    return "list[dict]"
                else:
                    return f"list[{item_type}]"
            else:
                return "list[unknown]"
        else:
            return schema_type