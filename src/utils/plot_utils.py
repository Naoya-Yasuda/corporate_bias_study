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
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
from matplotlib.gridspec import GridSpec
import japanize_matplotlib
from matplotlib import colors as mcolors
from matplotlib.sankey import Sankey
from .storage_utils import save_figure

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
        save_figure(fig, output_path)
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
        save_figure(fig, output_path)
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
        save_figure(fig, output_path)
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
        save_figure(fig, output_path)
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
        save_figure(fig, output_path)
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
        save_figure(fig, output_path)
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

def plot_pvalue_heatmap(pvalue_dict, output_path=None, title="p値ヒートマップ", reliability_label=None):
    """
    企業ごとのp値をヒートマップで可視化
    Parameters:
    -----------
    pvalue_dict : dict
        企業名→p値
    output_path : str, optional
        出力ファイルパス
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    matplotlib.figure.Figure
    """
    entities = list(pvalue_dict.keys())
    pvals = [pvalue_dict[e] for e in entities]
    data = np.array([pvals])
    fig, ax = plt.subplots(figsize=(max(6, len(entities)), 2))
    # カスタムカラーマップ
    from matplotlib.colors import ListedColormap, BoundaryNorm
    cmap = ListedColormap(["#bdbdbd", "#ffb3b3", "#ff0000"])
    bounds = [0, 0.01, 0.05, 1.01]
    norm = BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(data, cmap=cmap, norm=norm, aspect="auto")
    # 値をセルに表示
    for i, v in enumerate(pvals):
        ax.text(i, 0, f"{v:.3f}", ha="center", va="center", color="black" if v >= 0.05 else "white", fontsize=12)
    ax.set_xticks(np.arange(len(entities)))
    ax.set_xticklabels(entities, rotation=30, ha="right")
    ax.set_yticks([0])
    ax.set_yticklabels(["p値"])
    ax.set_title(title)
    plt.tight_layout()
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    if output_path:
        save_figure(fig, output_path)
        return output_path
    return fig

def plot_correlation_matrix(corr_dict, output_path=None, title="相関マトリクス", reliability_label=None):
    """
    複数実行間の相関マトリクスを可視化（Pearson/Spearman/Kendall）
    Parameters:
    -----------
    corr_dict : dict
        {"pearson": 2次元配列, "spearman": 2次元配列, "kendall": 2次元配列, "labels": ラベルリスト}
    output_path : str, optional
        出力ファイルパス
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    matplotlib.figure.Figure
    """
    labels = corr_dict.get("labels", [])
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for i, method in enumerate(["pearson", "spearman", "kendall"]):
        mat = np.array(corr_dict.get(method, []))
        ax = axes[i]
        sns.heatmap(mat, annot=True, fmt=".2f", cmap="coolwarm", vmin=-1, vmax=1, xticklabels=labels, yticklabels=labels, ax=ax)
        ax.set_title(method.capitalize())
    fig.suptitle(title)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    if reliability_label:
        draw_reliability_badge(axes[0], reliability_label)
    if output_path:
        save_figure(fig, output_path)
        return output_path
    return fig

