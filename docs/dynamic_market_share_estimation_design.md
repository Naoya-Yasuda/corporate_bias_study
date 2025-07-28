# 動的市場シェア推定システム詳細設計書

## 1. システム概要

### 1.1 目的
Perplexity APIの検索結果から動的に市場シェアを推定し、リアルタイムHHI計算を実現するシステム

### 1.2 基本コンセプト
```
検索結果の出現頻度・順位 → 市場シェアの代理指標 → 推定市場シェア → リアルタイムHHI
```

## 2. システムアーキテクチャ

### 2.1 全体構成

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ データ収集層    │    │ 処理・推定層    │    │ 出力・監視層    │
│                 │    │                 │    │                 │
│ • Perplexity API│───▶│ • データ前処理 │───▶│ • 推定結果出力 │
│ • 市場データAPI │    │ • シェア推定   │    │ • リアルタイム  │
│ • ストリーミング│    │ • HHI計算      │    │   モニタリング  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.2 コンポーネント詳細

#### 2.2.1 データ収集層
```
- Perplexity API Connector
- Market Data API Connector (Yahoo Finance, Alpha Vantage)
- Data Stream Processor (Apache Kafka)
- Data Quality Checker
```

#### 2.2.2 処理・推定層
```
- Data Preprocessor
- Market Share Estimator
- HHI Calculator
- Anomaly Detector
- Confidence Calculator
```

#### 2.2.3 出力・監視層
```
- Real-time Dashboard
- Alert System
- Data Storage (InfluxDB)
- Performance Monitor
```

## 3. データフロー設計

### 3.1 メインデータフロー

```
1. データ収集
   ↓
2. データ前処理
   ↓
3. 市場シェア推定
   ↓
4. HHI計算
   ↓
5. 結果出力・保存
   ↓
6. 監視・アラート
```

### 3.2 詳細フロー

#### 3.2.1 データ収集フロー
```
Perplexity API → 検索結果解析 → 企業名抽出 → 出現頻度計算
Market Data API → 時価総額取得 → データ正規化 → 品質チェック
```

#### 3.2.2 推定フロー
```
企業名マッチング → 重み付け計算 → シェア推定 → 信頼度評価
```

#### 3.2.3 計算フロー
```
推定シェア → HHI計算 → 変化率算出 → 異常値検出
```

## 4. 推定アルゴリズム設計

### 4.1 市場シェア推定アルゴリズム

#### 4.1.1 基本推定式
```
推定市場シェア = (検索出現頻度 × 順位重み × 時価総額補正) / 総和
```

#### 4.1.2 詳細計算式

**ステップ1: 検索出現頻度の正規化**
```
normalized_frequency[i] = frequency[i] / max(frequency)
```

**ステップ2: 順位重みの計算**
```
rank_weight[i] = 1 / (rank[i] + 1)  # 1位=1.0, 2位=0.5, 3位=0.33...
```

**ステップ3: 時価総額補正**
```
market_cap_correction[i] = log(market_cap[i]) / log(max_market_cap)
```

**ステップ4: 重み付き推定**
```
estimated_share[i] = (normalized_frequency[i] × rank_weight[i] × market_cap_correction[i]) / Σ(weighted_score)
```

#### 4.1.3 信頼度計算
```
confidence[i] = min(1.0, (data_quality[i] × sample_size[i] × consistency[i]))
```

### 4.2 リアルタイムHHI計算

#### 4.2.1 基本HHI計算
```
HHI = Σ(推定市場シェア[i]²) × 10000
```

#### 4.2.2 変化率計算
```
HHI_change_rate = (HHI_current - HHI_previous) / HHI_previous × 100
```

#### 4.2.3 異常値検出
```
if |HHI_change_rate| > threshold:
    trigger_alert()
```

## 5. データ構造設計

### 5.1 入力データ構造

#### 5.1.1 Perplexity APIデータ
```json
{
  "search_results": [
    {
      "entity_name": "企業名",
      "rank": 1,
      "frequency": 15,
      "sentiment_score": 0.8,
      "timestamp": "2025-01-16T10:00:00Z"
    }
  ],
  "search_query": "検索クエリ",
  "total_results": 100
}
```

#### 5.1.2 市場データ
```json
{
  "market_data": [
    {
      "entity_name": "企業名",
      "market_cap": 1500000000000,
      "stock_price": 150.0,
      "volume": 1000000,
      "timestamp": "2025-01-16T10:00:00Z"
    }
  ]
}
```

