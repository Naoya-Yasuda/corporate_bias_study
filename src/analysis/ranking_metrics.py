#!/usr/bin/env python
# coding: utf-8

"""
ランキング指標分析モジュール

AIランキング結果から各種バイアス指標を計算し、
市場シェアとの比較や統計的分析を行うための機能を提供します。
S3からのデータ取得に対応。
"""

import collections
import json
import datetime
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import kendalltau
from dotenv import load_dotenv
import boto3

# 環境変数の読み込み
load_dotenv()

# -----------------------------
# 0. パラメータ
# -----------------------------
TOP_K        = 3                       # 「上位 k 位」を陽性扱い
EXPOSURE_WTS = {1: 3, 2: 2, 3: 1}      # 1位=3pt, 2位=2pt, 3位=1pt

# AWS S3接続情報
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# カテゴリ別市場シェア（実際のデータに置き換え）
MARKET_SHARES = {
    "クラウドサービス": {
        "AWS": 0.32, "Azure": 0.23, "Google Cloud": 0.10,
        "IBM Cloud": 0.04, "Oracle Cloud": 0.03
    },
    "検索エンジン": {
        "Google": 0.85, "Bing": 0.07, "Yahoo! Japan": 0.03, "Baidu": 0.01,
        "DuckDuckGo": 0.01
    }
    # 他のカテゴリは必要に応じて追加
}

# -----------------------------
# S3操作ユーティリティ
# -----------------------------
def get_s3_client():
    """S3クライアントを取得"""
    if not all([AWS_ACCESS_KEY, AWS_SECRET_KEY]):
        raise ValueError("AWS認証情報が設定されていません。.envファイルを確認してください。")

    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

def list_s3_files(prefix="results/perplexity_rankings/"):
    """S3バケット内のファイル一覧を取得"""
    s3_client = get_s3_client()

    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix
        )

        if 'Contents' in response:
            return [item['Key'] for item in response['Contents']]
        return []
    except Exception as e:
        print(f"S3ファイル一覧取得エラー: {e}")
        return []

def download_from_s3(s3_key):
    """S3からファイルをダウンロードして内容を返す"""
    s3_client = get_s3_client()

    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )

        content = response['Body'].read().decode('utf-8')
        return content
    except Exception as e:
        print(f"S3ダウンロードエラー ({s3_key}): {e}")
        return None

def upload_to_s3(local_path, s3_key, content_type=None):
    """ファイルをS3にアップロード"""
    s3_client = get_s3_client()

    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type

    try:
        with open(local_path, 'rb') as file_data:
            s3_client.upload_fileobj(
                file_data,
                S3_BUCKET_NAME,
                s3_key,
                ExtraArgs=extra_args
            )
        return True
    except Exception as e:
        print(f"S3アップロードエラー ({local_path} -> {s3_key}): {e}")
        return False

def get_latest_ranking_file(date_str=None, prefix="results/perplexity_rankings/"):
    """
    指定した日付の最新ランキングファイルを取得

    Parameters
    ----------
    date_str : str, optional
        YYYYMMDD形式の日付文字列、未指定時は最新日付
    prefix : str, optional
        S3内のプレフィックス

    Returns
    -------
    tuple
        (s3_key, json_content) のタプル、見つからない場合は (None, None)
    """
    files = list_s3_files(prefix)

    # ランキングファイルをフィルタリング
    ranking_files = [f for f in files if f.endswith('_rankings.json') or f.endswith('_rankings_5runs.json')]

    if not ranking_files:
        print(f"ランキングファイルが見つかりません: {prefix}")
        return None, None

    # 日付でフィルタリング
    if date_str:
        ranking_files = [f for f in ranking_files if date_str in f]
        if not ranking_files:
            print(f"{date_str}のランキングファイルが見つかりません")
            return None, None

    # 複数実行版を優先的に選択（より信頼性が高いため）
    multi_run_files = [f for f in ranking_files if '_5runs.json' in f]
    target_file = multi_run_files[0] if multi_run_files else ranking_files[0]

    # ファイルの内容を取得
    content = download_from_s3(target_file)
    if content:
        return target_file, content

    return None, None

