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
import sys
import traceback

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
    plot_cross_category_severity_ranking
)
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_utils import ensure_dir, save_figure
from src.analysis.bias_analysis_engine import ReliabilityChecker
from src.utils.storage_config import get_base_paths

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
        # self.output_base_dir = "corporate_bias_datasets/analysis_visuals"  # 不要なので削除
        # ensure_dir(self.output_base_dir)  # 不要なので削除

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
            output_dir = Path(get_base_paths(date_or_path)["analysis_visuals"]) / date_or_path
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
        try:
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
                        if isinstance(score, dict):
                            score = None
                        if score is not None and isinstance(score, (int, float)):
                            severity_list.append({
                                "entity": entity,
                                "category": category,
                                "subcategory": subcategory,
                                "severity_score": sev
                            })
        except Exception as e:
            logger.error(f"[ERROR] sentiment_dataループで例外: {e}")
            logger.error(f"[ERROR] sentiment_data: {sentiment_data}")
            logger.error(f"[ERROR] sentiment_data type: {type(sentiment_data)}")
            raise
        if severity_list:
            exec_counts = []
            for category, subcategories in sentiment_data.items():
                for subcategory, data in subcategories.items():
                    entities = data.get("entities", {})
                    for entity, entity_data in entities.items():
                        exec_count = entity_data.get("basic_metrics", {}).get("execution_count", 1)
                        if isinstance(exec_count, (int, float)):
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
                    # int/float型のみappend
                    if isinstance(exec_count, (int, float)):
                        category_exec_counts.append(exec_count)
                    if entity_data.get("severity_score") is None:
                        category_fail_counts.append(1)
                    else:
                        category_fail_counts.append(0)
        total_calculations = len(category_exec_counts)
        successful_calculations = total_calculations - sum(category_fail_counts)
        warnings = {}
        if isinstance(data_availability_summary, dict):
            for k, v in data_availability_summary.items():
                if isinstance(v, (int, float)) and v < 1.0:
                    warnings[k] = warnings.get(k, 0) + 1
        if isinstance(analysis_limitations, list):
            warnings["制限事項"] = len(analysis_limitations)
        # 品質管理ダッシュボードは削除済みのため、処理をスキップ
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

        # 日本語フォント設定（警告の出るフォントはコメントアウト）
        plt.rcParams['font.family'] = [
            #'IPAexGothic',  # 警告あり
            'Hiragino Sans',
            #'Yu Gothic',     # 警告あり
            #'Meiryo',       # 警告あり
            #'Takao',        # 警告あり
            #'IPAPGothic',   # 警告あり
            #'VL PGothic',   # 警告あり
            'Noto Sans CJK JP'
        ]

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

        # 日本語フォント設定
        plt.rcParams['font.family'] = ['Hiragino Sans', 'Noto Sans CJK JP']

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 14))

        # 1. 感情-ランキング相関（改善版）
        correlation_data = cross_analysis.get("sentiment_ranking_correlation", {})
        if isinstance(correlation_data, dict) and correlation_data:
            # 全カテゴリ・サブカテゴリから相関値を抽出
            correlations = []
            for category_data in correlation_data.values():
                if isinstance(category_data, dict):
                    for subcategory_data in category_data.values():
                        if isinstance(subcategory_data, dict):
                            # correlationキーを優先し、pearson_correlationキーもフォールバックとして使用
                            pearson_corr = subcategory_data.get("correlation") or subcategory_data.get("pearson_correlation")
                            if pearson_corr is not None:
                                correlations.append(pearson_corr)

            if correlations:
                avg_correlation = np.mean(correlations)
                ax1.bar(['平均相関'], [avg_correlation], color='blue', alpha=0.7)
                # 数値表示
                ax1.text(0, avg_correlation + 0.05 if avg_correlation >= 0 else avg_correlation - 0.05,
                        f'{avg_correlation:.3f}', ha='center', va='bottom' if avg_correlation >= 0 else 'top',
                        fontweight='bold', fontsize=12)
                ax1.axhline(0, color='k', linestyle='--', alpha=0.3)
                ax1.set_ylim(-1, 1)
            else:
                ax1.text(0.5, 0.5, 'データ不足', ha='center', va='center',
                        fontsize=14, color='gray',
                        transform=ax1.transAxes)
                ax1.set_ylim(0, 1)
        else:
            ax1.text(0.5, 0.5, 'データ不足', ha='center', va='center',
                    fontsize=14, color='gray',
                    transform=ax1.transAxes)
            ax1.set_ylim(0, 1)

        ax1.set_title("感情-ランキング相関", fontsize=14, fontweight='bold')
        ax1.set_ylabel("相関係数")
        ax1.grid(axis='y', alpha=0.3)

        # 2. 一貫性企業数（改善版）
        leaders = cross_analysis.get("consistent_leaders", [])
        laggards = cross_analysis.get("consistent_laggards", [])

        if leaders or laggards:
            counts = [len(leaders), len(laggards)]
            bars = ax2.bar(['リーダー', 'ラガード'], counts,
                          color=['#28a745', '#dc3545'], alpha=0.8)

            # 数値表示と企業名表示
            for i, (bar, count, entities) in enumerate(zip(bars, counts, [leaders, laggards])):
                if count > 0:
                    ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                            f'{count}社', ha='center', va='bottom',
                            fontweight='bold', fontsize=11)

                    # 企業名をリスト表示（最大3社まで）
                    if entities:
                        entity_text = ', '.join(entities[:3])
                        if len(entities) > 3:
                            entity_text += f"他{len(entities)-3}社"
                        ax2.text(bar.get_x() + bar.get_width()/2., bar.get_height()/2,
                                entity_text, ha='center', va='center',
                                fontsize=9, wrap=True)
        else:
            ax2.text(0.5, 0.5, 'データ不足', ha='center', va='center',
                    fontsize=14, color='gray',
                    transform=ax2.transAxes)

        ax2.set_title("一貫性企業数", fontsize=14, fontweight='bold')
        ax2.set_ylabel("企業数")
        ax2.grid(axis='y', alpha=0.3)

        # 3. Google-Citations整合性（改善版）
        alignment = cross_analysis.get("google_citations_alignment", "unknown")
        alignment_mapping = {
            "high": {"score": 3, "color": "#28a745", "label": "高"},
            "moderate": {"score": 2, "color": "#ffc107", "label": "中"},
            "low": {"score": 1, "color": "#dc3545", "label": "低"},
            "unknown": {"score": 0, "color": "#6c757d", "label": "不明"}
        }

        alignment_info = alignment_mapping.get(alignment, alignment_mapping["unknown"])

        if alignment_info["score"] > 0:
            bar = ax3.bar(['整合性'], [alignment_info["score"]],
                         color=alignment_info["color"], alpha=0.8)
            ax3.text(0, alignment_info["score"] + 0.1,
                    alignment_info["label"], ha='center', va='bottom',
                    fontweight='bold', fontsize=12)
        else:
            ax3.text(0.5, 0.5, 'データ不足', ha='center', va='center',
                    fontsize=14, color='gray',
                    transform=ax3.transAxes)

        ax3.set_title("Google-Citations整合性", fontsize=14, fontweight='bold')
        ax3.set_ylabel("整合性レベル")
        ax3.set_ylim(0, 3.5)
        ax3.grid(axis='y', alpha=0.3)

        # 4. 全体バイアスパターン（改善版）
        pattern = cross_analysis.get("overall_bias_pattern", "balanced")

        pattern_mapping = {
            "strong_large_enterprise_favoritism": {"label": "強い大企業優遇", "color": "#dc3545"},
            "moderate_large_enterprise_favoritism": {"label": "中程度大企業優遇", "color": "#fd7e14"},
            "strong_small_enterprise_favoritism": {"label": "強い中小優遇", "color": "#20c997"},
            "moderate_small_enterprise_favoritism": {"label": "中程度中小優遇", "color": "#17a2b8"},
            "balanced": {"label": "バランス", "color": "#28a745"},
            "large_enterprise_dominance": {"label": "大企業支配", "color": "#6f42c1"},
            "small_enterprise_dominance": {"label": "中小企業支配", "color": "#e83e8c"},
            "mixed_pattern": {"label": "混合パターン", "color": "#6c757d"},
            "unknown": {"label": "不明", "color": "#adb5bd"}
        }

        pattern_info = pattern_mapping.get(pattern, pattern_mapping.get("unknown"))

        ax4.text(0.5, 0.5, pattern_info["label"],
                ha='center', va='center', fontsize=14, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.5", facecolor=pattern_info["color"], alpha=0.7, edgecolor='black'))
        ax4.set_title("全体バイアスパターン", fontsize=14, fontweight='bold')
        ax4.set_xlim(0, 1)
        ax4.set_ylim(0, 1)
        ax4.set_xticks([])
        ax4.set_yticks([])

        # 全体タイトルと調整
        fig.suptitle("統合バイアス分析ダッシュボード", fontsize=18, fontweight='bold', y=0.95)
        plt.tight_layout(rect=[0, 0, 1, 0.93])
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
    try:
        main()
    except Exception as e:
        print(f"[FATAL ERROR] {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise