#!/usr/bin/env python
# coding: utf-8

"""
X/Twitter API連携クラス

X（旧Twitter）APIを使用した投稿機能を提供します。
tweepyライブラリを使用した実際のAPI連携を実装しています。
"""

import os
from typing import Dict, Optional
from datetime import datetime

# 新しいユーティリティをインポート
from ..utils import (
    get_config_manager, get_logger, setup_default_logging,
    handle_errors, log_api_call, log_data_operation,
    APIError, ConfigError
)

logger = get_logger(__name__)


class TwitterClient:
    """X/Twitter API連携クラス"""

    @handle_errors
    def __init__(self):
        """X API認証情報を初期化"""
        # 設定管理システムを使用
        config_manager = get_config_manager()
        api_config = config_manager.get_api_config()

        self.api_key = api_config.get('twitter_api_key', '')
        self.api_secret = api_config.get('twitter_api_secret', '')
        self.bearer_token = api_config.get('twitter_bearer_token', '')
        self.access_token = api_config.get('twitter_access_token', '')
        self.access_token_secret = api_config.get('twitter_access_token_secret', '')

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

        # 詳細ログを追加
        logger.info("=== X API認証情報チェック ===")
        logger.info(f"TWITTER_API_KEY: {'設定済み' if self.api_key else '未設定'}")
        logger.info(f"TWITTER_API_SECRET: {'設定済み' if self.api_secret else '未設定'}")
        logger.info(f"TWITTER_BEARER_TOKEN: {'設定済み' if self.bearer_token else '未設定'}")
        logger.info(f"TWITTER_ACCESS_TOKEN: {'設定済み' if self.access_token else '未設定'}")
        logger.info(f"TWITTER_ACCESS_TOKEN_SECRET: {'設定済み' if self.access_token_secret else '未設定'}")

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

            logger.info("=== X API認証処理開始 ===")

            # OAuth 1.0a認証（投稿用）
            logger.info("OAuth 1.0a認証を開始...")
            auth = tweepy.OAuthHandler(self.api_key, self.api_secret)
            auth.set_access_token(self.access_token, self.access_token_secret)
            self.api = tweepy.API(auth)
            logger.info("OAuth 1.0a認証完了")

            # OAuth 1.0a認証（投稿用）
            logger.info("OAuth 1.0a認証を開始...")
            self.client = tweepy.Client(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret
            )
            logger.info("OAuth 1.0a認証完了")

            logger.info("X API認証成功")

        except ImportError:
            logger.error("tweepyライブラリがインストールされていません。pip install tweepy を実行してください。")
            self.is_authenticated = False
        except Exception as e:
            logger.error(f"X API認証失敗: {e}")
            logger.error(f"認証エラーの詳細: {type(e).__name__}")
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
            logger.error("X API認証が完了していません")
            return {
                "success": False,
                "error": "X API認証が完了していません"
            }

        try:
            logger.info("=== X API投稿処理開始 ===")
            logger.info(f"投稿テキスト長: {len(text)}文字")

            # 文字数制限チェック（280文字）
            if len(text) > 280:
                text = text[:277] + "..."
                logger.warning("投稿テキストが文字数制限を超えたため、切り詰めました")

            # API v2を使用した投稿を試行
            try:
                logger.info("API v2投稿を試行...")
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
                logger.warning(f"API v2エラータイプ: {type(v2_error).__name__}")

                # 429エラーの場合、レート制限情報を取得
                if "429" in str(v2_error):
                    rate_limit_info = self._extract_rate_limit_info(v2_error)
                    return {
                        "success": False,
                        "error": f"レート制限に達しました",
                        "rate_limit_info": rate_limit_info,
                        "api_version": "v2"
                    }

                # その他のエラーの場合
                return {
                    "success": False,
                    "error": f"X API v2投稿失敗: {v2_error}",
                    "api_version": "v2"
                }

        except Exception as e:
            logger.error(f"X投稿失敗: {e}")
            logger.error(f"投稿エラーの詳細: {type(e).__name__}")
            return {
                "success": False,
                "error": str(e)
            }

    def _extract_rate_limit_info(self, error) -> Dict:
        """
        エラーからレート制限情報を抽出

        Parameters:
        -----------
        error : Exception
            エラーオブジェクト

        Returns:
        --------
        Dict
            レート制限情報
        """
        try:
            logger.info(f"エラーオブジェクトの型: {type(error)}")
            logger.info(f"エラーメッセージ: {str(error)}")

            # tweepyのエラーオブジェクトからレスポンス情報を取得
            if hasattr(error, 'response') and error.response:
                logger.info(f"レスポンスオブジェクト: {error.response}")

                if hasattr(error.response, 'headers'):
                    headers = error.response.headers
                    logger.info(f"レスポンスヘッダー: {headers}")

                    # HTTPヘッダーをそのまま返す
                    return {
                        "http_headers": dict(headers),
                        "rate_limit_headers": {
                            "x-rate-limit-limit": headers.get('x-rate-limit-limit'),
                            "x-rate-limit-remaining": headers.get('x-rate-limit-remaining'),
                            "x-rate-limit-reset": headers.get('x-rate-limit-reset')
                        }
                    }
                else:
                    logger.info("レスポンスにheaders属性がありません")

            # エラーメッセージから429を検出
            if "429" in str(error):
                logger.info("エラーメッセージから429を検出")
                return {
                    "error_type": "429 Too Many Requests",
                    "message": str(error)
                }

            return {
                "error_type": "unknown",
                "message": str(error)
            }

        except Exception as e:
            logger.error(f"レート制限情報抽出エラー: {e}")
            return {
                "error_type": "extraction_error",
                "message": str(e)
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