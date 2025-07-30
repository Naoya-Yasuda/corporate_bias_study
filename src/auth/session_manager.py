"""
セッション管理モジュール

Streamlitのsession_stateを活用したセッション管理機能を提供します。
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import jwt
import streamlit as st
import os


class UserInfo:
    """ユーザー情報クラス"""

    def __init__(self, email: str, name: str = "", picture: str = ""):
        """
        初期化

        Args:
            email: ユーザーのメールアドレス
            name: ユーザー名
            picture: プロフィール画像URL
        """
        self.email = email
        self.name = name
        self.picture = picture
        self.domain = email.split('@')[1] if '@' in email else ""
        self.created_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "domain": self.domain,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserInfo':
        """辞書からUserInfoオブジェクトを作成"""
        user_info = cls(
            email=data.get("email", ""),
            name=data.get("name", ""),
            picture=data.get("picture", "")
        )
        if "created_at" in data:
            user_info.created_at = datetime.fromisoformat(data["created_at"])
        return user_info


class SessionManager:
    """セッション管理クラス"""

    def __init__(self, session_timeout: int = 3600):
        """
        初期化

        Args:
            session_timeout: セッションタイムアウト（秒）
        """
        self.session_timeout = session_timeout
        self.jwt_secret = os.getenv("JWT_SECRET_KEY", "default-secret-key")

    def create_session(self, user_info: UserInfo) -> str:
        """
        セッション作成

        Args:
            user_info: ユーザー情報

        Returns:
            str: セッションID
        """
        # JWTトークン生成
        session_data = {
            "user_info": user_info.to_dict(),
            "created_at": datetime.now().isoformat(),
            "exp": datetime.now() + timedelta(seconds=self.session_timeout)
        }

        session_token = jwt.encode(session_data, self.jwt_secret, algorithm="HS256")

        # Streamlit session_stateに保存
        st.session_state["auth_session"] = session_token
        st.session_state["user_info"] = user_info.to_dict()
        st.session_state["is_authenticated"] = True

        return session_token

    def validate_session(self, session_id: str = None) -> bool:
        """
        セッション検証

        Args:
            session_id: セッションID（Noneの場合はsession_stateから取得）

        Returns:
            bool: 有効なセッションの場合True
        """
        try:
            # session_stateからセッション情報を取得
            if "auth_session" not in st.session_state:
                return False

            session_token = session_id or st.session_state["auth_session"]

            # JWTトークンの検証
            payload = jwt.decode(session_token, self.jwt_secret, algorithms=["HS256"])

            # 有効期限チェック
            exp_time = datetime.fromisoformat(payload["exp"])
            if datetime.now() > exp_time:
                self.destroy_session()
                return False

            return True

        except jwt.ExpiredSignatureError:
            # トークン期限切れ
            self.destroy_session()
            return False
        except jwt.InvalidTokenError:
            # 無効なトークン
            self.destroy_session()
            return False
        except Exception:
            # その他のエラー
            self.destroy_session()
            return False

    def get_user_info(self, session_id: str = None) -> Optional[UserInfo]:
        """
        ユーザー情報取得

        Args:
            session_id: セッションID（Noneの場合はsession_stateから取得）

        Returns:
            Optional[UserInfo]: ユーザー情報、無効な場合はNone
        """
        try:
            if not self.validate_session(session_id):
                return None

            session_token = session_id or st.session_state["auth_session"]
            payload = jwt.decode(session_token, self.jwt_secret, algorithms=["HS256"])

            user_info_data = payload["user_info"]
            return UserInfo.from_dict(user_info_data)

        except Exception:
            return None

    def destroy_session(self, session_id: str = None) -> bool:
        """
        セッション破棄

        Args:
            session_id: セッションID（Noneの場合はsession_stateから取得）

        Returns:
            bool: 破棄成功の場合True
        """
        try:
            # session_stateからセッション情報を削除
            if "auth_session" in st.session_state:
                del st.session_state["auth_session"]
            if "user_info" in st.session_state:
                del st.session_state["user_info"]
            if "is_authenticated" in st.session_state:
                del st.session_state["is_authenticated"]

            return True

        except Exception:
            return False

    def refresh_session(self) -> bool:
        """
        セッション更新

        Returns:
            bool: 更新成功の場合True
        """
        try:
            user_info = self.get_user_info()
            if user_info:
                self.create_session(user_info)
                return True
            return False

        except Exception:
            return False

    def is_authenticated(self) -> bool:
        """
        認証状態チェック

        Returns:
            bool: 認証済みの場合True
        """
        return self.validate_session()

    def get_session_timeout(self) -> int:
        """
        セッションタイムアウト時間を取得

        Returns:
            int: タイムアウト時間（秒）
        """
        return self.session_timeout


def get_session_manager() -> SessionManager:
    """
    セッションマネージャーのインスタンスを取得

    Returns:
        SessionManager: セッションマネージャー
    """
    timeout = int(os.getenv("SESSION_TIMEOUT", "3600"))
    return SessionManager(timeout)