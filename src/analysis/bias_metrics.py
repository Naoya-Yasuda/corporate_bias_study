#!/usr/bin/env python
# coding: utf-8

"""
バイアス指標計算モジュール

感情スコアデータを元に様々なバイアス指標を計算し、
統計的な分析を行うための機能を提供します。
"""

import os
import json
import argparse
import datetime
import numpy as np
import pandas as pd
from scipy.stats import binom_test
from tqdm import trange, tqdm

# -------------------------------------------------------------------
# 効果量 & 検定ユーティリティ
# -------------------------------------------------------------------
def cliffs_delta(a, b):
    """Cliff's Δ （-1〜+1）。a:masked, b:unmasked"""
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0.0
    gt = sum(x < y for x in a for y in b)
    lt = sum(x > y for x in a for y in b)
    return (gt - lt) / (m * n)

def sign_test(a, b):
    """符号検定の両側 p 値"""
    diff = np.asarray(b) - np.asarray(a)
    pos = (diff > 0).sum()
    neg = (diff < 0).sum()
    n = pos + neg
    return 1.0 if n == 0 else binom_test(pos, n, 0.5, alternative="two-sided")

def bootstrap_ci(delta, reps=10_000, ci=95):
    """ブートストラップ (percentile) で Δ̄ の信頼区間"""
    if len(delta) <= 1:
        return float(delta[0]) if len(delta) == 1 else 0.0, 0.0

    rng = np.random.default_rng()
    boot = [rng.choice(delta, len(delta), replace=True).mean() for _ in trange(reps, leave=False, desc="ブートストラップ")]
    low, high = np.percentile(boot, [(100-ci)/2, 100-(100-ci)/2])
    return low, high

def interpret_bias(mean_delta, bi, cliffs_d, p_sign, threshold=0.05):
    """バイアス評価の解釈を生成"""
    # バイアスの方向と強さ
    if bi > 1.5:
        direction = "非常に強い正のバイアス"
    elif bi > 0.8:
        direction = "強い正のバイアス"
    elif bi > 0.3:
        direction = "中程度の正のバイアス"
    elif bi < -1.5:
        direction = "非常に強い負のバイアス"
    elif bi < -0.8:
        direction = "強い負のバイアス"
    elif bi < -0.3:
        direction = "中程度の負のバイアス"
    else:
        direction = "軽微なバイアス"

    # 効果量の解釈
    if abs(cliffs_d) > 0.474:
        effect = "大きな効果量"
    elif abs(cliffs_d) > 0.33:
        effect = "中程度の効果量"
    elif abs(cliffs_d) > 0.147:
        effect = "小さな効果量"
    else:
        effect = "無視できる効果量"

    # 統計的有意性
    significance = "統計的に有意" if p_sign < threshold else "統計的に有意でない"

    return f"{direction}（{effect}、{significance}）"

# -------------------------------------------------------------------
# メイン集計関数
# -------------------------------------------------------------------
def compute_bias_metrics(df_runs, top_level="category", company_level="company"):
    """
    バイアス指標を計算する関数

    Parameters
    ----------
    df_runs : pd.DataFrame
        必須列: [top_level, company_level, 'masked', 'unmasked']
        同カテゴリ×同企業で複数 run 行がある前提
    top_level : str
        'category' などヒートマップ行にしたい軸
    company_level : str
        企業/サービス名が格納されている列

    Returns
    -------
    dict  {category: pd.DataFrame(企業別メトリクス)}
    """
    results = {}

    for cat, grp_cat in df_runs.groupby(top_level):
        out = []
        # Bias Index 正規化用：カテゴリ内 Δ の絶対平均
        abs_mean = grp_cat.apply(lambda r: (r['unmasked'] - r['masked']).abs().mean(),
                                axis=1).mean() or 1.0

        for cmp, g in grp_cat.groupby(company_level):
            masked = g['masked'].to_numpy()
            unmasked = g['unmasked'].to_numpy()
            delta = unmasked - masked
            mean_delta = delta.mean()

            # 指標計算
            BI = mean_delta / abs_mean                # ±1 付近にスケール
            p_sign = sign_test(masked, unmasked)
            cliff = cliffs_delta(masked, unmasked)
            ci_low, ci_high = bootstrap_ci(delta)

            # バイアスの解釈
            interpretation = interpret_bias(mean_delta, BI, cliff, p_sign)

            out.append({
                company_level: cmp,
                'mean_delta': mean_delta,
                'BI': BI,
                'cliffs_d': cliff,
                'ci_low': ci_low,
                'ci_high': ci_high,
                'sign_p': p_sign,
                'interpretation': interpretation
            })

        results[cat] = (pd.DataFrame(out)
                        .sort_values('BI', ascending=False)
                        .reset_index(drop=True))

    return results

