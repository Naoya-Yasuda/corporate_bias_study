---
title: 企業バイアス分析ダッシュボード「時系列分析」画面仕様書
date: {dynamic_date}
type: "specification"
alwaysApply: true
globs: ["**/app.py", "**/plot_utils.py"]
---

# 企業バイアス分析ダッシュボード「時系列分析」画面仕様書

## 1. 目的
- 複数日付の分析データを集約し、主要指標の時系列推移・安定性・異常値を可視化することで、バイアス傾向の変化や一貫性を把握する。

## 2. UI設計
- サイドバーで「時系列分析」を選択すると、複数日付選択UI（multiselect）が表示される。
- カテゴリ・サブカテゴリ・エンティティも選択可能。
- メイン画面では、選択した日付ごとに主要指標の推移を折れ線グラフ等で可視化。
- 主要指標サマリー表を日付ごとに横並びで表示し、異常値・大きな変動は色やアイコンで強調。
- 詳細解釈や推奨コメントはexpanderやtooltipで補足。

## 3. 可視化内容
- BI値（バイアス指標）の時系列推移線グラフ
- 感情スコア平均・分布の時系列推移
- ランキング類似度（RBO, Kendall Tau, Overlap Ratio）の時系列推移
- 公式/非公式比率の時系列推移
- ポジティブ/ネガティブ比率の時系列推移
- 安定性スコア・標準偏差の時系列推移
- 異常値・大きな変動の自動強調

## 4. データ取得・処理
- HybridDataLoaderで複数日付のbias_analysis_results.jsonを一括取得
- 日付ごとに主要指標を抽出し、時系列データフレームに整形
- 欠損値・不整合はエラーハンドリング

## 5. 技術仕様
- フロントエンド: Streamlit
- 可視化ライブラリ: Matplotlib, Plotly
- データ形式: JSON（bias_analysis_results.json）
- 画像保存は行わず、全て動的生成

## 6. 時系列分析タブ構成

### 6.1 実装済みタブ
1. **BI値時系列推移** - `normalized_bias_index`の時系列推移
2. **感情スコア時系列推移** - `raw_delta`の時系列推移
3. **ランキング時系列推移** - `avg_rank`の時系列推移
4. **ランキング類似度時系列推移** - RBO、Kendall Tau、Overlap Ratioの時系列推移
5. **公式/非公式比率時系列推移** - Google公式比率、Citations公式比率、バイアス差分の時系列推移

### 6.2 追加実装予定タブ
6. **ポジティブ/ネガティブ比率時系列推移** - Googleポジティブ比率、Citationsポジティブ比率、ポジティブバイアス差分の時系列推移

### 6.3 将来実装予定タブ
7. **安定性スコア時系列推移** - 安定性スコア、標準偏差の時系列推移
8. **異常値・変動強調** - 大きな変動の自動検出・強調表示

## 7. データソース詳細

### 7.1 ランキング類似度データ
- **パス**: `citations_google_comparison[category][subcategory]["ranking_similarity"]`
- **指標**: `rbo_score`, `kendall_tau`, `overlap_ratio`
- **解釈**: サブカテゴリレベルでのGoogle検索とPerplexity検索の結果類似度

### 7.2 公式/非公式比率データ
- **パス**: `citations_google_comparison[category][subcategory]["official_domain_analysis"]`
- **指標**: `google_official_ratio`, `citations_official_ratio`, `official_bias_delta`
- **解釈**: サブカテゴリレベルでの公式サイト比率比較

### 7.3 ポジティブ/ネガティブ比率データ
- **パス**: `citations_google_comparison[category][subcategory]["sentiment_comparison"]`
- **指標**:
  - `google_sentiment_distribution.positive`
  - `google_sentiment_distribution.negative`
  - `citations_sentiment_distribution.positive`
  - `citations_sentiment_distribution.negative`
  - `positive_bias_delta`
- **解釈**: サブカテゴリレベルでの感情分析結果比較

## 8. 今後の拡張
- 新たな指標や可視化が必要な場合は設計書を随時更新
- 異常値検出アルゴリズムの実装
- 統計的有意性の自動判定機能

---

**本仕様書は{dynamic_date}時点のドラフトです。実装・運用状況に応じて随時更新します。**