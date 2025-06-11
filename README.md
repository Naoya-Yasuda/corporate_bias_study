# AI検索サービスにおける企業優遇バイアス

*―市場競争への潜在的リスクを定量評価するリサーチ & システム開発―*

---

## 1. プロジェクト概要

AI 検索サービス（ChatGPT、Perplexity、Copilot など）が提示する情報に **企業優遇バイアス** が存在しうるのかを検証し、
その **市場競争への影響** を **定量的指標** で可視化・評価することを目的とした学術・実装プロジェクトです。検索エンジンではなく *生成 AI ベースの検索* にフォーカスする点が新規性となります。

## 概要
このプロジェクトは、Google検索とPerplexity APIの結果を比較し、企業バイアスと経済的影響を分析するためのパイプラインです。

## 必要条件
- Python 3.8以上
- Google Custom Search API
- OpenAI API
- AWSアカウント（S3を使用する場合）

## セットアップ

### 必要な環境変数
`.env`ファイルに以下の環境変数を設定してください：

```
PERPLEXITY_API_KEY=your_perplexity_api_key
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id
AWS_REGION=ap-northeast-1  # AWSリージョン（デフォルト: ap-northeast-1）
AWS_ACCESS_KEY=your_aws_access_key
AWS_SECRET_KEY=your_aws_secret_key
S3_BUCKET_NAME=your_bucket_name
```

### インストール
```bash
pip install -r requirements.txt
```

## 使用方法

### 基本的な使用方法
```bash
python src/analysis/bias_ranking_pipeline.py --query "your search query"
```

### オプション
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

### 既存データを使用する場合
```bash
python src/analysis/bias_ranking_pipeline.py --perplexity-date YYYYMMDD --data-type citations
```

## 出力
- `rank_comparison.csv`: ランキング比較の詳細データ
- `bias_analysis.json`: バイアス分析のサマリー
- `delta_ranks.png`: ランク差の可視化
- `market_impact.png`: 市場影響の可視化
- `citation_analysis.json`: 引用データの分析結果
- `domain_distribution.png`: ドメイン分布の可視化

## 注意事項
- APIキーは必ず環境変数として設定してください
- AWSリージョンは必要に応じて変更可能です（デフォルト: ap-northeast-1）
- 大量のリクエストを送信する場合は、APIのレート制限に注意してください

## ライセンス
MIT License

---

## 2. 研究目標

| レイヤ         | 最低限 (MVP)                                         | 上限 (Stretch)                                             | 成果物                             |
| -------------- | ---------------------------------------------------- | ---------------------------------------------------------- | ---------------------------------- |
| **実装**       | Perplexity API を用いた感情評価バイアス検出 & 可視化 | 複数 AI 検索サービス対応・ダッシュボード統合               | Python スクリプト + GitHub Actions |
| **評価**       | 企業名マスク有無による感情スコア差分 + HHI 反映      | 多サービス横断のバイアス指標・相対露出指数・市場集中度比較 | 自動生成レポート (Markdown / CSV)  |
| **社会的貢献** | バイアス存在の定量的証明                             | 政策提言・倫理ガイドラインへの示唆                         | 論文・プレゼン資料                 |

---

## 3. 方法論

### 3.1 バイアス検出タスク

1. **感情評価差分**

   * 商品／サービス名をマスクしたプロンプト vs. そのままのプロンプト
   * 1–5 のスコア差 → **企業優遇バイアス指標**
2. **オススメ順ソート**

   * 「おすすめクラウドサービスは？」等で列挙順を取得し、売上・他 AI 結果と比較
3. **Google 検索比較**

   * 公式リンク率・ネガティブ記事比率の差分を計測

### 3.2 指標

| 指標                                 | 概要                           |
| ------------------------------------ | ------------------------------ |
| **Relative Exposure Index**          | 露出頻度 ÷ 企業平均            |
| **Market Consistency Ratio**         | 検索順位と市場シェアの一致度   |
| **Fair Share Index**                 | 表示結果の均等分配度合い       |
| **HHI (Herfindahl‑Hirschman Index)** | バイアス補正後の仮想市場集中度 |

---

## 4. データソース

* **AI 検索 API**: Perplexity (Sonar-Large)、ChatGPT、Gemini など
* **ビジネスデータ**: 総務省統計局、Statista、World Bank など公的・民間統計
* **プロンプトテンプレート**: 感情評価・ランキング・比較用を標準化済

---

## 5. リポジトリ構成

