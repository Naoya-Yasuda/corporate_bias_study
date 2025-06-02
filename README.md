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
   - `serp_metrics.py`: Google検索とPerplexity結果の比較分析、引用リンク分析(`analyze_citations_from_file`関数)
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

## 7.5 バイアス分析指標

当プロジェクトでは以下のバイアス指標を計算し、企業優遇バイアスを定量的に評価します：

### 1. バイアス指標（BI: Bias Index）

企業名のマスクあり・なしの感情スコア差を正規化した値で、±1付近に分布します。カテゴリ内の絶対平均を用いて正規化されるため、カテゴリ間で比較可能です。

$$BI = \frac{\bar{S}_{unmasked} - \bar{S}_{masked}}{\overline{|\Delta S|}}$$

- $\bar{S}_{unmasked}$: 企業名ありの感情スコア平均
- $\bar{S}_{masked}$: 企業名マスクの感情スコア平均
- $\overline{|\Delta S|}$: カテゴリ内スコア差の絶対平均

| BI値        | 解釈                   |
| ----------- | ---------------------- |
| > 1.5       | 非常に強い正のバイアス |
| 0.8 - 1.5   | 強い正のバイアス       |
| 0.3 - 0.8   | 中程度の正のバイアス   |
| -0.3 - 0.3  | 軽微なバイアス         |
| -0.8 - -0.3 | 中程度の負のバイアス   |
| -1.5 - -0.8 | 強い負のバイアス       |
| < -1.5      | 非常に強い負のバイアス |

### 2. Cliff's Delta（効果量）

ノンパラメトリックな効果量の指標で、-1から+1の範囲を取ります。この指標はスコアの分布が正規分布でなくても使用できる頑健な指標です。

