# AI検索サービスにおける企業優遇バイアス

*―市場競争への潜在的リスクを定量評価するリサーチ & システム開発―*

---

## 1. プロジェクト概要

AI 検索サービス（ChatGPT、Perplexity、Copilot など）が提示する情報に **企業優遇バイアス** が存在しうるのかを検証し、
その **市場競争への影響** を **定量的指標** で可視化・評価することを目的とした学術・実装プロジェクトです。検索エンジンではなく *生成 AI ベースの検索* にフォーカスする点が新規性となります。

## 概要
このプロジェクトは、AIモデルが企業名に対してどのようなバイアス（偏り）を持っているかを分析します。「最も優れた○○は△△である」というような文に対する感情評価のスコアを測定し、企業ごとの比較を行います。

## 機能
- Perplexity APIを使用した企業バイアス評価
- OpenAI APIを使用した企業バイアス評価
- マスクあり・マスクなしの評価値比較
- 複数回実行による平均値と標準偏差の計算
- ローカルとS3への結果保存
- モジュール化されたカテゴリ定義と再利用可能なプロンプトテンプレート
- サービスのランキング（おすすめ順）抽出機能

## セットアップ
1. リポジトリをクローン
2. 必要なパッケージをインストール
   ```
   pip install -r requirements.txt
   ```

   または以下のコマンドでconda環境を作成
   ```
   conda env create -f environment.yml
   conda activate cu_study
   ```

3. 必要な環境変数を設定した`.env`ファイルを作成
   ```
   PERPLEXITY_API_KEY=your_perplexity_api_key
   OPENAI_API_KEY=your_openai_api_key
   SERP_API_KEY=your_serp_api_key
   AWS_ACCESS_KEY=your_aws_access_key
   AWS_SECRET_KEY=your_aws_secret_key
   AWS_REGION=your_aws_region
   S3_BUCKET_NAME=your_s3_bucket_name
   ```

## 使用方法

### 単一実行
```bash
# Perplexity - バイアス評価
python -m src.perplexity_bias_loader

# Perplexity - ランキング抽出
python -m src.perplexity_ranking_loader

# OpenAI - バイアス評価
python -m src.openai_bias_loader
```

### 複数回実行（平均値を計算）
```bash
# Perplexity - バイアス評価（5回実行）+ 自動分析
python -m src.perplexity_bias_loader --multiple --runs 5

# Perplexity - ランキング抽出（5回実行）
python -m src.perplexity_ranking_loader --multiple --runs 5

# OpenAI - バイアス評価（5回実行）+ 自動分析
python -m src.openai_bias_loader --multiple --runs 5

# 分析なしで実行する場合
python -m src.perplexity_bias_loader --multiple --runs 5 --no-analysis
```

#### ストレージ設定のカスタマイズ
`.env`ファイルの`STORAGE_MODE`で保存方法を指定できます。

```
# ローカルのみに保存
STORAGE_MODE=local_only

# S3のみに保存
STORAGE_MODE=s3_only

# 両方に保存（デフォルト）
STORAGE_MODE=both
```

保存ディレクトリやS3プレフィックスのカスタマイズ：

```
# ローカル保存先のカスタマイズ
LOCAL_RESULTS_DIR=custom_results

# S3プレフィックスのカスタマイズ
S3_RESULTS_PREFIX=project/results
```

#### 新しいストレージAPIの使用例
```python
# JSONデータの保存
from src.utils import save_json_data
results = {"data": [...], "metadata": {...}}
save_json_data(results, "results/analysis.json")

# テキストデータの保存
from src.utils import save_text_data
text = "分析レポートの内容..."
save_text_data(text, "results/report.txt")

# 図の保存
from src.utils import save_figure
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
save_figure(fig, "results/graph.png")

# 明示的なS3パスの指定
save_json_data(results, "results/analysis.json", "custom/path/analysis.json")
```

#### 各モジュールのヘルプ
各モジュールのコマンドラインオプションと使用方法を確認するには、`--help`オプションを使用します：

```bash
# バイアス評価モジュールのヘルプ
python -m src.perplexity_bias_loader --help
python -m src.openai_bias_loader --help

# ランキング抽出モジュールのヘルプ
python -m src.perplexity_ranking_loader --help

# Google SERP抽出モジュールのヘルプ
python -m src.google_serp_loader --help

# 分析モジュールのヘルプ
python -m src.analysis.ranking_metrics --help
python -m src.analysis.bias_metrics --help
python -m src.analysis.serp_metrics --help
python -m src.analysis.bias_ranking_pipeline --help
```

