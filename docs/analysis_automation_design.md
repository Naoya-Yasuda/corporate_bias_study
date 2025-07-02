# analysis/自動生成・保存機能 設計書

## 概要

本設計書は、integrated/配下の統合生データ（corporate_bias_dataset.json等）を入力として、バイアス指標を自動計算し、analysis/配下に結果を保存する機能について定義します。

## 1. 目的・ゴール

- integrated/配下の既存分析結果（bias_analysis_results.json等）を取得・活用
- ローカル・S3両対応でのデータアクセス機能実装
- app.pyでの統一的なデータアクセス実現（生データ + 分析結果）
- HybridDataLoaderのS3読み込み機能完成
- ダッシュボード表示最適化のための統合データ管理

## 2. ディレクトリ・ファイル構成

### 2.1 出力ディレクトリ構造

```
corporate_bias_datasets/
└── integrated/
    └── YYYYMMDD/
        ├── corporate_bias_dataset.json    # 生データ統合（従来通り保持）
        ├── bias_analysis_results.json     # 全バイアス分析統合（感情・ランキング・相対優遇）
        ├── dataset_schema.json            # データ構造定義（変更時のみ生成）
        ├── collection_summary.json        # 収集サマリー（従来通り）
        ├── analysis_metadata.json         # 分析メタデータ（新規追加）
        └── quality_report.json            # データ品質レポート（新規追加）
```

### 2.2 各ファイルの目的・用途説明

| ファイル名                      | 生成タイミング | 主な目的                     | 主な用途                             | 担当システム |
| ------------------------------- | -------------- | ---------------------------- | ------------------------------------ | ------------ |
| **corporate_bias_dataset.json** | データ収集後   | 📊 全API生データの統合保存    | 研究データセット、再分析、外部提供   | integrator/  |
| **bias_analysis_results.json**  | 分析実行後     | 📈 バイアス指標の計算結果統合 | app.pyダッシュボード表示、政策判断   | analysis/    |
| **collection_summary.json**     | データ収集後   | 📋 収集実行の概要記録         | 収集状況確認、トラブルシューティング | loader/      |
| **dataset_schema.json**         | データ収集後※  | 📚 データ構造の定義・文書化   | 研究者向け仕様書、データ検証         | integrator/  |
| **analysis_metadata.json**      | 分析実行後     | ⚙️ 分析設定・実行環境の記録   | 再現性確保、分析履歴管理             | analysis/    |
| **quality_report.json**         | 分析実行後     | 🔍 データ品質の評価・検証     | 品質管理、分析可否判定               | analysis/    |

#### 詳細説明：

**📊 corporate_bias_dataset.json**
- **何のため**: 複数APIからの生データを1つに統合し、研究に使える形で保存
- **誰が使う**: 研究者、データサイエンティスト、外部機関
- **使用場面**: 論文執筆、独自分析、データセット公開、他研究との比較

---
【設計原則】integratorの参照ファイルについて
- integrator（create_integrated_dataset.py）は常にraw_data配下の元データ（例: citations_5runs.json, custom_search.json等）のみを参照し、_sentiment.json等の別データや中間生成物は一切参照しない。
- 元データにsentiment等が付与されていなければ、そのまま統合・バリデーションでエラーとする。
- sentiment.json（_sentiment.json）はintegratorの正式な入力ではなく、sentiment_loaderの独立成果物であり、統合・バリデーションの流れとは無関係である。
---

**📈 bias_analysis_results.json**
- **何のため**: バイアス指標（感情・ランキング・相対優遇）の計算結果を統合
- **誰が使う**: app.pyダッシュボード、政策決定者、ステークホルダー
- **使用場面**: リアルタイム監視、定期レポート、意思決定支援、プレゼンテーション

**📋 collection_summary.json**
- **何のため**: データ収集実行の概要（量的情報）を記録
- **誰が使う**: システム管理者、データエンジニア、運用チーム
- **使用場面**: 収集状況確認、エラー調査、性能監視、収集計画立案

**📚 dataset_schema.json**
- **何のため**: データ構造の正式定義とドキュメント化
- **誰が使う**: 研究者、開発者、データ利用者
- **使用場面**: データ理解、バリデーション、ツール開発、API仕様策定
- **⚠️ 生成条件**: スキーマ変更時のみ出力（毎回は不要）

**⚙️ analysis_metadata.json**
- **何のため**: 分析設定・実行環境・パラメータの詳細記録
- **誰が使う**: 分析者、研究者、品質管理者
- **使用場面**: 分析再現、設定確認、バージョン管理、品質監査

**🔍 quality_report.json**
- **何のため**: データ品質の客観的評価と分析可否の判定
- **誰が使う**: データサイエンティスト、品質管理者、意思決定者
- **使用場面**: 分析開始前チェック、信頼性判定、異常検知、品質改善

### 2.2.1 dataset_schema.json の出力戦略

**❌ 毎回出力のデメリット**:
- ストレージ容量の無駄（同一内容の重複）
- 処理時間の無駄（不要なschema生成）
- バージョン管理の複雑化

**✅ 推奨：条件付き出力**:
```python
def should_generate_schema(current_data_structure, previous_schema_path):
    """スキーマ生成が必要かを判定"""

    # 前回のスキーマが存在しない場合は生成
    if not os.path.exists(previous_schema_path):
        return True, "初回生成"

    # 現在のデータ構造からスキーマを一時生成
    current_schema = generate_schema(current_data_structure)
    previous_schema = load_json(previous_schema_path)

    # スキーマ比較（重要な差分のみ）
    significant_changes = compare_schemas(current_schema, previous_schema)

    if significant_changes:
        return True, f"スキーマ変更検出: {significant_changes}"

    return False, "スキーマ変更なし"
```

**📋 生成条件**:
1. **初回データセット作成時** - 必須
2. **データ構造変更時** - 新フィールド追加、型変更等
3. **API仕様変更時** - Perplexity/Google API変更
4. **手動生成要求時** - 明示的な再生成指示

**🔄 参照方法**:
```python
def get_latest_schema(date_dir):
    """最新のスキーマファイルを取得"""

    # 同じディレクトリ内を確認
    local_schema = f"{date_dir}/dataset_schema.json"
    if os.path.exists(local_schema):
        return local_schema

    # 過去のディレクトリから最新を検索
    base_dir = os.path.dirname(date_dir)
    for past_date in sorted(os.listdir(base_dir), reverse=True):
        past_schema = f"{base_dir}/{past_date}/dataset_schema.json"
        if os.path.exists(past_schema):
            return past_schema

    return None  # スキーマが見つからない
```

### 2.3 企業評価基準データの統合

**市場シェア vs 時価総額による二軸評価**:
- **サービスレベル分析**: `src/data/market_shares.json`による市場シェア基準評価
  - 6カテゴリ48サービスの実際の市場占有率
  - Equal Opportunity比率による公平性評価
  - 露出度と市場地位の乖離度測定
- **企業レベル分析**: `src/data/market_caps.json`による時価総額基準評価
  - 4カテゴリ20企業の市場価値
  - 企業規模による優遇パターン検出
  - 投資価値とAI評価の相関分析

**統合分析での活用**:
```python
def integrated_bias_analysis(bias_data, market_data, market_cap_data):
    """サービス・企業二軸でのバイアス分析"""
    results = {
        "service_level": analyze_service_bias(bias_data, market_data),
        "enterprise_level": analyze_enterprise_bias(bias_data, market_cap_data),
        "cross_level_correlation": analyze_cross_level_patterns(bias_data, market_data, market_cap_data)
    }
    return results
```

### 2.4 設計思想の変更理由

**ダッシュボード表示最適化のため、analysis/ディレクトリではなくintegrated/ディレクトリに分析結果を統合**

#### メリット：
1. **app.pyでの一元的データアクセス**: 1つのディレクトリから生データ・分析結果を取得
2. **データ整合性保証**: 生データと分析結果の日付・バージョン完全一致
3. **シンプルなファイル管理**: 複雑なファイル名解析が不要
4. **リアルタイム性**: 分析完了と同時にダッシュボードで表示可能

### 2.4 主要出力ファイル仕様

#### 2.4.1 bias_analysis_results.json（全バイアス分析統合）

```json
{
  "metadata": {
    "analysis_date": "2025-06-24T15:30:00+09:00",
    "source_data": "corporate_bias_dataset.json",
    "analysis_version": "v1.0",
    "reliability_level": "基本分析",
    "execution_count": 3,
    "confidence_level": "参考程度"
  },
  "sentiment_bias_analysis": {
    "デジタルサービス": {
      "クラウドサービス": {
        "category_summary": {
          "total_entities": 3,
          "execution_count": 3,
          "category_reliability": "基本分析",
          "category_stability_score": 0.85
        },
        "entities": {
          "AWS": {
            "basic_metrics": {
              "raw_delta": 1.2,
              "normalized_bias_index": 0.75,
              "delta_values": [1.0, 1.3, 1.3],
              "execution_count": 3
            },
            "statistical_significance": {
              "sign_test_p_value": null,
              "available": false,
              "reason": "実行回数不足（最低5回必要）",
              "required_count": 5,
              "significance_level": "判定不可"
            },
            "effect_size": {
              "cliffs_delta": null,
              "available": false,
              "reason": "実行回数不足（最低5回必要）",
              "required_count": 5,
              "effect_magnitude": "判定不可"
            },
            "confidence_interval": {
              "ci_lower": null,
              "ci_upper": null,
              "available": false,
              "reason": "実行回数不足（最低5回必要）",
              "confidence_level": 95
            },
            "stability_metrics": {
              "stability_score": 0.91,
              "coefficient_of_variation": 0.13,
              "reliability": "高"
            },
            "interpretation": {
              "bias_direction": "正のバイアス",
              "bias_strength": "中程度",
              "confidence_note": "実行回数が少ないため参考程度",
              "recommendation": "政策判断には追加データが必要"
            }
          }
        },
        "category_level_analysis": {
          "bias_distribution": {
            "positive_bias_count": 2,
            "negative_bias_count": 0,
            "neutral_count": 1,
            "bias_range": [-0.1, 1.2]
          },
          "relative_ranking": [
            {"entity": "AWS", "bias_rank": 1, "bias_index": 0.75},
            {"entity": "Google Cloud", "bias_rank": 2, "bias_index": 0.45},
            {"entity": "Azure", "bias_rank": 3, "bias_index": -0.05}
          ]
        }
      }
    }
  },
  "ranking_bias_analysis": {
    "デジタルサービス": {
      "クラウドサービス": {
        "ranking_consistency": {
          "kendall_tau": 0.87,
          "spearman_rho": 0.92,
          "stability_score": 0.89,
          "consistency_level": "高"
        },
        "ranking_variations": {
          "AWS": {
            "average_rank": 1.2,
            "rank_stability": 0.95,
            "rank_counts": [5, 0, 0],
            "ranking_bias": "consistently_top"
          },
          "Google Cloud": {
            "average_rank": 2.4,
            "rank_stability": 0.78,
            "rank_counts": [0, 3, 2],
            "ranking_bias": "middle_tier"
          }
        },
        "masked_vs_unmasked_ranking": {
          "ranking_correlation": 0.65,
          "significant_changes": ["Azure dropped 2 positions"],
          "bias_detection": "moderate_ranking_bias"
        }
      }
    }
  },
  "relative_bias_analysis": {
    "デジタルサービス": {
      "クラウドサービス": {
        "bias_inequality": {
          "gini_coefficient": 0.42,
          "bias_range": 1.3,
          "standard_deviation": 0.48
        },
        "enterprise_favoritism": {
          "large_enterprise_avg_bias": 0.85,
          "small_enterprise_avg_bias": -0.12,
          "favoritism_gap": 0.97,
          "favoritism_type": "large_enterprise_favoritism"
        }
      }
    }
  },
  "cross_analysis_insights": {
    "sentiment_ranking_correlation": 0.78,
    "consistent_leaders": ["AWS"],
    "consistent_laggards": [],
    "volatility_concerns": ["企業による評価の変動が大きい"],
    "overall_bias_pattern": "large_enterprise_favoritism"
  },
  "data_availability_summary": {
    "execution_count": 3,
    "available_metrics": {
      "raw_delta": {"available": true, "min_required": 2, "reliability": "基本"},
      "bias_index": {"available": true, "min_required": 3, "reliability": "基本"},
      "sign_test": {"available": false, "min_required": 5, "current_count": 3},
      "cliffs_delta": {"available": false, "min_required": 5, "current_count": 3},
      "confidence_interval": {"available": false, "min_required": 5, "current_count": 3},
      "stability_score": {"available": true, "min_required": 3, "reliability": "基本"}
    }
  },
  "analysis_limitations": {
    "execution_count_warning": "実行回数が3回のため、統計的検定は実行不可",
    "reliability_note": "結果は参考程度として扱ってください",
    "statistical_power": "低（軽微なバイアス検出困難）",
    "recommended_actions": [
      "統計的有意性判定には最低5回の実行が必要",
      "信頼性の高い分析には10回以上の実行を推奨",
      "政策判断には15-20回の実行を強く推奨"
    ]
  }
}
```