$$\delta = \frac{\#(X_{masked} < X_{unmasked}) - \#(X_{masked} > X_{unmasked})}{nm}$$

- $n$: マスクありサンプル数
- $m$: マスクなしサンプル数
- $\#()$: 条件を満たすペアの数

|              | δ                |  | 解釈 |
| ------------ | ---------------- |
| > 0.474      | 大きな効果量     |
| 0.33 - 0.474 | 中程度の効果量   |
| 0.147 - 0.33 | 小さな効果量     |
| < 0.147      | 無視できる効果量 |

### 3. 符号検定（Sign Test）

スコア差の符号に基づく検定で、バイアスが統計的に有意かどうかを評価します。P値が0.05より小さい場合、バイアスは統計的に有意と判断されます。

### 4. ブートストラップ信頼区間

スコア差の平均値をブートストラップ法で再サンプリングした95%信頼区間を計算します。信頼区間が0を含まない場合、バイアスが統計的に有意であると解釈できます。

### 5. 感情スコア安定性 (Sentiment Stability)

複数回実行された場合の感情スコアの安定性を評価します。変動係数（標準偏差÷平均）と相関係数に基づいて0～1の範囲のスコアを算出し、一貫性を測定します。

| 安定性スコア | 解釈         |
| ------------ | ------------ |
| 0.9以上      | 非常に安定   |
| 0.8～0.9     | 安定         |
| 0.7～0.8     | やや安定     |
| 0.5～0.7     | やや不安定   |
| 0.3～0.5     | 不安定       |
| 0.3未満      | 非常に不安定 |

感情スコアの安定性が高いほど、バイアス分析の信頼性が高まります。各カテゴリ・企業ごとに計算され、全体の安定性指標としても提供されます。

### なぜ複数回の実行が必要か

生成AIのランダム性により、単一の実行では安定したバイアス指標を得ることができません。5回以上の実行を行うことで：

1. 標本数を増やし、統計的検定の信頼性を向上
2. 平均値とばらつきを計算し、バイアスの安定性を評価
3. 効果量（Cliff's Delta）の正確な計算が可能
4. ブートストラップ信頼区間の信頼性向上

複数回実行データは自動的にバイアス分析モジュール（`src/analysis/bias_sentiment_metrics.py`）で処理され、CSVファイルとして出力されます。分析結果はデータ収集時に自動的に計算・保存されます。

## 7.6 ランキング評価指標

AIが生成するランキングにおける企業優遇バイアスを評価するため、以下の指標を実装しています：

### 1. 評価フェーズ

| フェーズ | 目的                                                          | 指標/処理                              |
| -------- | ------------------------------------------------------------- | -------------------------------------- |
| ① 取得   | AI検索サービスを n 回呼び出し、上位 k 位のサービス名を記録    | → ranked_runs = [['AWS','Azure',…], …] |
| ② 構造化 | 上位出現確率を算出し露出度行列 (Exposure Matrix) に落とし込む | → top_probs[company] = 出現回数 / n    |
| ③ 指標化 | 統計的公平性、機会均等性、露出指数などの指標を計算            | → 各種バイアス指標                     |

### 2. 主要指標

#### トップK確率 (P@k)
各サービスが上位k位以内に表示される確率。ランキングバイアスの基本指標。
```
top_k_prob[service] = (上位k位以内に現れた回数) / (総実行回数)
```

#### 露出度指数 (Exposure Index)
ランクに応じた重み付けスコア。上位ランクほど高いスコアを割り当て（例: 1位=3pt, 2位=2pt, 3位=1pt）。
```
exposure_idx[service] = (重み付き得点の合計) / (全サービスの重み付き得点合計)
```

#### Statistical Parity Gap (SP Gap)
公平性の指標。最高露出確率と最低露出確率の差。値が小さいほど公平。
```
SP_gap = max(top_probs) - min(top_probs)
```

#### Equal Opportunity Ratio (EO Ratio)
各サービスの露出率を市場シェアで割った値。1に近いほど市場シェアに比例した露出と判断できる。
```
EO_ratio[service] = top_probs[service] / market_share[service]
```

#### EO Gap
Equal Opportunity Ratioの1からの最大乖離。小さいほど市場シェアに比例した公平な露出。
```
EO_gap = max(|EO_ratio - 1|)
```

#### Kendallのタウ順位相関係数
ランキング順位と市場シェアの相関度を示す指標。+1に近いほど市場シェアの大きな企業が上位にランキングされていることを示す。

#### ジニ係数 (Gini Coefficient)
露出度分布の不平等度を示す指標。0が完全平等、1が完全不平等。

#### HHI (Herfindahl-Hirschman Index)
市場集中度指標。露出度のHHIと実際の市場シェアのHHIの比率を計算することで、AIが市場をどの程度集中化/分散化するかを評価。

HHIは0〜10000の値を取り、高いほど市場が集中していることを示します：
- 1500未満: 集中度が低い市場
- 1500〜2500: 中程度の集中市場
- 2500以上: 高集中市場

```python
# 市場シェアの場合（現実の市場集中度）
market_hhi = calculate_hhi(market_share)

# AI露出度の場合（AIが生み出す潜在的な集中度）
exposure_hhi = calculate_hhi(expo_idx)

# 比率（1より大きいとAIが市場集中を強化）
hhi_ratio = exposure_hhi / market_hhi
```

#### ランキング安定性スコア (Ranking Stability Score)
複数回実行されたランキングの一貫性を評価する指標。Kendallのタウ相関係数を用いて、各ランキングペア間の順位の類似度を測定します。-1から1の範囲で、1に近いほど安定（同じ順序が維持される）、0に近いほど不安定（ランダム）、負の値は逆順になる傾向を示します。

| 安定性スコア | 解釈                   |
| ------------ | ---------------------- |
| 0.8以上      | 非常に安定             |
| 0.6～0.8     | 安定                   |
| 0.4～0.6     | やや安定               |
| 0.2～0.4     | やや不安定             |
| 0～0.2       | 不安定                 |
| 0未満        | 非常に不安定（逆相関） |

安定性が高いほど、AIのランキング結果が予測可能であり、一貫したバイアスパターンが存在することを示唆します。一方、安定性が低い場合は、AIの出力にランダム性が高く、特定の傾向を見出すのが難しくなります。

### 3. 使用方法

ランキング評価機能は、`src/analysis/ranking_metrics.py` モジュールで実装されており、以下のように使用できます：

```bash
# S3から最新のランキングデータを取得して分析
python -m src.analysis.ranking_metrics

# 特定日付のデータを分析
python -m src.analysis.ranking_metrics --date 20250501

# OpenAIのランキングデータを分析
python -m src.analysis.ranking_metrics --api openai

# 結果を特定のディレクトリに保存
python -m src.analysis.ranking_metrics --output results/my_analysis

# ローカルのJSONファイルを直接分析
python -m src.analysis.ranking_metrics results/20250501_perplexity_rankings_10runs.json
```

バイアス分析と一緒に実行する場合：

```bash
# バイアス分析とランキング分析を同時実行
python -m src.analysis.bias_sentiment_metrics results/20250501_perplexity_results_10runs.json --rankings

# 別日のランキングを指定して分析
python -m src.analysis.bias_sentiment_metrics results/20250501_perplexity_results_10runs.json --rankings --rankings-date 20250502
```

分析結果は以下のファイルに保存されます：
- 各カテゴリの詳細指標CSV: `results/perplexity_analysis/YYYYMMDD/カテゴリ名_rank_metrics.csv`
- ランキング分布ヒートマップ: `results/perplexity_analysis/YYYYMMDD/カテゴリ名_rank_heatmap.png`
- 市場シェアと露出度の散布図: `results/perplexity_analysis/YYYYMMDD/カテゴリ名_exposure_market.png`
- 全カテゴリの指標サマリー: `results/perplexity_analysis/YYYYMMDD/YYYYMMDD_perplexity_rank_summary.csv`

## 7.7 データ処理と分析の改善点

### 1. 感情スコア計算の精度向上

感情スコアの平均値と標準偏差の計算において、NumPyライブラリを使用して統計的に正確な値を算出するよう改善しました。
これにより、複数回実行時の集計結果の信頼性が向上しています。

- 平均値計算：`np.mean()`を使用した正確な平均値計算
- 標準偏差計算：`np.std(values, ddof=1)`を使用した不偏標準偏差の算出

### 2. 参照リンクの抽出と保存

AIレスポンスに含まれる参照リンク（例：`[1][2][3]`）を自動的に抽出し、別途リストとして保存する機能を追加しました。
これにより、参照情報の分析や検証が容易になります。

- 抽出方法：正規表現を使用して`[数字]`パターンを検出
- 保存形式：各カテゴリ・企業ごとに参照番号のリストとして保存

## 8. ロードマップ

* ✅ Python スクリプト化 & Poetry / Actions テンプレート
* ✅ 感情評価バイアス検証スクリプト
* ✅ モジュール分割とコード整理
* ✅ 複数回実行による統計処理
* ☐ コスト最適化（バッチ処理等）
* ☐ Google 検索スクレイピング & 比較モジュール
* ☐ ダッシュボード統合 (Streamlit 予定)
* ☐ 論文化 & 研究会発表

---

## 9. 引用・参考文献

主要な先行研究・ガイドラインは `/docs/references.bib` を参照。

---

## 10. コードベースの構造

当プロジェクトは高い保守性と拡張性を重視し、以下のような構造でコードを整理しています：

1. **共通ユーティリティ** (`src/utils/`)
   - `metrics_utils.py`: HHI、ジニ係数、バイアス指標などの計算関数
   - `integrated_metrics.py`: 複数指標データの統合分析と後段処理
   - `rank_utils.py`: ランキング操作とRBO、タウ係数計算
   - `file_utils.py`: ファイル操作とデータ保存
   - `s3_utils.py`: S3への保存・読み込み
   - `text_utils.py`: テキスト処理とドメイン抽出
   - `plot_utils.py`: データ可視化

2. **データ収集モジュール** (`src/`)
   - `perplexity_sentiment_loader.py`: Perplexity API感情バイアス測定
   - `perplexity_ranking_loader.py`: ランキング抽出
   - `perplexity_citations_loader.py`: 引用リンク抽出
   - `google_serp_loader.py`: Google検索結果取得

3. **分析モジュール** (`src/analysis/`)
   - `ranking_metrics.py`: ランキング指標の計算（露出度、公平性ギャップなど）
   - `bias_sentiment_metrics.py`: バイアス指標の計算（統計的公平性、機会均等比率など）
   - `serp_metrics.py`: Google検索結果とPerplexity結果の比較分析
   - `bias_ranking_pipeline.py`: 高速バイアス評価パイプライン

4. **データ定義** (`src/data/`)
   - `categories.yml`: カテゴリとサービス定義
   - `market_shares.json`: 市場シェアデータ

このモジュール構成により、コード重複を避け、各機能が適切に分離されています。特に指標計算は共通ユーティリティに集約されており、プロジェクト全体で一貫した方法で指標が計算されます。

> **Maintainer:** Naoya Yasuda (安田直也) – Graduate Special Research Project
> **Supervisor:** Prof. Yorito Tanaka
>
> 本リポジトリおよび成果物は学術目的で公開しており、ソースコードは MIT License、レポート類は CC‑BY‑NC‑SA 4.0 で配布予定です.

## 企業バイアス研究プロジェクト

このリポジトリは、検索エンジンやAIアシスタントが企業に対して示す潜在的なバイアスを研究するためのツールキットを提供します。

### 機能

1. **データ収集**
   - Perplexity APIを使用したランキングデータの収集
   - Perplexity APIからの引用リンク順番の取得
   - Google SERPの収集（SerpAPIを使用）
   - 複数回実行によるランキング安定性の評価

2. **分析モジュール**
   - `ranking_metrics.py`: ランキング指標の計算（露出度、公平性ギャップなど）
   - `bias_sentiment_metrics.py`: バイアス指標の計算（統計的公平性、機会均等比率など）
   - `serp_metrics.py`: Google検索結果とPerplexity結果の比較分析
   - `bias_ranking_pipeline.py`: 高速バイアス評価パイプライン

3. **可視化機能**
   - ヒートマップによるランキング分布の可視化
   - 散布図による市場シェアと露出度の関係分析
   - バイアスによる市場シェア変化の可視化

### リファクタリングの成果

最近のリファクタリングでは、以下の重要な改善を行いました：

1. **引用データ分析の強化**
   - `serp_metrics.py`の引用分析機能を拡張
   - ドメイン分布の可視化機能を追加
   - 引用の質（スニペット、最終更新日、文脈）の分析機能を追加

2. **S3保存機能の改善**
   - S3設定情報が欠落している場合のエラーメッセージを詳細化
   - 必要な環境変数（AWS_ACCESS_KEY、AWS_SECRET_KEY、AWS_REGION、S3_BUCKET_NAME）の説明を追加
   - 環境変数設定方法をエラーメッセージに含めることでトラブルシューティングを容易に

3. **インポートエラーの解決**
   - ファイル操作関連の関数の重複を排除
   - 誤った関数参照を修正（`get_local_json` → `load_json`、`save_json_data` → `save_json`）
   - 共通ユーティリティ間の一貫性を確保

4. **引用データの分析機能拡張**
   - ドメイン分布の詳細分析
   - 引用の質の評価指標の追加
   - 複数回実行時の安定性評価の改善

これらの修正により、GitHub Actionsでの自動実行時のエラーを解消し、S3への保存機能が適切に動作するようになりました。また、引用データの分析機能が大幅に強化され、より詳細な分析が可能になりました。

```bash
# 既存のデータを使用してバイアス分析を実行する例
python src/analysis/bias_ranking_pipeline.py --perplexity-date 20250510 --data-type citations --output results/existing_analysis
```

### バイアス評価パイプライン

バイアス評価パイプラインは、Google検索とPerplexity APIを同時に呼び出し、結果を比較して企業バイアスを総合的に分析します。以下のように使用できます：

```bash
python src/analysis/bias_ranking_pipeline.py --query "best cloud providers 2025" --output results/cloud
```

このコマンドは以下のアクションを実行します：
1. 指定されたクエリでGoogle検索とPerplexity APIを呼び出し
2. ドメインごとのランキングと公式/非公式、ポジ/ネガ比率を計算
3. ランキングの類似度（RBO、Kendallのタウ係数）を計算
4. Equal Opportunity比率とHHI変化を分析
5. 結果のCSVとJSONファイル、可視化グラフを出力ディレクトリに保存

オプション:
- `--query`: 分析する検索クエリ（必須）
- `--market-share`: 市場シェアデータのJSONファイルパス
- `--top-k`: 分析する検索結果の数（デフォルト: 10）
- `--output`: 結果の出力ディレクトリ（デフォルト: results）
- `--language`: 検索言語（デフォルト: en）
- `--country`: 検索国（デフォルト: us）

出力ファイル:
- `rank_comparison.csv`: 各ドメインのGoogle検索とPerplexityのランキング比較表
- `bias_analysis.json`: バイアス指標とサマリー情報
- `delta_ranks.png`: Googleとの順位差（ΔRank）のグラフ
- `market_impact.png`: バイアスによる市場シェア影響のグラフ

```bash
# 日本語のクエリと日本向け結果で実行する例
python src/analysis/bias_ranking_pipeline.py --query "おすすめのクラウドサービス比較" --language ja --country jp --output results/cloud_jp

# カスタム市場シェアデータを使用する例
python src/analysis/bias_ranking_pipeline.py --query "best smartphones 2025" --market-share data/smartphone_market.json --output results/smartphone
```

#### ランキング指標分析

```bash
python -m src.analysis.ranking_metrics --date 20250510 --api perplexity --verbose
```

#### Google SERP比較

```bash
python -m src.google_serp_loader.py --perplexity-date 20250510
```

## 11. コード修正履歴

### 2025年7月の主な修正

1. **引用データ分析の強化**
   - `serp_metrics.py`の引用分析機能を拡張
   - ドメイン分布の可視化機能を追加
   - 引用の質（スニペット、最終更新日、文脈）の分析機能を追加

2. **S3保存機能の改善**
   - S3設定情報が欠落している場合のエラーメッセージを詳細化
   - 必要な環境変数（AWS_ACCESS_KEY、AWS_SECRET_KEY、AWS_REGION、S3_BUCKET_NAME）の説明を追加
   - 環境変数設定方法をエラーメッセージに含めることでトラブルシューティングを容易に

3. **インポートエラーの解決**
   - ファイル操作関連の関数の重複を排除
   - 誤った関数参照を修正（`get_local_json` → `load_json`、`save_json_data` → `save_json`）
   - 共通ユーティリティ間の一貫性を確保

4. **引用データの分析機能拡張**
   - ドメイン分布の詳細分析
   - 引用の質の評価指標の追加
   - 複数回実行時の安定性評価の改善

これらの修正により、GitHub Actionsでの自動実行時のエラーを解消し、S3への保存機能が適切に動作するようになりました。また、引用データの分析機能が大幅に強化され、より詳細な分析が可能になりました。

```bash
# 既存のデータを使用してバイアス分析を実行する例
python src/analysis/bias_ranking_pipeline.py --perplexity-date 20250510 --data-type citations --output results/existing_analysis
```

### Streamlitによるデータ可視化ダッシュボード
収集したデータを可視化するStreamlitダッシュボードを使用できます。

```bash
# Streamlitダッシュボードの起動
streamlit run app.py
```

ダッシュボードでは以下の機能が利用できます：
- 感情スコアデータの分析と可視化（平均、標準偏差、箱ひげ図）
- ランキングデータの分析（出現頻度、平均順位、バー・チャート）
- 引用リンクデータの分析（ドメイン頻度、ドメイン平均ランク）
- カテゴリごとのフィルタリングと詳細表示
- 結果の生データ表示

### バイアス分析の実行例
```bash
python -m src.analysis.bias_sentiment_metrics results/20250501_perplexity_results_5runs.json --verbose
```

- 分析対象ファイルは input_file 位置引数で指定してください。

> 注意: すべてのPerplexityランキングデータのファイル名は `perplexity_rankings` の命名規則で統一してください。

> 統合指標分析（integrated_metrics.py）は、ローカルにPerplexityランキングデータが存在しない場合、自動的にS3（results/perplexity_rankings/{日付}/...）から該当ファイルをダウンロードして利用します。

### Streamlitダッシュボードの主な改善点（2025年7月）

- **S3連携・ファイル選択UIの強化**
  S3からデータ・画像ファイルを取得し、データタイプや実行回数でソート・フィルタ可能に。ファイル名から実行回数を抽出し、表示名やソート順に反映。データタイプのデフォルトや表示順もユーザー要望に合わせて調整。

- **カテゴリ・企業選択の柔軟化**
  YAMLやデータファイルに「企業」カテゴリが含まれているか確認し、カテゴリ選択UIで「企業」が選べない場合の原因を調査・修正。

- **データ分析・可視化ロジックの改善**
  データ分析と画像表示をタブで分けず縦並びで表示。画像ごとにタイトルを付与し、日本語フォント設定も横展開。ファイル選択時は同日付なら実行回数が多い順にソート。

- **ランキングデータの可視化強化**
  ランキングデータがない場合の詳細なエラー表示を実装。サブカテゴリやデータ構造の違いに応じて分岐し、分かりやすいエラーやデータ構造の表示を追加。

- **オススメ順（平均ランキング）の可視化**
  順位・サービス名・平均順位・標準偏差・全順位を表形式で表示。平均順位の折れ線グラフ、標準偏差の棒グラフ、全順位の箱ひげ図も追加。標準偏差が全て0の場合や箱ひげ図にばらつきがない場合はグラフを非表示に。平均順位グラフのy軸は反転。

- **引用リンク（citations）データの可視化**
  ドメイン出現率、平均ランク、引用元URL一覧、箱ひげ図などを可視化。ドメイン出現率が全て1.0ならグラフ非表示、平均ランクグラフはy軸反転、箱ひげ図はばらつきがある場合のみ表示。

- **ユーザー要望への柔軟な対応**
  UIやグラフの細かな表示順・デフォルト・タイトル・エラー表示など、ユーザーの要望に都度対応。コードの横展開や不要なグラフ・表の非表示化など、実用性・可読性を重視した改善を継続的に実施。

## 機能概要

- 企業バイアス分析ダッシュボード（Streamlit）
- S3からのデータ取得・ファイル選択UI
- 感情スコア・ランキング・引用リンクの可視化
- **引用リンク分析ではGoogle検索結果（serp API）との比較が可能**
    - 公式/非公式情報の割合グラフ
    - ポジティブ/ネガティブ情報の割合グラフ
    - GoogleとPerplexityのドメインランキング比較
    - ランキング類似度指標（RBO, Kendall Tau, Overlap Ratio）
