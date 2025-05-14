# AI検索サービスにおける企業優遇バイアス

*―市場競争への潜在的リスクを定量評価するリサーチ & システム開発―*

---

## 1. プロジェクト概要

AI 検索サービス（ChatGPT、Perplexity、Copilot など）が提示する情報に **企業優遇バイアス** が存在しうるのかを検証し、
その **市場競争への影響** を **定量的指標** で可視化・評価することを目的とした学術・実装プロジェクトです。
検索エンジンではなく *生成 AI ベースの検索* にフォーカスする点が新規性となります。

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
├─ src/
│   ├─ api_clients/          # Perplexity, OpenAI などラッパ
│   ├─ prompts/              # json / yaml 形式テンプレート
│   ├─ analysis/             # 指標計算 & 可視化スクリプト
│   └─ reports/              # 自動生成される CSV / Markdown
├─ data/                     # 収集データ (gitignore 済)
├─ .github/
│   └─ workflows/
│       └─ bias_analysis.yml # GitHub Actions で定期実行
└─ README.md                 # ← 本ファイル
```

---

## 6. セットアップ

```bash
# 1. Poetry で依存ライブラリをインストール
poetry install

# 2. API キーをローカルで動かす場合は .env に設定
echo 'PPLX_API_KEY=xxxxxxxx' >> .env
```

---

## 7. GitHub Actions での定期実行

`.github/workflows/bias_analysis.yml`

```yaml
name: Bias Analysis (Daily)

on:
  schedule:
    - cron:  '0 21 * * *'   # 毎日 06:00 JST (=21:00 UTC) に実行
  workflow_dispatch:

jobs:
  run-analysis:
    runs-on: ubuntu-latest
    env:
      PPLX_API_KEY: ${{ secrets.PPLX_API_KEY }}
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'poetry'
      - name: Install deps
        run: |
          pip install poetry
          poetry install --no-interaction --no-root
      - name: Run daily bias analysis
        run: |
          poetry run python src/analysis/run_all.py
      - name: Upload reports artefact
        uses: actions/upload-artifact@v4
        with:
          name: bias_reports
          path: src/reports/
```

#### 7.1 秘密情報の設定

| Secret Key       | 説明                         |
| ---------------- | ---------------------------- |
| `PPLX_API_KEY`   | Perplexity API キー          |
| `OPENAI_API_KEY` | OpenAI API キー (オプション) |

GitHub リポジトリの **Settings → Secrets and variables → Actions** で追加してください。

---

## 8. 実行結果

* `src/reports/YYYYMMDD_bias_report.md` : 定量評価まとめ
* `src/reports/YYYYMMDD_bias_metrics.csv` : 指標値 (CSV)
* 成果物は Action 成功時に artefact としてダウンロード可能です。

---

## 9. ロードマップ

* ✅ Python スクリプト化 & Poetry / Actions テンプレート
* ✅ 感情評価バイアス検証スクリプト (`sentiment_bias.py`)
* ☐ Google 検索スクレイピング & 比較モジュール
* ☐ ダッシュボード統合 (Streamlit 予定)
* ☐ 論文化 & 研究会発表

---

## 10. 引用・参考文献

主要な先行研究・ガイドラインは `/docs/references.bib` を参照。

---

> **Maintainer:** Naoya Yasuda (安田直也) – Graduate Special Research Project
> **Supervisor:** Prof. Yorito Tanaka
>
> 本リポジトリおよび成果物は学術目的で公開しており、ソースコードは MIT License、レポート類は CC‑BY‑NC‑SA 4.0 で配布予定です.