ヘルプでは各モジュールの以下の情報が表示されます：
- 機能の概要説明
- 使用可能なコマンドラインオプション
- デフォルト値
- 使用例

### プロンプトテンプレートのテスト
```bash
# ランキングプロンプトの生成のみ
python -m src.prompts.ranking_prompts "クラウドサービス" "AWS,Azure,Google Cloud,IBM Cloud"

# テキストからのランキング抽出
python -m src.prompts.ranking_prompts "検索エンジン" "Google,Bing,Yahoo! Japan,Baidu" --response "1. Google 2. Bing 3. Yahoo! Japan 4. Baidu"

# ファイルからのランキング抽出
python -m src.prompts.ranking_prompts "検索エンジン" "Google,Bing,Yahoo! Japan,Baidu" --file response.txt

# Perplexity APIを使用した複数回ランキング取得（3回実行）
python -m src.prompts.ranking_prompts "クラウドサービス" "AWS,Azure,Google Cloud,IBM Cloud" --api --runs 3

# 結果をJSONファイルに保存
python -m src.prompts.ranking_prompts "クラウドサービス" "AWS,Azure,Google Cloud,IBM Cloud" --api --output results/cloud_ranks.json
```

### カテゴリ/サービスのカスタマイズ
カテゴリとサービスは `src/data/categories.yml` で一元管理されています。このYAMLファイルを編集することで、評価対象のカテゴリとサービスをカスタマイズできます。

```yaml
# カテゴリとサービスの例
categories:
  デジタルサービス:
    クラウドサービス:
      - AWS
      - Azure
      - Google Cloud
      - IBM Cloud
    検索エンジン:
      - Google
      - Bing
      - Yahoo! Japan
      - Baidu
    # コメントアウトされたカテゴリは評価されません
    # ストリーミングサービス:
    #   - Netflix
    #   - Amazon Prime Video
```

YAMLファイルを更新した後、変更を反映するために新しい実行を開始するだけで済みます。

## 自動化

### GitHub Actionsでの定期実行
このプロジェクトは、GitHub Actionsを使用して毎日自動的にPerplexityとOpenAIのバイアス分析を実行します。結果はS3バケットに保存され、GitHubのアーティファクトとしても7日間保存されます。

実行時間: 毎日 06:00 JST (21:00 UTC)

## 分析結果の保存先
- ローカル: `results/YYYYMMDD_*_results.json`
- S3: `s3://your-bucket/results/{openai|perplexity}/YYYYMMDD/*_results.json`

## ライセンス
MITライセンス

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
│   ├─ perplexity_bias_loader.py # Perplexity API実行ファイル
│   ├─ openai_bias_loader.py # OpenAI API実行ファイル
│   ├─ data/                 # データファイル
│   │   ├─ __init__.py
│   │   └─ categories.yml    # カテゴリとサービス定義（YAML）
│   ├─ prompts/              # プロンプトテンプレート
│   │   ├─ __init__.py
│   │   ├─ perplexity_prompts.py # Perplexity用プロンプト
│   │   └─ openai_prompts.py # OpenAI用プロンプト（未実装）
│   ├─ utils/                # 共通ユーティリティ
│   │   ├─ __init__.py       # 共通ユーティリティの初期化ファイル
│   │   ├─ s3_utils.py       # S3操作のユーティリティ
│   │   ├─ file_utils.py     # ファイル操作のユーティリティ
│   │   ├─ text_utils.py     # テキスト処理のユーティリティ
│   │   ├─ rank_utils.py     # ランキング処理のユーティリティ
│   │   └─ plot_utils.py     # 可視化のユーティリティ
│   └─ analysis/             # 分析・可視化ツール
├─ results/                  # 結果保存先（自動生成）
├─ .env                      # 環境変数（gitignore対象）
├─ .github/
│   └─ workflows/            # GitHub Actions定義ファイル
├─ requirements.txt          # 依存パッケージリスト
├─ environment.yml           # Conda環境定義ファイル
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

3. **API実行モジュール** (`src/perplexity_bias_loader.py`, `src/openai_bias_loader.py`)
   - API呼び出し処理
   - 複数回実行と統計処理
   - 結果の保存機能

4. **分析モジュール** (`src/analysis/`)
   - `ranking_metrics.py`: ランキング指標の計算（露出度、公平性ギャップ等）
   - `bias_metrics.py`: バイアス指標の計算（統計的公平性、機会均等比率等）
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
* `results/YYYYMMDD_perplexity_results_5runs.json` : Perplexity APIのバイアス評価結果（複数実行時）
* `results/YYYYMMDD_perplexity_rankings.json` : Perplexity APIのランキング抽出結果（単一実行）
* `results/YYYYMMDD_perplexity_rankings_5runs.json` : Perplexity APIのランキング抽出結果（複数実行時）
* `results/YYYYMMDD_openai_results.json` : OpenAI APIの結果
* `results/analysis/perplexity/YYYYMMDD/YYYYMMDD_*_bias_metrics.csv` : Perplexity APIのバイアス指標分析結果
* `results/analysis/openai/YYYYMMDD/YYYYMMDD_*_bias_metrics.csv` : OpenAI APIのバイアス指標分析結果
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

