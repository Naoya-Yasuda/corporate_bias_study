---
title: Phase 2: タブ別グラフ表示実装 詳細設計書
date: 2025-01-19
type: "detailed_design"
alwaysApply: true
globs: ["**/app.py", "**/plot_utils.py"]
---

# Phase 2: タブ別グラフ表示実装 詳細設計書

## 1. 実装対象の6タブ

### Tab 1: ランキング類似度分析 ✅（既存関数活用）
- **使用関数**: `plot_ranking_similarity` (plot_utils.py)
- **実装優先度**: 高（既存関数の組み込みのみ）
- **データソース**: ranking_bias_analysis

### Tab 2: バイアス指標棒グラフ ✅（既存関数活用）
- **使用関数**: `plot_bias_indices_bar` (plot_utils.py)
- **実装優先度**: 高（既存関数の組み込みのみ）
- **データソース**: ranking_bias_analysis

### Tab 3: ランキング変動ヒートマップ 🔄（新規実装）
- **新規関数**: `plot_ranking_variation_heatmap`
- **実装優先度**: 中
- **データソース**: perplexity_rankings

### Tab 4: 安定性スコア分布 🔄（新規実装）
- **新規関数**: `plot_stability_score_distribution`
- **実装優先度**: 中
- **データソース**: ranking_bias_analysis

### Tab 5: バイアス影響度レーダーチャート 🔄（新規実装）
- **新規関数**: `plot_bias_impact_radar`
- **実装優先度**: 低
- **データソース**: ranking_bias_analysis + perplexity_rankings

### Tab 6: エンティティ別影響度散布図 🔄（新規実装）
- **新規関数**: `plot_entity_impact_scatter`
- **実装優先度**: 低
- **データソース**: perplexity_rankings

## 2. 既存関数の組み込み（Tab 1, 2）

### 2.1 plot_ranking_similarity の確認・組み込み

**現在の関数シグネチャ確認が必要**:
```python
def plot_ranking_similarity(data, ...):
    # 引数・戻り値・データ形式の確認
```

**組み込み方法**:
```python
# app.py内のタブ表示部分
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "ランキング類似度分析", "バイアス指標棒グラフ", "ランキング変動ヒートマップ",
    "安定性スコア分布", "バイアス影響度レーダー", "エンティティ別影響度散布図"
])

with tab1:
    if ranking_bias_data:
        fig = plot_ranking_similarity(ranking_bias_data, selected_category, selected_subcategory)
        if fig:
            st.pyplot(fig, use_container_width=True)
        else:
            st.info("類似度分析データがありません")
    else:
        st.warning("分析データが不足しています")
```

### 2.2 plot_bias_indices_bar の確認・組み込み

**現在の関数シグネチャ確認が必要**:
```python
def plot_bias_indices_bar(data, ...):
    # 引数・戻り値・データ形式の確認
```

## 3. 新規関数実装仕様

### 3.1 Tab 3: ランキング変動ヒートマップ

**関数名**: `plot_ranking_variation_heatmap`

**目的**: 実行回数（X軸）×エンティティ（Y軸）の順位推移をヒートマップで可視化

**データ入力**:
```python
def plot_ranking_variation_heatmap(entities_data, selected_entities=None):
    """
    Args:
        entities_data: perplexity_rankings[category][subcategory]["ranking_summary"]["entities"]
        selected_entities: エンティティ絞り込みリスト

    Returns:
        matplotlib.figure.Figure or None
    """
```

**データ処理**:
```python
# ヒートマップ用のマトリックス作成
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def plot_ranking_variation_heatmap(entities_data, selected_entities=None):
    if not entities_data:
        return None

    # エンティティ絞り込み
    if selected_entities:
        filtered_entities = {k: v for k, v in entities_data.items() if k in selected_entities}
    else:
        filtered_entities = entities_data

    if not filtered_entities:
        return None

    # マトリックス作成
    entity_names = list(filtered_entities.keys())
    max_executions = max(len(entity_data.get("all_ranks", [])) for entity_data in filtered_entities.values())

    if max_executions == 0:
        return None

    # 順位マトリックス（entity x execution）
    rank_matrix = np.full((len(entity_names), max_executions), np.nan)

    for i, entity_name in enumerate(entity_names):
        all_ranks = filtered_entities[entity_name].get("all_ranks", [])
        for j, rank in enumerate(all_ranks):
            if j < max_executions:
                rank_matrix[i, j] = rank

    # プロット作成
    fig, ax = plt.subplots(figsize=(12, 8))

    # ヒートマップ
    sns.heatmap(rank_matrix,
                xticklabels=[f"実行{i+1}" for i in range(max_executions)],
                yticklabels=entity_names,
                cmap='RdYlBu_r',  # 順位なので逆色（低順位=良い=青）
                annot=True,
                fmt='.0f',
                cbar_kws={'label': '順位'},
                ax=ax)

    ax.set_title('ランキング変動ヒートマップ\n（実行回数×エンティティ）', fontsize=14, pad=20)
    ax.set_xlabel('実行回数', fontsize=12)
    ax.set_ylabel('エンティティ', fontsize=12)

    plt.tight_layout()
    return fig
```

