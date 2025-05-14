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

# AWS S3 設定
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# 保存モード設定（環境変数から取得、デフォルトは両方）
# "local_only": ローカルのみ保存
# "s3_only": S3のみ保存
# "both": ローカルとS3の両方に保存
STORAGE_MODE = os.getenv("STORAGE_MODE", "both")

# ベースパス設定
LOCAL_RESULTS_DIR = os.getenv("LOCAL_RESULTS_DIR", "results")
S3_RESULTS_PREFIX = os.getenv("S3_RESULTS_PREFIX", "results")

# S3が有効かどうかを確認
def is_s3_enabled():
    """S3が有効かどうかを確認"""
    has_credentials = all([AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_BUCKET_NAME])
    return has_credentials and STORAGE_MODE in ["s3_only", "both"]

# ローカル保存が有効かどうかを確認
def is_local_enabled():
    """ローカル保存が有効かどうかを確認"""
    return STORAGE_MODE in ["local_only", "both"]

# 保存設定の概要を取得
def get_storage_config():
    """現在の保存設定の概要を返す"""
    return {
        "storage_mode": STORAGE_MODE,
        "s3_enabled": is_s3_enabled(),
        "local_enabled": is_local_enabled(),
        "local_dir": LOCAL_RESULTS_DIR,
        "s3_bucket": S3_BUCKET_NAME if is_s3_enabled() else None,
        "s3_prefix": S3_RESULTS_PREFIX if is_s3_enabled() else None
    }

# パス構造の一貫性を保つためのヘルパー関数
def get_results_paths(api_type, date_str, file_name, subdir=None):
    """
    結果ファイルのパスを生成

    Parameters:
    -----------
    api_type : str
        API種別（'perplexity', 'openai'など）
    date_str : str
        日付文字列（'YYYYMMDD'形式）
    file_name : str
        ファイル名
    subdir : str, optional
        サブディレクトリ名

    Returns:
    --------
    tuple
        (ローカルパス, S3パス)のタプル
    """
    # ローカルパスの構築
    if subdir:
        local_dir = os.path.join(LOCAL_RESULTS_DIR, api_type, date_str, subdir)
    else:
        local_dir = os.path.join(LOCAL_RESULTS_DIR, api_type, date_str)
    local_path = os.path.join(local_dir, file_name)

    # S3パスの構築
    if subdir:
        s3_path = f"{S3_RESULTS_PREFIX}/{api_type}/{date_str}/{subdir}/{file_name}"
    else:
        s3_path = f"{S3_RESULTS_PREFIX}/{api_type}/{date_str}/{file_name}"

    return local_path, s3_path