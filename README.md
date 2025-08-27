# 企業優遇バイアス分析システム

企業優遇バイアス分析システムは、AI検索サービスにおける企業優遇バイアスを定量的に分析し、可視化するシステムです。

## 機能概要

### 1. バイアス分析機能
- **感情分析**: 企業名マスキング時と実名時の感情スコア比較
- **ランキング分析**: Google・Perplexity検索結果の順位比較
- **公平性評価**: 企業レベル・サービスレベル公平性スコア算出
- **統計的有意性検証**: p値、Cliff's Delta、信頼区間の計算
- **信頼性評価**: 実行回数に基づく分析信頼性レベルの自動判定

### 2. 可視化機能
- **ダッシュボード**: Streamlitベースのインタラクティブダッシュボード
- **動的可視化**: 事前生成画像ではなく、リアルタイムでグラフを生成
- **時系列分析**: バイアス指標の時系列推移表示
- **比較分析**: 企業間・サービス間の比較分析
- **統計レポート**: 詳細な統計分析レポート

### 3. データ管理機能
- **ハイブリッドストレージ**: ローカル・S3両対応のデータ保存
- **自動データ収集**: Perplexity APIを使用した自動データ収集
- **データ統合**: 複数データソースの統合処理
- **バックアップ**: 自動バックアップ機能

### 4. SNS投稿機能
- **自動変化監視**: NBI、ランキング、公平性スコアの変化を自動監視
- **X/Twitter投稿**: 顕著な変化を検知した際の自動投稿
- **投稿制御**: 重複防止、日次制限、時間帯制御
- **コンテンツ生成**: 自動的な投稿コンテンツ生成
- **監視ログ**: 投稿履歴と監視状況の詳細ログ

詳細な設定方法は [SNS投稿機能README](docs/sns_posting_guide.md) を参照してください。

## システム構成

### 設定ファイル構成
```
config/
├── analysis/
│   ├── analysis_config.yml      # バイアス分析設定
│   └── categories.yml           # 分析対象カテゴリ・エンティティ
├── data/
│   ├── market_shares.json       # 市場シェアデータ
│   └── market_caps.json         # 時価総額データ
└── sns/
    ├── sns_monitoring_config.yml
    └── simple_sns_config.yml
```

### スクリプト構成
```
scripts/
├── analysis/
│   └── run_bias_analysis.py     # 分析実行スクリプト
├── data/
│   ├── collect_data.py          # データ収集スクリプト
│   └── integrate_data.py        # データ統合スクリプト
├── sns/
│   └── github_actions_sns_posting.py
└── utils/
    ├── config_manager.py        # 共通設定管理
    ├── setup_environment.py     # 環境セットアップ
    └── validate_data.py         # データ検証
```

### ソースコード構成
```
src/
├── analysis/                 # バイアス分析エンジン
│   ├── bias_analysis_engine.py    # 統合分析エンジン
│   ├── hybrid_data_loader.py      # ハイブリッドデータローダー
│   └── sentiment_analyzer.py      # 感情分析処理
├── loader/                   # データローダー
│   ├── perplexity_sentiment_loader.py  # Perplexity感情分析データ取得
│   ├── perplexity_citations_loader.py  # Perplexity引用データ取得
│   ├── perplexity_ranking_loader.py    # Perplexityランキングデータ取得
│   └── google_search_loader.py         # Google検索データ取得
├── integrator/              # データ統合処理
│   ├── dataset_integrator.py     # データセット統合
│   ├── create_integrated_dataset.py  # 統合データセット作成
│   ├── data_validator.py         # データ検証
│   └── schema_generator.py       # スキーマ生成
├── sns/                     # SNS投稿機能
│   ├── integrated_posting_system.py  # 統合投稿システム
│   ├── simple_posting_system.py      # シンプル投稿システム
│   ├── simple_change_detector.py     # 変化検知
│   ├── simple_content_generator.py   # コンテンツ生成
│   ├── s3_data_loader.py            # S3データ読み込み
│   └── twitter_client.py            # X API連携
├── utils/                   # ユーティリティ
│   ├── plot_utils.py              # 可視化ユーティリティ
│   ├── storage_utils.py           # ストレージユーティリティ
│   ├── metrics_utils.py           # メトリクス計算
│   ├── perplexity_api.py          # Perplexity API連携
│   ├── storage_config.py          # ストレージ設定
│   ├── auth_utils.py              # 認証ユーティリティ
│   ├── text_utils.py              # テキスト処理
│   ├── rank_utils.py              # ランキング処理
│   ├── config_manager.py          # 統合設定管理
│   ├── error_handler.py           # エラーハンドリング
│   └── logger.py                  # 標準化ログ出力
├── auth/                    # 認証機能
│   ├── google_oauth.py           # Google OAuth認証
│   ├── session_manager.py        # セッション管理
│   └── domain_validator.py       # ドメイン検証
├── components/              # Webアプリケーションコンポーネント
│   └── auth_ui.py               # 認証UI
└── prompts/                 # プロンプト管理
    ├── prompt_manager.py        # プロンプト管理
    ├── sentiment_prompts.py     # 感情分析プロンプト
    ├── ranking_prompts.py       # ランキング分析プロンプト
    └── prompt_config.yml        # プロンプト設定
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
pip install -r requirements.txt

# GitHub Actions用（CI/CD）
pip install -r requirements-github-actions.txt
```

