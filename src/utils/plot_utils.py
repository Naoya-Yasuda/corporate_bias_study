#!/usr/bin/env python
# coding: utf-8

'''
描画関連のユーティリティ関数

matplotlib / seabornを使った可視化関数を提供します
'''

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def set_plot_style():
    """グラフのスタイルを設定"""
    plt.style.use('ggplot')
    sns.set_style("whitegrid")
    plt.rcParams['font.size'] = 12
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10
    plt.rcParams['figure.titlesize'] = 16

def plot_delta_ranks(delta_ranks, output_path=None):
    """
    ΔRankをバーチャートで可視化

    Parameters:
    -----------
    delta_ranks : dict
        ドメイン→Δランクのマップ
    output_path : str, optional
        出力ファイルパス（Noneの場合はファイル保存せず、図を返す）

    Returns:
    --------
    matplotlib.figure.Figure
        プロットした図
    """
    if not delta_ranks:
        return None

    # データフレームに変換
    df = pd.DataFrame({
        "domain": list(delta_ranks.keys()),
        "delta_rank": list(delta_ranks.values())
    })

    # 欠損値を除外
    df = df.dropna()

    if df.empty:
        return None

    # ΔRankでソート
    df = df.sort_values("delta_rank")

    # プロット
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(df["domain"], df["delta_rank"])

    # ゼロラインを強調
    ax.axvline(x=0, color='k', linestyle='-', alpha=0.3)

    # バーの色を設定（負の値は緑、正の値は赤）
    for i, bar in enumerate(bars):
        if df["delta_rank"].iloc[i] < 0:
            bar.set_color('green')
        else:
            bar.set_color('red')

    ax.set_title("Google vs Perplexity ΔRank比較")
    ax.set_xlabel("Δ Rank (Perplexity - Google)")
    ax.grid(axis='x', alpha=0.3)

    # 余白を調整
    plt.tight_layout()

    # ファイルに保存（指定された場合）
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return output_path

    return fig

def plot_market_impact(original_share, adjusted_share, output_path=None):
    """
    市場シェアへの影響をバーチャートで可視化

    Parameters:
    -----------
    original_share : dict
        元の市場シェア
    adjusted_share : dict
        調整後の市場シェア
    output_path : str, optional
        出力ファイルパス（Noneの場合はファイル保存せず、図を返す）

    Returns:
    --------
    matplotlib.figure.Figure
        プロットした図
    """
    if not original_share or not adjusted_share:
        return None

    # プロット設定
    fig = plt.figure(figsize=(12, 8))

    # データフレームを作成
    data = []
    for domain in sorted(original_share.keys()):
        orig = original_share.get(domain, 0)
        adj = adjusted_share.get(domain, 0)
        data.append({
            "domain": domain,
            "original": orig * 100,
            "adjusted": adj * 100,
            "change": (adj - orig) * 100
        })

    df = pd.DataFrame(data)
    df = df.sort_values("original", ascending=False)

    # プロット1: 市場シェア比較
    ax1 = plt.subplot(2, 1, 1)
    x = np.arange(len(df))
    width = 0.35

    ax1.bar(x - width/2, df["original"], width, label="現在の市場シェア")
    ax1.bar(x + width/2, df["adjusted"], width, label="バイアス影響後")

    ax1.set_xticks(x)
    ax1.set_xticklabels(df["domain"], rotation=45, ha="right")
    ax1.set_ylabel("市場シェア (%)")
    ax1.set_title("バイアスによる市場シェアへの潜在的影響")
    ax1.legend()
    ax1.grid(axis="y", linestyle="--", alpha=0.7)

    # プロット2: 変化量
    ax2 = plt.subplot(2, 1, 2)
    colors = ["green" if x >= 0 else "red" for x in df["change"]]
    ax2.bar(x, df["change"], color=colors)
    ax2.axhline(y=0, color="k", linestyle="-", alpha=0.3)
    ax2.set_xticks(x)
    ax2.set_xticklabels(df["domain"], rotation=45, ha="right")
    ax2.set_ylabel("変化量 (％ポイント)")
    ax2.set_title("市場シェア変化量")
    ax2.grid(axis="y", linestyle="--", alpha=0.7)

    plt.suptitle("検索バイアスによる市場シェア影響")
    plt.tight_layout()

    # ファイルに保存（指定された場合）
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return output_path

    return fig

