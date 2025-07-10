# AI検索サービスにおける企業優遇バイアス

*―市場競争への潜在的リスクを定量評価するリサーチ & システム開発―*

---

## 1. プロジェクト概要

AI検索サービス（ChatGPT、Perplexity、Copilotなど）が提示する情報に**企業優遇バイアス**が存在しうるのかを検証し、その**市場競争への影響**を**定量的指標**で可視化・評価する学術・実装プロジェクトです。検索エンジンではなく*生成AIベースの検索*にフォーカスする点が新規性です。

### 🎯 2段階実行アプローチ ⭐ **NEW**

効率的なバイアス分析を実現する新しいアーキテクチャを導入しました：

**Stage 1: 高速データ分析（1-3秒）** → **Stage 2: 高品質可視化（10-30秒）**

- **分離設計**: 分析処理と画像生成を分離し、各段階を最適化
- **柔軟性**: JSON中間形式により多様な可視化パターンに対応
- **効率性**: 必要に応じてStage 1のみ・Stage 2のみの実行が可能

詳細は [`docs/visualization_architecture.md`](docs/visualization_architecture.md) を参照してください。

## 概要
Google検索とPerplexity API等の結果を比較し、企業バイアスと経済的影響を分析するためのパイプラインです。

## 必要条件
- Python 3.12以上（Python 3.12.11で動作確認済み）
- Google Custom Search API
- Perplexity API
- AWSアカウント（S3を使用する場合）

## セットアップ

まずpipとsetuptoolsを最新版にアップグレードしてください（distutilsエラー対策）:

```
pip install --upgrade pip setuptools
```

その後、依存パッケージをインストール:

```
pip install -r requirements.txt
```

### 必要な環境変数
`.env`ファイルに以下を設定してください（`.env_sample`も参照）：

```
# API Keys
PERPLEXITY_API_KEY=your_perplexity_api_key
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id

# AWS Credentials
AWS_ACCESS_KEY=your_aws_access_key
AWS_SECRET_KEY=your_aws_secret_key
AWS_REGION=ap-northeast-1
S3_BUCKET_NAME=your_s3_bucket_name

# Perplexity API Settings
PERPLEXITY_MODELS_TO_TRY=sonar
```

## 日本語グラフ対応
matplotlibで日本語が文字化けする場合は、`import japanize_matplotlib` を追加してください。本リポジトリの可視化スクリプト・ユーティリティでは既に対応済みです。

## 使い方

### 1. 基本的な使い方

```bash
# Google検索データ収集
python -m src.loader.google_search_loader --perplexity-date 20251201 --verbose

# Perplexity感情分析データ収集（単一実行）
python -m src.loader.perplexity_sentiment_loader --verbose

# Perplexity感情分析データ収集（複数実行）
python -m src.loader.perplexity_sentiment_loader --runs 3 --verbose

# Perplexityランキングデータ収集（単一実行）
python -m src.loader.perplexity_ranking_loader --verbose

# Perplexity引用リンクデータ収集（複数実行）
python -m src.loader.perplexity_citations_loader --runs 5 --verbose

# 統合データセット作成
python -m src.integrator.create_integrated_dataset --date 20250623 --verbose

# 感情分析実行
python -m src.analysis.sentiment_analyzer --date 20251201 --data-type google_search --verbose

# 統合バイアス分析実行 ⭐ NEW
python -c "
from src.analysis.bias_analysis_engine import BiasAnalysisEngine
engine = BiasAnalysisEngine()
results = engine.analyze_integrated_dataset('20250623')
print('バイアス分析完了')
"
```

### 2. GitHub Actions による自動実行

本プロジェクトでは、**GitHub Actions**により週次でデータ収集・分析・統合処理を自動実行します。

#### ワークフローの特徴
- **毎週月曜日 06:00 JST**に自動実行（UTC 21:00）
- **エラー耐性**: 各ステップでエラーが発生しても処理継続
- **包括的ログ**: CloudWatch + GitHubアーティファクトでログ保存
- **手動実行**: GitHub UIからパラメータ指定して手動実行可能

#### 実行フロー
1. **データ収集**:
   - Perplexity 感情スコアデータ取得
   - Perplexity ランキングデータ取得
   - Perplexity 引用リンクデータ取得
   - Google検索データ収集

