import streamlit as st
from streamlit_oauth import OAuth2Component
import os
import logging

# ログ設定
logger = logging.getLogger(__name__)

def google_oauth_login(allowed_domains=None, debug_mode=False):
    """
    Google OAuth認証 + ドメイン制限機能

    Parameters:
    -----------
    allowed_domains : list, optional
        許可するドメインのリスト。デフォルトは["cyber-u.ac.jp"]
    debug_mode : bool, optional
        デバッグモード。Trueの場合、詳細なログを出力

    Returns:
    --------
    tuple : (認証成功フラグ, メールアドレス)
    """
    # デフォルトの許可ドメイン
    if allowed_domains is None:
        allowed_domains = ["cyber-u.ac.jp"]

    # 環境変数から認証情報を取得
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

    # 認証情報の検証
    if not client_id or not client_secret:
        st.error("Google OAuth認証情報が設定されていません。")
        st.info("環境変数 GOOGLE_CLIENT_ID と GOOGLE_CLIENT_SECRET を設定してください。")
        return False, None

    if debug_mode:
        logger.info(f"許可ドメイン: {allowed_domains}")
        logger.info(f"リダイレクトURI: {redirect_uri}")

    # OAuth2コンポーネントの初期化
    oauth2 = OAuth2Component(
        client_id=client_id,
        client_secret=client_secret,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        revoke_endpoint="https://oauth2.googleapis.com/revoke",
        redirect_uri=redirect_uri,
        scope="openid email profile"
    )

    # 認証ボタンの表示
    result = oauth2.authorize_button("Googleでログイン")

    if result and "email" in result:
        email = result["email"]

        if debug_mode:
            logger.info(f"認証成功 - メールアドレス: {email}")

        # ドメイン制限チェック
        user_domain = email.split("@")[-1] if "@" in email else ""

        if user_domain in allowed_domains:
            st.success(f"ログイン成功: {email}")
            if debug_mode:
                logger.info(f"ドメイン制限チェック通過: {user_domain}")
            return True, email
        else:
            st.error(f"アクセスが拒否されました。")
            st.warning(f"許可されているドメイン: {', '.join(allowed_domains)}")
            st.info(f"あなたのドメイン: {user_domain}")

            if debug_mode:
                logger.warning(f"ドメイン制限チェック失敗: {user_domain} (許可: {allowed_domains})")
            return False, None
    else:
        if debug_mode:
            logger.info("認証が完了していません")
        st.info("Googleアカウントでログインしてください。")
        return False, None

def is_domain_allowed(email, allowed_domains=None):
    """
    メールアドレスのドメインが許可されているかチェック

    Parameters:
    -----------
    email : str
        チェックするメールアドレス
    allowed_domains : list, optional
        許可するドメインのリスト

    Returns:
    --------
    bool : 許可されているかどうか
    """
    if allowed_domains is None:
        allowed_domains = ["cyber-u.ac.jp"]

    if not email or "@" not in email:
        return False

    user_domain = email.split("@")[-1].lower()
    return user_domain in [domain.lower() for domain in allowed_domains]

def get_allowed_domains():
    """
    環境変数から許可ドメインを取得

    Returns:
    --------
    list : 許可ドメインのリスト
    """
    domains_str = os.getenv("ALLOWED_DOMAINS", "cyber-u.ac.jp")
    return [domain.strip() for domain in domains_str.split(",")]