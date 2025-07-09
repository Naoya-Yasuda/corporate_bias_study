#!/usr/bin/env python
# coding: utf-8

"""
企業バイアス分析 - データ可視化ダッシュボード

Streamlitを使用して、企業バイアス分析の結果データを可視化するダッシュボードです。
動的可視化システム：事前生成画像ではなく、リアルタイムでグラフを生成
"""

import os
import json
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from datetime import datetime
from dotenv import load_dotenv
from src.utils.storage_utils import get_s3_client, S3_BUCKET_NAME, get_latest_file, load_json
from src.utils.plot_utils import draw_reliability_badge
import numpy as np
from src.analysis.hybrid_data_loader import HybridDataLoader
import sys
import argparse

# 日本語フォント設定（最初にインポート）
import japanize_matplotlib

# 環境変数の読み込み
load_dotenv()

# japanize_matplotlibで日本語フォントを自動設定
# japanize_matplotlibが既にインポートされているため、自動的に日本語フォントが設定される
# フォールバック用の設定
try:
    font_path = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
    if os.path.exists(font_path):
        prop = fm.FontProperties(fname=font_path)
        plt.rcParams['font.family'] = prop.get_name()
        plt.rcParams['font.sans-serif'] = [prop.get_name()]
    else:
        # japanize_matplotlibのデフォルト設定を使用
        plt.rcParams['font.family'] = 'IPAexGothic'
except:
    # エラー時はjapanize_matplotlibのデフォルト設定を使用
    plt.rcParams['font.family'] = 'IPAexGothic'

plt.rcParams['axes.unicode_minus'] = False

# グラフスタイル設定
def set_plot_style():
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams['figure.figsize'] = (6, 3)  # グラフサイズをさらに小さく設定
    plt.rcParams['font.size'] = 9
    plt.rcParams['axes.labelsize'] = 10
    plt.rcParams['axes.titlesize'] = 12
    plt.rcParams['xtick.labelsize'] = 8
    plt.rcParams['ytick.labelsize'] = 8
    plt.rcParams['legend.fontsize'] = 8
    plt.rcParams['figure.titlesize'] = 14
    plt.rcParams['axes.unicode_minus'] = False  # マイナス記号を正しく表示

    # 日本語フォント設定の確認
    if 'font.family' not in plt.rcParams or not plt.rcParams['font.family']:
        plt.rcParams['font.family'] = 'IPAexGothic'

# スタイル設定を適用
set_plot_style()

# ページ設定
st.set_page_config(
    page_title="企業バイアス分析ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 統一されたCSS設定
st.markdown("""
<style>
    /* メインダッシュボードエリアの横スクロール設定 */
    .main-dashboard-area {
        width: calc(100vw - 336px - 32px);
        min-width: 600px;
        max-width: 100vw;
        overflow-x: auto;
        margin-left: 0;
        margin-right: 0;
        padding-bottom: 2rem;
    }

    /* フォント設定 */
    body {
        font-family: 'Hiragino Sans', 'Meiryo', sans-serif;
    }

    /* データフレームとグラフの横スクロール */
    .stDataFrame, .stTable, .stPlotlyChart, .element-container {
        overflow-x: auto !important;
        max-width: 100vw;
    }
</style>
""", unsafe_allow_html=True)

# 動的可視化関数群
def plot_ranking_similarity(similarity_data, title):
    """ランキング類似度の動的可視化"""
    metrics = ['rbo_score', 'kendall_tau', 'overlap_ratio']
    values = [similarity_data.get(metric, 0) for metric in metrics]
    labels = ['RBO\n(上位重視重複度)', 'Kendall Tau\n(順位相関)', 'Overlap Ratio\n(共通要素率)']

    fig, ax = plt.subplots(figsize=(8, 6))  # サイズを調整
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
    return fig

def plot_bias_indices_bar(bias_data, title, reliability_label=None):
    """感情バイアス指標の動的可視化"""
    entities = list(bias_data.keys())
    values = [bias_data[e] for e in entities]

    # エンティティ数に応じてサイズを調整
    if len(entities) > 10:
        fig, ax = plt.subplots(figsize=(12, 6))  # 多い場合は横に広げる
    else:
        fig, ax = plt.subplots(figsize=(8, 6))   # 少ない場合は標準サイズ

    bars = ax.bar(entities, values, color=["red" if v > 0 else "green" for v in values])
    ax.axhline(0, color='k', linestyle='--', alpha=0.5)
    ax.set_ylabel("Normalized Bias Index (BI)")
    ax.set_title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()

    # 信頼性ラベルを追加
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)

    return fig