複数回実行データは自動的にバイアス分析モジュール（`src/analysis/bias_metrics.py`）で処理され、CSVファイルとして出力されます。分析結果はデータ収集時に自動的に計算・保存されます。

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
python -m src.analysis.ranking_metrics --date 20240501

# OpenAIのランキングデータを分析
python -m src.analysis.ranking_metrics --api openai

# 結果を特定のディレクトリに保存
python -m src.analysis.ranking_metrics --output results/my_analysis

# ローカルのJSONファイルを直接分析
python -m src.analysis.ranking_metrics --json-path results/20240501_perplexity_rankings_5runs.json
```

バイアス分析と一緒に実行する場合：

```bash
# バイアス分析とランキング分析を同時実行
python -m src.analysis.bias_metrics results/20240501_perplexity_results_5runs.json --rankings

# 別日のランキングを指定して分析
python -m src.analysis.bias_metrics results/20240501_perplexity_results_5runs.json --rankings --rankings-date 20240502
```

分析結果は以下のファイルに保存されます：
- 各カテゴリの詳細指標CSV: `results/ranking_analysis/YYYYMMDD/カテゴリ名_rank_metrics.csv`
- ランキング分布ヒートマップ: `results/ranking_analysis/YYYYMMDD/カテゴリ名_rank_heatmap.png`
- 市場シェアと露出度の散布図: `results/ranking_analysis/YYYYMMDD/カテゴリ名_exposure_market.png`
- 全カテゴリの指標サマリー: `results/ranking_analysis/YYYYMMDD/YYYYMMDD_perplexity_rank_summary.csv`

## 7.7 Google検索比較指標

AIが生成するランキングとGoogle検索結果を比較し、両者の違いを分析するための指標群を実装しています。

### 1. 順位比較指標

#### Rank-Biased Overlap (RBO)
Google検索結果とAI検索結果の上位k位の一致度を0〜1のスコアで表します。1に近いほど結果が類似していることを示します。重み付けにより、上位の順位ほど重要視されます。

#### Kendallのタウ係数
2つのランキングの順序の一致度を測る指標。-1〜1の範囲を取り、1は完全に同じ順序、-1は完全に逆順、0はランダムな関係を示します。

#### ΔRank
`Google順位 - Perplexity順位`で計算される各企業の順位差。負の値は「AIによる押し上げ効果」（Googleより上位表示）を、正の値は「AIによる押し下げ効果」（Googleより下位表示）を示します。

### 2. コンテンツ比較指標

#### 公式/非公式比率
検索結果に含まれる公式サイトの比率を比較し、AIとGoogleがどのように情報源を選択するかの違いを可視化します。

#### ポジティブ/ネガティブ比率
検索結果に含まれるネガティブなコンテンツの比率を比較し、AIとGoogleのセンチメントバイアスの違いを評価します。

### 3. 経済的影響評価

#### 調整後市場シェア
ΔRankに基づいて、各企業の市場シェアがAIによってどのように影響を受ける可能性があるかをシミュレーションします。

#### HHI (Herfindahl-Hirschman Index) 変化
AIバイアスによる市場集中度の変化を評価します。HHIの上昇は市場集中（独占・寡占）の強化を、減少は競争の促進を示唆します。

### 4. 使用方法

```bash
# Google SERP APIを使用して検索結果を取得し、Perplexityと比較
python -m src.google_serp_loader

# 特定の日付のPerplexityデータと比較
python -m src.google_serp_loader --perplexity-date 20240501

# 一部のカテゴリのみ処理
python -m src.google_serp_loader --max 3

# 取得のみ（分析なし）
python -m src.google_serp_loader --no-analysis

