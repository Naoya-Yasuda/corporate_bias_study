#!/usr/bin/env python
# coding: utf-8

"""
バイアス分析結果可視化生成スクリプト

bias_analysis_engine.pyの出力JSONから画像を一括生成します。
"""

import os
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
    plot_exposure_market
)
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_utils import ensure_directory_exists

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

        # 出力ディレクトリの設定
        self.output_base_dir = "corporate_bias_datasets/analysis_visuals"
        ensure_directory_exists(self.output_base_dir)

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
            ensure_directory_exists(str(output_dir))

            generated_files = {
                "sentiment_bias": [],
                "ranking_analysis": [],
                "citations_comparison": [],
                "relative_bias": [],
                "cross_analysis": []
            }

            # 1. 感情バイアス可視化
            sentiment_files = self._generate_sentiment_bias_visuals(
                analysis_results.get("sentiment_bias_analysis", {}),
                output_dir / "sentiment_bias"
            )
            generated_files["sentiment_bias"].extend(sentiment_files)

            # 2. ランキング分析可視化
            ranking_files = self._generate_ranking_analysis_visuals(
                analysis_results.get("ranking_bias_analysis", {}),
                output_dir / "ranking_analysis"
            )
            generated_files["ranking_analysis"].extend(ranking_files)

            # 3. Citations-Google比較可視化
            citations_files = self._generate_citations_comparison_visuals(
                analysis_results.get("citations_google_comparison", {}),
                output_dir / "citations_comparison"
            )
            generated_files["citations_comparison"].extend(citations_files)

            # 4. 相対バイアス可視化
            relative_files = self._generate_relative_bias_visuals(
                analysis_results.get("relative_bias_analysis", {}),
                output_dir / "relative_bias"
            )
            generated_files["relative_bias"].extend(relative_files)

            # 5. 統合分析サマリー可視化
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

    def _generate_sentiment_bias_visuals(self, sentiment_data: Dict, output_dir: Path) -> List[str]:
        """感情バイアス可視化を生成"""
        ensure_directory_exists(str(output_dir))
        generated_files = []

        for category, subcategories in sentiment_data.items():
            for subcategory, data in subcategories.items():
                if "entities" not in data:
                    continue

                entities = data["entities"]

                # バイアス指標棒グラフ
                bias_indices = {}
                for entity_name, entity_data in entities.items():
                    bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)
                    bias_indices[entity_name] = bi

                if bias_indices:
                    output_path = output_dir / f"{category}_{subcategory}_bias_indices.png"
                    self._plot_bias_indices_bar(bias_indices, str(output_path), f"{category} - {subcategory}")
                    generated_files.append(str(output_path))

                # 効果量散布図
                effect_data = {}
                for entity_name, entity_data in entities.items():
                    cliffs_delta = entity_data.get("effect_size", {}).get("cliffs_delta")
                    p_value = entity_data.get("statistical_significance", {}).get("sign_test_p_value")
                    if cliffs_delta is not None and p_value is not None:
                        effect_data[entity_name] = {"cliffs_delta": cliffs_delta, "p_value": p_value}

                if effect_data:
                    output_path = output_dir / f"{category}_{subcategory}_effect_significance.png"
                    self._plot_effect_significance_scatter(effect_data, str(output_path), f"{category} - {subcategory}")
                    generated_files.append(str(output_path))

        return generated_files

    def _generate_ranking_analysis_visuals(self, ranking_data: Dict, output_dir: Path) -> List[str]:
        """ランキング分析可視化を生成"""
        ensure_directory_exists(str(output_dir))
        generated_files = []

        for category, subcategories in ranking_data.items():
            for subcategory, data in subcategories.items():
                category_summary = data.get("category_summary", {})

                # ランキング安定性可視化
                stability_analysis = category_summary.get("stability_analysis", {})
                if stability_analysis.get("rank_variance"):
                    output_path = output_dir / f"{category}_{subcategory}_ranking_stability.png"
                    self._plot_ranking_stability(stability_analysis["rank_variance"], str(output_path), f"{category} - {subcategory}")
                    generated_files.append(str(output_path))

        return generated_files

    def _generate_citations_comparison_visuals(self, citations_data: Dict, output_dir: Path) -> List[str]:
        """Citations-Google比較可視化を生成"""
        ensure_directory_exists(str(output_dir))
        generated_files = []

        for category, subcategories in citations_data.items():
            if category == "error":
                continue

            for subcategory, data in subcategories.items():
                ranking_similarity = data.get("ranking_similarity", {})

                # ランキング類似度可視化
                if ranking_similarity:
                    output_path = output_dir / f"{category}_{subcategory}_ranking_similarity.png"
                    self._plot_ranking_similarity(ranking_similarity, str(output_path), f"{category} - {subcategory}")
                    generated_files.append(str(output_path))

        return generated_files

    def _generate_relative_bias_visuals(self, relative_data: Dict, output_dir: Path) -> List[str]:
        """相対バイアス可視化を生成"""
        ensure_directory_exists(str(output_dir))
        generated_files = []

        for category, subcategories in relative_data.items():
            if category == "overall_summary":
                continue

            for subcategory, data in subcategories.items():
                # バイアス不平等度可視化
                bias_inequality = data.get("bias_inequality", {})
                if bias_inequality and "gini_coefficient" in bias_inequality:
                    output_path = output_dir / f"{category}_{subcategory}_bias_inequality.png"
                    self._plot_bias_inequality(bias_inequality, str(output_path), f"{category} - {subcategory}")
                    generated_files.append(str(output_path))

                # 企業優遇度可視化
                enterprise_favoritism = data.get("enterprise_favoritism", {})
                if enterprise_favoritism and "favoritism_gap" in enterprise_favoritism:
                    output_path = output_dir / f"{category}_{subcategory}_enterprise_favoritism.png"
                    self._plot_enterprise_favoritism(enterprise_favoritism, str(output_path), f"{category} - {subcategory}")
                    generated_files.append(str(output_path))

        return generated_files

    def _generate_summary_visuals(self, analysis_results: Dict, output_dir: Path) -> List[str]:
        """統合分析サマリー可視化を生成"""
        ensure_directory_exists(str(output_dir))
        generated_files = []

        # 全体サマリーダッシュボード
        cross_analysis = analysis_results.get("cross_analysis_insights", {})
        if cross_analysis:
            output_path = output_dir / "cross_analysis_dashboard.png"
            self._plot_cross_analysis_dashboard(cross_analysis, str(output_path))
            generated_files.append(str(output_path))

        return generated_files

    def _plot_bias_indices_bar(self, bias_indices: Dict, output_path: str, title: str):
        """バイアス指標棒グラフ"""
        import matplotlib.pyplot as plt
        import numpy as np

        entities = list(bias_indices.keys())
        values = list(bias_indices.values())

        fig, ax = plt.subplots(figsize=(12, 6))
        colors = ['red' if v > 0 else 'blue' if v < 0 else 'gray' for v in values]

        bars = ax.bar(entities, values, color=colors, alpha=0.7)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax.set_title(f"{title} - バイアス指標", fontsize=14)
        ax.set_ylabel("バイアス指標")
        ax.tick_params(axis='x', rotation=45)

        # 値をバーの上に表示
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{value:.3f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_effect_significance_scatter(self, effect_data: Dict, output_path: str, title: str):
        """効果量-有意性散布図"""
        import matplotlib.pyplot as plt

        entities = list(effect_data.keys())
        cliffs_deltas = [data["cliffs_delta"] for data in effect_data.values()]
        p_values = [data["p_value"] for data in effect_data.values()]

        fig, ax = plt.subplots(figsize=(10, 8))

        # 有意性による色分け
        colors = ['red' if p < 0.05 else 'gray' for p in p_values]

        scatter = ax.scatter(cliffs_deltas, [-np.log10(p) for p in p_values],
                           c=colors, alpha=0.7, s=100)

        # 有意性ライン
        ax.axhline(y=-np.log10(0.05), color='red', linestyle='--', alpha=0.5, label='p=0.05')

        # 効果量境界
        ax.axvline(x=0.147, color='blue', linestyle='--', alpha=0.5, label='小効果量')
        ax.axvline(x=0.33, color='orange', linestyle='--', alpha=0.5, label='中効果量')
        ax.axvline(x=0.474, color='green', linestyle='--', alpha=0.5, label='大効果量')

        # 企業名ラベル
        for i, entity in enumerate(entities):
            ax.annotate(entity, (cliffs_deltas[i], -np.log10(p_values[i])),
                       xytext=(5, 5), textcoords='offset points', fontsize=8)

        ax.set_xlabel("Cliff's Delta (効果量)")
        ax.set_ylabel("-log10(p値)")
        ax.set_title(f"{title} - 効果量と統計的有意性")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_ranking_stability(self, rank_variance: Dict, output_path: str, title: str):
        """ランキング安定性可視化"""
        import matplotlib.pyplot as plt

        entities = list(rank_variance.keys())
        stds = [data["rank_std"] for data in rank_variance.values()]
        ranges = [data["rank_range"] for data in rank_variance.values()]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # 標準偏差
        ax1.bar(entities, stds, alpha=0.7, color='blue')
        ax1.set_title("順位の標準偏差")
        ax1.set_ylabel("標準偏差")
        ax1.tick_params(axis='x', rotation=45)

        # 順位範囲
        ax2.bar(entities, ranges, alpha=0.7, color='orange')
        ax2.set_title("順位の範囲")
        ax2.set_ylabel("範囲（最大-最小）")
        ax2.tick_params(axis='x', rotation=45)

        fig.suptitle(f"{title} - ランキング安定性", fontsize=14)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_ranking_similarity(self, similarity_data: Dict, output_path: str, title: str):
        """ランキング類似度可視化"""
        import matplotlib.pyplot as plt

        metrics = ['rbo_score', 'kendall_tau', 'overlap_ratio']
        values = [similarity_data.get(metric, 0) for metric in metrics]
        labels = ['RBO', 'Kendall Tau', 'Overlap Ratio']

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(labels, values, alpha=0.7, color=['blue', 'orange', 'green'])
        ax.set_title(f"{title} - Google vs Perplexity類似度")
        ax.set_ylabel("類似度スコア")
        ax.set_ylim(0, 1)

        # 値をバーの上に表示
        for bar, value in zip(bars, values):
            if value is not None:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.02,
                        f'{value:.3f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_bias_inequality(self, inequality_data: Dict, output_path: str, title: str):
        """バイアス不平等度可視化"""
        import matplotlib.pyplot as plt

        gini = inequality_data.get("gini_coefficient", 0)
        std_dev = inequality_data.get("std_deviation", 0)
        bias_range = inequality_data.get("bias_range", 0)

        metrics = ['Gini係数', '標準偏差', 'バイアス範囲']
        values = [gini, std_dev, bias_range]

        fig, ax = plt.subplots(figsize=(8, 6))

        bars = ax.bar(metrics, values, alpha=0.7, color=['red', 'orange', 'blue'])
        ax.set_title(f"{title} - バイアス不平等度")
        ax.set_ylabel("値")

        # 値をバーの上に表示
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.01,
                    f'{value:.3f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_enterprise_favoritism(self, favoritism_data: Dict, output_path: str, title: str):
        """企業優遇度可視化"""
        import matplotlib.pyplot as plt

        large_avg = favoritism_data.get("large_enterprise_avg_bias", 0)
        small_avg = favoritism_data.get("small_enterprise_avg_bias", 0)
        gap = favoritism_data.get("favoritism_gap", 0)

        categories = ['大企業', '中小企業']
        values = [large_avg, small_avg]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # 平均バイアス
        colors = ['red' if v > 0 else 'blue' for v in values]
        ax1.bar(categories, values, color=colors, alpha=0.7)
        ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax1.set_title("企業規模別平均バイアス")
        ax1.set_ylabel("平均バイアス指標")

        # 優遇格差
        ax2.bar(['優遇格差'], [gap], color='orange', alpha=0.7)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_title("優遇格差")
        ax2.set_ylabel("格差（大企業 - 中小企業）")

        fig.suptitle(f"{title} - 企業規模優遇度", fontsize=14)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

    def _plot_cross_analysis_dashboard(self, cross_analysis: Dict, output_path: str):
        """統合分析ダッシュボード"""
        import matplotlib.pyplot as plt
        import numpy as np

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        # 1. 感情-ランキング相関
        correlation = cross_analysis.get("sentiment_ranking_correlation", 0)
        ax1.bar(['相関'], [correlation], color='blue', alpha=0.7)
        ax1.set_title("感情-ランキング相関")
        ax1.set_ylabel("相関係数")
        ax1.set_ylim(-1, 1)

        # 2. 一貫性リーダー/ラガード
        leaders = cross_analysis.get("consistent_leaders", [])
        laggards = cross_analysis.get("consistent_laggards", [])

        ax2.bar(['リーダー', 'ラガード'], [len(leaders), len(laggards)],
                color=['green', 'red'], alpha=0.7)
        ax2.set_title("一貫性企業数")
        ax2.set_ylabel("企業数")

        # 3. Google-Citations整合性
        alignment = cross_analysis.get("google_citations_alignment", "unknown")
        alignment_score = {"high": 3, "moderate": 2, "low": 1, "unknown": 0}.get(alignment, 0)

        ax3.bar(['整合性'], [alignment_score], color='orange', alpha=0.7)
        ax3.set_title("Google-Citations整合性")
        ax3.set_ylabel("整合性レベル")
        ax3.set_ylim(0, 3)

        # 4. 全体バイアスパターン
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
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()


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