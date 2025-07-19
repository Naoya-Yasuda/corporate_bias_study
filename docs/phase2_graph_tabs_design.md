---
title: Phase 2: タブ別グラフ表示実装 詳細設計書
date: 2025-01-19
type: "detailed_design"
alwaysApply: true
globs: ["**/app.py", "**/plot_utils.py"]
---

# Phase 2: タブ別グラフ表示実装 詳細設計書

## 1. 実装対象の3タブ

### Tab 1: ランキング類似度分析 ✅（実装済み）
- **使用関数**: `plot_ranking_similarity_for_ranking_analysis` (plot_utils.py)
- **実装優先度**: 高（既存関数の組み込みのみ）
- **データソース**: ranking_bias_analysis
- **実装状況**: ✅ 完了（2025年1月19日）

### Tab 2: バイアス指標棒グラフ ✅（実装済み）
- **使用関数**: `plot_bias_indices_bar_for_ranking_analysis` (plot_utils.py)
- **実装優先度**: 高（既存関数の組み込みのみ）
- **データソース**: ranking_bias_analysis
- **実装状況**: ✅ 完了（2025年1月19日）

### Tab 3: ランキング変動ヒートマップ ✅（実装済み）
- **新規関数**: `plot_ranking_variation_heatmap`
- **実装優先度**: 中
- **データソース**: perplexity_rankings
- **実装状況**: ✅ 完了（2025年1月19日）

## 2. 将来実装予定のタブ（Week 3以降）

### Tab 4: バイアス影響度レーダーチャート ⏳（未実装）
- **新規関数**: `plot_bias_impact_radar`
- **実装優先度**: 低
- **データソース**: ranking_bias_analysis + perplexity_rankings
- **実装状況**: ⏳ 未実装（Week 3予定）

### Tab 5: エンティティ別影響度散布図 ⏳（未実装）
- **新規関数**: `plot_entity_impact_scatter`
- **実装優先度**: 低
- **データソース**: perplexity_rankings
- **実装状況**: ⏳ 未実装（Week 3予定）

## 3. 実装完了済み関数の詳細

### 3.1 plot_ranking_similarity_for_ranking_analysis ✅
**実装完了**: 2025年1月19日
**機能**: Google検索とPerplexityの検索結果の類似度を3つの指標で比較
- RBO：上位の検索結果がどれだけ一致しているか
- Kendall Tau：順位の並びがどれだけ似ているか
- Overlap Ratio：全体の検索結果がどれだけ重複しているか

### 3.2 plot_bias_indices_bar_for_ranking_analysis ✅
**実装完了**: 2025年1月19日
**機能**: 各エンティティのバイアス指標を棒グラフで表示
- バイアス指標は、各エンティティと他のエンティティとの順位差の平均値として計算
- 正の値（赤）：他のエンティティより平均的に上位に位置する傾向
- 負の値（緑）：他のエンティティより平均的に下位に位置する傾向

### 3.3 plot_ranking_variation_heatmap ✅
**実装完了**: 2025年1月19日
**機能**: 各エンティティの順位変動を実行回数ごとにヒートマップで表示
- 実行回数（X軸）×エンティティ（Y軸）の順位推移
- 色が濃いほど順位が低く、薄いほど順位が高いことを示す

## 4. 将来実装予定関数の仕様

### 4.1 Tab 4: バイアス影響度レーダーチャート ⏳

**関数名**: `plot_bias_impact_radar`

**目的**: エンティティ別の多次元バイアス影響度をレーダーチャートで表示

**実装予定**:
```python
def plot_bias_impact_radar(entities_data, ranking_bias_data, selected_entities=None):
    """
    Args:
        entities_data: ランキング生データ
        ranking_bias_data: 分析済みバイアスデータ
        selected_entities: 表示対象エンティティ
    """
    # 指標軸定義
    radar_axes = ['平均順位', '順位安定性', '出現頻度', 'バイアス感度', '競争力']

    # 各エンティティの指標計算とレーダーチャート作成
    # （実装詳細はWeek 3で決定）
```

### 4.2 Tab 5: エンティティ別影響度散布図 ⏳

**関数名**: `plot_entity_impact_scatter`

**目的**: 平均順位（X軸） vs 順位標準偏差（Y軸）での散布図

**実装予定**:
```python
def plot_entity_impact_scatter(entities_data, selected_entities=None):
    """
    Args:
        entities_data: perplexity_rankings[category][subcategory]["ranking_summary"]["entities"]
        selected_entities: エンティティ絞り込みリスト
    """
    # 平均順位と順位標準偏差の計算
    # 散布図作成と象限線追加
    # （実装詳細はWeek 3で決定）
```

## 5. 実装スケジュール更新

### ✅ Week 1: 既存関数組み込み（Tab 1, 2） - 完了
- [x] plot_ranking_similarity関数の確認・組み込み
- [x] plot_bias_indices_bar関数の確認・組み込み
- [x] タブUI基盤の実装

### ✅ Week 2: 新規関数実装（Tab 3） - 完了
- [x] plot_ranking_variation_heatmap実装

### ⏳ Week 3: 高度グラフ実装（Tab 4, 5） - 未実装
- [ ] plot_bias_impact_radar実装
- [ ] plot_entity_impact_scatter実装

### ⏳ Week 4: 統合テスト・調整 - 未実装
- [ ] 全タブ動作確認
- [ ] エラーハンドリング強化
- [ ] UI/UX調整

---

**注記**: 安定性スコア分布（旧Tab 4）は統合分析ダッシュボードに移動済み。カテゴリ横断的な分析として、重篤度ランキングなどと共に表示する。