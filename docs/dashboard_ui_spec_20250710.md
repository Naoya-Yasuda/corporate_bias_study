---
title: "企業バイアス分析ダッシュボード UI仕様書"
type: "specification"
date: "{{datetime.now().strftime('%Y-%m-%d')}}"
---

# 企業バイアス分析ダッシュボード UI仕様書

## 1. サイドバー仕様
- データ取得元（local/S3/auto）を選択可能
  - auto時はlocal/S3両方の候補をリスト表示し、ユーザーが選択できるUI
- カテゴリ選択は具体的なカテゴリのみ表示
- 「詳細可視化タイプを選択」UIで「おすすめランキング分析結果」や各種グラフ・表形式を選択可能

## 2. メイン画面・可視化仕様
- HybridDataLoaderの`get_integrated_dashboard_data()`で
  - bias_analysis_results.json（分析結果）
  - corporate_bias_dataset.json（統合生データ）
  を両方読み込み、統合データを返却
- 統合データをもとに各種可視化・表形式表示・詳細展開を行う
- 感情スコア分析では以下のグラフ・表形式を選択・表示できる：
  - BI値棒グラフ（Normalized Bias Indexの棒グラフ）
  - 重篤度レーダーチャート
  - p値ヒートマップ
  - 効果量 vs p値散布図
  - 表形式表示（perplexity_sentiment属性を表示。各エンティティのperplexity_sentiment値を表形式で一覧表示）
  - 表形式表示の仕様：
    - corporate_bias_dataset.jsonのperplexity_sentiment属性は「カテゴリ＞サブカテゴリ＞エンティティ＞属性」の多層構造
    - 表形式表示は常にダッシュボード上部に表示し、カテゴリ・サブカテゴリ・エンティティ選択に応じて該当データをDataFrameで表示
    - 感情スコア表のラベルは「感情スコア表｜カテゴリ: {カテゴリ}｜サブカテゴリ: {サブカテゴリ}」とし、表からカテゴリ・サブカテゴリカラムは除外
    - 表のカラムは以下の通り：
        - エンティティ
        - 感情スコア一覧（unmasked_valuesの整数値をカンマ区切りで全件表示）
        - 感情スコア平均（unmasked_valuesの整数値の平均）
        - 感情スコア標準偏差（unmasked_valuesの整数値の標準偏差）
        - 感情スコア（マスクあり）（masked_valuesの1件目）
        - 感情スコアバイアス（感情スコア差分）（感情スコア平均 - 感情スコア（マスクあり））
    - ラベルはすべて日本語で統一
    - 表の下に該当カテゴリ・サブカテゴリのperplexity_sentimentサブツリーをst.expanderで折りたたみJSON表示（デフォルト折りたたみ）
    - グラフ種別（BI値棒グラフ、重篤度レーダーチャート、p値ヒートマップ、効果量 vs p値散布図）はダッシュボード本体のタブ（st.tabs）で切り替え可能
    - サイドバーでのグラフ種別選択UIは廃止
    - 表形式表示では、カテゴリ・サブカテゴリ・エンティティごとに主要属性（例：masked_answer, masked_values, masked_reasons, masked_url, entities配下のunmasked_answer等）を1行ずつ持つフラットなテーブルに変換して表示
    - 主要カラム例：カテゴリ / サブカテゴリ / エンティティ / masked_answer / masked_values / masked_reasons / masked_url / unmasked_answer など
    - 必要に応じて他の属性も追加可能
    - サイドバー表示時はダッシュボード本体の最大横幅をサイドバー幅（約336px）分引いた幅にCSSで自動調整し、右側が見切れないようにする
    - サイドバーを閉じた場合はダッシュボード本体の最大横幅が自動で100vw-32pxまで広がる（CSS+JSで切り替え）
- S3/ローカル両方のデータ統合状況を都度HybridDataLoader経由で取得・検証

## 3. 操作フロー
1. サイドバーでデータ取得元を選択（auto時は候補リストから選択）
2. カテゴリを選択
3. 詳細可視化タイプを選択
4. 統合データ取得・可視化・表形式表示

## 4. 拡張・運用方針
- 画面仕様書は今後の拡張・運用時も随時更新
- S3/ローカル両方のデータ統合チェックを推奨
- README等には改訂履歴不要、画面仕様書に集約

## 5. 用語・データ仕様
- 感情スコア分析（perplexity_sentiment属性の表形式表示を含む）
- 表形式表示はperplexity_sentiment由来データのみ
- データ統合・可視化はHybridDataLoader経由で取得・検証

## 6. 備考
- bias_analysis_results.jsonのexecution_count等が0の場合は可視化指標が出ないことがある（データ収集・分析実行回数不足や前処理失敗が原因）
- ファイルが存在し構造的に統合されているだけでなく、実際にHybridDataLoaderで統合データを取得し、可視化・表形式表示・詳細展開に利用していることを確認すること