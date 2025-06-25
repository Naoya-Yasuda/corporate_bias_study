#!/usr/bin/env python
# coding: utf-8

"""
共通ユーティリティパッケージ

複数モジュールで使用する共通関数を提供します。
"""

# text utils
from .text_utils import extract_domain, is_negative, ratio

# rank utils
from .rank_utils import rbo, rank_map, compute_tau, compute_delta_ranks

# plot utils
from .plot_utils import plot_delta_ranks, plot_market_impact

# storage utils (統合ファイル操作・ストレージAPI)
from .storage_utils import (
    ensure_dir, get_today_str, load_json, save_json,
    save_text_data, save_binary_data, save_figure,
    get_s3_client, get_results_paths, save_results,
    get_latest_file, list_s3_files
)

# storage config
from .storage_config import is_s3_enabled, is_local_enabled, get_storage_config