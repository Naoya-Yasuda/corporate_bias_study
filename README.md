# 企業優遇バイアス分析システム

企業優遇バイアス分析システムは、AI検索サービスにおける企業優遇バイアスを定量的に分析し、可視化するシステムです。

## 機能概要

### 1. バイアス分析機能
- **感情分析**: 企業名マスキング時と実名時の感情スコア比較
- **ランキング分析**: Google・Perplexity検索結果の順位比較
- **公平性評価**: 企業レベル・サービスレベル公平性スコア算出
- **統計的有意性検証**: p値、Cliff's Delta、信頼区間の計算

### 2. 可視化機能
- **ダッシュボード**: Streamlitベースのインタラクティブダッシュボード
- **時系列分析**: バイアス指標の時系列推移表示
- **比較分析**: 企業間・サービス間の比較分析
- **統計レポート**: 詳細な統計分析レポート

### 3. データ管理機能
- **ハイブリッドストレージ**: ローカル・S3両対応のデータ保存
- **自動データ収集**: Perplexity APIを使用した自動データ収集
- **データ統合**: 複数データソースの統合処理
- **バックアップ**: 自動バックアップ機能

### 4. SNS投稿機能（新機能）
- **自動変化監視**: NBI、ランキング、公平性スコアの変化を自動監視
- **X/Twitter投稿**: 顕著な変化を検知した際の自動投稿
- **投稿制御**: 重複防止、日次制限、時間帯制御
- **コンテンツ生成**: 自動的な投稿コンテンツ生成
- **監視ログ**: 投稿履歴と監視状況の詳細ログ

## システム構成

```
src/
├── analysis/                 # バイアス分析エンジン
│   ├── bias_analysis_engine.py    # 統合分析エンジン
│   ├── hybrid_data_loader.py      # ハイブリッドデータローダー
│   └── sentiment_analyzer.py      # 感情分析処理
├── integrator/              # データ統合処理
├── sns/                     # SNS投稿機能（新規追加）
│   ├── bias_monitor.py      # バイアス変化監視
│   ├── content_generator.py # 投稿コンテンツ生成
│   ├── posting_manager.py   # 投稿管理
│   ├── s3_data_loader.py    # S3データ読み込み
│   └── twitter_client.py    # X API連携
├── utils/                   # ユーティリティ
└── components/              # Webアプリケーションコンポーネント
```

## インストール

### 1. リポジトリのクローン
```bash
git clone <repository-url>
cd corporate-bias-study
```

### 2. 依存関係のインストール
```bash
# アプリケーション用
pip install -r requirements-app.txt

# GitHub Actions用（CI/CD）
pip install -r requirements-github-actions.txt
```

### 3. 環境変数の設定
```bash
cp .env_sample .env
# .envファイルを編集して必要な設定を行ってください
```

### 4. データベースの初期化
```bash
python scripts/init_database.py
```

## 使用方法

### 1. 基本的な分析実行
```bash
# 感情分析の実行
python scripts/run_bias_analysis.py --date 20250127

# 統合分析の実行
python scripts/run_bias_analysis.py --date 20250127 --mode integrated
```

### 2. Webダッシュボードの起動
```bash
streamlit run app.py
```

### 3. SNS投稿機能のテスト
```bash
# SNS投稿機能のテスト実行
python scripts/test_sns_posting.py

# 監視機能のテスト
python -c "from src.sns.bias_monitor import BiasMonitor; monitor = BiasMonitor(); monitor.check_for_significant_changes()"
```

## SNS投稿機能の詳細

### 監視対象指標と閾値
| 指標                             | 閾値                            | 説明                         |
| -------------------------------- | ------------------------------- | ---------------------------- |
| **NBI（Normalized Bias Index）** | ±20%以上                        | 企業優遇バイアスの正規化指標 |
| **おすすめランキング順位**       | 上位3位以内変動 または ±3位以上 | 検索結果の順位変化           |
| **サービスレベル公平性スコア**   | ±15%以上                        | サービスカテゴリ全体の公平性 |
| **企業レベル公平性スコア**       | ±15%以上                        | 個別企業の公平性評価         |

### 投稿テンプレート例

#### 1. NBI変化検知
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

#### 2. ランキング変化検知
```
📊【検索ランキング変化検知】

🏢 対象企業: Microsoft Azure
📈 ランキング変化: 2位 → 5位 (-3位)
📋 カテゴリ: クラウドコンピューティング
📅 検知日時: 2025-01-27 15:45

🔍 詳細分析: https://your-domain.com/ranking
#検索ランキング #AI分析 #企業評価
```

#### 3. 公平性スコア変化検知
```
⚖️【公平性スコア変化検知】

🏢 対象企業: Google Cloud
📊 スコア変化: 0.78 → 0.65 (-16.7%)
📋 評価項目: 企業レベル公平性
📅 検知日時: 2025-01-27 16:20

🔍 詳細分析: https://your-domain.com/fairness
#公平性評価 #AI分析 #透明性
```

### 設定方法

#### 1. 環境変数設定（.envファイル）
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

#### 2. 機能設定（YAMLファイル）
**機能固有の詳細設定**（環境変数で制御された機能の動作パラメータ）：

#### 3. 監視設定ファイル
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

