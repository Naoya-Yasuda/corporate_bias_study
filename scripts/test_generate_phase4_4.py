import os
from src.utils.plot_utils import plot_multiple_comparison_pvalue_heatmap, plot_ranking_stability_vs_effect_size

# 多重比較補正p値ヒートマップ用ダミーデータ
categories = ["IT", "金融", "医療", "小売"]
pvalue_matrix = [
    [1.0, 0.03, 0.12, 0.07],
    [0.03, 1.0, 0.02, 0.15],
    [0.12, 0.02, 1.0, 0.04],
    [0.07, 0.15, 0.04, 1.0]
]

# 順位安定性vs効果量用ダミーデータ
data = [
    {"entity": "A社", "stability": 0.8, "effect_size": 1.2, "category": "IT"},
    {"entity": "B社", "stability": 0.5, "effect_size": 0.7, "category": "金融"},
    {"entity": "C社", "stability": 0.3, "effect_size": 0.9, "category": "医療"},
    {"entity": "D社", "stability": 0.6, "effect_size": 1.0, "category": "小売"},
    {"entity": "E社", "stability": 0.2, "effect_size": 0.5, "category": "IT"}
]

os.makedirs("test_outputs", exist_ok=True)

# 多重比較補正p値ヒートマップ
plot_multiple_comparison_pvalue_heatmap(
    pvalue_matrix,
    output_path="test_outputs/test_multiple_comparison_pvalue_heatmap.png",
    categories=categories,
    threshold=0.05,
    title="多重比較補正p値ヒートマップ",
    reliability_label="標準"
)

# 順位安定性vs効果量
plot_ranking_stability_vs_effect_size(
    data,
    output_path="test_outputs/test_ranking_stability_vs_effect_size.png",
    x_key="stability",
    y_key="effect_size",
    label_key="entity",
    color_key="category",
    title="順位安定性vs効果量",
    reliability_label="標準"
)

print("Phase4-4テスト画像をtest_outputs/に出力しました。")