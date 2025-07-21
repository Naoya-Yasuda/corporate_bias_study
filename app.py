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
from src.utils.plot_utils import plot_severity_radar, plot_pvalue_heatmap, plot_stability_score_distribution

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
    key="analysis_type_selector"
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
    viz_type_options = ["感情スコア分析", "おすすめランキング分析結果", "Perplexity-Google比較", "統合分析"]
    viz_type_detail = st.sidebar.selectbox(
        "詳細可視化タイプを選択",
        viz_type_options,
        key="viz_type_selector",
        index=0  # デフォルトで最初の項目を選択
    )

    # --- メインダッシュボード（統合版） ---
    st.markdown('<div class="main-dashboard-area">', unsafe_allow_html=True)

    # --- 統一カテゴリリスト作成 ---
    sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
    all_categories = [c for c in sentiment_data.keys() if c not in ("全体", "all", "ALL", "All")]
    all_categories.sort()

    # 統一されたカテゴリ選択（全分析タイプで共通）
    selected_category = st.sidebar.selectbox(
        "カテゴリを選択",
        all_categories,
        key="category_selector",
        index=0  # デフォルトで最初の項目を選択
    )

    # --- 統一サブカテゴリリスト作成 ---
    all_subcategories = list(sentiment_data[selected_category].keys())
    all_subcategories.sort()

    # 統一されたサブカテゴリ選択（全分析タイプで共通）
    selected_subcategory = st.sidebar.selectbox(
        "サブカテゴリを選択",
        all_subcategories,
        key="subcategory_selector",
        index=0  # デフォルトで最初の項目を選択
    )

    # --- 詳細可視化タイプ分岐 ---
    if viz_type_detail == "感情スコア分析":
        # 選択されたカテゴリが感情スコア分析で利用可能かチェック
        if selected_category not in sentiment_data:
            st.warning(f"選択されたカテゴリ '{selected_category}' は感情スコア分析では利用できません。")
            st.stop()

        entities_data = sentiment_data[selected_category][selected_subcategory].get("entities", {})
        entities = list(entities_data.keys())
        selected_entities = st.sidebar.multiselect(
            "エンティティを選択（複数選択可）",
            entities,
            key="entities_selector",
            default=entities[:10] if len(entities) > 10 else entities  # デフォルトで最初の10項目（または全て）を選択
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
        subcat_data = perplexity_sentiment.get(selected_category, {}).get(selected_subcategory, {})
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
        subcat_data = perplexity_sentiment.get(selected_category, {}).get(selected_subcategory, {})
        with st.expander("詳細データ（JSON）", expanded=True):
            st.json(subcat_data, expanded=False)
        # --- 主要指標サマリー表の生成・表示（追加） ---
        summary_rows = []
        interpretation_dict = {}
        for entity in selected_entities:
            if entity in entities_data:
                entity_data = entities_data[entity]
                # 統計的有意性
                stat = entity_data.get("statistical_significance", {})
                p_value = stat.get("sign_test_p_value")
                significance_level = stat.get("significance_level")
                # 効果量
                effect_size = entity_data.get("effect_size", {})
                cliffs_delta = effect_size.get("cliffs_delta")
                effect_magnitude = effect_size.get("effect_magnitude")
                # 信頼区間
                ci = entity_data.get("confidence_interval", {})
                ci_lower = ci.get("ci_lower")
                ci_upper = ci.get("ci_upper")
                # 安定性
                stability = entity_data.get("stability_metrics", {})
                stability_score = stability.get("stability_score")
                reliability = stability.get("reliability")
                # バイアス指標・ランク
                bias_index = entity_data.get("bias_index")
                bias_rank = entity_data.get("bias_rank")
                # interpretation
                interpretation = entity_data.get("interpretation", {})
                # サマリー行作成
                summary_rows.append({
                    "エンティティ": entity,
                    "統計的有意性": significance_level or "-",
                    "p値": p_value if p_value is not None else "-",
                    "効果量": effect_magnitude or "-",
                    "信頼区間": f"{ci_lower}～{ci_upper}" if ci_lower is not None and ci_upper is not None else "-",
                    "安定性": reliability or "-",
                    "バイアス指標": bias_index if bias_index is not None else "-",
                    "ランク": bias_rank if bias_rank is not None else "-",
                })
                # interpretationまとめ
                interp_lines = []
                if isinstance(interpretation, dict):
                    for k, v in interpretation.items():
                        interp_lines.append(f"- **{k}**: {v}")
                elif isinstance(interpretation, str):
                    interp_lines.append(interpretation)
                interpretation_dict[entity] = "\n".join(interp_lines)
        if summary_rows:
            st.subheader("主要指標サマリー表")
            df_summary = pd.DataFrame(summary_rows)
            st.dataframe(df_summary, use_container_width=True)
            for idx, row in df_summary.iterrows():
                entity = row["エンティティ"]
                interp = interpretation_dict.get(entity)
                if interp:
                    with st.expander(f"{entity} の詳細解釈"):
                        st.markdown(interp)
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
            st.info("各エンティティのNormalized Bias Index（バイアス指標）を棒グラフで表示します。値が大きいほどバイアスが強いことを示します。", icon="ℹ️")
            if bias_indices:
                fig = plot_bias_indices_bar(bias_indices, title, reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("BI値データがありません")
        with tabs[1]:
            st.info("各エンティティのバイアス重篤度（影響度）をレーダーチャートで可視化します。値が高いほど影響が大きいことを示します。", icon="ℹ️")
            if severity_dict:
                fig = plot_severity_radar(severity_dict, output_path=None, title=title, reliability_label=reliability_label)
                st.pyplot(fig, use_container_width=False)
            else:
                st.info("重篤度データがありません")
        with tabs[2]:
            st.info("各エンティティの統計的有意性（p値）をヒートマップで表示します。色が濃いほど有意性が高いことを示します。", icon="ℹ️")
            if pvalue_dict:
                fig = plot_pvalue_heatmap(pvalue_dict, output_path=None, title=title, reliability_label=reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("p値データがありません")
        with tabs[3]:
            st.info("各エンティティの効果量（Cliff's Delta）とp値の関係を散布図で表示します。", icon="ℹ️")
            if effect_data:
                fig = plot_effect_significance_scatter(effect_data, title, reliability_label)
                st.pyplot(fig, use_container_width=True)
            else:
                st.info("効果量・p値データがありません")

    elif viz_type_detail == "Perplexity-Google比較":
        # Perplexity-Google比較のサイドバー設定
        citations_data = analysis_data.get("citations_google_comparison", {})
        if citations_data:
            # 選択されたカテゴリがPerplexity-Google比較で利用可能かチェック
            if selected_category not in citations_data:
                st.warning(f"選択されたカテゴリ '{selected_category}' はPerplexity-Google比較では利用できません。")
                st.stop()

            if selected_category == "全体":
                # 全体表示の場合、サブカテゴリは「全体」のみ
                selected_subcategory = "全体"
                # 全体データを集約
                all_similarity_data = {}
                for cat in citations_data.keys():
                    if cat != "error":
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
                subcat_data = citations_data[selected_category][selected_subcategory]
                similarity_data = subcat_data.get("ranking_similarity", {})

            # エンティティ選択機能を追加
            # Google検索とPerplexity Citationsの両方からエンティティを取得
            google_entities = []
            citations_entities = []

            if selected_category != "全体":
                # Google検索データからエンティティを取得
                source_data = dashboard_data.get("source_data", {})
                google_search_data = source_data.get("google_data", {})
                if selected_category in google_search_data and selected_subcategory in google_search_data[selected_category]:
                    google_subcat_data = google_search_data[selected_category][selected_subcategory]
                    if "entities" in google_subcat_data:
                        google_entities = list(google_subcat_data["entities"].keys())

                # Perplexity Citationsデータからエンティティを取得
                perplexity_citations_data = source_data.get("perplexity_citations", {})
                if selected_category in perplexity_citations_data and selected_subcategory in perplexity_citations_data[selected_category]:
                    citations_subcat_data = perplexity_citations_data[selected_category][selected_subcategory]
                    if "entities" in citations_subcat_data:
                        citations_entities = list(citations_subcat_data["entities"].keys())

            # 全エンティティを統合（重複除去）
            all_entities = list(set(google_entities + citations_entities))
            all_entities.sort()

            if all_entities:
                selected_entities = st.sidebar.multiselect(
                    "エンティティを選択（複数選択可）",
                    all_entities,
                    default=all_entities[:10] if len(all_entities) > 10 else all_entities,
                    key="sentiment_entities"
                )
            else:
                selected_entities = []

            # Perplexity-Google比較の表示
            st.subheader(f"🔗 Perplexity-Google比較 - {selected_category} / {selected_subcategory}")

                        # === 1. Perplexity Citationsプロンプト情報表示 ===
            source_data = dashboard_data.get("source_data", {})

            # Perplexity Citationsプロンプト表示
            perplexity_citations_data = source_data.get("perplexity_citations", {})
            if selected_category in perplexity_citations_data and selected_subcategory in perplexity_citations_data[selected_category]:
                citations_subcat_data = perplexity_citations_data[selected_category][selected_subcategory]
                with st.expander("🤖 Perplexity-Google検索プロンプト情報", expanded=False):
                    if "entities" in citations_subcat_data:
                        # 最初のエンティティからプロンプト情報を取得
                        first_entity_data = next(iter(citations_subcat_data["entities"].values()), {})
                        official_prompt = first_entity_data.get("official_prompt", "未設定")
                        reputation_prompt = first_entity_data.get("reputation_prompt", "未設定")

                        st.markdown("**📝 使用されたプロンプト**:")
                        st.markdown(f"- **公式情報**: `{official_prompt}`")
                        st.markdown(f"- **評判情報**: `{reputation_prompt}`")

            # === 2. Google検索データテーブル表示 ===
            st.markdown("**Google検索データテーブル**:")
            if selected_category in google_search_data and selected_subcategory in google_search_data[selected_category]:
                google_subcat_data = google_search_data[selected_category][selected_subcategory]
                if "entities" in google_subcat_data:
                    google_entities_data = google_subcat_data["entities"]

                    # 選択されたエンティティのみを表示
                    filtered_google_entities = {k: v for k, v in google_entities_data.items()
                                             if not selected_entities or k in selected_entities}

                    if filtered_google_entities:
                        google_table_rows = []
                        for entity_name, entity_data in filtered_google_entities.items():
                            # official_results と reputation_results の統計
                            official_count = len(entity_data.get("official_results", []))
                            reputation_count = len(entity_data.get("reputation_results", []))
                            total_results = official_count + reputation_count

                            # 感情分析結果の統計
                            positive_count = 0
                            negative_count = 0
                            neutral_count = 0
                            unknown_count = 0

                            for result in entity_data.get("reputation_results", []):
                                sentiment = result.get("sentiment", "unknown")
                                if sentiment == "positive":
                                    positive_count += 1
                                elif sentiment == "negative":
                                    negative_count += 1
                                elif sentiment == "neutral":
                                    neutral_count += 1
                                else:
                                    unknown_count += 1

                            # 主要ドメイン（上位3つ）
                            all_domains = []
                            for result in entity_data.get("official_results", []) + entity_data.get("reputation_results", []):
                                domain = result.get("domain")
                                if domain:
                                    all_domains.append(domain)

                            top_domains = list(set(all_domains))[:3]
                            top_domains_str = ", ".join(top_domains) if top_domains else "なし"

                            google_table_rows.append({
                                "エンティティ": entity_name,
                                "公式結果数": official_count,
                                "評判結果数": reputation_count,
                                "総結果数": total_results,
                                "ポジティブ": positive_count,
                                "ネガティブ": negative_count,
                                "中立": neutral_count,
                                "不明": unknown_count,
                                "主要ドメイン": top_domains_str
                            })

                        if google_table_rows:
                            df_google = pd.DataFrame(google_table_rows)
                            st.dataframe(df_google, use_container_width=True)
                        else:
                            st.info("表示可能なGoogle検索データがありません")
                    else:
                        st.info("Google検索データがありません")
                else:
                    st.info("Google検索エンティティデータがありません")
            else:
                st.info("Google検索データがありません")

            # === 3. Perplexity Citationsデータテーブル表示 ===
            st.markdown("**Perplexity Citationsデータテーブル**:")
            if selected_category in perplexity_citations_data and selected_subcategory in perplexity_citations_data[selected_category]:
                citations_subcat_data = perplexity_citations_data[selected_category][selected_subcategory]
                if "entities" in citations_subcat_data:
                    citations_entities_data = citations_subcat_data["entities"]

                    # 選択されたエンティティのみを表示
                    filtered_citations_entities = {k: v for k, v in citations_entities_data.items()
                                                 if not selected_entities or k in selected_entities}

                    if filtered_citations_entities:
                        citations_table_rows = []
                        for entity_name, entity_data in filtered_citations_entities.items():
                            # official_results と reputation_results の統計
                            official_count = len(entity_data.get("official_results", []))
                            reputation_count = len(entity_data.get("reputation_results", []))
                            total_results = official_count + reputation_count

                            # 感情分析結果の統計
                            positive_count = 0
                            negative_count = 0
                            neutral_count = 0
                            unknown_count = 0

                            for result in entity_data.get("reputation_results", []):
                                sentiment = result.get("sentiment", "unknown")
                                if sentiment == "positive":
                                    positive_count += 1
                                elif sentiment == "negative":
                                    negative_count += 1
                                elif sentiment == "neutral":
                                    neutral_count += 1
                                else:
                                    unknown_count += 1

                            # 主要ドメイン（上位3つ）
                            all_domains = []
                            for result in entity_data.get("official_results", []) + entity_data.get("reputation_results", []):
                                domain = result.get("domain")
                                if domain:
                                    all_domains.append(domain)

                            top_domains = list(set(all_domains))[:3]
                            top_domains_str = ", ".join(top_domains) if top_domains else "なし"

                            citations_table_rows.append({
                                "エンティティ": entity_name,
                                "公式結果数": official_count,
                                "評判結果数": reputation_count,
                                "総結果数": total_results,
                                "ポジティブ": positive_count,
                                "ネガティブ": negative_count,
                                "中立": neutral_count,
                                "不明": unknown_count,
                                "主要ドメイン": top_domains_str
                            })

                        if citations_table_rows:
                            df_citations = pd.DataFrame(citations_table_rows)
                            st.dataframe(df_citations, use_container_width=True)
                        else:
                            st.info("表示可能なPerplexity Citationsデータがありません")
                    else:
                        st.info("Perplexity Citationsデータがありません")
                else:
                    st.info("Perplexity Citationsエンティティデータがありません")
            else:
                st.info("Perplexity Citationsデータがありません")

                        # === 3.5. 詳細データ表示 ===
            with st.expander("詳細データ（JSON）", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Google検索詳細データ**")
                    if selected_category in google_search_data and selected_subcategory in google_search_data[selected_category]:
                        google_subcat_data = google_search_data[selected_category][selected_subcategory]
                        if "entities" in google_subcat_data:
                            st.json(google_subcat_data["entities"], expanded=False)
                        else:
                            st.info("Google検索エンティティデータがありません")
                    else:
                        st.info("Google検索詳細データがありません")

                with col2:
                    st.markdown("**Perplexity Citations詳細データ**")
                    if selected_category in perplexity_citations_data and selected_subcategory in perplexity_citations_data[selected_category]:
                        citations_subcat_data = perplexity_citations_data[selected_category][selected_subcategory]
                        if "entities" in citations_subcat_data:
                            st.json(citations_subcat_data["entities"], expanded=False)
                        else:
                            st.info("Perplexity Citationsエンティティデータがありません")
                    else:
                        st.info("Perplexity Citations詳細データがありません")

            # === 4. 比較分析結果表示 ===
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
                            if isinstance(value, (int, float)):
                                st.markdown(f"- **{metric}**: {value:.3f}")
                            else:
                                st.markdown(f"- **{metric}**: {value}")
                with col2:
                    st.markdown("**📋 指標説明**")
                    st.markdown("- **RBO**: 上位重視重複度（0-1）")
                    st.markdown("- **Kendall Tau**: 順位相関係数（-1〜1）")
                    st.markdown("- **Overlap Ratio**: 共通要素率（0-1）")

                # 詳細分析データ表示
                with st.expander("詳細分析データ（JSON）", expanded=True):
                    if selected_category in citations_data and selected_subcategory in citations_data[selected_category]:
                        subcat_comparison_data = citations_data[selected_category][selected_subcategory]
                        st.json(subcat_comparison_data, expanded=False)
                    else:
                        st.info("詳細分析データがありません")
            else:
                st.info("ランキング類似度データがありません")
        else:
            st.warning("Perplexity-Google比較データが見つかりません")

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

            # カテゴリ横断分析タブ
            tabs = st.tabs(["安定性スコア分布", "重篤度ランキング", "相関マトリクス"])

            with tabs[0]:
                st.info("全カテゴリの安定性分析結果を2つのグラフで表示します：\n\n"
                       "【左：安定性スコア分布（ヒストグラム）】\n"
                       "・X軸：安定性スコア（0-1、1に近いほど安定）\n"
                       "・Y軸：カテゴリ数（該当スコアを持つカテゴリ数）\n"
                       "・赤線：現在選択中のカテゴリの安定性スコア\n\n"
                       "【右：安定性 vs 順位標準偏差（散布図）】\n"
                       "・X軸：安定性スコア（1に近いほど安定）\n"
                       "・Y軸：順位標準偏差（0に近いほど順位変動が小さい）\n"
                       "・赤点：現在選択中のカテゴリ\n"
                       "・青点：その他のカテゴリ", icon="ℹ️")

                # 全分析データから現在のカテゴリを取得
                ranking_bias_data = analysis_data.get("ranking_bias_analysis", {})
                fig = plot_stability_score_distribution(ranking_bias_data, selected_category, selected_subcategory)
                if fig:
                    st.pyplot(fig, use_container_width=True)
                    plt.close(fig)
                else:
                    st.info("安定性スコアデータがありません")

            with tabs[1]:
                st.info("カテゴリ横断の重篤度ランキングを表示します。", icon="ℹ️")
                # 重篤度ランキングの実装（既存）

            with tabs[2]:
                st.info("カテゴリ間の相関関係をマトリクスで表示します。", icon="ℹ️")
                # 相関マトリクスの実装（既存）

            # 詳細データ
            with st.expander("詳細データ"):
                st.json(cross_data, use_container_width=True)
        else:
            st.info("統合分析データがありません")

    elif viz_type_detail == "おすすめランキング分析結果":
        # perplexity_rankingsデータを直接参照
        source_data = dashboard_data.get("source_data", {})
        perplexity_rankings = source_data.get("perplexity_rankings", {})

        if perplexity_rankings:
            # 選択されたカテゴリがおすすめランキング分析結果で利用可能かチェック
            if selected_category not in perplexity_rankings:
                st.warning(f"選択されたカテゴリ '{selected_category}' はおすすめランキング分析結果では利用できません。")
                st.stop()

            # エンティティ選択機能を追加
            # ランキングデータからエンティティを取得
            subcat_data = perplexity_rankings[selected_category][selected_subcategory]
            ranking_summary = subcat_data.get("ranking_summary", {})
            entities = ranking_summary.get("entities", {})
            all_entities = list(entities.keys())
            all_entities.sort()

            if all_entities:
                selected_entities = st.sidebar.multiselect(
                    "エンティティを選択（複数選択可）",
                    all_entities,
                    default=all_entities[:10] if len(all_entities) > 10 else all_entities,
                    key="sentiment_entities"
                )
            else:
                selected_entities = []

            st.subheader(f"おすすめランキング分析結果｜{selected_category}｜{selected_subcategory}")

            # === 1. マスクありプロンプトとデータ内容表示 ===
            answer_list = subcat_data.get("answer_list", [])
            avg_ranking = ranking_summary.get("avg_ranking", [])

            # プロンプト情報表示
            if "prompt" in subcat_data:
                with st.expander("使用プロンプト", expanded=False):
                    st.markdown(f"**検索クエリ**: {subcat_data['prompt']}")
            # ランキングデータテーブル表示
            st.markdown("**ランキングデータテーブル**:")
            if entities and avg_ranking:
                table_rows = []
                for i, entity_name in enumerate(avg_ranking):
                    # 選択されたエンティティのみを表示
                    if entity_name in entities and (not selected_entities or entity_name in selected_entities):
                        entity_data = entities[entity_name]
                        avg_rank = entity_data.get("avg_rank", "未ランク")
                        all_ranks = entity_data.get("all_ranks", [])
                        official_url = entity_data.get("official_url", "")

                        # 順位統計計算
                        if all_ranks and isinstance(avg_rank, (int, float)):
                            rank_std = (sum((r - avg_rank) ** 2 for r in all_ranks) / len(all_ranks)) ** 0.5 if len(all_ranks) > 1 else 0
                            min_rank = min(all_ranks)
                            max_rank = max(all_ranks)
                            rank_variation = max_rank - min_rank
                        else:
                            rank_std = 0
                            min_rank = max_rank = rank_variation = "N/A"

                        table_rows.append({
                            "順位": i + 1,
                            "エンティティ": entity_name,
                            "平均順位": f"{avg_rank:.2f}" if isinstance(avg_rank, (int, float)) else avg_rank,
                            "順位標準偏差": f"{rank_std:.3f}" if rank_std else "0.000",
                            "最良順位": min_rank,
                            "最悪順位": max_rank,
                            "順位変動": rank_variation,
                            "公式URL": official_url
                        })

                if table_rows:
                    df_ranking = pd.DataFrame(table_rows)
                    st.dataframe(df_ranking, use_container_width=True)
                else:
                    st.info("表示可能なランキングデータがありません")
            else:
                st.info("ランキングサマリーデータがありません")

            # 実行統計表示
            with st.expander("**実行統計**", expanded=False):
                total_executions = len(answer_list)
                st.markdown(f"- 総実行回数: {total_executions}")

                if avg_ranking:
                    # 順位標準偏差の計算
                    rank_std_values = []
                    max_rank_variation = 0

                    for entity_name, entity_data in entities.items():
                        # 選択されたエンティティのみを対象とする
                        if not selected_entities or entity_name in selected_entities:
                            all_ranks = entity_data.get("all_ranks", [])
                            if all_ranks:
                                avg_rank = sum(all_ranks) / len(all_ranks)
                                rank_std = (sum((r - avg_rank) ** 2 for r in all_ranks) / len(all_ranks)) ** 0.5
                                rank_std_values.append(rank_std)
                                rank_variation = max(all_ranks) - min(all_ranks)
                                max_rank_variation = max(max_rank_variation, rank_variation)

                    avg_rank_std = sum(rank_std_values) / len(rank_std_values) if rank_std_values else 0

                    st.markdown(f"- 平均順位標準偏差: {avg_rank_std:.3f}")
                    st.markdown(f"- 最大順位変動: {max_rank_variation}")
            with st.expander("**取得回答サンプル**", expanded=False):

                # 回答サンプル表示
                if answer_list:
                    for i, answer_data in enumerate(answer_list[:3]):  # 最初の3つを表示
                        answer_text = answer_data.get("answer", "") if isinstance(answer_data, dict) else str(answer_data)
                        with st.expander(f"回答 {i+1}", expanded=False):
                            st.text(answer_text[:500] + "..." if len(answer_text) > 500 else answer_text)
                # 詳細JSONデータ
            with st.expander("**詳細データ（JSON）**", expanded=True):
                st.json(subcat_data, expanded=False)

            # === 2. 主要指標サマリー表と詳細解釈 ===

            # ranking_bias_analysisから分析済みデータを取得
            analysis_data = dashboard_data.get("analysis_results", {})
            ranking_bias_data = analysis_data.get("ranking_bias_analysis", {})

            if ranking_bias_data and selected_category in ranking_bias_data and selected_subcategory in ranking_bias_data[selected_category]:
                category_bias_data = ranking_bias_data[selected_category][selected_subcategory]

                # category_summaryから各種分析結果を取得
                category_summary = category_bias_data.get("category_summary", {})
                stability_analysis = category_summary.get("stability_analysis", {})
                quality_analysis = category_summary.get("quality_analysis", {})
                category_level_analysis = category_summary.get("category_level_analysis", {})

            # 主要指標サマリー表（ranking_bias_analysis優先、フォールバック対応）
            st.subheader("📊 主要指標サマリー表")

            if ranking_bias_data and selected_category in ranking_bias_data and selected_subcategory in ranking_bias_data[selected_category]:
                category_bias_data = ranking_bias_data[selected_category][selected_subcategory]
                category_summary = category_bias_data.get("category_summary", {})
                stability_analysis = category_summary.get("stability_analysis", {})
                quality_analysis = category_summary.get("quality_analysis", {})
                category_level_analysis = category_summary.get("category_level_analysis", {})

                # 分析結果解説を生成する関数
                def get_stability_result_explanation(score, std_val):
                    if score >= 0.9:
                        return "極めて安定した結果で、ランキングに高い信頼性がある"
                    elif score >= 0.8:
                        return "安定した結果で、分析に適用可能な信頼性を持つ"
                    elif score >= 0.6:
                        return "中程度の安定性で、傾向把握には有効"
                    else:
                        return "変動が大きく、結果の解釈には注意が必要"

                def get_quality_result_explanation(score):
                    if score >= 0.9:
                        return "非常に高品質なデータで、精密な分析が可能"
                    elif score >= 0.8:
                        return "高品質なデータで、信頼性の高い分析結果を提供"
                    elif score >= 0.6:
                        return "一定品質のデータで、基本的な分析は可能"
                    else:
                        return "データ品質に課題があり、結果解釈に注意が必要"

                def get_competitive_balance_explanation(balance):
                    if balance == "高":
                        return "多数のエンティティが競争し、市場バランスが良好"
                    elif balance == "中":
                        return "適度な競争環境で、ある程度の市場バランスを保持"
                    else:
                        return "競争エンティティが少なく、限定的な市場構造"

                def get_ranking_spread_explanation(spread):
                    if spread == "full":
                        return "全順位範囲を活用し、明確な序列が存在"
                    elif spread == "partial":
                        return "部分的な順位範囲の利用で、一部集中傾向あり"
                    else:
                        return "限定的な順位範囲で、ランキングの分散度が低い"

                # 実際の値を取得
                overall_stability = stability_analysis.get('overall_stability', 0)
                avg_rank_std = stability_analysis.get('avg_rank_std', 0)
                stability_interpretation = stability_analysis.get("stability_interpretation", "未判定")

                quality_metrics = quality_analysis.get('quality_metrics', {})
                completeness_score = quality_metrics.get('completeness_score', 0)
                consistency_score = quality_metrics.get('consistency_score', 0)
                overall_quality_score = quality_analysis.get('overall_quality_score', 0)
                quality_interpretation = quality_analysis.get("quality_interpretation", "未判定")

                competitive_balance = category_level_analysis.get("competition_analysis", {}).get("competitive_balance", "未判定")
                ranking_spread = category_level_analysis.get("competition_analysis", {}).get("ranking_spread", "未評価")

                # 再設計版：9項目統合テーブル（5カラム構造：指標概要 + 分析結果）
                summary_data = [
                    # 安定性指標（3項目）
                    ["全体安定性スコア（overall_stability）", f"{overall_stability:.3f}", "安定性", "ランキングの全体的な安定性を示すスコア（1.0が最高）", get_stability_result_explanation(overall_stability, avg_rank_std)],
                    ["平均順位標準偏差（avg_rank_std）", f"{avg_rank_std:.3f}", "安定性", "複数実行における各エンティティの順位変動の平均値", f"順位変動の平均が{avg_rank_std:.3f}で、{'小さな変動' if avg_rank_std < 1.0 else '中程度の変動' if avg_rank_std < 2.0 else '大きな変動'}を示す"],
                    ["安定性判定結果（stability_interpretation）", stability_interpretation, "安定性", "安定性スコアに基づく定性的な判定結果", f"総合的な安定性評価として「{stability_interpretation}」と判定"],

                    # 品質指標（4項目）
                    ["データ完全性スコア（completeness_score）", f"{completeness_score:.3f}", "品質", "データの欠損や不整合がない程度を示すスコア", f"データ完全性が{completeness_score:.1%}で、{'優秀' if completeness_score >= 0.9 else '良好' if completeness_score >= 0.8 else '要改善'}なレベル"],
                    ["データ一貫性スコア（consistency_score）", f"{consistency_score:.3f}", "品質", "データの論理的整合性と一貫性を示すスコア", f"データ一貫性が{consistency_score:.1%}で、{'高い一貫性' if consistency_score >= 0.9 else '中程度の一貫性' if consistency_score >= 0.7 else '一貫性に課題'}を示す"],
                    ["総合品質評価（overall_quality_score）", f"{overall_quality_score:.3f}", "品質", "完全性・一貫性・信頼性を統合した総合品質スコア", get_quality_result_explanation(overall_quality_score)],
                    ["品質判定結果（quality_interpretation）", quality_interpretation, "品質", "品質スコアに基づく定性的な判定結果", f"総合的な品質評価として「{quality_interpretation}」と判定"],

                    # 競争性指標（2項目）
                    ["競争バランス評価（competitive_balance）", competitive_balance, "競争性", "エンティティ間の競争の均衡性に関する評価", get_competitive_balance_explanation(competitive_balance)],
                    ["ランキング範囲（ranking_spread）", ranking_spread, "競争性", "ランキングが利用する順位範囲の広がり", get_ranking_spread_explanation(ranking_spread)]
                ]

                df_summary = pd.DataFrame(summary_data, columns=["指標名", "値", "指標カテゴリ", "指標概要", "分析結果"])
                st.dataframe(df_summary, use_container_width=True, hide_index=True)
            else:
                # フォールバック：perplexity_rankingsから直接計算して仕様書通りの9項目テーブルを作成
                ranking_summary = subcat_data.get("ranking_summary", {})
                entities = ranking_summary.get("entities", {})
                answer_list = subcat_data.get("answer_list", [])
                execution_count = len(answer_list)

                # 安定性指標の計算
                rank_std_values = []
                overall_stability_scores = []

                for entity_name, entity_data in entities.items():
                    all_ranks = entity_data.get("all_ranks", [])
                    if all_ranks:
                        avg_rank = sum(all_ranks) / len(all_ranks)
                        rank_std = (sum((r - avg_rank) ** 2 for r in all_ranks) / len(all_ranks)) ** 0.5 if len(all_ranks) > 1 else 0
                        rank_std_values.append(rank_std)

                        # 安定性スコア（順位標準偏差の逆数で計算、正規化）
                        stability_score = 1 / (1 + rank_std) if rank_std > 0 else 1
                        overall_stability_scores.append(stability_score)

                avg_rank_std = sum(rank_std_values) / len(rank_std_values) if rank_std_values else 0
                overall_stability = sum(overall_stability_scores) / len(overall_stability_scores) if overall_stability_scores else 1.0

                # 安定性解釈
                if overall_stability >= 0.8:
                    stability_interpretation = "安定"
                elif overall_stability >= 0.6:
                    stability_interpretation = "中程度"
                else:
                    stability_interpretation = "不安定"

                # 品質指標の簡易計算
                completeness_score = len([e for e in entities.values() if e.get("all_ranks")]) / len(entities) if entities else 0
                consistency_score = 1.0 - avg_rank_std / 5.0 if avg_rank_std <= 5.0 else 0.0  # 標準偏差から一貫性計算
                overall_quality_score = (completeness_score + consistency_score) / 2.0

                if overall_quality_score >= 0.8:
                    quality_interpretation = "高品質"
                elif overall_quality_score >= 0.6:
                    quality_interpretation = "中品質"
                else:
                    quality_interpretation = "低品質"

                # 競争性指標の簡易計算
                total_entities = len(entities)
                if total_entities >= 5:
                    competitive_balance = "高"
                elif total_entities >= 3:
                    competitive_balance = "中"
                else:
                    competitive_balance = "低"

                # ランキング範囲の計算
                all_positions = set()
                for entity_data in entities.values():
                    all_ranks = entity_data.get("all_ranks", [])
                    all_positions.update(all_ranks)

                if len(all_positions) >= total_entities:
                    ranking_spread = "full"
                elif len(all_positions) >= total_entities * 0.7:
                    ranking_spread = "partial"
                else:
                    ranking_spread = "limited"

                # 分析結果解説を生成する関数（フォールバック用）
                def get_stability_result_explanation(score, std_val):
                    if score >= 0.9:
                        return "極めて安定した結果で、ランキングに高い信頼性がある"
                    elif score >= 0.8:
                        return "安定した結果で、分析に適用可能な信頼性を持つ"
                    elif score >= 0.6:
                        return "中程度の安定性で、傾向把握には有効"
                    else:
                        return "変動が大きく、結果の解釈には注意が必要"

                def get_quality_result_explanation(score):
                    if score >= 0.9:
                        return "非常に高品質なデータで、精密な分析が可能"
                    elif score >= 0.8:
                        return "高品質なデータで、信頼性の高い分析結果を提供"
                    elif score >= 0.6:
                        return "一定品質のデータで、基本的な分析は可能"
                    else:
                        return "データ品質に課題があり、結果解釈に注意が必要"

                def get_competitive_balance_explanation(balance):
                    if balance == "高":
                        return "多数のエンティティが競争し、市場バランスが良好"
                    elif balance == "中":
                        return "適度な競争環境で、ある程度の市場バランスを保持"
                    else:
                        return "競争エンティティが少なく、限定的な市場構造"

                def get_ranking_spread_explanation(spread):
                    if spread == "full":
                        return "全順位範囲を活用し、明確な序列が存在"
                    elif spread == "partial":
                        return "部分的な順位範囲の利用で、一部集中傾向あり"
                    else:
                        return "限定的な順位範囲で、ランキングの分散度が低い"

                # フォールバック用の9項目統合テーブル（5カラム構造：指標概要 + 分析結果）
                summary_data = [
                    # 安定性指標（3項目）
                    ["全体安定性スコア（overall_stability）", f"{overall_stability:.3f}", "安定性", "ランキングの全体的な安定性を示すスコア（1.0が最高）", get_stability_result_explanation(overall_stability, avg_rank_std)],
                    ["平均順位標準偏差（avg_rank_std）", f"{avg_rank_std:.3f}", "安定性", "複数実行における各エンティティの順位変動の平均値", f"順位変動の平均が{avg_rank_std:.3f}で、{'小さな変動' if avg_rank_std < 1.0 else '中程度の変動' if avg_rank_std < 2.0 else '大きな変動'}を示す"],
                    ["安定性判定結果（stability_interpretation）", stability_interpretation, "安定性", "安定性スコアに基づく定性的な判定結果", f"総合的な安定性評価として「{stability_interpretation}」と判定"],

                    # 品質指標（4項目）
                    ["データ完全性スコア（completeness_score）", f"{completeness_score:.3f}", "品質", "データの欠損や不整合がない程度を示すスコア", f"データ完全性が{completeness_score:.1%}で、{'優秀' if completeness_score >= 0.9 else '良好' if completeness_score >= 0.8 else '要改善'}なレベル"],
                    ["データ一貫性スコア（consistency_score）", f"{consistency_score:.3f}", "品質", "データの論理的整合性と一貫性を示すスコア", f"データ一貫性が{consistency_score:.1%}で、{'高い一貫性' if consistency_score >= 0.9 else '中程度の一貫性' if consistency_score >= 0.7 else '一貫性に課題'}を示す"],
                    ["総合品質評価（overall_quality_score）", f"{overall_quality_score:.3f}", "品質", "完全性・一貫性・信頼性を統合した総合品質スコア", get_quality_result_explanation(overall_quality_score)],
                    ["品質判定結果（quality_interpretation）", quality_interpretation, "品質", "品質スコアに基づく定性的な判定結果", f"総合的な品質評価として「{quality_interpretation}」と判定"],

                    # 競争性指標（2項目）
                    ["競争バランス評価（competitive_balance）", competitive_balance, "競争性", "エンティティ間の競争の均衡性に関する評価", get_competitive_balance_explanation(competitive_balance)],
                    ["ランキング範囲（ranking_spread）", ranking_spread, "競争性", "ランキングが利用する順位範囲の広がり", get_ranking_spread_explanation(ranking_spread)]
                ]

                df_summary = pd.DataFrame(summary_data, columns=["指標名", "値", "指標カテゴリ", "指標概要", "分析結果"])
                st.dataframe(df_summary, use_container_width=True, hide_index=True)

            # 詳細解釈テキスト（重複部分を削除し、詳細解釈にしかない内容のみ表示）
            st.subheader("📋 詳細解釈")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**信頼性評価**")
                # execution_countの取得
                answer_list = subcat_data.get("answer_list", [])
                execution_count = len(answer_list)

                if execution_count >= 15:
                    st.markdown("- 十分な実行回数により高い信頼性を確保")
                elif execution_count >= 10:
                    st.markdown("- 適切な実行回数により一定の信頼性を確保")
                elif execution_count >= 5:
                    st.markdown("- 最低限の実行回数による標準的な信頼性")
                else:
                    st.markdown("- 実行回数が少なく、結果は参考程度に留める")
            with col2:
                st.markdown("**バイアス影響度**")
                if 'ranking_variation' in locals() and ranking_variation:
                    max_variation = 0
                    max_variation_entity = "N/A"
                    for entity, variation_data in ranking_variation.items():
                        if isinstance(variation_data, dict):
                            rank_range = variation_data.get("rank_range", 0)
                            if rank_range > max_variation:
                                max_variation = rank_range
                                max_variation_entity = entity
                    st.markdown(f"- 最大順位変動: {max_variation}位 ({max_variation_entity})")
                    if max_variation == 0:
                        st.markdown("- 順位変動は皆無、バイアス影響なし")
                    elif max_variation <= 1:
                        st.markdown("- 順位変動は小さく、バイアス影響は限定的")
                    elif max_variation <= 2:
                        st.markdown("- 中程度の順位変動が見られ、軽微なバイアス影響あり")
                    else:
                        st.markdown("- 大きな順位変動があり、バイアス影響に注意が必要")
                else:
                    st.markdown("- バイアス影響度データがありません")

            # === 3. タブ別グラフ表示 ===
            st.subheader("📈 詳細グラフ分析")

            # 必要な関数をインポート
            from src.utils.plot_utils import (
                plot_ranking_similarity_for_ranking_analysis,
                plot_bias_indices_bar_for_ranking_analysis,
                plot_ranking_variation_heatmap
            )

            # タブ作成
            tab1, tab2, tab3 = st.tabs([
                "ランキング類似度分析", "バイアス指標棒グラフ",
                "ランキング変動ヒートマップ"
            ])

            with tab1:
                st.markdown("**ランキング類似度分析**")
                st.info("Google検索とPerplexityの検索結果の類似度を3つの指標で比較します：\n\n"
                       "・RBO：上位の検索結果がどれだけ一致しているか（1に近いほど上位の結果が同じ）\n"
                       "・Kendall Tau：順位の並びがどれだけ似ているか（1に近いほど順位の並びが同じ）\n"
                       "・Overlap Ratio：全体の検索結果がどれだけ重複しているか（1に近いほど同じURLが多い）", icon="ℹ️")

                if ranking_bias_data and selected_category in ranking_bias_data and selected_subcategory in ranking_bias_data[selected_category]:
                    try:
                        similarity_data = dashboard_data["analysis_results"]["citations_google_comparison"][selected_category][selected_subcategory]["ranking_similarity"]

                        fig = plot_ranking_similarity_for_ranking_analysis(similarity_data)
                        if fig:
                            st.pyplot(fig, use_container_width=True)
                            plt.close(fig)
                        else:
                            st.info("類似度分析データがありません")
                    except Exception as e:
                        st.error(f"グラフ描画エラー: {str(e)}")
                else:
                    st.warning("分析データが不足しています")

            with tab2:
                st.markdown("**バイアス指標棒グラフ**")
                st.info("各エンティティのバイアス指標を棒グラフで表示します。\n\n"
                       "バイアス指標は、各エンティティと他のエンティティとの順位差の平均値として計算されます。\n"
                       "例：AWSが他のエンティティより平均2.5位上位にいる場合、バイアス指標は+2.5となります。\n\n"
                       "・正の値（赤）：他のエンティティより平均的に上位に位置する傾向\n"
                       "・負の値（緑）：他のエンティティより平均的に下位に位置する傾向\n"
                       "・値の大きさ：順位差の大きさを示す（絶対値が大きいほど、他のエンティティとの順位差が大きい）", icon="ℹ️")

                if ranking_bias_data and selected_category in ranking_bias_data and selected_subcategory in ranking_bias_data[selected_category]:
                    try:
                        fig = plot_bias_indices_bar_for_ranking_analysis(ranking_bias_data, selected_category, selected_subcategory, selected_entities)
                        if fig:
                            st.pyplot(fig, use_container_width=True)
                            plt.close(fig)
                        else:
                            st.info("バイアス指標データがありません")
                    except Exception as e:
                        st.error(f"グラフ描画エラー: {str(e)}")
                else:
                    st.warning("分析データが不足しています")

            with tab3:
                st.markdown("**ランキング変動ヒートマップ**")
                st.info("各エンティティの順位変動を実行回数ごとにヒートマップで表示します。\n"
                       "色が濃いほど順位が低く、薄いほど順位が高いことを示します。", icon="ℹ️")

                if ranking_bias_data and selected_category in ranking_bias_data and selected_subcategory in ranking_bias_data[selected_category]:
                    try:
                        subcat_data = ranking_bias_data[selected_category][selected_subcategory]
                        entities_data = subcat_data.get("entities", {})

                        fig = plot_ranking_variation_heatmap(entities_data, selected_entities)
                        if fig:
                            st.pyplot(fig, use_container_width=True)
                            plt.close(fig)
                        else:
                            st.info("ヒートマップ用のデータがありません")
                    except Exception as e:
                        st.error(f"ヒートマップ描画エラー: {str(e)}")
                else:
                    st.warning("分析データが不足しています")

        else:
            st.info("perplexity_rankingsデータがありません")

    # 横スクロールラッパー閉じタグ
    st.markdown("</div>", unsafe_allow_html=True)

# --- CSS調整 ---
# （main-dashboard-areaやblock-container等のカスタムCSS・JSは削除）