#!/usr/bin/env python
# coding: utf-8

"""
データ保存の設定を一元管理するモジュール

環境変数や設定ファイルから保存設定を読み込み、
一貫した保存動作を実現します。
"""

import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")

# ストレージモード設定（統一）
# "local": ローカルのみ使用（読み込み・保存）
# "s3": S3のみ使用（読み込み・保存）
# "both": 両方使用（保存は両方、読み込みは優先順位あり）
# "auto": 自動判定（S3利用可能なら優先、フォールバックでローカル）
STORAGE_MODE = os.getenv("STORAGE_MODE", "auto")

# ベースパス設定
LOCAL_RESULTS_DIR = os.getenv("LOCAL_RESULTS_DIR", "results")
S3_RESULTS_PREFIX = os.getenv("S3_RESULTS_PREFIX", "results")

def is_s3_enabled():
    """S3が有効かどうかを判定"""
    return bool(AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME)

def is_local_enabled():
    """ローカルストレージが有効かどうかを判定"""
    return True  # 常に有効

def get_storage_config():
    """ストレージ設定を取得"""
    return {
        "s3_enabled": is_s3_enabled(),
        "local_enabled": is_local_enabled(),
        "aws_region": AWS_REGION,
        "s3_bucket": S3_BUCKET_NAME
    }

def get_base_paths(date_str):
    """
    基本パスを取得 - corporate_bias_datasets/ 階層を含む標準的なディレクトリ構造

    学術研究用データセットとして設計された固定パス構造を使用。
    データの一貫性と互換性を保つため、パス構造は変更不可。
    """
    return {
        # 生データディレクトリ（API別）
        "raw_data": {
            "google": f"corporate_bias_datasets/raw_data/{date_str}/google",
            "perplexity": f"corporate_bias_datasets/raw_data/{date_str}/perplexity"
        },
        # 従来の結果ディレクトリ（後方互換性のため残す）
        "perplexity_rankings": f"corporate_bias_datasets/raw_data/{date_str}/perplexity",
        "perplexity_sentiment": f"corporate_bias_datasets/raw_data/{date_str}/perplexity",
        "perplexity_citations": f"corporate_bias_datasets/raw_data/{date_str}/perplexity",
        "google": f"corporate_bias_datasets/raw_data/{date_str}/google",
        # 分析結果ディレクトリ
        "analysis": {
            "perplexity": f"corporate_bias_datasets/analysis/{date_str}",
            "citations": f"corporate_bias_datasets/analysis/{date_str}",
            "integrated_metrics": f"corporate_bias_datasets/analysis/{date_str}",
            "bias_analysis": f"corporate_bias_datasets/analysis/{date_str}"
        },
        # 統合データセット
        "integrated": f"corporate_bias_datasets/integrated/{date_str}",
        # 可視化画像（corporate_bias_datasets配下に統一）
        "analysis_visuals": f"corporate_bias_datasets/analysis_visuals/{date_str}",
        # 研究成果・出版物
        "publications": "corporate_bias_datasets/publications",
        # 一時ファイル
        "temp": "corporate_bias_datasets/temp",
        # S3用パス設定（読み込み・保存パスの統一）
        "s3": {
            "integrated": f"corporate-bias-datasets/datasets/integrated/{date_str}",
            "raw_data": {
                "google": f"corporate-bias-datasets/datasets/corporate_bias_datasets/raw_data/{date_str}/google",
                "perplexity": f"corporate-bias-datasets/datasets/corporate_bias_datasets/raw_data/{date_str}/perplexity"
            },
            "analysis_visuals": f"corporate-bias-datasets/datasets/corporate_bias_datasets/analysis_visuals/{date_str}",
            "publications": f"corporate-bias-datasets/datasets/corporate_bias_datasets/publications"
        }
    }

def get_s3_key(filename, date_str, data_type):
    """
    ファイル名とデータタイプからS3キーを生成する共通関数
    get_base_paths()で一元管理されたパスを使用

    Parameters:
    -----------
    filename : str
        ファイル名
    date_str : str
        日付文字列（YYYYMMDD形式）
    data_type : str
        データタイプ（raw_data/google, raw_data/perplexity等）

    Returns:
    --------
    str
        S3キー
    """
    paths = get_base_paths(date_str)

    # get_base_pathsで一元管理されたパスを使用
    if data_type == "raw_data/google":
        return f"{paths['raw_data']['google']}/{filename}"
    elif data_type == "raw_data/perplexity":
        return f"{paths['raw_data']['perplexity']}/{filename}"
    elif data_type.startswith("analysis/"):
        # 分析タイプを取得（例: analysis/perplexity -> perplexity）
        analysis_type = data_type.split("/", 1)[1] if "/" in data_type else "perplexity"
        if analysis_type in paths["analysis"]:
            return f"{paths['analysis'][analysis_type]}/{filename}"
        else:
            # デフォルトの分析パスを使用
            return f"{paths['analysis']['perplexity']}/{filename}"
    elif data_type == "integrated":
        # 一元管理されたS3パス設定を使用
        return f"{paths['s3']['integrated']}/{filename}"
    elif data_type == "analysis_visuals":
        return f"{paths['analysis_visuals']}/{filename}"
    elif data_type == "publications":
        return f"{paths['publications']}/{filename}"
    elif data_type == "temp":
        return f"{paths['temp']}/{filename}"
    else:
        # 後方互換性のための従来パス
        if data_type in paths:
            base_path = paths[data_type]
            return f"{base_path}/{filename}"
        else:
            # フォールバック: 標準パターンで生成
            return f"results/{data_type}/{date_str}/{filename}"