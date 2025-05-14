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

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
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