"""
認証UIコンポーネント

Google OAuth認証のUIを提供します。
"""

import streamlit as st
import os
from typing import Optional
from streamlit_oauth import OAuth2Component


def render_auth_page():
    """認証ページのレンダリング"""

    # ログイン画面のレイアウトを調整
    st.markdown("""
    <style>
    .main .block-container {
        max-width: 600px;
        padding-left: 2rem;
        padding-right: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # 中央揃えでタイトルを表示
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("企業バイアス分析ダッシュボード")
        st.markdown("---")

    # 技術記事通りのOAuth2Component実装
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

    if not all([client_id, client_secret, redirect_uri]):
        with col2:
            st.error("認証設定が正しく設定されていません。管理者にお問い合わせください。")
        return

    oauth2 = OAuth2Component(
        client_id=client_id,
        client_secret=client_secret,
        authorize_endpoint="https://accounts.google.com/o/oauth2/v2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
        revoke_token_endpoint="https://oauth2.googleapis.com/revoke"
    )

    # 中央揃えでログインボタンを表示
    with col2:
        result = oauth2.authorize_button(
            name="Googleでログイン",
            redirect_uri=redirect_uri,
            scope="openid email profile",
            use_container_width=True
        )

    if result and "token" in result:
        # トークンが取得できた場合、ユーザー情報を取得
        token = result["token"]

        # Google User Info APIを使用してユーザー情報を取得
        try:
            import requests
            userinfo_response = requests.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"}
            )

            if userinfo_response.status_code == 200:
                user_info = userinfo_response.json()
                email = user_info.get("email", "")

                if email.endswith("@cyber-u.ac.jp"):
                    # 認証成功：セッション状態にユーザー情報を保存
                    st.session_state.authenticated = True
                    st.session_state.user_info = user_info
                    st.session_state.token = token

                    # 認証成功メッセージを表示
                    with col2:
                        st.success(f"ログイン成功: {email}")
                        st.info("認証が完了しました。ダッシュボードの機能をご利用ください。")

                    # ページを再読み込みしてダッシュボードを表示
                    st.rerun()
                else:
                    with col2:
                        st.error("cyber-u.ac.jpドメインのメールアドレスでログインしてください。")
            else:
                with col2:
                    st.error(f"ユーザー情報取得エラー: {userinfo_response.status_code}")
        except Exception as e:
            with col2:
                st.error(f"ユーザー情報取得エラー: {e}")
    elif result:
        with col2:
            st.write("**デバッグ: resultはあるがtokenがない**", result)
            st.info("認証が完了しましたが、トークンの取得に失敗しました。")
    else:
        with col2:
            st.info("Googleアカウントでログインしてください。")


def show_dashboard_header(user_info: dict):
    """ダッシュボードヘッダー表示（プロフィール情報付き）"""

    # サイドバーの一番上の空白を最小限にするCSS
    st.markdown("""
    <style>
    .css-1d391kg {
        padding-top: 0.5rem !important;
    }
    .css-1d391kg > div:first-child {
        padding-top: 0.25rem !important;
    }
    .st-emotion-cache-595tnf {
        height: 1.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # サイドバーの一番上にプロフィール情報を表示
    with st.sidebar:
        # 1行目：プロフィール画像と名前を横並びで表示
        col1, col2 = st.columns([1, 2])

        with col1:
            # プロフィール画像を表示（小さく）
            if user_info.get("picture"):
                st.image(user_info["picture"], width=30)
            else:
                st.markdown("👤")

        with col2:
            # 名前を表示（小さく）
            if user_info.get("name"):
                st.markdown(f"**{user_info['name']}**", help="ユーザー名")

        # 2行目：ログアウトボタンを名前の下に表示
        if st.button("Logout", type="secondary", key="logout_btn", use_container_width=True):
            # セッション状態をクリア
            for key in ['authenticated', 'user_info', 'token']:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("ログアウトしました")
            st.rerun()