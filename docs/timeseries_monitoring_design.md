# 時系列変化監視機能 詳細設計書

## 1. 概要

### 1.1 目的
企業優遇バイアス分析における時系列データを収集・監視し、顕著な変化を検知した際に自動SNS投稿を行う機能の詳細設計。

### 1.2 対象機能
- **感情スコア変化監視**: Raw Delta、Normalized Bias Indexの時系列変化
- **ランキング変化監視**: Google・Perplexity検索結果の順位変動
- **Perplexity分析変化監視**: 公式非公式率、ポジティブネガティブ率の変化
- **クロスプラットフォーム比較監視**: RBO、Kendall Tauの変化
- 時系列データ収集・保存
- 変化率計算・閾値判定
- 統計的有意性検証
- 自動投稿トリガー

### 1.3 対象外機能
- バイアス指標閾値監視
- 市場構造変化検知
- 高度な画像生成

## 2. システム設計

### 2.1 アーキテクチャ概要

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  分析エンジン    │───▶│  時系列監視     │───▶│  SNS投稿        │
│  (既存)         │    │  モジュール     │    │  モジュール     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  時系列DB       │
                       │  (SQLite/JSON)  │
                       └─────────────────┘
```

### 2.2 モジュール構成

```
src/
├── sns/
│   ├── __init__.py
│   ├── timeseries_monitor.py      # 時系列監視メイン
│   ├── data_collector.py          # データ収集
│   ├── change_detector.py         # 変化検知
│   ├── statistical_validator.py   # 統計検証
│   ├── posting_trigger.py         # 投稿トリガー
│   └── timeseries_db.py           # データベース操作
```

## 3. データ設計

### 3.1 時系列データ構造

#### 3.1.1 エンティティ別時系列データ
```json
{
  "entity_id": "aws_cloud_computing",
  "category": "クラウドサービス",
  "subcategory": "クラウドコンピューティング",
  "timeseries_data": [
    {
      "date": "2025-01-20",
      "sentiment_metrics": {
        "raw_delta": 2.3,
        "normalized_bias_index": 1.8,
        "p_value": 0.02,
        "cliffs_delta": 0.45
      },
      "ranking_metrics": {
        "google_rank": 1,
        "perplexity_rank": 2,
        "rank_change": -1,
        "rbo_score": 0.85,
        "kendall_tau": 0.72
      },
      "perplexity_metrics": {
        "official_ratio": 0.75,
        "positive_ratio": 0.68,
        "negative_ratio": 0.12,
        "neutral_ratio": 0.20
      },
      "execution_count": 5,
      "reliability_level": "実用分析"
    }
  ]
}
```

#### 3.1.2 カテゴリ別時系列データ
```json
{
  "category": "クラウドサービス",
  "subcategory": "クラウドコンピューティング",
  "timeseries_data": [
    {
      "date": "2025-01-20",
      "sentiment_summary": {
        "avg_raw_delta": 1.8,
        "avg_normalized_bias_index": 1.2,
        "significant_entities": 3
      },
      "ranking_summary": {
        "avg_rbo_score": 0.78,
        "avg_kendall_tau": 0.65,
        "ranking_stability": "中"
      },
      "perplexity_summary": {
        "avg_official_ratio": 0.72,
        "avg_positive_ratio": 0.61,
        "avg_negative_ratio": 0.18
      },
      "entity_count": 5
    }
  ]
}
```

### 3.2 データベース設計

#### 3.2.1 エンティティ時系列テーブル
```sql
CREATE TABLE entity_timeseries (
    id INTEGER PRIMARY KEY,
    entity_id VARCHAR(100),
    category VARCHAR(50),
    subcategory VARCHAR(50),
    analysis_date DATE,
    -- 感情スコア指標
    raw_delta REAL,
    normalized_bias_index REAL,
    p_value REAL,
    cliffs_delta REAL,
    -- ランキング指標
    google_rank INTEGER,
    perplexity_rank INTEGER,
    rank_change INTEGER,
    rbo_score REAL,
    kendall_tau REAL,
    -- Perplexity分析指標
    official_ratio REAL,
    positive_ratio REAL,
    negative_ratio REAL,
    neutral_ratio REAL,
    -- メタデータ
    execution_count INTEGER,
    reliability_level VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_id, analysis_date)
);
```

#### 3.2.2 カテゴリ時系列テーブル
```sql
CREATE TABLE category_timeseries (
    id INTEGER PRIMARY KEY,
    category VARCHAR(50),
    subcategory VARCHAR(50),
    analysis_date DATE,
    avg_raw_delta REAL,
    avg_normalized_bias_index REAL,
    entity_count INTEGER,
    significant_entities INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, subcategory, analysis_date)
);
```

#### 3.2.3 変化検知ログテーブル
```sql
CREATE TABLE change_detection_log (
    id INTEGER PRIMARY KEY,
    entity_id VARCHAR(100),
    category VARCHAR(50),
    subcategory VARCHAR(50),
    change_type VARCHAR(30),  -- 'sentiment', 'ranking', 'perplexity', 'cross_platform'
    change_metric VARCHAR(50), -- 'raw_delta', 'rbo_score', 'official_ratio', etc.
    change_rate REAL,
    threshold REAL,
    is_significant BOOLEAN,
    statistical_value REAL,   -- p_value, cliffs_delta, etc.
    detection_date DATE,
    posted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 4. 機能詳細設計

### 4.1 データ収集機能

#### 4.1.1 データ収集トリガー
- **トリガー条件**: バイアス分析エンジンの実行完了
- **収集対象**: 分析結果の統合データセット
- **収集頻度**: 日次（分析実行時）

#### 4.1.2 データ収集処理
```python
class DataCollector:
    def collect_entity_data(self, analysis_results: Dict) -> List[Dict]:
        """エンティティ別時系列データを収集"""

    def collect_category_data(self, analysis_results: Dict) -> List[Dict]:
        """カテゴリ別時系列データを収集"""

    def validate_data_quality(self, data: Dict) -> bool:
        """データ品質の検証"""

    def store_timeseries_data(self, data: List[Dict]) -> bool:
        """時系列データの保存"""
```

### 4.2 変化検知機能

#### 4.2.1 変化率計算
- **感情スコア変化**: Raw Delta (Δ)、Normalized Bias Index (BI)
  - 計算期間: 過去7日間
  - 計算方法: `(current - previous) / previous * 100`
  - 閾値: ±20%

- **ランキング変化**: Google・Perplexity順位変動
  - 計算対象: 順位変動、RBO、Kendall Tau
  - 閾値: 上位3位以内変動、または±3位以上、RBO < 0.7、Kendall Tau < 0.5

- **Perplexity分析変化**: 公式非公式率、ポジティブネガティブ率
  - 計算対象: official_ratio、positive_ratio、negative_ratio
  - 閾値: ±15%（公式率）、±20%（感情率）

- **クロスプラットフォーム比較変化**: RBO、Kendall Tau
  - 計算対象: RBO、Kendall Tauの時系列変化
  - 閾値: ±0.2（RBO）、±0.3（Kendall Tau）

#### 4.2.2 閾値判定
- **判定条件**: 各指標の変化率が対応する閾値を超える
- **統計的有意性**: 各指標の統計的有意性も同時に検証

#### 4.2.3 変化検知処理
```python
class ChangeDetector:
    def calculate_change_rate(self, current: float, previous: float) -> float:
        """変化率を計算"""

    def calculate_moving_average_change(self, values: List[float]) -> float:
        """移動平均変化率を計算"""

    def detect_significant_changes(self, entity_data: Dict) -> List[Dict]:
        """顕著な変化を検知"""

    def validate_change_significance(self, change_data: Dict) -> bool:
        """変化の有意性を検証"""
```

### 4.3 統計的有意性検証機能

#### 4.3.1 検証対象
- **p値**: 統計的有意性（p < 0.05）
- **Cliff's Delta**: 効果量（|δ| ≥ 0.33）
- **信頼区間**: 95%信頼区間での検証

#### 4.3.2 検証処理
```python
class StatisticalValidator:
    def validate_p_value(self, p_value: float) -> bool:
        """p値の有意性を検証"""

    def validate_cliffs_delta(self, cliffs_delta: float) -> bool:
        """Cliff's Deltaの効果量を検証"""

    def validate_confidence_interval(self, ci_data: Dict) -> bool:
        """信頼区間を検証"""

    def comprehensive_validation(self, metrics: Dict) -> Dict:
        """包括的な統計検証"""
```

### 4.4 投稿トリガー機能

#### 4.4.1 トリガー条件
1. **感情スコア変化**: 変化率±20%以上 かつ p < 0.05 かつ |δ| ≥ 0.33
2. **ランキング変化**: 上位3位以内変動 または ±3位以上 または RBO < 0.7 または Kendall Tau < 0.5
3. **Perplexity分析変化**: 公式率±15%以上 または 感情率±20%以上 かつ カイ二乗検定 p < 0.05
4. **クロスプラットフォーム比較変化**: RBO±0.2以上 または Kendall Tau±0.3以上 かつ 相関の有意性 p < 0.05
5. **信頼性条件**: 信頼性レベル「実用分析」以上
6. **重複防止**: 同一エンティティ・同一変化種別の24時間以内重複投稿防止

#### 4.4.2 トリガー処理
```python
class PostingTrigger:
    def check_posting_conditions(self, change_data: Dict) -> bool:
        """投稿条件をチェック"""

    def check_duplicate_post(self, entity_id: str) -> bool:
        """重複投稿をチェック"""

    def generate_posting_data(self, change_data: Dict) -> Dict:
        """投稿データを生成"""

    def trigger_posting(self, posting_data: Dict) -> bool:
        """投稿をトリガー"""
```

## 5. 実装仕様

### 5.1 時系列監視メインモジュール

```python
class TimeseriesMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.data_collector = DataCollector()
        self.change_detector = ChangeDetector()
        self.statistical_validator = StatisticalValidator()
        self.posting_trigger = PostingTrigger()
        self.db = TimeseriesDB()

    def process_analysis_results(self, analysis_results: Dict) -> List[Dict]:
        """分析結果を処理し、変化を検知"""

    def monitor_entity_changes(self, entity_data: Dict) -> List[Dict]:
        """エンティティの変化を監視"""

    def monitor_category_changes(self, category_data: Dict) -> List[Dict]:
        """カテゴリの変化を監視"""

    def generate_change_report(self, changes: List[Dict]) -> Dict:
        """変化レポートを生成"""
```

### 5.2 設定ファイル

```yaml
# config/timeseries_monitoring_config.yml
timeseries_monitoring:
  # 感情スコア変化検知設定
  sentiment_change_detection:
    raw_delta_threshold: 20.0  # ±20%
    normalized_bias_index_threshold: 20.0  # ±20%
    p_value_threshold: 0.05
    cliffs_delta_threshold: 0.33

  # ランキング変化検知設定
  ranking_change_detection:
    top_rank_change_threshold: 3  # 上位3位以内変動
    rank_change_threshold: 3  # ±3位以上
    rbo_threshold: 0.7
    kendall_tau_threshold: 0.5

  # Perplexity分析変化検知設定
  perplexity_change_detection:
    official_ratio_threshold: 15.0  # ±15%
    positive_ratio_threshold: 20.0  # ±20%
    negative_ratio_threshold: 20.0  # ±20%
    chi_square_threshold: 0.05

  # クロスプラットフォーム比較変化検知設定
  cross_platform_change_detection:
    rbo_change_threshold: 0.2  # ±0.2
    kendall_tau_change_threshold: 0.3  # ±0.3
    correlation_significance_threshold: 0.05

  # 共通設定
  monitoring_period: 7  # 7日間
  min_data_points: 3  # 最小データポイント数
  confidence_level: 0.95

  # 投稿制御設定
  posting_control:
    max_daily_posts: 10
    duplicate_prevention_hours: 24
    posting_time_range:
      start: "09:00"
      end: "21:00"

  # データベース設定
  database:
    type: "sqlite"  # または "json"
    path: "data/timeseries.db"
    backup_enabled: true
    backup_retention_days: 30
```

### 5.3 エラーハンドリング

```python
class TimeseriesMonitoringError(Exception):
    """時系列監視エラーの基底クラス"""
    pass

class DataCollectionError(TimeseriesMonitoringError):
    """データ収集エラー"""
    pass

class ChangeDetectionError(TimeseriesMonitoringError):
    """変化検知エラー"""
    pass

class StatisticalValidationError(TimeseriesMonitoringError):
    """統計検証エラー"""
    pass

class PostingTriggerError(TimeseriesMonitoringError):
    """投稿トリガーエラー"""
    pass
```

## 6. テスト設計

### 6.1 単体テスト

#### 6.1.1 データ収集テスト
- 正常な分析結果からのデータ収集
- 異常なデータ形式の処理
- データ品質検証

#### 6.1.2 変化検知テスト
- 閾値超過の検知
- 変化率計算の正確性
- 移動平均計算の正確性

#### 6.1.3 統計検証テスト
- p値検証の正確性
- Cliff's Delta検証の正確性
- 信頼区間計算の正確性

### 6.2 統合テスト

#### 6.2.1 エンドツーエンドテスト
- 分析結果から投稿トリガーまでの全フロー
- データベース操作の整合性
- エラーハンドリングの動作

#### 6.2.2 パフォーマンステスト
- 大量データ処理時の性能
- データベースクエリの最適化
- メモリ使用量の監視

## 7. 運用設計

### 7.1 監視・ログ

#### 7.1.1 ログ出力
```python
import logging

logger = logging.getLogger(__name__)

# データ収集ログ
logger.info(f"Data collected for entity: {entity_id}")

# 変化検知ログ
logger.warning(f"Significant change detected: {change_rate}%")

# 投稿トリガーログ
logger.info(f"Posting triggered for entity: {entity_id}")
```

#### 7.1.2 メトリクス収集
- データ収集成功率
- 変化検知頻度
- 投稿トリガー頻度
- 処理時間

### 7.2 バックアップ・復旧

#### 7.2.1 データバックアップ
- 日次自動バックアップ
- 30日間の保持期間
- バックアップ検証

#### 7.2.2 障害復旧
- データベース復旧手順
- 設定ファイル復旧
- ログファイル復旧

## 8. セキュリティ設計

### 8.1 データ保護
- 時系列データの暗号化
- アクセスログの記録
- データベース接続のセキュリティ

### 8.2 設定管理
- 設定ファイルの暗号化
- 環境変数による機密情報管理
- 設定変更の監査ログ

## 9. 実装スケジュール

### 9.1 Week 1: 基盤実装
- データベース設計・実装
- データ収集機能
- 基本設定ファイル

### 9.2 Week 2: 監視機能実装
- 変化検知機能
- 統計検証機能
- 投稿トリガー機能

### 9.3 Week 3: 統合・テスト
- 統合テスト
- パフォーマンス最適化
- ドキュメント整備

### 9.4 Week 4: 運用準備
- 運用監視設定
- バックアップ設定
- 本番環境デプロイ

## 10. 成功指標

### 10.1 技術指標
- **データ収集成功率**: 99%以上
- **変化検知精度**: 95%以上
- **誤検知率**: 5%以下
- **処理時間**: 5分以内

### 10.2 運用指標
- **システム稼働率**: 99.5%以上
- **投稿成功率**: 95%以上
- **データ保持率**: 100%

---

**作成日**: 2025年1月27日
**作成者**: AI Assistant
**バージョン**: 1.0
**承認者**: 未定