#!/usr/bin/env python
# coding: utf-8

"""
Perplexity API 共通モジュール
Perplexity APIを呼び出すための共通クラス・関数を提供するモジュール
"""

import os
import json
import time
import requests
from typing import Dict, List, Optional, Union
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# Perplexity API の設定
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
API_HOST = "api.perplexity.ai"
API_VERSION = "v1"
PERPLEXITY_MODELS_TO_TRY = os.environ.get("PERPLEXITY_MODELS_TO_TRY", "llama-3.1-sonar-large-128k-online,llama-3.1-sonar-large-128k").split(",")

class PerplexityAPI:
    """Perplexity APIを呼び出すためのクラス"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Parameters
        ----------
        api_key : str, optional
            Perplexity APIキー。指定がない場合は環境変数から取得
        """
        self.api_key = api_key or PERPLEXITY_API_KEY
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY が設定されていません。.env ファイルを確認してください。")

    def _get_headers(self) -> Dict[str, str]:
        """APIリクエスト用のヘッダーを取得"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _get_api_url(self, endpoint: str) -> str:
        """APIエンドポイントのURLを取得"""
        if endpoint == "chat/completions":
            return f"https://{API_HOST}/chat/completions"
        return f"https://{API_HOST}/{API_VERSION}/{endpoint}"

    def search(self, prompt: str, max_retries: int = 3, retry_delay: float = 1.0) -> Optional[Dict]:
        """
        Perplexity APIで検索を実行

        Parameters
        ----------
        prompt : str
            プロンプト
        max_retries : int, optional
            リトライ回数の上限（デフォルト: 3）
        retry_delay : float, optional
            リトライ間隔（秒）（デフォルト: 1.0）

        Returns
        -------
        Optional[Dict]
            検索結果。エラー時はNone
        """
        url = self._get_api_url("search")
        headers = self._get_headers()
        data = {"query": prompt}

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"Perplexity API リクエストエラー: {e}")
                    return None
                time.sleep(retry_delay)

        return None

    def call_perplexity_api(self, prompt: str, model: str = None, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Perplexity APIでAIモデルを呼び出し、回答テキストとcitationsを両方返す

        Returns
        -------
        tuple (str, list)
            (回答テキスト, citationsリスト)
        """
        url = self._get_api_url("chat/completions")
        headers = self._get_headers()
        if model is None:
            model = self.get_models_to_try()[0]
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.0,
            "stream": False
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"].strip() if "choices" in res_json and res_json["choices"] else ""
                citations = res_json.get("citations", [])
                return content, citations
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"Perplexity API リクエストエラー: {e}")
                    return "", []
                time.sleep(retry_delay)
        return "", []

    @staticmethod
    def get_models_to_try():
        """
        利用可能なPerplexityモデルのリストを返す（.envで管理、なければデフォルト）
        """
        return PERPLEXITY_MODELS_TO_TRY