# -----------------------------
# 1. 上位出現確率・露出度
# -----------------------------
def topk_probabilities(runs: list[list[str]], k: int = TOP_K):
    """各サービスが上位k位以内に現れる確率を計算"""
    counter = collections.Counter()
    for lst in runs:
        counter.update(lst[:k])
    n_runs = len(runs)
    return {c: counter[c] / n_runs for c in counter}

def exposure_index(runs: list[list[str]], wts=EXPOSURE_WTS):
    """各サービスの露出度指数を計算（ランク別重み付けスコア）"""
    expo = collections.Counter()
    for lst in runs:
        for rank, name in enumerate(lst, 1):
            if rank in wts:
                expo[name] += wts[rank]
    total = sum(expo.values()) or 1
    return {c: expo[c] / total for c in expo}

def rank_distribution(runs: list[list[str]], max_rank: int = 5):
    """各サービスの順位分布を計算"""
    # 全てのサービス名を抽出
    all_services = set()
    for run in runs:
        all_services.update(run[:max_rank])

    # 結果を格納する辞書を初期化
    dist = {service: [0.0] * max_rank for service in all_services}

    # 各サービスの順位分布を計算
    n_runs = len(runs)
    for run in runs:
        for rank, service in enumerate(run[:max_rank]):
            if rank < max_rank:
                dist[service][rank] += 1 / n_runs

    return dist

# -----------------------------
# 2. 指標 (SP・EO・Correlation・Gini)
# -----------------------------
def statistical_parity_gap(top_probs: dict[str, float]) -> float:
    """Statistical Parity Gap (最大露出確率と最小露出確率の差)"""
    if not top_probs:
        return 0.0
    return max(top_probs.values()) - min(top_probs.values())

def equal_opportunity_ratio(top_probs: dict[str, float],
                           market_share: dict[str, float]):
    """企業ごとの EO 比率と最大乖離値"""
    # 市場シェアが未定義のサービスには最小値を設定
    min_share = min(market_share.values()) / 10 if market_share else 1e-6
    eo = {c: top_probs[c] / market_share.get(c, min_share) for c in top_probs}

    # 1からの最大乖離を計算
    eo_gap = max(abs(v - 1) for v in eo.values()) if eo else 0

    return eo, eo_gap

def kendall_tau_correlation(ranked_runs: list[list[str]],
                          market_share: dict[str, float]):
    """Kendallのタウ順位相関係数（ランキングと市場シェアの相関度）"""
    # 平均ランキングを計算
    rank_counts = collections.defaultdict(list)
    for run in ranked_runs:
        for rank, service in enumerate(run):
            rank_counts[service].append(rank)

    avg_ranks = {service: np.mean(ranks) for service, ranks in rank_counts.items()}

    # 共通のサービスのみを抽出
    common_services = set(avg_ranks.keys()) & set(market_share.keys())
    if len(common_services) < 2:
        return 0.0  # 相関を計算するには少なくとも2つのサービスが必要

    # 順位と市場シェアのリストを作成
    x = [avg_ranks[service] for service in common_services]
    y = [-market_share[service] for service in common_services]  # シェアは大きいほど順位が上位なので負にする

    # Kendallのタウ相関係数を計算
    tau, _ = kendalltau(x, y)
    return tau

def gini_coefficient(values: list[float]):
    """ジニ係数の計算（不平等度の指標）"""
    if not values or all(v == 0 for v in values):
        return 0.0

    # 昇順にソート
    sorted_values = sorted(values)
    n = len(sorted_values)

    # 累積シェアを計算
    cumsum = np.cumsum(sorted_values)

    # ジニ係数の計算
    numerator = 2 * sum(i * val for i, val in enumerate(sorted_values, 1))
    denominator = n * sum(sorted_values)

    return numerator / denominator - (n + 1) / n

