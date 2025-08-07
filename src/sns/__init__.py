#!/usr/bin/env python
# coding: utf-8

"""
SNS投稿機能パッケージ

企業優遇バイアス分析結果の自動SNS投稿機能を提供します。
"""

import os
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

__version__ = "1.0.0"
__author__ = "Corporate Bias Study Team"

from .twitter_client import TwitterClient
from .simple_change_detector import SimpleChangeDetector
from .simple_content_generator import SimpleContentGenerator
from .simple_posting_system import SimplePostingSystem
from .s3_data_loader import S3DataLoader
from .integrated_posting_system import IntegratedPostingSystem

__all__ = [
    "TwitterClient",
    "SimpleChangeDetector",
    "SimpleContentGenerator",
    "SimplePostingSystem",
    "S3DataLoader",
    "IntegratedPostingSystem"
]