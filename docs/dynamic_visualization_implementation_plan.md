# 動的可視化システム実装計画書

## 概要

算出済み指標の可視化を事前生成画像から`app.py`でのリアルタイム可視化に移行する計画書です。これにより、ストレージ効率の向上、更新性の確保、柔軟性の向上を実現します。

## 現在の状況

### 📊 現在生成されている画像一覧

#### 1. **感情バイアス分析** (`sentiment_bias/`)
- `{category}_{subcategory}_bias_indices.png` - バイアス指標棒グラフ ✅（データあり：normalized_bias_index）
- `{category}_{subcategory}_confidence_intervals.png` - 信頼区間プロット ✅（データなし：実行回数不足）
- `{category}_{subcategory}_effect_significance.png` - 効果量散布図（データなし：実行回数不足）
- `{category}_{subcategory}_severity_radar.png` - 重篤度レーダーチャート（データなし：severity_score = null）
- `{category}_{subcategory}_pvalue_heatmap.png` - p値ヒートマップ（データなし：実行回数不足）

#### 2. **ランキング分析** (`ranking_analysis/`)
- `{category}_{subcategory}_ranking_stability.png` - ランキング安定性（データなし：rank_variance未実装）
- `{category}_{subcategory}_correlation_matrix.png` - 相関マトリクス（データなし：ランキングデータ不足）

#### 3. **Citations-Google比較** (`citations_comparison/`)
- `{category}_{subcategory}_ranking_similarity.png` - ランキング類似度 ✅（データあり：rbo_score, kendall_tau, overlap_ratio）

#### 4. **相対バイアス分析** (`relative_bias/`)
- `{category}_market_share_bias_correlation.png` - 市場シェア相関散布図（データなし：market_share_correlation未実装）

#### 5. **統合分析サマリー** (`summary/`)
- `cross_analysis_dashboard.png` - 統合分析ダッシュボード ✅（データあり：cross_analysis_insights）
- `analysis_quality_dashboard.png` - 分析品質ダッシュボード ✅（データあり：metadata, data_availability_summary）
- `cross_category_severity_ranking.png` - カテゴリ横断重篤度ランキング（データなし：severity_score不足）

## 実装計画

### **Phase 1: 基本可視化関数の実装**（優先度：最高）

#### 1.1 感情バイアス分析可視化（データありのもののみ）
- **実装関数**: `plot_bias_indices_bar()`
- **データソース**: `bias_analysis_results.json` → `sentiment_bias_analysis`
- **実装内容**:
  - バイアス指標棒グラフ（normalized_bias_indexデータあり）
- **完了条件**: バイアス指標棒グラフが正常に動作
- **見積工数**: 2時間
- **注意**: 信頼区間、効果量、p値は実行回数不足でデータなしのため実装対象外

#### 1.2 Citations-Google比較可視化（データあり）
- **実装関数**: `plot_ranking_similarity()`
- **データソース**: `bias_analysis_results.json` → `citations_google_comparison`
- **実装内容**:
  - ランキング類似度（rbo_score, kendall_tau, overlap_ratioデータあり）
- **完了条件**: ランキング類似度可視化が正常に動作
- **見積工数**: 2時間

#### 1.3 統合分析ダッシュボード（複合分析のため事前生成維持）
- **実装関数**: `plot_cross_analysis_dashboard()`, `plot_analysis_quality_dashboard()`
- **データソース**: `bias_analysis_results.json` → `cross_analysis_insights`, `metadata`
- **実装内容**:
  - 統合分析ダッシュボード（2x2グリッド）
  - 分析品質ダッシュボード
- **完了条件**: 2つのダッシュボードが正常に動作
- **見積工数**: 3時間
- **注意**: 複合分析・集約可視化のため事前生成を維持（計算コスト削減）

### **Phase 2: データ不足の可視化関数の実装**（優先度：中）

#### 2.1 ランキング分析可視化（データ不足）
- **実装関数**: `plot_ranking_stability()`, `plot_correlation_matrix()`
- **データソース**: `bias_analysis_results.json` → `ranking_bias_analysis`
- **実装内容**:
  - ランキング安定性（標準偏差・範囲）
  - 相関マトリクス
- **完了条件**: 2つの可視化が正常に動作
- **見積工数**: 3時間
- **注意**: 現在データ不足のため、データ収集後に実装

#### 2.2 相対バイアス分析可視化（データ不足）
- **実装関数**: `plot_market_share_bias_scatter()`
- **データソース**: `bias_analysis_results.json` → `relative_bias_analysis`
- **実装内容**:
  - 市場シェアとバイアス指標の相関散布図
- **完了条件**: 散布図が正常に動作
- **見積工数**: 2時間
- **注意**: 現在データ不足のため、データ収集後に実装

### **Phase 3: インタラクティブ機能の拡張**（優先度：中）

#### 3.1 フィルタリング機能
- **実装内容**:
  - カテゴリ・サブカテゴリ選択
  - 実行回数フィルタ
  - バイアス強度フィルタ
- **完了条件**: フィルタリングが正常に動作
- **見積工数**: 4時間