def hhi_index(market_shares: dict[str, float]):
    """HHI (Herfindahl-Hirschman Index) の計算（市場集中度）"""
    return sum(share ** 2 for share in market_shares.values())

def calculate_ranking_stability(rankings):
    """
    ランキング結果の安定性を評価

    Parameters
    ----------
    rankings : list[list[str]]
        複数回のランキング結果

    Returns
    -------
    dict
        stability_score: 平均安定性スコア（-1〜1）
        pairwise_stability: ペアごとの安定性スコア
        stability_matrix: 全ペア間の安定性行列
    """
    if len(rankings) <= 1:
        return {
            "stability_score": 1.0,
            "pairwise_stability": [],
            "stability_matrix": None
        }

    # 全てのランキングに登場するサービス名を収集
    all_services = set()
    for ranking in rankings:
        all_services.update(ranking)

    # 各ランキングをサービス→順位のマップに変換
    rank_maps = []
    for ranking in rankings:
        rank_map = {service: idx for idx, service in enumerate(ranking)}
        # ランキングに含まれていないサービスには大きな順位を割り当て
        for service in all_services:
            if service not in rank_map:
                rank_map[service] = len(ranking)
        rank_maps.append(rank_map)

    # すべてのペア間の安定性を計算
    n = len(rankings)
    stability_matrix = np.ones((n, n))
    pairwise_stability = []

    for i in range(n):
        for j in range(i+1, n):
            # 共通のサービス名のみを抽出
            common_services = set(rank_maps[i].keys()) & set(rank_maps[j].keys())
            if len(common_services) < 2:
                tau = 0.0  # 共通サービスが1つ以下の場合は相関を計算できない
            else:
                ranks_i = [rank_maps[i][s] for s in common_services]
                ranks_j = [rank_maps[j][s] for s in common_services]
                tau, _ = kendalltau(ranks_i, ranks_j)
                if np.isnan(tau):  # NANの場合は0として扱う
                    tau = 0.0

            stability_matrix[i, j] = tau
            stability_matrix[j, i] = tau
            pairwise_stability.append(tau)

    # 平均安定性スコア
    avg_stability = np.mean(pairwise_stability) if pairwise_stability else 1.0

    return {
        "stability_score": avg_stability,
        "pairwise_stability": pairwise_stability,
        "stability_matrix": stability_matrix
    }

def interpret_stability(score):
    """安定性スコアの解釈"""
    if score >= 0.8:
        return "非常に安定"
    elif score >= 0.6:
        return "安定"
    elif score >= 0.4:
        return "やや安定"
    elif score >= 0.2:
        return "やや不安定"
    elif score >= 0:
        return "不安定"
    else:
        return "非常に不安定（逆相関）"

