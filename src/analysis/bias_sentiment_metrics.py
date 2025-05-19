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
from scipy import stats
from tqdm import trange, tqdm
from src.analysis.ranking_metrics import analyze_s3_rankings
from dotenv import load_dotenv
import boto3
from src.utils.file_utils import ensure_dir, save_json, get_today_str
from src.utils.s3_utils import save_to_s3, put_json_to_s3

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

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
    return 1.0 if n == 0 else stats.binom_test(pos, n, 0.5, alternative="two-sided")

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

def calculate_sentiment_stability(sentiment_values):
    """
    感情スコアの安定性を評価

    Parameters
    ----------
    sentiment_values : dict or list
        感情スコアの値。辞書（企業→スコアリスト）またはリスト

    Returns
    -------
    dict
        stability_score: 平均安定性スコア（変動係数の逆数）
        cv_values: 企業ごとの変動係数
    """
    if isinstance(sentiment_values, dict):
        # 辞書形式（企業→スコアリスト）の場合
        companies = list(sentiment_values.keys())
        cv_values = {}
        correlations = []

        # 各企業の変動係数を計算
        for company, scores in sentiment_values.items():
            if len(scores) > 1:
                cv = np.std(scores, ddof=1) / np.mean(scores) if np.mean(scores) != 0 else 0
                cv_values[company] = cv
            else:
                cv_values[company] = 0

        # 企業間の相関を計算（複数実行間での順位の安定性）
        n_runs = max(len(scores) for scores in sentiment_values.values())
        if n_runs > 1:
            for i in range(n_runs - 1):
                for j in range(i + 1, n_runs):
                    values_i = []
                    values_j = []
                    for company in companies:
                        scores = sentiment_values[company]
                        if i < len(scores) and j < len(scores):
                            values_i.append(scores[i])
                            values_j.append(scores[j])

                    if len(values_i) >= 2:  # 最低2社以上必要
                        try:
                            corr, _ = stats.pearsonr(values_i, values_j)
                            if not np.isnan(corr):
                                correlations.append(corr)
                        except:
                            pass  # 相関計算エラーは無視

        # 安定性スコアの計算
        avg_cv = np.mean(list(cv_values.values())) if cv_values else 0
        stability_score_cv = 1 / (1 + avg_cv)  # 変動係数から安定性スコア（0～1）へ変換

        stability_score_corr = np.mean(correlations) if correlations else 1.0

        # 総合安定性スコア（相関と変動係数のバランス）
        stability_score = 0.5 * stability_score_cv + 0.5 * stability_score_corr

        return {
            "stability_score": stability_score,
            "cv_values": cv_values,
            "correlations": correlations,
            "stability_score_cv": stability_score_cv,
            "stability_score_corr": stability_score_corr
        }

    elif isinstance(sentiment_values, list):
        # リスト形式（単一企業・複数実行）の場合
        if len(sentiment_values) <= 1:
            return {"stability_score": 1.0, "cv": 0.0}

        mean_value = np.mean(sentiment_values)
        if mean_value == 0:
            cv = 0  # 平均が0の場合は変動係数を0とする
        else:
            cv = np.std(sentiment_values, ddof=1) / mean_value

        stability_score = 1 / (1 + cv)  # 変動係数から安定性スコア（0～1）へ変換

        return {"stability_score": stability_score, "cv": cv}

    else:
        # 不正な入力の場合
        return {"stability_score": 0.0, "cv": -1}

def interpret_sentiment_stability(score):
    """感情スコア安定性の解釈"""
    if score >= 0.9:
        return "非常に安定"
    elif score >= 0.8:
        return "安定"
    elif score >= 0.7:
        return "やや安定"
    elif score >= 0.5:
        return "やや不安定"
    elif score >= 0.3:
        return "不安定"
    else:
        return "非常に不安定"

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
        abs_mean = grp_cat.apply(lambda r: abs(r['unmasked'] - r['masked']).mean(),
                                axis=1).mean() or 1.0

        # カテゴリレベルの安定性を計算するためのデータ収集
        unmasked_values = {}

        for cmp, g in grp_cat.groupby(company_level):
            masked = g['masked'].to_numpy()
            unmasked = g['unmasked'].to_numpy()
            delta = unmasked - masked
            mean_delta = delta.mean()

            # 安定性評価用に企業ごとのunmaskedスコアを収集
            unmasked_values[cmp] = unmasked.tolist()

            # 指標計算
            BI = mean_delta / abs_mean                # ±1 付近にスケール
            p_sign = sign_test(masked, unmasked)
            cliff = cliffs_delta(masked, unmasked)
            ci_low, ci_high = bootstrap_ci(delta)

            # バイアスの解釈
            interpretation = interpret_bias(mean_delta, BI, cliff, p_sign)

            # 個別の安定性
            if len(unmasked) > 1:
                company_stability = calculate_sentiment_stability(unmasked.tolist())
                company_stability_score = company_stability["stability_score"]
                stability_interp = interpret_sentiment_stability(company_stability_score)
            else:
                company_stability_score = 1.0
                stability_interp = "単一データ"

            out.append({
                company_level: cmp,
                'mean_delta': mean_delta,
                'BI': BI,
                'cliffs_d': cliff,
                'ci_low': ci_low,
                'ci_high': ci_high,
                'sign_p': p_sign,
                'stability_score': company_stability_score,
                'stability': stability_interp,
                'interpretation': interpretation
            })

        # カテゴリ全体の感情スコア安定性
        category_stability = calculate_sentiment_stability(unmasked_values)

        df_result = (pd.DataFrame(out)
                    .sort_values('BI', ascending=False)
                    .reset_index(drop=True))

        # カテゴリレベルのメタデータを追加
        df_result.attrs['category_stability_score'] = category_stability["stability_score"]
        df_result.attrs['category_stability'] = interpret_sentiment_stability(category_stability["stability_score"])

        results[cat] = df_result

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
    category_summary = []
    for cat, df in metrics.items():
        safe_cat = cat.replace('/', '_').replace(' ', '_')
        df.to_csv(f"{output_dir}/{today}_{safe_cat}_bias_metrics.csv", index=False)

        # カテゴリごとの安定性情報を収集
        category_summary.append({
            "category": cat,
            "stability_score": df.attrs.get('category_stability_score', 0),
            "stability": df.attrs.get('category_stability', '未評価')
        })

    # 全カテゴリをまとめたCSV
    all_metrics = pd.concat([
        df.assign(category=cat) for cat, df in metrics.items()
    ]).reset_index(drop=True)

    all_metrics.to_csv(f"{output_dir}/{today}_all_bias_metrics.csv", index=False)

    # カテゴリ安定性情報も保存
    pd.DataFrame(category_summary).to_csv(f"{output_dir}/{today}_category_stability.csv", index=False)

    print(f"分析結果を {output_dir} に保存しました")
    return all_metrics, pd.DataFrame(category_summary)

