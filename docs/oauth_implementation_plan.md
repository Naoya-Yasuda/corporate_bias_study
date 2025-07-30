# Google OAuth SSO 実装計画

## 概要

Google OAuth SSO認証システムの段階的実装計画です。.envファイルによる設定管理で、シンプルで保守性の高い認証システムを構築します。

## 実装フェーズ

### Phase 1: 基本認証機能（1-2週間）

#### 1.1 環境設定
- [ ] 必要なライブラリの追加（requirements.txt）
  - `authlib>=1.2.0`
  - `requests-oauthlib>=1.3.0`
  - `PyJWT>=2.8.0`
  - `cryptography>=41.0.0`
- [ ] .envファイルの設定
  - Google OAuth認証情報
  - ドメイン制限設定
  - セッション管理設定

#### 1.2 認証モジュール実装
- [ ] `src/auth/google_oauth.py` - メイン認証ロジック
- [ ] `src/auth/session_manager.py` - セッション管理
- [ ] `src/auth/domain_validator.py` - ドメイン制限チェック
- [ ] `src/utils/auth_utils.py` - 認証関連ユーティリティ

#### 1.3 基本認証フロー
- [ ] Google OAuth認証URL生成
- [ ] コールバック処理
- [ ] トークン取得・検証
- [ ] ドメイン制限チェック
- [ ] セッション作成

### Phase 2: UI/UX改善（1週間）

#### 2.1 認証UI実装
- [ ] `src/components/auth_ui.py` - 認証UIコンポーネント
- [ ] ログイン画面デザイン
- [ ] エラー表示画面
- [ ] ローディング表示

#### 2.2 ユーザー体験改善
- [ ] レスポンシブ対応
- [ ] アクセシビリティ対応
- [ ] 多言語対応（日本語・英語）
- [ ] ヘルプ・FAQ表示

### Phase 3: セキュリティ強化（1週間）

#### 3.1 セキュリティ機能
- [ ] トークン暗号化
- [ ] CSRF保護
- [ ] レート制限
- [ ] セッションタイムアウト

#### 3.2 監査ログ
- [ ] 認証イベントログ
- [ ] エラーログ
- [ ] セキュリティイベントログ
- [ ] ログローテーション

### Phase 4: 運用機能（1週間）

#### 4.1 管理者機能
- [ ] 管理者ダッシュボード
- [ ] ユーザー管理
- [ ] 認証統計表示
- [ ] 設定変更機能

#### 4.2 監視・アラート
- [ ] 認証成功率監視
- [ ] エラー率監視
- [ ] アラート設定
- [ ] 障害時の自動復旧

## 詳細実装ステップ

### ステップ1: 環境準備

#### 1.1 ライブラリ追加
```bash
# requirements.txtに追加
authlib>=1.2.0
requests-oauthlib>=1.3.0
PyJWT>=2.8.0
cryptography>=41.0.0
```

#### 1.2 環境変数設定
```bash
# .envファイル
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8501
ALLOWED_DOMAINS=cyber-u.ac.jp
AUTH_DEBUG_MODE=false
SESSION_TIMEOUT=3600
JWT_SECRET_KEY=your_jwt_secret
ENCRYPTION_KEY=your_encryption_key
```

### ステップ2: 認証モジュール実装

#### 2.1 GoogleOAuthManager
```python
# src/auth/google_oauth.py
class GoogleOAuthManager:
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        self.allowed_domains = os.getenv("ALLOWED_DOMAINS", "cyber-u.ac.jp").split(",")
```

#### 2.2 SessionManager
```python
# src/auth/session_manager.py
class SessionManager:
    def create_session(self, user_info: UserInfo) -> str:
        # JWTトークン生成
        # セッション情報保存
```

#### 2.3 DomainValidator
```python
# src/auth/domain_validator.py
class DomainValidator:
    def validate_email(self, email: str) -> bool:
        # ドメイン制限チェック
```

### ステップ3: UI統合

#### 3.1 app.py統合
```python
# app.py
from src.auth.google_oauth import GoogleOAuthManager
from src.components.auth_ui import render_auth_page

# 認証チェック
if not is_authenticated():
    render_auth_page()
    st.stop()

# メインアプリケーション
```

#### 3.2 認証UI
```python
# src/components/auth_ui.py
def render_auth_page():
    st.title("企業バイアス分析ダッシュボード")
    show_login_form()
```

### ステップ4: テスト実装

#### 4.1 単体テスト
```python
# tests/test_auth.py
def test_google_oauth_manager():
    # OAuthマネージャーのテスト

def test_domain_validator():
    # ドメイン制限のテスト

def test_session_manager():
    # セッション管理のテスト
```

#### 4.2 統合テスト
```python
# tests/test_integration.py
def test_oauth_flow():
    # 認証フロー全体のテスト
```

## 実装チェックリスト

### 基本機能
- [ ] Google OAuth認証
- [ ] ドメイン制限（@cyber-u.ac.jp）
- [ ] セッション管理
- [ ] エラーハンドリング

### セキュリティ
- [ ] トークン暗号化
- [ ] CSRF保護
- [ ] レート制限
- [ ] セッションタイムアウト

### UI/UX
- [ ] レスポンシブデザイン
- [ ] アクセシビリティ
- [ ] エラー表示
- [ ] ローディング表示

### 運用
- [ ] ログ出力
- [ ] 監視機能
- [ ] アラート設定
- [ ] バックアップ

## リスク管理

### 技術リスク
- **OAuth設定エラー**: Google Cloud Consoleでの設定確認
- **ライブラリ互換性**: バージョン固定とテスト
- **セキュリティ脆弱性**: 定期的なセキュリティアップデート

### 運用リスク
- **設定漏れ**: 環境変数チェック機能
- **ログ容量**: ログローテーション設定
- **障害対応**: 障害時の代替認証

### 対策
- 段階的実装によるリスク分散
- 各フェーズでの動作確認
- セキュリティテストの実施
- 監視・アラートの設定

## 成功指標

### 技術指標
- 認証成功率: 99%以上
- レスポンス時間: 3秒以内
- エラー率: 1%以下

### 運用指標
- ユーザー満足度: 4.5/5.0以上
- サポート問い合わせ: 月5件以下
- セキュリティインシデント: 0件

### 品質指標
- テストカバレッジ: 90%以上
- コードレビュー通過率: 100%
- セキュリティスキャン: 合格

## 次のステップ

1. **Phase 1開始**: 基本認証機能の実装
2. **環境準備**: ライブラリ追加と環境変数設定
3. **開発環境**: ローカルでの動作確認
4. **段階的テスト**: 各フェーズでの動作確認
5. **本番展開**: 監視機能付きでの段階的ロールアウト