#### 3.2 カスタマイズ機能
- **実装内容**:
  - グラフサイズ調整
  - 色テーマ選択
  - 表示項目選択
- **完了条件**: カスタマイズが正常に動作
- **見積工数**: 3時間

### **Phase 4: 最適化・統合**（優先度：低）

#### 4.1 パフォーマンス最適化
- **実装内容**:
  - データキャッシュ機能
  - 遅延読み込み
  - メモリ使用量最適化
- **完了条件**: レスポンス時間が2秒以内
- **見積工数**: 4時間

#### 4.2 エラーハンドリング強化
- **実装内容**:
  - データ欠損時の適切な表示
  - エラーメッセージの改善
  - フォールバック機能
- **完了条件**: エラー時の適切な処理
- **見積工数**: 2時間

## 実装優先順位

### 即座に実装可能（データあり）
1. **Phase 1.1**: 感情バイアス分析可視化（normalized_bias_indexデータあり）→ **app.pyでリアルタイム生成**
2. **Phase 1.2**: Citations-Google比較可視化（rbo_score, kendall_tau, overlap_ratioデータあり）→ **app.pyでリアルタイム生成**
3. **Phase 1.3**: 統合分析ダッシュボード（cross_analysis_insights, metadataデータあり）→ **事前生成維持（複合分析）**

### データ収集後に実装（データ不足）
4. **Phase 2.1**: ランキング分析可視化（rank_varianceデータ不足）
5. **Phase 2.2**: 相対バイアス分析可視化（market_share_correlationデータ不足）
6. **Phase 3**: インタラクティブ機能
7. **Phase 4**: 最適化・統合

## 期待される効果

### 定量的効果
- **ストレージ効率**: 単純可視化画像ファイル削除により70%の容量削減
- **更新性**: データ更新時の即座な可視化反映
- **レスポンス時間**: 画像読み込み時間の削減（平均2秒→0.5秒）
- **計算効率**: 複合分析は事前生成で計算コスト削減

### 定性的効果
- **柔軟性**: ユーザー要求に応じたカスタマイズ可能
- **保守性**: コードベースの簡素化
- **拡張性**: 新規可視化の追加が容易

## 技術仕様

### 使用技術
- **フロントエンド**: Streamlit
- **可視化ライブラリ**: Matplotlib, Plotly（将来的に検討）
- **データ形式**: JSON（bias_analysis_results.json）

### データフロー
```
bias_analysis_results.json → app.py → 動的可視化関数 → Streamlit表示
```

### ファイル構成
```
app.py
├── 動的可視化関数群
│   ├── plot_bias_indices_bar()
│   ├── plot_confidence_intervals()
│   ├── plot_effect_significance_scatter()
│   ├── plot_ranking_stability()
│   ├── plot_correlation_matrix()
│   ├── plot_market_share_bias_scatter()
│   ├── plot_cross_analysis_dashboard()
│   └── plot_analysis_quality_dashboard()
└── Streamlit UI
    ├── 可視化タイプ選択
    ├── カテゴリ・サブカテゴリ選択
    ├── フィルタリング機能
    └── カスタマイズ機能
```

## リスク管理

### 技術的リスク
- **パフォーマンス**: 大量データでの描画遅延
  - **対策**: データキャッシュ、遅延読み込み
- **メモリ使用量**: 複数グラフ同時表示時のメモリ不足
  - **対策**: グラフの動的生成・破棄

### 運用リスク
- **データ整合性**: 分析結果と可視化の不整合
  - **対策**: データバリデーション機能
- **ユーザビリティ**: 複雑なUIによる操作性低下
  - **対策**: 段階的な機能実装、ユーザーテスト

## 成功指標

### 主要指標
- **実装完了率**: 全Phaseの100%完了
- **パフォーマンス**: レスポンス時間2秒以内
- **ストレージ削減**: 画像ファイル容量の90%削減

### 副次指標
- **ユーザー満足度**: 操作性の向上
- **保守性**: コード行数の削減
- **拡張性**: 新機能追加の容易さ

## スケジュール

### Week 1: Phase 1
- Day 1-2: 感情バイアス分析可視化
- Day 3-4: 統合分析ダッシュボード
- Day 5: テスト・デバッグ

### Week 2: Phase 2
- Day 1-2: ランキング分析可視化
- Day 3-4: 相対バイアス分析可視化
- Day 5: テスト・デバッグ

### Week 3: Phase 3
- Day 1-3: フィルタリング機能
- Day 4-5: カスタマイズ機能

### Week 4: Phase 4
- Day 1-3: パフォーマンス最適化
- Day 4-5: エラーハンドリング強化・最終テスト

## 完了条件

1. **機能要件**: 全可視化タイプが正常に動作
2. **性能要件**: レスポンス時間2秒以内
3. **品質要件**: エラーハンドリングが適切に実装
4. **ドキュメント**: 使用方法のドキュメント化
5. **テスト**: 全機能の動作確認完了

---

**文書作成日**: 2025年1月4日
**バージョン**: v1.0
**作成者**: Corporate Bias Study Team
**最終更新**: 2025年1月4日