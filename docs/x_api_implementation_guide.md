# X API投稿実装ガイド

## 1. 概要

### 1.1 目的
企業優遇バイアス分析結果の自動SNS投稿機能において、X（旧Twitter）APIを使用した投稿実装の調査結果と実装方法をまとめる。

### 1.2 対象機能
- X API認証・設定
- テキスト投稿機能
- 画像投稿機能
- 投稿制御・管理機能

## 2. X API認証情報の取得

### 2.1 必要な認証情報

#### 2.1.1 API v2（推奨）
```python
# 必要な認証情報
TWITTER_API_KEY = "your_api_key"                    # API Key
TWITTER_API_SECRET = "your_api_secret"              # API Secret
TWITTER_BEARER_TOKEN = "your_bearer_token"          # Bearer Token
TWITTER_ACCESS_TOKEN = "your_access_token"          # Access Token
TWITTER_ACCESS_TOKEN_SECRET = "your_access_token_secret"  # Access Token Secret
```

#### 2.1.2 認証情報の取得手順

1. **X Developer Portalでのアプリケーション作成**
   - https://developer.twitter.com/ にアクセス
   - Xアカウントでログイン
   - "Create App"でアプリケーションを作成

2. **アプリケーション設定**
   - App name: "Corporate Bias Monitor"
   - App description: "企業優遇バイアス分析結果の自動投稿"
   - Use case: "Making a bot"

3. **権限設定**
   - Read and Write permissions を有効化
   - OAuth 2.0 を有効化

4. **認証情報の取得**
   - API Key と API Secret を取得
   - Bearer Token を生成
   - Access Token と Access Token Secret を生成

### 2.2 環境変数設定

#### 2.2.1 .envファイルへの追加
```bash
# X API認証情報
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret

# X投稿設定
TWITTER_POSTING_ENABLED=true
TWITTER_MAX_DAILY_POSTS=10
TWITTER_DUPLICATE_PREVENTION_HOURS=24
```

## 3. X API実装方法

### 3.1 使用ライブラリ

#### 3.1.1 推奨ライブラリ
```python
# 主要ライブラリ
tweepy==4.14.0          # X API Pythonライブラリ
python-dotenv==1.0.0    # 環境変数管理
Pillow==10.0.0          # 画像処理
requests==2.31.0        # HTTP通信
```

### 3.2 X APIクライアント実装

#### 3.2.1 基本クライアントクラス
```python
import tweepy
import os
from typing import Dict, Optional, List
from dotenv import load_dotenv
import logging

class TwitterClient:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

        self.client = None
        self.api = None
        self._authenticate()

    def _authenticate(self):
        """X API認証"""
        try:
            # OAuth 1.0a認証（投稿用）
            auth = tweepy.OAuthHandler(self.api_key, self.api_secret)
            auth.set_access_token(self.access_token, self.access_token_secret)
            self.api = tweepy.API(auth)

            # OAuth 2.0認証（読み取り用）
            self.client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )

            logging.info("X API認証成功")
        except Exception as e:
            logging.error(f"X API認証失敗: {e}")
            raise
```

#### 3.2.2 投稿機能実装
```python
class TwitterPoster:
    def __init__(self, twitter_client: TwitterClient):
        self.client = twitter_client
        self.max_daily_posts = int(os.getenv('TWITTER_MAX_DAILY_POSTS', 10))
        self.duplicate_prevention_hours = int(os.getenv('TWITTER_DUPLICATE_PREVENTION_HOURS', 24))

    def post_text(self, text: str) -> Dict:
        """テキスト投稿"""
        try:
            # 文字数制限チェック（280文字）
            if len(text) > 280:
                text = text[:277] + "..."

            # 投稿実行
            response = self.client.api.update_status(text)

            return {
                "success": True,
                "tweet_id": response.id,
                "text": text,
                "created_at": response.created_at
            }
        except Exception as e:
            logging.error(f"テキスト投稿失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def post_with_image(self, text: str, image_path: str) -> Dict:
        """画像付き投稿"""
        try:
            # 文字数制限チェック
            if len(text) > 280:
                text = text[:277] + "..."

            # 画像アップロード
            media = self.client.api.media_upload(image_path)

            # 画像付き投稿
            response = self.client.api.update_status(
                status=text,
                media_ids=[media.media_id]
            )

            return {
                "success": True,
                "tweet_id": response.id,
                "text": text,
                "image_path": image_path,
                "created_at": response.created_at
            }
        except Exception as e:
            logging.error(f"画像付き投稿失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }
```

### 3.3 投稿制御機能

#### 3.3.1 投稿制御クラス
```python
from datetime import datetime, timedelta
import sqlite3

class TwitterPostingController:
    def __init__(self, db_path: str = "data/twitter_posts.db"):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """投稿履歴データベース初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS twitter_posts (
                id INTEGER PRIMARY KEY,
                tweet_id VARCHAR(50),
                content TEXT,
                image_path VARCHAR(255),
                entity_id VARCHAR(100),
                change_type VARCHAR(30),
                posted_at TIMESTAMP,
                engagement_metrics JSON,
                status VARCHAR(20)
            )
        ''')

        conn.commit()
        conn.close()

    def check_daily_limit(self) -> bool:
        """日次投稿制限チェック"""
        today = datetime.now().date()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM twitter_posts
            WHERE DATE(posted_at) = ?
        ''', (today,))

        count = cursor.fetchone()[0]
        conn.close()

        return count < self.max_daily_posts

    def check_duplicate_post(self, entity_id: str, change_type: str, hours: int = 24) -> bool:
        """重複投稿チェック"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) FROM twitter_posts
            WHERE entity_id = ? AND change_type = ? AND posted_at > ?
        ''', (entity_id, change_type, cutoff_time))

        count = cursor.fetchone()[0]
        conn.close()

        return count == 0
```

