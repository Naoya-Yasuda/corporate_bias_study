# SNS投稿機能ガイド

企業優遇バイアス分析システムのSNS投稿機能について詳しく説明します。

## 概要

SNS投稿機能は、バイアス分析結果の変化を自動監視し、顕著な変化を検知した際にX/Twitterに自動投稿する機能です。

### 主要機能
- **自動変化監視**: NBI、ランキング、公平性スコアの変化を自動監視
- **X/Twitter投稿**: 顕著な変化を検知した際の自動投稿
- **投稿制御**: 重複防止、日次制限、時間帯制御
- **コンテンツ生成**: 自動的な投稿コンテンツ生成
- **監視ログ**: 投稿履歴と監視状況の詳細ログ

## 監視対象指標と閾値

| 指標                             | 閾値                            | 説明                         |
| -------------------------------- | ------------------------------- | ---------------------------- |
| **NBI（Normalized Bias Index）** | ±20%以上                        | 企業優遇バイアスの正規化指標 |
| **おすすめランキング順位**       | 上位3位以内変動 または ±3位以上 | 検索結果の順位変化           |
| **サービスレベル公平性スコア**   | ±15%以上                        | サービスカテゴリ全体の公平性 |
| **企業レベル公平性スコア**       | ±15%以上                        | 個別企業の公平性評価         |

## 投稿テンプレート例

### 1. NBI変化検知
```
🚨【企業優遇バイアス変化検知】

📊 検知内容: NBI急激な変化
🏢 対象企業: AWS
📈 変化率: +25.3%
📋 詳細: 感情スコアが大幅に上昇
📅 検知日時: 2025-01-27 14:30

🔍 分析詳細: https://your-domain.com/analysis
#企業優遇バイアス #AI分析 #透明性
```

### 2. ランキング変化検知
```
📊【検索ランキング変化検知】

🏢 対象企業: Microsoft Azure
📈 ランキング変化: 2位 → 5位 (-3位)
📋 カテゴリ: クラウドコンピューティング
📅 検知日時: 2025-01-27 15:45

🔍 詳細分析: https://your-domain.com/ranking
#検索ランキング #AI分析 #企業評価
```

### 3. 公平性スコア変化検知
```
⚖️【公平性スコア変化検知】

🏢 対象企業: Google Cloud
📊 スコア変化: 0.78 → 0.65 (-16.7%)
📋 評価項目: 企業レベル公平性
📅 検知日時: 2025-01-27 16:20

🔍 詳細分析: https://your-domain.com/fairness
#公平性評価 #AI分析 #透明性
```

## 設定方法

### 1. 環境変数設定（.envファイル）
**認証情報、インフラ設定、基本制御**：
```bash
# X API認証情報
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# S3設定（データアクセス用）
S3_BUCKET_NAME=your_s3_bucket_name
AWS_ACCESS_KEY=your_aws_access_key
AWS_SECRET_KEY=your_aws_secret_key
AWS_REGION=ap-northeast-1

# 基本制御設定（最優先）
TWITTER_POSTING_ENABLED=true    # 投稿機能の有効/無効
SNS_MONITORING_ENABLED=true     # 監視機能の有効/無効
```

### 2. 監視設定ファイル
`config/sns_monitoring_config.yml`の設定例：
```yaml
sns_monitoring:
  thresholds:
    nbi_change_percent: 20.0
    ranking_change_positions: 3
    fairness_score_change_percent: 15.0

  posting:
    max_daily_posts: 10
    duplicate_prevention_hours: 24
    time_range:
      start: "09:00"
      end: "21:00"
    time_zone: "Asia/Tokyo"

  content:
    include_hashtags: true
    include_analysis_url: true
    max_character_count: 280
    base_url: "https://your-domain.com/analysis"

  monitoring:
    check_interval_minutes: 60
```

### 3. シンプル設定ファイル
`config/simple_sns_config.yml`の設定例：
```yaml
# 変化検知の閾値設定
change_thresholds:
  bias_score: 0.1        # バイアススコアの変化閾値（10%）
  sentiment_score: 0.15  # センチメントスコアの変化閾値（15%）
  ranking_change: 3      # ランキング変化閾値（3位以上）
  fairness_score: 0.1    # 公平性スコアの変化閾値（10%）
  neutrality_score: 0.1  # 中立性スコアの変化閾値（10%）

# 投稿設定
posting:
  enabled: true                    # 投稿機能の有効/無効
  max_changes_per_post: 5          # 1投稿あたりの最大変化数
  force_post_on_no_changes: false  # 変化がない場合の強制投稿
```

## 使用方法

### 1. 基本的な実行
```bash
# GitHub Actions用SNS投稿スクリプト
python scripts/github_actions_sns_posting.py

# 統合投稿システムのテスト
python -c "from src.sns.integrated_posting_system import IntegratedPostingSystem; system = IntegratedPostingSystem(); result = system.post_latest_changes(); print(result)"
```

