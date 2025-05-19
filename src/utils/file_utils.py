#!/usr/bin/env python
# coding: utf-8

'''
ファイル操作のユーティリティ関数

ファイルの読み書き機能を提供します
'''

import os
import json
import datetime

def ensure_dir(dir_path):
    '''
    ディレクトリが存在しない場合は作成する

    Parameters:
    -----------
    dir_path : str
        作成するディレクトリパス
    '''
    os.makedirs(dir_path, exist_ok=True)

def load_json(file_path):
    '''
    JSONファイルを読み込む（ローカルまたはS3対応）

    Parameters:
    -----------
    file_path : str
        読み込むファイルパス（s3://で始まる場合はS3から取得）

    Returns:
    --------
    dict | None
        読み込んだデータ、失敗した場合はNone
    '''
    if file_path.startswith('s3://'):
        # S3パスの場合
        import re
        from .s3_utils import get_s3_client, S3_BUCKET_NAME
        s3_client = get_s3_client()
        # s3://bucket/key の形式を想定
        m = re.match(r's3://([^/]+)/(.+)', file_path)
        if m:
            bucket, key = m.group(1), m.group(2)
        else:
            # バケット省略時はデフォルトバケット
            bucket, key = S3_BUCKET_NAME, file_path[5:]
        try:
            response = s3_client.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except Exception as e:
            print(f"S3からのJSONファイル読み込みに失敗しました: {e}")
            return None
    else:
        # ローカルファイル
        try:
            # ファイルが存在するか確認
            if not os.path.exists(file_path):
                print(f"ファイルが存在しません: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSONファイルの読み込みに失敗しました: {e}")
            return None

def get_today_str():
    '''
    今日の日付を YYYYMMDD 形式で取得

    Returns:
    --------
    str
        YYYYMMDD 形式の日付
    '''
    return datetime.datetime.now().strftime("%Y%m%d")