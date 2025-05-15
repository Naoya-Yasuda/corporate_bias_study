#!/usr/bin/env python
# coding: utf-8

"""
共通ユーティリティパッケージ

複数モジュールで使用する共通関数を提供します。
"""

# s3 utils
from .s3_utils import save_to_s3, upload_to_s3, put_json_to_s3, get_s3_client

# file utils
from .file_utils import ensure_dir, save_json, get_today_str, load_json

# text utils
from .text_utils import extract_domain, is_negative, ratio

# rank utils
from .rank_utils import rbo, rank_map, compute_tau, compute_delta_ranks

# plot utils
from .plot_utils import plot_delta_ranks, plot_market_impact, set_plot_style

# storage config
from .storage_config import is_s3_enabled, is_local_enabled, get_storage_config, get_results_paths

# storage utils (新しい統合ストレージAPI)
from .storage_utils import (
    save_data, save_json_data, save_text_data, save_binary_data, save_figure,
    get_today_str, get_s3_client
)