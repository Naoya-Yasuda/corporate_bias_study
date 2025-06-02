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

# 保存モード設定（環境変数から取得、デフォルトは両方）
# "local_only": ローカルのみ保存
# "s3_only": S3のみ保存
# "both": ローカルとS3の両方に保存
STORAGE_MODE = os.getenv("STORAGE_MODE", "both")

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
    """基本パスを取得"""
    return {
        "perplexity_rankings": f"results/perplexity_rankings/{date_str}",
        "perplexity_sentiment": f"results/perplexity_sentiment/{date_str}",
        "perplexity_citations": f"results/perplexity_citations/{date_str}",
        "google_serp": f"results/google_serp/{date_str}",
        "perplexity_analysis": f"results/perplexity_analysis/{date_str}",
        "analysis": {
            "perplexity": f"results/analysis/perplexity/{date_str}",
            "citations": f"results/analysis/citations/{date_str}",
            "integrated_metrics": f"results/integrated_metrics/{date_str}"
        },
        "bias_analysis": {
            "rankings": f"results/bias_analysis/rankings/{date_str}",
            "citations": f"results/bias_analysis/citations/{date_str}"
        }
    }