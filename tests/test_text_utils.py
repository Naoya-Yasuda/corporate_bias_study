#!/usr/bin/env python
# coding: utf-8

"""text_utilsモジュールのテスト"""

from pathlib import Path
import sys

import pytest

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.text_utils import extract_domain


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.example.com/path", "example.com"),
        ("HTTP://Sub.Example.COM/page", "sub.example.com"),
        ("example.com/about", "example.com"),
        ("www.example.com", "example.com"),
        ("example.com:8080/path", "example.com"),
        ("", ""),
    ],
)
def test_extract_domain(url, expected):
    """extract_domainがスキーム省略やポート番号などに対応できること"""

    assert extract_domain(url) == expected
