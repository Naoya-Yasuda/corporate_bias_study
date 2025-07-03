import os
from src.utils.plot_utils import plot_mask_effect_ranking_sankey

# マスク効果ランキング変動用ダミーデータ
sankey_data = [
    {"entity": "A社", "before": 1, "after": 2, "count": 10, "category": "IT"},
    {"entity": "B社", "before": 2, "after": 1, "count": 8, "category": "金融"},
    {"entity": "C社", "before": 3, "after": 3, "count": 6, "category": "医療"},
    {"entity": "D社", "before": 4, "after": 5, "count": 4, "category": "小売"},
    {"entity": "E社", "before": 5, "after": 4, "count": 2, "category": "IT"}
]

os.makedirs("test_outputs", exist_ok=True)

# マスク効果ランキング変動Sankey図
plot_mask_effect_ranking_sankey(
    sankey_data,
    output_path="test_outputs/test_mask_effect_ranking_sankey.png",
    source_key="before",
    target_key="after",
    value_key="count",
    label_key="entity",
    color_key="category",
    title="マスク効果ランキング変動Sankey図",
    reliability_label="標準"
)

print("Phase4-5テスト画像をtest_outputs/に出力しました。")