### 3.2 Tab 4: 安定性スコア分布

**関数名**: `plot_stability_score_distribution`

**目的**: カテゴリ別・サブカテゴリ別の安定性指標をヒストグラムで比較

**データ入力**:
```python
def plot_stability_score_distribution(ranking_bias_data, current_category, current_subcategory):
    """
    Args:
        ranking_bias_data: 全カテゴリの分析データ
        current_category: 現在のカテゴリ（強調表示用）
        current_subcategory: 現在のサブカテゴリ（強調表示用）

    Returns:
        matplotlib.figure.Figure or None
    """
```

**実装**:
```python
def plot_stability_score_distribution(ranking_bias_data, current_category, current_subcategory):
    if not ranking_bias_data:
        return None

    # 全カテゴリ・サブカテゴリの安定性データを収集
    stability_scores = []
    categories_info = []

    for category, category_data in ranking_bias_data.items():
        for subcategory, subcat_data in category_data.items():
            category_summary = subcat_data.get("category_summary", {})
            stability_analysis = category_summary.get("stability_analysis", {})

            overall_stability = stability_analysis.get("overall_stability")
            avg_rank_std = stability_analysis.get("avg_rank_std")

            if overall_stability is not None and avg_rank_std is not None:
                stability_scores.append(overall_stability)
                is_current = (category == current_category and subcategory == current_subcategory)
                categories_info.append({
                    'category': category,
                    'subcategory': subcategory,
                    'stability': overall_stability,
                    'std': avg_rank_std,
                    'is_current': is_current
                })

    if not stability_scores:
        return None

    # プロット作成
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # 左: 安定性スコア分布ヒストグラム
    ax1.hist(stability_scores, bins=10, alpha=0.7, color='skyblue', edgecolor='black')

    # 現在のカテゴリの値を強調
    current_stability = None
    for info in categories_info:
        if info['is_current']:
            current_stability = info['stability']
            break

    if current_stability is not None:
        ax1.axvline(current_stability, color='red', linestyle='--', linewidth=2,
                   label=f'現在カテゴリ: {current_stability:.3f}')
        ax1.legend()

    ax1.set_title('安定性スコア分布', fontsize=12)
    ax1.set_xlabel('安定性スコア', fontsize=10)
    ax1.set_ylabel('頻度', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 右: 安定性vs標準偏差の散布図
    x_vals = [info['stability'] for info in categories_info]
    y_vals = [info['std'] for info in categories_info]
    colors = ['red' if info['is_current'] else 'blue' for info in categories_info]

    ax2.scatter(x_vals, y_vals, c=colors, alpha=0.6, s=50)
    ax2.set_title('安定性スコア vs 順位標準偏差', fontsize=12)
    ax2.set_xlabel('安定性スコア', fontsize=10)
    ax2.set_ylabel('平均順位標準偏差', fontsize=10)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig
```

### 3.3 Tab 5: バイアス影響度レーダーチャート

**関数名**: `plot_bias_impact_radar`

**目的**: エンティティ別の多次元バイアス影響度をレーダーチャートで表示

**実装**:
```python
def plot_bias_impact_radar(entities_data, ranking_bias_data, selected_entities=None):
    """
    Args:
        entities_data: ランキング生データ
        ranking_bias_data: 分析済みバイアスデータ
        selected_entities: 表示対象エンティティ
    """
    if not entities_data:
        return None

    # 指標軸定義
    radar_axes = ['平均順位', '順位安定性', '出現頻度', 'バイアス感度', '競争力']

    # エンティティ別指標計算
    entity_scores = {}
    for entity_name, entity_data in entities_data.items():
        if selected_entities and entity_name not in selected_entities:
            continue

        all_ranks = entity_data.get("all_ranks", [])
        if not all_ranks:
            continue

        # 各指標を0-1スケールで正規化
        avg_rank = sum(all_ranks) / len(all_ranks)
        rank_stability = 1 / (1 + np.std(all_ranks))  # 標準偏差の逆数
        appearance_freq = len(all_ranks) / 15  # 15回実行基準
        bias_sensitivity = np.std(all_ranks) / 5  # 順位変動の敏感度
        competitiveness = 1 / max(1, avg_rank)  # 平均順位の逆数

        entity_scores[entity_name] = [
            1 - min(1, avg_rank / 10),  # 順位は低いほど良い
            min(1, rank_stability),
            min(1, appearance_freq),
            min(1, bias_sensitivity),
            min(1, competitiveness)
        ]

    if not entity_scores:
        return None

    # レーダーチャート作成
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

    # 角度設定
    angles = np.linspace(0, 2 * np.pi, len(radar_axes), endpoint=False).tolist()
    angles += angles[:1]  # 円を閉じる

    # 各エンティティのプロット
    colors = plt.cm.tab10(np.linspace(0, 1, len(entity_scores)))

    for i, (entity_name, scores) in enumerate(entity_scores.items()):
        scores_closed = scores + scores[:1]  # 円を閉じる
        ax.plot(angles, scores_closed, 'o-', linewidth=2, label=entity_name, color=colors[i])
        ax.fill(angles, scores_closed, alpha=0.25, color=colors[i])

    # レーダーチャート設定
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(radar_axes)
    ax.set_ylim(0, 1)
    ax.set_title('エンティティ別バイアス影響度レーダーチャート', fontsize=14, pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1))

    return fig
```

