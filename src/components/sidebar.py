#!/usr/bin/env python
# coding: utf-8

"""
サイドバーコンポーネント

企業バイアス分析ダッシュボードのサイドバー機能を提供します。
"""

import streamlit as st
from src.analysis.hybrid_data_loader import HybridDataLoader
from src.utils.storage_config import get_base_paths


def render_storage_mode_selector():
    """データ取得元選択UIを表示"""
    # コマンドライン引数でstorage-modeを受け取る
    if not hasattr(st, 'session_state') or 'storage_mode' not in st.session_state:
        st.session_state['storage_mode'] = 'auto'  # デフォルト値を設定

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


def render_analysis_type_selector():
    """可視化タイプ選択UIを表示"""
    viz_type = st.sidebar.selectbox(
        "可視化タイプを選択",
        ["単日分析", "時系列分析"],
        key="analysis_type_selector"
    )
    return viz_type


def render_date_selector(storage_mode, viz_type):
    """日付選択UIを表示"""
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
            return loader, selected_dates, None, None
        # 時系列分析時はこのUIを表示しない
        return None, None, loader_local, loader_s3
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
            return loader, selected_dates, None, None
        return None, None, loader, None


def render_time_series_period_selector(available_dates):
    """時系列分析の期間選択UIを表示"""
    # 表示期間選択
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

    # 期間フィルタリング
    if period_n is not None:
        selected_dates = sorted(sorted_dates[:period_n], reverse=False)
    else:
        selected_dates = sorted(available_dates)

    return selected_dates


def render_category_selectors(sentiment_data, viz_type, key_prefix=""):
    """カテゴリ・サブカテゴリ選択UIを表示"""
    all_categories = [c for c in sentiment_data.keys() if c not in ("全体", "all", "ALL", "All")]
    all_categories.sort()

    if not all_categories:
        st.info("カテゴリデータがありません")
        st.stop()

    selected_category = st.sidebar.selectbox(
        "カテゴリを選択",
        all_categories,
        key=f"{key_prefix}category_selector",
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
        key=f"{key_prefix}subcategory_selector",
        index=0
    )

    return selected_category, selected_subcategory


def render_entities_selector(entities_data, key_prefix=""):
    """エンティティ選択UIを表示"""
    entities = list(entities_data.keys())

    if not entities:
        st.info("エンティティデータがありません")
        st.stop()

    selected_entities = st.sidebar.multiselect(
        "エンティティを選択（複数選択可）",
        entities,
        default=entities,  # 全件をデフォルトで表示
        key=f"{key_prefix}entities_selector"
    )

    if not selected_entities:
        st.info("エンティティを選択してください")
        st.stop()

    return selected_entities


def render_viz_type_detail_selector():
    """詳細可視化タイプ選択UIを表示（単日分析用）"""
    viz_type_options = ["感情スコア分析", "おすすめランキング分析結果", "Perplexity-Google比較", "統合分析"]
    viz_type_detail = st.sidebar.selectbox(
        "詳細可視化タイプを選択",
        viz_type_options,
        key="viz_type_selector",
        index=0  # デフォルトで最初の項目を選択
    )
    return viz_type_detail


def render_load_status(expanded=False, key_prefix="", simplified=False):
    """
    読み込み状況を表示する共通関数

    Parameters:
    -----------
    expanded : bool
        エクスパンダーの初期展開状態
    key_prefix : str
        ページネーション用のキープレフィックス
    simplified : bool
        簡素化表示モード（単日分析用）
    """
    if hasattr(st.session_state, 'load_status') and st.session_state.load_status:
        if simplified:
            # 簡素化表示：最新の読み込み情報のみを緑色で直接表示（エクスパンダーなし）
            latest_item = st.session_state.load_status[-1]
            st.sidebar.success(latest_item)
        else:
            # 通常表示：エクスパンダー付きで統計情報とページネーション
            with st.sidebar.expander("📊 読み込み状況", expanded=expanded):
                # 統計情報を表示
                total_loads = len(st.session_state.load_status)
                new_loads = sum(1 for item in st.session_state.load_status if "新規読み込み" in item)
                cache_loads = sum(1 for item in st.session_state.load_status if "キャッシュ" in item)
                st.caption(f"📈 総読み込み: {total_loads}件 (新規: {new_loads}件, キャッシュ: {cache_loads}件)")

                # 読み込みリストを表示（全件表示）
                for item in st.session_state.load_status:
                    if "新規読み込み" in item:
                        st.info(item)
                    else:
                        st.success(item)


def render_sidebar_header():
    """サイドバーヘッダーを表示"""
    st.sidebar.header("📊 データ選択")


def render_main_sidebar():
    """メインサイドバーを表示"""
    render_sidebar_header()

    # データ取得元選択
    storage_mode = render_storage_mode_selector()

    # 可視化タイプ選択
    viz_type = render_analysis_type_selector()

    # 日付選択
    loader, selected_dates, loader_local, loader_s3 = render_date_selector(storage_mode, viz_type)

    return {
        'storage_mode': storage_mode,
        'viz_type': viz_type,
        'loader': loader,
        'selected_dates': selected_dates,
        'loader_local': loader_local,
        'loader_s3': loader_s3
    }
