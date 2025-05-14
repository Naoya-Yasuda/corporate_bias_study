# AI検索サービスにおける企業優遇バイアス

*―市場競争への潜在的リスクを定量評価するリサーチ & システム開発―*

---

## 1. プロジェクト概要

AI 検索サービス（ChatGPT、Perplexity、Copilot など）が提示する情報に **企業優遇バイアス** が存在しうるのかを検証し、
その **市場競争への影響** を **定量的指標** で可視化・評価することを目的とした学術・実装プロジェクトです。
検索エンジンではなく *生成 AI ベースの検索* にフォーカスする点が新規性となります。

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
│   └─ analysis/             # 分析・可視化ツール（今後追加予定）
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

### なぜ複数回の実行が必要か

生成AIのランダム性により、単一の実行では安定したバイアス指標を得ることができません。5回以上の実行を行うことで：

1. 標本数を増やし、統計的検定の信頼性を向上
2. 平均値とばらつきを計算し、バイアスの安定性を評価
3. 効果量（Cliff's Delta）の正確な計算が可能
4. ブートストラップ信頼区間の信頼性向上

複数回実行データは自動的にバイアス分析モジュール（`src/analysis/bias_metrics.py`）で処理され、CSVファイルとして出力されます。分析結果はデータ収集時に自動的に計算・保存されます。

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
