"""
データ品質チェックモジュール

統合データセット作成時の品質チェック機能を提供。
エラー重要度に応じた処理継続制御を実装。
"""

import json
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import copy

logger = logging.getLogger(__name__)


class ProcessingAbortedException(Exception):
    """致命的エラーによる処理中断例外"""
    pass


class DataValidator:
    """データ品質チェッククラス"""

    # 必須フィールド定義
    REQUIRED_FIELDS = {
        "google_data": {
            "entities": "required",
            "entities.*.official_results": "required",
            "entities.*.reputation_results": "required",
            "official_results.*.rank": ["required", "positive_integer"],
            "official_results.*.domain": ["required", "non_empty_string"],
            "reputation_results.*.rank": ["required", "positive_integer"],
            "reputation_results.*.domain": ["required", "non_empty_string"]
        },

        "perplexity_sentiment": {
            "masked_values": "required",
            "masked_avg": "required",
            "unmasked_values": "required",
            "unmasked_avg": "required",
            "masked_answer": "required",
            "unmasked_values.*": ["required", "numeric_list"]
        },

        "perplexity_rankings": {
            "services": "required",
            "ranking_summary": "required",
            "response_list": "required",
            "ranking_summary.*.average_rank": ["required", "positive_number"],
            "response_list.*.extracted_ranking": "required"
        },

        "perplexity_citations": {
            "entities.*.official_results": "required",
            "entities.*.reputation_results": "required",
            "official_results.*.url": ["required", "valid_url"],
            "reputation_results.*.url": ["required", "valid_url"]
        }
    }

    # 値制約定義
    VALUE_CONSTRAINTS = {
        "sentiment_score": {"min": 1.0, "max": 5.0},
        "rank": {"min": 1, "max": 100},
        "bias_index": {"min": -10.0, "max": 10.0},
        "url_pattern": r"^https?://[^\s/$.?#].[^\s]*$",
        "domain_pattern": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "title_max_length": 500,
        "snippet_max_length": 1000,
        "non_empty_strings": ["title", "snippet", "domain", "answer"]
    }

    # エラーメッセージテンプレート
    ERROR_MESSAGES = {
        "CRITICAL": {
            "CRIT_001": "JSONファイルが読み込めません: {details}",
            "CRIT_002": "必須カテゴリが完全に欠損しています: {details}",
            "CRIT_003": "データ構造が根本的に異なります: {details}",
            "CRIT_004": "メモリ不足により処理を継続できません: {details}"
        },
        "ERROR": {
            "REQ_G001": "必須フィールド 'entities' が存在しません - {path}",
            "REQ_G002": "必須フィールド 'official_results' が存在しません - {path}",
            "REQ_G003": "必須フィールド 'rank' が存在しません - {path}",
            "REQ_G004": "必須フィールド 'domain' が存在しません - {path}",
            "VAL_G001": "rankは1以上の整数である必要があります: rank={actual} - {path}",
            "VAL_G002": "domainは空文字列であってはいけません - {path}",
            "REQ_S001": "必須フィールド 'masked_values' が存在しません - {path}",
            "REQ_S002": "必須フィールド 'unmasked_values' が存在しません - {path}",
            "VAL_S001": "masked_valuesはリストである必要があります: 実際の型={actual} - {path}",
            "VAL_S002": "masked_values[{index}]は数値である必要があります: 実際の値={actual} - {path}",
            "VAL_S003": "masked_values[{index}]は1.0-5.0の範囲である必要があります: 実際の値={actual} - {path}",
            "VAL_S004": "unmasked_valuesは辞書である必要があります: 実際の型={actual} - {path}",
            "VAL_S005": "企業スコアはリストである必要があります: 実際の型={actual} - {path}",
            "VAL_S006": "スコア[{index}]は数値である必要があります: 実際の値={actual} - {path}",
            "VAL_S007": "スコア[{index}]は1.0-5.0の範囲である必要があります: 実際の値={actual} - {path}",
            "REQ_R001": "必須フィールド '{field}' が存在しません - {path}",
            "FMT_001": "不正な形式です: {field}={actual}, 期待形式={pattern} - {path}",
            "REQ_G005": "感情分析結果 'sentiment' が存在しません - {path}",
            "REQ_C005": "感情分析結果 'sentiment' が存在しません - {path}",
        },
        "WARNING": {
            "QUA_001": "品質注意: {field}が空文字列です - {path}",
            "QUA_002": "品質注意: URLにアクセスできません - {url}",
            "QUA_003": "品質注意: 異常値の可能性があります: {field}={actual} - {path}",
            "QUA_004": "品質注意: 推奨されない値です: {field}={actual} - {path}"
        }
    }

    def __init__(self):
        self.validation_results = []
        self.category_summary = {}

    def validate_all_data(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """全データの品質チェックを実行"""
        self.validation_results = []
        self.category_summary = {}

        logger.info("データ統合品質チェック開始")

        # 各データタイプの検証
        if "google_data" in raw_data:
            logger.info("CHK_001: チェック開始: Google検索データ検証")
            google_errors = self.validate_google_data(raw_data["google_data"])
            self.validation_results.extend(google_errors)
            logger.info(f"CHK_002: チェック完了: Google検索データ検証 - エラー: {len(google_errors)}件")

        if "perplexity_sentiment" in raw_data:
            logger.info("CHK_001: チェック開始: Perplexity感情データ検証")
            sentiment_errors = self.validate_perplexity_sentiment(raw_data["perplexity_sentiment"])
            self.validation_results.extend(sentiment_errors)
            logger.info(f"CHK_002: チェック完了: Perplexity感情データ検証 - エラー: {len(sentiment_errors)}件")

        if "perplexity_rankings" in raw_data:
            logger.info("CHK_001: チェック開始: Perplexityランキングデータ検証")
            ranking_errors = self.validate_perplexity_rankings(raw_data["perplexity_rankings"])
            self.validation_results.extend(ranking_errors)
            logger.info(f"CHK_002: チェック完了: Perplexityランキングデータ検証 - エラー: {len(ranking_errors)}件")

        if "perplexity_citations" in raw_data:
            logger.info("CHK_001: チェック開始: Perplexity引用データ検証")
            citation_errors = self.validate_perplexity_citations(raw_data["perplexity_citations"])
            self.validation_results.extend(citation_errors)
            logger.info(f"CHK_002: チェック完了: Perplexity引用データ検証 - エラー: {len(citation_errors)}件")

        # サマリー作成
        self._create_validation_summary()

        return self.validation_results

    def validate_google_data(self, data: Dict[str, Any], path: str = "google_data") -> List[Dict[str, Any]]:
        """Google検索データの検証"""
        errors = []

        # 実際のデータ構造に合わせて検証: カテゴリ.サブカテゴリ.entities
        for category, subcategories in data.items():
            category_path = f"{path}.{category}"

            for subcategory, subdata in subcategories.items():
                subdata_path = f"{category_path}.{subcategory}"

                # entities構造の存在チェック
                if "entities" not in subdata:
                    errors.append(self._create_error("REQ_G001", "ERROR", path=subdata_path))
                    continue

                # 各企業データのチェック
                for entity_name, entity_data in subdata["entities"].items():
                    entity_path = f"{subdata_path}.entities.{entity_name}"

                    # official_results チェック
                    if "official_results" not in entity_data:
                        errors.append(self._create_error("REQ_G002", "ERROR", path=entity_path))
                    else:
                        for i, result in enumerate(entity_data["official_results"]):
                            result_path = f"{entity_path}.official_results[{i}]"
                            errors.extend(self._validate_search_result(result, result_path))
                            # official_resultsはsentimentチェック不要

                    # reputation_results チェック
                    if "reputation_results" not in entity_data:
                        errors.append(self._create_error("REQ_G002", "ERROR",
                                                        field="reputation_results", path=entity_path))
                    else:
                        for i, result in enumerate(entity_data["reputation_results"]):
                            result_path = f"{entity_path}.reputation_results[{i}]"
                            errors.extend(self._validate_search_result(result, result_path))
                            # 感情分析済みチェック（reputation_resultsのみ）
                            if "sentiment" not in result and "sentiment_score" not in result:
                                errors.append(self._create_error("REQ_G005", "ERROR", path=result_path))

        return errors

    def validate_perplexity_sentiment(self, data: Dict[str, Any], path: str = "perplexity_sentiment") -> List[Dict[str, Any]]:
        """Perplexity感情データの検証"""
        errors = []

        for category, subcategories in data.items():
            category_path = f"{path}.{category}"

            for subcategory, subdata in subcategories.items():
                subdata_path = f"{category_path}.{subcategory}"

                # masked_values チェック
                if "masked_values" not in subdata:
                    errors.append(self._create_error("REQ_S001", "ERROR", path=subdata_path))
                elif not isinstance(subdata["masked_values"], list):
                    errors.append(self._create_error("VAL_S001", "ERROR",
                                                   actual=type(subdata["masked_values"]).__name__, path=subdata_path))
                else:
                    for i, value in enumerate(subdata["masked_values"]):
                        if not isinstance(value, (int, float)):
                            errors.append(self._create_error("VAL_S002", "ERROR",
                                                           index=i, actual=value, path=subdata_path))
                        elif not (1.0 <= value <= 5.0):
                            errors.append(self._create_error("VAL_S003", "ERROR",
                                                           index=i, actual=value, path=subdata_path))

                # entities配下のunmasked_valuesチェック
                entities = subdata.get("entities", {})
                if not isinstance(entities, dict):
                    errors.append(self._create_error("VAL_S004", "ERROR", actual=type(entities).__name__, path=f"{subdata_path}.entities"))
                    continue
                has_any_unmasked_values = False
                for entity_name, entity_data in entities.items():
                    entity_path = f"{subdata_path}.entities.{entity_name}"
                    if isinstance(entity_data, dict) and "unmasked_values" in entity_data:
                        has_any_unmasked_values = True
                        if not isinstance(entity_data["unmasked_values"], list):
                            errors.append(self._create_error("VAL_S005", "ERROR",
                                                           actual=type(entity_data["unmasked_values"]).__name__,
                                                           path=f"{entity_path}.unmasked_values"))
                        else:
                            for i, score in enumerate(entity_data["unmasked_values"]):
                                if not isinstance(score, (int, float)):
                                    errors.append(self._create_error("VAL_S006", "ERROR",
                                                                   index=i, actual=score,
                                                                   path=f"{entity_path}.unmasked_values"))
                                elif not (1.0 <= score <= 5.0):
                                    errors.append(self._create_error("VAL_S007", "ERROR",
                                                                   index=i, actual=score,
                                                                   path=f"{entity_path}.unmasked_values"))
                # どのentityにもunmasked_valuesが存在しない場合はエラー
                if not has_any_unmasked_values:
                    errors.append(self._create_error("REQ_S002", "ERROR", path=subdata_path))

        return errors

    def validate_perplexity_rankings(self, data: Dict[str, Any], path: str = "perplexity_rankings") -> List[Dict[str, Any]]:
        """Perplexityランキングデータの検証"""
        errors = []

        for category, subcategories in data.items():
            category_path = f"{path}.{category}"

            for subcategory, subdata in subcategories.items():
                subdata_path = f"{category_path}.{subcategory}"

                # 実際のデータ構造に合わせた必須フィールドチェック
                required_fields = ["prompt", "ranking_summary", "answer_list"]
                for field in required_fields:
                    if field not in subdata:
                        errors.append(self._create_error("REQ_R001", "ERROR",
                                                       field=field, path=subdata_path))

        return errors

    def validate_perplexity_citations(self, data: Dict[str, Any], path: str = "perplexity_citations") -> List[Dict[str, Any]]:
        """Perplexity引用データの検証"""
        errors = []

        for category, subcategories in data.items():
            category_path = f"{path}.{category}"

            for subcategory, subdata in subcategories.items():
                subdata_path = f"{category_path}.{subcategory}"

                if "entities" in subdata:
                    for entity_name, entity_data in subdata["entities"].items():
                        entity_path = f"{subdata_path}.entities.{entity_name}"

                        # URLの検証
                        # official_results: sentimentチェック不要
                        if "official_results" in entity_data:
                            for i, result in enumerate(entity_data["official_results"]):
                                result_path = f"{entity_path}.official_results[{i}]"
                                if "url" in result:
                                    if not self._is_valid_url(result["url"]):
                                        errors.append(self._create_error("FMT_001", "ERROR",
                                                                       field="url", actual=result["url"],
                                                                       pattern="valid URL", path=result_path))
                        # reputation_results: sentiment必須
                        if "reputation_results" in entity_data:
                            for i, result in enumerate(entity_data["reputation_results"]):
                                result_path = f"{entity_path}.reputation_results[{i}]"
                                if "url" in result:
                                    if not self._is_valid_url(result["url"]):
                                        errors.append(self._create_error("FMT_001", "ERROR",
                                                                       field="url", actual=result["url"],
                                                                       pattern="valid URL", path=result_path))
                                # 感情分析済みチェック（reputation_resultsのみ）
                                if "sentiment" not in result and "sentiment_score" not in result:
                                    errors.append(self._create_error("REQ_C005", "ERROR", path=result_path))

        return errors

    def _validate_search_result(self, result: Dict[str, Any], path: str) -> List[Dict[str, Any]]:
        """検索結果項目の検証"""
        errors = []

        # rank チェック
        if "rank" not in result:
            errors.append(self._create_error("REQ_G003", "ERROR", path=path))
        elif not isinstance(result["rank"], int) or result["rank"] < 1:
            errors.append(self._create_error("VAL_G001", "ERROR",
                                           actual=result["rank"], path=path))

        # domain チェック
        if "domain" not in result:
            errors.append(self._create_error("REQ_G004", "ERROR", path=path))
        elif not result["domain"] or not result["domain"].strip():
            errors.append(self._create_error("VAL_G002", "ERROR", path=path))

        # title と snippet の品質チェック（WARNING）
        if "title" in result and (not result["title"] or not result["title"].strip()):
            errors.append(self._create_error("QUA_001", "WARNING",
                                           field="title", path=path))

        if "snippet" in result and (not result["snippet"] or not result["snippet"].strip()):
            errors.append(self._create_error("QUA_001", "WARNING",
                                           field="snippet", path=path))

        return errors

    def _is_valid_url(self, url: str) -> bool:
        """URL形式の検証"""
        return bool(re.match(self.VALUE_CONSTRAINTS["url_pattern"], url))

    def _create_error(self, error_code: str, severity: str, **kwargs) -> Dict[str, Any]:
        """エラー情報の作成"""
        message_template = self.ERROR_MESSAGES[severity].get(error_code, f"Unknown error: {error_code}")

        error_info = {
            "check_id": error_code,
            "severity": severity,
            "error_message": message_template.format(**kwargs),
            "target_path": kwargs.get("path", "unknown"),
            "timestamp": datetime.now().isoformat()
        }

        # ログ出力
        if severity == "CRITICAL":
            logger.critical(f"{error_code}: {error_info['error_message']}")
        elif severity == "ERROR":
            logger.error(f"{error_code}: {error_info['error_message']}")
        elif severity == "WARNING":
            logger.warning(f"{error_code}: {error_info['error_message']}")

        return error_info

    def _create_validation_summary(self):
        """検証結果サマリーの作成"""
        summary = {
            "total_checks": len(self.validation_results),
            "critical_errors": len([r for r in self.validation_results if r["severity"] == "CRITICAL"]),
            "errors": len([r for r in self.validation_results if r["severity"] == "ERROR"]),
            "warnings": len([r for r in self.validation_results if r["severity"] == "WARNING"]),
            "validation_score": 0.0
        }

        # 品質スコア計算（CRITICAL と ERROR のみカウント）
        problem_count = summary["critical_errors"] + summary["errors"]
        if summary["total_checks"] > 0:
            summary["validation_score"] = max(0.0, (summary["total_checks"] - problem_count) / summary["total_checks"])

        self.validation_summary = summary

        # サマリーログ出力
        logger.info(f"CHK_003: データ統合品質チェック完了 - "
                   f"総チェック数: {summary['total_checks']}, "
                   f"品質スコア: {summary['validation_score']:.2f}, "
                   f"致命的エラー: {summary['critical_errors']}件, "
                   f"エラー: {summary['errors']}件, "
                   f"警告: {summary['warnings']}件")

    def process_data_with_validation(self, raw_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """エラー重要度に応じた処理継続制御"""
        validation_results = self.validate_all_data(raw_data)

        # CRITICAL エラーチェック
        critical_errors = [r for r in validation_results if r["severity"] == "CRITICAL"]
        if critical_errors:
            logger.critical("致命的エラーにより統合データセット作成を中断します")
            raise ProcessingAbortedException("致命的エラーにより処理を中断します")

        # ERROR エラーの処理（該当データを除外）
        error_results = [r for r in validation_results if r["severity"] == "ERROR"]
        cleaned_data = self.remove_error_data(raw_data, error_results)

        # WARNING の処理（ログ記録のみ）
        warning_results = [r for r in validation_results if r["severity"] == "WARNING"]
        if warning_results:
            logger.info(f"WARNINGにより{len(warning_results)}件の品質注意がありましたが、処理を継続します")

        return cleaned_data, validation_results

    def remove_error_data(self, data: Dict[str, Any], error_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """ERRORが発生したデータを除外"""
        cleaned_data = copy.deepcopy(data)
        excluded_entities = set()
        excluded_categories = set()

        for error in error_results:
            path = error["target_path"]
            error_type = error["check_id"]

            if error_type.startswith("REQ_G") or error_type.startswith("VAL_G"):  # Google検索データエラー
                entity_name = self._extract_entity_from_path(path)
                if entity_name and "google_data" in cleaned_data:
                    if entity_name not in excluded_entities:
                        if "entities" in cleaned_data["google_data"] and entity_name in cleaned_data["google_data"]["entities"]:
                            del cleaned_data["google_data"]["entities"][entity_name]
                            excluded_entities.add(entity_name)
                            logger.error(f"→ Google検索データからエラー企業を除外します: {entity_name}")

            elif error_type.startswith("REQ_S") or error_type.startswith("VAL_S"):  # Perplexity感情データエラー
                category, subcategory = self._extract_category_from_path(path)
                category_key = f"{category}.{subcategory}"
                if category_key not in excluded_categories and category and subcategory:
                    if ("perplexity_sentiment" in cleaned_data and
                        category in cleaned_data["perplexity_sentiment"] and
                        subcategory in cleaned_data["perplexity_sentiment"][category]):
                        del cleaned_data["perplexity_sentiment"][category][subcategory]
                        excluded_categories.add(category_key)
                        logger.error(f"→ 感情データからエラーカテゴリを除外します: {category}.{subcategory}")

        return cleaned_data

    def _extract_entity_from_path(self, path: str) -> Optional[str]:
        """パスから企業名を抽出"""
        match = re.search(r'\.entities\.([^\.]+)', path)
        return match.group(1) if match else None

    def _extract_category_from_path(self, path: str) -> Tuple[Optional[str], Optional[str]]:
        """パスからカテゴリとサブカテゴリを抽出"""
        # perplexity_sentiment.カテゴリ.サブカテゴリ の形式を想定
        parts = path.split('.')
        if len(parts) >= 3:
            return parts[1], parts[2]
        return None, None

    def get_validation_summary(self) -> Dict[str, Any]:
        """検証結果サマリーを取得"""
        return getattr(self, 'validation_summary', {})

    def get_processing_summary(self, input_records: int, output_records: int) -> Dict[str, Any]:
        """処理結果サマリーを生成"""
        excluded_records = input_records - output_records

        summary = {
            "processing_status": "COMPLETED",
            "total_records_input": input_records,
            "total_records_output": output_records,
            "records_excluded": excluded_records,
            "validation_summary": self.get_validation_summary(),
            "excluded_data": [],
            "recommendations": []
        }

        # 処理ステータスの決定
        if hasattr(self, 'validation_summary'):
            if self.validation_summary.get("critical_errors", 0) > 0:
                summary["processing_status"] = "ABORTED"
            elif self.validation_summary.get("errors", 0) > 0:
                summary["processing_status"] = "COMPLETED_WITH_ERRORS"

        # 推奨事項の生成
        if excluded_records > 0:
            summary["recommendations"].append(f"{excluded_records}件のデータが除外されました。データ収集プロセスの確認を推奨します。")

        if hasattr(self, 'validation_summary') and self.validation_summary.get("warnings", 0) > 0:
            summary["recommendations"].append("品質注意があります。分析時に注意してください。")

        return summary