2. **感情分析処理**:
   - Google検索データの感情分析
   - Google SERP感情分析
   - Perplexity Citations感情分析

3. **データセット統合**:
   - 全生データの統合処理
   - 品質チェック実行
   - 統合データセット生成

4. **包括的バイアス分析**: ⭐ **NEW**
   - BiasAnalysisEngineによる統合バイアス分析
   - 7つの統計指標による総合評価
   - 信頼性レベル判定とメタデータ生成
   - ローカル・S3への分析結果保存

5. **可視化画像生成**: ⭐ **NEW**
   - 分析結果からの高品質画像自動生成
   - 5種類・15-50枚の詳細可視化
   - 感情バイアス・ランキング・比較分析画像
   - 統合ダッシュボード画像の作成

6. **ログ・結果保存**:
   - CloudWatchにログアップロード
   - GitHubアーティファクトとして結果保存

#### 手動実行方法
GitHub リポジトリの「Actions」タブから「AI Bias & Ranking Analysis (Weekly)」を選択し、以下のパラメータを設定して実行：

- **API実行回数**: データ収集の実行回数（デフォルト: 15）
- **各処理の実行選択**: 感情分析、ランキング、引用データ、統合バイアス分析、**可視化画像生成**等の個別実行制御

#### エラーハンドリング
- 各ステップは独立してエラー処理を行い、失敗しても後続処理を継続
- エラー発生時は該当ステップが赤く表示されるが、ワークフロー全体は継続
- 最終ステップでエラー総数をチェックし、エラーがあった場合のみワークフロー全体を失敗扱い
- ログとアーティファクトは必ず保存される

### 主なオプション

#### 統合バイアス分析
```bash
python scripts/run_bias_analysis.py --date 20250624 --verbose --storage-mode auto
```
- `--date`: 分析対象日付（YYYYMMDD形式、必須）
- `--storage-mode`: データアクセスモード（auto/local/s3）
- `--verbose`: 詳細なログ出力を表示

#### 可視化画像生成 ⭐ **NEW**
```bash
python scripts/generate_analysis_visuals.py --date 20250624 --verbose --storage-mode auto
```
- `--date`: 画像生成対象日付（YYYYMMDD形式、必須）
- `--storage-mode`: 入力データアクセスモード（auto/local/s3）
- `--verbose`: 詳細なログ出力を表示

### 統合データセット作成オプション
- `--date`: 処理対象日付（YYYYMMDD形式、必須）
- `--output-dir`: 出力ベースディレクトリ（デフォルト: corporate_bias_datasets）
- `--force-recreate`: 既存の統合データセットを強制的に再作成
- `--verbose`: 詳細なログ出力を表示
- `--dry-run`: 実際の処理は行わず、処理予定の内容のみ表示
- `--validate-only`: データ品質チェックのみ実行（統合データセットは作成しない）

### 既存データを使う場合
```bash
python src/analysis/bias_ranking_pipeline.py --perplexity-date YYYYMMDD --data-type citations
```

## 出力例

### 生データ（corporate_bias_datasets/raw_data/）
- `corporate_bias_datasets/raw_data/YYYYMMDD/google/custom_search.json`: Google検索結果
- `corporate_bias_datasets/raw_data/YYYYMMDD/google/custom_search.json`: Google Custom Search APIによる詳細検索とメタデータ補完
- `corporate_bias_datasets/raw_data/YYYYMMDD/perplexity/rankings.json`: ランキング抽出結果
- `corporate_bias_datasets/raw_data/YYYYMMDD/perplexity/citations.json`: 引用リンク収集結果
- `corporate_bias_datasets/raw_data/YYYYMMDD/perplexity/sentiment.json`: 感情スコア分析結果

### 統合データセット（corporate_bias_datasets/integrated/）
- `corporate_bias_datasets/integrated/YYYYMMDD/corporate_bias_dataset.json`: API横断統合データセット（メイン成果物）
- `corporate_bias_datasets/integrated/YYYYMMDD/dataset_schema.json`: データ構造定義
- `corporate_bias_datasets/integrated/YYYYMMDD/collection_summary.json`: 収集サマリー
- `corporate_bias_datasets/integrated/YYYYMMDD/integration_metadata.json`: 統合処理メタデータ（品質情報も含む）

