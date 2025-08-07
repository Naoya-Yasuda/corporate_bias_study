#!/usr/bin/env python
# coding: utf-8

"""
投稿管理クラス

X/Twitter投稿の管理、重複防止、投稿制御を行います。
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class PostingManager:
    """投稿管理クラス"""

    def __init__(self, db_path: str = "data/sns_posts.db"):
        """
        Parameters:
        -----------
        db_path : str
            投稿履歴データベースのパス
        """
        self.db_path = db_path
        self._init_database()

        # 投稿制御設定
        self.max_daily_posts = int(os.getenv('TWITTER_MAX_DAILY_POSTS', 10))
        self.duplicate_prevention_hours = int(os.getenv('TWITTER_DUPLICATE_PREVENTION_HOURS', 24))

        # X API投稿機能（将来的に実装）
        self.twitter_client = None  # TwitterClient()

    def _init_database(self):
        """投稿履歴データベース初期化"""
        try:
            # ディレクトリを作成
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 投稿履歴テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sns_posts (
                    id INTEGER PRIMARY KEY,
                    post_id VARCHAR(50),
                    content TEXT,
                    image_path VARCHAR(255),
                    entity_id VARCHAR(100),
                    change_type VARCHAR(30),
                    change_rate REAL,
                    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    engagement_metrics JSON,
                    status VARCHAR(20) DEFAULT 'posted',
                    error_message TEXT
                )
            ''')

            # 投稿制御テーブル
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posting_control (
                    id INTEGER PRIMARY KEY,
                    control_date DATE,
                    daily_post_count INTEGER DEFAULT 0,
                    last_post_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(control_date)
                )
            ''')

            conn.commit()
            conn.close()
            logger.info(f"投稿履歴データベースを初期化しました: {self.db_path}")

        except Exception as e:
            logger.error(f"データベース初期化エラー: {e}")

    def check_daily_limit(self) -> bool:
        """
        日次投稿制限をチェック

        Returns:
        --------
        bool
            投稿可能な場合はTrue、制限に達している場合はFalse
        """
        try:
            today = datetime.now().date()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日の投稿数を取得
            cursor.execute('''
                SELECT daily_post_count FROM posting_control
                WHERE control_date = ?
            ''', (today,))

            result = cursor.fetchone()
            if result:
                daily_count = result[0]
            else:
                daily_count = 0

            conn.close()

            can_post = daily_count < self.max_daily_posts
            if not can_post:
                logger.warning(f"日次投稿制限に達しました: {daily_count}/{self.max_daily_posts}")

            return can_post

        except Exception as e:
            logger.error(f"日次制限チェックエラー: {e}")
            return True  # エラー時は投稿を許可

    def check_duplicate(self, entity_id: str, change_type: str) -> bool:
        """
        重複投稿をチェック

        Parameters:
        -----------
        entity_id : str
            エンティティID
        change_type : str
            変化タイプ

        Returns:
        --------
        bool
            重複がある場合はTrue、ない場合はFalse
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.duplicate_prevention_hours)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) FROM sns_posts
                WHERE entity_id = ? AND change_type = ? AND posted_at > ?
            ''', (entity_id, change_type, cutoff_time))

            count = cursor.fetchone()[0]
            conn.close()

            is_duplicate = count > 0
            if is_duplicate:
                logger.info(f"重複投稿を検出: {entity_id} - {change_type}")

            return is_duplicate

        except Exception as e:
            logger.error(f"重複チェックエラー: {e}")
            return False  # エラー時は重複なしとして扱う

    def post_change(self, content: str, change: Dict) -> Dict:
        """
        変化を投稿

        Parameters:
        -----------
        content : str
            投稿コンテンツ
        change : Dict
            変化データ

        Returns:
        --------
        Dict
            投稿結果
        """
        try:
            # 投稿制限チェック
            if not self.check_daily_limit():
                return {
                    "success": False,
                    "error": "日次投稿制限に達しました"
                }

            # 重複投稿チェック
            entity_id = change.get("entity", "unknown")
            change_type = change.get("type", "unknown")

            if self.check_duplicate(entity_id, change_type):
                return {
                    "success": False,
                    "error": "重複投稿を検出しました"
                }

            # 投稿実行（将来的にX APIを使用）
            result = self._execute_post(content, change)

            # 投稿履歴を記録
            if result.get("success"):
                self._record_post(content, change, result)
                self._update_daily_count()

            return result

        except Exception as e:
            logger.error(f"投稿処理エラー: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _execute_post(self, content: str, change: Dict) -> Dict:
        """
        実際の投稿を実行（将来的にX APIを使用）

        Parameters:
        -----------
        content : str
            投稿コンテンツ
        change : Dict
            変化データ

        Returns:
        --------
        Dict
            投稿結果
        """
        # 現在はログ出力のみ（将来的にX API実装）
        logger.info(f"投稿実行（シミュレーション）:")
        logger.info(f"コンテンツ: {content}")
        logger.info(f"変化データ: {change}")

        # 文字数チェック
        if len(content) > 280:
            logger.warning(f"投稿文字数が制限を超えています: {len(content)}文字")
            content = content[:277] + "..."

        return {
            "success": True,
            "post_id": f"sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "content": content,
            "posted_at": datetime.now()
        }

    def _record_post(self, content: str, change: Dict, result: Dict):
        """
        投稿履歴を記録

        Parameters:
        -----------
        content : str
            投稿コンテンツ
        change : Dict
            変化データ
        result : Dict
            投稿結果
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO sns_posts (
                    post_id, content, entity_id, change_type, change_rate,
                    posted_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.get("post_id"),
                content,
                change.get("entity"),
                change.get("type"),
                change.get("change_rate"),
                result.get("posted_at"),
                "posted"
            ))

            conn.commit()
            conn.close()
            logger.info("投稿履歴を記録しました")

        except Exception as e:
            logger.error(f"投稿履歴記録エラー: {e}")

    def _update_daily_count(self):
        """日次投稿カウントを更新"""
        try:
            today = datetime.now().date()
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日のレコードを取得または作成
            cursor.execute('''
                INSERT OR REPLACE INTO posting_control (
                    control_date, daily_post_count, last_post_time
                ) VALUES (
                    ?,
                    COALESCE((SELECT daily_post_count FROM posting_control WHERE control_date = ?), 0) + 1,
                    ?
                )
            ''', (today, today, datetime.now()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"日次カウント更新エラー: {e}")

    def get_post_history(self, days: int = 7) -> List[Dict]:
        """
        投稿履歴を取得

        Parameters:
        -----------
        days : int
            取得する日数（デフォルト: 7日）

        Returns:
        --------
        List[Dict]
            投稿履歴のリスト
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT post_id, content, entity_id, change_type, change_rate,
                       posted_at, status, error_message
                FROM sns_posts
                WHERE posted_at > ?
                ORDER BY posted_at DESC
            ''', (cutoff_date,))

            rows = cursor.fetchall()
            conn.close()

            history = []
            for row in rows:
                history.append({
                    "post_id": row[0],
                    "content": row[1],
                    "entity_id": row[2],
                    "change_type": row[3],
                    "change_rate": row[4],
                    "posted_at": row[5],
                    "status": row[6],
                    "error_message": row[7]
                })

            return history

        except Exception as e:
            logger.error(f"投稿履歴取得エラー: {e}")
            return []

    def get_daily_stats(self, date: Optional[str] = None) -> Dict:
        """
        日次投稿統計を取得

        Parameters:
        -----------
        date : Optional[str]
            統計を取得する日付（YYYY-MM-DD形式、省略時は今日）

        Returns:
        --------
        Dict
            日次統計データ
        """
        try:
            if date is None:
                target_date = datetime.now().date()
            else:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 投稿数
            cursor.execute('''
                SELECT COUNT(*) FROM sns_posts
                WHERE DATE(posted_at) = ?
            ''', (target_date,))
            post_count = cursor.fetchone()[0]

            # 変化タイプ別投稿数
            cursor.execute('''
                SELECT change_type, COUNT(*) FROM sns_posts
                WHERE DATE(posted_at) = ?
                GROUP BY change_type
            ''', (target_date,))
            change_type_counts = dict(cursor.fetchall())

            # エラー数
            cursor.execute('''
                SELECT COUNT(*) FROM sns_posts
                WHERE DATE(posted_at) = ? AND status = 'error'
            ''', (target_date,))
            error_count = cursor.fetchone()[0]

            conn.close()

            return {
                "date": target_date.strftime("%Y-%m-%d"),
                "total_posts": post_count,
                "change_type_counts": change_type_counts,
                "error_count": error_count,
                "max_daily_posts": self.max_daily_posts,
                "remaining_posts": max(0, self.max_daily_posts - post_count)
            }

        except Exception as e:
            logger.error(f"日次統計取得エラー: {e}")
            return {}

    def clear_old_records(self, days: int = 30):
        """
        古い投稿履歴を削除

        Parameters:
        -----------
        days : int
            削除する日数（デフォルト: 30日）
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                DELETE FROM sns_posts
                WHERE posted_at < ?
            ''', (cutoff_date,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"古い投稿履歴を削除しました: {deleted_count}件")

        except Exception as e:
            logger.error(f"古いレコード削除エラー: {e}")