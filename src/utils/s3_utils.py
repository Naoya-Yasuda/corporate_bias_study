#!/usr/bin/env python
# coding: utf-8

'''
S3関連のユーティリティ関数

S3へのファイルアップロード機能を提供します
'''

import os
import json
import datetime
import boto3

# S3設定情報
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
# リージョンが空文字列の場合はデフォルト値を使用
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
if not AWS_REGION or AWS_REGION.strip() == '':
    AWS_REGION = 'ap-northeast-1'
    print(f'AWS_REGIONが未設定または空のため、デフォルト値を使用します: {AWS_REGION}')

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# S3設定のデバッグ情報
print(f"S3設定情報: リージョン={AWS_REGION}, バケット={S3_BUCKET_NAME}")
print(f"S3エンドポイント: https://s3.{AWS_REGION}.amazonaws.com")

def get_s3_client():
    '''S3クライアントを取得'''
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

def save_to_s3(local_path, s3_path):
    '''
    ファイルをS3にアップロード

    Parameters:
    -----------
    local_path : str
        ローカルファイルパス
    s3_path : str
        S3上のパス

    Returns:
    --------
    bool
        成功したかどうか
    '''
    if not (AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME):
        print("S3認証情報が設定されていないため、S3への保存をスキップします")
        print("S3に保存するには、.env ファイルに以下の環境変数を設定してください：")
        print("  AWS_ACCESS_KEY - AWSアクセスキー")
        print("  AWS_SECRET_KEY - AWSシークレットキー")
        print("  AWS_REGION - AWSリージョン（デフォルト: ap-northeast-1）")
        print("  S3_BUCKET_NAME - S3バケット名")
        return False

    try:
        s3_client = get_s3_client()

        s3_client.upload_file(
            local_path,
            S3_BUCKET_NAME,
            s3_path
        )

        print(f"ファイルを S3 ({S3_BUCKET_NAME}/{s3_path}) に保存しました")
        return True
    except Exception as e:
        print(f"S3へのアップロードに失敗しました: {e}")
        return False

def upload_to_s3(local_path, s3_key, content_type=None):
    '''
    ファイルをS3にアップロード（ファイルオブジェクトとして）

    Parameters:
    -----------
    local_path : str
        ローカルファイルパス
    s3_key : str
        S3上のキー
    content_type : str, optional
        コンテンツタイプ

    Returns:
    --------
    bool
        成功したかどうか
    '''
    if not (AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME):
        print("S3認証情報が設定されていないため、S3への保存をスキップします")
        print("S3に保存するには、.env ファイルに以下の環境変数を設定してください：")
        print("  AWS_ACCESS_KEY - AWSアクセスキー")
        print("  AWS_SECRET_KEY - AWSシークレットキー")
        print("  AWS_REGION - AWSリージョン（デフォルト: ap-northeast-1）")
        print("  S3_BUCKET_NAME - S3バケット名")
        return False

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
        print(f"ファイルを S3 ({S3_BUCKET_NAME}/{s3_key}) に保存しました")
        return True
    except Exception as e:
        print(f"S3アップロードエラー ({local_path} -> {s3_key}): {e}")
        return False

def put_json_to_s3(data, s3_key):
    '''
    JSONデータをS3に直接アップロード

    Parameters:
    -----------
    data : dict
        JSONに変換するデータ
    s3_key : str
        S3上のキー

    Returns:
    --------
    bool
        成功したかどうか
    '''
    if not (AWS_ACCESS_KEY and AWS_SECRET_KEY and S3_BUCKET_NAME):
        print("S3認証情報が設定されていないため、S3への保存をスキップします")
        print("S3に保存するには、.env ファイルに以下の環境変数を設定してください：")
        print("  AWS_ACCESS_KEY - AWSアクセスキー")
        print("  AWS_SECRET_KEY - AWSシークレットキー")
        print("  AWS_REGION - AWSリージョン（デフォルト: ap-northeast-1）")
        print("  S3_BUCKET_NAME - S3バケット名")
        return False

    try:
        s3_client = get_s3_client()

        # JSONデータを文字列に変換
        json_data = json.dumps(data, ensure_ascii=False, indent=4)

        # S3にアップロード
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json"
        )

        print(f"JSONデータを S3 ({S3_BUCKET_NAME}/{s3_key}) に保存しました")
        return True
    except Exception as e:
        print(f"S3へのJSONアップロードに失敗しました: {e}")
        return False

