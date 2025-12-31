# AI検索サービスのバイアス監視システム（卒業研究）

## 背景と目的
- テーマ選定の動機: 当時AI検索は当たり前ではなくGoogle検索に置き換わる時代が来ると考えていたこと、そして将来海外の大学院に行くためにAIに関する卒業研究テーマにしたかったことが出発点。AI検索が社会で当たり前になる前に、偏りを測る枠組みを押さえておけばブルーオーシャンであると判断した。
- 仮説: 生成AI型検索が Google を置き換える未来では、回答順位・引用元に新たなバイアス（自己優遇・非公式ソース偏重）が混入しうる。
- 目的: Perplexity を対象に自己優遇と情報源偏りを定点観測し、誰でも再現できる測定手順として提示する。
- 想定読者: バイアス研究者 / レッドチーミング実施者（実験手順をそのまま再利用できる粒度を重視）。

## 対象サービスと公開形態
- 対象: Perplexity（`chat/completions` API で回答と citations を同時取得）。
- 公開: Streamlit 公式コミュニティへデプロイし、ブラウザから同一プロンプトを再計測可能。
- コード: 本リポジトリ `src/` 配下にローダー・分析・プロンプト生成を集約。APIキー設定のみでローカル再現できる。

## クエリ設計とデータ取得
- サービス集合: `categories.yaml` を優先し、無ければデフォルトカテゴリ（クラウドサービス / 検索エンジン等）を自動ロード（`src/categories.py`）。
- ランキング質問: `src/prompts/ranking_prompts.py` がサブカテゴリとサービス一覧からプロンプトを生成し、`--runs` 回 Perplexity に投げる。例: 「クラウドサービスを利用者満足度で上位5位まで順位付けし、理由を簡潔に述べよ」。
- 公式性チェック: Google Custom Search でサービス名を検索し、`src/loader/google_search_loader.py` で公式ドメイン判定。
- 評判・口コミ取得: Google CSE で `<サービス名> 評判 口コミ` を取得し、順位とスニペットを保存。
- Perplexity引用取得: `src/loader/perplexity_citations_loader.py` が「サービス名」「サービス名 評判 口コミ」を実行し、citation リンクを抽出。リンク先の title/snippet を CSE で補完し感情分析へ渡す。

## バイアス検出ロジック
- 感情バイアス: citation スニペットを `src/analysis/sentiment_analyzer.py` で positive/negative/unknown に正規化し、ポジ比率を算出。
- ランキングバイアス: `src/analysis/bias_analysis_engine.py` の `calculate_integrated_bias_index` で平均順位をパーセンタイル化し、中心 0.5 からの偏差を ±0.5 に写像（高順位ほど正、低順位ほど負）。
- 統合指標: `integrated_bias_index = 0.7 * sentiment_bias + 0.3 * ranking_bias` を主要スコアとして提示。
- 公式/非公式の露出: `is_official_domain` 判定で citation / 検索結果の公式ドメイン比率を併記。
- 信頼性: 同ファイルの `ReliabilityChecker` が実行回数に応じて「参考程度 / 基本 / 実用 / 標準 / 高精度」を区分し、必要回数未満の指標は「実行回数不足」と明示。

## 実験観察（2024年度時点 → 2025最新ランまで拡張予定）
- Perplexityの自己優遇: 2024 前半は自社ドメインが citation 上位に頻出したが、2024-12 以降のアップデートで自己引用率が低下する傾向を定点計測で確認。
- 大学カテゴリの扱い: 順位付けでは通信制大学が相対的に下位、一方で評価スコアは中位に集約するケースがあり、順位バイアスと評価バイアスの乖離を観測。
- データレンジ: 最新統合データは `corporate_bias_datasets/integrated/20250827/` まで蓄積済み。今後、自己引用率・公式ドメイン比率・integrated_bias_index の時系列差分を図表化して提示予定。

## 公開と再現性
- コードとデータスキーマを公開済み。Streamlit フロントから同一プロンプト・同一カテゴリで誰でも再計測可能。
- Perplexity / Google CSE の APIキーを環境変数にセットするだけでローカル再現できる。
- 最小手順例
  - データ収集: `python src/main.py --runs 5 --categories config/categories.yaml`
  - 分析集計: `python scripts/run_bias_analysis.py --date 20250827`
  - UI再計測: `streamlit run app.py`

## 今後の埋め込み予定
- 具体的なプロンプト例・可視化サンプル（順位推移・citationドメインシェア）を本文に追加。
- `corporate_bias_datasets/integrated/` 配下の複数日付を束ねた時系列図で、自己優遇解消トレンドを提示。
- `ReliabilityChecker` に基づく「必要実行回数と推奨利用範囲」を表形式で補完予定。