### 2. システム状態の確認
```python
from src.sns.integrated_posting_system import IntegratedPostingSystem

# システム状態の確認
system = IntegratedPostingSystem()
status = system.get_system_status()
print(f"システム状態: {status}")

# 接続テスト
test_result = system.test_connection()
print(f"接続テスト結果: {test_result}")

# 利用可能な分析日付の確認
available_dates = system.list_available_dates()
print(f"利用可能な分析日付: {available_dates}")
```

### 3. 手動投稿実行
```python
from src.sns.integrated_posting_system import IntegratedPostingSystem

# 統合投稿システムを初期化
system = IntegratedPostingSystem(storage_mode='auto')

# 最新の変化を検知して投稿
result = system.post_latest_changes(force_post=False)
print(f"投稿結果: {result}")

# 強制投稿（変化がなくても投稿）
result = system.post_latest_changes(force_post=True)
print(f"強制投稿結果: {result}")
```

## 監視ログと履歴

### 1. 投稿履歴の確認
```bash
# ログディレクトリの確認
ls -la logs/

# 投稿ログの確認
tail -f logs/sns_monitoring.log

# エラーログの確認
grep "ERROR" logs/sns_monitoring.log
```

### 2. 監視状況の確認
```python
from src.sns.integrated_posting_system import IntegratedPostingSystem

# 監視状況の確認
system = IntegratedPostingSystem()
status = system.get_system_status()
print(f"監視状況: {status}")
```

## トラブルシューティング

### よくある問題と解決方法

#### 1. S3接続エラー
**症状**: `botocore.exceptions.NoCredentialsError`
**解決方法**:
```bash
# AWS認証情報の確認
aws configure list

# 環境変数の設定確認
echo $AWS_ACCESS_KEY_ID
echo $AWS_SECRET_ACCESS_KEY
```

#### 2. X API認証エラー
**症状**: `tweepy.errors.Unauthorized`
**解決方法**:
```bash
# 環境変数の確認
echo $TWITTER_API_KEY
echo $TWITTER_API_SECRET

# API認証情報の再生成
# X Developer Portalで新しい認証情報を生成
```

#### 3. 投稿制限エラー
**症状**: `tweepy.errors.TooManyRequests`
**解決方法**:
```bash
# 制限設定の調整
# config/sns_monitoring_config.ymlでmax_daily_postsを調整
```

#### 4. 監視データ取得エラー
**症状**: `FileNotFoundError: No such file or directory`
**解決方法**:
```bash
# S3データの確認
python -c "from src.sns.s3_data_loader import S3DataLoader; loader = S3DataLoader(); print(loader.list_available_dates())"

# ローカルデータの確認
ls -la corporate_bias_datasets/analysis_visuals/
```

#### 5. メモリ不足エラー
**症状**: `MemoryError` または `Killed`
**解決方法**:
```bash
# メモリ使用量の確認
free -h

# バッチサイズの調整
# config/analysis_config.ymlでbatch_sizeを小さくする
```

## パフォーマンス最適化

### 1. 監視間隔の調整
```yaml
# config/sns_monitoring_config.yml
monitoring:
  interval_hours: 12  # 6時間から12時間に変更
```

### 2. データキャッシュの活用
```python
# キャッシュ機能の有効化
from src.utils.storage_utils import enable_cache
enable_cache(True)
```

### 3. 並列処理の設定
```yaml
# config/analysis_config.yml
parallel_processing:
  enabled: true
  max_workers: 4
```

## データ構造

### SNS投稿履歴データ
```json
{
  "post_id": "unique_post_id",
  "timestamp": "2025-01-27T14:30:00Z",
  "change_type": "nbi_change",
  "entity_name": "AWS",
  "change_percentage": 25.3,
  "post_content": "投稿内容...",
  "status": "posted",
  "tweet_id": "1234567890123456789"
}
```

## 開発者向け情報

### デバッグとトラブルシューティング

#### 1. SNS投稿機能のデバッグ
```python
from src.sns.integrated_posting_system import IntegratedPostingSystem

# システム状態の確認
system = IntegratedPostingSystem()
status = system.get_system_status()
print(f"システム状態: {status}")

# 接続テスト
test_result = system.test_connection()
print(f"接続テスト結果: {test_result}")

# 利用可能な分析日付の確認
available_dates = system.list_available_dates()
print(f"利用可能な分析日付: {available_dates}")
```

#### 2. 設定の検証
```python
from src.sns.integrated_posting_system import IntegratedPostingSystem

# 設定の検証
system = IntegratedPostingSystem()
status = system.get_system_status()
print(f"設定状況: {status}")
```

### ログ確認
```bash
# ログディレクトリ: logs/ （空の状態）
# 実行時に自動生成されます

# SNS投稿ログ
tail -f logs/sns_monitoring.log

# エラーログの確認
grep -i error logs/*.log
```