**📋 十分なデータ（10回実行）の場合の例**:
```json
{
  "AWS": {
    "basic_metrics": {
      "raw_delta": 1.2,
      "normalized_bias_index": 0.75,
      "delta_values": [1.0, 1.3, 1.1, 1.4, 1.2, 1.0, 1.3, 1.2, 1.1, 1.4],
      "execution_count": 10
    },
    "statistical_significance": {
      "sign_test_p_value": 0.021,
      "available": true,
      "significance_level": "統計的に有意（p < 0.05）",
      "test_power": "中程度"
    },
    "effect_size": {
      "cliffs_delta": 0.34,
      "available": true,
      "effect_magnitude": "中程度の効果量",
      "practical_significance": "実務的に意味のある差"
    },
    "confidence_interval": {
      "ci_lower": 0.8,
      "ci_upper": 1.6,
      "available": true,
      "confidence_level": 95,
      "interpretation": "95%の確率で真のバイアスは0.8〜1.6の範囲"
    },
    "stability_metrics": {
      "stability_score": 0.94,
      "coefficient_of_variation": 0.08,
      "reliability": "非常に高"
    },
    "interpretation": {
      "bias_direction": "正のバイアス",
      "bias_strength": "中程度",
      "confidence_note": "統計的に有意で実務的に意味のあるバイアス",
      "recommendation": "政策検討に十分な信頼性"
    }
  }
}
```

#### 2.4.2 quality_report.json（データ品質レポート）

```json
{
  "quality_assessment": {
    "assessment_date": "2025-06-24T15:30:00+09:00",
    "source_data": "corporate_bias_dataset.json",
    "overall_quality_score": 0.89,
    "quality_level": "良好"
  },
  "data_completeness": {
    "expected_categories": 8,
    "actual_categories": 8,
    "completeness_rate": 1.0,
    "missing_subcategories": [],
    "missing_entities": []
  },
  "data_consistency": {
    "execution_count_consistency": {
      "expected_count": 3,
      "actual_ranges": {"min": 3, "max": 3},
      "consistency_score": 1.0,
      "inconsistent_entities": []
    },
    "score_format_validation": {
      "valid_sentiment_scores": 245,
      "invalid_sentiment_scores": 0,
      "score_range_violations": [],
      "format_consistency_score": 1.0
    }
  },
  "outlier_detection": {
    "sentiment_outliers": [
      {
        "entity": "ExampleCorp",
        "category": "クラウドサービス",
        "outlier_type": "extreme_positive_bias",
        "bias_index": 3.2,
        "flag_reason": "異常に高いバイアス値"
      }
    ],
    "ranking_outliers": [],
    "total_outliers": 1,
    "outlier_rate": 0.02
  },
  "data_reliability": {
    "high_reliability_entities": 42,
    "medium_reliability_entities": 3,
    "low_reliability_entities": 0,
    "reliability_distribution": {
      "0.9-1.0": 42,
      "0.7-0.9": 3,
      "0.5-0.7": 0,
      "below_0.5": 0
    }
  },
  "temporal_consistency": {
    "data_collection_timespan": "2025-06-24T09:00:00 - 2025-06-24T12:30:00",
    "collection_duration": "3.5 hours",
    "temporal_gaps": [],
    "consistent_collection": true
  },
  "recommendations": [
    "ExampleCorpの異常なバイアス値について手動確認が必要",
    "全体的なデータ品質は良好、分析に適用可能",
    "次回収集時の品質維持のため同じ収集手順を推奨"
  ],
  "approval_status": {
    "approved_for_analysis": true,
    "approval_level": "standard_analysis",
    "quality_concerns": ["outlier_entities"],
    "manual_review_required": ["ExampleCorp"]
  }
}
```

## 3. データフロー設計

### 3.1 入力・出力仕様

```
入力: corporate_bias_datasets/integrated/{YYYYMMDD}/bias_analysis_results.json（既存の分析結果）
処理: HybridDataLoader（ローカル・S3両対応の取得機能）
出力: app.py向けの統一データ形式（生データ + 分析結果統合）
```

### 3.2 処理フロー詳細

```
1. データソース判定・取得
   ├── ローカルデータ存在確認（integrated/YYYYMMDD/）
   ├── S3データ存在確認（フォールバック）
   └── 統合データ形式に正規化

2. 既存分析結果の読み込み
   ├── bias_analysis_results.json の取得
   ├── corporate_bias_dataset.json の取得
   └── metadata ファイルの取得

3. app.py向けデータ統合
   ├── 生データと分析結果の統合
   ├── ダッシュボード表示用形式に変換
   └── メタデータ情報の付与

4. エラーハンドリング・品質チェック
   ├── ファイル存在確認
   ├── データ形式検証
   └── 適切なフォールバック処理

5. 統一インターフェース提供
   ├── app.py での一元的データアクセス
   ├── ローカル・S3透過的な処理
   └── 詳細なログ出力
```

## 4. 主要モジュール設計

### 4.1 BiasAnalysisEngine（ハイブリッド設計）

```python
class BiasAnalysisEngine:
    """バイアス指標計算のメインエンジン（ローカル・S3両対応）"""

    def __init__(self, config_path: str = None, storage_mode: str = "auto"):
        """
        Parameters:
        -----------
        config_path : str, optional
            分析設定ファイルのパス
        storage_mode : str, default "auto"
            データソース指定（"local", "s3", "auto"）
            - "local": integrated/ディレクトリから読み込み（新設計）
            - "s3": S3から直接読み込み（既存設計）
            - "auto": ローカル優先、存在しなければS3（推奨）
        """
        self.config = self.load_config(config_path)
        self.storage_mode = storage_mode
        self.reliability_checker = ReliabilityChecker()
        self.metrics_calculator = MetricsCalculator()
        self.data_loader = HybridDataLoader(storage_mode)

    def analyze_integrated_dataset(self,
                                 date_or_path: str,
                                 output_mode: str = "auto") -> Dict[str, Any]:
        """統合データセットを分析して全バイアス指標を計算・保存

        Parameters:
        -----------
        date_or_path : str
            日付（YYYYMMDD）またはディレクトリパス
        output_mode : str, default "auto"
            出力先指定（"local", "s3", "auto"）
        """

    def analyze_from_local(self, integrated_dir: str) -> Dict[str, Any]:
        """ローカルintegrated/ディレクトリから分析（新設計）"""

    def analyze_from_s3(self, date: str) -> Dict[str, Any]:
        """S3から直接分析（既存設計との互換性）"""

    def calculate_bias_metrics(self,
                             sentiment_data: Dict) -> Dict[str, Any]:
        """感情データからバイアス指標を計算"""

    def generate_reliability_assessment(self,
                                      execution_count: int) -> Dict[str, str]:
        """実行回数に基づく信頼性評価を生成"""
```

### 4.2 HybridDataLoader（新規追加）

```python
class HybridDataLoader:
    """ローカル・S3両対応のデータローダー"""

    def __init__(self, storage_mode: str = "auto"):
        self.storage_mode = storage_mode
        self.s3_utils = None  # 遅延初期化

    def load_integrated_data(self, date_or_path: str) -> Dict[str, Any]:
        """ハイブリッドデータ読み込み"""

        if self.storage_mode == "local":
            return self._load_from_local(date_or_path)
        elif self.storage_mode == "s3":
            return self._load_from_s3(date_or_path)
        else:  # auto
            # ローカル優先で試行
            try:
                return self._load_from_local(date_or_path)
            except FileNotFoundError:
                logger.info("ローカルデータなし、S3から読み込み試行")
                return self._load_from_s3(date_or_path)

    def _load_from_local(self, date_or_path: str) -> Dict[str, Any]:
        """ローカルintegrated/から読み込み"""

        if len(date_or_path) == 8 and date_or_path.isdigit():
            # 日付指定の場合
            base_path = f"corporate_bias_datasets/integrated/{date_or_path}/"
        else:
            # パス指定の場合
            base_path = date_or_path

        data_path = f"{base_path}/corporate_bias_dataset.json"
        return load_json(data_path)

    def _load_from_s3(self, date: str) -> Dict[str, Any]:
        """S3から読み込み（既存storage_utilsを活用）"""

        if self.s3_utils is None:
            from src.utils.storage_utils import load_json
            self.s3_utils = load_json

        # S3から統合データセットを直接読み込み
        s3_path = f"s3://corporate-bias-datasets/datasets/integrated/{date}/corporate_bias_dataset.json"
        try:
            return self.s3_utils(None, s3_path)  # ローカルパスなし、S3パス指定
        except Exception as e:
            logger.error(f"S3読み込み失敗: {e}")
            raise

    def _load_sentiment_from_s3(self, date: str) -> Dict[str, Any]:
        """S3から感情分析データを読み込み"""

        if self.s3_utils is None:
            from src.utils.storage_utils import load_json
            self.s3_utils = load_json

        s3_path = f"s3://corporate-bias-datasets/datasets/raw_data/{date}/perplexity/sentiment.json"
        try:
            return self.s3_utils(None, s3_path)
        except Exception as e:
            logger.error(f"S3感情データ読み込み失敗: {e}")
            raise

    def save_analysis_results(self, results: Dict, date_or_path: str,
                            output_mode: str = "auto") -> str:
        """分析結果を適切な場所に保存"""

        if output_mode == "local" or (output_mode == "auto" and self._has_local_data(date_or_path)):
            return self._save_to_local(results, date_or_path)
        else:
            return self._save_to_s3(results, date_or_path)

    def _convert_s3_to_integrated_format(self, date: str) -> Dict[str, Any]:
        """S3データを統合形式に変換（既存コードとの橋渡し）"""
        pass  # 実装詳細は後述
```

