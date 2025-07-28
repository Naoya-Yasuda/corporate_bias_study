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
import os
from src.utils.storage_config import get_base_paths
from src.components.auth import google_oauth_login, get_allowed_domains
import plotly.graph_objects as go

# キャッシュ付きデータ取得関数
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def get_cached_dashboard_data(_loader, selected_date):
    """
    ダッシュボードデータをキャッシュ付きで取得

    Parameters:
    -----------
    _loader : HybridDataLoader
        データローダーインスタンス（キャッシュキーから除外）
    selected_date : str
        選択された日付

    Returns:
    --------
    dict
        ダッシュボードデータ
    """
    return _loader.get_integrated_dashboard_data(selected_date)

# 非同期データ取得関数
def get_dashboard_data_async(_loader, selected_date):
    """
    ダッシュボードデータを非同期で取得（読み込み状況を表示）

    Parameters:
    -----------
    _loader : HybridDataLoader
        データローダーインスタンス
    selected_date : str
        選択された日付

    Returns:
    --------
    dict
        ダッシュボードデータ
    """
    # 読み込み開始時刻を記録
    start_time = datetime.now()

    # 読み込み状況を表示
    with st.spinner(f"📥 データ取得中: {selected_date}..."):
        try:
            data = get_cached_dashboard_data(_loader, selected_date)
            end_time = datetime.now()
            load_time = (end_time - start_time).total_seconds()

            # キャッシュ情報をサイドバーに表示
            if load_time < 0.1:  # キャッシュから取得された場合
                st.sidebar.success(f"💾 キャッシュから読み込み: {selected_date}")
            else:
                st.sidebar.info(f"📥 新規読み込み: {selected_date} ({load_time:.2f}秒)")

            if not data:
                st.error(f"❌ データ取得失敗: {selected_date}")

            return data
        except Exception as e:
            end_time = datetime.now()
            load_time = (end_time - start_time).total_seconds()
            st.error(f"❌ データ取得エラー: {selected_date} (読み込み時間: {load_time:.2f}秒)")
            st.error(f"エラー詳細: {str(e)}")
            return None

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

