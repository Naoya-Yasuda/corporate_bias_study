"""
Google OAuth認証モジュール

Google OAuth 2.0を使用した認証機能を提供します。
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from authlib.integrations.requests_client import OAuth2Session
from .domain_validator import DomainValidator
from .session_manager import SessionManager, UserInfo

# ロガー設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AuthResult:
    """認証結果クラス"""

    def __init__(self, success: bool, user_info: Optional[UserInfo] = None, error: str = ""):
        """
        初期化

        Args:
            success: 認証成功フラグ
            user_info: ユーザー情報
            error: エラーメッセージ
        """
        self.success = success
        self.user_info = user_info
        self.error = error


class GoogleOAuthManager:
    """Google OAuth認証管理クラス"""

    def __init__(self):
        """初期化"""
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        # デバッグモード
        self.debug_mode = os.getenv("AUTH_DEBUG_MODE", "false").lower() == "true"

        # デバッグ情報（常に出力）
        logger.info(f"OAuth初期化: client_id={self.client_id[:10] if self.client_id else 'None'}..., "
                   f"client_secret={'***' if self.client_secret else 'None'}, "
                   f"redirect_uri={self.redirect_uri}")

        # 環境変数の検証
        if not self.redirect_uri:
            logger.error("GOOGLE_REDIRECT_URIが設定されていません")
        if not self.client_id:
            logger.error("GOOGLE_CLIENT_IDが設定されていません")
        if not self.client_secret:
            logger.error("GOOGLE_CLIENT_SECRETが設定されていません")

        # 許可ドメインの設定
        allowed_domains = os.getenv("ALLOWED_DOMAINS", "cyber-u.ac.jp").split(",")
        allowed_emails = os.getenv("ALLOWED_EMAILS", "").split(",") if os.getenv("ALLOWED_EMAILS") else []
        # 空文字列を除去
        allowed_emails = [email.strip() for email in allowed_emails if email.strip()]
        self.domain_validator = DomainValidator(allowed_domains, allowed_emails)

        # セッションマネージャー
        self.session_manager = SessionManager()

        # OAuth設定
        self.authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        self.scope = ["openid", "email", "profile"]

    def initialize_oauth(self) -> bool:
        """
        OAuthクライアントの初期化

        Returns:
            bool: 初期化成功の場合True
        """
        try:
            if not all([self.client_id, self.client_secret, self.redirect_uri]):
                logger.error("OAuth設定が不完全です")
                return False

            return True

        except Exception as e:
            logger.error(f"OAuth初期化エラー: {e}")
            return False

    def get_auth_url(self) -> str:
        """
        認証URLの生成

        Returns:
            str: 認証URL
        """
        try:
            oauth = OAuth2Session(
                client_id=self.client_id,
                redirect_uri=self.redirect_uri,
                scope=self.scope
            )

            auth_url, state = oauth.create_authorization_url(self.authorize_url)

            if self.debug_mode:
                logger.info(f"認証URL生成: {auth_url}")

            return auth_url

        except Exception as e:
            logger.error(f"認証URL生成エラー: {e}")
            return ""

    def handle_callback(self, code: str) -> AuthResult:
        """
        認証コールバックの処理

        Args:
            code: 認証コード

        Returns:
            AuthResult: 認証結果
        """
        # 関数開始時のデバッグ情報
        logger.info("=== handle_callback関数開始 ===")
        logger.info(f"引数code: {code}")
        logger.info(f"引数code type: {type(code)}")
        logger.info(f"引数code is None: {code is None}")

        try:
            if not code:
                logger.error("認証コードがありません")
                return AuthResult(False, error="認証コードがありません")

            # 詳細なデバッグ情報
            logger.info("=== コールバック処理デバッグ ===")
            logger.info(f"code: {code[:10]}...")
            logger.info(f"self.redirect_uri: {self.redirect_uri}")
            logger.info(f"self.redirect_uri type: {type(self.redirect_uri)}")
            logger.info(f"self.redirect_uri is None: {self.redirect_uri is None}")
            logger.info(f"self.client_id: {self.client_id[:10] if self.client_id else 'None'}...")
            logger.info(f"self.client_secret: {'***' if self.client_secret else 'None'}")
            logger.info(f"self.debug_mode: {self.debug_mode}")

            # 環境変数を直接確認
            import os
            logger.info(f"os.getenv('GOOGLE_REDIRECT_URI'): {os.getenv('GOOGLE_REDIRECT_URI')}")
            logger.info(f"os.getenv('GOOGLE_REDIRECT_URI') type: {type(os.getenv('GOOGLE_REDIRECT_URI'))}")

            # リダイレクトURIの検証
            if not self.redirect_uri:
                logger.error("リダイレクトURIが設定されていません")
                return AuthResult(False, error="認証設定エラー: リダイレクトURIが設定されていません")

            # OAuth2Session作成前の確認
            logger.info(f"OAuth2Session作成前: redirect_uri={self.redirect_uri}")
            logger.info(f"OAuth2Session作成前: redirect_uri type={type(self.redirect_uri)}")

            # トークン取得
            try:
                oauth = OAuth2Session(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri=self.redirect_uri
                )
                logger.info("OAuth2Session作成成功")
            except Exception as e:
                logger.error(f"OAuth2Session作成エラー: {e}")
                return AuthResult(False, error=f"OAuth2Session作成エラー: {e}")

            # fetch_token前の確認
            logger.info(f"fetch_token呼び出し前: redirect_uri={self.redirect_uri}")
            logger.info(f"fetch_token呼び出し前: code={code}")

            # redirect_uriがNoneの場合はエラー
            if not self.redirect_uri:
                logger.error("fetch_token呼び出し前: redirect_uriがNone")
                return AuthResult(False, error="認証設定エラー: リダイレクトURIが設定されていません")

            # 正しいfetch_token呼び出し
            try:
                # authlibのOAuth2Session.fetch_tokenの正しい使い方
                token = oauth.fetch_token(
                    url=self.token_url,
                    code=code,
                    redirect_uri=self.redirect_uri
                )
                logger.info("fetch_token呼び出し成功")
            except Exception as e:
                logger.error(f"fetch_token呼び出しエラー: {e}")
                logger.error(f"code: {code}")
                logger.error(f"redirect_uri: {self.redirect_uri}")
                return AuthResult(False, error=f"トークン取得エラー: {e}")

            if not token:
                return AuthResult(False, error="トークンの取得に失敗しました")

            # ユーザー情報取得
            user_info = self._get_user_info(token.get("access_token"))
            if not user_info:
                return AuthResult(False, error="ユーザー情報の取得に失敗しました")

            # ドメイン制限チェック
            if not self.domain_validator.validate_email(user_info.email):
                return AuthResult(
                    False,
                    user_info=user_info,
                    error=f"ドメイン制限: {user_info.domain}は許可されていません"
                )

            # セッション作成
            session_id = self.session_manager.create_session(user_info)
            if not session_id:
                return AuthResult(False, error="セッション作成に失敗しました")

            if self.debug_mode:
                logger.info(f"認証成功: {user_info.email}")

            return AuthResult(True, user_info=user_info)

        except Exception as e:
            logger.error(f"コールバック処理エラー: {e}")
            return AuthResult(False, error=f"認証処理中にエラーが発生しました: {str(e)}")

    def _get_user_info(self, access_token: str) -> Optional[UserInfo]:
        """
        ユーザー情報の取得

        Args:
            access_token: アクセストークン

        Returns:
            Optional[UserInfo]: ユーザー情報
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(self.userinfo_url, headers=headers)

            if response.status_code != 200:
                logger.error(f"ユーザー情報取得エラー: {response.status_code}")
                return None

            user_data = response.json()

            user_info = UserInfo(
                email=user_data.get("email", ""),
                name=user_data.get("name", ""),
                picture=user_data.get("picture", "")
            )

            return user_info

        except Exception as e:
            logger.error(f"ユーザー情報取得エラー: {e}")
            return None

    def validate_token(self, token: str) -> bool:
        """
        トークンの検証

        Args:
            token: 検証するトークン

        Returns:
            bool: 有効なトークンの場合True
        """
        try:
            # トークン情報の取得
            token_info_url = "https://oauth2.googleapis.com/tokeninfo"
            params = {"access_token": token}
            response = requests.get(token_info_url, params=params)

            if response.status_code != 200:
                return False

            token_info = response.json()

            # 有効期限チェック
            if "expires_in" in token_info:
                expires_in = token_info["expires_in"]
                if expires_in <= 0:
                    return False

            return True

        except Exception as e:
            logger.error(f"トークン検証エラー: {e}")
            return False

    def logout(self) -> bool:
        """
        ログアウト処理

        Returns:
            bool: ログアウト成功の場合True
        """
        try:
            return self.session_manager.destroy_session()

        except Exception as e:
            logger.error(f"ログアウトエラー: {e}")
            return False

    def is_authenticated(self) -> bool:
        """
        認証状態チェック

        Returns:
            bool: 認証済みの場合True
        """
        return self.session_manager.is_authenticated()

    def get_user_info(self) -> Optional[UserInfo]:
        """
        現在のユーザー情報取得

        Returns:
            Optional[UserInfo]: ユーザー情報
        """
        return self.session_manager.get_user_info()

    def get_allowed_domains(self) -> list:
        """
        許可されているドメインのリストを取得

        Returns:
            list: 許可ドメインのリスト
        """
        return self.domain_validator.get_allowed_domains()

    def get_allowed_emails(self) -> list:
        """
        許可されているメールアドレスのリストを取得

        Returns:
            list: 許可メールアドレスのリスト
        """
        return self.domain_validator.get_allowed_emails()


def get_oauth_manager() -> GoogleOAuthManager:
    """
    OAuthマネージャーのインスタンスを取得

    Returns:
        GoogleOAuthManager: OAuthマネージャー
    """
    return GoogleOAuthManager()