def plot_market_share_bias_scatter(market_share_dict, bi_dict, output_path=None, title="市場シェア×BI散布図", reliability_label=None):
    """
    市場シェアとBI値の関係を散布図で可視化
    Parameters:
    -----------
    market_share_dict : dict
        企業名→市場シェア（0-1）
    bi_dict : dict
        企業名→BI値
    output_path : str, optional
        出力ファイルパス
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    matplotlib.figure.Figure
    """
    entities = list(set(market_share_dict.keys()) & set(bi_dict.keys()))
    x = [market_share_dict[e] for e in entities]
    y = [bi_dict[e] for e in entities]
    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(x, y, c="blue", s=80)
    for i, e in enumerate(entities):
        ax.annotate(e, (x[i], y[i]), fontsize=10)
    # 回帰直線
    if len(x) > 1:
        coef = np.polyfit(x, y, 1)
        poly1d_fn = np.poly1d(coef)
        ax.plot(x, poly1d_fn(x), color="red", linestyle="--", label="回帰直線")
        # 相関係数
        corr = np.corrcoef(x, y)[0, 1]
        ax.text(0.05, 0.95, f"r={corr:.2f}", transform=ax.transAxes, fontsize=13, va="top", ha="left", bbox=dict(boxstyle="round", fc="white", alpha=0.7))
    ax.set_xlabel("市場シェア")
    ax.set_ylabel("Normalized Bias Index (BI)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    if output_path:
        save_figure(fig, output_path)
        return output_path
    return fig

def plotly_pvalue_heatmap(pvalue_dict, output_path=None, title="p値ヒートマップ（インタラクティブ）"):
    """
    Plotlyでp値ヒートマップをHTML出力
    """
    entities = list(pvalue_dict.keys())
    pvals = [pvalue_dict[e] for e in entities]
    z = [pvals]
    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=entities,
        y=["p値"],
        colorscale=[[0, '#bdbdbd'], [0.01, '#ffb3b3'], [0.05, '#ff0000'], [1, '#ff0000']],
        zmin=0, zmax=1,
        text=[[f"{v:.3f}" for v in pvals]],
        texttemplate="%{text}",
        showscale=True,
        colorbar=dict(title="p値")
    ))
    fig.update_layout(title=title, xaxis_tickangle=30, height=300, margin=dict(t=60, b=40))
    if output_path:
        fig.write_html(output_path)
        return output_path
    return fig

def plotly_correlation_matrix(corr_dict, output_path=None, title="相関マトリクス（インタラクティブ）"):
    """
    Plotlyで相関マトリクス（3種）をHTML出力
    """
    labels = corr_dict.get("labels", [])
    figs = {}
    for method in ["pearson", "spearman", "kendall"]:
        mat = corr_dict.get(method, [])
        fig = go.Figure(data=go.Heatmap(
            z=mat,
            x=labels,
            y=labels,
            colorscale="RdBu",
            zmin=-1, zmax=1,
            colorbar=dict(title="相関係数")
        ))
        fig.update_layout(title=f"{title} - {method.capitalize()}", height=500, margin=dict(t=60, b=40))
        if output_path:
            html_path = output_path.replace(".html", f"_{method}.html")
            fig.write_html(html_path)
            figs[method] = html_path
        else:
            figs[method] = fig
    return figs

def plotly_market_share_bias_scatter(market_share_dict, bi_dict, output_path=None, title="市場シェア×BI散布図（インタラクティブ）"):
    """
    Plotlyで市場シェア×BI散布図をHTML出力
    """
    entities = list(set(market_share_dict.keys()) & set(bi_dict.keys()))
    x = [market_share_dict[e] for e in entities]
    y = [bi_dict[e] for e in entities]
    fig = px.scatter(x=x, y=y, text=entities, labels={"x": "市場シェア", "y": "Normalized Bias Index (BI)"}, title=title)
    fig.update_traces(textposition="top center")
    # 回帰直線
    if len(x) > 1:
        coef = np.polyfit(x, y, 1)
        poly1d_fn = np.poly1d(coef)
        fig.add_traces(go.Scatter(x=x, y=poly1d_fn(x), mode="lines", name="回帰直線", line=dict(color="red", dash="dash")))
        corr = np.corrcoef(x, y)[0, 1]
        fig.add_annotation(x=min(x), y=max(y), text=f"r={corr:.2f}", showarrow=False, font=dict(size=14, color="black"))
    fig.update_layout(height=500, margin=dict(t=60, b=40))
    if output_path:
        fig.write_html(output_path)
        return output_path
    return fig

def plotly_sankey_ranking_change(before_ranks, after_ranks, entities, output_path=None, title="ランキング変動サンキー図"):
    """
    企業のランキング変動をSankey図で可視化（Plotly）
    Parameters:
    -----------
    before_ranks : dict  # 企業名→マスク前順位
    after_ranks : dict   # 企業名→マスク後順位
    entities : list      # 企業名リスト
    output_path : str, optional
    title : str
    """
    # ラベル生成
    before_labels = [f"前:{before_ranks[e]}位" for e in entities]
    after_labels = [f"後:{after_ranks[e]}位" for e in entities]
    labels = before_labels + after_labels
    # Sankeyノード
    node = dict(label=labels, pad=15, thickness=20)
    # Sankeyリンク
    sources = list(range(len(entities)))
    targets = [i+len(entities) for i in range(len(entities))]
    values = [abs(before_ranks[e] - after_ranks[e]) + 1 for e in entities]  # 変動幅で太さ
    link = dict(source=sources, target=targets, value=values, label=entities)
    fig = go.Figure(go.Sankey(node=node, link=link))
    fig.update_layout(title_text=title, font_size=12, height=400)
    if output_path:
        fig.write_html(output_path)
        return output_path
    return fig

