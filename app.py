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

# 動的可視化関数群
def plot_ranking_similarity(similarity_data, title):
    """ランキング類似度の動的可視化"""
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
    return fig

def plot_bias_indices_bar(bias_data, title, reliability_label=None):
    """感情バイアス指標の動的可視化"""
    entities = list(bias_data.keys())
    values = [bias_data[e] for e in entities]

    fig, ax = plt.subplots(figsize=(10, 6))
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

    fig, ax = plt.subplots(figsize=(8, 6))
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

    fig, ax = plt.subplots(figsize=(10, 6))

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

def load_analysis_data(date_str):
    """指定日付の分析データを読み込む"""
    try:
        # ローカルファイルパス
        local_path = f"corporate_bias_datasets/integrated/{date_str}/bias_analysis_results.json"

        if os.path.exists(local_path):
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            st.error(f"分析データが見つかりません: {local_path}")
            return None
    except Exception as e:
        st.error(f"データ読み込みエラー: {str(e)}")
        return None

def get_data_files():
    """S3からデータファイル（JSON/CSV）のみを取得"""
    try:
        s3_client = get_s3_client()
        prefix = 'results/'
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)

        if 'Contents' not in response:
            st.warning("S3バケットにデータファイルが見つかりません。")
            return []

        files = []
        for content in response['Contents']:
            file_path = content['Key']
            file_name = os.path.basename(file_path)

            # データファイルのみを対象
            if not (file_name.endswith('.json') or file_name.endswith('.csv')):
                continue

            # 日付を抽出 (YYYYMMDD形式)
            date_match = next((part for part in file_name.split('_') if len(part) == 8 and part.isdigit()), None)

            if date_match:
                try:
                    date_obj = datetime.strptime(date_match, "%Y%m%d")
                    date_str = date_obj.strftime("%Y-%m-%d")
                except:
                    date_str = "不明"
            else:
                date_str = "不明"

            # データタイプを判断
            if "perplexity_sentiment" in file_name:
                data_type = "Perplexity 感情スコア"
            elif "perplexity_results" in file_name and "/sentiment/" in file_path:
                data_type = "Perplexity 感情スコア"
            elif "perplexity_rankings" in file_name:
                data_type = "Perplexity ランキング"
            elif "perplexity_results" in file_name and "/rankings/" in file_path:
                data_type = "Perplexity ランキング"
            elif "perplexity_citations" in file_name:
                data_type = "Perplexity 引用リンク"
            elif "perplexity_results" in file_name and "/citations/" in file_path:
                data_type = "Perplexity 引用リンク"
            elif "openai_sentiment" in file_name:
                data_type = "OpenAI 感情スコア"
            elif "openai_results" in file_name:
                data_type = "OpenAI 感情スコア"
            else:
                data_type = "その他"

            # 複数回実行かどうか
            import re
            m = re.search(r'_(\d+)runs\.json', file_name)
            if m:
                runs_count = int(m.group(1))
                is_multi_run = True
                runs_suffix = f"（{runs_count}回実行）"
            elif "_runs.json" in file_name:
                is_multi_run = False
                runs_suffix = "（単一実行）"
            else:
                is_multi_run = False
                runs_suffix = "（単一実行）"

            # 表示名を生成
            display_name = f"{date_str}: {data_type}{runs_suffix}"

            files.append({
                "path": f"s3://{S3_BUCKET_NAME}/{file_path}",
                "name": file_name,
                "date": date_str,
                "date_obj": date_obj if date_match else datetime.now(),
                "type": data_type,
                "is_multi_run": is_multi_run,
                "display_name": display_name,
                "date_raw": date_match
            })

        # 日付の新しい順＋同日付なら実行回数多い順にソート
        def extract_runs(file):
            m = re.search(r'_(\d+)runs\.json', file["name"])
            return int(m.group(1)) if m else 1
        files.sort(key=lambda x: (x["date_obj"], extract_runs(x)), reverse=True)
        return files

    except Exception as e:
        st.error(f"S3からのファイル一覧取得エラー: {e}")
        return []

