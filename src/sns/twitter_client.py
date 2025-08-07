#!/usr/bin/env python
# coding: utf-8

"""
X/Twitter API連携クラス

X（旧Twitter）APIを使用した投稿機能を提供します。
tweepyライブラリを使用した実際のAPI連携を実装しています。
"""

import os
import logging
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class TwitterClient:
    """X/Twitter API連携クラス"""

    def __init__(self):
        """X API認証情報を初期化"""
        # 環境変数を確実に読み込み
        load_dotenv()

        self.api_key = os.getenv('TWITTER_API_KEY')
        self.api_secret = os.getenv('TWITTER_API_SECRET')
        self.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

        self.client = None
        self.api = None
        self.is_authenticated = False

        # 認証情報の存在チェック
        self._check_credentials()

        if self.is_authenticated:
            self._authenticate()

    def _check_credentials(self):
        """認証情報の存在をチェック"""
        required_credentials = [
            self.api_key,
            self.api_secret,
            self.bearer_token,
            self.access_token,
            self.access_token_secret
        ]

        # 各認証情報の存在を個別にチェック
        missing_credentials = []
        if not self.api_key:
            missing_credentials.append("TWITTER_API_KEY")
        if not self.api_secret:
            missing_credentials.append("TWITTER_API_SECRET")
        if not self.bearer_token:
            missing_credentials.append("TWITTER_BEARER_TOKEN")
        if not self.access_token:
            missing_credentials.append("TWITTER_ACCESS_TOKEN")
        if not self.access_token_secret:
            missing_credentials.append("TWITTER_ACCESS_TOKEN_SECRET")

        if all(required_credentials):
            self.is_authenticated = True
            logger.info("X API認証情報が設定されています")
        else:
            self.is_authenticated = False
            logger.warning(f"X API認証情報が不完全です。不足している項目: {', '.join(missing_credentials)}")
            logger.info("環境変数ファイル(.env)の設定を確認してください。")

    def _authenticate(self):
        """X API認証"""
        try:
            import tweepy

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

            logger.info("X API認証成功")

        except ImportError:
            logger.error("tweepyライブラリがインストールされていません。pip install tweepy を実行してください。")
            self.is_authenticated = False
        except Exception as e:
            logger.error(f"X API認証失敗: {e}")
            self.is_authenticated = False

    def post_text(self, text: str) -> Dict:
        """
        テキスト投稿

        Parameters:
        -----------
        text : str
            投稿するテキスト

        Returns:
        --------
        Dict
            投稿結果
        """
        if not self.is_authenticated:
            return {
                "success": False,
                "error": "X API認証が完了していません"
            }

        try:
            # 文字数制限チェック（280文字）
            if len(text) > 280:
                text = text[:277] + "..."
                logger.warning("投稿テキストが文字数制限を超えたため、切り詰めました")

            # API v2を使用した投稿を試行
            try:
                response = self.client.create_tweet(text=text)

                if response and response.data:
                    tweet_id = response.data['id']
                    logger.info(f"X投稿成功 (API v2): {tweet_id}")

                    return {
                        "success": True,
                        "tweet_id": str(tweet_id),
                        "text": text,
                        "created_at": datetime.now(),
                        "api_version": "v2"
                    }
                else:
                    logger.error("X API v2投稿レスポンスが不正です")
                    return {
                        "success": False,
                        "error": "投稿レスポンスが不正です"
                    }

            except Exception as v2_error:
                logger.warning(f"API v2投稿失敗: {v2_error}")

                # API v1.1にフォールバック（Proプラン以上が必要）
                try:
                    response = self.api.update_status(text)
                    tweet_id = response.id
                    logger.info(f"X投稿成功 (API v1.1): {tweet_id}")

                    return {
                        "success": True,
                        "tweet_id": str(tweet_id),
                        "text": text,
                        "created_at": datetime.now(),
                        "api_version": "v1.1"
                    }

                except Exception as v1_error:
                    logger.error(f"API v1.1投稿失敗: {v1_error}")

                    # エラーメッセージから詳細情報を抽出
                    error_msg = str(v1_error)
                    if "453" in error_msg or "access level" in error_msg.lower():
                        error_msg = "X APIのアクセスレベルが不足しています。Proプラン以上が必要です。"

                    return {
                        "success": False,
                        "error": error_msg,
                        "api_version": "v1.1"
                    }

        except Exception as e:
            logger.error(f"X投稿失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def post_with_image(self, text: str, image_path: str) -> Dict:
        """
        画像付き投稿

        Parameters:
        -----------
        text : str
            投稿するテキスト
        image_path : str
            画像ファイルのパス

        Returns:
        --------
        Dict
            投稿結果
        """
        if not self.is_authenticated:
            return {
                "success": False,
                "error": "X API認証が完了していません"
            }

        try:
            # 文字数制限チェック
            if len(text) > 280:
                text = text[:277] + "..."
                logger.warning("投稿テキストが文字数制限を超えたため、切り詰めました")

            # 画像ファイルの存在チェック
            if not os.path.exists(image_path):
                return {
                    "success": False,
                    "error": f"画像ファイルが見つかりません: {image_path}"
                }

            # 画像をアップロード
            media = self.api.media_upload(image_path)

            # 画像付きツイートを投稿
            response = self.client.create_tweet(
                text=text,
                media_ids=[media.media_id]
            )

            if response and response.data:
                tweet_id = response.data['id']
                logger.info(f"X画像投稿成功: {tweet_id}")

                return {
                    "success": True,
                    "tweet_id": str(tweet_id),
                    "text": text,
                    "image_path": image_path,
                    "created_at": datetime.now()
                }
            else:
                logger.error("X API画像投稿レスポンスが不正です")
                return {
                    "success": False,
                    "error": "画像投稿レスポンスが不正です"
                }

        except Exception as e:
            logger.error(f"X画像投稿失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def post_thread(self, texts: list) -> Dict:
        """
        スレッド投稿

        Parameters:
        -----------
        texts : list
            投稿するテキストのリスト

        Returns:
        --------
        Dict
            投稿結果
        """
        if not self.is_authenticated:
            return {
                "success": False,
                "error": "X API認証が完了していません"
            }

        try:
            if not texts:
                return {
                    "success": False,
                    "error": "投稿テキストが空です"
                }

            # 各テキストの文字数チェック
            validated_texts = []
            for text in texts:
                if len(text) > 280:
                    text = text[:277] + "..."
                validated_texts.append(text)

            # スレッド投稿を実行
            tweet_ids = []
            in_reply_to_tweet_id = None

            for text in validated_texts:
                response = self.client.create_tweet(
                    text=text,
                    in_reply_to_tweet_id=in_reply_to_tweet_id
                )

                if response and response.data:
                    tweet_id = response.data['id']
                    tweet_ids.append(str(tweet_id))
                    in_reply_to_tweet_id = tweet_id
                else:
                    logger.error(f"スレッド投稿の一部が失敗: {text[:50]}...")
                    break

            if tweet_ids:
                logger.info(f"Xスレッド投稿成功: {len(tweet_ids)}件")
                return {
                    "success": True,
                    "tweet_ids": tweet_ids,
                    "texts": validated_texts,
                    "created_at": datetime.now()
                }
            else:
                return {
                    "success": False,
                    "error": "スレッド投稿に失敗しました"
                }

        except Exception as e:
            logger.error(f"Xスレッド投稿失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_user_info(self) -> Dict:
        """
        ユーザー情報を取得

        Returns:
        --------
        Dict
            ユーザー情報
        """
        if not self.is_authenticated:
            return {
                "success": False,
                "error": "X API認証が完了していません"
            }

        try:
            # 実際のX APIユーザー情報取得を実行
            user = self.client.get_me()

            if user and user.data:
                user_data = user.data
                return {
                    "success": True,
                    "user_id": str(user_data.id),
                    "username": user_data.username,
                    "name": user_data.name,
                    "followers_count": getattr(user_data, 'public_metrics', {}).get('followers_count', 0),
                    "following_count": getattr(user_data, 'public_metrics', {}).get('following_count', 0)
                }
            else:
                logger.error("X APIユーザー情報取得レスポンスが不正です")
                return {
                    "success": False,
                    "error": "ユーザー情報レスポンスが不正です"
                }

        except Exception as e:
            logger.error(f"ユーザー情報取得失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def check_rate_limit(self) -> Dict:
        """
        レート制限をチェック

        Returns:
        --------
        Dict
            レート制限情報
        """
        if not self.is_authenticated:
            return {
                "success": False,
                "error": "X API認証が完了していません"
            }

        try:
            # 実際のX APIレート制限チェックを実行
            rate_limit_status = self.api.rate_limit_status()

            # 投稿関連のレート制限を取得
            post_limits = rate_limit_status.get('resources', {}).get('statuses', {}).get('/statuses/update', {})

            remaining_requests = post_limits.get('remaining', 0)
            reset_time = post_limits.get('reset', 0)
            limit = post_limits.get('limit', 0)

            return {
                "success": True,
                "remaining_requests": remaining_requests,
                "reset_time": reset_time,
                "limit": limit
            }

        except Exception as e:
            logger.error(f"レート制限チェック失敗: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def test_connection(self) -> Dict:
        """
        接続テスト

        Returns:
        --------
        Dict
            テスト結果
        """
        try:
            if not self.is_authenticated:
                return {
                    "success": False,
                    "error": "認証情報が設定されていません"
                }

            # ユーザー情報取得で接続テスト
            user_info = self.get_user_info()
            if user_info.get("success"):
                return {
                    "success": True,
                    "message": "X API接続テスト成功",
                    "user_info": user_info
                }
            else:
                return {
                    "success": False,
                    "error": "接続テスト失敗"
                }

        except Exception as e:
            logger.error(f"接続テストエラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }