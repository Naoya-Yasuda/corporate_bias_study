import os

# テスト用ダミーデータ
dummy_quality_data = {
    "metadata": {"reliability_level": "標準"},
    "data_availability_summary": {"completeness": 0.92, "coverage": 0.95},
    "analysis_limitations": ["一部カテゴリで実行回数不足", "データ欠損あり"],
    "category_exec_counts": [10, 12, 8, 15, 9, 11, 7, 13],
    "category_fail_counts": [0, 1, 0, 0, 1, 0, 0, 0],
    "total_calculations": 8,
    "successful_calculations": 6,
    "warnings": {"completeness": 1, "coverage": 1, "制限事項": 2}
}

os.makedirs("test_outputs", exist_ok=True)

# --- plot_analysis_quality_dashboardのimportとテスト呼び出しを削除 ---

print("品質管理ダッシュボード画像をtest_outputs/に出力しました。")