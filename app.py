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
from src.utils.s3_utils import get_s3_client, S3_BUCKET_NAME, get_latest_file
from src.utils.file_utils import load_json
from src.analysis.ranking_metrics import get_exposure_market_data, compute_rank_metrics, MARKET_SHARES, get_timeseries_exposure_market_data

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

# サイドバー
st.sidebar.header("データ選択")

# 結果ファイルの検索
def get_result_files():
    """S3から利用可能な結果ファイルを取得"""
    try:
        s3_client = get_s3_client()
        prefix = 'results/'
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)

        if 'Contents' not in response:
            st.warning("S3バケットにファイルが見つかりません。")
            return []

        files = []
        for content in response['Contents']:
            file_path = content['Key']
            file_name = os.path.basename(file_path)

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
            is_multi_run = "_runs.json" in file_name or "_3runs.json" in file_name or "_5runs.json" in file_name or "_10runs.json" in file_name
            runs_suffix = "（複数回実行）" if is_multi_run else "（単一実行）"

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

        # 日付の新しい順にソート
        files.sort(key=lambda x: x["date_obj"], reverse=True)
        return files

    except Exception as e:
        st.error(f"S3からのファイル一覧取得エラー: {e}")
        return []

# 結果ファイルの一覧を取得
result_files = get_result_files()

if not result_files:
    st.warning("結果ファイルが見つかりません。まずはデータ収集を実行してください。")
    st.stop()

# データタイプでフィルタリングするオプション
data_types = sorted(list(set([f["type"] for f in result_files])))
selected_type = st.sidebar.selectbox("データタイプ", ["すべて"] + data_types)

# フィルタリング
if selected_type != "すべて":
    filtered_files = [f for f in result_files if f["type"] == selected_type]
