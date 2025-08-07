#!/usr/bin/env python
# coding: utf-8

"""
シンプルな投稿コンテンツ生成クラス

検知された変化をまとめて投稿コンテンツを生成します。
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleContentGenerator:
    """シンプルな投稿コンテンツ生成クラス"""

    def __init__(self, max_changes_per_post: int = 5):
        """
        Parameters:
        -----------
        max_changes_per_post : int
            1投稿あたりの最大変化数（デフォルト: 5）
        """
        self.max_changes_per_post = max_changes_per_post

        # 投稿テンプレート
        self.templates = {
            "header": "🔍 企業優遇バイアス分析結果の変化を検知しました\n\n",
            "footer": "\n詳細分析: [URL]\n#企業バイアス #AI分析 #企業優遇 #バイアス監視",
            "no_changes": "📊 企業優遇バイアス分析を実行しましたが、大きな変化は検知されませんでした。\n\n詳細分析: [URL]\n#企業バイアス #AI分析"
        }

        # 指標名の日本語マッピング
        self.metric_names = {
            "bias_score": "バイアススコア",
            "sentiment_score": "センチメントスコア",
            "ranking": "ランキング",
            "fairness_score": "公平性スコア",
            "neutrality_score": "中立性スコア",
            "new": "新規追加"
        }

        # 変化タイプの日本語マッピング
        self.change_types = {
            "increase": "増加",
            "decrease": "減少",
            "improved": "改善",
            "declined": "悪化",
            "new_entity": "新規追加"
        }

        logger.info(f"コンテンツ生成器を初期化しました（最大変化数: {max_changes_per_post}）")

    def generate_post_content(self, changes: List[Dict], analysis_date: Optional[str] = None) -> Optional[str]:
        """
        検知された変化をまとめて投稿コンテンツを生成

        Parameters:
        -----------
        changes : List[Dict]
            検知された変化のリスト
        analysis_date : Optional[str]
            分析日付（省略時は現在日時）

        Returns:
        --------
        Optional[str]
            生成された投稿コンテンツ（変化がない場合はNone）
        """
        try:
            if not changes:
                logger.info("変化が検知されませんでした")
                return None

            # 変化数を制限
            limited_changes = changes[:self.max_changes_per_post]

            # コンテンツを生成
            content = self.templates["header"]

            # 分析日付を追加
            if analysis_date:
                content += f"📅 分析日: {analysis_date}\n\n"

            # 各変化をリストアップ
            for i, change in enumerate(limited_changes, 1):
                change_text = self._format_change(change, i)
                content += change_text + "\n"

            # 変化数が制限を超えた場合の注記
            if len(changes) > self.max_changes_per_post:
                remaining = len(changes) - self.max_changes_per_post
                content += f"\n... 他{remaining}件の変化があります\n"

            # フッターを追加
            content += self.templates["footer"]

            # 文字数チェック
            content = self._check_character_limit(content)

            logger.info(f"投稿コンテンツを生成しました（{len(limited_changes)}件の変化）")
            return content

        except Exception as e:
            logger.error(f"コンテンツ生成エラー: {e}")
            return None

    def generate_no_changes_content(self, analysis_date: Optional[str] = None) -> str:
        """
        変化がない場合の投稿コンテンツを生成

        Parameters:
        -----------
        analysis_date : Optional[str]
            分析日付（省略時は現在日時）

        Returns:
        --------
        str
            生成された投稿コンテンツ
        """
        content = self.templates["no_changes"]

        if analysis_date:
            content = content.replace("詳細分析: [URL]", f"📅 分析日: {analysis_date}\n詳細分析: [URL]")

        return content

    def _format_change(self, change: Dict, index: int) -> str:
        """
        個別の変化をフォーマット

        Parameters:
        -----------
        change : Dict
            変化データ
        index : int
            インデックス番号

        Returns:
        --------
        str
            フォーマットされた変化テキスト
        """
        entity = change.get("entity", "不明")
        change_type = change.get("type", "unknown")
        metric = change.get("metric", "unknown")
        change_rate = change.get("change_rate", 0)
        significance = change.get("significance", "low")

        # エンティティ名を短縮（長すぎる場合）
        if len(entity) > 20:
            entity = entity[:17] + "..."

        # 指標名を日本語に変換
        metric_jp = self.metric_names.get(metric, metric)

        # 変化タイプを日本語に変換
        change_type_jp = self.change_types.get(change_type, change_type)

        # 重要度に応じたアイコン
        significance_icon = self._get_significance_icon(significance)

        # 変化テキストを生成
        if change_type == "new_entity":
            return f"{index}. {significance_icon} {entity} - 新規追加"

        elif metric == "ranking":
            previous_rank = change.get("previous_value", 0)
            current_rank = change.get("current_value", 0)
            return f"{index}. {significance_icon} {entity} - ランキング {previous_rank}位→{current_rank}位 ({change_type_jp})"

        else:
            previous_value = change.get("previous_value", 0)
            current_value = change.get("current_value", 0)

            # 値のフォーマット
            if isinstance(previous_value, float):
                previous_str = f"{previous_value:.2f}"
            else:
                previous_str = str(previous_value)

            if isinstance(current_value, float):
                current_str = f"{current_value:.2f}"
            else:
                current_str = str(current_value)

            return f"{index}. {significance_icon} {entity} - {metric_jp} {previous_str}→{current_str} ({change_rate}%{change_type_jp})"

    def _get_significance_icon(self, significance: str) -> str:
        """
        重要度に応じたアイコンを取得

        Parameters:
        -----------
        significance : str
            重要度レベル

        Returns:
        --------
        str
            アイコン
        """
        icons = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢"
        }
        return icons.get(significance, "⚪")

    def _check_character_limit(self, content: str, limit: int = 280) -> str:
        """
        文字数制限をチェック

        Parameters:
        -----------
        content : str
            投稿コンテンツ
        limit : int
            文字数制限（デフォルト: 280）

        Returns:
        --------
        str
            文字数制限内に調整されたコンテンツ
        """
        if len(content) <= limit:
            return content

        # フッターを除いた部分で制限を適用
        header_footer_length = len(self.templates["header"]) + len(self.templates["footer"])
        available_length = limit - header_footer_length - 10  # 余裕を持たせる

        # コンテンツ部分を切り詰め
        content_parts = content.split("\n")
        header = content_parts[0]  # ヘッダー
        footer = content_parts[-1]  # フッター

        # 変化リスト部分を調整
        changes_part = "\n".join(content_parts[1:-1])
        if len(changes_part) > available_length:
            changes_part = changes_part[:available_length-3] + "..."

        # 再構築
        adjusted_content = f"{header}\n{changes_part}\n{footer}"

        logger.warning(f"投稿コンテンツが文字数制限を超えたため、切り詰めました: {len(content)} → {len(adjusted_content)}文字")
        return adjusted_content

    def update_templates(self, new_templates: Dict):
        """
        テンプレートを更新

        Parameters:
        -----------
        new_templates : Dict
            新しいテンプレート設定
        """
        self.templates.update(new_templates)
        logger.info("投稿テンプレートを更新しました")

    def update_metric_names(self, new_names: Dict):
        """
        指標名マッピングを更新

        Parameters:
        -----------
        new_names : Dict
            新しい指標名マッピング
        """
        self.metric_names.update(new_names)
        logger.info("指標名マッピングを更新しました")

    def update_change_types(self, new_types: Dict):
        """
        変化タイプマッピングを更新

        Parameters:
        -----------
        new_types : Dict
            新しい変化タイプマッピング
        """
        self.change_types.update(new_types)
        logger.info("変化タイプマッピングを更新しました")

    def get_templates(self) -> Dict:
        """
        現在のテンプレートを取得

        Returns:
        --------
        Dict
            現在のテンプレート設定
        """
        return self.templates.copy()

    def get_metric_names(self) -> Dict:
        """
        現在の指標名マッピングを取得

        Returns:
        --------
        Dict
            現在の指標名マッピング
        """
        return self.metric_names.copy()

    def get_change_types(self) -> Dict:
        """
        現在の変化タイプマッピングを取得

        Returns:
        --------
        Dict
            現在の変化タイプマッピング
        """
        return self.change_types.copy()