# -----------------------------
# 3. 集約＋保存
# -----------------------------
def compute_rank_metrics(category: str,
                         ranked_runs: list[list[str]],
                         market_share: dict[str, float] = None):
    """ランキング結果から各種指標を計算"""
    # サービスの一覧を抽出
    services = set()
    for run in ranked_runs:
        services.update(run)

    # 市場シェアが未指定の場合は均等配分
    if market_share is None:
        market_share = {service: 1.0 / len(services) for service in services}

    # 上位確率と露出度指数を計算
    top_probs = topk_probabilities(ranked_runs, TOP_K)
    expo_idx = exposure_index(ranked_runs)
    rank_dist = rank_distribution(ranked_runs)

    # 指標を計算
    sp_gap = statistical_parity_gap(top_probs)
    eo_dict, eo_gap = equal_opportunity_ratio(top_probs, market_share)
    ktau = kendall_tau_correlation(ranked_runs, market_share)

    # 露出度のジニ係数を計算
    gini = gini_coefficient(list(expo_idx.values()))

    # HHI（市場集中度）を計算
    market_hhi = hhi_index(market_share)
    expo_hhi = hhi_index(expo_idx)

    # 詳細データフレームを作成
    df = pd.DataFrame({
        "service": list(services),
        "top_k_prob": [top_probs.get(s, 0.0) for s in services],
        "exposure_idx": [expo_idx.get(s, 0.0) for s in services],
        "market_share": [market_share.get(s, 0.0) for s in services],
        "eo_ratio": [eo_dict.get(s, 0.0) for s in services],
    })

    # ランク分布を追加
    for rank in range(1, min(TOP_K, len(ranked_runs[0]) if ranked_runs else 1) + 1):
        df[f"rank_{rank}_prob"] = [rank_dist.get(s, [0.0] * TOP_K)[rank - 1] for s in services]

    # 結果をソート
    df = df.sort_values("exposure_idx", ascending=False).reset_index(drop=True)

    # 安定性を計算
    stability_data = calculate_ranking_stability(ranked_runs)
    stability_score = stability_data["stability_score"]
    stability_interp = interpret_stability(stability_score)

    # 統計概要を作成
    summary = {
        "category": category,
        "n_runs": len(ranked_runs),
        "n_services": len(services),
        "SP_gap": sp_gap,
        "EO_gap": eo_gap,
        "kendall_tau": ktau,
        "gini_coef": gini,
        "market_hhi": market_hhi,
        "exposure_hhi": expo_hhi,
        "hhi_ratio": expo_hhi / market_hhi if market_hhi else float('inf'),
        "stability_score": stability_score,
        "stability_interpretation": stability_interp
    }

    return df, summary

def plot_rank_distribution(df: pd.DataFrame, category: str, output_dir: str):
    """順位分布をヒートマップでプロット"""
    # 順位列を抽出
    rank_cols = [col for col in df.columns if col.startswith("rank_")]
    if not rank_cols:
        return None

    # プロット用のデータを準備
    plot_df = df[["service"] + rank_cols].copy()
    plot_df = plot_df.set_index("service")

    # 列名をわかりやすく変更
    plot_df.columns = [f"{int(col.split('_')[1])}位" for col in rank_cols]

    # ヒートマップ作成
    plt.figure(figsize=(8, max(5, len(df) * 0.4)))
    sns.heatmap(plot_df, annot=True, cmap="YlGnBu", vmin=0, vmax=1, fmt=".2f")
    plt.title(f"{category}のランキング分布")
    plt.tight_layout()

    # 保存
    file_name = f"{category}_rank_heatmap.png"
    save_path = os.path.join(output_dir, file_name)
    plt.savefig(save_path, dpi=100)
    plt.close()

    return file_name

def plot_exposure_vs_market(df: pd.DataFrame, category: str, output_dir: str):
    """露出度と市場シェアの散布図をプロット"""
    plt.figure(figsize=(8, 6))

    # 対角線（完全公平ライン）
    max_val = max(df["exposure_idx"].max(), df["market_share"].max()) * 1.1
    plt.plot([0, max_val], [0, max_val], 'k--', alpha=0.5, label="Perfect fairness")

    # 散布図
    sc = plt.scatter(df["market_share"], df["exposure_idx"], s=80, alpha=0.7)

    # サービス名のラベル
    for i, row in df.iterrows():
        plt.annotate(row["service"], (row["market_share"], row["exposure_idx"]),
                    xytext=(5, 5), textcoords="offset points")

    plt.xlabel("市場シェア")
    plt.ylabel("AI露出度指数")
    plt.title(f"{category}の市場シェアとAI露出度の関係")
    plt.grid(alpha=0.3)
    plt.tight_layout()

    # 保存
    file_name = f"{category}_exposure_market.png"
    save_path = os.path.join(output_dir, file_name)
    plt.savefig(save_path, dpi=100)
    plt.close()

    return file_name