# 既存のJSONファイルを使って直接分析
python -m src.analysis.serp_metrics results/20240501_google_serp_results.json results/20240501_perplexity_rankings_5runs.json
```

分析結果は以下のファイルに保存されます：
- Google検索結果: `results/YYYYMMDD_google_serp_results.json`
- 比較結果: `results/YYYYMMDD_google_serp_comparison.json`
- 分析結果: `results/YYYYMMDD_google_serp_analysis.json`
- ΔRankグラフ: `results/analysis/カテゴリ名_delta_ranks.png`
- 市場影響グラフ: `results/analysis/カテゴリ名_market_impact.png`

---

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

> **Maintainer:** Naoya Yasuda (安田直也) – Graduate Special Research Project
> **Supervisor:** Prof. Yorito Tanaka
>
> 本リポジトリおよび成果物は学術目的で公開しており、ソースコードは MIT License、レポート類は CC‑BY‑NC‑SA 4.0 で配布予定です.

## 企業バイアス研究プロジェクト

このリポジトリは、検索エンジンやAIアシスタントが企業に対して示す潜在的なバイアスを研究するためのツールキットを提供します。

### 機能

1. **データ収集**
   - Perplexity APIを使用したランキングデータの収集
   - Google SERPの収集（SerpAPIを使用）
   - 複数回実行によるランキング安定性の評価

2. **分析モジュール**
   - `ranking_metrics.py`: ランキング指標の計算（露出度、公平性ギャップなど）
   - `bias_metrics.py`: バイアス指標の計算（統計的公平性、機会均等比率など）
   - `serp_metrics.py`: Google検索結果とPerplexity結果の比較分析
   - `bias_ranking_pipeline.py`: 高速バイアス評価パイプライン

3. **可視化機能**
   - ヒートマップによるランキング分布の可視化
   - 散布図による市場シェアと露出度の関係分析
   - バイアスによる市場シェア変化の可視化

### リファクタリングの成果

リファクタリングにより以下の改善を行いました：

1. **共通ユーティリティモジュールの整備**
   - `src/utils/s3_utils.py`: S3操作の共通関数
   - `src/utils/file_utils.py`: ファイル操作の共通関数
   - `src/utils/text_utils.py`: テキスト処理の共通関数
   - `src/utils/rank_utils.py`: ランキング処理の共通関数
   - `src/utils/plot_utils.py`: データ可視化の共通関数

2. **コードの保守性向上**
   - 重複コードの削除によるバグリスクの低減
   - 一貫した関数名と引数による可読性の向上
   - モジュール間の依存関係の明確化

3. **拡張性の改善**
   - 新しいデータソースの追加が容易に
   - 分析手法の追加・変更がしやすく
   - テスト可能性の向上

4. **データ保存の一元化**
   - 統一的なストレージAPIの実装
   - ローカル保存とS3保存の設定による切り替え
   - 一貫したパス構造の確保

### 今後の改善点

1. **データ保存機能の充実**
   - エラーリカバリ機能の強化
   - キャッシュメカニズムの追加
   - ストレージ抽象化のさらなる改善

2. **コードドキュメントの充実**
   - 各モジュールのdocstringの追加・改善
   - 型ヒントの追加によるコード品質の向上

3. **エラーハンドリングの強化**
   - API呼び出しの例外処理の統一
   - リトライ機能の追加

4. **テストコードの整備**
   - ユニットテストの追加
   - 自動テスト環境の構築

5. **ドキュメント生成**
   - Sphinxを使用した自動ドキュメント生成
   - READMEとAPIドキュメントの連携
   - コードの使用例を含むチュートリアルの作成

### バイアス指標

#### ランキング評価指標
- **Statistical Parity Gap (SP Gap)**: 最大露出確率と最小露出確率の差。0に近いほど公平。
- **Equal Opportunity Ratio (EO比率)**: 市場シェアと上位出現確率の比率。1に近いほど公平。
- **Kendallのタウ係数**: ランキングと市場シェアの順位相関。1に近いほど市場シェアに一致。
- **RBO (Rank-Biased Overlap)**: 異なるランキング間の類似度。1に近いほど類似。

#### 安定性指標
- **ランキング安定性スコア**: 複数回の検索結果のランキング一貫性（-1〜1）。
  - 0.8以上: 非常に安定
  - 0.6-0.8: 安定
  - 0.4-0.6: やや安定
  - 0.2-0.4: やや不安定
  - 0.0-0.2: 不安定
  - 0.0未満: 非常に不安定（逆相関）

#### Google検索比較指標
- **ΔRank**: Googleと他のプラットフォームとの順位差。負の値はGoogleで高く評価。
- **公式/非公式比率**: 検索結果における公式ドメインの比率の差。
- **ポジ/ネガ比率**: 検索結果における肯定的/否定的コンテンツの比率の差。
- **HHI変化率**: バイアスによる市場集中度（HHI）の変化率。

### 使用方法

#### バイアス評価パイプライン

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
python src/analysis/ranking_metrics.py --date 20240510 --api perplexity
```

#### Google SERP比較

```bash
python src/google_serp_loader.py --perplexity-date 20240510
```
