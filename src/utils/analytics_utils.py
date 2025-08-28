#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Google Analytics 4 統合ユーティリティ

Streamlitアプリケーション用のGA4トラッキング機能を提供します。
環境変数による設定管理と、基本的なページビュー追跡を実装しています。
"""

import os
import streamlit as st
from typing import Optional


def get_ga4_measurement_id() -> Optional[str]:
    """
    環境変数からGA4測定IDを取得
    
    Returns:
        str: GA4測定ID、設定されていない場合はNone
    """
    return os.getenv('GA4_MEASUREMENT_ID', '').strip() or None


def render_ga4_tracking() -> None:
    """
    GA4トラッキングコードをStreamlitアプリに注入
    
    環境変数GA4_MEASUREMENT_IDが設定されている場合のみ、
    Google Analytics 4のトラッキングコードを挿入します。
    """
    measurement_id = get_ga4_measurement_id()
    
    # GA4測定IDが設定されていない場合は何もしない
    if not measurement_id:
        return
    
    # GA4測定IDの形式チェック（G-で始まる形式）
    if not measurement_id.startswith('G-'):
        st.warning(f"⚠️ GA4測定IDの形式が正しくありません: {measurement_id}")
        return
    
    # Google Analytics 4のトラッキングコード
    ga4_script = f"""
    <!-- Google Analytics 4 -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{measurement_id}');
    </script>
    """
    
    # HTMLを注入（ページの<head>部分に追加される）
    st.markdown(ga4_script, unsafe_allow_html=True)


def track_page_view(page_title: Optional[str] = None, page_location: Optional[str] = None) -> None:
    """
    カスタムページビューイベントを送信
    
    Args:
        page_title: ページタイトル（オプション）
        page_location: ページURL（オプション）
    """
    measurement_id = get_ga4_measurement_id()
    
    # GA4測定IDが設定されていない場合は何もしない
    if not measurement_id:
        return
    
    # カスタムページビューイベント用のJavaScript
    custom_event_script = f"""
    <script>
      if (typeof gtag !== 'undefined') {{
        gtag('event', 'page_view', {{
          page_title: '{page_title or "企業バイアス分析ダッシュボード"}',
          page_location: '{page_location or window.location.href}'
        }});
      }}
    </script>
    """
    
    st.markdown(custom_event_script, unsafe_allow_html=True)


def is_ga4_enabled() -> bool:
    """
    GA4トラッキングが有効かどうかを確認
    
    Returns:
        bool: GA4が有効な場合True
    """
    measurement_id = get_ga4_measurement_id()
    return measurement_id is not None and measurement_id.startswith('G-')


def get_ga4_status_info() -> dict:
    """
    GA4設定の状態情報を取得
    
    Returns:
        dict: GA4の設定状態情報
    """
    measurement_id = get_ga4_measurement_id()
    
    if not measurement_id:
        return {
            'enabled': False,
            'status': 'disabled',
            'message': 'GA4_MEASUREMENT_IDが設定されていません',
            'measurement_id': None
        }
    
    if not measurement_id.startswith('G-'):
        return {
            'enabled': False,
            'status': 'invalid',
            'message': f'GA4測定IDの形式が正しくありません: {measurement_id}',
            'measurement_id': measurement_id
        }
    
    return {
        'enabled': True,
        'status': 'active',
        'message': 'GA4トラッキングが有効です',
        'measurement_id': measurement_id
    }