# タイトル
st.title("企業バイアス分析ダッシュボード")
st.markdown("AI検索サービスにおける企業優遇バイアスの可視化")

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
    if viz_type == "単日分析":
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
    # --- 時系列分析時はこのUIを表示しない ---
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
if viz_type == "時系列分析":
    loader_local = HybridDataLoader("local")
    loader_s3 = HybridDataLoader("s3")
    dates_local = set(loader_local.list_available_dates(mode="local"))
    dates_s3 = set(loader_s3.list_available_dates(mode="s3"))
    all_dates = sorted(list(dates_local | dates_s3))

    best_data_by_date = {}

    # 進捗バーを表示
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, date in enumerate(all_dates):
        # 進捗を更新
        progress = (i + 1) / len(all_dates)
        progress_bar.progress(progress)
        status_text.text(f"データ取得中... {i+1}/{len(all_dates)}: {date}")

        # 非同期でデータを取得
        data_local = get_dashboard_data_async(loader_local, date) if date in dates_local else None
        data_s3 = get_dashboard_data_async(loader_s3, date) if date in dates_s3 else None
        def get_meta(d):
            if d and "analysis_results" in d and "metadata" in d["analysis_results"]:
                meta = d["analysis_results"]["metadata"]
                return meta.get("execution_count", 0), meta.get("analysis_date", "")
            return 0, ""
        exec_local, date_local = get_meta(data_local)
        exec_s3, date_s3 = get_meta(data_s3)
        # 両方のデータがNoneの場合は除外
        if data_local is None and data_s3 is None:
            continue

        if exec_local > exec_s3:
            best_data_by_date[date] = (data_local, "local")
        elif exec_s3 > exec_local:
            best_data_by_date[date] = (data_s3, "s3")
        else:
            if date_local >= date_s3:
                best_data_by_date[date] = (data_local, "local")
            else:
                best_data_by_date[date] = (data_s3, "s3")

    # 進捗バーとステータステキストをクリア
    progress_bar.empty()
    status_text.empty()

    available_dates = sorted(best_data_by_date.keys())
        # ここから追加
    status_list = []
    for date in available_dates:
        data, source = best_data_by_date[date]
        # パス取得ロジックを修正
        paths = get_base_paths(date)
        if source == 'local':
            path = os.path.join(paths["integrated"], "bias_analysis_results.json")
        else:
            # S3パスはprefixをそのまま表示
            path = f"s3://{paths['integrated']}/bias_analysis_results.json"
        status = 'OK' if data is not None else '取得失敗'
        status_list.append(f"{date}｜{source}｜{status}｜{path}")

    with st.sidebar.expander("📊 データ取得状況", expanded=False):
        if status_list:
            for s in status_list:
                if "OK" in s:
                    st.success(s)
                elif "失敗" in s or "エラー" in s:
                    st.error(s)
                else:
                    st.info(s)
        else:
            st.info("データ取得状況がありません")
    # ここまで追加
    period_options = {
        "1ヶ月": 4,
        "3ヶ月": 12,
        "半年": 24,
        "1年": 52,
        "全期間": None
    }
    selected_period = st.sidebar.selectbox(
        "表示期間を選択",
        list(period_options.keys()),
        index=2,
        key="ts_period_selector"
    )
    period_n = period_options[selected_period]
    sorted_dates = sorted(available_dates, reverse=True)
    if period_n is not None:
        selected_dates = sorted(sorted_dates[:period_n], reverse=False)
    else:
        selected_dates = sorted(available_dates)
    if not selected_dates:
        st.info("利用可能なデータがありません")
        st.stop()
    latest_date = max(selected_dates)
    dashboard_data, source = best_data_by_date[latest_date]
    if dashboard_data is None:
        if source == 'local':
            file_path = os.path.join(get_base_paths(latest_date)['integrated'], 'bias_analysis_results.json')
        else:
            file_path = f"s3://{get_base_paths(latest_date)['integrated']}/bias_analysis_results.json"
        st.error(
            f"データ取得に失敗しました: {latest_date}\n"
            f"取得元: {source}\n"
            f"ファイルパス: {file_path}\n"
            "該当日付のデータファイルが存在しないか、読み込みに失敗しています。"
        )
        st.stop()
    if "analysis_results" not in dashboard_data:
        st.error(
            f"analysis_resultsが見つかりません: {latest_date}\n"
            f"取得元: {source}\n"
            f"ファイル内容: {str(dashboard_data)[:500]}..."
        )
        st.stop()
    analysis_data = dashboard_data["analysis_results"]
    sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
    all_categories = [c for c in sentiment_data.keys() if c not in ("全体", "all", "ALL", "All")]
    all_categories.sort()
    if not all_categories:
        st.info("カテゴリデータがありません")
        st.stop()
    selected_category = st.sidebar.selectbox(
        "カテゴリを選択",
        all_categories,
        key="ts_category_selector",
        index=0
    )
    all_subcategories = list(sentiment_data[selected_category].keys())
    all_subcategories.sort()
    if not all_subcategories:
        st.info("サブカテゴリデータがありません")
        st.stop()
    selected_subcategory = st.sidebar.selectbox(
        "サブカテゴリを選択",
        all_subcategories,
        key="ts_subcategory_selector",
        index=0
    )
    entities_data = sentiment_data[selected_category][selected_subcategory].get("entities", {})
    entities = list(entities_data.keys())
    if not entities:
        st.info("エンティティデータがありません")
        st.stop()
    selected_entities = st.sidebar.multiselect(
        "エンティティを選択（複数選択可）",
        entities,
        default=entities,  # 全件をデフォルトで表示
        key="ts_entities_selector"
    )
    if not selected_entities:
        st.info("エンティティを選択してください")
        st.stop()



    # --- 時系列データ収集 ---
    bi_timeseries = {entity: [] for entity in selected_entities}
    sentiment_timeseries = {entity: [] for entity in selected_entities}
    ranking_timeseries = {entity: [] for entity in selected_entities}

    # 新規追加：ランキング類似度と公式/非公式比率の時系列データ
    rbo_timeseries = []
    kendall_tau_timeseries = []
    overlap_ratio_timeseries = []
    google_official_ratio_timeseries = []
    citations_official_ratio_timeseries = []
    official_bias_delta_timeseries = []

    # 新規追加：ポジティブ/ネガティブ比率の時系列データ
    google_positive_ratio_timeseries = []
    google_negative_ratio_timeseries = []
    citations_positive_ratio_timeseries = []
    citations_negative_ratio_timeseries = []
    positive_bias_delta_timeseries = []

    date_labels = []

    for date in selected_dates:
        dashboard_data, source = best_data_by_date[date]
        if dashboard_data is None:
            continue
        analysis_data = dashboard_data["analysis_results"]
        sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
        ranking_data = analysis_data.get("ranking_bias_analysis", {})
        citations_google_data = analysis_data.get("citations_google_comparison", {})

        # 感情分析データ
        subcat_data = sentiment_data.get(selected_category, {}).get(selected_subcategory, {})
        entities_data = subcat_data.get("entities", {})
        # Noneやdict以外を除外
        entities_data = {k: v for k, v in entities_data.items() if isinstance(v, dict)}

        # ランキング分析データ
        ranking_subcat_data = ranking_data.get(selected_category, {}).get(selected_subcategory, {})
        ranking_entities_data = ranking_subcat_data.get("entities", {})

        # 新規追加：ランキング類似度データ
        similarity_data = citations_google_data.get(selected_category, {}).get(selected_subcategory, {}).get("ranking_similarity", {})
        rbo_timeseries.append(similarity_data.get("rbo_score"))
        kendall_tau_timeseries.append(similarity_data.get("kendall_tau"))
        overlap_ratio_timeseries.append(similarity_data.get("overlap_ratio"))

        # 新規追加：公式/非公式比率データ
        official_data = citations_google_data.get(selected_category, {}).get(selected_subcategory, {}).get("official_domain_analysis", {})
        google_official_ratio_timeseries.append(official_data.get("google_official_ratio"))
        citations_official_ratio_timeseries.append(official_data.get("citations_official_ratio"))
        official_bias_delta_timeseries.append(official_data.get("official_bias_delta"))

        # 新規追加：ポジティブ/ネガティブ比率データ
        sentiment_comparison_data = citations_google_data.get(selected_category, {}).get(selected_subcategory, {}).get("sentiment_comparison", {})
        google_sentiment_dist = sentiment_comparison_data.get("google_sentiment_distribution", {})
        citations_sentiment_dist = sentiment_comparison_data.get("citations_sentiment_distribution", {})

        google_positive_ratio_timeseries.append(google_sentiment_dist.get("positive"))
        google_negative_ratio_timeseries.append(google_sentiment_dist.get("negative"))
        citations_positive_ratio_timeseries.append(citations_sentiment_dist.get("positive"))
        citations_negative_ratio_timeseries.append(citations_sentiment_dist.get("negative"))
        positive_bias_delta_timeseries.append(sentiment_comparison_data.get("positive_bias_delta"))

        date_labels.append(date)

        for entity in selected_entities:
            # BI値
            bi = None
            if entity in entities_data:
                bi = entities_data[entity].get("basic_metrics", {}).get("normalized_bias_index")
            bi_timeseries[entity].append(bi)

            # 感情スコア差分（raw_delta）
            sentiment_avg = None
            if entity in entities_data:
                sentiment_avg = entities_data[entity].get("basic_metrics", {}).get("raw_delta")
            sentiment_timeseries[entity].append(sentiment_avg)

            # ランキング平均（正しいパスで取得）
            ranking_avg = None
            if entity in ranking_entities_data:
                ranking_avg = ranking_entities_data[entity].get("avg_rank")
            ranking_timeseries[entity].append(ranking_avg)

    # データが取得できたかチェック
    if not date_labels:
        st.error("選択された期間でデータを取得できませんでした。別の期間を選択してください。")
        st.stop()

    # --- 時系列分析ダッシュボード ---
    st.subheader(f"時系列分析｜{selected_category}｜{selected_subcategory}")

    # タブで可視化タイプを選択
    ts_tabs = st.tabs(["BI値時系列推移", "感情スコア時系列推移", "ランキング時系列推移", "ランキング類似度時系列推移", "公式/非公式比率時系列推移", "ポジティブ/ネガティブ比率時系列推移"])
    import matplotlib.pyplot as plt

    # BI値時系列推移タブ
    with ts_tabs[0]:
        st.info("各エンティティのNormalized Bias Index（バイアス指標）の時系列推移を表示します。値が大きいほどバイアスが強いことを示します。", icon="ℹ️")

        # データの有効性チェック
        valid_bi_data = {k: v for k, v in bi_timeseries.items() if any(x is not None for x in v)}

        if not valid_bi_data:
            st.warning("BI値データが利用できません。normalized_bias_indexが存在しないか、データ形式が正しくありません。")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))
            for entity, values in valid_bi_data.items():
                # None値を除外してプロット
                valid_values = [(i, v) for i, v in enumerate(values) if v is not None]
                if valid_values:
                    x_indices, y_values = zip(*valid_values)
                    x_dates = [date_labels[i] for i in x_indices]
                    ax.plot(x_dates, y_values, marker="o", label=entity, linewidth=2, markersize=6)

            ax.set_xlabel("日付")
            ax.set_ylabel("BI値（normalized_bias_index）")
            ax.set_title(f"BI値の時系列推移（{selected_category} - {selected_subcategory}）")
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            # 0.0の基準線を追加
            ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 統計情報の表示
            with st.expander("BI値統計情報", expanded=False):
                for entity, values in valid_bi_data.items():
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        avg_val = sum(valid_values) / len(valid_values)
                        min_val = min(valid_values)
                        max_val = max(valid_values)
                        bias_direction = "正のバイアス" if avg_val > 0 else "負のバイアス" if avg_val < 0 else "バイアスなし"
                        st.write(f"**{entity}**: 平均BI={avg_val:.3f}, 最小={min_val:.3f}, 最大={max_val:.3f} ({bias_direction})")

        # 感情スコア時系列推移タブ
    with ts_tabs[1]:
        st.info("各エンティティの感情スコア差分（raw_delta）の時系列推移を表示します。値が高いほど好意的なバイアスを示します。", icon="ℹ️")

        # データの有効性チェック
        valid_sentiment_data = {k: v for k, v in sentiment_timeseries.items() if any(x is not None for x in v)}

        if not valid_sentiment_data:
            st.warning("感情スコアデータが利用できません。raw_deltaが存在しないか、データ形式が正しくありません。")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))
            for entity, values in valid_sentiment_data.items():
                # None値を除外してプロット
                valid_values = [(i, v) for i, v in enumerate(values) if v is not None]
                if valid_values:
                    x_indices, y_values = zip(*valid_values)
                    x_dates = [date_labels[i] for i in x_indices]
                    ax.plot(x_dates, y_values, marker="s", label=entity, linewidth=2, markersize=6)

            ax.set_xlabel("日付")
            ax.set_ylabel("感情スコア差分（raw_delta）")
            ax.set_title(f"感情スコア差分の時系列推移（{selected_category} - {selected_subcategory}）")
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            # 0.0の基準線を追加
            ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 統計情報の表示
            with st.expander("感情スコア統計情報", expanded=False):
                for entity, values in valid_sentiment_data.items():
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        avg_val = sum(valid_values) / len(valid_values)
                        min_val = min(valid_values)
                        max_val = max(valid_values)
                        bias_direction = "好意的バイアス" if avg_val > 0 else "否定的バイアス" if avg_val < 0 else "バイアスなし"
                        st.write(f"**{entity}**: 平均差分={avg_val:.2f}, 最小={min_val:.2f}, 最大={max_val:.2f} ({bias_direction})")

    # ランキング時系列推移タブ
    with ts_tabs[2]:
        st.info("各エンティティの平均ランキングの時系列推移を表示します。値が小さいほど上位ランキングを示します。", icon="ℹ️")

        # データの有効性チェック
        valid_ranking_data = {k: v for k, v in ranking_timeseries.items() if any(x is not None for x in v)}

        if not valid_ranking_data:
            st.warning("ランキングデータが利用できません。avg_rankが存在しないか、データ形式が正しくありません。")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))
            for entity, values in valid_ranking_data.items():
                # None値を除外してプロット
                valid_values = [(i, v) for i, v in enumerate(values) if v is not None]
                if valid_values:
                    x_indices, y_values = zip(*valid_values)
                    x_dates = [date_labels[i] for i in x_indices]
                    ax.plot(x_dates, y_values, marker="^", label=entity, linewidth=2, markersize=6)

            ax.set_xlabel("日付")
            ax.set_ylabel("平均ランキング（avg_rank）")
            ax.set_title(f"ランキングの時系列推移（{selected_category} - {selected_subcategory}）")
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 統計情報の表示
            with st.expander("ランキング統計情報", expanded=False):
                for entity, values in valid_ranking_data.items():
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        avg_val = sum(valid_values) / len(valid_values)
                        min_val = min(valid_values)
                        max_val = max(valid_values)
                        st.write(f"**{entity}**: 平均ランク={avg_val:.1f}, 最高位={min_val:.0f}, 最低位={max_val:.0f}")

    # ランキング類似度時系列推移タブ
    with ts_tabs[3]:
        st.info("Google検索とPerplexityの検索結果の類似度指標の時系列推移を表示します。\n\n"
               "・RBO：上位の検索結果がどれだけ一致しているか（1に近いほど上位の結果が同じ）\n"
               "・Kendall Tau：順位の並びがどれだけ似ているか（1に近いほど順位の並びが同じ）\n"
               "・Overlap Ratio：全体の検索結果がどれだけ重複しているか（1に近いほど同じURLが多い）", icon="ℹ️")

        # データの有効性チェック
        valid_rbo = [v for v in rbo_timeseries if v is not None]
        valid_kendall = [v for v in kendall_tau_timeseries if v is not None]
        valid_overlap = [v for v in overlap_ratio_timeseries if v is not None]

        if not valid_rbo and not valid_kendall and not valid_overlap:
            st.warning("ランキング類似度データが利用できません。ranking_similarityが存在しないか、データ形式が正しくありません。")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))

            # RBOスコア
            if valid_rbo:
                valid_indices = [i for i, v in enumerate(rbo_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_rbo, marker="o", label="RBO", linewidth=2, markersize=6, color="blue")

            # Kendall Tau
            if valid_kendall:
                valid_indices = [i for i, v in enumerate(kendall_tau_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_kendall, marker="s", label="Kendall Tau", linewidth=2, markersize=6, color="orange")

            # Overlap Ratio
            if valid_overlap:
                valid_indices = [i for i, v in enumerate(overlap_ratio_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_overlap, marker="^", label="Overlap Ratio", linewidth=2, markersize=6, color="green")

            ax.set_xlabel("日付")
            ax.set_ylabel("類似度スコア")
            ax.set_title(f"ランキング類似度の時系列推移（{selected_category} - {selected_subcategory}）")
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 1)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 統計情報の表示
            with st.expander("ランキング類似度統計情報", expanded=False):
                if valid_rbo:
                    avg_rbo = sum(valid_rbo) / len(valid_rbo)
                    min_rbo = min(valid_rbo)
                    max_rbo = max(valid_rbo)
                    st.write(f"**RBO**: 平均={avg_rbo:.3f}, 最小={min_rbo:.3f}, 最大={max_rbo:.3f}")

                if valid_kendall:
                    avg_kendall = sum(valid_kendall) / len(valid_kendall)
                    min_kendall = min(valid_kendall)
                    max_kendall = max(valid_kendall)
                    st.write(f"**Kendall Tau**: 平均={avg_kendall:.3f}, 最小={min_kendall:.3f}, 最大={max_kendall:.3f}")

                if valid_overlap:
                    avg_overlap = sum(valid_overlap) / len(valid_overlap)
                    min_overlap = min(valid_overlap)
                    max_overlap = max(valid_overlap)
                    st.write(f"**Overlap Ratio**: 平均={avg_overlap:.3f}, 最小={min_overlap:.3f}, 最大={max_overlap:.3f}")

    # 公式/非公式比率時系列推移タブ
    with ts_tabs[4]:
        st.info("Google検索とPerplexityの公式サイト比率の時系列推移を表示します。\n\n"
               "・Google公式比率：Google検索結果における公式サイトの割合\n"
               "・Citations公式比率：Perplexity検索結果における公式サイトの割合\n"
               "・バイアス差分：Google比率 - Citations比率（正の値はGoogleが公式サイトを多く表示）", icon="ℹ️")

        # データの有効性チェック
        valid_google_ratio = [v for v in google_official_ratio_timeseries if v is not None]
        valid_citations_ratio = [v for v in citations_official_ratio_timeseries if v is not None]
        valid_bias_delta = [v for v in official_bias_delta_timeseries if v is not None]

        if not valid_google_ratio and not valid_citations_ratio and not valid_bias_delta:
            st.warning("公式/非公式比率データが利用できません。official_domain_analysisが存在しないか、データ形式が正しくありません。")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Google公式比率
            if valid_google_ratio:
                valid_indices = [i for i, v in enumerate(google_official_ratio_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_google_ratio, marker="o", label="Google公式比率", linewidth=2, markersize=6, color="blue")

            # Citations公式比率
            if valid_citations_ratio:
                valid_indices = [i for i, v in enumerate(citations_official_ratio_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_citations_ratio, marker="s", label="Citations公式比率", linewidth=2, markersize=6, color="orange")

            # バイアス差分
            if valid_bias_delta:
                valid_indices = [i for i, v in enumerate(official_bias_delta_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_bias_delta, marker="^", label="バイアス差分", linewidth=2, markersize=6, color="red")

            ax.set_xlabel("日付")
            ax.set_ylabel("比率・差分")
            ax.set_title(f"公式/非公式比率の時系列推移（{selected_category} - {selected_subcategory}）")
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(-0.5, 1.0)
            # 0.0の基準線を追加
            ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 統計情報の表示
            with st.expander("公式/非公式比率統計情報", expanded=False):
                if valid_google_ratio:
                    avg_google = sum(valid_google_ratio) / len(valid_google_ratio)
                    min_google = min(valid_google_ratio)
                    max_google = max(valid_google_ratio)
                    st.write(f"**Google公式比率**: 平均={avg_google:.3f}, 最小={min_google:.3f}, 最大={max_google:.3f}")

                if valid_citations_ratio:
                    avg_citations = sum(valid_citations_ratio) / len(valid_citations_ratio)
                    min_citations = min(valid_citations_ratio)
                    max_citations = max(valid_citations_ratio)
                    st.write(f"**Citations公式比率**: 平均={avg_citations:.3f}, 最小={min_citations:.3f}, 最大={max_citations:.3f}")

                if valid_bias_delta:
                    avg_bias = sum(valid_bias_delta) / len(valid_bias_delta)
                    min_bias = min(valid_bias_delta)
                    max_bias = max(valid_bias_delta)
                    bias_trend = "Google優位" if avg_bias > 0 else "Citations優位" if avg_bias < 0 else "均衡"
                    st.write(f"**バイアス差分**: 平均={avg_bias:.3f}, 最小={min_bias:.3f}, 最大={max_bias:.3f} ({bias_trend})")

    # ポジティブ/ネガティブ比率時系列推移タブ
    with ts_tabs[5]:
        st.info("Google検索とPerplexityの検索結果の感情分析比率の時系列推移を表示します。\n\n"
               "・Googleポジティブ比率：Google検索結果のポジティブ感情の割合\n"
               "・Citationsポジティブ比率：Perplexity検索結果のポジティブ感情の割合\n"
               "・ポジティブバイアス差分：両者のポジティブ比率の差（正の値はGoogle優位）", icon="ℹ️")

        # データの有効性チェック
        valid_google_positive = [v for v in google_positive_ratio_timeseries if v is not None]
        valid_google_negative = [v for v in google_negative_ratio_timeseries if v is not None]
        valid_citations_positive = [v for v in citations_positive_ratio_timeseries if v is not None]
        valid_citations_negative = [v for v in citations_negative_ratio_timeseries if v is not None]
        valid_positive_bias_delta = [v for v in positive_bias_delta_timeseries if v is not None]

        if not valid_google_positive and not valid_citations_positive and not valid_positive_bias_delta:
            st.warning("ポジティブ/ネガティブ比率データが利用できません。sentiment_comparisonが存在しないか、データ形式が正しくありません。")
        else:
            fig, ax = plt.subplots(figsize=(10, 6))

            # Googleポジティブ比率
            if valid_google_positive:
                valid_indices = [i for i, v in enumerate(google_positive_ratio_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_google_positive, marker="o", label="Googleポジティブ比率", linewidth=2, markersize=6, color="blue")

            # Citationsポジティブ比率
            if valid_citations_positive:
                valid_indices = [i for i, v in enumerate(citations_positive_ratio_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_citations_positive, marker="s", label="Citationsポジティブ比率", linewidth=2, markersize=6, color="orange")

            # ポジティブバイアス差分
            if valid_positive_bias_delta:
                valid_indices = [i for i, v in enumerate(positive_bias_delta_timeseries) if v is not None]
                valid_dates = [date_labels[i] for i in valid_indices]
                ax.plot(valid_dates, valid_positive_bias_delta, marker="^", label="ポジティブバイアス差分", linewidth=2, markersize=6, color="red")

            ax.set_xlabel("日付")
            ax.set_ylabel("比率・差分")
            ax.set_title(f"ポジティブ/ネガティブ比率の時系列推移（{selected_category} - {selected_subcategory}）")
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(-1.0, 1.0)
            # 0.0の基準線を追加
            ax.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 統計情報の表示
            with st.expander("ポジティブ/ネガティブ比率統計情報", expanded=False):
                if valid_google_positive:
                    avg_google_pos = sum(valid_google_positive) / len(valid_google_positive)
                    min_google_pos = min(valid_google_positive)
                    max_google_pos = max(valid_google_positive)
                    st.write(f"**Googleポジティブ比率**: 平均={avg_google_pos:.3f}, 最小={min_google_pos:.3f}, 最大={max_google_pos:.3f}")

                if valid_citations_positive:
                    avg_citations_pos = sum(valid_citations_positive) / len(valid_citations_positive)
                    min_citations_pos = min(valid_citations_positive)
                    max_citations_pos = max(valid_citations_positive)
                    st.write(f"**Citationsポジティブ比率**: 平均={avg_citations_pos:.3f}, 最小={min_citations_pos:.3f}, 最大={max_citations_pos:.3f}")

                if valid_positive_bias_delta:
                    avg_positive_bias = sum(valid_positive_bias_delta) / len(valid_positive_bias_delta)
                    min_positive_bias = min(valid_positive_bias_delta)
                    max_positive_bias = max(valid_positive_bias_delta)
                    bias_trend = "Google優位" if avg_positive_bias > 0 else "Citations優位" if avg_positive_bias < 0 else "均衡"
                    st.write(f"**ポジティブバイアス差分**: 平均={avg_positive_bias:.3f}, 最小={min_positive_bias:.3f}, 最大={max_positive_bias:.3f} ({bias_trend})")

elif viz_type == "単日分析":
    # 非同期でデータを取得（読み込み状況を表示）
    dashboard_data = get_dashboard_data_async(loader, selected_date)
    analysis_data = dashboard_data["analysis_results"] if dashboard_data else None

    if not analysis_data:
        st.error(f"分析データの読み込みに失敗しました: {selected_date}")
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
            default=entities  # 全件をデフォルトで表示
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
            with st.expander("プロンプト", expanded=False):
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
                    # severity = entity_data.get("severity_score", {}).get("severity_score", 0)
                    severity = (entity_data.get("severity_score") or {}).get("severity_score", 0)
                    if isinstance(severity, dict):
                        score = severity.get("severity_score")
                    else:
                        score = severity
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
            st.info("各企業のバイアス指標を棒グラフで表示します。この指標は「企業名を知った時の評価」と「企業名を隠した時の評価」の差を表します。\n\n• 正の値（赤）：企業名を知ると評価が上がる（好意的なバイアス）\n• 負の値（緑）：企業名を知ると評価が下がる（否定的なバイアス）\n• 値の絶対値が大きいほど、企業名による影響が強いことを示します", icon="ℹ️")
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
            st.info("各エンティティの統計的有意性（p値）をヒートマップで表示します。色が濃いほど有意性(結果が偶然でない可能性)が高いことを示します。", icon="ℹ️")
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
                    default=all_entities,  # 全件をデフォルトで表示
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
            st.markdown("**Google検索データテーブル**:**※APIの仕様で引用URL（結果数）は各10件固定**")
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

                            # 公式/非公式の統計（公式結果のみ）
                            official_official_count = 0
                            official_unofficial_count = 0

                            # official_resultsの公式/非公式カウント
                            for result in entity_data.get("official_results", []):
                                if result.get("is_official") == "official":
                                    official_official_count += 1
                                else:
                                    official_unofficial_count += 1

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
                                "公式": official_official_count,
                                "非公式": official_unofficial_count,
                                "ポジティブ": positive_count,
                                "ネガティブ": negative_count,
                                "中立": neutral_count,
                                "感情不明": unknown_count,
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
            st.markdown("**Perplexity Citationsデータテーブル**: **※APIの仕様で引用URL（結果数）は各5件固定**")
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

                            # 公式/非公式の統計（公式結果のみ）
                            official_official_count = 0
                            official_unofficial_count = 0

                            # official_resultsの公式/非公式カウント
                            for result in entity_data.get("official_results", []):
                                if result.get("is_official") == "official":
                                    official_official_count += 1
                                else:
                                    official_unofficial_count += 1

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
                                "公式": official_official_count,
                                "非公式": official_unofficial_count,
                                "ポジティブ": positive_count,
                                "ネガティブ": negative_count,
                                "中立": neutral_count,
                                "感情不明": unknown_count,
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

            # === 4. 比較分析結果表示（タブ形式） ===
            if similarity_data:
                title = f"{selected_category} - {selected_subcategory}"

                # タブ作成
                tab1, tab2, tab3 = st.tabs([
                    "ランキング類似度分析", "公式ドメイン比較", "感情分析比較"
                ])

                with tab1:
                    st.markdown("**ランキング類似度分析**")
                    st.info("Google検索とPerplexityの検索結果の類似度を3つの指標で比較します：\n\n"
                           "・RBO：上位の検索結果がどれだけ一致しているか（1に近いほど上位の結果が同じ）\n"
                           "・Kendall Tau：順位の並びがどれだけ似ているか（1に近いほど順位の並びが同じ）\n"
                           "・Overlap Ratio：全体の検索結果がどれだけ重複しているか（1に近いほど同じURLが多い）", icon="ℹ️")

                    fig = plot_ranking_similarity(similarity_data, title)
                    st.pyplot(fig, use_container_width=True)

                                        # グラフ解説（metrics_validationの解釈情報を使用）
                    if selected_category in citations_data and selected_subcategory in citations_data[selected_category]:
                        subcat_comparison_data = citations_data[selected_category][selected_subcategory]
                        ranking_similarity = subcat_comparison_data.get("ranking_similarity", {})
                        metrics_validation = ranking_similarity.get("metrics_validation", {})

                        if metrics_validation:
                            st.markdown("**📊 グラフ解説**")

                            # 統合解釈
                            interpretation = metrics_validation.get("interpretation", "")
                            if interpretation:
                                st.markdown(f"**統合解釈**: {interpretation}")

                            # 個別指標解釈
                            kendall_interpretation = metrics_validation.get("kendall_tau_interpretation", "")
                            rbo_interpretation = metrics_validation.get("rbo_interpretation", "")

                            if kendall_interpretation:
                                st.markdown(f"**Kendall Tau解釈**: {kendall_interpretation}")
                            if rbo_interpretation:
                                st.markdown(f"**RBO解釈**: {rbo_interpretation}")

                            # 共通サイト情報
                            common_count = metrics_validation.get("common_items_count", 0)
                            overlap_percentage = metrics_validation.get("overlap_percentage", 0)
                            if common_count > 0:
                                st.markdown(f"**共通サイト**: {common_count}個（重複率: {overlap_percentage}%）")
                        else:
                            st.info("グラフ解説データがありません")
                    else:
                        st.info("グラフ解説データがありません")

                with tab2:
                    st.markdown("**公式ドメイン比較**")
                    st.info("Google検索とPerplexityの検索結果における公式ドメインの露出比率を比較します。\n\n"
                           "・Google公式ドメイン率：Google検索結果中の公式サイト比率\n"
                           "・Perplexity公式ドメイン率：Perplexity引用中の公式サイト比率\n"
                           "・バイアスデルタ：両者の差分（正の値はGoogleが公式サイトを多く表示）", icon="ℹ️")

                    # 公式ドメイン比較データの取得と表示
                    if selected_category in citations_data and selected_subcategory in citations_data[selected_category]:
                        subcat_comparison_data = citations_data[selected_category][selected_subcategory]
                        official_data = subcat_comparison_data.get("official_domain_analysis", {})

                        if official_data:
                            fig = plot_official_domain_comparison(official_data, title)
                            st.pyplot(fig, use_container_width=True)

                            # グラフ解説
                            st.markdown("**📊 グラフ解説**")

                            google_ratio = official_data.get("google_official_ratio", 0)
                            citations_ratio = official_data.get("citations_official_ratio", 0)
                            bias_delta = official_data.get("official_bias_delta", 0)

                            # 解釈の生成
                            if bias_delta > 0.1:
                                interpretation = f"Google検索（{google_ratio:.1%}）がPerplexity（{citations_ratio:.1%}）より公式サイトを多く表示しており、Google側に公式サイト露出のバイアスがあります"
                            elif bias_delta < -0.1:
                                interpretation = f"Perplexity（{citations_ratio:.1%}）がGoogle検索（{google_ratio:.1%}）より公式サイトを多く表示しており、Perplexity側に公式サイト露出のバイアスがあります"
                            else:
                                interpretation = f"Google検索（{google_ratio:.1%}）とPerplexity（{citations_ratio:.1%}）の公式サイト表示は均衡しており、大きなバイアスは見られません"

                            st.markdown(f"**解釈**: {interpretation}")

                            # バイアスデルタの詳細説明
                            if abs(bias_delta) > 0.2:
                                st.markdown(f"**バイアス強度**: 強い（差分: {bias_delta:.1%}）")
                            elif abs(bias_delta) > 0.1:
                                st.markdown(f"**バイアス強度**: 中程度（差分: {bias_delta:.1%}）")
                            else:
                                st.markdown(f"**バイアス強度**: 弱い（差分: {bias_delta:.1%}）")
                        else:
                            st.info("公式ドメイン比較データがありません")
                    else:
                        st.info("公式ドメイン比較データがありません")

                with tab3:
                    st.markdown("**感情分析比較**")
                    st.info("Google検索とPerplexityの検索結果における感情分析結果の分布を比較します。\n\n"

                           "・不明：感情分析ができない結果の比率", icon="ℹ️")

                    # 感情分析比較データの取得と表示
                    if selected_category in citations_data and selected_subcategory in citations_data[selected_category]:
                        subcat_comparison_data = citations_data[selected_category][selected_subcategory]
                        sentiment_data = subcat_comparison_data.get("sentiment_comparison", {})

                        if sentiment_data:
                            fig = plot_sentiment_comparison(sentiment_data, title)
                            st.pyplot(fig, use_container_width=True)

                            # グラフ解説
                            st.markdown("**📊 グラフ解説**")

                            google_dist = sentiment_data.get("google_sentiment_distribution", {})
                            citations_dist = sentiment_data.get("citations_sentiment_distribution", {})
                            sentiment_correlation = sentiment_data.get("sentiment_correlation", 0)

                            # 主要感情の比較
                            google_positive = google_dist.get("positive", 0)
                            google_negative = google_dist.get("negative", 0)
                            citations_positive = citations_dist.get("positive", 0)
                            citations_negative = citations_dist.get("negative", 0)

                            # 感情傾向の解釈
                            if sentiment_correlation > 0.7:
                                correlation_interpretation = "非常に類似"
                            elif sentiment_correlation > 0.5:
                                correlation_interpretation = "類似"
                            elif sentiment_correlation > 0.3:
                                correlation_interpretation = "やや類似"
                            else:
                                correlation_interpretation = "異なる"

                            # ポジティブ感情の比較
                            positive_diff = google_positive - citations_positive
                            if abs(positive_diff) > 0.1:
                                if positive_diff > 0:
                                    positive_interpretation = f"Google検索（{google_positive:.1%}）がPerplexity（{citations_positive:.1%}）よりポジティブな結果を多く表示"
                                else:
                                    positive_interpretation = f"Perplexity（{citations_positive:.1%}）がGoogle検索（{google_positive:.1%}）よりポジティブな結果を多く表示"
                            else:
                                positive_interpretation = f"両者のポジティブ感情比率は均衡（Google: {google_positive:.1%}, Perplexity: {citations_positive:.1%}）"

                            st.markdown(f"**感情相関**: {sentiment_correlation:.3f}（{correlation_interpretation}）")
                            st.markdown(f"**ポジティブ感情比較**: {positive_interpretation}")

                            # ネガティブ感情の比較
                            negative_diff = google_negative - citations_negative
                            if abs(negative_diff) > 0.1:
                                if negative_diff > 0:
                                    negative_interpretation = f"Google検索（{google_negative:.1%}）がPerplexity（{citations_negative:.1%}）よりネガティブな結果を多く表示"
                                else:
                                    negative_interpretation = f"Perplexity（{citations_negative:.1%}）がGoogle検索（{google_negative:.1%}）よりネガティブな結果を多く表示"
                            else:
                                negative_interpretation = f"両者のネガティブ感情比率は均衡（Google: {google_negative:.1%}, Perplexity: {citations_negative:.1%}）"

                            st.markdown(f"**ネガティブ感情比較**: {negative_interpretation}")
                        else:
                            st.info("感情分析比較データがありません")
                    else:
                        st.info("感情分析比較データがありません")

                # 詳細分析データ表示（全タブ共通）
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

        # 新タブ構成
        main_tabs = st.tabs(["サブカテゴリ分析", "全体統合分析", "市場分析"])

        # 重篤度スコアの説明文を変数にまとめて使い回す
        severity_info_text = """
**重篤度スコアの計算式**
`severity = abs_bi × |cliffs_delta| × (1 - p値) × 安定性スコア`（最大10で丸める）
- **abs_bi**: バイアス指標（normalized_bias_index等）
- **cliffs_delta**: 効果量（Cliff's delta等）
- **p値**: 統計的有意性（小さいほど重み大）
- **安定性スコア**: ばらつきが小さいほど重み大

これにより「大きく・有意で・安定したバイアスのみが高スコア」となります。
"""

        # --- サブカテゴリ分析タブ ---
        with main_tabs[0]:
            st.markdown(f"### サブカテゴリ分析: {selected_category} / {selected_subcategory}")

            # 重篤度スコアの計算式をexpanderで表示
            with st.expander("重篤度スコアの計算式", expanded=False):
                st.markdown(severity_info_text)
            # サブカテゴリ単位のデータ抽出
            sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
            subcat_data = sentiment_data.get(selected_category, {}).get(selected_subcategory, {})
            entities = subcat_data.get("entities", {})
            # Noneやdict以外を除外
            entities = {k: v for k, v in entities.items() if isinstance(v, dict)}

            # サブカテゴリ重篤度ランキング
            st.markdown("#### 重篤度ランキング（サブカテゴリ内）")
            if not entities:
                st.info("サブカテゴリ内の重篤度ランキングデータがありません")
            else:
                ranking_rows = []
                for entity, entity_data in entities.items():
                    if not isinstance(entity_data, dict):
                        continue  # dict型以外はスキップ
                    # severity = entity_data.get("severity_score", {}).get("severity_score", 0)
                    severity = (entity_data.get("severity_score") or {}).get("severity_score", 0)
                    ranking_rows.append({
                        "エンティティ": entity,
                        "重篤度スコア": f"{severity:.3f}",
                        "重篤度レベル": "重篤" if severity > 3.0 else "軽微"
                    })
                df_severity = pd.DataFrame(ranking_rows).sort_values(by="重篤度スコア", ascending=False)
                st.dataframe(df_severity, use_container_width=True, hide_index=True)

            # サブカテゴリ感情-ランキング相関
            st.markdown("#### 感情-ランキング相関（サブカテゴリ内）")

            # 計算方法の説明を追加
            with st.expander("相関係数の計算方法", expanded=False):
                st.markdown("""
                **計算対象**: 感情分析のbias_index vs ランキング分析のavg_rank

                **計算手順**:
                1. 共通エンティティの抽出（感情分析とランキング分析の両方に存在する企業）
                2. ランキング値の逆転処理（数値が大きいほど上位になるように）
                   - 元のランキング: 1位=1, 2位=2, 3位=3...
                   - 逆転後: 1位=5, 2位=4, 3位=3...（5社の場合）
                3. Pearson相関係数の計算
                4. Spearman相関係数の計算

                **解釈**:
                - 正の相関: 感情分析で好意的な企業がランキングでも上位
                - 負の相関: 感情分析で好意的な企業がランキングでは下位
                - 相関なし: 感情分析とランキングが独立した評価
                """)

            cross_insights = analysis_data.get("cross_analysis_insights", {})
            sentiment_corr = cross_insights.get("sentiment_ranking_correlation", {})
            subcat_corr = sentiment_corr.get(selected_category, {}).get(selected_subcategory, {})
            if subcat_corr:
                corr = subcat_corr.get('correlation', 0)
                pval = subcat_corr.get('p_value', None)
                spearman = subcat_corr.get('spearman', None)
                n_entities = subcat_corr.get('n_entities', None)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Pearson相関係数", f"{corr:.3f}")
                with col2:
                    if spearman is not None:
                        st.metric("Spearman相関係数", f"{spearman:.3f}")
                with col3:
                    if n_entities is not None:
                        st.metric("分析対象企業数", f"{n_entities}")

                if pval is not None:
                    st.markdown(f"**p値**: {pval:.3f}")
                    if pval < 0.05:
                        sig_text = "統計的に有意 (p < 0.05)"
                    else:
                        sig_text = "統計的に有意でない (p >= 0.05)"
                else:
                    sig_text = "p値データなし"

                if corr > 0.3:
                    corr_text = "正の相関：感情分析とランキングで同じ企業が優遇される傾向"
                elif corr < -0.3:
                    corr_text = "負の相関：感情分析とランキングで異なる評価基準が働く傾向"
                else:
                    corr_text = "相関なし：感情分析とランキングが独立した評価"
                st.markdown(f"**解釈**: {corr_text} / {sig_text}")
            else:
                st.info("サブカテゴリ内の相関データがありません")

            # サブカテゴリバイアスパターン
            st.markdown("#### バイアスパターン・解説（サブカテゴリ内）")
            cat_analysis = subcat_data.get("category_level_analysis", {})
            bias_dist = cat_analysis.get("bias_distribution", {})
            if bias_dist:
                st.markdown(f"- 正のバイアス数: {bias_dist.get('positive_bias_count', 'N/A')}")
                st.markdown(f"- 負のバイアス数: {bias_dist.get('negative_bias_count', 'N/A')}")
                st.markdown(f"- ニュートラル数: {bias_dist.get('neutral_count', 'N/A')}")
                st.markdown(f"- バイアス範囲: {bias_dist.get('bias_range', 'N/A')}")
            else:
                st.info("バイアス分布データがありません")
            # 解釈（もしあれば）
            if 'interpretation' in cat_analysis:
                st.markdown(f"解釈: {cat_analysis['interpretation']}")
            else:
                st.info("サブカテゴリ単位の解釈データがありません")

        # --- 全体統合分析タブ ---
        with main_tabs[1]:
            st.markdown("### 全体統合分析")

            # 重篤度スコアの計算式をexpanderで表示
            with st.expander("重篤度スコアの計算式", expanded=False):
                st.markdown(severity_info_text)

            # 全体重篤度ランキング
            st.markdown("#### 全体重篤度ランキング")
            def extract_severity_ranking(analysis_data):
                severity_data = {}
                relative_bias = analysis_data.get("relative_bias_analysis", {})
                for category, category_data in relative_bias.items():
                    for subcategory, subcat_data in category_data.items():
                        entities = subcat_data.get("entities", {})
                        for entity, entity_data in entities.items():
                            if not isinstance(entity_data, dict):
                                continue
                            severity_score = (entity_data.get("severity_score") or {}).get("severity_score", 0)
                            severity_data[f"{category}/{subcategory}/{entity}"] = severity_score
                return dict(sorted(severity_data.items(), key=lambda x: x[1], reverse=True))
            severity_ranking = extract_severity_ranking(analysis_data)
            if severity_ranking:
                ranking_rows = []
                for i, (entity_path, severity) in enumerate(severity_ranking.items(), 1):
                    path_parts = entity_path.split('/')
                    if len(path_parts) >= 3:
                        category = path_parts[0]
                        subcategory = path_parts[1]
                        entity = path_parts[2]
                        display_name = f"{category}/{subcategory} - {entity}"
                    else:
                        display_name = entity_path
                    ranking_rows.append({
                        "順位": i,
                        "エンティティ": display_name,
                        "重篤度スコア": f"{severity:.3f}",
                        "重篤度レベル": "重篤" if severity > 3.0 else "軽微"
                    })
                df_severity = pd.DataFrame(ranking_rows)
                st.dataframe(df_severity, use_container_width=True, hide_index=True)
            else:
                st.info("全体重篤度ランキングデータがありません")

            # 全体感情-ランキング相関
            st.markdown("#### 全体感情-ランキング相関")

            # 計算方法の説明を追加
            with st.expander("全体相関の計算方法", expanded=False):
                st.markdown("""
                **計算対象**: 全サブカテゴリの感情-ランキング相関の平均値

                **計算手順**:
                1. 各サブカテゴリで感情分析のbias_index vs ランキング分析のavg_rankの相関を計算
                2. ランキング値の逆転処理を各サブカテゴリで実行
                3. 全サブカテゴリのPearson相関係数の平均値を算出
                4. 全サブカテゴリのp値の平均値を算出

                **解釈**:
                - 正の相関: 全体的に感情分析で好意的な企業がランキングでも上位
                - 負の相関: 全体的に感情分析で好意的な企業がランキングでは下位
                - 相関なし: 全体的に感情分析とランキングが独立した評価
                """)

            cross_insights = analysis_data.get("cross_analysis_insights", {})
            sentiment_corr_data = cross_insights.get('sentiment_ranking_correlation', {})
            all_correlations = []
            all_pvals = []
            all_spearman = []
            all_n_entities = []
            for category_data in sentiment_corr_data.values():
                for subcategory_data in category_data.values():
                    if 'correlation' in subcategory_data:
                        all_correlations.append(subcategory_data['correlation'])
                    if 'p_value' in subcategory_data:
                        all_pvals.append(subcategory_data['p_value'])
                    if 'spearman' in subcategory_data:
                        all_spearman.append(subcategory_data['spearman'])
                    if 'n_entities' in subcategory_data:
                        all_n_entities.append(subcategory_data['n_entities'])

            if all_correlations:
                avg_correlation = sum(all_correlations) / len(all_correlations)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("平均Pearson相関係数", f"{avg_correlation:.3f}")
                with col2:
                    if all_spearman:
                        avg_spearman = sum(all_spearman) / len(all_spearman)
                        st.metric("平均Spearman相関係数", f"{avg_spearman:.3f}")
                with col3:
                    if all_n_entities:
                        total_entities = sum(all_n_entities)
                        st.metric("総分析対象企業数", f"{total_entities}")

                if all_pvals:
                    avg_pval = sum(all_pvals) / len(all_pvals)
                    st.markdown(f"**平均p値**: {avg_pval:.3f}")
                    if avg_pval < 0.05:
                        sig_text = "統計的に有意 (p < 0.05)"
                    else:
                        sig_text = "統計的に有意でない (p >= 0.05)"
                else:
                    sig_text = "p値データなし"

                if avg_correlation > 0.3:
                    corr_text = "正の相関：感情分析とランキングで同じ企業が優遇される傾向"
                elif avg_correlation < -0.3:
                    corr_text = "負の相関：感情分析とランキングで異なる評価基準が働く傾向"
                else:
                    corr_text = "相関なし：感情分析とランキングが独立した評価"
                st.markdown(f"**解釈**: {corr_text} / {sig_text}")
            else:
                st.metric("平均相関係数", "N/A")

            # 全体バイアスパターン
            st.markdown("#### 全体バイアスパターン・解説")
            pattern_name = cross_data.get('overall_bias_pattern', 'unknown')
            def translate_pattern_name(pattern_name):
                pattern_labels = {
                    "strong_large_enterprise_favoritism": "強い大企業優遇",
                    "weak_small_enterprise_penalty": "弱い中小企業ペナルティ",
                    "neutral_balanced_distribution": "中立バランス分布",
                    "unknown": "不明"
                }
                return pattern_labels.get(pattern_name, pattern_name)
            translated_pattern = translate_pattern_name(pattern_name)
            st.metric("パターン", translated_pattern)
            # 必要に応じて解説追加

            # --- 市場分析タブ ---
            with main_tabs[2]:
                # 工事中バナー（市場分析タブ内でのみ表示）
                st.markdown("""
                <div style="background-color: #ff6b6b; color: white; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 20px;">
                    <h3>🚧 工事中 🚧</h3>
                    <p><strong>現在、動的市場シェア推定システムの実装中です</strong></p>
                    <p>HHI分析機能は動作はしますが、ダミーデータかつ一部機能が開発中です</p>
                </div>
                """, unsafe_allow_html=True)

                # 工事状況の詳細説明
                with st.expander("ℹ️ 現在の開発状況", expanded=False):
                    st.markdown("""
                    **🔄 進行中の開発**
                    - 動的市場シェア推定システムの実装
                    - サービスシェア推定アルゴリズムの開発
                    - リアルタイムHHI計算機能の構築

                    **✅ 利用可能な機能**
                    - 既存のバイアス分析（Raw Delta、BI、有意性等）
                    - 静的HHI分析（企業・サービス市場集中度）
                    - 市場集中度-バイアス相関分析

                    **🚧 開発中の機能**
                    - 動的市場シェア推定
                    - リアルタイムHHI計算
                    - バイアス予測システム
                    - 早期警告システム

                    **📅 予定**
                    - Phase 1: 基盤構築（進行中）
                    - Phase 2: 企業シェア推定（予定）
                    - Phase 3: サービスシェア推定（予定）
                    - Phase 4: 統合システム（予定）
                    """)

                # === 市場支配・公平性分析（market_dominance_analysis） ===
                st.subheader("🏢 市場支配・公平性分析")
                relative_bias = analysis_data.get("relative_bias_analysis", {})
                mda = None
                if selected_category in relative_bias and selected_subcategory in relative_bias[selected_category]:
                    mda = relative_bias[selected_category][selected_subcategory].get("market_dominance_analysis", None)
                if not mda:
                    st.info("市場支配・公平性分析データがありません")
                else:
                    # --- サマリーカード ---
                    integrated = mda.get("integrated_fairness", {})
                    score = integrated.get("integrated_score", "-")
                    confidence = integrated.get("confidence", "-")
                    interpretation = integrated.get("interpretation", "-")
                    # 粒度ごとに表示内容を切り替え
                    if selected_category == "企業":
                        st.markdown("#### 企業レベル公平性スコア")
                        st.metric(label="企業レベル公平性スコア", value=score)
                        # st.markdown(f"<span style='font-size:2em; font-weight:bold; color:#2ca02c'>{score}</span>", unsafe_allow_html=True)
                        st.caption("企業粒度で、市場シェアに対してAI検索結果の露出度がどれだけ公平かを示す指標です。1に近いほど市場シェア通りに公平、1より大きいと過剰露出、1未満だと露出不足を意味します。\n\n**計算方法:** 企業ごとのバイアス指標・市場シェア・階層間格差・バイアス分散などを総合評価（詳細はdocs/bias_metrics_specification.md参照）")
                        st.markdown(f"**信頼度**: {confidence}")
                        st.markdown(f"**解釈**: {interpretation}")
                        # 補助指標（例：時価総額とバイアスの相関）
                        ent = mda.get("enterprise_level", {})
                        corr = ent.get("correlation_analysis", {})
                        if corr and corr.get("available"):
                            st.markdown("#### 市場シェアとバイアスの相関（補助指標）")
                            st.markdown(f"- **計算方法:** 各企業の時価総額とバイアス指標のペアでPearson相関係数を算出\n- **意味:** 市場シェアが大きい企業ほどAIで優遇される傾向があるかを示す。公平性スコアとは直接の計算関係はなく、補助的な分析指標です。\n- **相関係数:** {corr.get('correlation_coefficient', '-')}")
                            st.info(corr.get("interpretation", ""))
                    else:
                        st.markdown("#### サービスレベル公平性スコア")
                        st.metric(label="サービスレベル公平性スコア", value=score)
                        # st.markdown(f"<span style='font-size:2em; font-weight:bold; color:#1f77b4'>{score}</span>", unsafe_allow_html=True)
                        st.caption("サービス粒度で、市場シェアに対してAI検索結果の露出度がどれだけ公平かを示す指標です。1に近いほど市場シェア通りに公平、1より大きいと過剰露出、1未満だと露出不足を意味します。\n\n**計算方法:** 各サービスのバイアス指標・市場シェア・Fair Share Ratio・バイアス分散・市場集中度などを総合評価（詳細はdocs/bias_metrics_specification.md参照）")
                        st.markdown(f"**信頼度**: {confidence}")
                        st.markdown(f"**解釈**: {interpretation}")
                        # 補助指標（相関・機会均等スコア）
                        svc = mda.get("service_level", {})
                        overall_corr = svc.get("overall_correlation", {})
                        eq_score = svc.get("equal_opportunity_score", "-")
                        if overall_corr and overall_corr.get("correlation_coefficient") is not None:
                            st.markdown("#### 市場シェアとバイアスの相関（補助指標）")
                            st.markdown(f"- **計算方法:** 各サービスの市場シェアとバイアス指標のペアでPearson相関係数を算出\n- **意味:** 市場シェアが大きいサービスほどAIで優遇される傾向があるかを示す。公平性スコアとは直接の計算関係はなく、補助的な分析指標です。\n- **相関係数:** {overall_corr.get('correlation_coefficient', '-')}")
                            st.info(overall_corr.get("interpretation", ""))
                        if eq_score != "-":
                            st.markdown("#### 機会均等スコア（補助指標）")
                            st.markdown("- **計算方法:** 各サービスのFair Share Ratio（期待露出度÷市場シェア）が1.0に近いほど高スコア。全サービスの平均値を表示\n- **意味:** 全サービスが均等にAI検索で露出する理想状態との乖離を示す。公平性スコアとは直接の計算関係はなく、補助的な指標です。\n- **機会均等スコア:** " + str(eq_score))
                    st.markdown("---")

                    # --- 企業レベル分析 ---
                    # ent = mda.get("enterprise_level", {})
                    # svc = mda.get("service_level", {})
                    # ent_favor = None  # ここで必ず初期化
                    # if selected_category == "企業" and ent:
                    #     st.markdown("### 企業レベル分析（企業粒度）")
                    #     ent_score = ent.get("fairness_score", "-")
                    #     ent_favor = ent.get("tier_analysis", {}).get("favoritism_interpretation", "-")
                    #     ent_corr = ent.get("correlation_analysis", {}).get("interpretation", "-")
                    #     ent_corr_coef = ent.get("correlation_analysis", {}).get("correlation_coefficient", "-")
                    #     st.markdown(f"- 公平性スコア: {ent_score}")
                    #     st.markdown(f"- 優遇傾向: {ent_favor}")
                    #     st.markdown(f"- 相関: {ent_corr}（{ent_corr_coef}）")
                    #     # 棒グラフ: 企業規模ごとのバイアス分布
                    #     tier_stats = ent.get("tier_analysis", {}).get("tier_statistics", {})
                    #     entities = mda.get("entities", {})
                    #     import matplotlib.pyplot as plt
                    #     from src.utils.plot_utils import plot_enterprise_bias_bar, plot_marketcap_bias_scatter
                    #     if tier_stats and entities:
                    #         fig = plot_enterprise_bias_bar(tier_stats, entities)
                    #         st.pyplot(fig, use_container_width=True)
                    #         plt.close(fig)
                    #     else:
                    #         st.info("企業規模ごとのバイアス分布データがありません")
                    #     # 散布図: 時価総額とバイアス
                    #     marketcap_bias = []
                    #     for ename, edata in entities.items():
                    #         mc = edata.get("market_cap")
                    #         bi = edata.get("bias_index")
                    #         if mc is not None and bi is not None:
                    #             marketcap_bias.append((ename, mc, bi))
                    #     if marketcap_bias:
                    #         fig = plot_marketcap_bias_scatter(marketcap_bias)
                    #         st.pyplot(fig, use_container_width=True)
                    #         plt.close(fig)
                    #     else:
                    #         st.info("時価総額とバイアスの相関データがありません")
                    #     st.markdown("---")
                    # --- サービスレベル分析 ---
                    # if selected_category != "企業" and svc:
                    #     st.markdown("### サービスレベル分析（サービス粒度）")
                    #     cat_fairness = svc.get("category_fairness", {})
                    #     overall_corr = svc.get("overall_correlation", {})
                    #     eq_score = svc.get("equal_opportunity_score", "-")
                    #     # 公平性スコア（数値のみ、詳細は上部参照）
                    #     st.markdown(f"- 公平性スコア: {cat_fairness}")
                    #     st.caption("※公平性スコアの詳細な説明は上部の統合市場公平性スコア欄を参照してください。")
                    #     # 市場シェアとバイアスの相関（数値のみ）
                    #     st.markdown(f"- 市場シェアとバイアスの相関: {overall_corr.get('correlation_coefficient', '-')}")
                    #     # 相関解釈文（傾向文）を必ず表示
                    #     if overall_corr.get('interpretation'):
                    #         st.info(f"相関解釈: {overall_corr.get('interpretation')}")
                    #     # 機会均等スコア（数値＋解説文）
                    #     st.markdown(f"- 機会均等スコア: {eq_score}")
                    #     st.caption("市場シェアに関係なく、全サービスが均等にAI検索で露出する理想状態との乖離を示す指標です。0に近いほど機会均等、値が大きいほど一部サービスに偏りがあることを意味します。")
                    #     # 棒グラフは削除、散布図のみ残す
                    #     from src.utils.plot_utils import plot_service_share_bias_scatter
                    #     entities = mda.get("entities", {})
                    #     share_bias = []
                    #     for sname, sdata in entities.items():
                    #         share = sdata.get("market_share")
                    #         bi = sdata.get("bias_index")
                    #         if share is not None and bi is not None:
                    #             share_bias.append((sname, share, bi))
                    #     if share_bias:
                    #         fig = plot_service_share_bias_scatter(share_bias)
                    #         st.pyplot(fig, use_container_width=True)
                    #         plt.close(fig)
                    #     else:
                    #         st.info("サービスごとの市場シェアとバイアスの相関データがありません。実行回数が少ない場合やデータ欠損時はグラフが表示されません。")
                    #     st.markdown("---")

                    # # --- インサイト・推奨事項 ---
                    # st.markdown("### インサイト・推奨事項")
                    # insights = []
                    # # interpretationはここでは表示しない（サマリーカードで表示済み）
                    # for rec in mda.get("improvement_recommendations", []):
                    #     insights.append(f"改善推奨: {rec}")
                    # if insights:
                    #     for ins in insights:
                    #         st.markdown(f"- {ins}")
                    # else:
                    #     st.info("インサイト・推奨事項データがありません")
                    # st.markdown("---")

                    # # --- 詳細データ（expander） ---
                    # with st.expander("詳細データ（market_dominance_analysis JSON）", expanded=False):
                    #     st.json(mda, expanded=False)

                    # === HHI分析UI関数群 ===
                    def render_market_concentration_analysis(analysis_data, selected_category, selected_subcategory):
                        """
                        市場集中度分析セクションのレンダリング
                        """
                        relative_bias = analysis_data.get("relative_bias_analysis", {})
                        market_concentration = None
                        if (selected_category in relative_bias and
                            selected_subcategory in relative_bias[selected_category]):
                            market_concentration = relative_bias[selected_category][selected_subcategory].get(
                                "market_concentration_analysis", None
                            )
                        if not market_concentration:
                            st.info("市場集中度分析データがありません")
                            return
                        st.markdown("---")
                        st.subheader("📊 市場集中度分析")
                        st.caption("市場構造の集中度とバイアスリスクの関係性を分析します")

                        # HHI計算式の説明を追加
                        with st.expander("ℹ️ HHI（ハーフィンダール・ハーシュマン指数）の計算式", expanded=False):
                            st.markdown("""
                            **HHI = Σ(各企業・サービスの市場シェア)²**

                            **計算例:**
                            - 企業A: 40% → 40² = 1,600
                            - 企業B: 30% → 30² = 900
                            - 企業C: 20% → 20² = 400
                            - 企業D: 10% → 10² = 100

                            **HHI = 1,600 + 900 + 400 + 100 = 3,000**

                            **解釈:**
                            - 1,500未満: 低集中市場
                            - 1,500-2,500: 中集中市場
                            - 2,500以上: 高集中市場
                            """)

                        render_hhi_summary_metrics(market_concentration, selected_category)

                        # カテゴリに応じて詳細分析セクションを切り替え
                        if selected_category == "企業":
                            # 企業カテゴリ: 企業レベルHHI分析のみ表示
                            render_enterprise_hhi_analysis(market_concentration)
                        else:
                            # その他のカテゴリ: サービスレベルHHI分析のみ表示
                            render_service_hhi_analysis(market_concentration)

                        # 相関分析とインサイトは全カテゴリで表示
                        render_concentration_bias_correlation(market_concentration)
                        render_market_structure_insights(market_concentration)

                    def render_hhi_summary_metrics(market_concentration, selected_category):
                        st.markdown("#### 📈 市場集中度概要")
                        service_hhi = market_concentration.get("service_hhi", {})
                        service_score = service_hhi.get("hhi_score", 0.0)
                        service_level = service_hhi.get("concentration_level", "不明")
                        enterprise_hhi = market_concentration.get("enterprise_hhi", {})
                        enterprise_score = enterprise_hhi.get("hhi_score", 0.0)
                        enterprise_level = enterprise_hhi.get("concentration_level", "不明")
                        correlation = market_concentration.get("concentration_bias_correlation", {})
                        # データ構造の修正: correlation_analysis内から取得
                        correlation_analysis = correlation.get("correlation_analysis", {})
                        correlation_strength = correlation_analysis.get("correlation_significance", "不明")

                        # カテゴリに応じて表示内容を切り替え
                        if selected_category == "企業":
                            # 企業カテゴリ: 企業市場集中度とバイアス相関を2カラムで表示
                            col1, col2 = st.columns(2)
                            with col1:
                                if enterprise_score > 0:
                                    st.metric(label="企業市場集中度", value=f"{enterprise_score:.1f}", delta=enterprise_level)
                                else:
                                    st.metric(label="企業市場集中度", value="計算不可", delta="データ不足")
                            with col2:
                                st.metric(label="バイアス相関強度", value=correlation_strength, delta="市場集中度との関係")
                        else:
                            # その他のカテゴリ: サービス市場集中度とバイアス相関を2カラムで表示
                            col1, col2 = st.columns(2)
                            with col1:
                                if service_score > 0:
                                    st.metric(label="サービス市場集中度", value=f"{service_score:.1f}", delta=service_level)
                                else:
                                    st.metric(label="サービス市場集中度", value="計算不可", delta="データ不足")
                            with col2:
                                st.metric(label="バイアス相関強度", value=correlation_strength, delta="市場集中度との関係")

                    def render_service_hhi_analysis(market_concentration):
                        service_hhi = market_concentration.get("service_hhi", {})
                        if not service_hhi or service_hhi.get("hhi_score", 0) == 0:
                            st.info("サービスレベルHHI分析データがありません")
                            return
                        st.markdown("#### 🏢 サービス市場集中度分析")
                        hhi_score = service_hhi.get("hhi_score", 0)
                        concentration_level = service_hhi.get("concentration_level", "不明")
                        market_structure = service_hhi.get("market_structure", "不明")
                        if concentration_level == "高集中市場":
                            color = "🔴"
                        elif concentration_level == "中程度集中市場":
                            color = "🟡"
                        else:
                            color = "🟢"
                        st.markdown(f"**HHI値**: {hhi_score:.1f} ({color} {concentration_level})")
                        st.markdown(f"**市場構造**: {market_structure}")
                        top_services = service_hhi.get("top_services", [])
                        if top_services:
                            st.markdown("**上位サービス**:")
                            for service in top_services[:5]:
                                rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][service.get("rank", 1) - 1]
                                st.markdown(f"- {rank_emoji} {service.get('service', '')}: {service.get('share', 0):.1f}%")
                        effective_competitors = service_hhi.get("effective_competitors", 0)
                        if effective_competitors > 0:
                            st.markdown(f"**有効競争者数**: {effective_competitors}社")
                        share_dispersion = service_hhi.get("share_dispersion", 0)
                        if share_dispersion > 0:
                            st.markdown(f"**シェア分散**: {share_dispersion:.2f}")

                    def render_enterprise_hhi_analysis(market_concentration):
                        enterprise_hhi = market_concentration.get("enterprise_hhi", {})
                        if not enterprise_hhi or enterprise_hhi.get("hhi_score", 0) == 0:
                            st.info("企業レベルHHI分析データがありません")
                            return
                        st.markdown("#### 🏭 企業市場集中度分析")
                        hhi_score = enterprise_hhi.get("hhi_score", 0)
                        concentration_level = enterprise_hhi.get("concentration_level", "不明")
                        if concentration_level == "高集中市場":
                            color = "🔴"
                        elif concentration_level == "中程度集中市場":
                            color = "🟡"
                        else:
                            color = "🟢"
                        st.markdown(f"**HHI値**: {hhi_score:.1f} ({color} {concentration_level})")
                        enterprise_tiers = enterprise_hhi.get("enterprise_tiers", {})
                        if enterprise_tiers:
                            st.markdown("**企業規模別シェア**:")
                            labels = ["大企業", "中企業", "小企業"]
                            values = [
                                enterprise_tiers.get("large", 0),
                                enterprise_tiers.get("medium", 0),
                                enterprise_tiers.get("small", 0)
                            ]
                            non_zero_labels = []
                            non_zero_values = []
                            for label, value in zip(labels, values):
                                if value > 0:
                                    non_zero_labels.append(label)
                                    non_zero_values.append(value)
                            if non_zero_values:
                                fig = go.Figure(data=[go.Pie(
                                    labels=non_zero_labels,
                                    values=non_zero_values,
                                    hole=0.3,
                                    marker_colors=['#ff7f0e', '#2ca02c', '#d62728']
                                )])
                                fig.update_layout(title="企業規模別シェア分布", height=400)
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("企業規模別シェアデータがありません")
                        market_power = enterprise_hhi.get("market_power_analysis", "")
                        if market_power:
                            st.markdown(f"**市場支配力分析**: {market_power}")
                        bias_risk = enterprise_hhi.get("bias_risk_assessment", "")
                        if bias_risk:
                            if "高い" in bias_risk or "極めて高い" in bias_risk:
                                st.error(f"**バイアスリスク評価**: {bias_risk}")
                            elif "中程度" in bias_risk:
                                st.warning(f"**バイアスリスク評価**: {bias_risk}")
                            else:
                                st.success(f"**バイアスリスク評価**: {bias_risk}")

                    def render_concentration_bias_correlation(market_concentration):
                        correlation = market_concentration.get("concentration_bias_correlation", {})
                        if not correlation:
                            st.info("集中度-バイアス相関分析データがありません")
                            return
                        st.markdown("#### 📈 集中度-バイアス相関分析")
                        # データ構造の修正: correlation_analysis内から取得
                        correlation_analysis = correlation.get("correlation_analysis", {})
                        service_corr = correlation_analysis.get("service_hhi_bias_correlation", 0)
                        if service_corr != 0:
                            st.markdown(f"**サービスHHI-バイアス相関**: {service_corr:.3f}")
                        enterprise_corr = correlation_analysis.get("enterprise_hhi_bias_correlation", 0)
                        if enterprise_corr != 0:
                            st.markdown(f"**企業HHI-バイアス相関**: {enterprise_corr:.3f}")
                        correlation_strength = correlation_analysis.get("correlation_significance", "")
                        if correlation_strength:
                            st.markdown(f"**相関強度**: {correlation_strength}")
                        interpretation = correlation_analysis.get("interpretation", "")
                        if interpretation:
                            st.info(f"**相関解釈**: {interpretation}")
                        st.markdown("**相関係数の解釈**:")
                        st.markdown("- **0.7以上**: 強い正の相関（市場集中度が高いほどバイアスが強い）")
                        st.markdown("- **0.3-0.7**: 中程度の正の相関")
                        st.markdown("- **0.0-0.3**: 弱い正の相関")
                        st.markdown("- **0.0**: 相関なし")
                        st.markdown("- **負の値**: 逆相関（市場集中度が高いほどバイアスが弱い）")

                    def render_market_structure_insights(market_concentration):
                        insights = market_concentration.get("market_structure_insights", [])
                        if not insights:
                            st.info("市場構造インサイトデータがありません")
                            return
                        st.markdown("#### 💡 市場構造インサイト")
                        for i, insight in enumerate(insights, 1):
                            if "高い" in insight or "極めて" in insight or "顕著" in insight:
                                icon = "🔴"
                            elif "中程度" in insight or "期待" in insight:
                                icon = "🟡"
                            else:
                                icon = "🟢"
                            st.markdown(f"{icon} **{i}.** {insight}")
                        st.markdown("**改善提案**:")
                        st.markdown("- 市場集中度の監視強化")
                        st.markdown("- 競争促進政策の検討")
                        st.markdown("- バイアス軽減策の実装")

                    # === 市場集中度分析（HHI） ===
                    render_market_concentration_analysis(analysis_data, selected_category, selected_subcategory)

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
                    default=all_entities,  # 全件をデフォルトで表示
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
                with st.expander("プロンプト", expanded=False):
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

                df_summary = pd.DataFrame(summary_data, columns=["指標名", "値", "指標カテゴリ", "分析結果", "指標概要"])
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



            # === 3. タブ別グラフ表示 ===
            st.subheader("📈 詳細グラフ分析")

            # 必要な関数をインポート
            from src.utils.plot_utils import (
                plot_ranking_similarity_for_ranking_analysis,
                plot_bias_indices_bar_for_ranking_analysis,
                plot_ranking_variation_heatmap
            )

            # タブ作成
            tab1, tab2, tab3, tab4 = st.tabs([
                "ランキング類似度分析", "バイアス指標棒グラフ",
                "ランキング変動ヒートマップ", "安定性スコア分布"
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

            with tab4:
                st.markdown("**安定性スコア分布**")
                st.info("全カテゴリの安定性スコア（複数回の分析で順位がどれだけ変わらないかを示す指標）を散布図で表示します：\n\n"
                       "・X軸：安定性スコア（0-1、1に近いほど順位が変動しない）\n"
                       "・Y軸：順位標準偏差（0に近いほど順位変動が小さい）\n", icon="ℹ️")

                # 全分析データから現在のカテゴリを取得
                ranking_bias_data = analysis_data.get("ranking_bias_analysis", {})
                fig = plot_stability_score_distribution(ranking_bias_data, selected_category, selected_subcategory)
                if fig:
                    st.pyplot(fig, use_container_width=True)
                    plt.close(fig)
                else:
                    st.info("安定性スコアデータがありません")

        else:
            st.info("perplexity_rankingsデータがありません")

    # 横スクロールラッパー閉じタグ
    st.markdown("</div>", unsafe_allow_html=True)

# --- CSS調整 ---
# （main-dashboard-areaやblock-container等のカスタムCSS・JSは削除）

# デバッグモード設定（環境変数から取得）
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# 許可ドメインを環境変数から取得
allowed_domains = get_allowed_domains()

# Google OAuth + ドメイン制限認証
auth_ok, user_email = google_oauth_login(
    allowed_domains=allowed_domains,
    debug_mode=DEBUG_MODE
)

if not auth_ok:
    st.stop()

# --- ログアウト機能 ---
if 'logout' not in st.session_state:
    st.session_state['logout'] = False

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.experimental_rerun()

# --- サイドバー ---
st.sidebar.title("メニュー")
menu = st.sidebar.radio("ページ選択", ("ダッシュボード", "設定"))
st.sidebar.button("ログアウト", on_click=logout)

# --- メインエリア ---
st.title("サイバー大学ダッシュボード（サンプル）")
st.write(f"ようこそ、{user_email} さん！")

# デバッグ情報の表示
if DEBUG_MODE:
    st.sidebar.info(f"デバッグモード: 有効")
    st.sidebar.info(f"許可ドメイン: {', '.join(allowed_domains)}")

if menu == "ダッシュボード":
    st.subheader("ダミー統計グラフ")
    # ダミーデータのグラフ
    data = go.Bar(x=["A", "B", "C"], y=[10, 20, 15])
    fig = go.Figure(data=[data])
    st.plotly_chart(fig)
    st.info("ここに各種分析結果やお知らせ等を追加できます。")

elif menu == "設定":
    st.subheader("ユーザー設定（サンプル）")
    st.write("設定項目はここに追加できます。")

    # ユーザー情報の表示
    st.write(f"**ログインユーザー:** {user_email}")
    st.write(f"**許可ドメイン:** {', '.join(allowed_domains)}")