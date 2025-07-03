import os
from src.utils.plot_utils import plotly_pvalue_heatmap, plotly_correlation_matrix, plotly_market_share_bias_scatter

# テスト用ダミーデータ
pvalue_dict = {
    "A社": 0.003,
    "B社": 0.045,
    "C社": 0.12,
    "D社": 0.0005,
    "E社": 0.21
}
corr_dict = {
    "labels": ["Run1", "Run2", "Run3"],
    "pearson": [[1.0, 0.85, 0.80], [0.85, 1.0, 0.78], [0.80, 0.78, 1.0]],
    "spearman": [[1.0, 0.82, 0.75], [0.82, 1.0, 0.70], [0.75, 0.70, 1.0]],
    "kendall": [[1.0, 0.65, 0.60], [0.65, 1.0, 0.55], [0.60, 0.55, 1.0]]
}
market_share_dict = {
    "A社": 0.35,
    "B社": 0.22,
    "C社": 0.18,
    "D社": 0.10,
    "E社": 0.05
}
bi_dict = {
    "A社": 0.85,
    "B社": -0.42,
    "C社": 0.12,
    "D社": -0.05,
    "E社": 0.33
}

os.makedirs("test_outputs", exist_ok=True)

# p値ヒートマップ（インタラクティブ）
plotly_pvalue_heatmap(pvalue_dict, output_path="test_outputs/test_pvalue_heatmap_interactive.html")

# 相関マトリクス（インタラクティブ）
plotly_correlation_matrix(corr_dict, output_path="test_outputs/test_correlation_matrix_interactive.html")

# 市場シェア×BI散布図（インタラクティブ）
plotly_market_share_bias_scatter(market_share_dict, bi_dict, output_path="test_outputs/test_market_share_bias_scatter_interactive.html")

print("Phase3インタラクティブテストHTMLをtest_outputs/に出力しました。")