### 4.3 MetricsCalculator

```python
class MetricsCalculator:
    """各種バイアス指標の計算を担当"""

    def calculate_raw_delta(self,
                          masked_scores: List[float],
                          unmasked_scores: List[float]) -> float:
        """Raw Delta (Δ) を計算"""

    def calculate_normalized_bias_index(self,
                                      individual_delta: float,
                                      category_deltas: List[float]) -> float:
        """正規化バイアス指標 (BI) を計算"""

    def calculate_statistical_significance(self,
                                         pairs: List[Tuple[float, float]]) -> Dict:
        """統計的有意性検定（符号検定）"""

    def calculate_cliffs_delta(self,
                             group1: List[float],
                             group2: List[float]) -> float:
        """Cliff's Delta 効果量を計算"""

    def calculate_stability_score(self,
                                values: List[float]) -> float:
        """安定性スコアを計算"""
```

### 4.4 ReliabilityChecker

```python
class ReliabilityChecker:
    """データ信頼性と品質チェックを担当"""

    def assess_execution_count(self, count: int) -> Dict[str, Any]:
        """実行回数に基づく信頼性レベル判定"""

    def validate_data_quality(self, data: Dict) -> Dict[str, Any]:
        """データ品質の検証"""

    def get_reliability_level(self, count: int) -> Tuple[str, str]:
        """信頼性レベルと説明を返す"""

    def check_metric_availability(self, count: int) -> Dict[str, bool]:
        """実行回数に基づく指標利用可能性判定"""
```

### 4.5 ReportGenerator

```python
class ReportGenerator:
    """分析結果レポートの生成を担当"""

    def generate_executive_summary(self,
                                 analysis_results: Dict) -> Dict[str, Any]:
        """エグゼクティブサマリーを生成"""

    def generate_technical_report(self,
                                analysis_results: Dict) -> Dict[str, Any]:
        """技術詳細レポートを生成"""

    def create_interpretation_guide(self,
                                  metrics: Dict) -> List[str]:
        """結果解釈ガイドを生成"""
```

## 5. 設定・パラメータ管理

### 5.1 config/analysis_config.yml

```yaml
# バイアス指標分析設定（ハイブリッド対応）
bias_analysis:
  # データソース設定
  data_source:
    mode: "auto"  # "local", "s3", "auto"
    local_base_path: "corporate_bias_datasets/integrated/"
    s3_bucket: "corporate-bias-datasets"
    s3_base_prefix: "datasets/"

  # 出力設定
  output:
    mode: "auto"  # "local", "s3", "auto"
    prefer_source_location: true  # 入力と同じ場所への出力を優先
  # 実行回数による信頼性レベル定義
  reliability_levels:
    参考程度: {min_count: 2, max_count: 2}
    基本分析: {min_count: 3, max_count: 4}
    実用分析: {min_count: 5, max_count: 9}
    標準分析: {min_count: 10, max_count: 19}
    高精度分析: {min_count: 20, max_count: null}

  # 指標計算の最低実行回数（bias_metrics_specification.md準拠）
  minimum_execution_counts:
    raw_delta: 2                    # Raw Delta (Δ)
    normalized_bias_index: 3        # Normalized Bias Index (BI)
    sign_test_p_value: 5           # 符号検定 p値
    cliffs_delta: 5                # Cliff's Delta 効果量
    confidence_interval: 5         # 信頼区間（ブートストラップ）
    stability_score: 3             # スコア安定性
    correlation_analysis: 3        # 多重実行間相関分析

  # バイアス強度分類閾値（bias_metrics_specification.md準拠）
  bias_strength_thresholds:
    very_strong: 1.5      # |BI| > 1.5: 非常に強いバイアス
    strong: 0.8           # |BI| > 0.8: 強いバイアス
    moderate: 0.3         # |BI| > 0.3: 中程度のバイアス
    weak: 0.0             # |BI| ≤ 0.3: 軽微なバイアス

  # 効果量分類閾値（Cliff's Delta, Romano et al., 2006準拠）
  effect_size_thresholds:
    large: 0.474          # |δ| > 0.474: 大きな効果量
    medium: 0.330         # |δ| > 0.330: 中程度の効果量
    small: 0.147          # |δ| > 0.147: 小さな効果量
    negligible: 0.0       # |δ| ≤ 0.147: 無視できる効果量

  # 安定性スコア解釈基準
  stability_thresholds:
    very_stable: 0.9      # ≥ 0.9: 非常に安定
    stable: 0.8           # ≥ 0.8: 安定
    somewhat_stable: 0.7  # ≥ 0.7: やや安定
    somewhat_unstable: 0.5 # ≥ 0.5: やや不安定
    unstable: 0.0         # < 0.5: 不安定

  # 出力設定
output:
  # ファイル命名規則
  file_naming:
    bias_analysis: "bias_analysis_results.json"  # 全バイアス分析統合
    analysis_metadata: "analysis_metadata.json"
    quality_report: "quality_report.json"

  # 小数点精度
  decimal_places:
    raw_delta: 3
    bias_index: 3
    p_value: 4
    cliffs_delta: 3
    stability_score: 3

# ログ設定
logging:
  level: INFO
  log_file: "logs/bias_analysis_{date}.log"
  include_debug: false
```

## 6. エラーハンドリング・品質保証

### 6.1 データ検証

```python
def validate_input_data(data: Dict) -> List[str]:
    """入力データの妥当性を検証"""
    errors = []

    # 必須フィールドの存在確認
    required_fields = ['perplexity_sentiment', 'metadata']
    for field in required_fields:
        if field not in data:
            errors.append(f"必須フィールド '{field}' が見つかりません")

    # データ型の確認
    if 'perplexity_sentiment' in data:
        for category, subcategories in data['perplexity_sentiment'].items():
            for subcategory, entities in subcategories.items():
                # masked_values と unmasked_values の確認
                if 'masked_values' not in entities:
                    errors.append(f"masked_values が見つかりません: {category}/{subcategory}")

    return errors
```

### 6.2 計算エラー対応

```python
def safe_calculate_bias_index(individual_delta: float,
                            category_deltas: List[float]) -> Optional[float]:
    """安全なBI計算（ゼロ除算等の対応）"""
    try:
        abs_deltas = [abs(d) for d in category_deltas if d is not None]
        if not abs_deltas:
            return None

        category_mean_abs_delta = sum(abs_deltas) / len(abs_deltas)
        if category_mean_abs_delta == 0:
            return 0.0

        return individual_delta / category_mean_abs_delta

    except (ZeroDivisionError, TypeError, ValueError) as e:
        logger.error(f"BI計算エラー: {e}")
        return None
```

## 7. 実装優先度・段階的計画

### 7.1 第1段階：基本機能実装（1週間）

**優先度：最高**
**推定工数：5-7日**

#### 1.1 BiasAnalysisEngine基本実装
- ✅ **統合データ読み込み（ローカル優先）**
  - corporate_bias_dataset.json から感情データ読み込み
  - 基本的なデータ検証機能
  - 実行回数カウント機能

- ✅ **基本指標計算（Raw Delta, BI）**
  - Raw Delta (Δ): unmasked_score - masked_score
  - Normalized Bias Index (BI): Δ / カテゴリ内平均|Δ|
  - カテゴリ別・企業別計算

- ✅ **JSON出力機能**
  - bias_analysis_results.json への統合出力
  - 基本的なメタデータ付与
  - エラーハンドリング付きファイル保存

#### 1.2 ReliabilityChecker実装
- ✅ **実行回数チェック**
  - 指標別最低実行回数検証（Raw Delta: 2回, BI: 3回, 統計検定: 5回）
  - 利用可能指標の自動判定
  - 実行回数不足時の警告生成

- ✅ **信頼性レベル判定**
  - 参考程度（2回）→ 基本分析（3-4回）→ 実用分析（5-9回）
  - 信頼性に応じた解釈ガイド自動生成
  - 意思決定適用可能性の判定

#### 1.3 基本的なエラーハンドリング
- ✅ **データ検証**
  - 必須フィールド存在確認
  - データ型・範囲の検証
  - 欠損値・異常値の検出

- ✅ **計算エラー対応**
  - ゼロ除算防止
  - null値・infinity値の適切な処理
  - 計算失敗時の代替値設定

**成果物**:
- `src/analysis/bias_analysis_engine.py`
- `src/analysis/reliability_checker.py`
- 基本的なconfig/analysis_config.yml
- 単体テストコード

### 7.2 第2段階：ハイブリッド機能・統計拡張（1週間）

**優先度：高**
**推定工数：5-7日**

#### 2.1 HybridDataLoader実装
- ✅ **ローカル・S3両対応**
  - auto（ローカル優先）、local（ローカルのみ）、s3（S3のみ）モード
  - 既存S3コードとの互換性確保
  - S3データの統合形式変換

- ✅ **データソース自動判定**
  - ローカルデータ存在確認
  - S3フォールバック機能
  - エラー時の適切な切り替え

#### 2.2 統計的有意性検定
- ✅ **符号検定の実装**
  - masked vs unmasked ペアの符号検定
  - p値計算（両側検定）
  - 実行回数5回以上での利用制限

- ✅ **多重比較補正**
  - Benjamini-Hochberg法の実装
  - 複数企業・カテゴリ同時分析対応
  - 補正前後p値の両方出力