def networkx_bias_similarity_graph(similarity_matrix, entities, output_path=None, title="バイアス類似ネットワーク図"):
    """
    企業間バイアス類似性ネットワークをNetworkX+Plotlyで可視化
    Parameters:
    -----------
    similarity_matrix : 2次元リスト（対称行列, 0-1）
    entities : list
    output_path : str, optional
    title : str
    """
    G = nx.Graph()
    for i, e1 in enumerate(entities):
        G.add_node(e1)
        for j, e2 in enumerate(entities):
            if i < j and similarity_matrix[i][j] > 0.3:
                G.add_edge(e1, e2, weight=similarity_matrix[i][j])
    pos = nx.spring_layout(G, seed=42)
    edge_x = []
    edge_y = []
    edge_weights = []
    for e1, e2, d in G.edges(data=True):
        x0, y0 = pos[e1]
        x1, y1 = pos[e2]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
        edge_weights.append(d['weight'])
    node_x = [pos[e][0] for e in entities]
    node_y = [pos[e][1] for e in entities]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, line=dict(width=2, color='gray'), hoverinfo='none', mode='lines'))
    fig.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text', text=entities, textposition='top center', marker=dict(size=20, color='skyblue'), hoverinfo='text'))
    fig.update_layout(title=title, showlegend=False, height=500, margin=dict(t=60, b=40))
    if output_path:
        fig.write_html(output_path)
        return output_path
    return fig

def plot_cross_category_severity_ranking(severity_list, output_path, max_entities=20, reliability_label=None):
    """
    カテゴリ横断の重篤度ランキングを横棒グラフで描画
    Parameters:
    -----------
    severity_list : list of dict
        [{"entity":..., "category":..., "subcategory":..., "severity_score":...}, ...]
    output_path : str
        出力ファイルパス
    max_entities : int
        最大表示件数（降順上位のみ表示）
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    str (output_path)
    """
    if not severity_list:
        return None

    # 降順ソート＆上位のみ
    sorted_list = sorted(severity_list, key=lambda x: x["severity_score"], reverse=True)[:max_entities]
    labels = [f"{d['entity']}\n({d['category']}/{d['subcategory']})" for d in sorted_list]
    scores = [d["severity_score"] for d in sorted_list]

    # 色分け
    def get_color(score):
        if score >= 7.0:
            return "#d62728"  # 赤
        elif score >= 4.0:
            return "#ff7f0e"  # オレンジ
        elif score >= 2.0:
            return "#ffdd57"  # 黄
        else:
            return "#2ca02c"  # 緑
    colors = [get_color(s) for s in scores]

    fig, ax = plt.subplots(figsize=(12, max(6, len(labels)*0.5)))
    bars = ax.barh(labels, scores, color=colors)
    ax.set_xlabel("重篤度スコア (Severity Score)")
    ax.set_title("重篤度ランキング（カテゴリ横断）")
    ax.invert_yaxis()
    # スコア値をバー右に表示
    for i, bar in enumerate(bars):
        ax.text(bar.get_width()+0.1, bar.get_y()+bar.get_height()/2, f"{scores[i]:.2f}", va="center", fontsize=11)
    # 凡例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#d62728", label="非常に重篤 (7.0以上)"),
        Patch(facecolor="#ff7f0e", label="重篤 (4.0以上)"),
        Patch(facecolor="#ffdd57", label="中程度 (2.0以上)"),
        Patch(facecolor="#2ca02c", label="軽微 (2.0未満)")
    ]
    ax.legend(handles=legend_elements, loc="lower right")
    plt.tight_layout()
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    save_figure(fig, output_path)
    return output_path

