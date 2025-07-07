#!/usr/bin/env python
# coding: utf-8

"""
バイアス分析結果可視化生成スクリプト

【2025年7月改訂】
本スクリプトは「横断的・複雑な可視化のみ画像事前生成」方針に基づき、
カテゴリ横断重篤度ランキング、サマリーダッシュボード、相関マトリクス等のみ画像として出力します。
BI値棒グラフや単一カテゴリの重篤度レーダーチャート等、単純な指標は画像生成せず、app.pyで動的に可視化してください。
"""

import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# 既存のplot_utilsを活用
from src.utils.plot_utils import (
    plot_delta_ranks,
    plot_market_impact,
    plot_rank_heatmap,
    plot_exposure_market,
    plot_confidence_intervals,
    plot_severity_radar,
    plot_pvalue_heatmap,
    plot_correlation_matrix,
    plot_market_share_bias_scatter,
    plot_cross_category_severity_ranking,
    plot_analysis_quality_dashboard
)
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_utils import ensure_dir, save_figure
from src.analysis.bias_analysis_engine import ReliabilityChecker

import matplotlib.pyplot as plt
import japanize_matplotlib
import numpy as np

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AnalysisVisualizationGenerator:
    """分析結果から可視化画像を生成するクラス"""

    def __init__(self, storage_mode: str = "auto"):
        """
        Parameters:
        -----------
        storage_mode : str
            ストレージモード ('local', 's3', 'auto')
        """
        self.storage_mode = storage_mode
        self.data_loader = HybridDataLoader(storage_mode)

        # 出力ディレクトリの設定（corporate_bias_datasets配下に統一）
        # ローカル・S3共にcorporate_bias_datasets/analysis_visuals/YYYYMMDD/
        self.output_base_dir = "corporate_bias_datasets/analysis_visuals"
        ensure_dir(self.output_base_dir)

    def generate_all_visuals(self, date_or_path: str) -> Dict[str, List[str]]:
        """指定日付の分析結果から全可視化画像を生成

        Parameters:
        -----------
        date_or_path : str
            日付（YYYYMMDD）またはパス

        Returns:
        --------
        Dict[str, List[str]]
            生成された画像ファイルパス一覧
        """
        logger.info(f"可視化画像生成開始: {date_or_path}")

        try:
            # 分析結果の読み込み
            analysis_results = self.data_loader.load_analysis_results(date_or_path)

            if not analysis_results:
                logger.error(f"分析結果が見つかりません: {date_or_path}")
                return {}

            # 出力ディレクトリの作成
            output_dir = Path(self.output_base_dir) / date_or_path
            ensure_dir(str(output_dir))

            generated_files = {
                "cross_analysis": []
            }

            # 統合分析サマリー可視化のみ生成
            summary_files = self._generate_summary_visuals(
                analysis_results,
                output_dir / "summary"
            )
            generated_files["cross_analysis"].extend(summary_files)

            total_files = sum(len(files) for files in generated_files.values())
            logger.info(f"可視化画像生成完了: {total_files}ファイル生成")

            return generated_files

        except Exception as e:
            logger.error(f"可視化画像生成エラー: {e}")
            raise

    def _generate_summary_visuals(self, analysis_results: Dict, output_dir: Path) -> List[str]:
        """
        統合分析サマリー可視化を生成
        ※cross_category_severity_ranking, cross_analysis_dashboard, analysis_quality_dashboard等、横断的・複雑な可視化のみ画像生成対象。
        """
        ensure_dir(str(output_dir))
        generated_files = []
        # --- 横断的・複雑な可視化のみ画像生成 ---
        cross_analysis = analysis_results.get("cross_analysis_insights", {})
        if cross_analysis:
            output_path = output_dir / "cross_analysis_dashboard.png"
            self._plot_cross_analysis_dashboard(cross_analysis, str(output_path))
            generated_files.append(str(output_path))
        # カテゴリ横断重篤度ランキング
        sentiment_data = analysis_results.get("sentiment_bias_analysis", {})
        severity_list = []
        for category, subcategories in sentiment_data.items():
            for subcategory, data in subcategories.items():
                entities = data.get("entities", {})
                for entity, entity_data in entities.items():
                    sev = entity_data.get("severity_score")
                    if isinstance(sev, dict):
                        score = sev.get("severity_score")
                    else:
                        score = sev
                    if score is not None:
                        severity_list.append({
                            "entity": entity,
                            "category": category,
                            "subcategory": subcategory,
                            "severity_score": score
                        })
        if severity_list:
            exec_counts = []
            for category, subcategories in sentiment_data.items():
                for subcategory, data in subcategories.items():
                    entities = data.get("entities", {})
                    for entity, entity_data in entities.items():
                        exec_count = entity_data.get("basic_metrics", {}).get("execution_count", 1)
                        exec_counts.append(exec_count)
            min_exec = min(exec_counts) if exec_counts else 1
            reliability_label, _ = ReliabilityChecker().get_reliability_level(min_exec)
            output_path = output_dir / "cross_category_severity_ranking.png"
            plot_cross_category_severity_ranking(severity_list, str(output_path), reliability_label=reliability_label)
            generated_files.append(str(output_path))
        # 品質管理ダッシュボード
        metadata = analysis_results.get("metadata", {})
        data_availability_summary = analysis_results.get("data_availability_summary", {})
        analysis_limitations = analysis_results.get("analysis_limitations", [])
        sentiment_data = analysis_results.get("sentiment_bias_analysis", {})
        category_exec_counts = []
        category_fail_counts = []
        for category, subcategories in sentiment_data.items():
            for subcategory, data in subcategories.items():
                entities = data.get("entities", {})
                for entity, entity_data in entities.items():
                    exec_count = entity_data.get("basic_metrics", {}).get("execution_count", 1)
                    category_exec_counts.append(exec_count)
                    if entity_data.get("severity_score") is None:
                        category_fail_counts.append(1)
        total_calculations = len(category_exec_counts)
        successful_calculations = total_calculations - sum(category_fail_counts)
        warnings = {}
        if isinstance(data_availability_summary, dict):
            for k, v in data_availability_summary.items():
                if isinstance(v, (int, float)) and v < 1.0:
                    warnings[k] = warnings.get(k, 0) + 1
        if isinstance(analysis_limitations, list):
            warnings["制限事項"] = len(analysis_limitations)
        quality_data = {
            "metadata": metadata,
            "data_availability_summary": data_availability_summary,
            "analysis_limitations": analysis_limitations,
            "category_exec_counts": category_exec_counts,
            "category_fail_counts": category_fail_counts,
            "total_calculations": total_calculations,
            "successful_calculations": successful_calculations,
            "warnings": warnings
        }
        reliability_label = metadata.get("reliability_level", "参考")
        output_path = output_dir / "analysis_quality_dashboard.png"
        plot_analysis_quality_dashboard(quality_data, str(output_path), reliability_label=reliability_label)
        generated_files.append(str(output_path))
        return generated_files

    def _plot_bias_indices_bar(self, bias_indices: Dict, output_path: str, title: str, reliability_label=None):
        from src.utils.plot_utils import draw_reliability_badge
        import matplotlib.pyplot as plt
        from src.utils.storage_utils import save_figure
        entities = list(bias_indices.keys())
        values = [bias_indices[e] for e in entities]
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(entities, values, color=["red" if v > 0 else "green" for v in values])
        ax.axhline(0, color='k', linestyle='--', alpha=0.5)
        ax.set_ylabel("Normalized Bias Index (BI)")
        ax.set_title(title)
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        if reliability_label:
            draw_reliability_badge(ax, reliability_label)
        save_figure(fig, output_path, storage_mode=self.storage_mode)

    def _plot_effect_significance_scatter(self, effect_data: Dict, output_path: str, title: str, reliability_label=None):
        from src.utils.plot_utils import draw_reliability_badge
        import matplotlib.pyplot as plt
        from src.utils.storage_utils import save_figure
        entities = list(effect_data.keys())
        cliffs = [effect_data[e]["cliffs_delta"] for e in entities]
        pvals = [effect_data[e]["p_value"] for e in entities]
        fig, ax = plt.subplots(figsize=(8, 6))
        scatter = ax.scatter(cliffs, [-np.log10(p) if p > 0 else 0 for p in pvals], c=["red" if c > 0 else "green" for c in cliffs], s=80)
        for i, e in enumerate(entities):
            ax.annotate(e, (cliffs[i], -np.log10(pvals[i]) if pvals[i] > 0 else 0), fontsize=10)
        ax.set_xlabel("Cliff's Delta")
        ax.set_ylabel("-log10(p値)")
        ax.set_title(title)
        plt.tight_layout()
        if reliability_label:
            draw_reliability_badge(ax, reliability_label)
        save_figure(fig, output_path, storage_mode=self.storage_mode)

    def _plot_ranking_stability(self, rank_variance: Dict, output_path: str, title: str):
        import matplotlib.pyplot as plt
        from src.utils.storage_utils import save_figure
        entities = list(rank_variance.keys())
        stds = [data["rank_std"] for data in rank_variance.values()]
        ranges = [data["rank_range"] for data in rank_variance.values()]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        ax1.bar(entities, stds, alpha=0.7, color='blue')
        ax1.set_title("順位の標準偏差")
        ax1.set_ylabel("標準偏差")
        ax1.tick_params(axis='x', rotation=45)
        ax2.bar(entities, ranges, alpha=0.7, color='orange')
        ax2.set_title("順位の範囲")
        ax2.set_ylabel("範囲（最大-最小）")
        ax2.tick_params(axis='x', rotation=45)
        fig.suptitle(f"{title} - ランキング安定性", fontsize=14)
        plt.tight_layout()
        save_figure(fig, output_path, storage_mode=self.storage_mode)

    def _plot_ranking_similarity(self, similarity_data: Dict, output_path: str, title: str):
        import matplotlib.pyplot as plt
        from src.utils.storage_utils import save_figure

        # 日本語フォント設定
        plt.rcParams['font.family'] = ['IPAexGothic', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP']

        metrics = ['rbo_score', 'kendall_tau', 'overlap_ratio']
        values = [similarity_data.get(metric, 0) for metric in metrics]
        labels = ['RBO\n(上位重視重複度)', 'Kendall Tau\n(順位相関)', 'Overlap Ratio\n(共通要素率)']
        fig, ax = plt.subplots(figsize=(10, 7))
        bars = ax.bar(labels, values, alpha=0.7, color=['blue', 'orange', 'green'])
        ax.set_title(f"{title} - Google vs Perplexity類似度")
        ax.set_ylabel("類似度スコア")
        ax.set_ylim(0, 1)

        # X軸ラベルの回転と位置調整
        plt.xticks(rotation=0, ha='center')

        for bar, value in zip(bars, values):
            if value is not None:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.02,
                        f'{value:.3f}', ha='center', va='bottom', fontweight='bold')

        # グリッド追加
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        save_figure(fig, output_path, storage_mode=self.storage_mode)

    def _plot_cross_analysis_dashboard(self, cross_analysis: Dict, output_path: str):
        import matplotlib.pyplot as plt
        import numpy as np
        from src.utils.storage_utils import save_figure
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        correlation = cross_analysis.get("sentiment_ranking_correlation", 0)
        ax1.bar(['相関'], [correlation], color='blue', alpha=0.7)
        ax1.set_title("感情-ランキング相関")
        ax1.set_ylabel("相関係数")
        ax1.set_ylim(-1, 1)
        leaders = cross_analysis.get("consistent_leaders", [])
        laggards = cross_analysis.get("consistent_laggards", [])
        ax2.bar(['リーダー', 'ラガード'], [len(leaders), len(laggards)],
                color=['green', 'red'], alpha=0.7)
        ax2.set_title("一貫性企業数")
        ax2.set_ylabel("企業数")
        alignment = cross_analysis.get("google_citations_alignment", "unknown")
        alignment_score = {"high": 3, "moderate": 2, "low": 1, "unknown": 0}.get(alignment, 0)
        ax3.bar(['整合性'], [alignment_score], color='orange', alpha=0.7)
        ax3.set_title("Google-Citations整合性")
        ax3.set_ylabel("整合性レベル")
        ax3.set_ylim(0, 3)
        pattern = cross_analysis.get("overall_bias_pattern", "balanced")
        pattern_labels = {"large_enterprise_favoritism": "大企業優遇",
                         "small_enterprise_favoritism": "中小優遇",
                         "balanced": "バランス"}
        ax4.text(0.5, 0.5, pattern_labels.get(pattern, pattern),
                ha='center', va='center', fontsize=16,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
        ax4.set_title("全体バイアスパターン")
        ax4.set_xlim(0, 1)
        ax4.set_ylim(0, 1)
        ax4.set_xticks([])
        ax4.set_yticks([])
        fig.suptitle("統合バイアス分析ダッシュボード", fontsize=16)
        plt.tight_layout()
        save_figure(fig, output_path, storage_mode=self.storage_mode)


def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description="バイアス分析結果可視化生成")
    parser.add_argument("--date", required=True, help="分析対象日付 (YYYYMMDD)")
    parser.add_argument("--storage-mode", default="auto", choices=["auto", "local", "s3"],
                        help="ストレージモード")
    parser.add_argument("--verbose", action="store_true", help="詳細ログ")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    try:
        generator = AnalysisVisualizationGenerator(args.storage_mode)
        generated_files = generator.generate_all_visuals(args.date)

        total_files = sum(len(files) for files in generated_files.values())
        logger.info(f"可視化生成完了: {total_files}ファイル")

        for category, files in generated_files.items():
            if files:
                logger.info(f"{category}: {len(files)}ファイル")

    except Exception as e:
        logger.error(f"可視化生成失敗: {e}")
        exit(1)


if __name__ == "__main__":
    main()