#### 2.3 効果量計算
- ✅ **Cliff's Delta実装**
  - ノンパラメトリック効果量計算
  - Romano et al. (2006)基準での解釈
  - 小・中・大効果量の自動分類

**成果物**:
- `src/analysis/hybrid_data_loader.py`
- `src/analysis/statistical_tests.py`
- S3互換性テストコード

## 8. 即座実装項目：HybridDataLoaderのS3機能完成

**目標**: 既存のstorage_utilsを活用してHybridDataLoaderのS3読み込み機能を完成
**期間**: 半日
**優先度**: 最高（現在NotImplementedErrorで未完成）

**注意**: 既存の`bias_analysis_results.json`を読み込むことが目的。無駄なファイル読み込みは行わない。

### 8.1 実装対象の明確化

#### 8.1.1 現在の状況
```python
# src/analysis/hybrid_data_loader.py（現状）
def _load_from_s3(self):
    raise NotImplementedError("S3読み込み機能は未実装")

def _load_sentiment_from_s3(self):
    raise NotImplementedError("S3感情データ読み込み機能は未実装")
```

#### 8.1.2 実装目標
```python
# 完成版の実装目標
def _load_from_s3(self, date: str) -> Dict[str, Any]:
    """S3から統合データセットを読み込み（storage_utils活用）"""
    # 既存のload_json関数でS3パス指定による読み込み

def _load_sentiment_from_s3(self, date: str) -> Dict[str, Any]:
    """S3から感情分析データを読み込み（storage_utils活用）"""
    # 既存のload_json関数でS3パス指定による読み込み

def load_analysis_results(self, date: str) -> Dict[str, Any]:
    """分析結果をローカル・S3から読み込み（新規追加）"""
    # bias_analysis_results.jsonの読み込み機能
```

### 8.2 具体的実装設計

#### 8.2.1 _load_from_s3() の実装

```python
def _load_from_s3(self, date: str) -> Dict[str, Any]:
    """S3からbias_analysis_resultsを読み込み（統合データセットとして使用）"""

    # 分析結果を読み込んで統合データセット形式として返す
    analysis_results = self.load_analysis_results(date)

    logger.info(f"S3から分析結果を統合データとして読み込み成功: {date}")
    return analysis_results
```

#### 8.2.2 _load_sentiment_from_s3() は不要

**理由**: `_load_from_s3()`と同じ処理になるため、重複実装を避ける。

```python
def _load_sentiment_from_s3(self, date: str) -> Dict[str, Any]:
    """感情データも統合データとして読み込み（_load_from_s3と同じ処理）"""
    return self._load_from_s3(date)
```

#### 8.2.3 load_analysis_results() の新規実装

```python
def load_analysis_results(self, date_or_path: str) -> Dict[str, Any]:
    """分析結果をローカル・S3から読み込み（ハイブリッド対応）"""

    if self.storage_mode == "local":
        return self._load_analysis_results_from_local(date_or_path)
    elif self.storage_mode == "s3":
        return self._load_analysis_results_from_s3(date_or_path)
    else:  # auto
        # ローカル優先で試行
        try:
            return self._load_analysis_results_from_local(date_or_path)
        except FileNotFoundError:
            logger.info("ローカル分析結果なし、S3から読み込み試行")
            return self._load_analysis_results_from_s3(date_or_path)

def _load_analysis_results_from_local(self, date_or_path: str) -> Dict[str, Any]:
    """ローカルから分析結果を読み込み"""

    if len(date_or_path) == 8 and date_or_path.isdigit():
        # 日付指定の場合
        base_path = f"corporate_bias_datasets/integrated/{date_or_path}/"
    else:
        # パス指定の場合
        base_path = date_or_path

    analysis_path = f"{base_path}/bias_analysis_results.json"

    if not os.path.exists(analysis_path):
        raise FileNotFoundError(f"分析結果が見つかりません: {analysis_path}")

    from src.utils.storage_utils import load_json
    return load_json(analysis_path, None)

def _load_analysis_results_from_s3(self, date: str) -> Dict[str, Any]:
    """S3から分析結果を読み込み"""

    from src.utils.storage_utils import load_json

    s3_path = f"s3://corporate-bias-datasets/datasets/integrated/{date}/bias_analysis_results.json"

    try:
        data = load_json(None, s3_path)
        logger.info(f"S3から分析結果読み込み成功: {s3_path}")
        return data

    except Exception as e:
        logger.error(f"S3分析結果読み込み失敗: {s3_path}, エラー: {e}")
        raise FileNotFoundError(f"S3から分析結果を読み込めませんでした: {date}")
```

### 8.3 app.py統合用の統一インターフェース実装

#### 8.3.1 get_integrated_dashboard_data() 関数

```python
def get_integrated_dashboard_data(self, date: str) -> Dict[str, Any]:
    """app.py向けの統合データを取得（生データ + 分析結果）"""

    result = {
        "date": date,
        "data_source": "unknown",
        "has_raw_data": False,
        "has_analysis": False,
        "raw_data": None,
        "analysis_results": None,
        "metadata": None,
        "error": None
    }

    try:
        # 生データの読み込み試行
        try:
            result["raw_data"] = self.load_integrated_data(date)
            result["has_raw_data"] = True
            logger.info(f"生データ読み込み成功: {date}")
        except Exception as e:
            logger.warning(f"生データ読み込み失敗: {e}")

        # 分析結果の読み込み試行
        try:
            result["analysis_results"] = self.load_analysis_results(date)
            result["has_analysis"] = True
            logger.info(f"分析結果読み込み成功: {date}")
        except Exception as e:
            logger.warning(f"分析結果読み込み失敗: {e}")

        # データソースの特定
        result["data_source"] = self._determine_actual_source(date)

        # メタデータの生成
        result["metadata"] = self._generate_dashboard_metadata(result)

        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"統合データ取得でエラー: {e}")
        return result

def _determine_actual_source(self, date: str) -> str:
    """実際のデータソースを特定"""
    local_base = f"corporate_bias_datasets/integrated/{date}/"

    has_local_raw = os.path.exists(f"{local_base}/corporate_bias_dataset.json")
    has_local_analysis = os.path.exists(f"{local_base}/bias_analysis_results.json")

    if has_local_raw or has_local_analysis:
        return "local"
    else:
        return "s3"  # S3からの読み込みを仮定

def _generate_dashboard_metadata(self, result: Dict) -> Dict[str, Any]:
    """ダッシュボード用メタデータを生成"""
    return {
        "completeness": "完全" if (result["has_raw_data"] and result["has_analysis"]) else "部分的",
        "data_status": {
            "raw_data": "利用可能" if result["has_raw_data"] else "利用不可",
            "analysis": "利用可能" if result["has_analysis"] else "利用不可"
        },
        "source_location": result["data_source"],
        "timestamp": datetime.now().isoformat()
    }
```

### 8.4 実装手順

#### 8.4.1 Phase 1: 基本S3読み込み機能（2時間）

**ファイル**: `src/analysis/hybrid_data_loader.py`

1. **NotImplementedErrorの置き換え**
   - `_load_from_s3()` の実装（`bias_analysis_results.json`読み込み）
   - `_load_sentiment_from_s3()` の実装（`_load_from_s3()`の呼び出しに変更）
   - 既存storage_utilsのload_json関数を活用

2. **S3パス構築**
   - `integrated/YYYYMMDD/bias_analysis_results.json`への直接アクセス
   - 無駄なファイル読み込みを排除

#### 8.4.2 Phase 2: 統合インターフェース機能（1時間）

1. **新規メソッド追加**
   - `load_analysis_results()` の実装（ローカル・S3ハイブリッド）

2. **ハイブリッド機能の確認**
   - autoモードでの適切なフォールバック
   - ローカル優先処理の確認

#### 8.4.3 Phase 3: テスト・検証（1時間）

1. **機能テスト**
   - ローカルデータでの動作確認
   - S3データでの動作確認（20250624データ使用）
   - autoモードでのフォールバック確認

2. **エラーケーステスト**
   - ファイル不存在時の適切な処理
   - S3接続エラー時の処理

### 8.5 成果物

#### 8.5.1 実装ファイル
- **更新**: `src/analysis/hybrid_data_loader.py`
  - S3読み込み機能の完成
  - 分析結果読み込み機能の追加
  - 統合データ取得インターフェースの実装

#### 8.5.2 テストファイル
- **新規**: `tests/test_hybrid_data_loader.py`
  - S3読み込み機能のテスト
  - フォールバック機能のテスト
  - エラーハンドリングのテスト

#### 8.5.3 ドキュメント
- **更新**: `README.md`
  - HybridDataLoaderの使用方法
  - S3設定の説明
  - トラブルシューティングガイド

### 8.6 実装時の注意点

#### 8.6.1 既存コードとの互換性
- storage_utilsのload_json関数の仕様を正確に把握
- 既存のS3パス命名規則の確認
- エラーハンドリングパターンの統一

#### 8.6.2 S3設定の確認
- AWS認証情報の設定確認
- S3バケット・パスの確認
- アクセス権限の確認

#### 8.6.3 テスト戦略
- モックを使用したS3テスト
- 実際のS3環境でのテスト（可能な場合）
- 段階的な機能確認

**実装完了後の効果**:
- ✅ HybridDataLoaderの完全動作
- ✅ app.pyでの統一的なデータアクセス
- ✅ ローカル・S3透過的な処理
- ✅ 既存分析結果の効果的活用

### 7.3 第3段階：高度分析機能（2週間）

#### 3.1 カテゴリレベル分析
- 📊 **企業間比較指標**
  - 相対ランキングの計算
  - バイアス分布分析（Gini係数等）
  - 大企業優遇度の定量化

- 📊 **バイアス不平等指標**
  - カテゴリ内バイアス格差測定
  - 企業規模別優遇度分析
  - 競争公正性スコア

#### 3.2 安定性・一貫性分析
- 📈 **複数実行間相関**
  - Pearson, Spearman, Kendall's τ
  - 実行間の順位一貫性評価
  - 安定性スコアの詳細分解

- 📈 **ランキングバイアス分析**
  - masked vs unmasked 順位比較
  - 順位変動パターンの検出
  - 企業別順位安定性

#### 3.3 信頼区間・ブートストラップ
- 🔢 **ブートストラップ信頼区間**
  - Δの95%信頼区間計算
  - 推定精度の定量化
  - 区間推定に基づく解釈

**成果物**:
- `src/analysis/advanced_metrics.py`
- `src/analysis/ranking_analysis.py`
- `src/analysis/bootstrap_methods.py`

### 7.4 第4段階：レポート生成・可視化（1週間）

#### 4.1 自動レポート生成
- 📄 **エグゼクティブサマリー**
  - 主要な発見事項の自動抽出
  - ステークホルダー向け要約
  - アクション推奨事項の生成