def plot_analysis_quality_dashboard(quality_data: dict, output_path: str, reliability_label: str = None):
    """
    品質管理ダッシュボード画像を生成
    Parameters:
    -----------
    quality_data : dict
        {"metadata":..., "data_availability_summary":..., "analysis_limitations":..., "category_exec_counts":..., "category_fail_counts":..., "warnings":...}
    output_path : str
        出力ファイルパス
    reliability_label : str, optional
        信頼性バッジラベル
    Returns:
    --------
    str (output_path)
    """
    fig = plt.figure(figsize=(15, 10))
    gs = GridSpec(2, 2, figure=fig)

    # 1. 実行回数ヒストグラム
    ax1 = fig.add_subplot(gs[0, 0])
    exec_counts = quality_data.get("category_exec_counts", [])
    if exec_counts:
        ax1.hist(exec_counts, bins=min(10, len(set(exec_counts))), color="#0070C0", alpha=0.7)
        ax1.set_title("実行回数分布")
        ax1.set_xlabel("実行回数")
        ax1.set_ylabel("カテゴリ数")
    else:
        ax1.text(0.5, 0.5, "データなし", ha="center", va="center")
        ax1.set_title("実行回数分布")

    # 2. データ完全性ゲージ
    ax2 = fig.add_subplot(gs[0, 1])
    completeness = quality_data.get("data_availability_summary", {}).get("completeness", 1.0)
    ax2.barh(["完全性"], [completeness], color="#00B050", alpha=0.7)
    ax2.set_xlim(0, 1)
    ax2.set_title("データ完全性スコア")
    for i, v in enumerate([completeness]):
        ax2.text(v + 0.02, i, f"{v*100:.1f}%", va="center")

    # 3. 計算成功率円グラフ
    ax3 = fig.add_subplot(gs[1, 0])
    total = quality_data.get("total_calculations", 1)
    success = quality_data.get("successful_calculations", total)
    fail = total - success
    ax3.pie([success, fail], labels=["成功", "失敗"], colors=["#00B050", "#d62728"], autopct="%1.0f%%", startangle=90)
    ax3.set_title("計算成功率")

    # 4. 警告・エラー件数バー
    ax4 = fig.add_subplot(gs[1, 1])
    warnings = quality_data.get("warnings", {})
    warn_labels = list(warnings.keys()) if warnings else ["警告なし"]
    warn_counts = list(warnings.values()) if warnings else [0]
    ax4.bar(warn_labels, warn_counts, color="#FFC000", alpha=0.7)
    ax4.set_title("警告・エラー件数")
    ax4.set_ylabel("件数")
    for i, v in enumerate(warn_counts):
        ax4.text(i, v + 0.1, str(v), ha="center")
    plt.setp(ax4.get_xticklabels(), rotation=20, ha="right")

    # 信頼性バッジ
    if reliability_label:
        draw_reliability_badge(ax1, reliability_label)

    # 主要な制限事項・注釈
    limitations = quality_data.get("analysis_limitations", [])
    if limitations:
        fig.text(0.5, 0.02, "主な制限事項: " + "; ".join(limitations), ha="center", va="bottom", fontsize=12, color="red")

    fig.suptitle("分析品質管理ダッシュボード", fontsize=18)
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])
    save_figure(fig, output_path)
    return output_path

