#!/usr/bin/env python
# coding: utf-8

"""
データ保存の共通ユーティリティ

ローカルファイルシステムとS3への保存操作を統一的に扱う
インターフェースを提供します。
"""

import os
import json
import datetime
import boto3
from .storage_config import is_s3_enabled, is_local_enabled, get_storage_config
from .storage_config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, S3_BUCKET_NAME
from .file_utils import ensure_dir

def get_s3_client():
    """S3クライアントを取得"""
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

def get_today_str():
    """今日の日付を文字列（YYYYMMDD形式）で取得"""
    return datetime.datetime.now().strftime("%Y%m%d")

def save_json(data, local_path, s3_path=None):
    """
    JSONデータをローカルとS3に保存

    Parameters:
    -----------
    data : dict
        保存するJSONデータ
    local_path : str
        ローカル保存先のパス
    s3_path : str, optional
        S3保存先のパス

    Returns:
    --------
    dict
        {"local": bool, "s3": bool} の形式で保存結果を返す
    """
    result = {"local": False, "s3": False}

    # ローカルに保存
    try:
        ensure_dir(os.path.dirname(local_path))
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        result["local"] = True
    except Exception as e:
        print(f"ローカル保存エラー: {e}")

    # S3に保存
    if s3_path and is_s3_enabled():
        try:
            s3_client = get_s3_client()
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_path,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8'),
                ContentType="application/json"
            )
            result["s3"] = True
        except Exception as e:
            print(f"S3保存エラー: {e}")

    return result

def save_text_data(text, local_path, s3_path=None):
    """
    テキストデータをローカルとS3に保存

    Parameters:
    -----------
    text : str
        保存するテキストデータ
    local_path : str
        ローカル保存先のパス
    s3_path : str, optional
        S3保存先のパス

    Returns:
    --------
    dict
        {"local": bool, "s3": bool} の形式で保存結果を返す
    """
    result = {"local": False, "s3": False}

    # ローカルに保存
    try:
        ensure_dir(os.path.dirname(local_path))
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(text)
        result["local"] = True
    except Exception as e:
        print(f"ローカル保存エラー: {e}")

    # S3に保存
    if s3_path and is_s3_enabled():
        try:
            s3_client = get_s3_client()
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_path,
                Body=text.encode('utf-8'),
                ContentType="text/plain"
            )
            result["s3"] = True
        except Exception as e:
            print(f"S3保存エラー: {e}")

    return result

def save_binary_data(data, local_path, s3_path=None, content_type=None):
    """
    バイナリデータをローカルとS3に保存

    Parameters:
    -----------
    data : bytes
        保存するバイナリデータ
    local_path : str
        ローカル保存先のパス
    s3_path : str, optional
        S3保存先のパス
    content_type : str, optional
        Content-Typeヘッダー

    Returns:
    --------
    dict
        {"local": bool, "s3": bool} の形式で保存結果を返す
    """
    result = {"local": False, "s3": False}

    # ローカルに保存
    try:
        ensure_dir(os.path.dirname(local_path))
        with open(local_path, 'wb') as f:
            f.write(data)
        result["local"] = True
    except Exception as e:
        print(f"ローカル保存エラー: {e}")

    # S3に保存
    if s3_path and is_s3_enabled():
        try:
            s3_client = get_s3_client()
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_path,
                Body=data,
                ContentType=content_type
            )
            result["s3"] = True
        except Exception as e:
            print(f"S3保存エラー: {e}")

    return result

def save_figure(fig, local_path, s3_path=None, dpi=100, bbox_inches="tight"):
    """
    Matplotlibの図を保存（ローカルとS3の両方に対応）

    Parameters:
    -----------
    fig : matplotlib.figure.Figure
        保存する図
    local_path : str
        ローカルファイルパス
    s3_path : str, optional
        S3上のパス
    dpi : int, optional
        解像度（dpi）
    bbox_inches : str, optional
        余白設定

    Returns:
    --------
    dict
        保存結果 {"local": bool, "s3": bool}
    """
    result = {"local": False, "s3": False}

    # ローカル保存
    if is_local_enabled():
        try:
            # ディレクトリの作成
            local_dir = os.path.dirname(local_path)
            if local_dir:
                ensure_dir(local_dir)

            # 図の保存
            fig.savefig(local_path, dpi=dpi, bbox_inches=bbox_inches)
            print(f"図をローカルに保存しました: {local_path}")
            result["local"] = True
        except Exception as e:
            print(f"図のローカル保存エラー: {e}")

    # S3保存
    if is_s3_enabled() and result["local"]:
        # S3パスが指定されていない場合、ローカルパスからの変換を試みる
        if not s3_path:
            s3_path = local_path.replace("\\", "/")
            # resultsディレクトリプレフィックスを削除（S3のパスを短くするため）
            if s3_path.startswith("results/"):
                s3_path = s3_path[8:]

        try:
            s3_client = get_s3_client()

            # 拡張子からコンテンツタイプを推測
            ext = os.path.splitext(local_path)[1].lower()
            content_type = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".svg": "image/svg+xml",
                ".pdf": "application/pdf"
            }.get(ext, "application/octet-stream")

            # ファイルをアップロード
            s3_client.upload_file(
                local_path,
                S3_BUCKET_NAME,
                s3_path,
                ExtraArgs={"ContentType": content_type}
            )

            print(f"図をS3に保存しました: s3://{S3_BUCKET_NAME}/{s3_path}")
            result["s3"] = True
        except Exception as e:
            print(f"図のS3保存エラー: {e}")

    return result

def get_results_paths(data_type, date_str, file_name):
    """
    指定したデータタイプと日付に対応するローカルパスとS3パスを生成

    Args:
        data_type: データタイプ（perplexity_sentiment, perplexity_rankings, openai など）
        date_str: 日付文字列（YYYYMMDD形式）
        file_name: ファイル名

    Returns:
        tuple: (ローカルパス, S3パス)
    """
    # ストレージ設定を取得
    storage_config = get_storage_config()

    # ローカルパスの生成
    local_dir = os.path.join(storage_config["local_dir"], data_type)
    local_path = os.path.join(local_dir, file_name)
    ensure_dir(local_dir)

    # S3パスの生成
    s3_dir = f"results/perplexity/{data_type}/{date_str}"
    s3_path = f"{s3_dir}/{file_name}"

    return local_path, s3_path