### 監視ログと履歴

#### 1. 投稿履歴の確認
```bash
# 投稿履歴の表示
python scripts/check_post_history.py

# 特定日付の投稿履歴
python scripts/check_post_history.py --date 20250127
```

#### 2. 監視ログの確認
```bash
# リアルタイムログ監視
tail -f logs/sns_monitoring.log

# エラーログの確認
grep "ERROR" logs/sns_monitoring.log
```

#### 3. 監視状況の確認
```python
from src.sns.bias_monitor import BiasMonitor

# 監視状況の確認
monitor = BiasMonitor()
status = monitor.get_monitoring_status()
print(f"監視状況: {status}")
```

## 設定ファイル

### 環境変数（.env）- 最優先設定
- **認証情報**: X API、AWS S3認証情報
- **インフラ設定**: S3バケット名、リージョン
- **基本制御**: 機能の有効/無効切り替え（`TWITTER_POSTING_ENABLED`, `SNS_MONITORING_ENABLED`）

### 分析設定
- `config/analysis_config.yml`: バイアス分析の設定
- `config/sns_monitoring_config.yml`: SNS投稿機能の詳細設定（閾値、投稿制御、コンテンツ設定など）

### データ設定
- `src/data/categories.yml`: 分析対象カテゴリ・エンティティの定義
- `src/data/market_shares.json`: 市場シェアデータ
- `src/data/market_caps.json`: 時価総額データ

### 設定の優先順位
1. **環境変数（.env）**: 最優先（認証情報、基本制御）
2. **YAML設定ファイル**: 機能固有の詳細設定
3. **デフォルト値**: 設定ファイルが存在しない場合のフォールバック

## データ構造

### 分析結果データ
```json
{
  "metadata": {
    "analysis_date": "20250127",
    "execution_count": 5,
    "reliability_level": "実用分析"
  },
  "categories": {
    "クラウドサービス": {
      "service_level_fairness_score": 0.85,
      "enterprise_level_fairness_score": 0.78,
      "subcategories": {
        "クラウドコンピューティング": {
          "entities": [
            {
              "name": "AWS",
              "normalized_bias_index": 1.8,
              "sign_test_p_value": 0.02,
              "cliffs_delta": 0.45
            }
          ]
        }
      }
    }
  }
}
```

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

### テスト実行
```bash
# 単体テスト
python -m pytest tests/

# SNS投稿機能テスト
python scripts/test_sns_posting.py

# 統合テスト
python scripts/run_integration_tests.py

# Playwright E2Eテスト
python -m pytest tests/ --headed --browser chromium
```

### ログ確認
```bash
# アプリケーションログ
tail -f logs/app.log

# SNS投稿ログ
tail -f logs/sns_monitoring.log

# エラーログの確認
grep -i error logs/*.log
```

### データベース管理
```bash
# 投稿履歴の確認
python scripts/check_post_history.py

# 古いレコードの削除
python scripts/cleanup_old_records.py

# データベースのバックアップ
python scripts/backup_database.py
```

### デバッグとトラブルシューティング

#### 1. SNS投稿機能のデバッグ
```python
from src.sns.bias_monitor import BiasMonitor
from src.sns.posting_manager import PostingManager

# 監視機能のテスト
monitor = BiasMonitor()
changes = monitor.check_for_significant_changes()
print(f"検知された変化: {changes}")

# 投稿機能のテスト
manager = PostingManager()
test_post = manager.create_test_post()
print(f"テスト投稿: {test_post}")
```

#### 2. 設定の検証
```python
from src.sns.bias_monitor import BiasMonitor

# 設定の検証
monitor = BiasMonitor()
config_status = monitor.validate_config()
print(f"設定状況: {config_status}")
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
# 投稿履歴の確認
python scripts/check_post_history.py --date $(date +%Y%m%d)

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

### パフォーマンス最適化

#### 1. 監視間隔の調整
```yaml
# config/sns_monitoring_config.yml
monitoring:
  interval_hours: 12  # 6時間から12時間に変更
```

#### 2. データキャッシュの活用
```python
# キャッシュ機能の有効化
from src.utils.storage_utils import enable_cache
enable_cache(True)
```

#### 3. 並列処理の設定
```yaml
# config/analysis_config.yml
parallel_processing:
  enabled: true
  max_workers: 4
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

プルリクエストやイシューの報告を歓迎します。貢献する前に、コーディング規約とテスト要件を確認してください。

### 開発ガイドライン
1. 新しい機能追加時は必ずテストを作成
2. SNS投稿機能の変更時は投稿制御を考慮
3. 環境変数の変更時は`.env_sample`も更新
4. ドキュメントの更新を忘れずに

## 更新履歴

### v1.2.0 (2025-01-27)
- SNS投稿機能の詳細設定とトラブルシューティングを追加
- 監視ログと履歴管理機能を強化
- 投稿テンプレートの多様化
- デバッグ機能の充実

### v1.1.0 (2025-01-25)
- SNS投稿機能を追加
- バイアス変化自動監視機能を実装
- X/Twitter API連携機能を追加
- 投稿制御・管理機能を実装

### v1.0.0 (2025-01-20)
- 初回リリース
- 基本的なバイアス分析機能
- Webダッシュボード
- データ管理機能