def plot_bias_pattern_classification(entity_data, output_path, x_key="bi", y_key="size", label_key="cluster_label", title="バイアスパターン分類図", reliability_label=None):
    """
    企業ごとのバイアス傾向をクラスタリングし、2次元散布図で分類ラベル・色分け表示
    Parameters:
    -----------
    entity_data : list of dict
        [{"entity":..., "bi":..., "size":..., "cluster_label":...}, ...]
    output_path : str
        出力ファイルパス
    x_key, y_key : str
        散布図のX軸・Y軸に使うキー（例: "bi", "size"）
    label_key : str
        クラスタラベルのキー
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.cm import get_cmap
    from src.utils.plot_utils import draw_reliability_badge

    if not entity_data:
        return None
    x = [d.get(x_key, 0) for d in entity_data]
    y = [d.get(y_key, 0) for d in entity_data]
    labels = [d.get(label_key, "未分類") for d in entity_data]
    entities = [d.get("entity", "") for d in entity_data]
    unique_labels = sorted(set(labels))
    cmap = get_cmap("tab10")
    color_map = {lab: cmap(i % 10) for i, lab in enumerate(unique_labels)}
    fig, ax = plt.subplots(figsize=(10, 8))
    for lab in unique_labels:
        idxs = [i for i, l in enumerate(labels) if l == lab]
        ax.scatter([x[i] for i in idxs], [y[i] for i in idxs], label=str(lab), s=120, alpha=0.8, color=color_map[lab])
        for i in idxs:
            ax.text(x[i], y[i], entities[i], fontsize=10, ha="right", va="bottom")
    ax.set_xlabel(x_key)
    ax.set_ylabel(y_key)
    ax.set_title(title)
    ax.legend(title="クラスタ")
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    save_figure(fig, output_path)
    return output_path

def plot_bias_inequality_detailed(bi_values, output_path, title="ローレンツ曲線による不平等度詳細", reliability_label=None):
    """
    企業間バイアス格差をローレンツ曲線で可視化し、Gini係数・標準偏差・範囲を注釈で併記
    Parameters:
    -----------
    bi_values : list or np.ndarray
        各企業のBI値や重篤度スコア
    output_path : str
        出力ファイルパス
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from src.utils.plot_utils import draw_reliability_badge
    bi = np.array(bi_values)
    n = len(bi)
    if n == 0:
        return None
    sorted_bi = np.sort(np.abs(bi))
    cum_bi = np.cumsum(sorted_bi)
    lorenz = np.insert(cum_bi / cum_bi[-1], 0, 0)
    x = np.linspace(0, 1, n+1)
    gini = 1 - 2 * np.trapz(lorenz, x)
    std = np.std(bi)
    bi_range = np.max(bi) - np.min(bi)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(x, lorenz, label="ローレンツ曲線", color="#0070C0", linewidth=2)
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", label="完全平等線")
    ax.set_xlabel("累積企業割合")
    ax.set_ylabel("累積バイアス割合")
    ax.set_title(title)
    ax.legend()
    # 指標注釈
    textstr = f"Gini係数: {gini:.3f}\n標準偏差: {std:.3f}\n範囲: {bi_range:.3f}"
    ax.text(0.05, 0.85, textstr, transform=ax.transAxes, fontsize=13, bbox=dict(boxstyle="round", fc="white", alpha=0.7))
    if reliability_label:
        draw_reliability_badge(ax, reliability_label)
    plt.tight_layout()
    save_figure(fig, output_path)
    return output_path