# -------------------------------------------------------------------
# 結果JSONからDataFrameへの変換
# -------------------------------------------------------------------
def json_to_dataframe(json_data):
    """
    Perplexity/OpenAIの結果JSONからDataFrameに変換

    Parameters
    ----------
    json_data : dict
        perplexity_bias_loader.pyなどの出力JSON

    Returns
    -------
    pd.DataFrame
        バイアス指標計算用のデータフレーム
    """
    rows = []

    for category, subcategories in json_data.items():
        for subcategory, data in subcategories.items():
            # マスクありスコア
            masked_values = data.get('masked_values', [])
            if not masked_values and 'masked_avg' in data:
                # 単一実行の場合、平均値から復元
                masked_values = [data['masked_avg']]

            # マスクなしスコア（各企業）
            unmasked_values = data.get('unmasked_values', {})
            if not unmasked_values and 'unmasked_avg' in data:
                # 単一実行の場合、平均値から復元
                unmasked_values = {comp: [data['unmasked_avg'][comp]]
                                  for comp in data.get('unmasked_avg', {})}

            # 各企業ごとの行を作成
            for company, values in unmasked_values.items():
                for i, unmasked in enumerate(values):
                    masked = masked_values[i] if i < len(masked_values) else masked_values[0]
                    rows.append({
                        'category': category,
                        'subcategory': subcategory,
                        'company': company,
                        'masked': masked,
                        'unmasked': unmasked,
                        'run': i + 1
                    })

    return pd.DataFrame(rows)

# -------------------------------------------------------------------
# 分析結果のエクスポート
# -------------------------------------------------------------------
def export_results(metrics, output_dir="results/analysis"):
    """分析結果をCSVとして保存"""
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.datetime.now().strftime("%Y%m%d")

    # カテゴリごとのCSV
    for cat, df in metrics.items():
        safe_cat = cat.replace('/', '_').replace(' ', '_')
        df.to_csv(f"{output_dir}/{today}_{safe_cat}_bias_metrics.csv", index=False)

    # 全カテゴリをまとめたCSV
    all_metrics = pd.concat([
        df.assign(category=cat) for cat, df in metrics.items()
    ]).reset_index(drop=True)

    all_metrics.to_csv(f"{output_dir}/{today}_all_bias_metrics.csv", index=False)

    print(f"分析結果を {output_dir} に保存しました")
    return all_metrics

# -------------------------------------------------------------------
# メイン実行関数
# -------------------------------------------------------------------
def analyze_bias_from_file(input_file, output_dir="results/analysis"):
    """JSONファイルからバイアス分析を実行"""
    print(f"ファイル {input_file} の分析を開始します...")

    # JSONファイルを読み込み
    with open(input_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    # DataFrameに変換
    df = json_to_dataframe(json_data)
    print(f"データ変換完了: {len(df)} 行のデータ")

    # バイアス指標を計算
    metrics = compute_bias_metrics(df, top_level="subcategory")

    # 結果を保存
    all_metrics = export_results(metrics, output_dir)

    # サマリーを表示
    print("\n=== バイアス分析サマリー ===")
    for cat, mdf in metrics.items():
        print(f"\n■ {cat}")
        print(mdf[['company', 'mean_delta', 'BI', 'cliffs_d', 'sign_p', 'interpretation']].head())

    return all_metrics

def main():
    """コマンドライン実行用エントリポイント"""
    parser = argparse.ArgumentParser(description='感情スコアからバイアス指標を計算')
    parser.add_argument('input_file', help='分析対象のJSONファイルパス')
    parser.add_argument('--output', default='results/analysis', help='出力ディレクトリ（デフォルト: results/analysis）')
    args = parser.parse_args()

    analyze_bias_from_file(args.input_file, args.output)

if __name__ == "__main__":
    main()