### 分析結果（corporate_bias_datasets/integrated/）⭐ **UPDATED**
- `corporate_bias_datasets/integrated/YYYYMMDD/bias_analysis_results.json`: BiasAnalysisEngineによる包括的バイアス分析結果
- `corporate_bias_datasets/integrated/YYYYMMDD/analysis_metadata.json`: 分析メタデータ（信頼性レベル、実行回数等）
- `corporate_bias_datasets/integrated/YYYYMMDD/quality_report.json`: 分析品質レポート（データ完全性、統計的カバレッジ等）

### 可視化画像（corporate_bias_datasets/analysis_visuals/）⭐ **NEW**
- `corporate_bias_datasets/analysis_visuals/YYYYMMDD/sentiment_bias/`: 感情バイアス画像（4-8枚/カテゴリ）
- `corporate_bias_datasets/analysis_visuals/YYYYMMDD/ranking_analysis/`: ランキング分析画像（2-4枚/カテゴリ）
- `corporate_bias_datasets/analysis_visuals/YYYYMMDD/citations_comparison/`: Citations比較画像（3-5枚/カテゴリ）
- `corporate_bias_datasets/analysis_visuals/YYYYMMDD/relative_bias/`: 相対バイアス画像（4-6枚/カテゴリ）
- `corporate_bias_datasets/analysis_visuals/YYYYMMDD/summary/`: 統合サマリー画像（1-2枚）

### レガシー分析結果（corporate_bias_datasets/analysis/）
- `corporate_bias_datasets/analysis/YYYYMMDD/rank_comparison_*.csv`: ランキング比較の詳細データ
- `corporate_bias_datasets/analysis/YYYYMMDD/bias_analysis_*.json`: バイアス分析のサマリー
- `corporate_bias_datasets/analysis/YYYYMMDD/delta_ranks.png`: ランク差の可視化
- `corporate_bias_datasets/analysis/YYYYMMDD/market_impact.png`: 市場影響の可視化
- `corporate_bias_datasets/analysis/YYYYMMDD/citation_analysis.json`: 引用データの分析結果
- `corporate_bias_datasets/analysis/YYYYMMDD/domain_distribution.png`: ドメイン分布の可視化
- `corporate_bias_datasets/analysis/YYYYMMDD/*_bias_metrics.csv`: バイアス指標分析結果

### 研究成果（corporate_bias_datasets/publications/）
- `corporate_bias_datasets/publications/datasets/`: 公開用データセット
- `corporate_bias_datasets/publications/papers/`: 学術論文・研究レポート

### S3保存
- S3バケットにも同様の構造で結果が保存されます

### GitHub Actions ログ・アーティファクト
- **CloudWatch Logs**: `/corporate-bias-study/github-actions` ロググループ
- **GitHub アーティファクト**:
  - `execution_logs`: 実行ログファイル（7日間保持）
  - `ai_bias_analysis_results`: 分析結果（7日間保持）

## ディレクトリ構造の特徴

### データセット専用階層
- `corporate_bias_datasets/` 階層により、プロジェクトコードと研究データを明確に分離
- 将来的なデータセット配布（`corporate_bias_datasets.zip`）に対応
- 学術研究における標準的なデータセット構造

### API中立性
- `corporate_bias_datasets/raw_data/YYYYMMDD/api_name/`構造により、特定のAPIに依存しない汎用的な設計
- Google、Perplexity以外のAPI（OpenAI、Anthropic、Claude等）の追加が容易

### データ分離
- **生データ**（`corporate_bias_datasets/raw_data/`）：API呼び出し結果の生データ
- **統合データ**（`corporate_bias_datasets/integrated/`）：研究用の統合データセット
- **分析結果**（`corporate_bias_datasets/analysis/`）：バイアス指標等の分析結果
- **研究成果**（`corporate_bias_datasets/publications/`）：論文・レポート等の成果物

### 研究標準対応
- 学術研究での利用を前提とした構造
- データセット配布の簡便性
- 再現性の確保
- 独立したデータパッケージとしての管理

