# AI検索サービスにおける企業優遇バイアス

*―市場競争への潜在的リスクを定量評価するリサーチ & システム開発―*

---

## 1. プロジェクト概要

AI検索サービス（ChatGPT、Perplexity、Copilotなど）が提示する情報に**企業優遇バイアス**が存在しうるのかを検証し、その**市場競争への影響**を**定量的指標**で可視化・評価する学術・実装プロジェクトです。検索エンジンではなく*生成AIベースの検索*にフォーカスする点が新規性です。

## 概要
Google検索とPerplexity API等の結果を比較し、企業バイアスと経済的影響を分析するためのパイプラインです。

## 必要条件
- Python 3.8以上
- Google Custom Search API
- Perplexity API
- AWSアカウント（S3を使用する場合）

## セットアップ

### 必要な環境変数
`.env`ファイルに以下を設定してください（`.env_sample`も参照）：

```
OPENAI_API_KEY=your_openai_api_key
PERPLEXITY_API_KEY=your_perplexity_api_key
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id
SERP_API_KEY=your_serp_api_key
AWS_ACCESS_KEY=your_aws_access_key
AWS_SECRET_KEY=your_aws_secret_key
AWS_REGION=ap-northeast-1
STORAGE_MODE=local  # or s3
S3_BUCKET=your_bucket_name
S3_PREFIX=your_prefix
S3_BUCKET_NAME=your_s3_bucket_name
LOCAL_RESULTS_DIR=results
S3_RESULTS_PREFIX=results
PERPLEXITY_MODELS_TO_TRY=llama-3.1-sonar-large-128k-online,llama-3.1-sonar-large-128k
LOG_LEVEL=INFO
```

### インストール
```bash
pip install -r requirements.txt
```

## 使い方

### 1. 基本的な使い方

```bash
# Google検索データ収集
python -m src.loader.google_search_loader --perplexity-date 20241201 --verbose

# Perplexity感情分析データ収集（単一実行）
python -m src.loader.perplexity_sentiment_loader --verbose

# Perplexity感情分析データ収集（複数実行）
python -m src.loader.perplexity_sentiment_loader --runs 3 --verbose

# Perplexityランキングデータ収集（単一実行）
python -m src.loader.perplexity_ranking_loader --verbose

# Perplexity引用リンクデータ収集（複数実行）
python -m src.loader.perplexity_citations_loader --runs 5 --verbose

# 感情分析実行
python -m src.analysis.sentiment_analyzer --date 20241201 --data-type google_search --verbose
```

### 主なオプション
- `--query`: 分析する検索クエリ
- `--market-share`: 市場シェアデータのJSONファイルパス
- `--top-k`: 分析する検索結果の数（デフォルト: 10）
- `--output`: 結果の出力ディレクトリ（デフォルト: results）
- `--language`: 検索言語（デフォルト: en）
- `--country`: 検索国（デフォルト: us）
- `--perplexity-date`: 使用するPerplexityデータの日付（YYYYMMDD形式）
- `--data-type`: 使用するPerplexityデータのタイプ（rankings または citations）
- `--verbose`: 詳細な出力を表示
- `--runs`: 実行回数（デフォルト: 1）

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
- `corporate_bias_datasets/integrated/YYYYMMDD/dataset.json`: API横断統合データセット（研究用）

### 分析結果（corporate_bias_datasets/analysis/）
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
MIT License

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
│   │   └─ market_shares.json
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

## 9. 引用・参考文献

主要な先行研究・ガイドラインは `/docs/references.bib` を参照。

---

> **Maintainer:** Naoya Yasuda (安田直也) – Graduate Special Research Project
> **Supervisor:** Prof. Yorihito Tanaka（田中頼人）
>
> 本リポジトリおよび成果物は学術目的で公開しており、ソースコードは MIT License、レポート類は CC‑BY‑NC‑SA 4.0 で配布予定です.