def get_image_files():
    """S3から画像ファイル（PNG）のみを取得"""
    try:
        s3_client = get_s3_client()
        prefix = 'results/perplexity_analysis/'
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)

        if 'Contents' not in response:
            st.warning("S3バケットに画像ファイルが見つかりません。")
            return []

        files = []
        for content in response['Contents']:
            file_path = content['Key']
            file_name = os.path.basename(file_path)

            # 画像ファイルのみを対象
            if not file_name.endswith('.png'):
                continue

            # 日付を抽出 (YYYYMMDD形式)
            date_match = next((part for part in file_path.split('/') if len(part) == 8 and part.isdigit()), None)

            if date_match:
                try:
                    date_obj = datetime.strptime(date_match, "%Y%m%d")
                    date_str = date_obj.strftime("%Y-%m-%d")
                except:
                    date_str = "不明"
            else:
                date_str = "不明"

            # 画像タイプを判断
            if "_exposure_market.png" in file_name:
                image_type = "露出度・市場シェア"
            elif "_rank_heatmap.png" in file_name:
                image_type = "ランキング分布"
            elif "_stability_matrix.png" in file_name:
                image_type = "安定性行列"
            else:
                image_type = "その他"

            # 表示名を生成
            display_name = f"{date_str}: {image_type} - {file_name}"

            files.append({
                "path": f"s3://{S3_BUCKET_NAME}/{file_path}",
                "name": file_name,
                "date": date_str,
                "date_obj": date_obj if date_match else datetime.now(),
                "type": image_type,
                "display_name": display_name,
                "date_raw": date_match
            })

        # 日付の新しい順にソート
        files.sort(key=lambda x: x["date_obj"], reverse=True)
        return files

    except Exception as e:
        st.error(f"S3からの画像ファイル一覧取得エラー: {e}")
        return []

def get_visualization_files(date_str):
    """指定日付の可視化画像ファイル一覧を取得"""
    # integratedの日付ディレクトリと同じ日付のanalysis_visuals/配下を参照
    # ローカル・S3共にcorporate_bias_datasets/analysis_visuals/YYYYMMDD/に統一

    visuals_dir = os.path.join("corporate_bias_datasets/analysis_visuals", date_str)
    return visuals_dir