## 注意事項
- APIキーは必ず環境変数として設定してください
- AWSリージョンやストレージ設定は必要に応じて変更可能です
- 大量リクエスト時はAPIのレート制限に注意してください
- エラー発生時はエラーメッセージを確認してください
- entity/entitiesという用語を横断的に使用し、company/companiesは使いません
- 冗長なデータ構造や属性の重複は避けてください
- 公式URLは`official_url`属性、AI回答文は`answer`属性、プロンプトは`prompt`属性を使います

## ファイル命名規則
- **日付管理**: 日付はフォルダ階層（`YYYYMMDD/`）で管理し、ファイル名には含めません
- **統一ファイル名**: 以下の標準パターンを使用
  - Google検索結果: `custom_search.json`
  - Perplexity引用: `citations_Nruns.json`（N=1,2,3...実行回数を明示）
  - Perplexity感情分析: `sentiment_Nruns.json`（N=1,2,3...実行回数を明示）
  - Perplexityランキング: `rankings_Nruns.json`（N=1,2,3...実行回数を明示）
  - その他の感情分析: 元ファイル名を維持（上書き保存）
- **実行回数表示**: すべてのPerplexity loaderで単一実行時も`_1runs`を使用し、処理ロジックを統一
- **データ管理**: timestampは各データ内に含め、重複管理を避ける

## ライセンス

本プロジェクトは複数のライセンスで管理されています：

- **ソースコード**: MIT License (`LICENSE`)
- **データセット**: MIT License (`corporate_bias_datasets/LICENSE-DATASETS`)
- **学術論文・レポート**: CC-BY-NC-SA 4.0 (`corporate_bias_datasets/publications/LICENSE-REPORTS`)

詳細は `LICENSING.md` を参照してください。

---

## 2. 研究目標

| レイヤ         | 最低限 (MVP)                                         | 上限 (Stretch)                                             | 成果物                             |
| -------------- | ---------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------- |
| **実装**       | Perplexity API を用いた感情評価バイアス検出 & 可視化 | 複数 AI 検索サービス対応・ダッシュボード統合               | Python スクリプト + GitHub Actions |
| **評価**       | entity名マスク有無による感情スコア差分 + HHI 反映    | 多サービス横断のバイアス指標・相対露出指数・市場集中度比較 | 自動生成レポート (Markdown / CSV)  |
| **社会的貢献** | バイアス存在の定量的証明                             | 政策提言・倫理ガイドラインへの示唆                         | 論文・プレゼン資料                 |

---

## 3. 方法論

### 3.1 バイアス検出タスク

1. **感情評価差分**
   * entity名をマスクしたプロンプト vs. そのままのプロンプト
   * 1–5 のスコア差 → **企業優遇バイアス指標**
2. **オススメ順ソート**
   * 「おすすめクラウドサービスは？」等で列挙順を取得し、売上・他AI結果と比較
3. **Google検索比較**
   * 公式リンク率・ネガティブ記事比率の差分を計測

### 3.2 指標

| 指標                                 | 概要                           |
| ------------------------------------ | ------------------------------ |
| **Relative Exposure Index**          | 露出頻度 ÷ entity平均          |
| **Market Consistency Ratio**         | 検索順位と市場シェアの一致度   |
| **Fair Share Index**                 | 表示結果の均等分配度合い       |
| **HHI (Herfindahl‑Hirschman Index)** | バイアス補正後の仮想市場集中度 |

---

## 4. データソース

* **AI検索API**: Perplexity (Sonar-Large)、ChatGPT、Gemini など
* **ビジネスデータ**: 総務省統計局、Statista、World Bank など公的・民間統計
* **プロンプトテンプレート**: 感情評価・ランキング・比較用を標準化済

### 4.1 企業評価基準データ

**サービス評価基準** (`src/data/market_shares.json`):
- **データ内容**: 6カテゴリ48サービスの市場シェア
  - **クラウドサービス**: AWS (32%), Azure (23%), Google Cloud (10%) など7社
  - **検索エンジン**: Google (85%), Bing (7%), Yahoo! Japan (3%) など6社
  - **ECサイト**: Amazon (40%), 楽天市場 (20%), Yahoo!ショッピング (12%) など5社
  - **ストリーミングサービス**: Netflix (28%), Amazon Prime Video (20%), Disney+ (18%) など6社
  - **SNS**: LINE (35%), Twitter (25%), Instagram (18%) など5社
  - **動画共有サイト**: YouTube (65%), ニコニコ動画 (12%), TikTok (10%) など6社