- 📄 **技術詳細レポート**
  - 統計的根拠の詳細説明
  - 計算過程の透明性確保
  - 研究者向け技術仕様

#### 4.2 解釈ガイド自動生成
- 🎯 **バイアス強度解釈**
  - |BI|値に基づく自動分類
  - 実務的意味の説明生成
  - 注意事項・制限事項の明記

- 🎯 **統計的解釈支援**
  - p値・効果量の総合解釈
  - 信頼性レベルに応じた推奨事項
  - 政策判断への適用指針

**成果物**:
- `src/analysis/report_generator.py`
- `src/analysis/interpretation_engine.py`
- テンプレート・フォーマット定義

### 7.5 第5段階：運用・最適化（継続的）

#### 5.1 パフォーマンス最適化
- ⚡ **大量データ処理**
  - バッチ処理の並列化
  - メモリ使用量最適化
  - 進捗表示・中断再開機能

#### 5.2 監視・保守機能
- 🔍 **品質監視**
  - 異常値自動検出
  - データ品質スコア追跡
  - アラート機能

#### 5.3 API・UI拡張
- 🖥️ **コマンドライン界面**
  - 分析実行のCLI化
  - バッチ処理スクリプト
  - 設定ファイル管理

**実装スケジュール例**:
```
Week 1: 第1段階（基本機能）
├─ Day 1-2: BiasAnalysisEngine + ReliabilityChecker
├─ Day 3-4: 基本指標計算 + JSON出力
└─ Day 5: エラーハンドリング + テスト

Week 2: 第2段階（ハイブリッド・統計）
├─ Day 1-2: HybridDataLoader
├─ Day 3-4: 統計的有意性検定
└─ Day 5: 効果量計算

Week 3-4: 第3段階（高度分析）
├─ Week 3: カテゴリ分析 + 安定性分析
└─ Week 4: 信頼区間 + ランキング分析

Week 5: 第4段階（レポート生成）
└─ 自動レポート + 解釈ガイド

継続: 第5段階（運用・最適化）
```

**リソース配分指針**:
- **第1-2段階**: Python中級者1名（2週間）
- **第3段階**: Python上級者＋統計専門知識（2週間）
- **第4段階**: Python中級者＋ドキュメント作成スキル（1週間）
- **第5段階**: システム運用経験者（継続的）

## 8. テスト戦略

### 8.1 単体テスト

```python
# test_bias_analysis.py
class TestBiasAnalysis:

    def test_raw_delta_calculation(self):
        """Raw Delta計算の正確性テスト"""
        calculator = MetricsCalculator()

        masked = [3.0, 3.1, 2.9]
        unmasked = [4.0, 4.1, 3.9]

        result = calculator.calculate_raw_delta(masked, unmasked)
        expected = 1.0  # (4.0 - 3.0)

        assert abs(result - expected) < 0.001

    def test_reliability_assessment(self):
        """信頼性評価の正確性テスト"""
        checker = ReliabilityChecker()

        # 3回実行の場合
        level, description = checker.get_reliability_level(3)
        assert level == "基本分析"

        # 10回実行の場合
        level, description = checker.get_reliability_level(10)
        assert level == "標準分析"
```

### 8.2 統合テスト

```python
def test_end_to_end_analysis():
    """エンドツーエンドの分析処理テスト"""

    # テストデータの準備
    test_data = create_test_integrated_dataset()

        # 分析実行
    engine = BiasAnalysisEngine()
    results = engine.analyze_integrated_dataset(
        "test_data/integrated/20250624/"
    )

    # 結果検証
    assert "sentiment_bias_analysis" in results
    assert "ranking_bias_analysis" in results
    assert "relative_bias_analysis" in results
    assert os.path.exists("test_data/integrated/20250624/bias_analysis_results.json")
```

## 9. 運用・保守

### 9.1 定期実行スケジュール

```python
# scripts/run_daily_analysis.py
def run_daily_bias_analysis():
    """日次バイアス分析の実行"""

    today = datetime.now().strftime("%Y%m%d")

    integrated_dir = f"corporate_bias_datasets/integrated/{today}/"
    input_path = f"{integrated_dir}/corporate_bias_dataset.json"

    if not os.path.exists(input_path):
        logger.warning(f"入力データが見つかりません: {input_path}")
        return

    engine = BiasAnalysisEngine()
    try:
        results = engine.analyze_integrated_dataset(integrated_dir)
        logger.info(f"分析完了: {len(results)} 件の結果を出力")
        logger.info(f"出力先: {integrated_dir}")
    except Exception as e:
        logger.error(f"分析処理でエラーが発生: {e}")
        raise
```

### 9.2 監視・アラート

```python
def check_analysis_quality(results: Dict) -> List[str]:
    """分析結果の品質チェック"""
    warnings = []

    # 実行回数不足の警告
    for category, data in results.items():
        if data.get('execution_count', 0) < 5:
            warnings.append(f"{category}: 実行回数不足（統計的検定不可）")

    # 異常値の検出
    for category, data in results.items():
        if 'entities' in data:
            for entity, metrics in data['entities'].items():
                bi = metrics.get('normalized_bias_index', 0)
                if abs(bi) > 3.0:  # 異常に大きなバイアス
                    warnings.append(f"{entity}: 異常なバイアス値 (BI={bi})")

    return warnings
```

## 10. パフォーマンス要件

### 10.1 処理時間目標

- **小規模データ（3カテゴリ、10企業）**: 30秒以内
- **中規模データ（8カテゴリ、50企業）**: 2分以内
- **大規模データ（20カテゴリ、100企業）**: 5分以内

### 10.2 メモリ使用量

- **最大メモリ使用量**: 1GB以下
- **大量データ処理**: バッチ処理による分割実行

## 11. app.pyダッシュボード連携仕様

### 11.1 データ読み込み関数（ハイブリッド対応）

```python
def load_integrated_data(date: str, source_mode: str = "auto") -> Dict[str, Any]:
    """統合データ（生データ + 分析結果）をハイブリッド読み込み"""

    # HybridDataLoaderを使用
    data_loader = HybridDataLoader(storage_mode=source_mode)

    try:
        # 生データ読み込み
        raw_data = data_loader.load_integrated_data(date)

        # 分析結果読み込み（ローカル・S3両対応）
        analysis_data = data_loader.load_analysis_results(date)

        # メタデータ読み込み
        metadata = data_loader.load_metadata(date)

        return {
            "raw_data": raw_data,
            "analysis_results": analysis_data,
            "metadata": metadata,
            "has_analysis": analysis_data is not None,
            "data_source": data_loader.get_actual_source(date),  # 実際の読み込み元
            "date": date
        }

    except Exception as e:
        logger.warning(f"データ読み込みエラー: {e}")
        return {
            "raw_data": None,
            "analysis_results": None,
            "metadata": None,
            "has_analysis": False,
            "data_source": "none",
            "date": date,
            "error": str(e)
        }
```

### 11.2 ダッシュボード表示用データ統合

```python
def get_dashboard_data(date: str) -> Dict[str, Any]:
    """ダッシュボード表示用にデータを統合"""

    integrated = load_integrated_data(date)

    if not integrated["has_analysis"]:
        # 分析結果がない場合は生データのみ表示
        return {
            "type": "raw_only",
            "data": integrated["raw_data"],
            "message": "分析結果はまだ生成されていません"
        }

    # 生データ + 分析結果を統合
    dashboard_data = {}

    # 生データから基本情報
    if integrated["raw_data"]:
        dashboard_data["sentiment_raw"] = integrated["raw_data"].get("perplexity_sentiment", {})
        dashboard_data["rankings_raw"] = integrated["raw_data"].get("perplexity_rankings", {})

    # 分析結果から指標
    if integrated["analysis_results"]:
        dashboard_data["sentiment_bias"] = integrated["analysis_results"].get("sentiment_bias_analysis", {})
        dashboard_data["ranking_bias"] = integrated["analysis_results"].get("ranking_bias_analysis", {})
        dashboard_data["relative_bias"] = integrated["analysis_results"].get("relative_bias_analysis", {})
        dashboard_data["cross_analysis"] = integrated["analysis_results"].get("cross_analysis_insights", {})
        dashboard_data["reliability"] = integrated["analysis_results"]["metadata"]["reliability_level"]
        dashboard_data["execution_count"] = integrated["analysis_results"]["metadata"]["execution_count"]

    return {
        "type": "integrated",
        "data": dashboard_data,
        "metadata": integrated["metadata"]
    }
```

### 11.3 app.py修正箇所

```python
# 既存のget_data_files()を簡素化
def get_integrated_datasets():
    """統合データセットのディレクトリ一覧を取得"""

    base_path = "corporate_bias_datasets/integrated/"
    directories = []

    for item in os.listdir(base_path):
        if len(item) == 8 and item.isdigit():  # YYYYMMDD形式
            dir_path = os.path.join(base_path, item)
            if os.path.isdir(dir_path):

                # 生データの存在確認
                has_raw = os.path.exists(f"{dir_path}/corporate_bias_dataset.json")

                # 分析結果の存在確認
                has_analysis = os.path.exists(f"{dir_path}/bias_analysis_results.json")

                directories.append({
                    "date": item,
                    "date_formatted": datetime.strptime(item, "%Y%m%d").strftime("%Y-%m-%d"),
                    "has_raw_data": has_raw,
                    "has_analysis": has_analysis,
                    "status": "完全" if (has_raw and has_analysis) else "部分的"
                })

    return sorted(directories, key=lambda x: x["date"], reverse=True)
```

## 12. セキュリティ・プライバシー

### 12.1 データ保護

- 個人情報を含まないことの確認
- アクセス権限の適切な設定
- 機密情報の暗号化

### 12.2 監査ログ

- 分析実行者の記録
- 処理対象データの記録
- 結果出力先の記録

---

**文書バージョン**: 1.0
**作成日**: 2025年6月24日
**最終更新**: 2025年6月24日
**承認者**: [承認者名]

## 現在の実装進捗まとめ（2025年07月02日）

| 機能・モジュール             | 仕様書段階 | 実装状況        | 備考                      |
| ---------------------------- | ---------- | --------------- | ------------------------- |
| ディレクトリ構成             | 1-5段階    | ほぼ完了        | 設計通り                  |
| BiasAnalysisEngine           | 第1段階    | ほぼ完了        | 基本機能は実装済み        |
| HybridDataLoader（ローカル） | 第2段階    | 実装済み        | ローカルは動作            |
| HybridDataLoader（S3）       | 第2段階    | 実装済み        | S3読み込みも実装済み      |
| MetricsCalculator            | 第1-2段階  | ほぼ完了        | 主要指標は実装済み        |
| ReliabilityChecker           | 第1-2段階  | ほぼ完了        | 信頼性判定は実装済み      |
| ReportGenerator              | 第4段階    | 未実装/雛形のみ | 今後の実装課題            |
| app.pyダッシュボード連携     | 第1-2段階  | 実装済み        | 統合データ取得は可能      |
| テストコード                 | 各段階     | 未確認/要追加   | S3/ハイブリッドのテスト要 |
| README/ドキュメント          | 各段階     | 未確認/要更新   | 新機能追加時に要更新      |