### 3.4 Tab 6: エンティティ別影響度散布図

**関数名**: `plot_entity_impact_scatter`

**目的**: 平均順位（X軸） vs 順位標準偏差（Y軸）での散布図

**実装**:
```python
def plot_entity_impact_scatter(entities_data, selected_entities=None):
    if not entities_data:
        return None

    x_vals, y_vals, labels, sizes = [], [], [], []

    for entity_name, entity_data in entities_data.items():
        if selected_entities and entity_name not in selected_entities:
            continue

        all_ranks = entity_data.get("all_ranks", [])
        if len(all_ranks) < 2:
            continue

        avg_rank = sum(all_ranks) / len(all_ranks)
        rank_std = np.std(all_ranks)

        x_vals.append(avg_rank)
        y_vals.append(rank_std)
        labels.append(entity_name)
        sizes.append(len(all_ranks) * 10)  # 実行回数に比例したサイズ

    if not x_vals:
        return None

    fig, ax = plt.subplots(figsize=(12, 8))

    scatter = ax.scatter(x_vals, y_vals, s=sizes, alpha=0.6, c=range(len(x_vals)), cmap='viridis')

    # ラベル追加
    for i, label in enumerate(labels):
        ax.annotate(label, (x_vals[i], y_vals[i]), xytext=(5, 5),
                   textcoords='offset points', fontsize=9)

    ax.set_xlabel('平均順位', fontsize=12)
    ax.set_ylabel('順位標準偏差（変動度）', fontsize=12)
    ax.set_title('エンティティ別影響度散布図\n（平均順位 vs 順位変動）', fontsize=14)

    # 象限線追加
    x_median = np.median(x_vals)
    y_median = np.median(y_vals)
    ax.axhline(y_median, color='gray', linestyle='--', alpha=0.5)
    ax.axvline(x_median, color='gray', linestyle='--', alpha=0.5)

    # 象限ラベル
    ax.text(min(x_vals), max(y_vals), '高順位・高変動', fontsize=10, alpha=0.7)
    ax.text(max(x_vals), max(y_vals), '低順位・高変動', fontsize=10, alpha=0.7)
    ax.text(min(x_vals), min(y_vals), '高順位・安定', fontsize=10, alpha=0.7)
    ax.text(max(x_vals), min(y_vals), '低順位・安定', fontsize=10, alpha=0.7)

    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig
```

## 4. app.py への統合実装

### 4.1 タブUI実装
```python
# === 3. タブ別グラフ表示 ===
st.subheader("📈 詳細グラフ分析")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "ランキング類似度分析", "バイアス指標棒グラフ", "ランキング変動ヒートマップ",
    "安定性スコア分布", "バイアス影響度レーダー", "エンティティ別影響度散布図"
])

with tab1:
    st.markdown("**ランキング類似度分析**")
    if ranking_bias_data and selected_category in ranking_bias_data and selected_subcategory in ranking_bias_data[selected_category]:
        try:
            fig = plot_ranking_similarity(ranking_bias_data, selected_category, selected_subcategory)
            if fig:
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
            else:
                st.info("類似度分析データがありません")
        except Exception as e:
            st.error(f"グラフ描画エラー: {str(e)}")
    else:
        st.warning("分析データが不足しています")

with tab2:
    st.markdown("**バイアス指標棒グラフ**")
    # 同様の実装パターン

with tab3:
    st.markdown("**ランキング変動ヒートマップ**")
    try:
        fig = plot_ranking_variation_heatmap(entities, selected_entities)
        if fig:
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
        else:
            st.info("ヒートマップ用のデータがありません")
    except Exception as e:
        st.error(f"ヒートマップ描画エラー: {str(e)}")

# Tab 4-6も同様のパターン
```

## 5. 実装スケジュール

### Week 1: 既存関数組み込み（Tab 1, 2）
- [ ] plot_ranking_similarity関数の確認・組み込み
- [ ] plot_bias_indices_bar関数の確認・組み込み
- [ ] タブUI基盤の実装

### Week 2: 新規関数実装（Tab 3, 4）
- [ ] plot_ranking_variation_heatmap実装
- [ ] plot_stability_score_distribution実装

### Week 3: 高度グラフ実装（Tab 5, 6）
- [ ] plot_bias_impact_radar実装
- [ ] plot_entity_impact_scatter実装

### Week 4: 統合テスト・調整
- [ ] 全タブ動作確認
- [ ] エラーハンドリング強化
- [ ] UI/UX調整

---

**次のステップ**: 既存関数（plot_ranking_similarity, plot_bias_indices_bar）の確認から開始