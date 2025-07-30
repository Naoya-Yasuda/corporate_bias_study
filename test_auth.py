#!/usr/bin/env python
# coding: utf-8

"""
認証機能テストスクリプト

Google OAuth SSO認証機能の動作確認を行います。
"""

import os
import sys
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# プロジェクトルートをパスに追加
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.auth.domain_validator import DomainValidator, create_default_domain_validator
from src.auth.session_manager import SessionManager, UserInfo, get_session_manager
from src.auth.google_oauth import GoogleOAuthManager, get_oauth_manager
from src.utils.auth_utils import validate_auth_config, get_auth_debug_info, check_auth_health


def test_domain_validator():
    """ドメイン制限チェックのテスト"""
    print("=== ドメイン制限チェックテスト ===")

    # デフォルトバリデーター作成
    validator = create_default_domain_validator()

    # テストケース
    test_emails = [
        "test@cyber-u.ac.jp",      # 許可ドメイン
        "user@cyber-u.ac.jp",      # 許可ドメイン
        "test@gmail.com",          # 不許可ドメイン
        "user@yahoo.co.jp",        # 不許可ドメイン
        "invalid-email",           # 無効なメールアドレス
        "",                        # 空文字
        None                       # None
    ]

    for email in test_emails:
        if email is None:
            result = validator.validate_email("")
        else:
            result = validator.validate_email(email)
        print(f"Email: {email} -> Valid: {result}")

    print()


def test_session_manager():
    """セッション管理のテスト"""
    print("=== セッション管理テスト ===")

    # セッションマネージャー作成
    session_manager = get_session_manager()

    # テストユーザー情報作成
    user_info = UserInfo(
        email="test@cyber-u.ac.jp",
        name="テストユーザー",
        picture="https://example.com/avatar.jpg"
    )

    print(f"User Info: {user_info.to_dict()}")

    # セッション作成
    session_id = session_manager.create_session(user_info)
    print(f"Session ID: {session_id}")

    # セッション検証
    is_valid = session_manager.validate_session()
    print(f"Session Valid: {is_valid}")

    # ユーザー情報取得
    retrieved_user = session_manager.get_user_info()
    if retrieved_user:
        print(f"Retrieved User: {retrieved_user.to_dict()}")

    # 認証状態チェック
    is_auth = session_manager.is_authenticated()
    print(f"Is Authenticated: {is_auth}")

    print()


def test_oauth_manager():
    """OAuthマネージャーのテスト"""
    print("=== OAuthマネージャーテスト ===")

    # OAuthマネージャー作成
    oauth_manager = get_oauth_manager()

    # 初期化チェック
    init_result = oauth_manager.initialize_oauth()
    print(f"OAuth Initialized: {init_result}")

    # 設定情報表示
    print(f"Client ID Set: {bool(oauth_manager.client_id)}")
    print(f"Client Secret Set: {bool(oauth_manager.client_secret)}")
    print(f"Redirect URI: {oauth_manager.redirect_uri}")
    print(f"Allowed Domains: {oauth_manager.get_allowed_domains()}")
    print(f"Debug Mode: {oauth_manager.debug_mode}")

    print()


def test_auth_utils():
    """認証ユーティリティのテスト"""
    print("=== 認証ユーティリティテスト ===")

    # 設定検証
    config_valid = validate_auth_config()
    print(f"Config Valid: {config_valid}")

    # デバッグ情報取得
    debug_info = get_auth_debug_info()
    print("Debug Info:")
    for key, value in debug_info.items():
        print(f"  {key}: {value}")

    # 健全性チェック
    health_info = check_auth_health()
    print("Health Info:")
    for key, value in health_info.items():
        print(f"  {key}: {value}")

    print()


def test_environment_variables():
    """環境変数のテスト"""
    print("=== 環境変数テスト ===")

    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI",
        "ALLOWED_DOMAINS",
        "AUTH_DEBUG_MODE",
        "SESSION_TIMEOUT",
        "JWT_SECRET_KEY",
        "ENCRYPTION_KEY"
    ]

    for var in required_vars:
        value = os.getenv(var)
        if value:
            # 機密情報は一部マスク
            if "SECRET" in var or "KEY" in var:
                masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:] if len(value) > 8 else "***"
                print(f"{var}: {masked_value}")
            else:
                print(f"{var}: {value}")
        else:
            print(f"{var}: NOT SET")

    print()


def main():
    """メイン関数"""
    print("Google OAuth SSO認証機能テスト")
    print("=" * 50)

    # 環境変数テスト
    test_environment_variables()

    # ドメイン制限チェックテスト
    test_domain_validator()

    # セッション管理テスト
    test_session_manager()

    # OAuthマネージャーテスト
    test_oauth_manager()

    # 認証ユーティリティテスト
    test_auth_utils()

    print("テスト完了")


if __name__ == "__main__":
    main()