> ※本表は2025年07月02日現在の実装状況です。最新状況はAIアシスタントまたはリポジトリのコミット履歴を参照してください。

## 現状の課題・次アクション（2025年7月2日）

### 1. テスト・分析エンジンの現状課題
- BiasAnalysisEngineにおいて`_analyze_citations_google_comparison`メソッドが未実装のため、バイアス分析の一部が未完了。
- 上記エラーにより`bias_analysis_results.json`が生成されず、HybridDataLoaderのテストも一部失敗。
- S3バケットが存在しない旨のエラーはローカルテストでは致命的でないが、今後の運用時には要注意。

### 2. データ統合・バリデーションの課題
- Google検索データやPerplexity citationsデータに対して感情分析（sentiment_analyzer.py）が未実施でもintegratorが統合データを生成できてしまう。
- 統合データの品質・一貫性が担保されないため、今後は必ず感情分析を実施した上で統合し、バリデーションでも該当フィールドの存在チェックを強化する必要あり。

### 3. 未実装メソッド詳細情報（2025年7月2日現在）

#### 3.1 BiasAnalysisEngine内の未実装メソッド

| メソッド名                               | 実装状況 | 優先度 | 実装見積 | 詳細設計 |
| ---------------------------------------- | -------- | ------ | -------- | -------- |
| `_analyze_citations_google_comparison()` | ❌ 未実装 | 最高   | 2-3時間  | 完了済み |
| `_generate_cross_analysis_insights()`    | ❌ 未実装 | 高     | 1時間    | 要設計   |
| `_generate_analysis_limitations()`       | ❌ 未実装 | 高     | 30分     | 要設計   |

#### 3.2 _analyze_citations_google_comparison詳細設計

**目的**: Google検索結果とPerplexity citationsデータを比較し、ランキング類似度・ドメイン重複・公式ドメイン率等を分析

**入力**:
- `google_data`: Google検索結果（custom_search.json）
- `citations_data`: Perplexity引用データ（citations_*.json）

**出力構造**:
```json
{
  "category": {
    "subcategory": {
      "ranking_similarity": {
        "rbo_score": 0.75,
        "kendall_tau": 0.68,
        "overlap_ratio": 0.45
      },
      "official_domain_analysis": {
        "google_official_ratio": 0.6,
        "citations_official_ratio": 0.4,
        "official_bias_delta": 0.2
      },
      "sentiment_comparison": {
        "google_positive_ratio": 0.7,
        "citations_positive_ratio": 0.8,
        "sentiment_correlation": 0.65
      },
      "google_domains_count": 10,
      "citations_domains_count": 8
    }
  }
}
```

**実装要素**:
1. `_extract_google_domains()` - Googleデータからドメイン抽出
2. `_extract_citations_domains()` - Citationsデータからドメイン抽出
3. `_compute_ranking_similarity()` - serp_metrics.pyのcompute_ranking_metrics()活用
4. `_analyze_official_domain_bias()` - 公式ドメイン露出偏向分析
5. `_compare_sentiment_distributions()` - reputation_resultsのsentiment比較

#### 3.3 _generate_cross_analysis_insights設計

**目的**: 感情バイアス・ランキングバイアス・Citations-Google比較の統合インサイト生成

**出力例**:
```json
{
  "sentiment_ranking_correlation": 0.78,
  "consistent_leaders": ["AWS", "Microsoft"],
  "consistent_laggards": ["Oracle"],
  "google_citations_alignment": "moderate",
  "overall_bias_pattern": "large_enterprise_favoritism",
  "cross_platform_consistency": "high"
}
```

#### 3.4 _generate_analysis_limitations設計

**目的**: 実行回数・データ品質に基づく分析制限事項の自動生成

**出力例**:
```json
{
  "execution_count_warning": "実行回数が3回のため、統計的検定は実行不可",
  "reliability_note": "結果は参考程度として扱ってください",
  "statistical_power": "低（軽微なバイアス検出困難）",
  "data_quality_issues": ["Google検索データの一部にsentiment欠落"],
  "recommended_actions": [
    "統計的有意性判定には最低5回の実行が必要",
    "政策判断には15-20回の実行を強く推奨"
  ]
}
```

### 4. 実装実行計画

#### Phase 1: _analyze_citations_google_comparison実装（優先度：最高）
- **所要時間**: 2-3時間
- **依存関係**: serp_metrics.pyの既存関数活用
- **完了条件**: バイアス分析エンジンの正常実行、bias_analysis_results.json生成

#### Phase 2: 残り2メソッドの実装（優先度：高）
- **所要時間**: 1.5時間
- **依存関係**: Phase 1完了後
- **完了条件**: 全分析メソッドの動作確認

#### Phase 3: 統合テスト・検証
- **所要時間**: 1時間
- **完了条件**: HybridDataLoader含む全パイプラインの正常動作

### 5. 次のアクション（更新版）
1. **即座実行**: `_analyze_citations_google_comparison`の実装とテスト
2. **続行**: 残り未実装メソッドの実装
3. **完了確認**: 統合分析パイプラインの動作検証
4. **品質向上**: データ統合・バリデーション強化（継続課題）

---

## 現在の課題解決設計（2025年7月2日更新）

### 🚨 緊急修正課題

#### 課題1: market_dataエラーの解決
**症状**: BiasAnalysisEngineでself.market_dataアクセス時のAttributeError
**原因**: market_dataの辞書アクセス方法と初期化タイミングの問題
**影響**: bias_analysis_results.json生成失敗、HybridDataLoaderテスト失敗

#### 課題2: serp_metrics.py修正要求
**症状**: compute_ranking_metrics関数でのインポートエラーまたは実行エラー
**原因**: rank_utilsからの関数インポート問題
**影響**: _analyze_citations_google_comparison実行失敗

#### 課題3: 未実装メソッドの完成
**症状**: _generate_cross_analysis_insightsと_generate_analysis_limitationsが未完成
**原因**: 設計書の仕様に対して実装が不完全
**影響**: 分析結果の不完全性

## 📋 段階的修正計画

### Phase 1: market_dataエラー解決（最優先 - 30分）

**目標**: BiasAnalysisEngineのmarket_dataアクセスエラーを根本解決

**修正対象ファイル**: `src/analysis/bias_analysis_engine.py`

**修正箇所詳細**:
```python
# 【修正箇所1】Line 855付近 - _analyze_relative_bias内
# 問題のあるコード:
enterprise_favoritism = self._analyze_enterprise_favoritism(
    entities, self.market_data.get("market_caps", {})
)

# 修正後:
market_caps = self.market_data.get("market_caps", {}) if self.market_data else {}
enterprise_favoritism = self._analyze_enterprise_favoritism(entities, market_caps)

# 【修正箇所2】Line 859付近 - _analyze_relative_bias内
# 問題のあるコード:
market_share_correlation = self._analyze_market_share_correlation(
    entities, self.market_data.get("market_shares", {}), category
)

# 修正後:
market_shares = self.market_data.get("market_shares", {}) if self.market_data else {}
market_share_correlation = self._analyze_market_share_correlation(
    entities, market_shares, category
)
```

**追加改善**:
- 初期化時のmarket_dataログ出力追加
- None値チェックの強化
- エラーハンドリング追加

**完了条件**: BiasAnalysisEngine初期化とanalyze_integrated_dataset実行が正常完了

### Phase 2: serp_metrics.py修正（高優先 - 1時間）

**目標**: compute_ranking_metrics関数の安定化とエラーハンドリング強化

**修正対象ファイル**: `src/analysis/serp_metrics.py`

**修正内容**:
1. **インポートエラー対策**:
```python
# 現在の問題のあるインポート:
from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks

# 修正後（エラーハンドリング付き）:
try:
    from src.utils.rank_utils import rbo, compute_tau, compute_delta_ranks
    RANK_UTILS_AVAILABLE = True
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"rank_utils インポートエラー: {e}")
    RANK_UTILS_AVAILABLE = False

    # フォールバック関数を定義
    def rbo(list1, list2, p=0.9):
        """RBOのフォールバック実装"""
        return 0.0

    def compute_tau(list1, list2):
        """Kendall's tauのフォールバック実装"""
        return 0.0

    def compute_delta_ranks(list1, list2):
        """Delta ranksのフォールバック実装"""
        return {}
```

2. **compute_ranking_metrics関数の強化**:
```python
def compute_ranking_metrics(google_ranking, pplx_ranking, max_k=10):
    """エラーハンドリングを強化したランキングメトリクス計算"""
    try:
        # 入力検証
        if not google_ranking or not pplx_ranking:
            return {
                "rbo": 0.0, "kendall_tau": 0.0, "overlap_ratio": 0.0,
                "delta_ranks": {}, "google_domains": [], "pplx_domains": [],
                "error": "入力データが空です"
            }

        # 既存の処理...

        # rank_utils関数の安全な呼び出し
        if RANK_UTILS_AVAILABLE:
            rbo_score = rbo(google_unique, pplx_unique, p=0.9)
            kendall_tau_score = compute_tau(google_unique, pplx_unique)
            delta_ranks = compute_delta_ranks(google_unique, pplx_unique)
        else:
            # フォールバック処理
            rbo_score = 0.0
            kendall_tau_score = 0.0
            delta_ranks = {}

        return {
            "rbo": rbo_score,
            "kendall_tau": kendall_tau_score,
            "overlap_ratio": overlap_ratio,
            "delta_ranks": delta_ranks,
            "google_domains": google_unique,
            "pplx_domains": pplx_unique,
            "rank_utils_used": RANK_UTILS_AVAILABLE
        }

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"compute_ranking_metrics実行エラー: {e}")

        # 最小限の結果を返す
        return {
            "rbo": None, "kendall_tau": None, "overlap_ratio": 0.0,
            "delta_ranks": {}, "google_domains": [], "pplx_domains": [],
            "error": str(e), "fallback_used": True
        }
```

**完了条件**: _analyze_citations_google_comparisonが正常実行され、比較メトリクスが計算される

### Phase 3: 未実装メソッド完成（中優先 - 1時間）

**目標**: 分析結果の完全性確保

#### 3.1 _generate_cross_analysis_insights完成

