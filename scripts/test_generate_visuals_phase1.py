import os
from src.utils.plot_utils import plot_confidence_intervals, plot_severity_radar, plot_cross_category_severity_ranking
import matplotlib.pyplot as plt
import japanize_matplotlib

# テスト用ダミーデータ
bi_dict = {
    "A社": 0.85,
    "B社": -0.42,
    "C社": 0.12,
    "D社": -0.05,
    "E社": 0.33
}
ci_dict = {
    "A社": (0.60, 1.10),
    "B社": (-0.70, -0.10),
    "C社": (-0.10, 0.35),
    "D社": (-0.30, 0.20),
    "E社": (0.10, 0.55)
}
severity_dict = {
    "A社": {"abs_bi": 0.85, "cliffs_delta": 0.5, "p_value": 0.01, "stability_score": 0.92, "severity_score": {"severity_score": 7.8}},
    "B社": {"abs_bi": 0.42, "cliffs_delta": 0.2, "p_value": 0.12, "stability_score": 0.80, "severity_score": {"severity_score": 2.1}},
    "C社": {"abs_bi": 0.12, "cliffs_delta": 0.1, "p_value": 0.45, "stability_score": 0.75, "severity_score": {"severity_score": 0.3}},
    "D社": {"abs_bi": 0.05, "cliffs_delta": 0.05, "p_value": 0.60, "stability_score": 0.60, "severity_score": {"severity_score": 0.1}},
    "E社": {"abs_bi": 0.33, "cliffs_delta": 0.3, "p_value": 0.08, "stability_score": 0.85, "severity_score": {"severity_score": 1.5}}
}

os.makedirs("test_outputs", exist_ok=True)

try:
    # 信頼区間プロット
    plot_confidence_intervals(bi_dict, ci_dict, output_path="test_outputs/test_confidence_intervals.png", reliability_label="標準")
except Exception as e:
    print(f"plot_confidence_intervalsで例外発生: {e}")

try:
    # 重篤度レーダーチャート
    plot_severity_radar(severity_dict, output_path="test_outputs/test_severity_radar.png", reliability_label="高精度")
except Exception as e:
    print(f"plot_severity_radarで例外発生: {e}")

try:
    # 重篤度ランキング（カテゴリ横断）
    severity_list = [
        {"entity": "A社", "category": "IT", "subcategory": "クラウド", "severity_score": {"severity_score": 7.8}},
        {"entity": "B社", "category": "IT", "subcategory": "クラウド", "severity_score": {"severity_score": 2.1}},
        {"entity": "C社", "category": "金融", "subcategory": "決済", "severity_score": {"severity_score": 0.3}},
        {"entity": "D社", "category": "金融", "subcategory": "決済", "severity_score": {"severity_score": 0.1}},
        {"entity": "E社", "category": "IT", "subcategory": "AI", "severity_score": {"severity_score": 1.5}},
        {"entity": "F社", "category": "IT", "subcategory": "AI", "severity_score": {"severity_score": 4.5}},
        {"entity": "G社", "category": "流通", "subcategory": "小売", "severity_score": {"severity_score": 8.2}}
    ]
    plot_cross_category_severity_ranking(severity_list, output_path="test_outputs/test_cross_category_severity_ranking.png", reliability_label="実用")
except Exception as e:
    print(f"plot_cross_category_severity_rankingで例外発生: {e}")

print("テスト画像をtest_outputs/に出力しました。")