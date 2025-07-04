#!/usr/bin/env python
# coding: utf-8

"""
企業バイアス分析 - データ可視化ダッシュボード

Streamlitを使用して、企業バイアス分析の結果データを可視化するダッシュボードです。
"""

import os
import json
import glob
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from datetime import datetime
import matplotlib as mpl
import matplotlib.font_manager as fm
from dotenv import load_dotenv
from src.utils.storage_utils import get_s3_client, S3_BUCKET_NAME, get_latest_file, load_json
from src.analysis.ranking_metrics import get_exposure_market_data, compute_rank_metrics, MARKET_SHARES, get_timeseries_exposure_market_data
import importlib
serp_metrics = importlib.import_module('src.analysis.serp_metrics')

# 利用可能な日本語フォントを優先的に取得
import matplotlib.pyplot as plt
import japanize_matplotlib

# 環境変数の読み込み
load_dotenv()

# ヒラギノ角ゴシックのパス（W3を例に）
font_path = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = prop.get_name()
plt.rcParams['font.sans-serif'] = [prop.get_name()]
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

# スタイル設定を適用
set_plot_style()

# ページ設定
st.set_page_config(
    page_title="企業バイアス分析ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
                    "生差分": metrics.get("raw_delta"),
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

# --- 画像指標セクション ---
st.header("画像指標（integrated仕様）")

def get_latest_visuals_dir():
    # integratedの日付ディレクトリと同じ日付のanalysis_visuals/配下を参照
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