else:
    filtered_files = result_files

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

        category_data = data[selected_category]

        # 複数回実行の場合
        if selected_file["is_multi_run"] and "all_rankings" in category_data:
            rankings_data = category_data["all_rankings"]

            # 平均ランキングがあれば表示
            if "avg_ranking" in category_data:
                st.markdown("### 平均ランキング")
                avg_ranking = category_data["avg_ranking"]

                # 平均ランキングの表示
                for i, service in enumerate(avg_ranking[:10], 1):
                    st.write(f"{i}. {service}")

            # サービスごとの出現頻度と平均順位を計算
            service_stats = {}

            for ranking in rankings_data:
                for i, service in enumerate(ranking, 1):
                    if service not in service_stats:
                        service_stats[service] = {"appearances": 0, "positions": []}

                    service_stats[service]["appearances"] += 1
                    service_stats[service]["positions"].append(i)

            # 統計情報をDataFrameに変換
            stats_records = []
            for service, stats in service_stats.items():
                avg_position = sum(stats["positions"]) / len(stats["positions"]) if stats["positions"] else 0
                appearance_rate = stats["appearances"] / len(rankings_data)

                stats_records.append({
                    "サービス": service,
                    "出現回数": stats["appearances"],
                    "出現率": appearance_rate,
                    "平均順位": avg_position
                })

            stats_df = pd.DataFrame(stats_records)
            stats_df = stats_df.sort_values("平均順位")

            # 出現率と平均順位のグラフ
            st.markdown("### サービスの出現頻度と平均順位")
            fig, ax = plt.subplots()

            # 上位10サービスに絞る
            top_services = stats_df.head(10)

            # 棒グラフ（出現率）
            bars = ax.bar(top_services["サービス"], top_services["出現率"], alpha=0.7)

            # 出現率のスケール
            ax.set_ylabel("出現率", fontproperties=prop)
            ax.tick_params(axis='y', colors='blue')

            # 平均順位のスケール（反転：小さいほど上位）
            ax2 = ax.twinx()
            ax2.plot(top_services["サービス"], top_services["平均順位"], 'ro-', alpha=0.7)
            ax2.set_ylabel("平均順位", fontproperties=prop)
            ax2.tick_params(axis='y', colors='red')
            ax2.invert_yaxis()  # 順位は小さいほど上位なので反転

            ax.set_xticklabels(top_services["サービス"], rotation=45, ha='right', fontproperties=prop)
            ax.set_title(f"{selected_category} のサービス出現率と平均順位", fontproperties=prop)

            st.pyplot(fig)

            # データテーブル
            st.dataframe(stats_df)

        # 単一実行の場合
        elif "ranking" in category_data:
            st.markdown("### ランキング結果")
            ranking = category_data["ranking"]

            # ランキングの表示
            for i, service in enumerate(ranking[:10], 1):
                st.write(f"{i}. {service}")

            # 棒グラフで可視化
            fig, ax = plt.subplots()

            # 上位10サービスに絞る
            top_services = ranking[:10]
            y_pos = range(len(top_services))

            # 順位を反転して表示（1位が一番上に来るように）
            ax.barh(y_pos, [10 - i for i in range(len(top_services))], align='center')
            ax.set_yticks(y_pos)
            ax.set_yticklabels(top_services, fontproperties=prop)
            ax.invert_yaxis()  # 1位を上に表示
            ax.set_xlabel('順位（逆順）', fontproperties=prop)
            ax.set_title(f"{selected_category} のランキング", fontproperties=prop)

            st.pyplot(fig)

        else:
            st.warning("このカテゴリにはランキングデータがありません")

    elif "引用リンク" in selected_file["type"]:
        # 引用リンクの可視化
        st.subheader("引用リンク分析")

        category_data = data[selected_category]

        # サブカテゴリがある場合
        if isinstance(category_data, dict) and len(category_data) > 0:
            # サブカテゴリの選択
            subcategories = list(category_data.keys())
            selected_subcategory = st.selectbox("サブカテゴリを選択", subcategories)

            subcategory_data = category_data[selected_subcategory]

            # 複数回実行の場合
            if "all_runs" in subcategory_data:
                runs_data = subcategory_data["all_runs"]

                # ドメインランキングがある場合
                if "domain_rankings" in subcategory_data:
                    st.markdown("### ドメインランキング")
                    domain_rankings = subcategory_data["domain_rankings"]

                    # ドメインランキングをDataFrameに変換
                    rankings_df = pd.DataFrame(domain_rankings)

                    # 上位10ドメインの選択
                    top_domains = rankings_df.head(10)

                    # ドメイン出現率のグラフ
                    st.markdown("### ドメイン出現率")
                    fig, ax = plt.subplots()
                    bars = ax.bar(top_domains["domain"], top_domains["appearance_ratio"])

                    # バーにラベルを追加
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

                    # 平均ランクのグラフ
                    st.markdown("### ドメイン平均ランク")
                    fig, ax = plt.subplots()
                    bars = ax.bar(top_domains["domain"], top_domains["avg_rank"])

                    # バーにラベルを追加
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                                f'{height:.2f}',
                                ha='center', va='bottom')

                    ax.set_xticklabels(top_domains["domain"], rotation=45, ha='right', fontproperties=prop)
                    ax.set_ylabel('平均ランク', fontproperties=prop)
                    ax.set_title(f"{selected_category} - {selected_subcategory} のドメイン平均ランク", fontproperties=prop)
                    plt.tight_layout()

                    st.pyplot(fig)

                    # データテーブル
                    st.dataframe(rankings_df)

                # 個別の実行データを表示
                st.markdown("### 個別実行データ")

                for i, run in enumerate(runs_data):
                    with st.expander(f"実行 {i+1}"):
                        if "citations" in run:
                            citations = run["citations"]

                            # DataFrameに変換
                            citations_df = pd.DataFrame(citations)
                            st.dataframe(citations_df)
                        else:
                            st.write("引用データがありません")

            # 単一実行の場合
            elif "run" in subcategory_data and "citations" in subcategory_data["run"]:
                citations = subcategory_data["run"]["citations"]

                # DataFrameに変換
                citations_df = pd.DataFrame(citations)

                st.markdown("### 引用リンク")
                st.dataframe(citations_df)

                # ドメイン頻度のグラフ
                if len(citations_df) > 0 and "domain" in citations_df.columns:
                    domain_counts = citations_df["domain"].value_counts()

                    st.markdown("### ドメイン頻度")
                    fig, ax = plt.subplots()
                    domain_counts.head(10).plot(kind="bar", ax=ax)
                    ax.set_ylabel("頻度", fontproperties=prop)
                    ax.set_title(f"{selected_category} - {selected_subcategory} のドメイン頻度", fontproperties=prop)

                    st.pyplot(fig)
            else:
                st.warning("このサブカテゴリには引用データがありません")
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