### 3.4 投稿テンプレート生成

#### 3.4.1 テンプレート生成クラス
```python
class TwitterContentGenerator:
    def __init__(self):
        self.base_url = "https://your-domain.com/analysis"  # 分析結果URL

    def generate_sentiment_change_post(self, entity_name: str, change_rate: float,
                                     change_type: str, details: str) -> str:
        """感情スコア変化投稿テンプレート"""
        return f"""🚨【企業優遇バイアス変化検知】

📊 検知内容: 感情スコア{change_type}
🏢 対象企業: {entity_name}
📈 変化率: {change_rate:.1f}%
📋 詳細: {details}

🔍 分析詳細: {self.base_url}
#企業優遇バイアス #AI分析 #透明性"""

    def generate_ranking_change_post(self, entity_name: str, old_rank: int,
                                   new_rank: int, platform: str) -> str:
        """ランキング変化投稿テンプレート"""
        rank_change = old_rank - new_rank
        direction = "上昇" if rank_change > 0 else "下降"

        return f"""📈【検索ランキング変化検知】

🏢 対象企業: {entity_name}
📊 プラットフォーム: {platform}
📈 順位変化: {old_rank}位 → {new_rank}位 ({direction})
📋 詳細: 検索結果での露出度が変化

🔍 分析詳細: {self.base_url}
#企業優遇バイアス #検索分析 #ランキング"""
```

## 4. 統合実装

### 4.1 メイン投稿マネージャー
```python
class TwitterPostingManager:
    def __init__(self):
        self.twitter_client = TwitterClient()
        self.poster = TwitterPoster(self.twitter_client)
        self.controller = TwitterPostingController()
        self.generator = TwitterContentGenerator()

    def post_change_detection(self, change_data: Dict) -> Dict:
        """変化検知結果の投稿"""
        try:
            # 投稿制限チェック
            if not self.controller.check_daily_limit():
                return {"success": False, "error": "日次投稿制限に達しました"}

            # 重複投稿チェック
            if not self.controller.check_duplicate_post(
                change_data["entity_id"],
                change_data["change_type"]
            ):
                return {"success": False, "error": "重複投稿を検出しました"}

            # 投稿内容生成
            content = self._generate_content(change_data)

            # 投稿実行
            result = self.poster.post_text(content)

            # 投稿記録
            if result["success"]:
                self.controller.record_post(
                    result["tweet_id"],
                    content,
                    change_data["entity_id"],
                    change_data["change_type"]
                )

            return result

        except Exception as e:
            logging.error(f"投稿処理失敗: {e}")
            return {"success": False, "error": str(e)}
```

## 5. エラーハンドリング

### 5.1 主要エラーと対処法

#### 5.1.1 認証エラー
```python
class TwitterAuthError(Exception):
    """X API認証エラー"""
    pass

def handle_auth_error(e):
    """認証エラーの対処"""
    if "401" in str(e):
        logging.error("認証情報が無効です。API Key/Secretを確認してください。")
        return "認証情報の確認が必要です"
    elif "403" in str(e):
        logging.error("アプリケーションの権限が不足しています。")
        return "アプリケーション権限の確認が必要です"
    else:
        logging.error(f"認証エラー: {e}")
        return "認証エラーが発生しました"
```

#### 5.1.2 レート制限エラー
```python
class TwitterRateLimitError(Exception):
    """X APIレート制限エラー"""
    pass

def handle_rate_limit_error(e):
    """レート制限エラーの対処"""
    logging.warning("レート制限に達しました。15分後に再試行します。")
    # 15分待機後に再試行
    time.sleep(900)
    return "レート制限により投稿を遅延します"
```

## 6. セキュリティ考慮事項

### 6.1 認証情報の保護
- 環境変数による認証情報管理
- .envファイルの.gitignore設定
- 本番環境での暗号化保存

### 6.2 投稿内容の検証
- 投稿前の内容チェック
- 不適切な内容のフィルタリング
- 文字数制限の遵守

### 6.3 レート制限の遵守
- 投稿頻度の制御
- エラー時の適切な待機
- バックオフ戦略の実装

## 7. 実装スケジュール

### 7.1 Week 1: 基盤実装
- X Developer Portalでのアプリケーション作成
- 認証情報の取得・設定
- 基本クライアントクラスの実装

### 7.2 Week 2: 投稿機能実装
- テキスト投稿機能
- 画像投稿機能
- 投稿制御機能

### 7.3 Week 3: 統合・テスト
- 時系列監視との統合
- 単体・統合テスト
- エラーハンドリング

### 7.4 Week 4: 運用準備
- ログ・監視設定
- セキュリティ強化
- 本番環境デプロイ

---

**作成日**: 2025年1月27日
**作成者**: AI Assistant
**バージョン**: 1.0
**承認者**: 未定