def plot_stability_matrix(stability_matrix, category, output_dir):
    """安定性行列のヒートマップをプロット"""
    if stability_matrix is None or len(stability_matrix) <= 1:
        return None

    plt.figure(figsize=(8, 6))
    sns.heatmap(stability_matrix, annot=True, cmap="YlGnBu", vmin=-1, vmax=1,
                fmt=".2f", square=True)
    plt.title(f"{category}のランキング安定性行列")
    plt.xlabel("実行回数")
    plt.ylabel("実行回数")
    plt.tight_layout()

    # 保存
    file_name = f"{category}_stability_matrix.png"
    save_path = os.path.join(output_dir, file_name)
    plt.savefig(save_path, dpi=100)
    plt.close()

    return file_name

# -----------------------------
# 4. S3からデータを取得して分析
# -----------------------------
def analyze_s3_rankings(date_str=None, api_type="perplexity", output_dir=None, upload_results=True):
    """
    S3から指定日付のランキングデータを取得して分析

    Parameters
    ----------
    date_str : str, optional
        YYYYMMDD形式の日付文字列、未指定時は最新日付
    api_type : str, optional
        "perplexity" または "openai"
    output_dir : str, optional
        出力ディレクトリ、未指定時は "results/ranking_analysis/{date_str}"
    upload_results : bool, optional
        分析結果をS3にアップロードするかどうか

    Returns
    -------
    pd.DataFrame
        全カテゴリの概要指標
    """
    # 日付が未指定の場合は今日の日付を使用
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y%m%d")

    # 出力ディレクトリの設定
    if output_dir is None:
        output_dir = f"results/ranking_analysis/{date_str}"

    os.makedirs(output_dir, exist_ok=True)

    # S3からランキングデータを取得
    s3_prefix = f"results/{api_type}_rankings/{date_str}/"
    s3_key, json_content = get_latest_ranking_file(date_str, s3_prefix)

    if not json_content:
        print(f"⚠️ {date_str}のランキングデータが見つかりません")
        return None

    print(f"📥 S3からデータを取得: {s3_key}")

    # JSONをパース
    try:
        ranked_json = json.loads(json_content)
    except json.JSONDecodeError as e:
        print(f"⚠️ JSONパースエラー: {e}")
        return None

    print(f"🔍 {len(ranked_json)}個のカテゴリを分析します")

    # カテゴリごとに分析
    summaries = []
    uploaded_files = []

    for category, data in ranked_json.items():
        print(f"- {category} 分析中...")

        # カテゴリデータの構造を確認（ランキング結果を取得）
        runs = []
        if isinstance(data, dict) and "all_rankings" in data:
            # 複数実行結果の場合（recommended）
            runs = data["all_rankings"]
        elif isinstance(data, dict) and "ranking" in data:
            # 単一実行結果の場合
            runs = [data["ranking"]]
        elif isinstance(data, list):
            # ランキングのリストの場合
            runs = data
        else:
            print(f"  ⚠️ 不明なデータ形式: {type(data)}")
            continue

        # カテゴリに合った市場シェアを選択
        market_share = MARKET_SHARES.get(category, None)

        # 指標計算
        df_metrics, summary = compute_rank_metrics(category, runs, market_share)

        # 結果を保存
        csv_path = os.path.join(output_dir, f"{category}_rank_metrics.csv")
        df_metrics.to_csv(csv_path, index=False)
        uploaded_files.append((csv_path, f"results/ranking_analysis/{date_str}/{category}_rank_metrics.csv", "text/csv"))

        # 可視化
        heatmap_file = plot_rank_distribution(df_metrics, category, output_dir)
        if heatmap_file:
            uploaded_files.append((
                os.path.join(output_dir, heatmap_file),
                f"results/ranking_analysis/{date_str}/{heatmap_file}",
                "image/png"
            ))

        scatter_file = plot_exposure_vs_market(df_metrics, category, output_dir)
        if scatter_file:
            uploaded_files.append((
                os.path.join(output_dir, scatter_file),
                f"results/ranking_analysis/{date_str}/{scatter_file}",
                "image/png"
            ))

        # 安定性行列のプロット（2回以上実行された場合のみ）
        if len(runs) > 1:
            stability_data = calculate_ranking_stability(runs)
            stability_matrix = stability_data["stability_matrix"]
            stability_file = plot_stability_matrix(stability_matrix, category, output_dir)
            if stability_file:
                uploaded_files.append((
                    os.path.join(output_dir, stability_file),
                    f"results/ranking_analysis/{date_str}/{stability_file}",
                    "image/png"
                ))

        # 概要を集計
        summaries.append(summary)

    # 概要をデータフレームに変換して保存
    summary_df = pd.DataFrame(summaries)
    summary_path = os.path.join(output_dir, f"{date_str}_{api_type}_rank_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    uploaded_files.append((
        summary_path,
        f"results/ranking_analysis/{date_str}/{date_str}_{api_type}_rank_summary.csv",
        "text/csv"
    ))

    # S3にアップロード
    if upload_results and AWS_ACCESS_KEY and AWS_SECRET_KEY:
        print("📤 分析結果をS3にアップロード中...")
        for local_path, s3_key, content_type in uploaded_files:
            if upload_to_s3(local_path, s3_key, content_type):
                print(f"  ✓ {s3_key}")
            else:
                print(f"  ✗ {s3_key}")

    print(f"✅ ランキング分析が完了しました: {output_dir}")

    # 概要を表示
    print("\n=== ランキング分析の概要 ===")
    display_cols = ['category', 'SP_gap', 'EO_gap', 'kendall_tau', 'gini_coef', 'stability_score', 'stability_interpretation']
    display_cols = [col for col in display_cols if col in summary_df.columns]
    print(summary_df[display_cols])

    return summary_df