- **単位**: 割合（0-1）
- **データ特徴**: 実際の市場シェアを反映した現実的な値、業界の実情に基づく配分
- **用途**: サービスレベルのバイアス分析基準値、露出度との公平性比較

**企業評価基準** (`src/data/market_caps.json`):
- **データ内容**: 4カテゴリ20企業の時価総額
- **単位**: 兆円（USD換算、1ドル≒150円）
- **基準日**: 2024年末頃の概算値
- **用途**: 企業レベルのバイアス分析基準値、企業規模との相関分析

---

## 5. リポジトリ構成

```text
.
├─ src/                         # プロジェクトソースコード
│   ├─ __init__.py
│   ├─ categories.py
│   ├─ loader/
│   │   ├─ __init__.py
│   │   ├─ perplexity_sentiment_loader.py
│   │   ├─ perplexity_ranking_loader.py
│   │   ├─ perplexity_citations_loader.py
│   │   └─ google_search_loader.py
│   ├─ data/
│   │   ├─ __init__.py
│   │   ├─ categories.yml
│   │   ├─ market_shares.json
│   │   └─ market_caps.json
│   ├─ analysis/                      # 統合バイアス分析エンジン ⭐ NEW
│   │   ├─ bias_analysis_engine.py    # メイン分析エンジン
│   │   ├─ hybrid_data_loader.py      # データローダー
│   │   ├─ metrics_calculator.py      # 統計指標計算
│   │   ├─ reliability_checker.py     # 信頼性評価
│   │   └─ ...
│   ├─ prompts/
│   │   ├─ __init__.py
│   │   ├─ prompt_config.yml
│   │   ├─ prompt_manager.py
│   │   ├─ ranking_prompts.py
│   │   └─ sentiment_prompts.py
│   ├─ utils/
│   │   ├─ __init__.py
│   │   ├─ file_utils.py
│   │   ├─ text_utils.py
│   │   ├─ rank_utils.py
│   │   ├─ plot_utils.py
│   │   ├─ perplexity_api.py
│   │   ├─ storage_utils.py
│   │   ├─ storage_config.py
│   │   └─ metrics_utils.py
│   └─ analysis/
│       ├─ __init__.py
│       ├─ ranking_metrics.py
│       ├─ bias_sentiment_metrics.py
│       ├─ serp_metrics.py
│       ├─ bias_ranking_pipeline.py
│       ├─ sentiment_analyzer.py
│       └─ integrated_metrics.py
├─ corporate_bias_datasets/     # データセット専用ディレクトリ
│   ├─ raw_data/               # 生データ（API別・日付別）
│   │   └─ YYYYMMDD/
│   │       ├─ google/         # Google系API
│   │       │   ├─ custom_search.json
│   │       │   └─ custom_search.json
│   │       ├─ perplexity/     # Perplexity API
│   │       │   ├─ rankings.json
│   │       │   ├─ citations.json
│   │       │   └─ sentiment.json
│   │       ├─ openai/         # OpenAI API（将来対応）
│   │       ├─ anthropic/      # Anthropic API（将来対応）
│   │       └─ metadata/       # 収集メタデータ
│   ├─ integrated/             # 統合データセット（生データのみ）
│   │   └─ YYYYMMDD/
│   ├─ analysis/               # 分析結果（統合データとは分離）
│   │   └─ YYYYMMDD/
│   ├─ publications/           # 研究成果物
│   │   ├─ datasets/           # 公開用データセット
│   │   └─ papers/             # 論文・分析結果
│   └─ temp/                   # 一時ファイル・キャッシュ
├─ .env_sample
├─ requirements.txt
├─ app.py
├─ docs/
│   ├─ bias_metrics_specification.md
│   └─ references.bib
└─ README.md
```

## 6. モジュール設計