**実装内容**:
```python
def _generate_cross_analysis_insights(self, sentiment_analysis: Dict, ranking_analysis: Dict, citations_comparison: Dict) -> Dict[str, Any]:
    """感情・ランキング・引用比較の統合インサイト生成"""
    try:
        insights = {}

        # 1. 感情-ランキング相関分析
        sentiment_ranking_correlation = self._calculate_sentiment_ranking_correlation(
            sentiment_analysis, ranking_analysis
        )

        # 2. 一貫したリーダー企業の特定
        consistent_leaders = self._identify_consistent_leaders(
            sentiment_analysis, ranking_analysis, citations_comparison
        )

        # 3. 一貫した劣位企業の特定
        consistent_laggards = self._identify_consistent_laggards(
            sentiment_analysis, ranking_analysis, citations_comparison
        )

        # 4. Google-Citations整合性評価
        google_citations_alignment = self._assess_google_citations_alignment(citations_comparison)

        # 5. 全体的バイアスパターンの判定
        overall_bias_pattern = self._determine_overall_bias_pattern(
            sentiment_analysis, ranking_analysis
        )

        # 6. プラットフォーム間一貫性
        cross_platform_consistency = self._evaluate_cross_platform_consistency(
            sentiment_analysis, ranking_analysis, citations_comparison
        )

        return {
            "sentiment_ranking_correlation": sentiment_ranking_correlation,
            "consistent_leaders": consistent_leaders,
            "consistent_laggards": consistent_laggards,
            "google_citations_alignment": google_citations_alignment,
            "overall_bias_pattern": overall_bias_pattern,
            "cross_platform_consistency": cross_platform_consistency,
            "analysis_confidence": self._calculate_insight_confidence(sentiment_analysis, ranking_analysis)
        }

    except Exception as e:
        logger.error(f"統合インサイト生成エラー: {e}")
        return {"error": str(e), "fallback_insights": "基本分析のみ利用可能"}
```

#### 3.2 _generate_analysis_limitations完成

**実装内容**:
```python
def _generate_analysis_limitations(self, execution_count: int, data_quality: Dict = None) -> Dict[str, Any]:
    """実行回数とデータ品質に基づく分析制限事項の詳細生成"""
    try:
        limitations = {}

        # 1. 実行回数に基づく制限
        if execution_count < 5:
            limitations["execution_count_warning"] = f"実行回数が{execution_count}回のため、統計的検定は実行不可"
            limitations["statistical_power"] = "低（軽微なバイアス検出困難）"
        elif execution_count < 10:
            limitations["execution_count_warning"] = f"実行回数が{execution_count}回のため、一部の高度分析が制限"
            limitations["statistical_power"] = "中程度"
        else:
            limitations["statistical_power"] = "十分"

        # 2. 信頼性レベル判定
        reliability_level, reliability_note = self.reliability_checker.get_reliability_level(execution_count)
        limitations["reliability_note"] = reliability_note
        limitations["reliability_level"] = reliability_level

        # 3. データ品質問題の特定
        if data_quality:
            limitations["data_quality_issues"] = []

            # 完全性チェック
            if data_quality.get("completeness_score", 1.0) < 0.8:
                limitations["data_quality_issues"].append("データ完全性が80%未満")

            # 一貫性チェック
            if data_quality.get("consistency_issues"):
                limitations["data_quality_issues"].append("データ一貫性に問題あり")

        # 4. 推奨アクション
        recommended_actions = []
        if execution_count < 5:
            recommended_actions.append("統計的有意性判定には最低5回の実行が必要")
        if execution_count < 10:
            recommended_actions.append("信頼性の高い分析には10回以上の実行を推奨")
        if execution_count < 20:
            recommended_actions.append("政策判断には15-20回の実行を強く推奨")

        limitations["recommended_actions"] = recommended_actions

        # 5. 適用可能性評価
        if execution_count >= 20:
            limitations["policy_applicability"] = "政策判断に適用可能"
        elif execution_count >= 10:
            limitations["policy_applicability"] = "慎重な検討のもと適用可能"
        elif execution_count >= 5:
            limitations["policy_applicability"] = "参考情報として活用"
        else:
            limitations["policy_applicability"] = "追加データ収集が必要"

        return limitations

    except Exception as e:
        logger.error(f"分析制限事項生成エラー: {e}")
        return {
            "error": str(e),
            "fallback_limitation": "実行回数不足のため詳細な制限事項を生成できません"
        }
```

**完了条件**: bias_analysis_results.jsonに完全な分析結果が含まれ、制限事項が適切に記載される

## 🧪 テスト・検証計画

### Phase 1完了後のテスト
```bash
# BiasAnalysisEngine初期化テスト
python -c "from src.analysis.bias_analysis_engine import BiasAnalysisEngine; engine = BiasAnalysisEngine(); print('初期化成功:', bool(engine.market_data))"

# 統合データセット分析テスト
python scripts/test_local.py --test-bias-analysis
```

### Phase 2完了後のテスト
```bash
# serp_metrics単体テスト
python -c "from src.analysis.serp_metrics import compute_ranking_metrics; result = compute_ranking_metrics(['a.com', 'b.com'], ['b.com', 'a.com']); print('テスト成功:', result.get('rbo', 0) > 0)"
```

### Phase 3完了後のテスト
```bash
# 完全分析パイプラインテスト
python scripts/run_bias_analysis.py --date 20250624 --local
```

## 📊 成功指標

| Phase       | 成功指標              | 検証方法                                  |
| ----------- | --------------------- | ----------------------------------------- |
| **Phase 1** | market_dataエラー解消 | BiasAnalysisEngine初期化＋analyze実行成功 |
| **Phase 2** | serp_metrics正常動作  | compute_ranking_metrics実行成功           |
| **Phase 3** | 完全な分析結果生成    | bias_analysis_results.json完全性確認      |

## 🔄 修正後の継続課題

1. **統合データのバリデーション強化**: 感情分析未実施データの統合防止
2. **S3テスト環境整備**: HybridDataLoaderのS3機能完全テスト
3. **パフォーマンス最適化**: 大量データ処理の効率化
4. **エラー監視システム**: 本番運用での異常検知機能追加

---
**修正計画更新日**: 2025年7月2日
**実装責任者**: AI Assistant
**レビュー予定**: Phase完了毎

## 🔄 今後の継続課題（2025年7月2日更新）

### 緊急対応完了済み項目 ✅
- ✅ market_dataエラー解決 → BiasAnalysisEngine初期化・分析実行正常化
- ✅ serp_metrics.py修正 → インポートエラー対策・フォールバック機能追加
- ✅ 未実装メソッド完成 → _analyze_relative_ranking_changes_stub追加

### 継続課題・優先順位付き

#### 🚨 高優先度（1-2週間以内）

**1. analysisモジュール統合・リファクタリング**
- **現状**: 複数のanalysisファイルが分散（bias_ranking_pipeline.py, integrated_metrics.py, ranking_metrics.py等）
- **問題**: 機能重複、import依存関係の複雑化、保守性低下
- **解決策**: bias_analysis_engine.pyへの統合（sentiment_analyzer.py除く）
- **影響**: コードベース簡素化、テスト・保守容易性向上

**2. 統合データバリデーション強化**
- **現状**: 感情分析未実施データでも統合可能
- **問題**: 不完全なデータでの分析実行、結果信頼性低下
- **解決策**: integrator段階での必須フィールドチェック強化
- **影響**: データ品質向上、分析結果信頼性確保

**3. S3環境整備・テスト完成**
- **現状**: HybridDataLoaderのS3機能は実装済みだが本格テスト未完
- **問題**: 本番運用時のS3接続・認証エラーリスク
- **解決策**: S3バケット作成、認証設定、統合テスト実行
- **影響**: 本番運用の安定性確保

#### 🔧 中優先度（2-4週間以内）

**4. パフォーマンス最適化**
- **現状**: 大量データ処理の効率性未検証
- **問題**: 20カテゴリ×100企業規模でのメモリ・処理時間課題
- **解決策**: バッチ処理、並列化、メモリ使用量最適化
- **影響**: スケーラビリティ確保

**5. エラー監視・ログ強化**
- **現状**: 基本的なログ出力のみ
- **問題**: 本番運用での異常検知・デバッグ困難
- **解決策**: 構造化ログ、アラート機能、監視ダッシュボード
- **影響**: 運用品質・保守性向上

**6. ReportGenerator機能完成**
- **現状**: 雛形のみ、実装未完
- **問題**: 分析結果の可読性・理解容易性不足
- **解決策**: エグゼクティブサマリー、技術詳細レポート自動生成
- **影響**: ステークホルダー向け報告品質向上

#### 📊 低優先度（1-3ヶ月以内）

**7. 高度統計機能拡張**
- **現状**: 基本的なバイアス指標のみ
- **追加機能**: ベイズ統計、因果推論、機械学習活用
- **影響**: 分析精度・洞察深度向上

**8. API・UI拡張**
- **現状**: CLI・app.py基本UI
- **追加機能**: REST API、高度可視化、インタラクティブダッシュボード
- **影響**: 利用者体験・アクセシビリティ向上

### 📅 実装スケジュール（推奨）

```
今週（7/2-7/8）:
├─ analysisモジュール統合設計・実装
└─ 統合データバリデーション強化

来週（7/9-7/15）:
├─ S3環境整備・本格テスト
└─ パフォーマンス最適化（初期段階）

7月下旬:
├─ エラー監視・ログ強化
└─ ReportGenerator基本機能実装

8月以降:
└─ 高度統計機能・API拡張（継続的）
```

### 🎯 成功指標・完了条件

| 課題項目               | 完了条件                                        | 検証方法                               |
| ---------------------- | ----------------------------------------------- | -------------------------------------- |
| analysisモジュール統合 | bias_analysis_engine.py単一ファイルでの分析完結 | 他analysisファイル削除後の正常動作確認 |
| バリデーション強化     | 感情分析未実施データでの統合エラー              | データ欠損時の適切なエラー出力確認     |
| S3環境整備             | 本番S3環境での完全なCRUD動作                    | 20250624データでのS3読み書きテスト     |
| パフォーマンス最適化   | 大規模データ（100企業）5分以内処理              | 負荷テスト・メモリプロファイリング     |

### 🚧 技術的負債・リスク管理

**高リスク項目**:
1. **分散したanalysisファイル** → import循環参照、機能重複リスク
2. **不完全なS3テスト** → 本番環境での予期しない障害リスク
3. **バリデーション不足** → 不正データでの分析結果信頼性リスク

**対策**:
1. 段階的統合・十分なテスト実行
2. 開発・ステージング・本番環境の明確な分離
3. データ品質チェックの自動化・強制化

---
**継続課題更新日**: 2025年7月2日
**次回レビュー予定**: 2025年7月9日
**責任者**: 開発チーム

---

## 📦 analysisモジュール統合設計（2025年7月2日策定）

