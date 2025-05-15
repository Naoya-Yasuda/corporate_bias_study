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

def save_json(data, file_path, ensure_dir_exists=True):
    '''
    JSONデータをファイルに保存

    Parameters:
    -----------
    data : dict
        保存するデータ
    file_path : str
        保存先ファイルパス
    ensure_dir_exists : bool, optional
        ディレクトリを自動作成するかどうか

    Returns:
    --------
    bool
        成功したかどうか
    '''
    try:
        if ensure_dir_exists:
            dir_name = os.path.dirname(file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

        # Infinity値をJSON互換の値に変換するカスタムエンコーダー
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, float) and (obj == float('inf') or obj == float('-inf') or obj != obj):  # 最後の条件はNaN
                    if obj == float('inf'):
                        return "Infinity"
                    elif obj == float('-inf'):
                        return "-Infinity"
                    else:
                        return "NaN"
                return super().default(obj)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4, cls=CustomJSONEncoder)
        return True
    except Exception as e:
        print(f"JSONファイルの保存に失敗しました: {e}")
        return False

def load_json(file_path):
    '''
    JSONファイルを読み込む

    Parameters:
    -----------
    file_path : str
        読み込むファイルパス

    Returns:
    --------
    dict | None
        読み込んだデータ、失敗した場合はNone
    '''
    try:
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

# 後方互換性のための関数エイリアス
def get_local_json(file_path):
    '''
    JSONファイルを読み込む (load_jsonのエイリアス)

    Parameters:
    -----------
    file_path : str
        読み込むファイルパス

    Returns:
    --------
    dict | None
        読み込んだデータ、失敗した場合はNone
    '''
    print(f"注意: get_local_jsonは非推奨です。代わりにload_jsonを使用してください")
    return load_json(file_path)

def get_s3_json(s3_key):
    '''
    S3からJSONを読み込む関数のスタブ
    このスタブは後方互換性のために存在します

    Parameters:
    -----------
    s3_key : str
        S3上のキー

    Returns:
    --------
    dict | None
        読み込んだデータ、失敗した場合はNone
    '''
    print(f"注意: get_s3_jsonは非推奨です。代わりにS3アクセス用の適切な関数を使用してください")
    from .s3_utils import get_s3_client, S3_BUCKET_NAME

    try:
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        print(f"S3からのJSONファイル読み込みに失敗しました: {e}")
        return None

def save_json_data(data, local_path, s3_path=None):
    '''
    JSONデータを保存する (storage_utils.save_json_dataのエイリアス)

    Parameters:
    -----------
    data : dict
        保存するデータ
    local_path : str
        ローカルファイルパス
    s3_path : str, optional
        S3上のパス

    Returns:
    --------
    dict
        保存結果 {"local": bool, "s3": bool}
    '''
    print(f"注意: file_utils.save_json_dataは非推奨です。代わりにstorage_utils.save_json_dataを使用してください")
    from .storage_utils import save_json_data as storage_save_json_data
    return storage_save_json_data(data, local_path, s3_path)