def plot_market_power_vs_bias(entity_data, output_path, x_key="market_share", y_key="bi", size_key="revenue", label_key="entity", color_key="category", title="市場支配力vs優遇度散布図", reliability_label=None):
    """
    市場支配力vs優遇度散布図を生成
    Parameters:
    -----------
    entity_data : list of dict
        [{"entity":..., "market_share":..., "bi":..., "revenue":..., "category":...}, ...]
    output_path : str
        出力ファイルパス
    x_key, y_key, size_key, label_key, color_key : str
        各軸・バブルサイズ・ラベル・色分けに使うキー
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.cm import get_cmap
    from src.utils.plot_utils import draw_reliability_badge

    if not entity_data:
        return None

    x = np.array([d.get(x_key, 0) for d in entity_data])
    y = np.array([d.get(y_key, 0) for d in entity_data])
    sizes = np.array([d.get(size_key, 1) for d in entity_data])
    labels = [d.get(label_key, "") for d in entity_data]
    colors = [d.get(color_key, "カテゴリ") for d in entity_data]
    unique_colors = list(sorted(set(colors)))
    color_map = {c: get_cmap("tab10")(i % 10) for i, c in enumerate(unique_colors)}
    color_vals = [color_map[c] for c in colors]

    plt.figure(figsize=(8, 6))
    sc = plt.scatter(x, y, s=sizes*10, c=color_vals, alpha=0.7, edgecolors="w", linewidths=0.8)
    for i, label in enumerate(labels):
        plt.text(x[i], y[i], label, fontsize=8, ha="center", va="bottom")
    plt.xlabel("市場シェア")
    plt.ylabel("バイアス指標")
    plt.title(title)
    # 凡例
    handles = [plt.Line2D([0], [0], marker='o', color='w', label=c, markerfacecolor=color_map[c], markersize=8) for c in unique_colors]
    plt.legend(handles=handles, title="カテゴリ", bbox_to_anchor=(1.01, 1), loc="upper left")
    if reliability_label:
        draw_reliability_badge(plt.gca(), reliability_label, loc="upper right")
    plt.tight_layout()
    save_figure(plt.gcf(), output_path)
    return output_path

def plot_category_stability_analysis(stability_data, output_path, time_key="year", value_key="bi", category_key="category", title="カテゴリ安定性分析", reliability_label=None):
    """
    カテゴリ安定性分析（時系列推移線グラフ＋分散棒グラフ）を生成
    Parameters:
    -----------
    stability_data : list of dict
        [{"category":..., "year":..., "bi":...}, ...]
    output_path : str
        出力ファイルパス
    time_key, value_key, category_key : str
        時系列・値・カテゴリのキー
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from collections import defaultdict
    from src.utils.plot_utils import draw_reliability_badge

    if not stability_data:
        return None

    # (A) 時系列推移線グラフ
    cat2data = defaultdict(list)
    for d in stability_data:
        cat2data[d[category_key]].append((d[time_key], d[value_key]))
    plt.figure(figsize=(10, 5))
    for cat, vals in cat2data.items():
        vals = sorted(vals)
        x = [v[0] for v in vals]
        y = [v[1] for v in vals]
        plt.plot(x, y, marker="o", label=cat)
    plt.xlabel("年度")
    plt.ylabel("bi値")
    plt.title(title + "（時系列推移）")
    plt.legend()
    if reliability_label:
        draw_reliability_badge(plt.gca(), reliability_label, loc="upper right")
    plt.tight_layout()
    save_figure(plt.gcf(), output_path.replace(".png", "_timeseries.png"))

    # (B) 分散・標準偏差棒グラフ
    cat2values = {cat: [v[1] for v in sorted(vals)] for cat, vals in cat2data.items()}
    cats = list(cat2values.keys())
    variances = [np.var(cat2values[cat]) for cat in cats]
    stds = [np.std(cat2values[cat]) for cat in cats]
    x = np.arange(len(cats))
    width = 0.35
    plt.figure(figsize=(10, 5))
    plt.bar(x - width/2, variances, width, label="分散")
    plt.bar(x + width/2, stds, width, label="標準偏差")
    plt.xticks(x, cats, rotation=30)
    plt.ylabel("値")
    plt.title(title + "（分散・標準偏差）")
    plt.legend()
    if reliability_label:
        draw_reliability_badge(plt.gca(), reliability_label, loc="upper right")
    plt.tight_layout()
    save_figure(plt.gcf(), output_path.replace(".png", "_variance.png"))

    return output_path

