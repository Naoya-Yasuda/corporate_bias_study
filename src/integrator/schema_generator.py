"""
データセットスキーマ生成モジュール

統合データセットの構造定義を自動生成し、
データ型やフィールド説明を含むスキーマを出力する。
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


class SchemaGenerator:
    """データセットスキーマ生成クラス"""

    def __init__(self):
        self.schema = {}
        self.field_descriptions = {
            # Google検索データ
            "entities": "企業・サービスごとのデータ",
            "official_results": "企業公式サイトの検索結果",
            "reputation_results": "企業評判に関する検索結果",
            "rank": "検索結果での順位（1以上の整数）",
            "title": "検索結果のタイトル",
            "link": "検索結果のURL",
            "domain": "検索結果のドメイン名",
            "snippet": "検索結果のスニペット（要約文）",

            # Perplexity感情データ
            "masked_values": "企業名を伏せた状態での感情スコアリスト（1-5点）",
            "masked_avg": "企業名を伏せた状態での感情スコア平均値",
            "masked_answer": "企業名を伏せた状態でのAI回答文",
            "masked_url": "企業名を伏せた状態での引用URLリスト",
            "masked_reasons": "企業名を伏せた状態での評価理由",
            "unmasked_values": "企業名を明示した状態での感情スコアリスト",
            "unmasked_avg": "企業名を明示した状態での感情スコア平均値",
            "unmasked_answer": "企業名を明示した状態でのAI回答文",
            "unmasked_url": "企業名を明示した状態での引用URLリスト",
            "unmasked_reasons": "企業名を明示した状態での評価理由",

            # Perplexityランキングデータ
            "services": "対象サービス・企業のリスト",
            "ranking_summary": "ランキング結果のサマリー統計",
            "average_rank": "平均順位",
            "rank_counts": "各順位の出現回数",
            "response_list": "AI応答の生データリスト",
            "run": "実行回数（何回目の実行か）",
            "answer": "AIの回答文",
            "extracted_ranking": "抽出されたランキング順位",
            "url": "引用URL",
            "official_url": "企業公式URL",

            # Perplexity引用データ
            "official_answer": "企業公式情報に関するAI回答",
            "reputation_answer": "企業評判に関するAI回答",
            "is_official": "公式サイトかどうかのフラグ",

            # メタデータ
            "timestamp": "データ収集時刻（ISO 8601形式）",
            "category": "カテゴリ名",
            "subcategory": "サブカテゴリ名",
            "masked_prompt": "企業名を伏せたプロンプト",
            "unmasked_prompt": "企業名を明示したプロンプト"
        }

        self.value_constraints = {
            "sentiment_score": {"type": "number", "minimum": 1.0, "maximum": 5.0},
            "rank": {"type": "integer", "minimum": 1, "maximum": 100},
            "url": {"type": "string", "format": "uri"},
            "timestamp": {"type": "string", "format": "date-time"},
            "domain": {"type": "string", "pattern": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"},
            "title": {"type": "string", "maxLength": 500},
            "snippet": {"type": "string", "maxLength": 1000}
        }

    def generate_schema(self, integrated_data: Dict[str, Any]) -> Dict[str, Any]:
        """統合データからスキーマを生成"""
        logger.info("データセットスキーマ生成開始")

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "Corporate Bias Dataset Schema",
            "description": "企業優遇バイアス研究用統合データセットのスキーマ定義",
            "type": "object",
            "properties": {},
            "required": [],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
                "data_sources": [],
                "field_count": 0,
                "record_count": 0
            }
        }

        # データソースの検出
        data_sources = []
        if "google_data" in integrated_data:
            data_sources.append("Google Search API")
        if "perplexity_sentiment" in integrated_data:
            data_sources.append("Perplexity API (Sentiment)")
        if "perplexity_rankings" in integrated_data:
            data_sources.append("Perplexity API (Rankings)")
        if "perplexity_citations" in integrated_data:
            data_sources.append("Perplexity API (Citations)")

        schema["metadata"]["data_sources"] = data_sources

        # 各データタイプのスキーマ生成
        if "google_data" in integrated_data:
            schema["properties"]["google_data"] = self._generate_google_schema(integrated_data["google_data"])
            schema["required"].append("google_data")

        if "perplexity_sentiment" in integrated_data:
            schema["properties"]["perplexity_sentiment"] = self._generate_sentiment_schema(integrated_data["perplexity_sentiment"])
            schema["required"].append("perplexity_sentiment")

        if "perplexity_rankings" in integrated_data:
            schema["properties"]["perplexity_rankings"] = self._generate_rankings_schema(integrated_data["perplexity_rankings"])
            schema["required"].append("perplexity_rankings")

        if "perplexity_citations" in integrated_data:
            schema["properties"]["perplexity_citations"] = self._generate_citations_schema(integrated_data["perplexity_citations"])
            schema["required"].append("perplexity_citations")

        # メタデータ更新
        schema["metadata"]["field_count"] = self._count_fields(schema["properties"])
        schema["metadata"]["record_count"] = self._count_records(integrated_data)

        self.schema = schema
        logger.info(f"スキーマ生成完了 - フィールド数: {schema['metadata']['field_count']}, レコード数: {schema['metadata']['record_count']}")

        return schema

    def _generate_google_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Google検索データのスキーマ生成"""
        schema = {
            "type": "object",
            "description": "Google検索結果データ",
            "properties": {},
            "required": []
        }

        # カテゴリレベルの分析
        sample_category = next(iter(data.keys())) if data else None
        if sample_category and sample_category in data:
            sample_subcategory = next(iter(data[sample_category].keys())) if data[sample_category] else None

            if sample_subcategory and sample_subcategory in data[sample_category]:
                sample_data = data[sample_category][sample_subcategory]

                # timestamp
                if "timestamp" in sample_data:
                    schema["properties"]["timestamp"] = {
                        "type": "string",
                        "format": "date-time",
                        "description": self.field_descriptions.get("timestamp", "データ収集時刻")
                    }

                # category, subcategory
                schema["properties"]["category"] = {
                    "type": "string",
                    "description": self.field_descriptions.get("category", "カテゴリ名")
                }
                schema["properties"]["subcategory"] = {
                    "type": "string",
                    "description": self.field_descriptions.get("subcategory", "サブカテゴリ名")
                }

                # entities構造
                if "entities" in sample_data:
                    schema["properties"]["entities"] = self._generate_entities_schema(sample_data["entities"])
                    schema["required"].append("entities")

        return schema

    def _generate_entities_schema(self, entities_data: Dict[str, Any]) -> Dict[str, Any]:
        """entitiesフィールドのスキーマ生成"""
        schema = {
            "type": "object",
            "description": self.field_descriptions.get("entities", "企業・サービスごとのデータ"),
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "description": "個別企業・サービスのデータ",
                    "properties": {
                        "official_results": {
                            "type": "array",
                            "description": self.field_descriptions.get("official_results", "企業公式サイトの検索結果"),
                            "items": self._generate_search_result_schema()
                        },
                        "reputation_results": {
                            "type": "array",
                            "description": self.field_descriptions.get("reputation_results", "企業評判に関する検索結果"),
                            "items": self._generate_search_result_schema()
                        }
                    },
                    "required": ["official_results", "reputation_results"]
                }
            }
        }

        return schema

    def _generate_search_result_schema(self) -> Dict[str, Any]:
        """検索結果項目のスキーマ生成"""
        schema = {
            "type": "object",
            "description": "検索結果の個別項目",
            "properties": {
                "rank": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": self.field_descriptions.get("rank", "検索結果での順位")
                },
                "title": {
                    "type": "string",
                    "maxLength": 500,
                    "description": self.field_descriptions.get("title", "検索結果のタイトル")
                },
                "link": {
                    "type": "string",
                    "format": "uri",
                    "description": self.field_descriptions.get("link", "検索結果のURL")
                },
                "domain": {
                    "type": "string",
                    "pattern": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                    "description": self.field_descriptions.get("domain", "検索結果のドメイン名")
                },
                "snippet": {
                    "type": "string",
                    "maxLength": 1000,
                    "description": self.field_descriptions.get("snippet", "検索結果のスニペット")
                }
            },
            "required": ["rank", "domain"]
        }

        return schema

    def _generate_sentiment_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perplexity感情データのスキーマ生成"""
        schema = {
            "type": "object",
            "description": "Perplexity API感情分析データ",
            "patternProperties": {
                ".*": {  # カテゴリレベル
                    "type": "object",
                    "description": "カテゴリごとの感情分析データ",
                    "patternProperties": {
                        ".*": {  # サブカテゴリレベル
                            "type": "object",
                            "description": "サブカテゴリごとの感情分析データ",
                            "properties": {
                                "masked_prompt": {
                                    "type": "string",
                                    "description": self.field_descriptions.get("masked_prompt", "企業名を伏せたプロンプト")
                                },
                                "masked_values": {
                                    "type": "array",
                                    "description": self.field_descriptions.get("masked_values", "企業名を伏せた状態での感情スコアリスト"),
                                    "items": {
                                        "type": "number",
                                        "minimum": 1.0,
                                        "maximum": 5.0
                                    }
                                },
                                "masked_avg": {
                                    "type": "number",
                                    "minimum": 1.0,
                                    "maximum": 5.0,
                                    "description": self.field_descriptions.get("masked_avg", "企業名を伏せた状態での感情スコア平均値")
                                },
                                "unmasked_values": {
                                    "type": "object",
                                    "description": self.field_descriptions.get("unmasked_values", "企業名を明示した状態での感情スコアリスト"),
                                    "patternProperties": {
                                        ".*": {
                                            "type": "array",
                                            "items": {
                                                "type": "number",
                                                "minimum": 1.0,
                                                "maximum": 5.0
                                            }
                                        }
                                    }
                                },
                                "unmasked_avg": {
                                    "type": "object",
                                    "description": self.field_descriptions.get("unmasked_avg", "企業名を明示した状態での感情スコア平均値"),
                                    "patternProperties": {
                                        ".*": {
                                            "type": "number",
                                            "minimum": 1.0,
                                            "maximum": 5.0
                                        }
                                    }
                                }
                            },
                            "required": ["masked_values", "masked_avg", "unmasked_values", "unmasked_avg"]
                        }
                    }
                }
            }
        }

        return schema

    def _generate_rankings_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perplexityランキングデータのスキーマ生成"""
        schema = {
            "type": "object",
            "description": "Perplexity APIランキング抽出データ",
            "patternProperties": {
                ".*": {  # カテゴリレベル
                    "type": "object",
                    "description": "カテゴリごとのランキングデータ",
                    "patternProperties": {
                        ".*": {  # サブカテゴリレベル
                            "type": "object",
                            "description": "サブカテゴリごとのランキングデータ",
                            "properties": {
                                "timestamp": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": self.field_descriptions.get("timestamp", "データ収集時刻")
                                },
                                "services": {
                                    "type": "array",
                                    "description": self.field_descriptions.get("services", "対象サービス・企業のリスト"),
                                    "items": {"type": "string"}
                                },
                                "ranking_summary": {
                                    "type": "object",
                                    "description": self.field_descriptions.get("ranking_summary", "ランキング結果のサマリー統計"),
                                    "patternProperties": {
                                        ".*": {
                                            "type": "object",
                                            "properties": {
                                                "average_rank": {
                                                    "type": "number",
                                                    "minimum": 1.0,
                                                    "description": self.field_descriptions.get("average_rank", "平均順位")
                                                },
                                                "rank_counts": {
                                                    "type": "array",
                                                    "description": self.field_descriptions.get("rank_counts", "各順位の出現回数"),
                                                    "items": {"type": "integer", "minimum": 0}
                                                }
                                            },
                                            "required": ["average_rank", "rank_counts"]
                                        }
                                    }
                                },
                                "response_list": {
                                    "type": "array",
                                    "description": self.field_descriptions.get("response_list", "AI応答の生データリスト"),
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "run": {
                                                "type": "integer",
                                                "minimum": 1,
                                                "description": self.field_descriptions.get("run", "実行回数")
                                            },
                                            "answer": {
                                                "type": "string",
                                                "description": self.field_descriptions.get("answer", "AIの回答文")
                                            },
                                            "extracted_ranking": {
                                                "type": "array",
                                                "description": self.field_descriptions.get("extracted_ranking", "抽出されたランキング順位"),
                                                "items": {"type": "string"}
                                            }
                                        },
                                        "required": ["run", "answer", "extracted_ranking"]
                                    }
                                }
                            },
                            "required": ["services", "ranking_summary", "response_list"]
                        }
                    }
                }
            }
        }

        return schema

    def _generate_citations_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Perplexity引用データのスキーマ生成"""
        schema = {
            "type": "object",
            "description": "Perplexity API引用リンクデータ",
            "patternProperties": {
                ".*": {  # カテゴリレベル
                    "type": "object",
                    "description": "カテゴリごとの引用データ",
                    "patternProperties": {
                        ".*": {  # サブカテゴリレベル
                            "type": "object",
                            "description": "サブカテゴリごとの引用データ",
                            "properties": {
                                "entities": {
                                    "type": "object",
                                    "description": self.field_descriptions.get("entities", "企業・サービスごとのデータ"),
                                    "patternProperties": {
                                        ".*": {
                                            "type": "object",
                                            "description": "個別企業・サービスの引用データ",
                                            "properties": {
                                                "official_results": {
                                                    "type": "array",
                                                    "description": self.field_descriptions.get("official_results", "企業公式情報に関する引用"),
                                                    "items": self._generate_citation_result_schema()
                                                },
                                                "reputation_results": {
                                                    "type": "array",
                                                    "description": self.field_descriptions.get("reputation_results", "企業評判に関する引用"),
                                                    "items": self._generate_citation_result_schema()
                                                }
                                            },
                                            "required": ["official_results", "reputation_results"]
                                        }
                                    }
                                }
                            },
                            "required": ["entities"]
                        }
                    }
                }
            }
        }

        return schema

    def _generate_citation_result_schema(self) -> Dict[str, Any]:
        """引用結果項目のスキーマ生成"""
        schema = {
            "type": "object",
            "description": "引用結果の個別項目",
            "properties": {
                "rank": {
                    "type": "integer",
                    "minimum": 1,
                    "description": self.field_descriptions.get("rank", "引用での順位")
                },
                "url": {
                    "type": "string",
                    "format": "uri",
                    "description": self.field_descriptions.get("url", "引用URL")
                },
                "domain": {
                    "type": "string",
                    "pattern": r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                    "description": self.field_descriptions.get("domain", "引用サイトのドメイン名")
                },
                "title": {
                    "type": "string",
                    "maxLength": 500,
                    "description": self.field_descriptions.get("title", "引用ページのタイトル")
                },
                "snippet": {
                    "type": "string",
                    "maxLength": 1000,
                    "description": self.field_descriptions.get("snippet", "引用ページのスニペット")
                },
                "is_official": {
                    "type": "boolean",
                    "description": self.field_descriptions.get("is_official", "公式サイトかどうかのフラグ")
                }
            },
            "required": ["url"]
        }

        return schema

    def _count_fields(self, properties: Dict[str, Any]) -> int:
        """スキーマ内のフィールド数をカウント"""
        count = 0

        def count_recursive(obj):
            nonlocal count
            if isinstance(obj, dict):
                if "properties" in obj:
                    count += len(obj["properties"])
                    for prop in obj["properties"].values():
                        count_recursive(prop)
                elif "patternProperties" in obj:
                    for prop in obj["patternProperties"].values():
                        count_recursive(prop)
                elif "items" in obj:
                    count_recursive(obj["items"])

        count_recursive({"properties": properties})
        return count

    def _count_records(self, data: Dict[str, Any]) -> int:
        """データ内のレコード数をカウント"""
        total_records = 0

        # Google検索データのレコード数
        if "google_data" in data:
            for category_data in data["google_data"].values():
                for subcategory_data in category_data.values():
                    if "entities" in subcategory_data:
                        for entity_data in subcategory_data["entities"].values():
                            total_records += len(entity_data.get("official_results", []))
                            total_records += len(entity_data.get("reputation_results", []))

        # Perplexity感情データのレコード数
        if "perplexity_sentiment" in data:
            for category_data in data["perplexity_sentiment"].values():
                for subcategory_data in category_data.values():
                    total_records += len(subcategory_data.get("masked_values", []))
                    if "unmasked_values" in subcategory_data:
                        for entity_values in subcategory_data["unmasked_values"].values():
                            total_records += len(entity_values)

        return total_records

    def get_schema(self) -> Dict[str, Any]:
        """生成されたスキーマを取得"""
        return self.schema

    def save_schema(self, output_path: str):
        """スキーマをファイルに保存"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.schema, f, ensure_ascii=False, indent=2)
        logger.info(f"スキーマを保存しました: {output_path}")

    def validate_data_against_schema(self, data: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> List[str]:
        """データがスキーマに準拠しているかチェック"""
        if schema is None:
            schema = self.schema

        validation_errors = []

        # 簡易的な構造チェック（完全なJSON Schema validationではない）
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                validation_errors.append(f"必須フィールド '{field}' が存在しません")

        return validation_errors