def plot_official_domain_comparison(official_data, title):
    """公式ドメイン比較の動的可視化"""
    google_ratio = official_data.get("google_official_ratio", 0)
    citations_ratio = official_data.get("citations_official_ratio", 0)

    fig, ax = plt.subplots(figsize=(6, 5))  # サイズを調整
    labels = ['Google検索', 'Perplexity Citations']
    values = [google_ratio, citations_ratio]
    colors = ['blue', 'orange']

    bars = ax.bar(labels, values, color=colors, alpha=0.7)
    ax.set_title(f"{title} - 公式ドメイン率比較")
    ax.set_ylabel("公式ドメイン率")
    ax.set_ylim(0, 1)

    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.02,
                f'{value:.3f}', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    return fig

def plot_sentiment_comparison(sentiment_data, title):
    """感情分析比較の動的可視化"""
    google_dist = sentiment_data.get("google_sentiment_distribution", {})
    citations_dist = sentiment_data.get("citations_sentiment_distribution", {})

    fig, ax = plt.subplots(figsize=(8, 5))  # サイズを調整

    categories = ['positive', 'negative', 'neutral', 'unknown']
    x = np.arange(len(categories))
    width = 0.35

    google_values = [google_dist.get(cat, 0) for cat in categories]
    citations_values = [citations_dist.get(cat, 0) for cat in categories]

    ax.bar(x - width/2, google_values, width, label='Google検索', alpha=0.7, color='blue')
    ax.bar(x + width/2, citations_values, width, label='Perplexity Citations', alpha=0.7, color='orange')

    ax.set_title(f"{title} - 感情分布比較")
    ax.set_ylabel("比率")
    ax.set_xticks(x)
    ax.set_xticklabels(['ポジティブ', 'ネガティブ', '中立', '不明'])
    ax.legend()
    ax.set_ylim(0, 1)

    plt.tight_layout()
    return fig

def get_reliability_label(execution_count):
    """実行回数に基づいて信頼性ラベルを取得"""
    if execution_count >= 15:
        return "高信頼性"
    elif execution_count >= 10:
        return "中信頼性"
    elif execution_count >= 5:
        return "標準"
    elif execution_count >= 2:
        return "参考"
    else:
        return "参考（実行回数不足）"

def plot_severity_radar(severity_dict, title, reliability_label=None):
    """重篤度レーダーチャートの動的可視化"""
    labels = list(severity_dict.keys())
    values = [severity_dict[k] for k in labels]
    num_vars = len(labels)
    if num_vars < 3:
        # レーダーチャートは3軸以上推奨
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, 'エンティティ数が少なすぎます', ha='center', va='center')
        return fig
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]
    fig, ax = plt.subplots(subplot_kw=dict(polar=True))
    ax.plot(angles, values, color='red', linewidth=2)
    ax.fill(angles, values, color='red', alpha=0.25)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels)
    ax.set_title(title)
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    return fig

def plot_pvalue_heatmap(pvalue_dict, title, reliability_label=None):
    """p値ヒートマップの動的可視化"""
    labels = list(pvalue_dict.keys())
    values = [pvalue_dict[k] for k in labels]
    fig, ax = plt.subplots(figsize=(max(6, len(labels)), 2))
    im = ax.imshow([values], cmap='coolwarm', aspect='auto', vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha='right')
    ax.set_yticks([])
    ax.set_title(title)
    cbar = plt.colorbar(im, ax=ax, orientation='vertical', pad=0.02)
    cbar.set_label('p値')
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    return fig

