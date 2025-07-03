import os
from src.utils.plot_utils import plot_bias_pattern_classification, plot_bias_inequality_detailed

# バイアスパターン分類図用ダミーデータ
entity_data = [
    {"entity": "A社", "bi": 0.8, "size": 100, "cluster_label": "大企業優遇型"},
    {"entity": "B社", "bi": -0.5, "size": 80, "cluster_label": "中立型"},
    {"entity": "C社", "bi": 0.2, "size": 60, "cluster_label": "選択的優遇型"},
    {"entity": "D社", "bi": 0.6, "size": 90, "cluster_label": "大企業優遇型"},
    {"entity": "E社", "bi": -0.1, "size": 70, "cluster_label": "中立型"},
    {"entity": "F社", "bi": 0.4, "size": 50, "cluster_label": "選択的優遇型"}
]

# ローレンツ曲線用ダミーデータ
bi_values = [0.8, -0.5, 0.2, 0.6, -0.1, 0.4]

os.makedirs("test_outputs", exist_ok=True)

# バイアスパターン分類図
plot_bias_pattern_classification(
    entity_data,
    output_path="test_outputs/test_bias_pattern_classification.png",
    x_key="bi",
    y_key="size",
    label_key="cluster_label",
    title="バイアスパターン分類図",
    reliability_label="標準"
)

# ローレンツ曲線不平等度詳細
plot_bias_inequality_detailed(
    bi_values,
    output_path="test_outputs/test_bias_inequality_detailed.png",
    title="ローレンツ曲線による不平等度詳細",
    reliability_label="標準"
)

print("Phase4-2テスト画像をtest_outputs/に出力しました。")