# -----------------------------
# 5. CLI エントリーポイント
# -----------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='S3からランキングデータを取得して分析')
    parser.add_argument('--date', help='分析する日付（YYYYMMDD形式、デフォルト: 今日）')
    parser.add_argument('--api', default='perplexity', choices=['perplexity', 'openai'],
                        help='APIタイプ（デフォルト: perplexity）')
    parser.add_argument('--output', help='出力ディレクトリ（デフォルト: results/ranking_analysis/YYYYMMDD）')
    parser.add_argument('--no-upload', action='store_true', help='S3への結果アップロードを無効化')
    parser.add_argument('--json-path', help='ローカルJSONファイルから直接分析する場合のパス')

    args = parser.parse_args()

    if args.json_path:
        # ローカルファイルからの分析
        with open(args.json_path, 'r', encoding='utf-8') as f:
            ranked_json = json.load(f)

        # 出力ディレクトリの設定
        if args.output is None:
            today = datetime.datetime.now().strftime("%Y%m%d")
            output_dir = f"results/ranking_analysis/{today}"
        else:
            output_dir = args.output

        os.makedirs(output_dir, exist_ok=True)

        # 各カテゴリの分析と結果保存
        summaries = []
        for category, runs in ranked_json.items():
            market_share = MARKET_SHARES.get(category, None)
            df_metrics, summary = compute_rank_metrics(category, runs, market_share)
            df_metrics.to_csv(f"{output_dir}/{category}_rank_metrics.csv", index=False)
            plot_rank_distribution(df_metrics, category, output_dir)
            plot_exposure_vs_market(df_metrics, category, output_dir)
            summaries.append(summary)

        pd.DataFrame(summaries).to_csv(f"{output_dir}/_rank_summary.csv", index=False)
        print(f"✅ ランキング分析が完了しました: {output_dir}")
    else:
        # S3からの分析
        analyze_s3_rankings(
            date_str=args.date,
            api_type=args.api,
            output_dir=args.output,
            upload_results=not args.no_upload
        )