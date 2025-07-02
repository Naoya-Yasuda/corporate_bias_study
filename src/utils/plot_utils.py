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

def plot_confidence_intervals(bi_dict, ci_dict, output_path=None, highlight_zero_cross=True, title="BI信頼区間プロット", reliability_label=None):
    """
    各企業のBI値と95%信頼区間をエラーバー付きで可視化
    Parameters:
    -----------
    bi_dict : dict
        企業名→BI値
    ci_dict : dict
        企業名→(ci_lower, ci_upper)
    output_path : str, optional
        出力ファイルパス
    highlight_zero_cross : bool
        信頼区間が0を跨ぐ場合に色やマーカーで強調
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    matplotlib.figure.Figure
    """
    entities = list(bi_dict.keys())
    bi_values = [bi_dict[e] for e in entities]
    ci_lowers = [ci_dict[e][0] for e in entities]
    ci_uppers = [ci_dict[e][1] for e in entities]
    errors = [(
        bi - ci_lower, ci_upper - bi
    ) for bi, ci_lower, ci_upper in zip(bi_values, ci_lowers, ci_uppers)]
    error_array = np.array(errors).T

    fig, ax = plt.subplots(figsize=(10, 6))
    for i, e in enumerate(entities):
        # 信頼区間が0を跨ぐ場合はグレー、それ以外は赤/緑
        if highlight_zero_cross and ci_lowers[i] < 0 < ci_uppers[i]:
            color = "gray"
        else:
            color = "red" if bi_values[i] > 0 else "green"
        ax.errorbar(e, bi_values[i],
                    yerr=[[bi_values[i] - ci_lowers[i]], [ci_uppers[i] - bi_values[i]]],
                    fmt='o', color='black', ecolor=color, elinewidth=2, capsize=6, markerfacecolor='white', markersize=8)
        ax.scatter(e, bi_values[i], color=color, s=80, zorder=3)
    ax.axhline(0, color='k', linestyle='--', alpha=0.5)
    ax.set_ylabel("Normalized Bias Index (BI)")
    ax.set_title(title)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_path
    return fig

def plot_severity_radar(severity_dict, output_path=None, title="重篤度レーダーチャート", threshold=7.0, reliability_label=None):
    """
    各企業の重篤度スコア構成要素をレーダーチャートで可視化
    Parameters:
    -----------
    severity_dict : dict
        企業名→{"abs_bi":..., "cliffs_delta":..., "p_value":..., "stability_score":..., "severity_score":...}
    output_path : str, optional
        出力ファイルパス
    title : str
        グラフタイトル
    threshold : float
        重篤度スコアの警告閾値
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    matplotlib.figure.Figure
    """
    labels = ["|BI|", "Cliff's Δ", "1-p値", "安定性"]
    num_vars = len(labels)
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]
    for entity, comp in severity_dict.items():
        values = [
            abs(comp.get("abs_bi", 0)),
            abs(comp.get("cliffs_delta", 0)),
            1 - comp.get("p_value", 1),
            comp.get("stability_score", 0)
        ]
        values += values[:1]
        score = comp.get("severity_score", 0)
        color = "red" if score >= threshold else "blue"
        ax.plot(angles, values, label=f"{entity} ({score:.2f})", color=color, linewidth=2)
        ax.fill(angles, values, color=color, alpha=0.15)
    ax.set_thetagrids(np.degrees(angles[:-1]), labels)
    ax.set_title(title, y=1.1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return output_path
    return fig

def draw_reliability_badge(ax, label, color_map=None, loc="upper right"):
    """
    信頼性レベルバッジを画像右上に描画
    Parameters:
    -----------
    ax : matplotlib.axes.Axes
        描画対象のAxes
    label : str
        信頼性ラベル
    color_map : dict, optional
        ラベル→色のマップ
    loc : str
        配置位置（upper right, upper left, lower right, lower left）
    """
    if color_map is None:
        color_map = {
            "高精度": "#0070C0",
            "標準": "#00B050",
            "実用": "#FFC000",
            "基本": "#FF6600",
            "参考": "#C00000"
        }
    color = color_map.get(label, "#888888")
    bbox_props = dict(boxstyle="round,pad=0.4", fc=color, ec="none", alpha=0.8)
    pos = {
        "upper right": (0.98, 0.98),
        "upper left": (0.02, 0.98),
        "lower right": (0.98, 0.02),
        "lower left": (0.02, 0.02)
    }[loc]
    ax.text(pos[0], pos[1], label, transform=ax.transAxes, fontsize=13, color="white", ha="right" if "right" in loc else "left", va="top" if "upper" in loc else "bottom", bbox=bbox_props, zorder=10)