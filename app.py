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

# ページ設定
st.set_page_config(
    page_title="企業バイアス分析ダッシュボード",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# タイトル
st.title("企業バイアス分析ダッシュボード")
st.markdown("AI検索サービスにおける企業優遇バイアスの可視化")

# サイドバー
st.sidebar.header("データ選択")

# 結果ファイルの検索
def get_result_files():
    """resultsディレクトリから利用可能な結果ファイルを取得"""
    # 結果ファイルパターン
    patterns = [
        # 新しいパス構造と命名規則
        "results/perplexity/sentiment/*_perplexity_sentiment_*.json",
        "results/perplexity/rankings/*_perplexity_rankings_*.json",
        "results/perplexity/citations/*_perplexity_citations_*.json",
        "results/openai/sentiment/*_openai_sentiment_*.json",

        # 旧パス構造
        "results/perplexity_sentiment/*_perplexity_sentiment_*.json",
        "results/perplexity_rankings/*_perplexity_rankings_*.json",
        "results/perplexity_citations/*_perplexity_citations_*.json",
        "results/openai_sentiment/*_openai_sentiment_*.json",

        # 古い命名規則（後方互換性のため）
        "results/perplexity/sentiment/*_perplexity_results_*.json",
        "results/perplexity/rankings/*_perplexity_results_*.json",
        "results/perplexity/citations/*_perplexity_results_*.json",
        "results/openai/sentiment/*_openai_results_*.json",

        # ルートのresultsフォルダも検索
        "results/*_perplexity_sentiment_*.json",
        "results/*_perplexity_rankings_*.json",
        "results/*_perplexity_citations_*.json",
        "results/*_openai_sentiment_*.json",
        "results/*_perplexity_results_*.json",
        "results/*_openai_results_*.json"
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    # 重複を削除
    files = list(set(files))

    # ファイル情報を整理
    file_info = []
    for file_path in files:
        # ファイル名から情報を抽出
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

        file_info.append({
            "path": file_path,
            "name": file_name,
            "date": date_str,
            "date_obj": date_obj if date_match else datetime.now(),
            "type": data_type,
            "is_multi_run": is_multi_run,
            "display_name": display_name,
            "date_raw": date_match
        })

    # 日付の新しい順にソート
    file_info.sort(key=lambda x: x["date_obj"], reverse=True)
    return file_info

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
        with open(selected_file["path"], "r", encoding="utf-8") as f:
            data = json.load(f)
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

        # 複数回実行の場合
        if selected_file["is_multi_run"] and "scores" in category_data:
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
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.boxplot(x="service", y="score", hue="mask_type", data=df, ax=ax)
            ax.set_xlabel("サービス")
            ax.set_ylabel("感情スコア")
            ax.set_title(f"{selected_category} の感情スコア分布")
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
                fig, ax = plt.subplots(figsize=(10, 6))
                sns.barplot(x="サービス", y="バイアス指標", data=bias_df, ax=ax)
                ax.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
                ax.set_title(f"{selected_category} のバイアス指標")
                st.pyplot(fig)

                # バイアス指標のテーブル
                st.dataframe(bias_df)

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
                fig, ax = plt.subplots(figsize=(10, 6))

                x = np.arange(len(df))
                width = 0.35

                ax.bar(x - width/2, df["マスクなしスコア"], width, label="マスクなし")
                ax.bar(x + width/2, df["マスクありスコア"], width, label="マスクあり")

                ax.set_xticks(x)
                ax.set_xticklabels(df["サービス"])
                ax.set_ylabel("感情スコア")
                ax.set_title(f"{selected_category} の感情スコア比較")
                ax.legend()

                st.pyplot(fig)

                # データテーブル
                st.dataframe(df)
            else:
                st.warning("このカテゴリにはスコアデータがありません")

    # 他のデータタイプの表示（ランキング、引用リンクなど）は省略...
    # ... 既存のコード ...

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

    # 選択したカテゴリのデータを時系列で集計
    if "感情スコア" in selected_type or selected_type == "すべて":
        # 感情スコアの時系列データ
        st.subheader(f"感情スコアの日次変化: {selected_category}")

        # 感情スコアファイルのみをフィルタリング
        sentiment_files = [f for f in filtered_files if "感情スコア" in f["type"]]

        if not sentiment_files:
            st.warning("感情スコアデータが見つかりません。")
        else:
            # 時系列データを収集
            time_series_data = []

            for file_info in sentiment_files:
                try:
                    with open(file_info["path"], "r", encoding="utf-8") as f:
                        data = json.load(f)

                        if selected_category in data:
                            category_data = data[selected_category]
                            date = file_info["date_obj"]

                            # サブカテゴリがある場合
                            for subcategory, subcategory_data in category_data.items():
                                # スコアデータの取得方法はファイル構造に応じて調整
                                if "competitors" in subcategory_data:  # 新しい形式
                                    # 新しい形式のデータ構造
                                    if "masked_avg" in subcategory_data and "unmasked_avg" in subcategory_data:
                                        masked_score = subcategory_data["masked_avg"]

                                        for service, score in subcategory_data["unmasked_avg"].items():
                                            time_series_data.append({
                                                "日付": date,
                                                "カテゴリ": selected_category,
                                                "サブカテゴリ": subcategory,
                                                "サービス": service,
                                                "マスクなしスコア": score,
                                                "マスクありスコア": masked_score,
                                                "バイアス": score - masked_score
                                            })
                                elif "scores" in subcategory_data:  # 複数回実行の形式
                                    masked_scores = subcategory_data["scores"].get("masked", [])
                                    masked_avg = np.mean(masked_scores) if masked_scores else 0

                                    for service, service_data in subcategory_data["scores"].items():
                                        if service != "masked" and "unmasked" in service_data:
                                            unmasked_scores = service_data["unmasked"]
                                            unmasked_avg = np.mean(unmasked_scores) if unmasked_scores else 0

                                            time_series_data.append({
                                                "日付": date,
                                                "カテゴリ": selected_category,
                                                "サブカテゴリ": subcategory,
                                                "サービス": service,
                                                "マスクなしスコア": unmasked_avg,
                                                "マスクありスコア": masked_avg,
                                                "バイアス": unmasked_avg - masked_avg
                                            })

                except Exception as e:
                    st.warning(f"ファイル {file_info['name']} の読み込みエラー: {e}")

            if time_series_data:
                # DataFrameに変換
                df = pd.DataFrame(time_series_data)

                # 日付でソート
                df = df.sort_values("日付")

                # ユニークなサブカテゴリ一覧
                subcategories = df["サブカテゴリ"].unique()
                selected_subcategory = st.selectbox("サブカテゴリを選択", subcategories)

                # 選択したサブカテゴリのデータ
                subcategory_df = df[df["サブカテゴリ"] == selected_subcategory]

                # 日付を文字列に変換
                subcategory_df["日付文字列"] = subcategory_df["日付"].dt.strftime("%Y-%m-%d")

                # サービス別の時系列データ
                services = subcategory_df["サービス"].unique()

                # 折れ線グラフ（マスクなしスコア）
                fig, ax = plt.subplots(figsize=(12, 6))

                for service in services:
                    service_data = subcategory_df[subcategory_df["サービス"] == service]
                    ax.plot(service_data["日付文字列"], service_data["マスクなしスコア"], marker='o', label=service)

                ax.set_xlabel("日付")
                ax.set_ylabel("マスクなしスコア")
                ax.set_title(f"{selected_category} - {selected_subcategory} の時系列変化")
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=45)
                plt.tight_layout()

                st.pyplot(fig)

                # 折れ線グラフ（バイアススコア）
                fig, ax = plt.subplots(figsize=(12, 6))

                for service in services:
                    service_data = subcategory_df[subcategory_df["サービス"] == service]
                    ax.plot(service_data["日付文字列"], service_data["バイアス"], marker='o', label=service)

                ax.set_xlabel("日付")
                ax.set_ylabel("バイアススコア (マスクなし - マスクあり)")
                ax.set_title(f"{selected_category} - {selected_subcategory} のバイアス時系列変化")
                ax.legend()
                ax.grid(True, alpha=0.3)
                ax.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
                plt.xticks(rotation=45)
                plt.tight_layout()

                st.pyplot(fig)

                # データテーブル
                st.subheader("時系列データテーブル")
                st.dataframe(subcategory_df.sort_values(["日付", "サービス"]))
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

                fig, ax = plt.subplots(figsize=(12, 6))

                ax.plot(df["日付文字列"], df["マスクなしスコア"], marker='o', label="マスクなし", color='blue')
                ax.plot(df["日付文字列"], df["マスクありスコア"], marker='s', label="マスクあり", color='green')
                ax.plot(df["日付文字列"], df["バイアス"], marker='^', label="バイアス", color='red')

                ax.set_xlabel("日付")
                ax.set_ylabel("スコア")
                ax.set_title(f"{selected_category} - {selected_subcategory} の {selected_service} 時系列変化")
                ax.legend()
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
st.markdown("企業バイアス分析ダッシュボード © 2024")