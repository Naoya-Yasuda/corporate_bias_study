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
from src.utils.storage_utils import get_s3_client, S3_BUCKET_NAME, get_latest_file
from src.utils.file_utils import load_json
from src.analysis.ranking_metrics import get_exposure_market_data, compute_rank_metrics, MARKET_SHARES, get_timeseries_exposure_market_data
import importlib
serp_metrics = importlib.import_module('src.analysis.serp_metrics')

# 利用可能な日本語フォントを優先的に取得
import matplotlib.pyplot as plt
import japanize_matplotlib  # 追加

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

# --- データ分析セクション ---
# st.header("データ分析")

# データファイルの取得
data_files = get_data_files()

if not data_files:
    st.warning("データファイルが見つかりません。まずはデータ収集を実行してください。")
else:
    # データタイプの優先順
    type_order = [
        "Perplexity 感情スコア", "OpenAI 感情スコア", "Perplexity ランキング", "OpenAI ランキング", "Perplexity 引用リンク", "OpenAI 引用リンク", "その他"
    ]
    # データタイプ一覧を優先順で並べる
    data_types = []
    for t in type_order:
        if t in [f["type"] for f in data_files]:
            data_types.append(t)
    # デフォルトを感情スコア系に
    default_type = None
    for t in data_types:
        if "感情スコア" in t:
            default_type = t
            break
    selected_type = st.sidebar.selectbox("データタイプ", ["すべて"] + data_types, index=(1 if default_type else 0))

    # フィルタリング
    if selected_type != "すべて":
        filtered_files = [f for f in data_files if f["type"] == selected_type]
    else:
        # データタイプの優先順でファイルを並べる
        def file_type_order(f):
            try:
                return type_order.index(f["type"])
            except ValueError:
                return len(type_order)
        filtered_files = sorted(data_files, key=file_type_order)

    # ページ選択
    view_options = ["単一データ分析", "時系列分析", "サービス時系列分析"]
    selected_view = st.sidebar.radio("表示モード", view_options)

    if selected_view == "単一データ分析":
        # 単一ファイル選択モード
        # ファイル選択
        file_options = {f["display_name"]: f for f in filtered_files}
        selected_file_name = st.sidebar.selectbox(
            "ファイルを選択",
            list(file_options.keys()),
            index=0 if file_options else None
        )

        if not selected_file_name:
            st.warning("選択可能なファイルがありません。フィルターを変更するか、データ収集を実行してください。")
            st.stop()

        selected_file = file_options[selected_file_name]
        st.sidebar.info(f"選択ファイル: {selected_file['name']}")

        # ファイル読み込み
        try:
            data = load_json(selected_file['path'])
            if data is None:
                st.error(f"ファイルの読み込みに失敗しました: {selected_file['path']}")
                st.stop()
            st.sidebar.success("ファイルの読み込みに成功しました")
        except Exception as e:
            st.error(f"ファイルの読み込みエラー: {e}")
            st.stop()

        # カテゴリ一覧を抽出
        categories = list(data.keys())
        selected_category = st.sidebar.selectbox("カテゴリを選択", categories)

        # 選択したカテゴリのデータを表示
        st.header(f"カテゴリ: {selected_category}")

        # データタイプに応じた可視化
        if "感情スコア" in selected_file["type"]:
            # 感情スコアの可視化
            st.subheader("感情スコア分析")

            category_data = data[selected_category]

            # データ構造判定
            is_old_multi_run = selected_file["is_multi_run"] and "scores" in category_data
            is_new_multi_run = isinstance(category_data, dict) and any(isinstance(val, dict) and "masked_avg" in val for val in category_data.values())
            is_single_run = not (is_old_multi_run or is_new_multi_run)

            # 複数回実行の場合（古い形式）
            if is_old_multi_run:
                scores_data = category_data["scores"]

                # DataFrameに変換
                records = []
                for service, service_data in scores_data.items():
                    for mask_type, scores in service_data.items():
                        for score in scores:
                            records.append({
                                "service": service,
                                "mask_type": "マスクあり" if mask_type == "masked" else "マスクなし",
                                "score": score
                            })

                df = pd.DataFrame(records)

                # 統計情報
                st.markdown("### 統計情報")
                stats_df = df.groupby(["service", "mask_type"])["score"].agg(["mean", "std", "min", "max"]).reset_index()
                stats_df.columns = ["サービス", "マスクタイプ", "平均", "標準偏差", "最小", "最大"]
                st.dataframe(stats_df)

                # 箱ひげ図
                st.markdown("### 感情スコア分布")
                fig, ax = plt.subplots()
                sns.boxplot(x="service", y="score", hue="mask_type", data=df, ax=ax)
                ax.set_xlabel("サービス", fontproperties=prop)
                ax.set_ylabel("感情スコア", fontproperties=prop)
                ax.set_title(f"{selected_category} の感情スコア分布", fontproperties=prop)
                plt.tight_layout()
                st.pyplot(fig)

                # バイアス指標
                if "bias_metrics" in category_data:
                    st.markdown("### バイアス指標")
                    bias_metrics = category_data["bias_metrics"]
                    bias_df = pd.DataFrame([
                        {"サービス": service, "バイアス指標": metrics.get("bias_index", 0)}
                        for service, metrics in bias_metrics.items()
                    ])

                    # バイアス指標の棒グラフ
                    fig, ax = plt.subplots()
                    sns.barplot(x="サービス", y="バイアス指標", data=bias_df, ax=ax)
                    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
                    ax.set_title(f"{selected_category} のバイアス指標", fontproperties=prop)
                    ax.set_xlabel("サービス", fontproperties=prop)
                    ax.set_ylabel("バイアス指標", fontproperties=prop)
                    plt.tight_layout()
                    st.pyplot(fig)

                    # バイアス指標のテーブル
                    st.dataframe(bias_df)

            # 複数回実行の場合（新しい形式）
            elif is_new_multi_run:
                # サブカテゴリ選択
                subcategories = list(category_data.keys())
                selected_subcategory = st.selectbox("サブカテゴリを選択", subcategories)
                subcategory_data = category_data[selected_subcategory]

                # データフレーム作成
                if "masked_avg" in subcategory_data and "unmasked_avg" in subcategory_data and isinstance(subcategory_data["unmasked_avg"], dict):
                    masked_score = subcategory_data["masked_avg"]

                    # 生データの確認用
                    with st.expander("生データと処理ステップの確認"):
                        st.json(subcategory_data)

                        st.write("### データ処理ステップ")
                        if "masked_values" in subcategory_data:
                            st.write(f"masked_values: {subcategory_data['masked_values']}")
                        if "all_masked_results" in subcategory_data:
                            st.write(f"all_masked_results: {subcategory_data['all_masked_results']}")

                        if "unmasked_values" in subcategory_data:
                            st.write("unmasked_values:")
                            for service, vals in subcategory_data["unmasked_values"].items():
                                st.write(f"  {service}: {vals}")

                    # マスクありのプロンプトを表示
                    if "masked_example" in subcategory_data:
                        with st.expander("プロンプトを表示"):
                            st.markdown("""
                            <style>
                            .prompt-box {
                                padding-bottom: 10px;
                                margin-top: -1rem;
                                background-color: transparent;
                                color: #f5f5f5;
                                white-space: pre-wrap;
                            }
                            </style>
                            """, unsafe_allow_html=True)
                            st.markdown(f'<div class="prompt-box">{subcategory_data["masked_example"]}</div>', unsafe_allow_html=True)

                    records = []

                    # unmasked_valuesのリストから個々のスコアを取得
                    if "unmasked_values" in subcategory_data and isinstance(subcategory_data["unmasked_values"], dict):
                        for service, values in subcategory_data["unmasked_values"].items():
                            if isinstance(values, list) and len(values) > 0:
                                # 生データを表示用に整形
                                if all(isinstance(v, (int, float)) for v in values):
                                    values_str = ", ".join([f"{v:.1f}" for v in values])
                                else:
                                    values_str = str(values)

                                records.append({
                                    "サービス": service,
                                    "マスクなしスコア": subcategory_data["unmasked_avg"].get(service, 0),  # 平均値を使用
                                    "マスクありスコア": masked_score,
                                    "差分": subcategory_data["unmasked_avg"].get(service, 0) - masked_score,
                                    "元データ": values_str
                                })
                    else:
                        # 平均値のみ使用
                        for service, score in subcategory_data["unmasked_avg"].items():
                            records.append({
                                "サービス": service,
                                "マスクなしスコア": score,
                                "マスクありスコア": masked_score,
                                "差分": score - masked_score,
                                "元データ": "不明"
                            })

                    if records:
                        df = pd.DataFrame(records)

                        # 表形式で表示（生データも含める）
                        st.markdown("### スコアデータ詳細")
                        st.dataframe(df.style.format({
                            "マスクなしスコア": "{:.1f}",
                            "マスクありスコア": "{:.1f}",
                            "差分": "{:.1f}"
                        }))

                        # スコア比較グラフ（平均値ベース）
                        st.markdown("### 感情スコア比較")
                        fig, ax = plt.subplots()

                        x = np.arange(len(df))
                        width = 0.35

                        bar1 = ax.bar(x - width/2, df["マスクなしスコア"], width, label="マスクなし")
                        bar2 = ax.bar(x + width/2, df["マスクありスコア"], width, label="マスクあり")

                        # バーの上に値を表示
                        for i, bar in enumerate(bar1):
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)

                        for i, bar in enumerate(bar2):
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                                    f'{height:.1f}', ha='center', va='bottom', fontsize=8)

                        ax.set_xticks(x)
                        ax.set_xticklabels(df["サービス"], fontproperties=prop)
                        ax.set_ylabel("感情スコア", fontproperties=prop)
                        ax.set_title(f"{selected_category} - {selected_subcategory} の感情スコア比較", fontproperties=prop)
                        ax.legend(loc='upper right', fontsize=8, prop=prop)
                        plt.tight_layout()

                        st.pyplot(fig)

                        # バイアスの棒グラフ
                        st.markdown("### バイアス（差分）")
                        fig, ax = plt.subplots()

                        bars = sns.barplot(x="サービス", y="差分", data=df, ax=ax)

                        # バーの上に値を表示
                        for i, bar in enumerate(ax.patches):
                            height = bar.get_height()
                            ax.text(bar.get_x() + bar.get_width()/2.,
                                    0 if height < 0 else height,
                                    f'{height:.1f}',
                                    ha='center',
                                    va='bottom' if height >= 0 else 'top',
                                    fontsize=8)

                        ax.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
                        ax.set_title(f"{selected_category} - {selected_subcategory} のバイアス（マスクなし - マスクあり）", fontproperties=prop)
                        ax.set_xlabel("サービス", fontproperties=prop)
                        ax.set_ylabel("バイアス", fontproperties=prop)
                        ax.legend(prop=prop)
                        plt.tight_layout()

                        st.pyplot(fig)

                    else:
                        st.warning("このサブカテゴリにはスコアデータがありません")
                else:
                    # キーの有無を確認
                    available_keys = list(subcategory_data.keys())
                    st.warning(f"このサブカテゴリには必要なスコアデータがありません。利用可能なキー: {available_keys}")

            # 単一実行の場合
            else:
                # DataFrameに変換
                records = []
                for service, service_data in category_data.items():
                    if "score" in service_data:
                        records.append({
                            "サービス": service,
                            "マスクなしスコア": service_data.get("score", {}).get("unmasked", 0),
                            "マスクありスコア": service_data.get("score", {}).get("masked", 0),
                            "差分": service_data.get("score", {}).get("unmasked", 0) - service_data.get("score", {}).get("masked", 0)
                        })

                if records:
                    df = pd.DataFrame(records)

                    # スコア比較グラフ
                    st.markdown("### 感情スコア比較")
                    fig, ax = plt.subplots()
                    x = np.arange(len(df))
                    width = 0.35

                    ax.bar(x - width/2, df["マスクなしスコア"], width, label="マスクなし")
                    ax.bar(x + width/2, df["マスクありスコア"], width, label="マスクあり")

                    ax.set_xticks(x)
                    ax.set_xticklabels(df["サービス"], fontproperties=prop)
                    ax.set_ylabel("感情スコア", fontproperties=prop)
                    ax.set_title(f"{selected_category} の感情スコア比較", fontproperties=prop)
                    ax.legend(prop=prop)
                    plt.tight_layout()

                    st.pyplot(fig)

                    # データテーブル
                    st.dataframe(df)
                else:
                    # 生データを表示して確認
                    st.warning("このカテゴリにはスコアデータがありません")
                    st.json(category_data)

        elif "ランキング" in selected_file["type"]:
            # ランキングの可視化
            st.subheader("ランキング分析")

            category_data = data.get(selected_category, None)
            if category_data is None:
                st.error("選択したカテゴリにデータが存在しません（data[selected_category] is None）")
            elif not category_data:
                st.error("選択したカテゴリのデータが空です（data[selected_category] is empty）")
            elif ("all_rankings" not in category_data and "ranking" not in category_data and
                  not any(isinstance(v, dict) and ("all_rankings" in v or "ranking" in v) for v in category_data.values())):
                st.error("このカテゴリにランキングデータ（all_rankings/ranking）が見つかりません。データ構造が異なるか、ファイルにランキングデータが含まれていない可能性があります。")
                st.write("データ構造:", category_data)
            elif (isinstance(category_data, dict) and not ("all_rankings" in category_data or "ranking" in category_data)):
                # サブカテゴリ構造の場合
                subcategories = list(category_data.keys())
                selected_subcategory = st.selectbox("サブカテゴリを選択", subcategories)
                subcategory_data = category_data[selected_subcategory]

                # --- プロンプト表示（queryをexpanderで表示） ---
                if "query" in subcategory_data:
                    with st.expander("プロンプトを表示"):
                        st.markdown("""
                        <style>
                        .prompt-box {
                            padding-bottom: 10px;
                            margin-top: -1rem;
                            background-color: transparent;
                            color: #f5f5f5;
                            white-space: pre-wrap;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        st.markdown(f'<div class="prompt-box">{subcategory_data["query"]}</div>', unsafe_allow_html=True)

                if selected_file["is_multi_run"] and "all_rankings" in subcategory_data:
                    rankings_data = subcategory_data["all_rankings"]
                    # ...（既存の複数回実行の可視化処理）...
                    # オススメ順（平均ランキング）の可視化
                    if "avg_ranking" in subcategory_data:
                        st.markdown("### オススメ順（平均ランキング）")
                        avg_ranking = subcategory_data["avg_ranking"]
                        rank_details = subcategory_data.get("rank_details", {})
                        records = []
                        std_list = []
                        avg_list = []
                        all_ranks_dict = {}
                        for i, service in enumerate(avg_ranking, 1):
                            detail = rank_details.get(service, {})
                            avg_rank = detail.get('avg_rank', 0.0)
                            std_dev = detail.get('std_dev', 0.0)
                            all_ranks = detail.get('all_ranks', [])
                            records.append({
                                "順位": i,
                                "サービス": service,
                                "平均順位": f"{avg_rank:.2f}",
                                "標準偏差": f"{std_dev:.2f}",
                                "全順位": all_ranks
                            })
                            avg_list.append(avg_rank)
                            std_list.append(std_dev)
                            if all_ranks:
                                all_ranks_dict[service] = all_ranks
                        st.dataframe(records)
                        # 平均順位の折れ線グラフ
                        st.markdown("#### 平均順位の推移（オススメ順）")
                        fig, ax = plt.subplots()
                        ax.plot([i+1 for i in range(len(avg_list))], avg_list, marker='o')
                        ax.set_xticks([i+1 for i in range(len(avg_ranking))])
                        ax.set_xticklabels(avg_ranking, rotation=45, ha='right', fontproperties=prop)
                        ax.set_xlabel('サービス', fontproperties=prop)
                        ax.set_ylabel('平均順位', fontproperties=prop)
                        ax.set_title('平均順位の推移', fontproperties=prop)
                        ax.invert_yaxis()  # 小さい値が上
                        plt.tight_layout()
                        st.pyplot(fig)
                        # 標準偏差の棒グラフ（全て0または空なら表示しない）
                        if any(std > 0 for std in std_list):
                            st.markdown("#### 標準偏差（ばらつき）の棒グラフ")
                            fig, ax = plt.subplots()
                            ax.bar([i+1 for i in range(len(std_list))], std_list, tick_label=avg_ranking)
                            ax.set_xticklabels(avg_ranking, rotation=45, ha='right', fontproperties=prop)
                            ax.set_xlabel('サービス', fontproperties=prop)
                            ax.set_ylabel('標準偏差', fontproperties=prop)
                            ax.set_title('標準偏差（ばらつき）', fontproperties=prop)
                            plt.tight_layout()
                            st.pyplot(fig)
                        # 全順位の箱ひげ図（全サービスでばらつきがある場合のみ）
                        if all_ranks_dict and any(len(set(all_ranks_dict[s])) > 1 for s in avg_ranking if s in all_ranks_dict):
                            st.markdown("#### 全順位の箱ひげ図")
                            fig, ax = plt.subplots()
                            ax.boxplot([all_ranks_dict[s] for s in avg_ranking], labels=avg_ranking, patch_artist=True)
                            ax.set_xlabel('サービス', fontproperties=prop)
                            ax.set_ylabel('順位', fontproperties=prop)
                            ax.set_title('全実行における順位の分布', fontproperties=prop)
                            ax.invert_yaxis()  # 小さい値が上
                            plt.tight_layout()
                            st.pyplot(fig)
                elif "ranking" in subcategory_data:
                    ranking = subcategory_data["ranking"]
                    # ...（既存の単一実行の可視化処理）...
                else:
                    st.error("このサブカテゴリにランキングデータがありません（all_rankings/rankingが存在しません）")
                    st.write("サブカテゴリデータ:", subcategory_data)
            else:
                # 既存の分岐
                if selected_file["is_multi_run"] and "all_rankings" in category_data:
                    rankings_data = category_data["all_rankings"]
                    # ...（既存の複数回実行の可視化処理）...
                    # オススメ順（平均ランキング）の可視化
                    if "avg_ranking" in category_data:
                        st.markdown("### オススメ順（平均ランキング）")
                        avg_ranking = category_data["avg_ranking"]
                        rank_details = category_data.get("rank_details", {})
                        records = []
                        std_list = []
                        avg_list = []
                        all_ranks_dict = {}
                        for i, service in enumerate(avg_ranking, 1):
                            detail = rank_details.get(service, {})
                            avg_rank = detail.get('avg_rank', 0.0)
                            std_dev = detail.get('std_dev', 0.0)
                            all_ranks = detail.get('all_ranks', [])
                            records.append({
                                "順位": i,
                                "サービス": service,
                                "平均順位": f"{avg_rank:.2f}",
                                "標準偏差": f"{std_dev:.2f}",
                                "全順位": all_ranks
                            })
                            avg_list.append(avg_rank)
                            std_list.append(std_dev)
                            if all_ranks:
                                all_ranks_dict[service] = all_ranks
                        st.dataframe(records)
                        # 平均順位の折れ線グラフ
                        st.markdown("#### 平均順位の推移（オススメ順）")
                        fig, ax = plt.subplots()
                        ax.plot([i+1 for i in range(len(avg_list))], avg_list, marker='o')
                        ax.set_xticks([i+1 for i in range(len(avg_ranking))])
                        ax.set_xticklabels(avg_ranking, rotation=45, ha='right', fontproperties=prop)
                        ax.set_xlabel('サービス', fontproperties=prop)
                        ax.set_ylabel('平均順位', fontproperties=prop)
                        ax.set_title('平均順位の推移', fontproperties=prop)
                        ax.invert_yaxis()  # 小さい値が上
                        plt.tight_layout()
                        st.pyplot(fig)
                        # 標準偏差の棒グラフ（全て0または空なら表示しない）
                        if any(std > 0 for std in std_list):
                            st.markdown("#### 標準偏差（ばらつき）の棒グラフ")
                            fig, ax = plt.subplots()
                            ax.bar([i+1 for i in range(len(std_list))], std_list, tick_label=avg_ranking)
                            ax.set_xticklabels(avg_ranking, rotation=45, ha='right', fontproperties=prop)
                            ax.set_xlabel('サービス', fontproperties=prop)
                            ax.set_ylabel('標準偏差', fontproperties=prop)
                            ax.set_title('標準偏差（ばらつき）', fontproperties=prop)
                            plt.tight_layout()
                            st.pyplot(fig)
                        # 全順位の箱ひげ図（全サービスでばらつきがある場合のみ）
                        if all_ranks_dict and any(len(set(all_ranks_dict[s])) > 1 for s in avg_ranking if s in all_ranks_dict):
                            st.markdown("#### 全順位の箱ひげ図")
                            fig, ax = plt.subplots()
                            ax.boxplot([all_ranks_dict[s] for s in avg_ranking], labels=avg_ranking, patch_artist=True)
                            ax.set_xlabel('サービス', fontproperties=prop)
                            ax.set_ylabel('順位', fontproperties=prop)
                            ax.set_title('全実行における順位の分布', fontproperties=prop)
                            ax.invert_yaxis()  # 小さい値が上
                            plt.tight_layout()
                            st.pyplot(fig)
                elif "ranking" in category_data:
                    ranking = category_data["ranking"]
                    # ...（既存の単一実行の可視化処理）...
                else:
                    st.error("このカテゴリにランキングデータがありません（all_rankings/rankingが存在しません）")
                    st.write("カテゴリデータ:", category_data)

        elif "引用リンク" in selected_file["type"]:
            # 引用リンクの可視化
            st.subheader("引用リンク分析")
            category_data = data[selected_category]
            # --- Google SERP比較 ---
            import json
            import os
            # Google SERPデータのパスを自動推定（同日付 or 直近）
            serp_date = selected_file["date_raw"] or selected_file["date"] or ""
            analysis_path = f"results/perplexity_analysis/{serp_date}/analysis_results.json"
            if not os.path.exists(analysis_path):
                # S3からダウンロードを試みる
                s3_key = analysis_path
                try:
                    s3_client = get_s3_client()
                    response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
                    os.makedirs(os.path.dirname(analysis_path), exist_ok=True)
                    with open(analysis_path, "wb") as f:
                        f.write(response["Body"].read())
                    st.info(f"S3から分析結果データをダウンロードしました: {analysis_path}")
                except Exception as e:
                    st.warning(f"分析結果データが見つかりません: {analysis_path} (S3も失敗)\n{e}")
            if os.path.exists(analysis_path):
                with open(analysis_path, "r", encoding="utf-8") as f:
                    analysis_results = json.load(f)
                if selected_category in analysis_results:
                    comp = analysis_results[selected_category]
                    st.markdown("### Google検索結果との比較（分析済みデータ）")
                    # ランキング類似度
                    st.markdown("#### ランキング類似度指標")
                    st.write({
                        "RBO": comp["ranking_similarity"]["rbo"],
                        "Kendall Tau": comp["ranking_similarity"]["kendall_tau"],
                        "Overlap Ratio": comp["ranking_similarity"]["overlap_ratio"]
                    })
                    # 公式/非公式・ポジ/ネガ比率
                    st.markdown("#### 公式/非公式・ポジ/ネガ比率（Google vs Perplexity）")
                    import matplotlib.pyplot as plt
                    import numpy as np
                    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
                    labels = ["公式", "非公式"]
                    google_official = [comp["content_comparison"]["google_official_ratio"], 1-comp["content_comparison"]["google_official_ratio"]]
                    pplx_official = [0, 1]  # Perplexity引用は公式/非公式判定不可のため仮
                    axes[0].bar(labels, google_official, color=["#4caf50", "#f44336"])
                    axes[0].set_title("Google公式/非公式")
                    axes[1].bar(labels, pplx_official, color=["#4caf50", "#f44336"])
                    axes[1].set_title("Perplexity公式/非公式")
                    plt.tight_layout()
                    st.pyplot(fig)
                    # ポジ/ネガ比率
                    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
                    labels = ["ポジティブ", "ネガティブ"]
                    google_neg = [1-comp["content_comparison"]["google_negative_ratio"], comp["content_comparison"]["google_negative_ratio"]]
                    pplx_neg = [1, 0]  # Perplexity引用はポジ/ネガ判定不可のため仮
                    axes[0].bar(labels, google_neg, color=["#2196f3", "#ff9800"])
                    axes[0].set_title("Googleポジ/ネガ")
                    axes[1].bar(labels, pplx_neg, color=["#2196f3", "#ff9800"])
                    axes[1].set_title("Perplexityポジ/ネガ")
                    plt.tight_layout()
                    st.pyplot(fig)
                    # ドメインランキング比較
                    st.markdown("#### ドメインランキング比較")
                    st.write("Google:", comp.get("google_domains", []))
                    st.write("Perplexity:", comp.get("pplx_domains", []))
                else:
                    st.warning(f"分析結果データにカテゴリ {selected_category} が見つかりません")
            else:
                st.warning(f"分析結果データが見つかりません: {analysis_path}")

            # --- ここから従来の引用リンク（Perplexity側）可視化を復活 ---
            # サブカテゴリがある場合
            if isinstance(category_data, dict) and len(category_data) > 0:
                # サブカテゴリの選択
                subcategories = list(category_data.keys())
                selected_subcategory = st.selectbox("サブカテゴリを選択", subcategories)

                subcategory_data = category_data[selected_subcategory]
                # --- プロンプト表示（queryをexpanderで表示） ---
                if "query" in subcategory_data:
                    with st.expander("プロンプトを表示"):
                        st.markdown("""
                        <style>
                        .prompt-box {
                            padding-bottom: 10px;
                            margin-top: -1rem;
                            background-color: transparent;
                            color: #f5f5f5;
                            white-space: pre-wrap;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        st.markdown(f'<div class="prompt-box">{subcategory_data["query"]}</div>', unsafe_allow_html=True)
                # --- ここまでプロンプト表示 ---
                # 複数回実行の場合
                if "all_runs" in subcategory_data:
                    runs_data = subcategory_data["all_runs"]

                    # ドメインランキングがある場合
                    if "domain_rankings" in subcategory_data:
                        st.markdown("### ドメイン分析（Perplexity引用リンク）")
                        domain_rankings = subcategory_data["domain_rankings"]
                        rankings_df = pd.DataFrame(domain_rankings)
                        top_domains = rankings_df.head(10)

                        # ドメイン出現率のグラフ（全て1.0なら非表示）
                        if not all(top_domains["appearance_ratio"] == 1.0):
                            st.markdown("#### ドメイン出現率")
                            fig, ax = plt.subplots()
                            bars = ax.bar(top_domains["domain"], top_domains["appearance_ratio"])
                            for bar in bars:
                                height = bar.get_height()
                                ax.text(bar.get_x() + bar.get_width()/2., height,
                                        f'{height:.2f}',
                                        ha='center', va='bottom')
                            ax.set_xticklabels(top_domains["domain"], rotation=45, ha='right', fontproperties=prop)
                            ax.set_ylabel('出現率', fontproperties=prop)
                            ax.set_title(f"{selected_category} - {selected_subcategory} のドメイン出現率", fontproperties=prop)
                            plt.tight_layout()
                            st.pyplot(fig)

                        # ドメイン平均ランクのグラフ（y軸反転）
                        st.markdown("#### ドメイン平均ランク")
                        fig, ax = plt.subplots()
                        ax.plot(range(len(top_domains)), top_domains["avg_rank"], marker='o')
                        ax.set_xticks(range(len(top_domains)))
                        ax.set_xticklabels(top_domains["domain"], rotation=45, ha='right', fontproperties=prop)
                        ax.set_ylabel('平均ランク', fontproperties=prop)
                        ax.set_title(f"{selected_category} - {selected_subcategory} のドメイン平均ランク", fontproperties=prop)
                        ax.invert_yaxis()  # 小さい値が上
                        plt.tight_layout()
                        st.pyplot(fig)

                        # ドメインごとの全ランクの箱ひげ図（ばらつきがある場合のみ）
                        if any(len(set(r["all_ranks"])) > 1 for _, r in top_domains.iterrows() if "all_ranks" in r):
                            st.markdown("#### ドメイン順位の箱ひげ図")
                            fig, ax = plt.subplots()
                            box_data = [r["all_ranks"] for _, r in top_domains.iterrows() if "all_ranks" in r]
                            labels = [r["domain"] for _, r in top_domains.iterrows() if "all_ranks" in r]
                            ax.boxplot(box_data, labels=labels, patch_artist=True)
                            ax.set_xlabel('ドメイン', fontproperties=prop)
                            ax.set_ylabel('順位', fontproperties=prop)
                            ax.set_title('全実行におけるドメイン順位の分布', fontproperties=prop)
                            ax.invert_yaxis()  # 小さい値が上
                            plt.tight_layout()
                            st.pyplot(fig)

                        # データテーブル
                        st.markdown("#### ドメインランキングデータ")
                        st.dataframe(rankings_df)

                    # 個別の実行データを表示
                    st.markdown("### 個別実行データ（引用元URL一覧）")
                    for i, run in enumerate(runs_data):
                        with st.expander(f"実行 {i+1}"):
                            if "citations" in run:
                                citations = run["citations"]
                                citations_df = pd.DataFrame(citations)
                                st.dataframe(citations_df)
                                # 回答内容を表示（消さない）
                                if "answer" in run:
                                    st.markdown("#### 回答内容")
                                    st.markdown("""
                                    <style>
                                    .answer-box {
                                        padding: 10px;
                                        margin-top: 10px;
                                        background: rgba(30, 30, 30, 0.7);
                                        border-radius: 5px;
                                        color: #f5f5f5;
                                        white-space: pre-wrap;
                                    }
                                    </style>
                                    """, unsafe_allow_html=True)
                                    st.write(f'<div class="answer-box">{run["answer"]}</div>', unsafe_allow_html=True)
                            else:
                                st.write("引用データがありません")

                # 単一実行の場合
                elif "run" in subcategory_data and "citations" in subcategory_data["run"]:
                    citations = subcategory_data["run"]["citations"]
                    citations_df = pd.DataFrame(citations)
                    st.markdown("### 引用リンク（Perplexity単一実行）")
                    st.dataframe(citations_df)
                    # 回答内容を表示（消さない）
                    if "answer" in subcategory_data["run"]:
                        st.markdown("#### 回答内容")
                        st.markdown("""
                        <style>
                        .answer-box {
                            padding: 10px;
                            margin-top: 10px;
                            background: rgba(30, 30, 30, 0.7);
                            border-radius: 5px;
                            color: #f5f5f5;
                            white-space: pre-wrap;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        st.write(f'<div class="answer-box">{subcategory_data["run"]["answer"]}</div>', unsafe_allow_html=True)
                    # ドメイン頻度のグラフ
                    if len(citations_df) > 0 and "domain" in citations_df.columns:
                        domain_counts = citations_df["domain"].value_counts()
                        if not all(domain_counts == 1):
                            st.markdown("#### ドメイン頻度")
                            fig, ax = plt.subplots()
                            domain_counts.head(10).plot(kind="bar", ax=ax)
                            ax.set_ylabel("頻度", fontproperties=prop)
                            ax.set_title(f"{selected_category} - {selected_subcategory} のドメイン頻度", fontproperties=prop)
                            plt.tight_layout()
                            st.pyplot(fig)
                    # 平均ランクのグラフ（y軸反転）
                    if "rank" in citations_df.columns:
                        st.markdown("#### ドメイン平均ランク")
                        avg_rank_df = citations_df.groupby("domain")["rank"].mean().sort_values()
                        fig, ax = plt.subplots()
                        ax.plot(range(len(avg_rank_df)), avg_rank_df.values, marker='o')
                        ax.set_xticks(range(len(avg_rank_df)))
                        ax.set_xticklabels(avg_rank_df.index, rotation=45, ha='right', fontproperties=prop)
                        ax.set_ylabel('平均ランク', fontproperties=prop)
                        ax.set_title(f"{selected_category} - {selected_subcategory} のドメイン平均ランク", fontproperties=prop)
                        ax.invert_yaxis()
                        plt.tight_layout()
                        st.pyplot(fig)
                else:
                    st.warning("このカテゴリにはサブカテゴリデータがありません")
            else:
                st.warning("このカテゴリにはサブカテゴリデータがありません")
        else:
            st.warning("このデータタイプの可視化はまだサポートされていません")

    elif selected_view == "時系列分析":
        # 時系列データの分析モード
        st.header("時系列分析")

        # カテゴリ選択
        # 全ファイルを読み込んでカテゴリ一覧を取得
        unique_categories = set()
        for file_info in filtered_files:
            try:
                with open(file_info["path"], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for category in data.keys():
                        unique_categories.add(category)
            except Exception as e:
                pass

        if not unique_categories:
            st.warning("カテゴリデータが見つかりません。")
            st.stop()

        selected_category = st.selectbox("カテゴリを選択", sorted(list(unique_categories)))

        # 露出度・市場シェアの時系列データ
        st.subheader(f"露出度・市場シェアの日次変化: {selected_category}")
        df_metrics = get_timeseries_exposure_market_data(selected_category)
        if df_metrics is not None:
            subcategories = df_metrics["service"].unique()
            selected_subcategories = st.multiselect(
                "分析するサブカテゴリを選択",
                subcategories,
                default=subcategories[:3] if len(subcategories) > 3 else subcategories
            )
            if selected_subcategories:
                filtered_df = df_metrics[df_metrics["service"].isin(selected_subcategories)]
                # 露出度の時系列グラフ
                st.write("露出度の時系列推移")
                fig = plt.figure(figsize=(12, 6))
                for subcategory in selected_subcategories:
                    subcategory_data = filtered_df[filtered_df["service"] == subcategory]
                    plt.plot(subcategory_data["date"], subcategory_data["exposure_idx"], label=subcategory, marker='o')
                plt.title(f"{selected_category}の露出度推移")
                plt.xlabel("日付")
                plt.ylabel("露出度")
                plt.legend()
                plt.grid(True)
                st.pyplot(fig)
                # 市場シェアの時系列グラフ
                st.write("市場シェアの時系列推移")
                fig = plt.figure(figsize=(12, 6))
                for subcategory in selected_subcategories:
                    subcategory_data = filtered_df[filtered_df["service"] == subcategory]
                    plt.plot(subcategory_data["date"], subcategory_data["market_share"], label=subcategory, marker='o')
                plt.title(f"{selected_category}の市場シェア推移")
                plt.xlabel("日付")
                plt.ylabel("市場シェア")
                plt.legend()
                plt.grid(True)
                st.pyplot(fig)
                # データテーブルの表示
                st.write("時系列データ")
                st.dataframe(filtered_df)
        else:
            st.warning("時系列データが見つかりません。")

    elif selected_view == "サービス時系列分析":
        # 特定サービスの時系列分析モード
        st.header("サービス時系列分析")

        # カテゴリとサービスの一覧を取得
        all_services = {}
        for file_info in filtered_files:
            try:
                with open(file_info["path"], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for category, category_data in data.items():
                        if category not in all_services:
                            all_services[category] = {}

                        for subcategory, subcategory_data in category_data.items():
                            # サービス一覧の抽出方法はファイル構造に応じて調整
                            services = []

                            if "competitors" in subcategory_data:  # 新しい形式
                                services = subcategory_data["competitors"]
                            elif "unmasked_avg" in subcategory_data:
                                services = list(subcategory_data["unmasked_avg"].keys())

                            if services:
                                if subcategory not in all_services[category]:
                                    all_services[category][subcategory] = set()
                                all_services[category][subcategory].update(services)
            except Exception as e:
                pass

        if not all_services:
            st.warning("サービスデータが見つかりません。")
            st.stop()

        # カテゴリ選択
        selected_category = st.selectbox("カテゴリを選択", sorted(all_services.keys()))

        # サブカテゴリ選択
        if selected_category in all_services:
            selected_subcategory = st.selectbox("サブカテゴリを選択", sorted(all_services[selected_category].keys()))

            # サービス選択
            if selected_subcategory in all_services[selected_category]:
                selected_service = st.selectbox("サービスを選択", sorted(all_services[selected_category][selected_subcategory]))

                # 選択したサービスの時系列データを収集
                service_time_series = []

                for file_info in filtered_files:
                    if "感情スコア" in file_info["type"]:  # 感情スコアデータのみ
                        try:
                            with open(file_info["path"], "r", encoding="utf-8") as f:
                                data = json.load(f)

                                if selected_category in data and selected_subcategory in data[selected_category]:
                                    subcategory_data = data[selected_category][selected_subcategory]
                                    date = file_info["date_obj"]

                                    # スコアデータの取得方法はファイル構造に応じて調整
                                    unmasked_score = None
                                    masked_score = None

                                    if "unmasked_avg" in subcategory_data and selected_service in subcategory_data["unmasked_avg"]:
                                        unmasked_score = subcategory_data["unmasked_avg"][selected_service]
                                        masked_score = subcategory_data.get("masked_avg", 0)
                                    elif "scores" in subcategory_data:
                                        for service, service_data in subcategory_data["scores"].items():
                                            if service == selected_service and "unmasked" in service_data:
                                                unmasked_scores = service_data["unmasked"]
                                                unmasked_score = np.mean(unmasked_scores) if unmasked_scores else 0

                                                masked_scores = subcategory_data["scores"].get("masked", [])
                                                masked_score = np.mean(masked_scores) if masked_scores else 0

                                    if unmasked_score is not None and masked_score is not None:
                                        service_time_series.append({
                                            "日付": date,
                                            "マスクなしスコア": unmasked_score,
                                            "マスクありスコア": masked_score,
                                            "バイアス": unmasked_score - masked_score,
                                            "日付文字列": file_info["date"]
                                        })
                        except Exception as e:
                            st.warning(f"ファイル {file_info['name']} の読み込みエラー: {e}")

                if service_time_series:
                    # DataFrameに変換
                    df = pd.DataFrame(service_time_series)

                    # 日付でソート
                    df = df.sort_values("日付")

                    # 折れ線グラフ（すべてのスコア）
                    st.subheader(f"{selected_service} の時系列変化")

                    fig, ax = plt.subplots()

                    ax.plot(df["日付文字列"], df["マスクなしスコア"], marker='o', label="マスクなし", color='blue')
                    ax.plot(df["日付文字列"], df["マスクありスコア"], marker='s', label="マスクあり", color='green')
                    ax.plot(df["日付文字列"], df["バイアス"], marker='^', label="バイアス", color='red')

                    ax.set_xlabel("日付", fontproperties=prop)
                    ax.set_ylabel("スコア", fontproperties=prop)
                    ax.set_title(f"{selected_category} - {selected_subcategory} の {selected_service} 時系列変化", fontproperties=prop)
                    ax.legend(prop=prop)
                    ax.grid(True, alpha=0.3)
                    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
                    plt.xticks(rotation=45)
                    plt.tight_layout()

                    st.pyplot(fig)

                    # データテーブル
                    st.subheader("時系列データテーブル")
                    display_df = df[["日付文字列", "マスクなしスコア", "マスクありスコア", "バイアス"]].copy()
                    display_df.columns = ["日付", "マスクなしスコア", "マスクありスコア", "バイアス"]
                    st.dataframe(display_df)
                else:
                    st.warning(f"{selected_service} の時系列データが見つかりません。")
        else:
            st.warning("表示モードを選択してください。")

    # 生データの表示 (単一データ分析モードのみ)
    if selected_view == "単一データ分析":
        with st.expander("生データを表示"):
            st.json(data[selected_category])

    # フッター
    st.markdown("---")
    st.markdown("企業バイアス分析ダッシュボード © 2025")

# --- 画像指標セクション ---
st.header("画像指標")

# 画像ファイルの取得
image_files = get_image_files()

if not image_files:
    st.warning("画像ファイルが見つかりません。まずはデータ分析を実行してください。")
else:
    # 画像タイプでフィルタリングするオプション
    image_types = sorted(list(set([f["type"] for f in image_files])))
    selected_type = st.sidebar.selectbox("画像タイプ", ["すべて"] + image_types)

    # フィルタリング
    if selected_type != "すべて":
        filtered_files = [f for f in image_files if f["type"] == selected_type]
    else:
        filtered_files = image_files

    # 実行回数（runs数）で降順ソート（同日付ならruns数が多い方を上に）
    def extract_runs(file):
        import re
        m = re.search(r'_(\d+)runs\.json', file["name"])
        return int(m.group(1)) if m else 1
    filtered_files = sorted(filtered_files, key=lambda f: (f["date_obj"], extract_runs(f)), reverse=True)

    # 画像ファイル選択
    file_options = {f["display_name"]: f for f in filtered_files}
    selected_file_name = st.sidebar.selectbox(
        "画像ファイルを選択",
        list(file_options.keys()),
        index=0 if file_options else None
    )

    if selected_file_name:
        selected_file = file_options[selected_file_name]
        st.sidebar.info(f"選択ファイル: {selected_file['name']}")

        # 画像タイプに応じたタイトルを表示
        st.subheader(selected_file["type"])

        # S3から画像を取得して表示
        try:
            s3_client = get_s3_client()
            response = s3_client.get_object(
                Bucket=S3_BUCKET_NAME,
                Key=selected_file["path"].replace(f"s3://{S3_BUCKET_NAME}/", "")
            )
            image_data = response['Body'].read()
            st.image(image_data, caption=selected_file["display_name"])
        except Exception as e:
            st.error(f"画像の読み込みに失敗しました: {e}")