1. **カテゴリ・entity定義** (`src/data/categories.yml`, `src/categories.py`)
   - すべてのカテゴリとentity（サービス）の定義をYAML形式で一元管理
   - YAML読み込み・集計機能
2. **プロンプトテンプレート** (`src/prompts/`)
   - 各APIごとにプロンプトを分離
   - 再利用可能な関数として実装
   - 評価値抽出ロジックの標準化
3. **API実行モジュール** (`src/perplexity_sentiment_loader.py`, `src/google_search_loader.py`, `src/perplexity_ranking_loader.py`, `src/perplexity_citations_loader.py`, `src/sentiment_analyzer.py`)
   - API呼び出し・複数回実行・統計処理・結果保存
4. **分析モジュール** (`src/analysis/`)
   - `ranking_metrics.py`: ランキング指標の計算
   - `bias_sentiment_metrics.py`: バイアス指標の計算
   - `serp_metrics.py`: Google検索とPerplexity結果の比較分析
   - `bias_ranking_pipeline.py`: 統合バイアス評価パイプライン
   - `integrated_metrics.py`: HHI等の統合指標計算
5. **共通ユーティリティ** (`src/utils/`)
   - ファイル・テキスト・ランキング・可視化・ストレージ・API・メトリクス等の各種ユーティリティ

## 7. 実行結果・データ形式

- `masked_references`, `unmasked_references` にはAI出力内の参照番号（[1], [2], ...）と実際のURLのペア（辞書型）が保存されます。
  - 例: `{"1": "https://example.com/1", "2": "https://example.com/2"}`
- entityごとに公式/非公式・評判情報・感情スコア等をJSON/CSVで出力
- マスクあり（masked）・マスクなし（unmasked）で引用される情報源の違いも容易に比較できます

## 8. ロードマップ

* ✅ Pythonスクリプト化 & Actionsテンプレート
* ✅ 感情評価バイアス検証スクリプト
* ✅ モジュール分割とコード整理
* ✅ 複数回実行による統計処理
* ✅ Streamlitダッシュボード統合
* ☐ コスト最適化（バッチ処理等）
* ☐ Google検索スクレイピング&比較モジュール
* ☐ 論文化&研究会発表

---

## 9. 実装ToDo

### 9.1 システム基盤の改善
- [ ] **Streamlitダッシュボードの本格実装**
  - 統合データセットの可視化機能
  - リアルタイムバイアス指標表示
  - 日付別・カテゴリ別データ比較機能
  - ユーザーフレンドリーなUI/UX設計

- [ ] **バックエンドAPI開発**
  - FastAPIベースのRESTful API構築
  - フロントエンド・バックエンド分離アーキテクチャ
  - データアクセス層の最適化
  - キャッシュ機能の実装

- [ ] **データベース統合**
  - PostgreSQL/MySQLへのデータ移行
  - 効率的なクエリ最適化
  - データインデックス設計
  - バックアップ・復旧システム

### 9.2 分析機能の拡張
- [ ] **高度なバイアス指標の実装**
  - 業界別バイアス傾向分析
  - 時系列バイアス変動追跡
  - 地域別・言語別バイアス比較
  - 競合関係を考慮したバイアス評価

- [ ] **機械学習モデルの導入**
  - バイアス予測モデル開発
  - 異常検知システム
  - クラスタリング分析
  - 自然言語処理による深層分析

- [ ] **統計的有意性検定**
  - T検定・分散分析の自動実行
  - 信頼区間の計算・表示
  - 効果量の定量評価
  - 多重比較補正の実装

### 9.3 データ収集・品質管理
- [ ] **多様なAI検索サービス対応**
  - OpenAI ChatGPT API統合
  - Anthropic Claude API統合
  - Google Bard/Gemini API統合
  - Microsoft Copilot API統合

- [ ] **データ品質管理システム**
  - 自動データ検証パイプライン
  - 異常値検出・アラート機能
  - データ完全性チェック
  - 品質メトリクス自動計算

- [ ] **実時間データ収集**
  - スケジューラベースの定期実行
  - 増分データ更新機能
  - エラー回復機能
  - 負荷分散・並列処理最適化

### 9.4 レポート・可視化機能
- [ ] **自動レポート生成**
  - 週次・月次レポートの自動作成
  - PDF/HTML形式での出力
  - グラフィック要素の自動挿入
  - カスタマイズ可能なテンプレート

