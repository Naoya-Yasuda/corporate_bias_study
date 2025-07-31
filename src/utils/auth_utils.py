"""
認証関連ユーティリティ

認証機能で使用する共通ユーティリティ関数を提供します。
"""

import os
import logging
from typing import Optional, Dict, Any
from ..auth.google_oauth import GoogleOAuthManager
from ..auth.session_manager import SessionManager

# ロガー設定
logger = logging.getLogger(__name__)


def validate_auth_config() -> bool:
    """
    認証設定の検証

    Returns:
        bool: 設定が正しい場合True
    """
    # OAuth認証フラグの確認
    oauth_flag = os.getenv('OAUTH_FLAG', 'true').lower()
    if oauth_flag in ['false', '0', 'no']:
        logger.info("OAuth認証が無効化されているため、認証設定の検証をスキップします")
        return True

    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI"
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"必要な環境変数が設定されていません: {missing_vars}")
        return False

    return True


def is_authenticated() -> bool:
    """
    認証状態チェック

    Returns:
        bool: 認証済みの場合True
    """
    try:
        import streamlit as st
        # セッション状態ベースの認証チェック
        return hasattr(st.session_state, 'authenticated') and st.session_state.authenticated
    except Exception as e:
        logger.error(f"認証状態チェックエラー: {e}")
        return False


def get_current_user_info():
    """
    現在のユーザー情報取得

    Returns:
        ユーザー情報、未認証の場合はNone
    """
    try:
        import streamlit as st
        # セッション状態からユーザー情報を取得
        if hasattr(st.session_state, 'authenticated') and st.session_state.authenticated:
            return getattr(st.session_state, 'user_info', None)
        return None
    except Exception as e:
        logger.error(f"ユーザー情報取得エラー: {e}")
        return None


def logout_user() -> bool:
    """
    ユーザーログアウト

    Returns:
        bool: ログアウト成功の場合True
    """
    try:
        oauth_manager = GoogleOAuthManager()
        return oauth_manager.logout()
    except Exception as e:
        logger.error(f"ログアウトエラー: {e}")
        return False


def get_allowed_domains() -> list:
    """
    許可されているドメインのリストを取得

    Returns:
        list: 許可ドメインのリスト
    """
    try:
        oauth_manager = GoogleOAuthManager()
        return oauth_manager.get_allowed_domains()
    except Exception as e:
        logger.error(f"許可ドメイン取得エラー: {e}")
        return ["cyber-u.ac.jp"]  # デフォルト


def log_auth_event(event_type: str, user_info: Dict[str, Any] = None, success: bool = True, error: str = ""):
    """
    認証イベントのログ出力

    Args:
        event_type: イベントタイプ
        user_info: ユーザー情報
        success: 成功フラグ
        error: エラーメッセージ
    """
    try:
        log_data = {
            "event_type": event_type,
            "success": success,
            "user_email": user_info.get("email") if user_info else None,
            "user_domain": user_info.get("domain") if user_info else None,
            "error": error
        }

        if success:
            logger.info(f"Auth event: {log_data}")
        else:
            logger.error(f"Auth event: {log_data}")

    except Exception as e:
        logger.error(f"認証ログ出力エラー: {e}")


def get_auth_debug_info() -> Dict[str, Any]:
    """
    認証デバッグ情報の取得

    Returns:
        Dict[str, Any]: デバッグ情報
    """
    try:
        oauth_manager = GoogleOAuthManager()
        oauth_flag = os.getenv('OAUTH_FLAG', 'true').lower()

        debug_info = {
            "oauth_flag": oauth_flag,
            "oauth_enabled": oauth_flag not in ['false', '0', 'no'],
            "client_id_set": bool(os.getenv("GOOGLE_CLIENT_ID")),
            "client_secret_set": bool(os.getenv("GOOGLE_CLIENT_SECRET")),
            "redirect_uri_set": bool(os.getenv("GOOGLE_REDIRECT_URI")),
            "allowed_domains": oauth_manager.get_allowed_domains(),
            "debug_mode": os.getenv("AUTH_DEBUG_MODE", "false").lower() == "true",
            "session_timeout": int(os.getenv("SESSION_TIMEOUT", "3600")),
            "jwt_secret_set": bool(os.getenv("JWT_SECRET_KEY")),
            "is_authenticated": oauth_manager.is_authenticated()
        }

        return debug_info

    except Exception as e:
        logger.error(f"デバッグ情報取得エラー: {e}")
        return {"error": str(e)}


def check_auth_health() -> Dict[str, Any]:
    """
    認証システムの健全性チェック

    Returns:
        Dict[str, Any]: 健全性情報
    """
    try:
        health_info = {
            "config_valid": validate_auth_config(),
            "oauth_initialized": False,
            "session_manager_ready": False,
            "overall_status": "unknown"
        }

        # OAuth初期化チェック
        oauth_manager = GoogleOAuthManager()
        health_info["oauth_initialized"] = oauth_manager.initialize_oauth()

        # セッションマネージャーチェック
        session_manager = SessionManager()
        health_info["session_manager_ready"] = True

        # 全体ステータス判定
        if health_info["config_valid"] and health_info["oauth_initialized"] and health_info["session_manager_ready"]:
            health_info["overall_status"] = "healthy"
        elif health_info["config_valid"]:
            health_info["overall_status"] = "partial"
        else:
            health_info["overall_status"] = "unhealthy"

        return health_info

    except Exception as e:
        logger.error(f"健全性チェックエラー: {e}")
        return {
            "config_valid": False,
            "oauth_initialized": False,
            "session_manager_ready": False,
            "overall_status": "error",
            "error": str(e)
        }