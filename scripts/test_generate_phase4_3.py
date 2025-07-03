import os
from src.utils.plot_utils import plot_market_power_vs_bias, plot_category_stability_analysis

# 市場支配力vs優遇度用ダミーデータ
entity_data = [
    {"entity": "A社", "market_share": 0.35, "bi": 0.8, "revenue": 100, "category": "IT"},
    {"entity": "B社", "market_share": 0.25, "bi": -0.5, "revenue": 80, "category": "金融"},
    {"entity": "C社", "market_share": 0.15, "bi": 0.2, "revenue": 60, "category": "IT"},
    {"entity": "D社", "market_share": 0.10, "bi": 0.6, "revenue": 90, "category": "医療"},
    {"entity": "E社", "market_share": 0.08, "bi": -0.1, "revenue": 70, "category": "金融"},
    {"entity": "F社", "market_share": 0.07, "bi": 0.4, "revenue": 50, "category": "医療"}
]

# カテゴリ安定性分析用ダミーデータ
stability_data = [
    {"category": "IT", "year": 2021, "bi": 0.7},
    {"category": "IT", "year": 2022, "bi": 0.8},
    {"category": "IT", "year": 2023, "bi": 0.6},
    {"category": "金融", "year": 2021, "bi": -0.2},
    {"category": "金融", "year": 2022, "bi": -0.1},
    {"category": "金融", "year": 2023, "bi": -0.3},
    {"category": "医療", "year": 2021, "bi": 0.3},
    {"category": "医療", "year": 2022, "bi": 0.4},
    {"category": "医療", "year": 2023, "bi": 0.5}
]

os.makedirs("test_outputs", exist_ok=True)

# 市場支配力vs優遇度散布図
plot_market_power_vs_bias(
    entity_data,
    output_path="test_outputs/test_market_power_vs_bias.png",
    x_key="market_share",
    y_key="bi",
    size_key="revenue",
    label_key="entity",
    color_key="category",
    title="市場支配力vs優遇度散布図",
    reliability_label="標準"
)

# カテゴリ安定性分析（時系列推移＋分散棒グラフ）
plot_category_stability_analysis(
    stability_data,
    output_path="test_outputs/test_category_stability_analysis.png",
    time_key="year",
    value_key="bi",
    category_key="category",
    title="カテゴリ安定性分析",
    reliability_label="標準"
)

print("Phase4-3テスト画像をtest_outputs/に出力しました。")