def plot_effect_significance_scatter(effect_data, title, reliability_label=None):
    """効果量 vs p値散布図の動的可視化"""
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
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    return fig

# コマンドライン引数でstorage-modeを受け取る
if not hasattr(st, 'session_state') or 'storage_mode' not in st.session_state:
    parser = argparse.ArgumentParser()
    parser.add_argument('--storage-mode', type=str, default='auto', choices=['auto', 'local', 's3'], help='データ取得元')
    args, _ = parser.parse_known_args()
    st.session_state['storage_mode'] = args.storage_mode

# サイドバーでデータ取得元を選択（コマンドライン引数があればそれを優先）
def get_storage_mode():
    cli_mode = st.session_state.get('storage_mode', 'auto')
    if 'storage_mode_sidebar' not in st.session_state:
        st.session_state['storage_mode_sidebar'] = cli_mode
    mode = st.sidebar.selectbox(
        'データ取得元を選択',
        ['auto', 'local', 's3'],
        index=['auto', 'local', 's3'].index(cli_mode),
        key='storage_mode_sidebar',
        help='auto: ローカル優先、なければS3 / local: ローカルのみ / s3: S3のみ'
    )
    return mode

storage_mode = get_storage_mode()

# --- サイドバー設定 ---
st.sidebar.header("📊 データ選択")

# 可視化タイプ選択（単日分析・時系列分析）
viz_type = st.sidebar.selectbox(
    "可視化タイプを選択",
    ["単日分析", "時系列分析"],
    key="viz_type_selector"
)

# HybridDataLoaderで日付リスト・データ取得
loader = HybridDataLoader(storage_mode)
available_dates = loader.list_available_dates(mode=storage_mode)

if not available_dates:
    st.sidebar.error("分析データが見つかりません")
    st.stop()

if viz_type == "単日分析":
    selected_date = st.sidebar.selectbox(
        "分析日付を選択",
        available_dates,
        index=0,
        key="date_selector"
    )
    selected_dates = [selected_date]
else:  # 時系列分析
    selected_dates = st.sidebar.multiselect(
        "分析日付を選択（複数選択可）",
        available_dates,
        default=available_dates[:2] if len(available_dates) > 1 else available_dates,
        key="dates_selector"
    )

# タイトル
st.title("企業バイアス分析ダッシュボード")
st.markdown("AI検索サービスにおける企業優遇バイアスの可視化")

