#!/usr/bin/env python
# coding: utf-8

"""
データ保存の設定を一元管理するモジュール

環境変数や設定ファイルから保存設定を読み込み、
一貫した保存動作を実現します。
"""

import os
from dotenv import load_dotenv
from .storage_utils import get_results_paths

# .envファイルから環境変数を読み込む
load_dotenv()

# AWS S3 設定
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
# リージョンが空の場合はデフォルト値を使用
if not AWS_REGION or AWS_REGION.strip() == '':
    AWS_REGION = 'ap-northeast-1'
    print(f'[storage_config] AWS_REGIONが未設定または空のため、デフォルト値を使用します: {AWS_REGION}')
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

# get_results_paths関数を削除