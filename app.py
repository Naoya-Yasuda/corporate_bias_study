#!/usr/bin/env python
# coding: utf-8

"""
企業バイアス分析 - データ可視化ダッシュボード

Streamlitを使用して、企業バイアス分析の結果データを可視化するダッシュボードです。
動的可視化システム：事前生成画像ではなく、リアルタイムでグラフを生成
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from src.utils.plot_utils import draw_reliability_badge
import numpy as np
from src.analysis.hybrid_data_loader import HybridDataLoader
import japanize_matplotlib

# 環境変数の読み込み
# load_dotenv() # 削除

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
    # 日本語フォントを複数指定
    plt.rcParams['font.family'] = ['IPAexGothic', 'Noto Sans CJK JP', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAPGothic', 'VL PGothic', 'DejaVu Sans']

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
# （main-dashboard-areaやstDataFrame等のカスタムCSSは削除）

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
    # parser = argparse.ArgumentParser() # 削除
    # parser.add_argument('--storage-mode', type=str, default='auto', choices=['auto', 'local', 's3'], help='データ取得元') # 削除
    # args, _ = parser.parse_known_args() # 削除
    st.session_state['storage_mode'] = 'auto' # デフォルト値を設定

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

# --- データ取得元「auto」時のlocal/S3両方候補リスト表示 ---
if storage_mode == "auto":
    loader_local = HybridDataLoader("local")
    loader_s3 = HybridDataLoader("s3")
    dates_local = set(loader_local.list_available_dates(mode="local"))
    dates_s3 = set(loader_s3.list_available_dates(mode="s3"))
    all_dates = sorted(list(dates_local | dates_s3), reverse=True)
    date_source_options = []
    for d in all_dates:
        if d in dates_local:
            date_source_options.append(f"local: {d}")
        if d in dates_s3:
            date_source_options.append(f"S3: {d}")
    if not date_source_options:
        st.sidebar.error("分析データが見つかりません")
        st.stop()
    selected_date_source = st.sidebar.selectbox(
        "分析日付と取得元を選択",
        date_source_options,
        index=0,
        key="date_source_selector"
    )
    # 選択に応じてloaderとdateを決定
    if selected_date_source.startswith("local: "):
        loader = loader_local
        selected_date = selected_date_source.replace("local: ", "")
    else:
        loader = loader_s3
        selected_date = selected_date_source.replace("S3: ", "")
    selected_dates = [selected_date]
else:
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
    dashboard_data = loader.get_integrated_dashboard_data(selected_date)
    analysis_data = dashboard_data["analysis_results"] if dashboard_data else None

    if not analysis_data:
        st.sidebar.error(f"分析データの読み込みに失敗しました: {selected_date}")
        st.stop()

    # --- 詳細可視化タイプ選択（おすすめランキング分析結果を統合） ---
    viz_type_detail = st.sidebar.selectbox(
        "詳細可視化タイプを選択",
        ["感情スコア分析", "Citations-Google比較", "統合分析", "おすすめランキング分析結果"],
        key=f"viz_type_detail_selector_{selected_date}"
    )

    # --- メインダッシュボード（統合版） ---
    st.markdown('<div class="main-dashboard-area">', unsafe_allow_html=True)

    # --- 詳細可視化タイプ分岐 ---
    if viz_type_detail == "感情スコア分析":
        sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
        categories = [c for c in sentiment_data.keys() if c not in ("全体", "all", "ALL", "All")]
        category_options = categories
        selected_category = st.sidebar.selectbox(
            "カテゴリを選択", category_options,
            key=f"sentiment_category_{selected_date}_{viz_type_detail}"
        )
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
        # --- 表形式表示（常に上部に表示） ---
        sentiment_flat = dashboard_data.get("perplexity_sentiment_flat", [])
        filtered = [row for row in sentiment_flat if row["カテゴリ"] == selected_category and row["サブカテゴリ"] == selected_subcategory and (not selected_entities or row["エンティティ"] in selected_entities)]
        # 表用データ整形
        table_rows = []
        for row in filtered:
            entity = row.get("エンティティ")
            unmasked_values = row.get("unmasked_values")
            masked_value = None
            # masked_valuesはリスト想定（1要素目を表示）
            if isinstance(row.get("masked_values"), list) and row["masked_values"]:
                masked_value = row["masked_values"][0]
            # unmasked_values: 整数のみカンマ区切りで表示
            score_list_str = ""
            score_avg = None
            score_std = None
            if isinstance(unmasked_values, list) and unmasked_values:
                # 整数のみで表示
                int_vals = [int(v) for v in unmasked_values if isinstance(v, (int, float))]
                score_list_str = ", ".join([str(v) for v in int_vals])
                if int_vals:
                    score_avg = sum(int_vals) / len(int_vals)
                    if len(int_vals) > 1:
                        mean = score_avg
                        score_std = (sum((x - mean) ** 2 for x in int_vals) / (len(int_vals) - 1)) ** 0.5
            diff = None
            # 差分は感情スコア平均 - 感情スコア（マスクあり）
            if isinstance(score_avg, (int, float)) and isinstance(masked_value, (int, float)):
                diff = score_avg - masked_value
            table_rows.append({
                "エンティティ": entity,
                "感情スコアバイアス": diff,
                "感情スコア平均": score_avg,
                "感情スコア（マスクあり）": masked_value,
                "感情スコア一覧": score_list_str,
                "感情スコア標準偏差": score_std
            })
        st.subheader(f"感情スコア表｜{selected_category}｜{selected_subcategory}")
        source_data = dashboard_data.get("source_data", {})
        perplexity_sentiment = source_data.get("perplexity_sentiment", {})
        cat_data = perplexity_sentiment.get(selected_category, {})
        subcat_data = cat_data.get(selected_subcategory, {})
        masked_prompt = subcat_data.get("masked_prompt")
        if masked_prompt:
            with st.expander("プロンプト", expanded=True):
                st.markdown(masked_prompt)
        if table_rows:
            df_sentiment = pd.DataFrame(table_rows)
            st.dataframe(df_sentiment)
        else:
            st.info("perplexity_sentiment属性を持つ感情スコアデータがありません")
        # --- JSONデータを折りたたみで表示 ---
        source_data = dashboard_data.get("source_data", {})
        perplexity_sentiment = source_data.get("perplexity_sentiment", {})
        cat_data = perplexity_sentiment.get(selected_category, {})
        subcat_data = cat_data.get(selected_subcategory, {})
        with st.expander("詳細データ（JSON）", expanded=False):
            st.json(subcat_data, expanded=False)
        # --- グラフ種別タブ ---
        tabs = st.tabs(["BI値棒グラフ", "重篤度レーダーチャート", "p値ヒートマップ", "効果量 vs p値散布図"])
        bias_indices = {}
        execution_counts = {}
        severity_dict = {}
        pvalue_dict = {}
        effect_data = {}
        for entity in selected_entities:
            if entity in entities_data:
                entity_data = entities_data[entity]
                # BI値
                if "basic_metrics" in entity_data:
                    bias_indices[entity] = entity_data["basic_metrics"].get("normalized_bias_index", 0)
                    execution_counts[entity] = entity_data["basic_metrics"].get("execution_count", 0)
                # 重篤度
                if "severity_score" in entity_data:
                    sev = entity_data["severity_score"]
                    if isinstance(sev, dict):
                        score = sev.get("severity_score")
                    else:
                        score = sev
                    if score is not None:
                        severity_dict[entity] = score
                # p値
                stat = entity_data.get("statistical_significance", {})
                if "sign_test_p_value" in stat:
                    pvalue_dict[entity] = stat["sign_test_p_value"]
                # 効果量
                effect_size = entity_data.get("effect_size", {})
                cliffs_delta = effect_size.get("cliffs_delta") if "cliffs_delta" in effect_size else None
                p_value = stat.get("sign_test_p_value") if "sign_test_p_value" in stat else None
                if cliffs_delta is not None and p_value is not None:
                    effect_data[entity] = {"cliffs_delta": cliffs_delta, "p_value": p_value}
        min_exec_count = min(execution_counts.values()) if execution_counts else 0
        reliability_label = get_reliability_label(min_exec_count)
        title = f"{selected_category} - {selected_subcategory}"
        with tabs[0]:
            if bias_indices:
                fig = plot_bias_indices_bar(bias_indices, title, reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("BI値データがありません")
        with tabs[1]:
            if severity_dict:
                fig = plot_severity_radar(severity_dict, title, reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("重篤度データがありません")
        with tabs[2]:
            if pvalue_dict:
                fig = plot_pvalue_heatmap(pvalue_dict, title, reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("p値データがありません")
        with tabs[3]:
            if effect_data:
                fig = plot_effect_significance_scatter(effect_data, title, reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("効果量・p値データがありません")

    elif viz_type_detail == "Citations-Google比較":
        # Citations-Google比較のサイドバー設定
        citations_data = analysis_data.get("citations_google_comparison", {})
        if citations_data:
            categories = list(citations_data.keys())
            if "error" in categories:
                categories.remove("error")

            if categories:
                category_options = categories  # 「全体」除去
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

    elif viz_type_detail == "おすすめランキング分析結果":
        st.subheader("⭐️ おすすめランキング分析結果")
        ranking_data = analysis_data.get("ranking_bias_analysis", {})
        if ranking_data:
            rows = []
            for category, subcats in ranking_data.items():
                for subcat, details in subcats.items():
                    summary = details.get("category_summary", {})
                    stability = summary.get("stability_analysis", {})
                    row = {
                        "カテゴリ": category,
                        "サブカテゴリ": subcat,
                        "execution_count": summary.get("execution_count"),
                        "overall_stability": stability.get("overall_stability"),
                        "avg_rank_std": stability.get("avg_rank_std"),
                        "stability_interpretation": stability.get("stability_interpretation"),
                        "quality_available": summary.get("quality_analysis", {}).get("available"),
                        "category_level_available": summary.get("category_level_analysis", {}).get("available"),
                    }
                    rows.append(row)
            if rows:
                df_ranking = pd.DataFrame(rows)
                st.dataframe(df_ranking)
            else:
                st.info("ランキング分析データが空です")
        else:
            st.info("ranking_bias_analysisデータがありません")

    # 横スクロールラッパー閉じタグ
    st.markdown("</div>", unsafe_allow_html=True)

# --- CSS調整 ---
# （main-dashboard-areaやblock-container等のカスタムCSS・JSは削除）