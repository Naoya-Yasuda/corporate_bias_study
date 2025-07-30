"""
認証モジュール

Google OAuth SSO認証機能を提供します。
"""

from .google_oauth import GoogleOAuthManager, AuthResult, get_oauth_manager
from .session_manager import SessionManager, UserInfo, get_session_manager
from .domain_validator import DomainValidator, create_default_domain_validator

__all__ = [
    "GoogleOAuthManager",
    "AuthResult",
    "get_oauth_manager",
    "SessionManager",
    "UserInfo",
    "get_session_manager",
    "DomainValidator",
    "create_default_domain_validator"
]