def get_s3_key_path(date_str: str, data_type: str, file_type: str) -> str:
    """
    S3のキーパスを生成します。

    Parameters:
    -----------
    date_str : str
        日付（YYYYMMDD形式）
    data_type : str
        データタイプ（'rankings', 'citations', 'sentiment', 'google_serp'）
    file_type : str
        ファイルタイプ（'perplexity', 'google'）

    Returns:
    --------
    str
        S3のキーパス
    """
    base_path = f"results/{data_type}/{date_str}"

    if file_type == "perplexity":
        if data_type == "rankings":
            return f"{base_path}/{date_str}_perplexity_rankings_10runs.json"
        elif data_type == "citations":
            return f"{base_path}/{date_str}_perplexity_citations_10runs.json"
        elif data_type == "sentiment":
            return f"{base_path}/{date_str}_perplexity_sentiment_3runs.json"
    elif file_type == "google":
        if data_type == "google_serp":
            return f"{base_path}/{date_str}_google_serp_results.json"

    raise ValueError(f"未対応のデータタイプまたはファイルタイプ: {data_type}, {file_type}")

def get_local_path(date_str, data_type, file_type):
    """
    ローカルファイルパスを生成する関数

    Parameters
    ----------
    date_str : str
        日付文字列（YYYYMMDD形式）
    data_type : str
        データタイプ（"rankings", "citations", "sentiment", "google_serp"）
    file_type : str
        ファイルタイプ（"perplexity", "google"）

    Returns
    -------
    str
        生成されたローカルファイルパス
    """
    # データタイプに基づいてディレクトリを決定
    if data_type == "rankings":
        dir_name = "perplexity_rankings"
    elif data_type == "citations":
        dir_name = "perplexity_citations"
    elif data_type == "sentiment":
        dir_name = "perplexity_sentiment"
    elif data_type == "google_serp":
        dir_name = "google_serp"
    else:
        raise ValueError(f"Unsupported data type: {data_type}")

    # ファイル名を生成
    if file_type == "perplexity":
        file_name = f"{date_str}_perplexity_{data_type}.json"
    elif file_type == "google":
        file_name = f"{date_str}_google_serp_results.json"
    else:
        raise ValueError(f"Unsupported file type: {file_type}")

    # パスを生成（S3と同じ構造）
    local_path = f"results/{dir_name}/{date_str}/{file_name}"

    # ディレクトリが存在しない場合は作成
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    return local_path

def get_latest_file(date_str=None, data_type="rankings", api_type="perplexity", prefix="results/"):
    """
    指定した日付の最新ファイルを取得

    Parameters
    ----------
    date_str : str, optional
        YYYYMMDD形式の日付文字列、未指定時は最新日付
    data_type : str, optional
        データタイプ（"rankings", "citations", "sentiment", "google_serp"）
    api_type : str, optional
        APIタイプ（"perplexity", "google"）
    prefix : str, optional
        S3内のプレフィックス

    Returns
    -------
    tuple
        (s3_key, json_content) のタプル、見つからない場合は (None, None)
    """
    s3_client = get_s3_client()

    # データタイプに応じたディレクトリ名を設定
    dir_map = {
        "rankings": "perplexity_rankings",
        "citations": "perplexity_citations",
        "sentiment": "perplexity_sentiment",
        "google_serp": "google_serp"
    }
    dir_name = dir_map.get(data_type, data_type)

    # 日付が指定されている場合はその日付のディレクトリを検索
    if date_str:
        prefix = f"{prefix}{dir_name}/{date_str}/"
    else:
        prefix = f"{prefix}{dir_name}/"

    try:
        # 指定プレフィックスのファイル一覧を取得
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix
        )

        if 'Contents' not in response:
            print(f"ファイルが見つかりません: {prefix}")
            return None, None

        # データタイプに一致するファイルをフィルタリング
        target_files = [item for item in response['Contents']
                       if item['Key'].endswith('.json') and data_type in item['Key']]

        if not target_files:
            print(f"ファイルが見つかりません: {prefix}")
            return None, None

        # 複数回実行のファイルを優先的に選択
        multi_run_files = [f for f in target_files if '_runs.json' in f['Key']]
        if multi_run_files:
            # 実行回数が多いものを優先し、同じ実行回数の場合は更新日時が新しいものを選択
            target_file = sorted(multi_run_files,
                               key=lambda x: (
                                   int(x['Key'].split('_runs')[0].split('_')[-1]),  # 実行回数
                                   x['LastModified']  # 更新日時
                               ),
                               reverse=True)[0]
        else:
            # 単一実行のファイルを使用（更新日時が新しいものを選択）
            target_file = sorted([f for f in target_files if not '_runs.json' in f['Key']],
                               key=lambda x: x['LastModified'],
                               reverse=True)[0]

        # ファイルの内容を取得
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=target_file['Key'])
        content = response['Body'].read().decode('utf-8')

        return target_file['Key'], content

    except Exception as e:
        print(f"S3からのファイル取得エラー: {e}")
        return None, None