# -------------------------------------------------------------------
# メイン実行関数
# -------------------------------------------------------------------
def analyze_bias_from_file(input_file, output_dir="results/analysis", verbose=False):
    """JSONファイルからバイアス分析を実行"""
    print(f"ファイル {input_file} の分析を開始します...")

    if verbose:
        import logging
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.info(f"詳細ログモードでバイアス分析を実行中: {input_file}")

    # JSONファイルを読み込み
    with open(input_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    # DataFrameに変換
    df = json_to_dataframe(json_data)
    print(f"データ変換完了: {len(df)} 行のデータ")
    if verbose:
        logging.info(f"カテゴリ数: {df['category'].nunique()}, サブカテゴリ数: {df['subcategory'].nunique()}, 企業数: {df['company'].nunique()}")

    # バイアス指標を計算
    metrics = compute_bias_metrics(df, top_level="subcategory")
    if verbose:
        logging.info(f"バイアス指標計算完了: {len(metrics)} カテゴリのデータ")

    # 結果を保存
    all_metrics, category_summary = export_results(metrics, output_dir)
    if verbose:
        logging.info(f"結果の保存完了: {output_dir}")

    # サマリーを表示
    print("\n=== バイアス分析サマリー ===")
    for cat, mdf in metrics.items():
        print(f"\n■ {cat} (安定性スコア: {mdf.attrs.get('category_stability_score', 0):.2f} - {mdf.attrs.get('category_stability', '未評価')})")
        print(mdf[['company', 'mean_delta', 'BI', 'cliffs_d', 'sign_p', 'stability_score', 'interpretation']].head())

    return all_metrics, category_summary

def main():
    """コマンドライン実行用エントリポイント"""
    parser = argparse.ArgumentParser(description='感情スコアからバイアス指標を計算')
    parser.add_argument('input_file', help='分析対象のJSONファイルパス')
    parser.add_argument('--output', default='results/analysis', help='出力ディレクトリ（デフォルト: results/analysis）')
    parser.add_argument('--rankings', action='store_true', help='ランキング分析も実行する')
    parser.add_argument('--rankings-date', help='ランキング分析の日付（YYYYMMDD形式、デフォルト: 同日）')
    parser.add_argument('--api-type', default='perplexity', choices=['perplexity', 'openai'],
                        help='APIタイプ（デフォルト: perplexity）')
    parser.add_argument('--verbose', action='store_true', help='詳細なログ出力を有効化')
    args = parser.parse_args()

    # 詳細ログの設定
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logging.info("詳細ログモードが有効になりました")

    # バイアス分析を実行
    bias_metrics, category_summary = analyze_bias_from_file(args.input_file, args.output, verbose=args.verbose)

    # ランキング分析も実行するオプションが指定されている場合
    if args.rankings:
        print("\n=== ランキング分析を実行します ===")
        # 入力ファイル名から日付を抽出（例: 20250425_perplexity_results.json）
        date_from_file = None
        try:
            import re
            date_match = re.search(r'(\d{8})_', os.path.basename(args.input_file))
            if date_match:
                date_from_file = date_match.group(1)
        except:
            pass

        # 日付の指定順位: コマンドライン引数 > ファイル名から抽出 > 今日の日付
        date_str = args.rankings_date or date_from_file or datetime.datetime.now().strftime("%Y%m%d")

        # S3からランキングデータを取得して分析
        ranking_summary = analyze_s3_rankings(
            date_str=date_str,
            api_type=args.api_type,
            output_dir=f"{args.output}/rankings/{date_str}",
            upload_results=True,
            verbose=args.verbose
        )

        if ranking_summary is not None:
            print("\n✅ バイアス分析とランキング分析が完了しました")
        else:
            print("\n⚠️ ランキング分析は失敗しましたが、バイアス分析は完了しています")

if __name__ == "__main__":
    main()

# S3からランキングデータを取得して分析する例
# 例1: 最新の Perplexity ランキングを分析
# summary = analyze_s3_rankings()

# 例2: 特定日付の OpenAI ランキングを分析
# summary = analyze_s3_rankings(
#     date_str="20230501",
#     api_type="openai"
# )