def plot_multiple_comparison_pvalue_heatmap(pvalue_matrix, output_path, categories=None, threshold=0.05, title="多重比較補正p値ヒートマップ", reliability_label=None):
    """
    多重比較補正p値ヒートマップを生成
    Parameters:
    -----------
    pvalue_matrix : 2D array-like
        p値行列（カテゴリ×カテゴリまたは企業×企業）
    output_path : str
        出力ファイルパス
    categories : list of str, optional
        行・列ラベル
    threshold : float
        有意水準（閾値強調）
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from src.utils.plot_utils import draw_reliability_badge

    pvalue_matrix = np.array(pvalue_matrix)
    n = pvalue_matrix.shape[0]
    if categories is None:
        categories = [f"C{i+1}" for i in range(n)]

    plt.figure(figsize=(max(6, n*0.6), max(5, n*0.5)))
    im = plt.imshow(pvalue_matrix, cmap="coolwarm_r", vmin=0, vmax=1)
    plt.colorbar(im, label="p値")
    plt.xticks(np.arange(n), categories, rotation=45, ha="right")
    plt.yticks(np.arange(n), categories)
    # 閾値以下を強調
    for i in range(n):
        for j in range(n):
            val = pvalue_matrix[i, j]
            color = "white" if val < threshold else "black"
            weight = "bold" if val < threshold else "normal"
            plt.text(j, i, f"{val:.2g}", ha="center", va="center", color=color, fontsize=9, fontweight=weight)
    plt.title(title + f"（閾値={threshold}）")
    if reliability_label:
        draw_reliability_badge(plt.gca(), reliability_label, loc="upper right")
    plt.tight_layout()
    save_figure(plt.gcf(), output_path)
    return output_path

def plot_ranking_stability_vs_effect_size(data, output_path, x_key="stability", y_key="effect_size", label_key="entity", color_key="category", title="順位安定性vs効果量", reliability_label=None):
    """
    順位安定性vs効果量の散布図を生成
    Parameters:
    -----------
    data : list of dict
        [{"entity":..., "stability":..., "effect_size":..., "category":...}, ...]
    output_path : str
        出力ファイルパス
    x_key, y_key, label_key, color_key : str
        各軸・ラベル・色分けに使うキー
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.cm import get_cmap
    from src.utils.plot_utils import draw_reliability_badge

    if not data:
        return None

    x = np.array([d.get(x_key, 0) for d in data])
    y = np.array([d.get(y_key, 0) for d in data])
    labels = [d.get(label_key, "") for d in data]
    colors = [d.get(color_key, "カテゴリ") for d in data]
    unique_colors = list(sorted(set(colors)))
    color_map = {c: get_cmap("tab10")(i % 10) for i, c in enumerate(unique_colors)}
    color_vals = [color_map[c] for c in colors]

    plt.figure(figsize=(8, 6))
    sc = plt.scatter(x, y, c=color_vals, alpha=0.7, edgecolors="w", linewidths=0.8)
    for i, label in enumerate(labels):
        plt.text(x[i], y[i], label, fontsize=8, ha="center", va="bottom")
    plt.xlabel("順位安定性")
    plt.ylabel("効果量")
    plt.title(title)
    # 凡例
    handles = [plt.Line2D([0], [0], marker='o', color='w', label=c, markerfacecolor=color_map[c], markersize=8) for c in unique_colors]
    plt.legend(handles=handles, title="カテゴリ", bbox_to_anchor=(1.01, 1), loc="upper left")
    if reliability_label:
        draw_reliability_badge(plt.gca(), reliability_label, loc="upper right")
    plt.tight_layout()
    save_figure(plt.gcf(), output_path)
    return output_path

def plot_mask_effect_ranking_sankey(sankey_data, output_path, source_key="before", target_key="after", value_key="count", label_key="entity", color_key="category", title="マスク効果ランキング変動Sankey図", reliability_label=None):
    """
    マスク効果ランキング変動をSankey図で可視化
    Parameters:
    -----------
    sankey_data : list of dict
        [{"entity":..., "before":..., "after":..., "count":..., "category":...}, ...]
    output_path : str
        出力ファイルパス
    source_key, target_key, value_key, label_key, color_key : str
        前後順位・遷移数・ラベル・色分けに使うキー
    title : str
        グラフタイトル
    reliability_label : str, optional
        信頼性バッジ
    Returns:
    --------
    str (output_path)
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib import colors as mcolors
    from matplotlib.sankey import Sankey
    from src.utils.plot_utils import draw_reliability_badge

    # Sankey用データ整形
    sources = [f"{d[source_key]}位:{d[label_key]}" for d in sankey_data]
    targets = [f"{d[target_key]}位:{d[label_key]}" for d in sankey_data]
    values = [d[value_key] for d in sankey_data]
    cats = [d.get(color_key, "カテゴリ") for d in sankey_data]
    unique_nodes = list(sorted(set(sources + targets)))
    node_indices = {n: i for i, n in enumerate(unique_nodes)}
    color_map = {c: mcolors.TABLEAU_COLORS[list(mcolors.TABLEAU_COLORS.keys())[i % 10]] for i, c in enumerate(sorted(set(cats)))}
    node_colors = [color_map[c] for c in cats] + [color_map[c] for c in cats]

    # Sankeyパッチ
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(1, 1, 1, xticks=[], yticks=[])
    sankey = Sankey(ax=ax, unit=None)
    for i, d in enumerate(sankey_data):
        sankey.add(flows=[-d[value_key], d[value_key]],
                   labels=[sources[i], targets[i]],
                   orientations=[-1, 1],
                   facecolor=color_map[cats[i]],
                   alpha=0.7)
    sankey.finish()
    plt.title(title)
    if reliability_label:
        draw_reliability_badge(ax, reliability_label, loc="upper right")
    plt.tight_layout()
    save_figure(fig, output_path)
    return output_path