### 5.2 出力データ構造

#### 5.2.1 推定結果
```json
{
  "estimation_results": {
    "timestamp": "2025-01-16T10:00:00Z",
    "market_shares": [
      {
        "entity_name": "企業名",
        "estimated_share": 0.25,
        "confidence": 0.85,
        "rank": 1
      }
    ],
    "hhi_score": 3026.4,
    "hhi_change_rate": 2.1,
    "concentration_level": "高集中市場",
    "anomaly_detected": false
  }
}
```

## 6. 技術実装詳細

### 6.1 データベース設計

#### 6.1.1 時系列データベース（InfluxDB）
```
measurement: market_analysis
tags: category, subcategory, entity_name
fields: estimated_share, hhi_score, confidence, market_cap
timestamp: 自動付与
```

#### 6.1.2 リレーショナルデータベース（PostgreSQL）
```
tables:
- entities (企業マスタ)
- market_data (市場データ履歴)
- estimation_results (推定結果履歴)
- alerts (アラート履歴)
```

### 6.2 API設計

#### 6.2.1 REST API
```
GET /api/v1/market-shares/{category}/{subcategory}
GET /api/v1/hhi/{category}/{subcategory}
GET /api/v1/estimation/{entity_name}
POST /api/v1/estimation/trigger
```

#### 6.2.2 WebSocket API
```
ws://api/v1/stream/market-updates
ws://api/v1/stream/hhi-changes
ws://api/v1/stream/alerts
```

### 6.3 ストリーミング処理

#### 6.3.1 Apache Kafka設定
```
topics:
- perplexity-search-results
- market-data-updates
- estimation-results
- hhi-changes
- alerts
```

#### 6.3.2 ストリーミング処理フロー
```
Kafka Consumer → Data Processor → Estimator → HHI Calculator → Kafka Producer
```

## 7. パフォーマンス要件

### 7.1 処理性能
```
- データ処理: 1000件/秒
- HHI計算: 100ms以内
- 推定精度: 90%以上
- 可用性: 99.9%
```

### 7.2 スケーラビリティ
```
- 水平スケーリング対応
- 負荷分散機能
- 自動スケーリング
```

### 7.3 監視・ログ
```
- メトリクス収集: Prometheus
- ログ管理: ELK Stack
- アラート: Grafana Alerting
```

## 8. セキュリティ設計

### 8.1 認証・認可
```
- API認証: JWT Token
- アクセス制御: RBAC
- データ暗号化: AES-256
```

### 8.2 データ保護
```
- 個人情報の匿名化
- データ保持期間の管理
- アクセスログの記録
```

## 9. テスト戦略

### 9.1 単体テスト
```
- 推定アルゴリズムの精度テスト
- HHI計算の正確性テスト
- データ処理の品質テスト
```

### 9.2 統合テスト
```
- API連携テスト
- ストリーミング処理テスト
- データベース連携テスト
```

### 9.3 負荷テスト
```
- 高負荷時の性能テスト
- 同時接続数テスト
- メモリ使用量テスト
```

## 10. 運用設計

### 10.1 デプロイメント
```
- コンテナ化: Docker
- オーケストレーション: Kubernetes
- CI/CD: GitHub Actions
```

### 10.2 監視・運用
```
- ヘルスチェック
- 自動復旧機能
- バックアップ・リストア
```

### 10.3 メンテナンス
```
- 定期メンテナンス計画
- アップデート手順
- 障害対応手順
```

## 11. 実装計画

### 11.1 Phase 1: 基盤構築（2週間）
```
- データベース設計・構築
- API基盤の実装
- 基本的なデータ収集機能
```

### 11.2 Phase 2: 推定アルゴリズム（3週間）
```
- 市場シェア推定アルゴリズムの実装
- HHI計算機能の実装
- 精度検証・調整
```

### 11.3 Phase 3: リアルタイム処理（2週間）
```
- ストリーミング処理の実装
- リアルタイム計算機能
- パフォーマンス最適化
```

### 11.4 Phase 4: 統合・テスト（1週間）
```
- システム統合
- 総合テスト
- 本番環境への展開
```

---

**作成日**: 2025年1月16日
**作成者**: AI Assistant
**バージョン**: 1.0