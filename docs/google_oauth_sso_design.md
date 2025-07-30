# Google OAuth SSO 設計書

## 概要

企業バイアス分析ダッシュボードにGoogle OAuth 2.0によるSSO（Single Sign-On）認証機能を実装する設計書です。

## 設計方針

### 1. アーキテクチャ
- **認証コンポーネント分離**: app.pyとは独立した認証モジュールとして実装
- **ドメイン制限**: `@cyber-u.ac.jp`ドメイン限定アクセス
- **セッション管理**: Streamlitのsession_stateを活用
- **エラーハンドリング**: 包括的なエラー処理とユーザーフィードバック

### 2. 技術スタック
- **認証ライブラリ**: `authlib` + `requests-oauthlib`
- **セッション管理**: Streamlit session_state
- **設定管理**: 環境変数（.envファイル）
- **ログ管理**: Python logging

## 詳細設計

### 1. ディレクトリ構造

```
src/
├── auth/
│   ├── __init__.py
│   ├── google_oauth.py          # メイン認証ロジック
│   ├── session_manager.py       # セッション管理
│   └── domain_validator.py      # ドメイン制限チェック
├── components/
│   └── auth_ui.py              # 認証UIコンポーネント
└── utils/
    └── auth_utils.py           # 認証関連ユーティリティ
```

### 2. クラス設計

#### 2.1 GoogleOAuthManager
```python
class GoogleOAuthManager:
    """Google OAuth認証管理クラス"""

    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        self.allowed_domains = os.getenv("ALLOWED_DOMAINS", "cyber-u.ac.jp").split(",")

    def initialize_oauth(self) -> bool:
        """OAuthクライアントの初期化"""

    def get_auth_url(self) -> str:
        """認証URLの生成"""

    def handle_callback(self, code: str) -> AuthResult:
        """認証コールバックの処理"""

    def validate_token(self, token: str) -> bool:
        """トークンの検証"""
```

#### 2.2 SessionManager
```python
class SessionManager:
    """セッション管理クラス"""

    def create_session(self, user_info: UserInfo) -> str:
        """セッション作成"""

    def validate_session(self, session_id: str) -> bool:
        """セッション検証"""

    def get_user_info(self, session_id: str) -> Optional[UserInfo]:
        """ユーザー情報取得"""

    def destroy_session(self, session_id: str) -> bool:
        """セッション破棄"""
```

#### 2.3 DomainValidator
```python
class DomainValidator:
    """ドメイン制限チェッククラス"""

    def __init__(self, allowed_domains: List[str]):
        self.allowed_domains = allowed_domains

    def validate_email(self, email: str) -> bool:
        """メールアドレスのドメイン検証"""

    def get_user_domain(self, email: str) -> str:
        """ユーザードメインの抽出"""
```

### 3. 認証フロー

#### 3.1 基本認証フロー
```
1. ユーザーがアプリにアクセス
2. セッション確認
   ├─ 有効なセッション → ダッシュボード表示
   └─ 無効なセッション → 認証画面表示
3. Google OAuth認証
   ├─ 認証URL生成
   ├─ ユーザーがGoogleでログイン
   ├─ コールバック処理
   └─ トークン取得・検証
4. ドメイン制限チェック
   ├─ 許可ドメイン → セッション作成・ダッシュボード表示
   └─ 不許可ドメイン → エラー表示
```

#### 3.2 エラーハンドリングフロー
```
認証エラー発生時:
1. エラータイプ判定
   ├─ ネットワークエラー → 再試行ボタン表示
   ├─ 認証情報エラー → 管理者連絡案内
   ├─ ドメイン制限エラー → 許可ドメイン案内
   └─ トークン期限切れ → 自動リフレッシュ
2. ユーザーフレンドリーなエラーメッセージ表示
3. ログ出力（デバッグモード時）
```

### 4. 設定管理

#### 4.1 環境変数（.envファイル）
```bash
# Google OAuth設定
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8501

# 認証設定
ALLOWED_DOMAINS=cyber-u.ac.jp
AUTH_DEBUG_MODE=false
SESSION_TIMEOUT=3600

# セキュリティ設定
JWT_SECRET_KEY=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key
```