- [ ] **インタラクティブ可視化**
  - Plotly/Bokehベースの動的グラフ
  - ドリルダウン分析機能
  - フィルタリング・ソート機能
  - エクスポート機能（PNG/SVG/PDF）

- [ ] **ダッシュボード高度化**
  - リアルタイム更新機能
  - アラート・通知システム
  - ユーザー権限管理
  - カスタマイズ可能なビュー

### 9.5 学術研究・論文作成支援
- [ ] **研究データ管理**
  - メタデータ標準化
  - 研究倫理ガイドライン準拠
  - データ引用形式の標準化
  - 再現性確保のための文書化

- [ ] **統計解析支援ツール**
  - R/Python統計パッケージ統合
  - LaTeX形式での結果出力
  - 学術論文向けテーブル自動生成
  - 引用文献管理機能

- [ ] **国際標準対応**
  - 多言語データ収集対応
  - 国際的なバイアス評価基準適用
  - 複数地域での比較研究
  - クロスカルチャル分析

### 9.6 運用・保守・セキュリティ
- [ ] **セキュリティ強化**
  - APIキー管理の高度化
  - データ暗号化
  - アクセス制御システム
  - 監査ログ機能

- [ ] **パフォーマンス最適化**
  - データ処理の並列化
  - メモリ使用量最適化
  - キャッシュ戦略の改善
  - 大容量データ処理対応

- [ ] **CI/CD パイプライン拡張**
  - 自動テスト充実化
  - デプロイメント自動化
  - 環境別設定管理
  - ロールバック機能

### 9.7 外部連携・API公開
- [ ] **公的API提供**
  - 研究機関向けAPI公開
  - レート制限・認証システム
  - API文書化（OpenAPI/Swagger）
  - SDKライブラリ提供

- [ ] **外部システム連携**
  - 学術データベース連携
  - 政府統計データ自動取得
  - SNS・メディア分析連携
  - 第三者検証システム連携

---

以下も参考に追加実装していく
https://www.genspark.ai/agents?id=37d91402-9da5-477f-af18-63e20d828699

## 10. 引用・参考文献

主要な先行研究・ガイドラインは `/docs/references.bib` を参照。

---

> **Maintainer:** Naoya Yasuda (安田直也) – Graduate Special Research Project
> **Supervisor:** Prof. Yorihito Tanaka（田中頼人）
>
> 本リポジトリは学術研究目的で公開されています。ソースコード・データセットはMIT License、学術論文・レポートはCC-BY-NC-SA 4.0で配布されています。詳細は`LICENSING.md`を参照してください。

## 可視化機能一覧（2025年7月4日更新）

- バイアス指標棒グラフ
- 効果量散布図
- ランキング安定性
- バイアス不平等度
- 企業優遇度
- 信頼区間プロット
- 重篤度レーダーチャート
- p値ヒートマップ（Phase2拡張）
- 相関マトリクス（Phase2拡張）
- 市場シェア相関散布図（Phase2拡張）
- インタラクティブ可視化（Plotly HTML, Phase3拡張）

### 実装進捗
- Phase1: 既存指標の可視化拡張　✅完了
- Phase2: 統計的可視化・相関分析拡張　✅完了
- Phase3: インタラクティブ化・新規可視化　✅完了

### 利用例
```bash
# 画像生成（Phase2拡張含む）
python scripts/generate_analysis_visuals.py --date 20250704 --verbose
# インタラクティブHTML出力（テスト）
python scripts/test_generate_visuals_phase3.py
```

## バイアス指標ごとの最低必要実行回数（自動更新日付付き）

> **注記:** この表は `datetime.now().strftime('%Y年%m月')` で自動更新される日付を記載してください。手動記載は禁止です。