```text
.
├─ src/                      # ソースコード
│   ├─ __init__.py           # パッケージ初期化ファイル
│   ├─ categories.py         # カテゴリとサービス定義読み込み機能
│   ├─ perplexity_sentiment_loader.py # Perplexity APIによる感情スコア取得
│   ├─ perplexity_ranking_loader.py # Perplexity APIによるランキング取得
│   ├─ perplexity_citations_loader.py # Perplexity APIによる引用リンク取得
│   ├─ google_serp_loader.py # Google SERP APIによる検索データ取得
│   ├─ data/                 # データファイル
│   │   ├─ __init__.py
│   │   └─ categories.yml    # カテゴリとサービス定義（YAML）
│   ├─ prompts/              # プロンプトテンプレート
│   │   ├─ __init__.py
│   │   └─ perplexity_prompts.py # Perplexity用プロンプト
│   ├─ utils/                # 共通ユーティリティ
│   │   ├─ __init__.py       # 共通ユーティリティの初期化ファイル
│   │   ├─ s3_utils.py       # S3操作のユーティリティ
│   │   ├─ file_utils.py     # ファイル操作のユーティリティ
│   │   ├─ text_utils.py     # テキスト処理のユーティリティ
│   │   ├─ rank_utils.py     # ランキング処理のユーティリティ
│   │   ├─ plot_utils.py     # 可視化のユーティリティ
│   │   └─ perplexity_api.py # Perplexity API共通クラス
│   └─ analysis/             # 分析・可視化ツール
│       ├─ __init__.py
│       ├─ ranking_metrics.py # ランキング指標の計算
│       ├─ bias_sentiment_metrics.py # バイアス指標の計算
│       ├─ serp_metrics.py   # Google検索とPerplexity結果の比較分析
│       └─ bias_ranking_pipeline.py # 統合されたバイアス評価
├─ results/                  # 結果保存先（自動生成）
├─ .env                      # 環境変数（gitignore対象）
├─ .github/
│   └─ workflows/            # GitHub Actions定義ファイル
├─ requirements.txt          # 依存パッケージリスト
└─ README.md                 # 本ファイル
```

## 6. モジュール設計

本プロジェクトは以下のようにモジュール化されています：

1. **カテゴリとサービス定義** (`src/data/categories.yml` と `src/categories.py`)
   - すべてのカテゴリとサービスの定義をYAML形式で一元管理
   - YAML読み込み機能
   - カウント・集計機能

2. **プロンプトテンプレート** (`src/prompts/`)
   - 各APIごとにプロンプトを分離
   - 再利用可能な関数として実装
   - 評価値抽出ロジックの標準化

3. **API実行モジュール** (`src/perplexity_sentiment_loader.py`, `src/google_serp_loader.py`, `src/perplexity_ranking_loader.py`, `src/perplexity_citations_loader.py`)
   - API呼び出し処理
   - 複数回実行と統計処理
   - 結果の保存機能

4. **分析モジュール** (`src/analysis/`)
   - `ranking_metrics.py`: ランキング指標の計算（露出度、公平性ギャップ等）
   - `bias_sentiment_metrics.py`: バイアス指標の計算（統計的公平性、機会均等比率等）
   - `serp_metrics.py`: Google検索とPerplexity結果の比較分析
   - `bias_ranking_pipeline.py`: 統合されたバイアス評価パイプライン

5. **共通ユーティリティ** (`src/utils/`)
   - `s3_utils.py`: S3へのデータ保存・アップロード機能
   - `file_utils.py`: ファイル操作とJSON読み書き機能
   - `text_utils.py`: URLからのドメイン抽出、ネガティブ判定機能
   - `rank_utils.py`: ランキング操作とRBO、Kendallのタウ係数計算
   - `plot_utils.py`: データ可視化と標準グラフ生成

## 7. 実行結果

* `results/YYYYMMDD_perplexity_results.json` : Perplexity APIのバイアス評価結果（単一実行）
* `results/YYYYMMDD_perplexity_results_10runs.json` : Perplexity APIのバイアス評価結果（複数実行時）
* `results/YYYYMMDD_perplexity_rankings.json` : Perplexity APIのランキング抽出結果（単一実行）
* `results/YYYYMMDD_perplexity_rankings_10runs.json` : Perplexity APIのランキング抽出結果（複数実行時）
* `results/YYYYMMDD_perplexity_citations.json` : Perplexity APIの引用リンク順番結果（単一実行）
* `results/YYYYMMDD_perplexity_citations_10runs.json` : Perplexity APIの引用リンク順番結果（複数実行時）
* `results/YYYYMMDD_openai_results.json` : OpenAI APIの結果（単一実行）
* `results/YYYYMMDD_openai_results_10runs.json` : OpenAI APIの結果（複数実行時）
* `results/YYYYMMDD_google_serp_results.json` : Google検索結果
* `results/YYYYMMDD_google_serp_comparison.json` : Google検索とPerplexityの比較結果
* `results/YYYYMMDD_google_serp_analysis.json` : Google検索の分析結果
* `results/analysis/perplexity/YYYYMMDD/YYYYMMDD_*_bias_metrics.csv` : Perplexity APIのバイアス指標分析結果
* `results/analysis/openai/YYYYMMDD/YYYYMMDD_*_bias_metrics.csv` : OpenAI APIのバイアス指標分析結果
* `results/perplexity_analysis/YYYYMMDD/` : ランキング分析の結果
* `results/analysis/citations/` : 引用データの分析結果
* 同様の結果がS3バケットにも保存されます

## 8. ロードマップ

* ✅ Python スクリプト化 & Poetry / Actions テンプレート
* ✅ 感情評価バイアス検証スクリプト
* ✅ モジュール分割とコード整理
* ✅ 複数回実行による統計処理
* ✅ Streamlitダッシュボード統合
* ☐ コスト最適化（バッチ処理等）
* ☐ Google 検索スクレイピング & 比較モジュール
* ☐ 論文化 & 研究会発表

---

## 9. 引用・参考文献

主要な先行研究・ガイドラインは `/docs/references.bib` を参照。

---

> **Maintainer:** Naoya Yasuda (安田直也) – Graduate Special Research Project
> **Supervisor:** Prof. Yorito Tanaka
>
> 本リポジトリおよび成果物は学術目的で公開しており、ソースコードは MIT License、レポート類は CC‑BY‑NC‑SA 4.0 で配布予定です.