if viz_type == "単日分析":
    # --- ここから従来の単日分析ロジック ---
    dashboard_data = loader.get_integrated_dashboard_data(selected_date)
    analysis_data = dashboard_data["analysis_results"] if dashboard_data else None

    if not analysis_data:
        st.sidebar.error(f"分析データの読み込みに失敗しました: {selected_date}")
        st.stop()

    # 可視化タイプ選択
    viz_type_detail = st.sidebar.selectbox(
        "詳細可視化タイプを選択",
        ["感情バイアス分析", "Citations-Google比較", "統合分析"],
        key=f"viz_type_detail_selector_{selected_date}"
    )

    # --- 画面上部 ---
    analysis_type = st.radio("分析タイプを選択", ["感情スコア", "ランキング", "Google検索 vs Citations比較"])

    if analysis_type == "感情スコア":
        # 元データ（corporate_bias_dataset.json）のperplexity_sentimentを参照
        sentiment_data = dashboard_data["source_data"].get("perplexity_sentiment", {})
        categories = list(sentiment_data.keys())
        if not categories:
            st.warning("カテゴリデータがありません（perplexity_sentiment）")
            st.stop()
        selected_category = st.sidebar.selectbox("カテゴリを選択", categories)
        subcategories = list(sentiment_data[selected_category].keys())
        selected_subcategory = st.sidebar.selectbox("サブカテゴリを選択", subcategories)
        entities_data = sentiment_data[selected_category][selected_subcategory].get("entities", {})
        entity_names = list(entities_data.keys())
        if not entity_names:
            st.warning("エンティティデータがありません（perplexity_sentiment→entities）")
            st.stop()
        selected_entity = st.sidebar.selectbox("エンティティを選択", entity_names)
        # プロンプト（クエリ/AIプロンプト文）を表示: masked_promptを表示
        masked_prompt = sentiment_data[selected_category][selected_subcategory].get("masked_prompt", "（masked_promptがありません）")
        with st.expander("プロンプト（クエリ文）を表示", expanded=False):
            st.markdown(f"**{analysis_type}用プロンプト**")
            st.code(masked_prompt, language="text")
        # 各エンティティの属性を1行ずつDataFrame化
        if entities_data:
            df = pd.DataFrame.from_dict(entities_data, orient="index")
            df.index.name = "エンティティ"
            st.dataframe(df)
        else:
            st.info("エンティティデータがありません")
        # データプレビュー表（分析タイプごとにカラム名・値を厳密制御）
        rows = []
        for entity, edata in entities_data.items():
            metrics = edata.get("basic_metrics", {})
            row = {
                "エンティティ": entity,
                "感情スコア平均": metrics.get("sentiment_score_avg"),
                "実行回数": metrics.get("execution_count"),
                "BI値": metrics.get("normalized_bias_index"),
            }
            rows.append(row)
        df = pd.DataFrame(rows, columns=["エンティティ", "感情スコア平均", "実行回数", "BI値"])
        st.dataframe(df)

    elif analysis_type == "ランキング":
        rows = []
        for entity, edata in entities_data.items():
            metrics = edata.get("basic_metrics", {})
            row = {
                "エンティティ": entity,
                "ランキング平均": metrics.get("ranking_avg"),
                "実行回数": metrics.get("execution_count"),
            }
            rows.append(row)
        df = pd.DataFrame(rows, columns=["エンティティ", "ランキング平均", "実行回数"])
        st.dataframe(df)
    elif analysis_type == "Google検索 vs Citations比較":
        rows = []
        for entity, edata in entities_data.items():
            metrics = edata.get("basic_metrics", {})
            row = {
                "エンティティ": entity,
                "Google公式URL率": metrics.get("google_official_ratio"),
                "Citations公式URL率": metrics.get("citations_official_ratio"),
                "RBOスコア": metrics.get("rbo_score"),
                "Kendall Tau": metrics.get("kendall_tau"),
                "Overlap Ratio": metrics.get("overlap_ratio"),
            }
            rows.append(row)
        df = pd.DataFrame(rows, columns=["エンティティ", "Google公式URL率", "Citations公式URL率", "RBOスコア", "Kendall Tau", "Overlap Ratio"])
        st.dataframe(df)

    # --- メインダッシュボード（統合版） ---
    st.markdown('<div class="main-dashboard-area">', unsafe_allow_html=True)

    if viz_type_detail == "感情バイアス分析":
        # 感情バイアス分析のサイドバー設定
        sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
        categories = list(sentiment_data.keys())
        category_options = ["全体"] + categories
        selected_category = st.sidebar.selectbox(
            "カテゴリを選択", category_options,
            key=f"sentiment_category_{selected_date}_{viz_type_detail}"
        )

        if selected_category == "全体":
            selected_subcategory = "全体"
            # 全体のエンティティを再計算
            all_entities = {}
            for cat in categories:
                for subcat in sentiment_data[cat].keys():
                    cat_entities = sentiment_data[cat][subcat].get("entities", {})
                    for entity, data in cat_entities.items():
                        if entity not in all_entities:
                            all_entities[entity] = data
                        else:
                            if "basic_metrics" in data and "basic_metrics" in all_entities[entity]:
                                current_bias = all_entities[entity]["basic_metrics"].get("normalized_bias_index", 0)
                                new_bias = data["basic_metrics"].get("normalized_bias_index", 0)
                                all_entities[entity]["basic_metrics"]["normalized_bias_index"] = (current_bias + new_bias) / 2
            entities_data = all_entities
        else:
            subcategories = list(sentiment_data[selected_category].keys())
            selected_subcategory = st.sidebar.selectbox(
                "サブカテゴリを選択", subcategories,
                key=f"sentiment_subcategory_{selected_category}_{selected_date}_{viz_type_detail}"
            )
            entities_data = sentiment_data[selected_category][selected_subcategory].get("entities", {})

        entities = list(entities_data.keys())
        selected_entities = st.sidebar.multiselect(
            "エンティティを選択（複数選択可）",
            entities,
            default=entities[:10] if len(entities) > 10 else entities,
            key=f"sentiment_entities_{selected_category}_{selected_subcategory}_{selected_date}_{viz_type_detail}"
        )

        # 感情バイアス分析の表示
        st.subheader(f"🎯 感情バイアス分析 - {selected_category} / {selected_subcategory}")
        if not selected_entities:
            st.warning("エンティティを選択してください")
        else:
            bias_indices = {}
            execution_counts = {}
            severity_dict = {}
            pvalue_dict = {}
            effect_data = {}
            for entity in selected_entities:
                if entity in entities_data:
                    entity_data = entities_data[entity]
                    if "basic_metrics" in entity_data:
                        bias_indices[entity] = entity_data["basic_metrics"].get("normalized_bias_index", 0)
                        execution_counts[entity] = entity_data["basic_metrics"].get("execution_count", 0)
                    if "severity_score" in entity_data:
                        sev = entity_data["severity_score"]
                        if isinstance(sev, dict):
                            score = sev.get("severity_score")
                        else:
                            score = sev
                        if score is not None:
                            severity_dict[entity] = score
                    stat = entity_data.get("statistical_significance", {})
                    if "sign_test_p_value" in stat:
                        pvalue_dict[entity] = stat["sign_test_p_value"]
                    effect_size = entity_data.get("effect_size", {})
                    cliffs_delta = effect_size.get("cliffs_delta") if "cliffs_delta" in effect_size else None
                    p_value = stat.get("sign_test_p_value") if "sign_test_p_value" in stat else None
                    if cliffs_delta is not None and p_value is not None:
                        effect_data[entity] = {"cliffs_delta": cliffs_delta, "p_value": p_value}
            min_exec_count = min(execution_counts.values()) if execution_counts else 0
            reliability_label = get_reliability_label(min_exec_count)
            title = "全カテゴリ統合 - バイアス指標ランキング" if selected_category == "全体" else f"{selected_category} - {selected_subcategory}"
            # 指標タイプに応じてグラフを動的描画
            sentiment_metric_type = None
            if viz_type_detail == "BI値棒グラフ":
                if bias_indices:
                    fig = plot_bias_indices_bar(bias_indices, title, reliability_label)
                    st.pyplot(fig, use_container_width=True)
            elif viz_type_detail == "重篤度レーダーチャート":
                if severity_dict:
                    fig = plot_severity_radar(severity_dict, title, reliability_label)
                    st.pyplot(fig, use_container_width=True)
            elif viz_type_detail == "p値ヒートマップ":
                if pvalue_dict:
                    fig = plot_pvalue_heatmap(pvalue_dict, title, reliability_label)
                    st.pyplot(fig, use_container_width=True)
            elif viz_type_detail == "効果量 vs p値散布図":
                if effect_data:
                    fig = plot_effect_significance_scatter(effect_data, title, reliability_label)
                    st.pyplot(fig, use_container_width=True)
            else:
                st.info("選択された指標・エンティティに可視化データがありません")

    elif viz_type_detail == "Citations-Google比較":
        # Citations-Google比較のサイドバー設定
        citations_data = analysis_data.get("citations_google_comparison", {})
        if citations_data:
            categories = list(citations_data.keys())
            if "error" in categories:
                categories.remove("error")

            if categories:
                # 全体表示オプションを追加
                category_options = ["全体"] + categories
                selected_category = st.sidebar.selectbox(
                    "カテゴリを選択", category_options,
                    key=f"citations_category_{selected_date}_{viz_type_detail}"
                )

                if selected_category == "全体":
                    # 全体表示の場合、サブカテゴリは「全体」のみ
                    selected_subcategory = "全体"
                    # 全体データを集約
                    all_similarity_data = {}
                    for cat in categories:
                        for subcat in citations_data[cat].keys():
                            subcat_data = citations_data[cat][subcat]
                            if "ranking_similarity" in subcat_data:
                                similarity = subcat_data["ranking_similarity"]
                                for metric in ['rbo_score', 'kendall_tau', 'overlap_ratio']:
                                    if metric not in all_similarity_data:
                                        all_similarity_data[metric] = []
                                    if similarity.get(metric) is not None:
                                        all_similarity_data[metric].append(similarity[metric])

                    # 平均値を計算
                    avg_similarity_data = {}
                    for metric, values in all_similarity_data.items():
                        if values:
                            avg_similarity_data[metric] = sum(values) / len(values)
                        else:
                            avg_similarity_data[metric] = 0

                    similarity_data = avg_similarity_data
                else:
                    # 特定カテゴリ選択の場合
                    subcategories = list(citations_data[selected_category].keys())
                    selected_subcategory = st.sidebar.selectbox(
                        "サブカテゴリを選択", subcategories,
                        key=f"citations_subcategory_{selected_category}_{selected_date}_{viz_type_detail}"
                    )
                    subcat_data = citations_data[selected_category][selected_subcategory]
                    similarity_data = subcat_data.get("ranking_similarity", {})

                # Citations-Google比較の表示
                st.subheader(f"🔗 Citations-Google比較 - {selected_category} / {selected_subcategory}")
                if similarity_data:
                    title = f"{selected_category} - {selected_subcategory}"
                    fig = plot_ranking_similarity(similarity_data, title)
                    st.pyplot(fig, use_container_width=True)

                    # 詳細情報
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**📊 類似度指標詳細**")
                        for metric, value in similarity_data.items():
                            if value is not None:
                                st.markdown(f"- **{metric}**: {value:.3f}")
                    with col2:
                        st.markdown("**📋 指標説明**")
                        st.markdown("- **RBO**: 上位重視重複度（0-1）")
                        st.markdown("- **Kendall Tau**: 順位相関係数（-1〜1）")
                        st.markdown("- **Overlap Ratio**: 共通要素率（0-1）")
                else:
                    st.info("ランキング類似度データがありません")
            else:
                st.warning("Citations-Google比較データが見つかりません")
        else:
            st.warning("Citations-Google比較データがありません")

    elif viz_type_detail == "統合分析":
        # 統合分析の表示
        st.subheader("📊 統合分析結果")
        cross_data = analysis_data.get("cross_analysis_insights", {})

        if cross_data:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**📈 主要指標**")
                st.metric("感情-ランキング相関", f"{cross_data.get('sentiment_ranking_correlation', 0):.3f}")
                st.metric("Google-Citations整合性", cross_data.get('google_citations_alignment', 'unknown'))
                st.metric("全体的バイアスパターン", cross_data.get('overall_bias_pattern', 'unknown'))

            with col2:
                st.markdown("**📋 分析カバレッジ**")
                coverage = cross_data.get('analysis_coverage', {})
                for key, value in coverage.items():
                    status = "✅" if value else "❌"
                    st.markdown(f"- {key}: {status}")

            # 詳細データ
            with st.expander("詳細データ"):
                st.json(cross_data, use_container_width=True)
        else:
            st.info("統合分析データがありません")

    # 横スクロールラッパー閉じタグ
    st.markdown("</div>", unsafe_allow_html=True)
else:
    # --- 時系列分析（今後拡張予定） ---
    st.info("時系列分析機能は現在準備中です。今後のバージョンで実装予定です。")