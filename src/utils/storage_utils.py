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
from .storage_config import is_s3_enabled, is_local_enabled, get_storage_config, get_base_paths
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

def get_results_paths(date_str):
    """結果ファイルのパスを取得"""
    return get_base_paths(date_str)

def ensure_dir(directory):
    """ディレクトリが存在しない場合は作成"""
    if not os.path.exists(directory):
        os.makedirs(directory)



def load_json(local_path, s3_path=None):
    """
    JSONデータをローカルまたはS3から読み込み

    Parameters:
    -----------
    local_path : str
        ローカルファイルパス
    s3_path : str, optional
        S3ファイルパス

    Returns:
    --------
    dict | None
        読み込んだデータ、失敗した場合はNone
    """
    # ローカルから読み込み
    if os.path.exists(local_path):
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"ローカルファイル読み込みエラー: {e}")

    # S3から読み込み
    if s3_path and is_s3_enabled():
        try:
            s3_client = get_s3_client()
            response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_path)
            return json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            print(f"S3ファイル読み込みエラー: {e}")

    return None

def get_latest_file(date_str, data_type, file_type):
    """最新のファイルを取得"""
    if not is_s3_enabled():
        return None, None
    try:
        s3_client = get_s3_client()
        s3_key = get_s3_key_path(date_str, data_type, file_type)
        if not s3_key:
            return None, None
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        return s3_key, content
    except Exception as e:
        print(f"S3取得エラー: {e}")
        return None, None

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

def get_s3_key_path(date_str, data_type, file_type):
    """S3のキーパスを取得"""
    paths = get_results_paths(date_str)
    base_path = None

    if data_type == "perplexity_rankings":
        base_path = paths["perplexity_rankings"]
    elif data_type == "perplexity_sentiment":
        base_path = paths["perplexity_sentiment"]
    elif data_type == "perplexity_citations":
        base_path = paths["perplexity_citations"]
    elif data_type == "google_search" or data_type == "google":
        base_path = paths["google"]
    elif data_type == "perplexity_analysis":
        base_path = paths["perplexity_analysis"]
    elif data_type == "analysis":
        if file_type == "perplexity":
            base_path = paths["analysis"]["perplexity"]
        elif file_type == "citations":
            base_path = paths["analysis"]["citations"]
        elif file_type == "integrated_metrics":
            base_path = paths["analysis"]["integrated_metrics"]
    elif data_type == "bias_analysis":
        if file_type == "rankings":
            base_path = paths["bias_analysis"]["rankings"]
        elif file_type == "citations":
            base_path = paths["bias_analysis"]["citations"]

    if base_path:
        # ファイル名を生成（日付を先頭に、data_typeを使用）
        filename = f"{date_str}_{data_type}.json"
        return os.path.join(base_path, filename)
    return None

def get_local_path(date_str, data_type, file_type):
    """ローカルのパスを取得"""
    return get_s3_key_path(date_str, data_type, file_type)

def save_to_s3(data, s3_key):
    """データをS3に保存"""
    if not is_s3_enabled():
        return False
    try:
        s3_client = get_s3_client()
        if isinstance(data, str):
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=data.encode('utf-8')
            )
        else:
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_key,
                Body=json.dumps(data, ensure_ascii=False).encode('utf-8')
            )
        return True
    except Exception as e:
        print(f"S3保存エラー: {e}")
        return False

def put_json_to_s3(data, s3_key):
    """JSONデータをS3に保存"""
    return save_to_s3(data, s3_key)

def list_s3_files(prefix):
    """
    指定したprefix配下のS3ファイル一覧を取得

    Parameters:
    -----------
    prefix : str
        S3バケット内のプレフィックス（例: 'results/rankings/'）

    Returns:
    --------
    list[str]
        ファイルキーのリスト
    """
    if not is_s3_enabled():
        return []
    s3_client = get_s3_client()
    paginator = s3_client.get_paginator('list_objects_v2')
    files = []
    try:
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix=prefix):
            for obj in page.get('Contents', []):
                files.append(obj['Key'])
    except Exception as e:
        print(f"S3ファイル一覧取得エラー: {e}")
    return files

def save_results(data, local_path, s3_key=None, verbose=False):
    """
    結果データをローカルとS3に保存する共通関数
    - local_path: ローカル保存先パス
    - s3_key: S3保存先キー（省略時はローカルパスから自動変換も可）
    - verbose: Trueなら詳細ログ
    """
    try:
        ensure_dir(os.path.dirname(local_path))
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"ローカルに保存しました: {local_path}")
    except Exception as e:
        print(f"ローカル保存エラー: {e}")
        return None

    # S3保存
    if AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME:
        if not s3_key:
            # デフォルトでlocal_pathからS3キーを生成
            s3_key = local_path.replace("\\", "/")
            if s3_key.startswith("results/"):
                s3_key = s3_key[8:]
        try:
            s3_client = get_s3_client()
            with open(local_path, 'rb') as f:
                s3_client.upload_fileobj(f, S3_BUCKET_NAME, s3_key)
            if verbose:
                print(f"S3に保存しました: s3://{S3_BUCKET_NAME}/{s3_key}")
        except Exception as e:
            print(f"S3保存エラー: {e}")
    else:
        if verbose:
            print("S3認証情報が不足しています。AWS_ACCESS_KEY, AWS_SECRET_KEY, S3_BUCKET_NAMEを環境変数で設定してください。")
    return local_path