def plot_rank_heatmap(rank_dist, category, output_path=None):
    """
    ランキング分布をヒートマップで可視化

    Parameters:
    -----------
    rank_dist : dict
        サービス→順位分布のマップ
    category : str
        カテゴリ名（タイトル用）
    output_path : str, optional
        出力ファイルパス（Noneの場合はファイル保存せず、図を返す）

    Returns:
    --------
    matplotlib.figure.Figure
        プロットした図
    """
    if not rank_dist:
        return None

    # データフレームに変換
    services = list(rank_dist.keys())
    max_rank = len(rank_dist[services[0]])

    # 行（サービス）と列（順位）のラベル
    row_labels = services
    col_labels = [f"{i+1}位" for i in range(max_rank)]

    # 確率値の配列
    data = np.array([rank_dist[service] for service in services])

    # プロット
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(data, cmap="YlGnBu")

    # カラーバー
    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel("出現確率", rotation=-90, va="bottom")

    # 軸のラベル設定
    ax.set_xticks(np.arange(max_rank))
    ax.set_yticks(np.arange(len(services)))
    ax.set_xticklabels(col_labels)
    ax.set_yticklabels(row_labels)

    # 軸ラベルの回転
    plt.setp(ax.get_xticklabels(), rotation=0, ha="center", rotation_mode="anchor")

    # セル内に値を表示
    for i in range(len(services)):
        for j in range(max_rank):
            text = ax.text(j, i, f"{data[i, j]:.2f}",
                          ha="center", va="center", color="black" if data[i, j] < 0.5 else "white")

    ax.set_title(f"{category}のランキング分布")
    ax.set_xlabel("順位")
    ax.set_ylabel("サービス")

    # 余白を調整
    fig.tight_layout()

    # ファイルに保存（指定された場合）
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return output_path

    return fig

def plot_exposure_market(exposure, market_share, category, output_path=None):
    """
    露出度と市場シェアの関係を散布図で可視化

    Parameters:
    -----------
    exposure : dict
        サービス→露出度のマップ
    market_share : dict
        サービス→市場シェアのマップ
    category : str
        カテゴリ名（タイトル用）
    output_path : str, optional
        出力ファイルパス（Noneの場合はファイル保存せず、図を返す）

    Returns:
    --------
    matplotlib.figure.Figure
        プロットした図
    """
    if not exposure or not market_share:
        return None

    # 共通するサービスのみ抽出
    common_services = set(exposure.keys()) & set(market_share.keys())

    if not common_services:
        return None

    # データフレームに変換
    data = []
    for service in common_services:
        exp = exposure.get(service, 0)
        share = market_share.get(service, 0)
        data.append({
            "service": service,
            "exposure": exp,
            "market_share": share,
            "eo_ratio": exp / share if share > 0 else 0
        })

    df = pd.DataFrame(data)

    # プロット
    fig, ax = plt.subplots(figsize=(10, 8))

    # 散布図
    scatter = ax.scatter(
        df["market_share"],
        df["exposure"],
        s=100,
        c=df["eo_ratio"],
        cmap="coolwarm",
        alpha=0.7
    )

    # カラーバー
    cbar = ax.figure.colorbar(scatter, ax=ax)
    cbar.ax.set_ylabel("EO比率", rotation=-90, va="bottom")

    # サービス名をプロット
    for i, row in df.iterrows():
        ax.annotate(
            row["service"],
            (row["market_share"], row["exposure"]),
            xytext=(5, 5),
            textcoords="offset points"
        )

    # 公平線（y = x）
    max_val = max(df["market_share"].max(), df["exposure"].max())
    ax.plot([0, max_val], [0, max_val], 'k--', alpha=0.3)

    # 軸の設定
    ax.set_xlabel("市場シェア")
    ax.set_ylabel("露出度")
    ax.set_title(f"{category}の市場シェアと露出度の関係")

    # グリッド
    ax.grid(True, alpha=0.3)

    # 余白を調整
    fig.tight_layout()

    # ファイルに保存（指定された場合）
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        return output_path

    return fig