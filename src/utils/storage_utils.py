#!/usr/bin/env python
# coding: utf-8

"""
ファイル操作・データ保存の共通ユーティリティ

ファイルの読み書き、ローカルファイルシステムとS3への保存操作を
統一的に扱うインターフェースを提供します。
"""

import os
import json
import datetime
import boto3
import re
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
from .storage_config import is_s3_enabled, is_local_enabled, get_storage_config, get_base_paths
from .storage_config import AWS_ACCESS_KEY, AWS_SECRET_KEY, AWS_REGION, S3_BUCKET_NAME
from .storage_config import STORAGE_MODE

class NumpyJSONEncoder(json.JSONEncoder):
    """numpy型をPython標準型に変換するJSONエンコーダー"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

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

def should_save_locally(storage_mode=None):
    """ローカル保存すべきかを判定"""
    mode = storage_mode or STORAGE_MODE
    return mode in ["local", "both", "auto"]

def should_save_to_s3(storage_mode=None):
    """S3保存すべきかを判定"""
    mode = storage_mode or STORAGE_MODE
    return mode in ["s3", "both", "auto"] and is_s3_enabled()

def ensure_dir(dir_path):
    """
    ディレクトリが存在しない場合は作成する

    Parameters:
    -----------
    dir_path : str
        作成するディレクトリパス
    """
    os.makedirs(dir_path, exist_ok=True)


def load_json(file_path, s3_path=None):
    """
    JSONファイルを読み込む（ローカルまたはS3対応）

    Parameters:
    -----------
    file_path : str
        読み込むファイルパス（s3://で始まる場合はS3から取得、
        またはローカルファイルパス）
    s3_path : str, optional
        S3ファイルパス（file_pathがローカルパスの場合の代替S3パス）

    Returns:
    --------
    dict | None
        読み込んだデータ、失敗した場合はNone
    """
    if file_path.startswith('s3://'):
        # S3パスの場合
        m = re.match(r's3://([^/]+)/(.+)', file_path)
        if m:
            bucket, key = m.group(1), m.group(2)
        else:
            # バケット省略時はデフォルトバケット
            bucket, key = S3_BUCKET_NAME, file_path[5:]
        try:
            s3_client = get_s3_client()
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except Exception as e:
            print(f"S3からのJSONファイル読み込みに失敗しました: {e}")
            return None
    else:
        # ローカルファイル
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"ローカルファイル読み込みエラー: {e}")
                return None
        else:
            print(f"ファイルが存在しません: {file_path}")

        # S3から読み込み（ローカルが失敗した場合）
        if s3_path and is_s3_enabled():
            try:
                s3_client = get_s3_client()
                response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_path)
                return json.loads(response['Body'].read().decode('utf-8'))
            except Exception as e:
                print(f"S3ファイル読み込みエラー: {e}")

        return None


def save_json(data, file_path):
    """
    JSONファイルを保存する（ローカル）

    Parameters:
    -----------
    data : dict
        保存するデータ
    file_path : str
        保存先ファイルパス

    Returns:
    --------
    bool
        保存成功時True、失敗時False
    """
    try:
        # ディレクトリを作成
        ensure_dir(os.path.dirname(file_path))

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=NumpyJSONEncoder)
        return True
    except Exception as e:
        print(f"JSONファイルの保存に失敗しました: {e}")
        return False

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

def save_figure(fig, local_path, s3_path=None, dpi=100, bbox_inches="tight", storage_mode=None):
    """
    Matplotlibの図を保存（ローカルとS3の両方に対応、STORAGE_MODE環境変数で制御）

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
    storage_mode : str, optional
        ストレージモード（Noneの場合は環境変数STORAGE_MODEを使用）

    Returns:
    --------
    dict
        保存結果 {"local": bool, "s3": bool}
    """
    result = {"local": False, "s3": False}

    # ストレージモードの取得
    mode = storage_mode or STORAGE_MODE

    # ローカル保存
    if should_save_locally(mode):
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
    if should_save_to_s3(mode) and result["local"]:
        # S3パスが指定されていない場合、ローカルパスからの変換を試みる
        if not s3_path:
            s3_path = local_path.replace("\\", "/")
            # corporate_bias_datasetsディレクトリプレフィックスを削除（S3のパスを短くするため）
            if s3_path.startswith("corporate_bias_datasets/"):
                s3_path = s3_path.replace("corporate_bias_datasets/", "", 1)

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
    elif data_type == "google":
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
                Body=json.dumps(data, ensure_ascii=False, cls=NumpyJSONEncoder).encode('utf-8')
            )
        return True
    except Exception as e:
        print(f"S3保存エラー: {e}")
        return False

def list_s3_files(prefix):
    """
    指定したprefix配下のS3ファイル一覧を取得

    Parameters:
    -----------
    prefix : str
        S3バケット内のプレフィックス（例: 'corporate_bias_datasets/raw_data/rankings/'）

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
            json.dump(data, f, ensure_ascii=False, indent=2, cls=NumpyJSONEncoder)
        if verbose:
            print(f"ローカルに保存しました: {local_path}")
    except Exception as e:
        print(f"ローカル保存エラー: {e}")
        return None

    # S3保存
    if is_s3_enabled():
        if not s3_key:
            # デフォルトでlocal_pathからS3キーを生成
            s3_key = local_path.replace("\\", "/")
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

def load_json_from_s3_integrated(date_or_path: str, filename: str = "bias_analysis_results.json") -> dict:
    """
    S3のintegratedディレクトリから指定ファイル（bias_analysis_results.json等）をロード
    Parameters:
    -----------
    date_or_path : str
        日付（YYYYMMDD）またはintegrated/パス
    filename : str
        読み込むファイル名（デフォルト: bias_analysis_results.json）
    Returns:
    --------
    dict
        読み込んだデータ
    Raises:
    -------
    FileNotFoundError
        ファイルが見つからない場合
    """
    from .storage_config import get_base_paths, S3_BUCKET_NAME
    try:
        if len(date_or_path) == 8 and date_or_path.isdigit():
            paths = get_base_paths(date_or_path)
            s3_path = f"s3://{S3_BUCKET_NAME}/{paths['integrated']}/{filename}"
        else:
            if "integrated/" in date_or_path:
                path_parts = date_or_path.split("/")
                date_part = None
                for part in path_parts:
                    if len(part) == 8 and part.isdigit():
                        date_part = part
                        break
                if date_part:
                    paths = get_base_paths(date_part)
                    s3_path = f"s3://{S3_BUCKET_NAME}/{paths['integrated']}/{filename}"
                else:
                    raise ValueError(f"日付を抽出できませんでした: {date_or_path}")
            else:
                s3_path = f"s3://{S3_BUCKET_NAME}/datasets/{date_or_path}/{filename}"
        data = load_json(s3_path)
        if data is None:
            raise FileNotFoundError(f"S3から{s3_path}を読み込めませんでした")
        return data
    except Exception as e:
        print(f"S3から{s3_path}の読み込み失敗: {e}")
        raise FileNotFoundError(f"S3から{s3_path}を読み込めませんでした: {date_or_path}")