#### 4.2 設定検証
```python
def validate_auth_config() -> bool:
    """認証設定の検証"""
    required_vars = [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_REDIRECT_URI"
    ]

    for var in required_vars:
        if not os.getenv(var):
            st.error(f"必要な環境変数 {var} が設定されていません")
            return False

    return True
```

### 5. UI設計

#### 5.1 認証画面
```python
def render_auth_page():
    """認証ページのレンダリング"""

    st.title("企業バイアス分析ダッシュボード")
    st.markdown("---")

    # ログイン状態確認
    if is_authenticated():
        show_dashboard()
    else:
        show_login_form()
```

#### 5.2 ログインフォーム
```python
def show_login_form():
    """ログインフォーム表示"""

    st.header("ログイン")
    st.info("サイバー大学のGoogleアカウントでログインしてください。")

    # Google OAuthボタン
    if st.button("Googleでログイン", type="primary"):
        initiate_oauth_flow()

    # ヘルプ情報
    with st.expander("ログインについて"):
        st.write("""
        - サイバー大学のGoogleアカウント（@cyber-u.ac.jp）が必要です
        - 初回ログイン時はGoogleの認証画面が表示されます
        - セキュリティのため、一定時間後に自動ログアウトされます
        """)
```

#### 5.3 エラー表示
```python
def show_error_page(error_type: str, error_details: dict):
    """エラーページ表示"""

    st.error("認証エラーが発生しました")

    if error_type == "domain_restricted":
        st.warning(f"ドメイン制限: {error_details['user_domain']}")
        st.info(f"許可されているドメイン: {', '.join(error_details['allowed_domains'])}")

    elif error_type == "authentication_failed":
        st.warning("Google認証に失敗しました")
        st.button("再試行", on_click=retry_authentication)

    # 管理者連絡先
    st.info("問題が解決しない場合は管理者にお問い合わせください。")
```

### 6. セキュリティ考慮事項

#### 6.1 トークン管理
- **アクセストークン**: 短期間（1時間）で期限切れ
- **リフレッシュトークン**: 長期保存、自動更新
- **JWT**: セッション管理用、署名付き

#### 6.2 データ保護
- **暗号化**: 機密情報の暗号化保存
- **HTTPS**: 全通信の暗号化
- **CSRF保護**: クロスサイトリクエストフォージェリ対策

#### 6.3 監査ログ
```python
def log_auth_event(event_type: str, user_info: dict, success: bool):
    """認証イベントのログ出力"""

    log_data = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "user_email": user_info.get("email"),
        "user_domain": user_info.get("domain"),
        "success": success,
        "ip_address": get_client_ip(),
        "user_agent": get_user_agent()
    }

    logger.info(f"Auth event: {log_data}")
```

### 7. 実装計画

#### Phase 1: 基本認証機能
1. Google OAuth設定
2. 基本的な認証フロー実装
3. ドメイン制限機能
4. セッション管理

#### Phase 2: UI/UX改善
1. 認証画面のデザイン
2. エラーハンドリング
3. ローディング表示
4. レスポンシブ対応

#### Phase 3: セキュリティ強化
1. トークン暗号化
2. 監査ログ
3. レート制限
4. セキュリティテスト

#### Phase 4: 運用機能
1. 管理者ダッシュボード
2. ユーザー管理
3. 統計・レポート
4. 監視・アラート

### 8. テスト計画

#### 8.1 単体テスト
- 認証ロジック
- ドメイン制限チェック
- セッション管理
- エラーハンドリング

#### 8.2 統合テスト
- OAuthフロー全体
- セッション継続性
- エラーシナリオ

#### 8.3 セキュリティテスト
- トークン漏洩
- CSRF攻撃
- セッションハイジャック

### 9. 運用・保守

#### 9.1 監視項目
- 認証成功率
- エラー率
- レスポンス時間
- セッション数

#### 9.2 アラート設定
- 認証エラー率上昇
- セッション異常
- セキュリティイベント

#### 9.3 バックアップ・復旧
- 設定ファイルバックアップ
- セッションデータ復旧
- 障害時の代替認証

## 結論

この設計により、シンプルで保守性の高いGoogle OAuth SSO認証システムを実装できます。.envファイルによる設定管理により、設定の一元化と運用の簡素化を実現します。