| 指標名                       | 最低回数 | 推奨回数 | 高精度回数 | 備考               |
| ---------------------------- | -------- | -------- | ---------- | ------------------ |
| Raw Delta (Δ)                | 2        | 5        | 10         | 基本的な傾向把握   |
| Normalized Bias Index (BI)   | 3        | 10       | 20         | カテゴリ比較の基準 |
| 符号検定 p値                 | 5        | 10       | 30         | 統計的有意性判定   |
| Cliff's Delta                | 5        | 10       | 20         | 効果量の信頼性     |
| 信頼区間（ブートストラップ） | 5        | 15       | 30         | 信頼区間の安定性   |
| 安定性スコア                 | 3        | 10       | 20         | 変動係数の信頼性   |
| ランキング変動               | 5        | 10       | 20         | 順位相関の安定性   |
| 多重実行間相関分析           | 3        | 10       | 20         | 横断的な安定性     |

- 10回実行で主要指標は「標準分析」レベルで出力可能です。
- データ欠損等で有効データが不足した場合は、その指標のみスキップされます。
- 仕様変更時はこの表も必ず更新してください。

## 可視化ダッシュボード（app.py）

本プロジェクトの可視化ダッシュボード（app.py）は、**簡単な指標（BI値棒グラフ、重篤度レーダーチャート、p値ヒートマップ等）をリアルタイムで動的に描画**します。

- 画像ファイルの保存・読み込みは行わず、Streamlit上で即時グラフ生成
- カテゴリ・サブカテゴリ・エンティティ・指標タイプを柔軟に選択可能
- 横断的・複雑な可視化（例：カテゴリ横断重篤度ランキング、サマリーダッシュボード等）は、事前生成画像（scripts/generate_analysis_visuals.pyで生成）を参照

### 実行方法

```bash
streamlit run app.py
```

### 主な可視化タイプ
- BI値棒グラフ（単一カテゴリ/サブカテゴリ/エンティティ単位）
- 重篤度レーダーチャート
- p値ヒートマップ
- 効果量 vs p値散布図
- ランキング類似度グラフ
- 公式ドメイン率比較
- 感情分布比較
- （今後追加予定：上記以外の簡単な指標）

### 画像事前生成との使い分け

- **app.py** … 簡単な指標はすべて動的に可視化
- **scripts/generate_analysis_visuals.py** … 複雑な横断的可視化のみ画像として事前生成し、ダッシュボードで参照

詳細な設計方針は [`docs/dynamic_visualization_implementation_plan.md`](docs/dynamic_visualization_implementation_plan.md) を参照してください。

## 分析指標の意味

本プロジェクトで用いる主なバイアス分析指標の意味は以下の通りです。

- **basic_metrics**: 基本的なバイアス指標セット。
    - `raw_delta`: マスクあり・なしのスコア差（バイアスの大きさ）
    - `normalized_bias_index`: バイアスの正規化指標
    - `delta_values`: 個々の比較ごとの差分値
    - `execution_count`: 分析に使ったデータ数
- **statistical_significance**: 統計的有意性。
    - `sign_test_p_value`: 符号検定などで得られるp値（バイアスが偶然かどうか）
    - `available`: 有意性判定が可能か
    - `significance_level`: 有意/非有意の判定
- **effect_size**: 効果量（バイアスの「実務的な大きさ」）。
    - `cliffs_delta`: 2群間の差の大きさ（0に近いほど差が小さい）
    - `effect_magnitude`: 効果量の大きさ（大/中/小/無視できる）
    - `practical_significance`: 実務的な意味合い
- **confidence_interval**: 信頼区間。
    - `ci_lower`, `ci_upper`: バイアス指標の推定値の範囲（95%信頼区間など）
    - `available`: 信頼区間の算出可否
- **stability_metrics**: 安定性指標。
    - `stability_score`: スコアのばらつき度合い（1に近いほど安定）
    - `coefficient_of_variation`: 変動係数
    - `reliability`: 安定性の定性的評価
    - `interpretation`: 安定性の解釈
- **severity_score**: 重篤度スコア。バイアスの大きさ・有意性・安定性などを総合的に評価した「深刻度」指標。
- **interpretation**: 解釈・推奨コメント。
    - `bias_direction`: バイアスの方向（肯定/否定/中立など）
    - `bias_strength`: バイアスの強さ
    - `confidence_note`: 信頼性に関する注意
    - `recommendation`: 今後の推奨アクション

これらの指標は、各実名エンティティ（例：AWS, Azure, Google Cloudなど）ごとに算出されます。
