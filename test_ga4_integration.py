#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GA4統合のテストスクリプト

GA4の基本機能が正常に動作することを確認します。
"""

import os
import sys
import tempfile
from pathlib import Path

# プロジェクトルートを追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_ga4_utilities():
    """GA4ユーティリティ関数のテスト"""
    from src.utils.analytics_utils import (
        get_ga4_measurement_id, 
        is_ga4_enabled, 
        get_ga4_status_info,
        render_ga4_tracking
    )
    
    print("=== GA4ユーティリティテスト ===")
    
    # 1. 環境変数なしの場合
    os.environ.pop('GA4_MEASUREMENT_ID', None)
    
    measurement_id = get_ga4_measurement_id()
    enabled = is_ga4_enabled()
    status = get_ga4_status_info()
    
    assert measurement_id is None, f"Expected None, got {measurement_id}"
    assert not enabled, f"Expected False, got {enabled}"
    assert not status['enabled'], f"Expected False, got {status['enabled']}"
    assert status['status'] == 'disabled', f"Expected 'disabled', got {status['status']}"
    
    print("✓ 環境変数なしの場合のテスト: 成功")
    
    # 2. 正しいGA4 IDの場合
    os.environ['GA4_MEASUREMENT_ID'] = 'G-TEST123456'
    
    measurement_id = get_ga4_measurement_id()
    enabled = is_ga4_enabled()
    status = get_ga4_status_info()
    
    assert measurement_id == 'G-TEST123456', f"Expected 'G-TEST123456', got {measurement_id}"
    assert enabled, f"Expected True, got {enabled}"
    assert status['enabled'], f"Expected True, got {status['enabled']}"
    assert status['status'] == 'active', f"Expected 'active', got {status['status']}"
    
    print("✓ 正しいGA4 IDの場合のテスト: 成功")
    
    # 3. 不正なGA4 IDの場合
    os.environ['GA4_MEASUREMENT_ID'] = 'INVALID_ID'
    
    measurement_id = get_ga4_measurement_id()
    enabled = is_ga4_enabled()
    status = get_ga4_status_info()
    
    assert measurement_id == 'INVALID_ID', f"Expected 'INVALID_ID', got {measurement_id}"
    assert not enabled, f"Expected False, got {enabled}"
    assert not status['enabled'], f"Expected False, got {status['enabled']}"
    assert status['status'] == 'invalid', f"Expected 'invalid', got {status['status']}"
    
    print("✓ 不正なGA4 IDの場合のテスト: 成功")
    
    # 4. 空文字の場合
    os.environ['GA4_MEASUREMENT_ID'] = '   '
    
    measurement_id = get_ga4_measurement_id()
    enabled = is_ga4_enabled()
    
    assert measurement_id is None, f"Expected None, got {measurement_id}"
    assert not enabled, f"Expected False, got {enabled}"
    
    print("✓ 空文字の場合のテスト: 成功")
    
    # クリーンアップ
    os.environ.pop('GA4_MEASUREMENT_ID', None)
    
    print("✓ 全てのGA4ユーティリティテストが成功しました")

def test_app_imports():
    """アプリのインポートテスト"""
    print("\n=== アプリインポートテスト ===")
    
    try:
        # GA4モジュールのインポート
        from src.utils.analytics_utils import render_ga4_tracking, is_ga4_enabled, get_ga4_status_info
        print("✓ GA4モジュールのインポート: 成功")
        
        # 他の主要モジュールのインポート確認
        from src.utils.config_manager import ConfigManager
        print("✓ 設定マネージャーのインポート: 成功")
        
        print("✓ 全てのインポートテストが成功しました")
        
    except ImportError as e:
        print(f"✗ インポートエラー: {e}")
        raise
    except Exception as e:
        print(f"✗ 実行時エラー: {e}")
        raise

def main():
    """メインテスト実行"""
    print("企業バイアス分析システム - GA4統合テスト")
    print("=" * 50)
    
    try:
        test_ga4_utilities()
        test_app_imports()
        
        print("\n" + "=" * 50)
        print("🎉 全てのテストが成功しました！")
        print("GA4統合が正常に実装されています。")
        
        # 実際の使用方法を表示
        print("\n📋 使用方法:")
        print("1. .env ファイルに GA4_MEASUREMENT_ID=G-XXXXXXXXXX を設定")
        print("2. Streamlitアプリを起動: streamlit run app.py")
        print("3. サイドバーでGA4ステータスを確認")
        
        return True
        
    except Exception as e:
        print(f"\n❌ テストが失敗しました: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)