# CSSでフォント設定を追加
st.markdown("""
<style>
    body {
        font-family: 'Hiragino Sans', 'Meiryo', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# タイトル
st.title("企業バイアス分析ダッシュボード")
st.markdown("AI検索サービスにおける企業優遇バイアスの可視化")

# --- 分析サマリーセクション ---
st.header("分析サマリー（最新データ）")

def get_latest_integrated_dir():
    """corporate_bias_datasets/integrated/配下の最新日付ディレクトリを返す"""
    base_dir = "corporate_bias_datasets/integrated"
    dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.isdigit()]
    if not dirs:
        return None
    latest = sorted(dirs, reverse=True)[0]
    return os.path.join(base_dir, latest)

def get_bias_summary():
    """最新のbias_analysis_results.jsonからカテゴリ・サブカテゴリごとの主要バイアス指標を抽出しDataFrameで返す"""
    latest_dir = get_latest_integrated_dir()
    if not latest_dir:
        return None, "データディレクトリが見つかりません"
    bias_path = os.path.join(latest_dir, "bias_analysis_results.json")
    if not os.path.exists(bias_path):
        return None, f"{bias_path} が見つかりません"
    with open(bias_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    sentiment = data.get("sentiment_bias_analysis", {})
    for category, subcats in sentiment.items():
        for subcat, subdata in subcats.items():
            entities = subdata.get("entities", {})
            for key, ent in entities.items():
                metrics = ent.get("basic_metrics", {})
                interp = ent.get("interpretation", {})
                stability = ent.get("stability_metrics", {})
                stat = ent.get("statistical_significance", {})
                results.append({
                    "カテゴリ": category,
                    "サブカテゴリ": subcat,
                    "分析単位": key,
                    "バイアス指標": metrics.get("normalized_bias_index"),
                    "スコアの平均差": metrics.get("raw_delta"),
                    "安定性": stability.get("stability_score"),
                    "バイアス方向": interp.get("bias_direction"),
                    "バイアス強度": interp.get("bias_strength"),
                    "有意性": stat.get("available"),
                    "推奨": interp.get("recommendation")
                })
    df = pd.DataFrame(results)
    return df, None

df, err = get_bias_summary()
if err:
    st.warning(err)
else:
    # バイアス指標ランキング
    st.subheader("バイアス指標ランキング（降順）")
    top = df.sort_values("バイアス指標", ascending=False).head(20)
    st.dataframe(top)
    # バイアス方向・強度の分布
    st.subheader("バイアス方向・強度の分布")
    bias_dir_counts = df["バイアス方向"].value_counts()
    bias_strength_counts = df["バイアス強度"].value_counts()
    col1, col2 = st.columns(2)
    with col1:
        st.bar_chart(bias_dir_counts)
    with col2:
        st.bar_chart(bias_strength_counts)
    # 有意なバイアスのハイライト
    st.subheader("有意なバイアス（p<0.05相当）")
    sig = df[df["有意性"] == True]
    if not sig.empty:
        st.dataframe(sig)
    else:
        st.info("有意なバイアスは検出されていません")

# --- データ分析セクション ---
st.header("詳細分析（カテゴリ・サブカテゴリ単位）")

def get_latest_dataset_path():
    latest_dir = get_latest_integrated_dir()
    if not latest_dir:
        return None
    dataset_path = os.path.join(latest_dir, "corporate_bias_dataset.json")
    if not os.path.exists(dataset_path):
        return None
    return dataset_path

dataset_path = get_latest_dataset_path()
if not dataset_path:
    st.warning("corporate_bias_dataset.json が見つかりません")
else:
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    categories = list(dataset.keys())
    selected_category = st.selectbox("カテゴリを選択", categories)
    subcategories = list(dataset[selected_category].keys())
    selected_subcategory = st.selectbox("サブカテゴリを選択", subcategories)
    subcat_data = dataset[selected_category][selected_subcategory]
    st.subheader(f"{selected_category} - {selected_subcategory} の詳細データ")
    st.json(subcat_data)

# --- サイドバー設定 ---
st.sidebar.header("📊 データ選択")

# 利用可能な日付を取得
def get_available_dates():
    """利用可能な分析日付を取得"""
    integrated_dir = "corporate_bias_datasets/integrated"
    if not os.path.exists(integrated_dir):
        return []

    dates = []
    for item in os.listdir(integrated_dir):
        item_path = os.path.join(integrated_dir, item)
        if os.path.isdir(item_path):
            bias_path = os.path.join(item_path, "bias_analysis_results.json")
            if os.path.exists(bias_path):
                dates.append(item)

    return sorted(dates, reverse=True)

available_dates = get_available_dates()
st.write(f"利用可能な日付: {available_dates}")  # デバッグ用

if not available_dates:
    st.sidebar.error("分析データが見つかりません")
    st.stop()

# 日付選択
selected_date = st.sidebar.selectbox(
    "分析日付を選択",
    available_dates,
    index=0
)

# 分析データを読み込み
analysis_data = load_analysis_data(selected_date)
st.write(f"分析データ読み込み結果: {analysis_data is not None}")  # デバッグ用

if not analysis_data:
    st.sidebar.error(f"分析データの読み込みに失敗しました: {selected_date}")
    st.stop()

# 可視化タイプ選択
viz_type = st.sidebar.selectbox(
    "可視化タイプを選択",
    ["感情バイアス分析", "Citations-Google比較", "統合分析"]
)

# カテゴリ・サブカテゴリ選択（サイドバー）
if viz_type == "感情バイアス分析":
    sentiment_data = analysis_data.get("sentiment_bias_analysis", {})
    if sentiment_data:
        categories = list(sentiment_data.keys())
        selected_category = st.sidebar.selectbox("カテゴリを選択", categories)

        subcategories = list(sentiment_data[selected_category].keys())
        selected_subcategory = st.sidebar.selectbox("サブカテゴリを選択", subcategories)

        # エンティティ選択
        entities_data = sentiment_data[selected_category][selected_subcategory].get("entities", {})
        entities = list(entities_data.keys())
        selected_entities = st.sidebar.multiselect(
            "エンティティを選択（複数選択可）",
            entities,
            default=entities[:5] if len(entities) > 5 else entities
        )

elif viz_type == "Citations-Google比較":
    citations_data = analysis_data.get("citations_google_comparison", {})
    if citations_data:
        categories = list(citations_data.keys())
        if "error" in categories:
            categories.remove("error")

        if categories:
            selected_category = st.sidebar.selectbox("カテゴリを選択", categories)
            subcategories = list(citations_data[selected_category].keys())
            selected_subcategory = st.sidebar.selectbox("サブカテゴリを選択", subcategories)

# --- メイン画面 ---
st.header(f"📈 動的可視化ダッシュボード - {selected_date}")

# データ読み込み状況の表示
st.sidebar.markdown("---")
st.sidebar.markdown("**📋 データ状況**")

# データ可用性の確認
data_availability = analysis_data.get("data_availability_summary", {})
if data_availability:
    available_count = sum(1 for item in data_availability.values() if isinstance(item, dict) and item.get("available", False))
    total_count = len(data_availability)
    st.sidebar.metric("利用可能指標", f"{available_count}/{total_count}")

# 分析制限事項の表示
limitations = analysis_data.get("analysis_limitations", {})
if limitations and isinstance(limitations, dict):
    warnings = []
    if "execution_count_warning" in limitations:
        warnings.append("⚠️ 実行回数不足")
    if "reliability_note" in limitations:
        warnings.append("📊 参考レベルの信頼性")

    if warnings:
        st.sidebar.markdown("**⚠️ 注意事項**")
        for warning in warnings:
            st.sidebar.markdown(warning)

# --- メイン可視化画面 ---
if viz_type == "感情バイアス分析":
    st.subheader(f"🎯 感情バイアス分析 - {selected_category} / {selected_subcategory}")

    if not selected_entities:
        st.warning("エンティティを選択してください")
    else:
        # 選択されたエンティティのバイアス指標を抽出
        bias_indices = {}
        execution_counts = {}

        for entity in selected_entities:
            if entity in entities_data:
                entity_data = entities_data[entity]
                if "basic_metrics" in entity_data:
                    bias_indices[entity] = entity_data["basic_metrics"].get("normalized_bias_index", 0)
                    execution_counts[entity] = entity_data["basic_metrics"].get("execution_count", 0)

        if bias_indices:
            # 信頼性ラベルを計算（最小実行回数を使用）
            min_exec_count = min(execution_counts.values()) if execution_counts else 0
            reliability_label = get_reliability_label(min_exec_count)

            # バイアス指標グラフを表示
            fig = plot_bias_indices_bar(
                bias_indices,
                f"{selected_category} - {selected_subcategory}",
                reliability_label
            )
            st.pyplot(fig)

            # 詳細情報を表示
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📊 バイアス指標詳細**")
                for entity, bias_index in bias_indices.items():
                    exec_count = execution_counts.get(entity, 0)
                    st.markdown(f"- **{entity}**: {bias_index:.3f} (実行回数: {exec_count}回)")

            with col2:
                st.markdown("**📋 信頼性情報**")
                st.markdown(f"- **信頼性レベル**: {reliability_label}")
                st.markdown(f"- **最小実行回数**: {min_exec_count}回")
                if min_exec_count < 5:
                    st.warning("⚠️ 統計的有意性検定には最低5回の実行が必要です")
        else:
            st.info("選択されたエンティティにバイアス指標データがありません")

elif viz_type == "Citations-Google比較":
    st.subheader(f"🔄 Citations-Google比較分析 - {selected_category} / {selected_subcategory}")

    comparison_data = citations_data[selected_category][selected_subcategory]

    # タブで可視化を分ける
    tab1, tab2, tab3, tab4 = st.tabs(["ランキング類似度", "公式ドメイン比較", "感情分析比較", "データ品質"])

    with tab1:
        if "ranking_similarity" in comparison_data:
            fig = plot_ranking_similarity(
                comparison_data["ranking_similarity"],
                f"{selected_category} - {selected_subcategory}"
            )
            st.pyplot(fig)

            # 指標の説明
            st.markdown("""
            **📈 指標の説明:**
            - **RBO (Rank Biased Overlap)**: 上位の結果を重視した重複度（0-1）
            - **Kendall Tau**: 順位の相関係数（-1〜1）
            - **Overlap Ratio**: 共通要素の割合（0-1）
            """)
        else:
            st.info("ランキング類似度データがありません")

    with tab2:
        if "official_domain_analysis" in comparison_data:
            fig = plot_official_domain_comparison(
                comparison_data["official_domain_analysis"],
                f"{selected_category} - {selected_subcategory}"
            )
            st.pyplot(fig)

            # 分析結果の説明
            official_data = comparison_data["official_domain_analysis"]
            st.markdown(f"""
            **📊 分析結果:**
            - Google検索公式ドメイン率: {official_data.get('google_official_ratio', 0):.3f}
            - Perplexity公式ドメイン率: {official_data.get('citations_official_ratio', 0):.3f}
            - バイアス方向: {official_data.get('bias_direction', 'unknown')}
            """)
        else:
            st.info("公式ドメイン分析データがありません")

    with tab3:
        if "sentiment_comparison" in comparison_data:
            fig = plot_sentiment_comparison(
                comparison_data["sentiment_comparison"],
                f"{selected_category} - {selected_subcategory}"
            )
            st.pyplot(fig)

            # 相関情報
            sentiment_data = comparison_data["sentiment_comparison"]
            st.markdown(f"""
            **📈 感情分析相関:**
            - 相関係数: {sentiment_data.get('sentiment_correlation', 0):.3f}
            - ポジティブバイアス差分: {sentiment_data.get('positive_bias_delta', 0):.3f}
            """)
        else:
            st.info("感情分析比較データがありません")

    with tab4:
        if "data_quality" in comparison_data:
            quality_data = comparison_data["data_quality"]
            st.markdown("**🔍 データ品質情報:**")
            st.json(quality_data)
        else:
            st.info("データ品質情報がありません")

elif viz_type == "統合分析":
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
            st.json(cross_data)
    else:
        st.info("統合分析データがありません")

# --- 従来の画像表示セクション（参考用） ---
with st.expander("従来の事前生成画像（参考）"):
    st.header("事前生成画像（参考用）")

    def get_latest_visuals_dir():
        # integratedの日付ディレクトリと同じ日付のanalysis_visuals/配下を参照
        # ローカル・S3共にcorporate_bias_datasets/analysis_visuals/YYYYMMDD/に統一
        latest_dir = get_latest_integrated_dir()
        if not latest_dir:
            return None
        date_str = os.path.basename(latest_dir)
        visuals_dir = os.path.join("corporate_bias_datasets/analysis_visuals", date_str)
        if not os.path.exists(visuals_dir):
            return None
        return visuals_dir

    visuals_dir = get_latest_visuals_dir()
    if not visuals_dir:
        st.warning("画像指標ディレクトリが見つかりません")
    else:
        # サブディレクトリごとに画像を表示
        for subdir in os.listdir(visuals_dir):
            subdir_path = os.path.join(visuals_dir, subdir)
            if os.path.isdir(subdir_path):
                st.subheader(f"{subdir} の画像指標")
                images = [f for f in os.listdir(subdir_path) if f.lower().endswith(".png")]
                for img in images:
                    img_path = os.path.join(subdir_path, img)
                    st.image(img_path, caption=img)