### 3. 環境変数の設定
```bash
cp .env_sample .env
# .envファイルを編集して必要な設定を行ってください
```

## 使用方法

### 1. 基本的な分析実行
```bash
# 統合バイアス分析の実行
python scripts/analysis/run_bias_analysis.py --date 20250127

# 詳細ログ付きで実行
python scripts/analysis/run_bias_analysis.py --date 20250127 --verbose

# 特定の実行回数で実行
python scripts/analysis/run_bias_analysis.py --date 20250127 --runs 5
```

### 2. 個別コンポーネントの実行
```bash
# Perplexity感情分析データ取得
python -m src.loader.perplexity_sentiment_loader --runs 3 --verbose

# Perplexityランキングデータ取得
python -m src.loader.perplexity_ranking_loader --runs 3 --verbose

# Perplexity引用データ取得
python -m src.loader.perplexity_citations_loader --runs 3 --verbose

# Google検索データ取得
python -m src.loader.google_search_loader --verbose

# 統合データセット作成
python -m src.integrator.create_integrated_dataset --date 20250127 --verbose

# バイアス分析エンジン直接実行
python -m src.analysis.bias_analysis_engine --date 20250127 --verbose
```

### 3. Webダッシュボードの起動
```bash
streamlit run app.py
```

### 4. データ収集・統合・検証
```bash
# データ収集（全データタイプ）
python scripts/data/collect_data.py --type all --runs 3

# 特定データタイプの収集
python scripts/data/collect_data.py --type sentiment --runs 5

# データ統合
python scripts/data/integrate_data.py --date 20250127 --validate

# データ検証
python scripts/utils/validate_data.py --date 20250127 --type all
```

### 5. 環境セットアップ・検証
```bash
# 環境セットアップ（不足ディレクトリの作成）
python scripts/utils/setup_environment.py --create-dirs --verbose

# 環境検証
python scripts/utils/setup_environment.py --verbose
```

### 6. SNS投稿機能の実行
```bash
# GitHub Actions用SNS投稿スクリプト
python scripts/sns/github_actions_sns_posting.py

# 統合投稿システムのテスト
python -c "from src.sns.integrated_posting_system import IntegratedPostingSystem; system = IntegratedPostingSystem(); result = system.post_latest_changes(); print(result)"
```

## 設定ファイル

### 環境変数（.env）- 最優先設定
- **認証情報**: X API、AWS S3認証情報
- **インフラ設定**: S3バケット名、リージョン
- **基本制御**: 機能の有効/無効切り替え（`TWITTER_POSTING_ENABLED`, `SNS_MONITORING_ENABLED`）

### 分析設定
- `config/analysis_config.yml`: バイアス分析の設定（信頼性レベル、閾値等）
- `config/analysis/categories.yml`: 分析対象カテゴリ・エンティティの定義

### SNS設定
- `config/sns_monitoring_config.yml`: SNS投稿機能の詳細設定
- `config/simple_sns_config.yml`: シンプルSNS投稿機能の設定

### データ設定
- `config/data/market_shares.json`: 市場シェアデータ
- `config/data/market_caps.json`: 時価総額データ

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

## 開発者向け情報

### テスト実行
```bash
# 現在テストファイルは実装されていません
# テストディレクトリ: tests/ （空の状態）

# 手動テスト
python scripts/analysis/run_bias_analysis.py --date 20250127 --verbose
python scripts/sns/github_actions_sns_posting.py

# 環境検証
python scripts/utils/setup_environment.py --verbose

# データ検証
python scripts/utils/validate_data.py --date 20250127 --type all
```

### ログ確認
```bash
# ログディレクトリ: logs/ （空の状態）
# 実行時に自動生成されます

# アプリケーションログ
tail -f logs/app.log

# SNS投稿ログ
tail -f logs/sns_monitoring.log

# エラーログの確認
grep -i error logs/*.log
```

## パフォーマンス最適化

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

### 開発ガイドライン
1. 新しい機能追加時は必ずテストを作成
2. SNS投稿機能の変更時は投稿制御を考慮
3. 環境変数の変更時は`.env_sample`も更新
4. ドキュメントの更新を忘れずに