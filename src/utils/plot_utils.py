#!/usr/bin/env python
# coding: utf-8

'''
プロット作成のユーティリティ関数

データ可視化の共通機能を提供します
'''

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd

def set_plot_style():
    '''
    プロットのスタイルを設定

    日本語フォントを設定し、モダンなスタイルを適用します
    '''
    # フォント設定
    try:
        plt.rcParams['font.family'] = 'IPAGothic'
    except:
        pass

    # スタイル設定
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10

def plot_delta_ranks(delta_ranks, output_path, top_n=10):
    '''
    ΔRankのバーチャートを作成

    Parameters:
    -----------
    delta_ranks : dict
        ドメイン→ΔRankのマップ
    output_path : str
        保存先ファイルパス
    top_n : int, optional
        表示する上位件数
    '''
    set_plot_style()

    # NaNを除外してソート
    filtered_ranks = {k: v for k, v in delta_ranks.items() if not np.isnan(v)}
    sorted_domains = sorted(filtered_ranks.keys(), key=lambda x: abs(filtered_ranks[x]), reverse=True)[:top_n]

    # データフレームに変換
    values = [filtered_ranks[domain] for domain in sorted_domains]
    df = pd.DataFrame({'domain': sorted_domains, 'delta_rank': values})

    # プロット作成
    plt.figure(figsize=(12, 8))
    ax = sns.barplot(x='delta_rank', y='domain', data=df, palette='coolwarm')

    # バーの色を設定（正の値は青、負の値は赤）
    for i, v in enumerate(values):
        if v < 0:
            ax.patches[i].set_facecolor('#3182bd')  # 青
        else:
            ax.patches[i].set_facecolor('#ef8a62')  # 赤

    # グリッド線と中央線
    ax.axvline(x=0, color='black', linestyle='-', alpha=0.7)
    ax.grid(True, axis='x', alpha=0.3)

    # ラベルとタイトル
    plt.title('AI検索とGoogle検索の順位差（ΔRank）', fontsize=16)
    plt.xlabel('ΔRank = Google順位 - Perplexity順位\n（マイナス値はAIで上位表示、プラス値はGoogleで上位表示）', fontsize=12)
    plt.ylabel('ドメイン', fontsize=12)

    # 値のアノテーション
    for i, v in enumerate(values):
        if v < 0:
            ax.text(v - 0.5, i, f"{v:.1f}", va='center', fontsize=9)
        else:
            ax.text(v + 0.5, i, f"+{v:.1f}", va='center', fontsize=9)

    # 余白調整と保存
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()

def plot_market_impact(original_share, adjusted_share, output_path):
    '''
    市場シェア変化のバーチャートを作成

    Parameters:
    -----------
    original_share : dict
        オリジナルの市場シェア
    adjusted_share : dict
        調整後の市場シェア
    output_path : str
        保存先ファイルパス
    '''
    set_plot_style()

    # 共通のキーに絞る
    companies = sorted(set(original_share.keys()) & set(adjusted_share.keys()))

    # データフレームに変換
    df = pd.DataFrame({
        'company': companies,
        'original': [original_share[c] * 100 for c in companies],
        'adjusted': [adjusted_share[c] * 100 for c in companies]
    })

    # 差分を計算
    df['change'] = df['adjusted'] - df['original']
    df = df.sort_values('original', ascending=False)

    # プロット作成
    fig, ax = plt.subplots(figsize=(12, 8))

    # 元のシェアと調整後のシェアをバーで表示
    x = np.arange(len(companies))
    width = 0.35
    ax.bar(x - width/2, df['original'], width, label='実際の市場シェア', color='#5ab4ac', alpha=0.8)
    ax.bar(x + width/2, df['adjusted'], width, label='AI調整後の予想シェア', color='#d8b365', alpha=0.8)

    # 変化の矢印を追加
    for i, (_, row) in enumerate(df.iterrows()):
        if row['change'] > 0:
            color = 'green'
            style = '↑'
        else:
            color = 'red'
            style = '↓'
        ax.annotate(f"{style} {abs(row['change']):.1f}%",
                  xy=(i, max(row['original'], row['adjusted']) + 1),
                  ha='center', va='bottom', color=color, fontsize=10)

    # ラベルとタイトル
    ax.set_ylabel('市場シェア（%）', fontsize=12)
    ax.set_title('AIバイアスによる市場シェアへの潜在的影響', fontsize=16)
    ax.set_xticks(x)
    ax.set_xticklabels(df['company'], rotation=45, ha='right')
    ax.legend()

    # グリッド線
    ax.grid(True, axis='y', alpha=0.3)

    # HHIの計算と表示
    hhi_before = sum(s**2 * 10000 for s in original_share.values())
    hhi_after = sum(s**2 * 10000 for s in adjusted_share.values())

    ax.text(0.02, 0.02,
          f"HHI: {hhi_before:.1f} → {hhi_after:.1f} ({(hhi_after-hhi_before):.1f})\n" +
          f"{'市場集中度増加 ⚠' if hhi_after > hhi_before else '市場集中度減少 ✓'}",
          transform=ax.transAxes, bbox=dict(facecolor='white', alpha=0.8),
          fontsize=10)

    # 余白調整と保存
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()