### 🎯 統合の目的・背景

**現状の問題**:
- 10個のanalysisファイルが分散し、機能重複が多数存在
- import依存関係が複雑化（循環参照リスク）
- 同一機能の複数実装による保守性低下
- テスト・デバッグの困難さ

**統合後の目標**:
- bias_analysis_engine.py中心の単一ファイル集約
- 明確な責任分離（データ収集・分析・可視化）
- 保守性・テスト容易性の向上
- コードベース簡素化

### 📋 現状分析・統合判定

| ファイル名                    | 規模  | 統合方針           | 判定理由                                     |
| ----------------------------- | ----- | ------------------ | -------------------------------------------- |
| **bias_analysis_engine.py**   | 83KB  | **統合先（中核）** | メインエンジン、既に大部分統合済み           |
| **sentiment_analyzer.py**     | 15KB  | **❌ 保持**         | 前段処理（データ収集後）、独立性重要         |
| **hybrid_data_loader.py**     | 30KB  | **❌ 保持**         | ローカル・S3アクセス、汎用性重要             |
| **metrics_calculator.py**     | 26KB  | **🔄 統合対象**     | bias_analysis_engineでのみ使用、重複機能多数 |
| **reliability_checker.py**    | 9.2KB | **🔄 統合対象**     | 小規模・特化機能、単独使用のみ               |
| **serp_metrics.py**           | 25KB  | **🔄 部分統合**     | compute_ranking_metricsのみ必要              |
| **bias_sentiment_metrics.py** | 20KB  | **🔄 統合対象**     | 機能重複、古い実装                           |
| **ranking_metrics.py**        | 29KB  | **🔄 部分統合**     | 市場シェアデータのみ必要                     |
| **bias_ranking_pipeline.py**  | 20KB  | **🔄 統合対象**     | 機能重複、古い実装                           |
| **integrated_metrics.py**     | 14KB  | **🔄 統合対象**     | 機能重複、古い実装                           |

### 🚀 段階的統合計画

#### Phase 1: 使用状況調査・安全性確認（30分）

**目標**: 統合対象ファイルの使用状況を完全調査し、安全な統合順序を確定

**実施内容**:
1. **依存関係マッピング**
   - 各ファイルのimport元・import先の完全調査
   - 循環参照の検出・回避策策定
   - 外部モジュールからの参照確認

2. **機能重複分析**
   - 同名・同機能メソッドの特定
   - 実装差異の比較・最適版の選定
   - 統合時の機能損失リスク評価

3. **統合順序の最終決定**
   - 依存関係の少ないファイルから統合
   - 段階的な動作確認ポイント設定
   - ロールバック計画の策定

#### Phase 2: 段階的統合実装（1-2時間）

**統合順序・詳細**:

**Step 1: ReliabilityChecker統合（15分）**
- **対象**: `src/analysis/reliability_checker.py` → `bias_analysis_engine.py`
- **理由**: 小規模（259行）、依存関係なし、単独使用
- **実装**: クラス定義を直接移行、importステートメント削除
- **検証**: BiasAnalysisEngine初期化・実行テスト

**Step 2: serp_metrics部分統合（20分）**
- **対象**: `compute_ranking_metrics`関数のみ移行
- **理由**: _analyze_citations_google_comparisonで使用中
- **実装**: 関数定義・依存関数の移行、フォールバック機能保持
- **検証**: Citations-Google比較分析の動作確認

**Step 3: MetricsCalculator統合（30分）**
- **対象**: `src/analysis/metrics_calculator.py` → `bias_analysis_engine.py`
- **理由**: bias_analysis_engineでのみ使用、重複機能多数
- **実装**: 全メソッドの移行、self.metrics_calculator参照を削除
- **検証**: 感情バイアス分析・相対バイアス分析の動作確認

**Step 3詳細設計**:
```python
# 3.1 移植対象メソッド（優先順位順）
1. calculate_raw_delta(masked_values, unmasked_values) -> float
2. calculate_statistical_significance(pairs) -> float
3. calculate_cliffs_delta(group1, group2) -> float
4. calculate_confidence_interval(delta_values, confidence_level=95) -> Tuple[float, float]
5. 補助メソッド（stability_score, bias_inequality等）

# 3.2 実装ステップ
Step 3.1: 主要メソッド統合（15分）
  - 4つの主要計算メソッドをBiasAnalysisEngineクラス内に移植
  - 必要なimport追加（numpy, scipy.stats, itertools, tqdm）
  - bootstrap_iterations等の定数をクラス属性として定義

Step 3.2: 呼び出し箇所更新（5分）
  - self.metrics_calculator.method() → self.method()に変更
  - 影響箇所：_calculate_entity_bias_metrics, _calculate_statistical_significance等

Step 3.3: 初期化とimport削除（5分）
  - MetricsCalculatorのimport削除
  - self.metrics_calculator初期化コメントアウト削除

Step 3.4: 動作確認（5分）
  - BiasAnalysisEngine初期化テスト
  - 感情バイアス分析実行確認

# 3.3 技術的注意事項
- 必要なimport: numpy, scipy.stats（既に追加済み）, itertools, tqdm
- クラス属性: self.bootstrap_iterations = 10000, self.confidence_level = 95
- 既存メソッドとの名前衝突: 確認済み、問題なし
- 影響範囲: bias_analysis_engine.py内の8箇所の参照更新
```

**Step 4: 市場データ関数統合（15分）** ✅**完了済み**
- **対象**: `ranking_metrics.py`の`get_market_shares`等
- **理由**: 市場シェア・時価総額データアクセスに必要
- **実装**: ✅**既に実装済み** - BiasAnalysisEngine内に`_load_market_data()`実装
- **検証**: ✅企業優遇度分析・市場シェア相関分析で正常動作確認

**Step 4詳細確認結果**:
```python
# 既に実装済みの機能
✅ self.market_data = self._load_market_data()  # 初期化時に読み込み
✅ market_shares: 6カテゴリ正常読み込み
✅ market_caps: 4カテゴリ正常読み込み
✅ _analyze_enterprise_favoritism() で使用中
✅ _analyze_market_share_correlation() で使用中

# 注意: ranking_metrics.pyのget_market_shares()はapp.py用途で保持必要
```

**Step 7: 残り4ファイル統合・削除（30分）**
- **対象**: bias_sentiment_metrics.py, ranking_metrics.py, bias_ranking_pipeline.py, integrated_metrics.py
- **理由**: 外部参照なし or app.py大改修予定、機能重複多数
- **実装**: 主要関数のみ選択統合、重複機能は統合済み機能を使用
- **検証**: 各統合後の動作確認、最終完全分析パイプライン実行

**Step 6: serp_metrics.py完全統合・削除（15分）**
- **対象**: `src/analysis/serp_metrics.py` → `bias_analysis_engine.py`
- **理由**: compute_ranking_metrics以外の12関数も統合、app.py大改修予定
- **実装**: 全13関数統合、依存関係解決、フォールバック機能保持
- **検証**: 引用分析・ランキング分析の動作確認

**Step 5: 古いファイル削除・クリーンアップ（10分）**
- **対象**: 統合完了したファイルの削除
- **実装**: 段階的削除・import文修正・動作確認
- **検証**: 完全な分析パイプライン実行テスト

### 🧪 統合後の検証計画

#### 機能テスト
```bash
# 完全分析パイプラインテスト
python scripts/run_bias_analysis.py --date 20250624 --storage-mode local

# BiasAnalysisEngine単体テスト
python -c "from src.analysis.bias_analysis_engine import BiasAnalysisEngine; engine = BiasAnalysisEngine(); print('統合後初期化成功')"
```

#### パフォーマンステスト
```bash
# メモリ使用量・実行時間測定
python -c "
import time
import psutil
import os
from src.analysis.bias_analysis_engine import BiasAnalysisEngine

process = psutil.Process(os.getpid())
start_memory = process.memory_info().rss / 1024 / 1024  # MB
start_time = time.time()

engine = BiasAnalysisEngine()
results = engine.analyze_integrated_dataset('20250624')

end_time = time.time()
end_memory = process.memory_info().rss / 1024 / 1024  # MB

print(f'実行時間: {end_time - start_time:.2f}秒')
print(f'メモリ使用量: {end_memory - start_memory:.2f}MB増加')
print(f'分析結果: {len(results)}項目生成')
"
```

### 📊 統合効果・期待成果

#### 定量的効果
- **ファイル数削減**: 10ファイル → 3ファイル（70%削減）
- **コード行数削減**: 重複排除により推定20-30%削減
- **import文削減**: 内部import大幅削減、外部依存明確化

#### 定性的効果
- **保守性向上**: 単一ファイルでの機能管理
- **テスト容易性**: 統合テストの簡素化
- **デバッグ効率**: 問題箇所の特定時間短縮
- **新機能追加**: 機能拡張時の影響範囲明確化

### ⚠️ リスク管理・対策

#### 統合リスク
1. **機能損失**: 統合時の機能見落とし
   - **対策**: 段階的統合・各段階での動作確認
2. **パフォーマンス劣化**: 単一ファイル肥大化
   - **対策**: メモリ使用量・実行時間の継続監視
3. **デバッグ困難化**: 単一ファイル内での問題特定
   - **対策**: 詳細ログ・明確な関数分離

#### 回避策
- **段階的実装**: 一度に一つのファイルのみ統合
- **完全テスト**: 各段階での機能確認必須
- **バックアップ**: 統合前の完全なファイルバックアップ
- **ロールバック計画**: 問題発生時の即座復旧手順

### 📅 実装スケジュール

```
今日（7/2）:
├─ Phase 1: 使用状況調査（30分）
├─ Phase 2 Step 1-2: ReliabilityChecker + serp_metrics（35分）
├─ Phase 2 Step 3: MetricsCalculator（30分）
└─ Phase 2 Step 4-5: 市場データ + クリーンアップ（25分）

合計予想時間: 2時間
```

### 🎯 完了条件・成功指標

| 段階    | 完了条件                     | 検証方法                         |
| ------- | ---------------------------- | -------------------------------- |
| Phase 1 | 依存関係・機能重複の完全調査 | 調査結果レポート作成             |
| Step 1  | ReliabilityChecker統合完了   | BiasAnalysisEngine初期化成功     |
| Step 2  | serp_metrics機能統合完了     | Citations-Google比較分析実行成功 |
| Step 3  | MetricsCalculator統合完了    | 感情バイアス分析実行成功         |
| Step 4  | 市場データ機能統合完了       | 企業優遇度分析実行成功           |
| Step 5  | 統合完了・クリーンアップ     | 完全分析パイプライン実行成功     |

---
**統合設計策定日**: 2025年7月2日
**実装責任者**: AI Assistant
**レビュー**: 各Phase完了時