#!/usr/bin/env python
# coding: utf-8

"""
投稿コンテンツ生成クラス

バイアス変化検知結果に基づいてX/Twitter投稿用のコンテンツを生成します。
"""

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ContentGenerator:
    """投稿コンテンツ生成クラス"""

    def __init__(self, base_url: str = "https://your-domain.com/analysis"):
        """
        Parameters:
        -----------
        base_url : str
            分析詳細ページのベースURL
        """
        self.base_url = base_url

    def generate_content(self, change: Dict, current_date: str) -> str:
        """
        変化データから投稿コンテンツを生成

        Parameters:
        -----------
        change : Dict
            検知された変化データ
        current_date : str
            現在の分析日（YYYYMMDD形式）

        Returns:
        --------
        str
            投稿用テキスト
        """
        change_type = change.get("type")

        if change_type == "nbi_change":
            return self._generate_nbi_change_content(change, current_date)
        elif change_type == "ranking_change":
            return self._generate_ranking_change_content(change, current_date)
        elif change_type == "service_fairness_change":
            return self._generate_service_fairness_content(change, current_date)
        elif change_type == "enterprise_fairness_change":
            return self._generate_enterprise_fairness_content(change, current_date)
        else:
            logger.warning(f"未対応の変化タイプ: {change_type}")
            return self._generate_generic_content(change, current_date)

    def _generate_nbi_change_content(self, change: Dict, current_date: str) -> str:
        """NBI変化の投稿コンテンツを生成"""
        entity_name = change.get("entity", "不明")
        change_rate = change.get("change_rate", 0)
        direction = change.get("direction", "up")
        current_value = change.get("current_value", 0)
        previous_value = change.get("previous_value", 0)

        # 方向性の日本語表現
        direction_text = "上昇" if direction == "up" else "下降"

        # 詳細説明
        if abs(change_rate) >= 50:
            detail = f"感情スコアが急激に{direction_text}"
        elif abs(change_rate) >= 30:
            detail = f"感情スコアが大幅に{direction_text}"
        else:
            detail = f"感情スコアが{direction_text}"

        # 統計的有意性の表示
        p_value = change.get("p_value")
        cliffs_delta = change.get("cliffs_delta")
        significance_text = ""
        if p_value is not None and cliffs_delta is not None:
            if p_value < 0.01:
                significance_text = "（統計的に非常に有意）"
            elif p_value < 0.05:
                significance_text = "（統計的に有意）"

        content = f"""🚨【企業優遇バイアス変化検知】

📊 検知内容: NBI急激な変化
🏢 対象企業: {entity_name}
📈 変化率: {change_rate:.1f}%
📋 詳細: {detail}{significance_text}

🔍 分析詳細: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #AI分析 #透明性"""

        return content

    def _generate_ranking_change_content(self, change: Dict, current_date: str) -> str:
        """ランキング変化の投稿コンテンツを生成"""
        entity_name = change.get("entity", "不明")
        platform = change.get("platform", "不明")
        current_rank = change.get("current_rank", 0)
        previous_rank = change.get("previous_rank", 0)
        rank_change = change.get("rank_change", 0)
        direction = change.get("direction", "up")

        # 方向性の日本語表現
        direction_text = "上昇" if direction == "up" else "下降"

        # 詳細説明
        if abs(rank_change) >= 5:
            detail = f"検索結果での露出度が大幅に変化"
        else:
            detail = f"検索結果での露出度が変化"

        content = f"""📈【検索ランキング変化検知】

🏢 対象企業: {entity_name}
📊 プラットフォーム: {platform}
📈 順位変化: {previous_rank}位 → {current_rank}位 ({direction_text})
📋 詳細: {detail}

🔍 分析詳細: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #検索分析 #ランキング"""

        return content

    def _generate_service_fairness_content(self, change: Dict, current_date: str) -> str:
        """サービスレベル公平性スコア変化の投稿コンテンツを生成"""
        category_name = change.get("category", "不明")
        change_rate = change.get("change_rate", 0)
        direction = change.get("direction", "up")
        current_value = change.get("current_value", 0)
        previous_value = change.get("previous_value", 0)

        # 方向性の日本語表現
        direction_text = "向上" if direction == "up" else "低下"

        # 詳細説明
        if abs(change_rate) >= 30:
            detail = f"市場における公平性評価が大幅に{direction_text}"
        else:
            detail = f"市場における公平性評価が{direction_text}"

        content = f"""⚖️【公平性スコア変化検知】

🏢 対象業界: {category_name}
📊 スコア種別: サービスレベル公平性スコア
📈 変化率: {change_rate:.1f}%
📋 詳細: {detail}

🔍 分析詳細: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #公平性 #市場分析"""

        return content

    def _generate_enterprise_fairness_content(self, change: Dict, current_date: str) -> str:
        """企業レベル公平性スコア変化の投稿コンテンツを生成"""
        category_name = change.get("category", "不明")
        change_rate = change.get("change_rate", 0)
        direction = change.get("direction", "up")
        current_value = change.get("current_value", 0)
        previous_value = change.get("previous_value", 0)

        # 方向性の日本語表現
        direction_text = "向上" if direction == "up" else "低下"

        # 詳細説明
        if abs(change_rate) >= 30:
            detail = f"企業規模による公平性評価が大幅に{direction_text}"
        else:
            detail = f"企業規模による公平性評価が{direction_text}"

        content = f"""⚖️【公平性スコア変化検知】

🏢 対象業界: {category_name}
📊 スコア種別: 企業レベル公平性スコア
📈 変化率: {change_rate:.1f}%
📋 詳細: {detail}

🔍 分析詳細: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #公平性 #企業分析"""

        return content

    def _generate_generic_content(self, change: Dict, current_date: str) -> str:
        """汎用的な変化の投稿コンテンツを生成"""
        entity_name = change.get("entity", "不明")
        change_type = change.get("type", "不明")
        change_rate = change.get("change_rate", 0)
        direction = change.get("direction", "up")

        # 方向性の日本語表現
        direction_text = "上昇" if direction == "up" else "下降"

        content = f"""🚨【企業優遇バイアス変化検知】

📊 検知内容: {change_type}
🏢 対象企業: {entity_name}
📈 変化率: {change_rate:.1f}%
📋 詳細: バイアス指標が{direction_text}

🔍 分析詳細: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #AI分析 #透明性"""

        return content

    def _generate_analysis_url(self, current_date: str) -> str:
        """分析詳細ページのURLを生成"""
        return f"{self.base_url}/{current_date}"

    def generate_summary_content(self, changes: list, current_date: str) -> str:
        """
        複数の変化をまとめたサマリー投稿コンテンツを生成

        Parameters:
        -----------
        changes : list
            検知された変化のリスト
        current_date : str
            現在の分析日（YYYYMMDD形式）

        Returns:
        --------
        str
            サマリー投稿用テキスト
        """
        if not changes:
            return ""

        # 変化の種類別にカウント
        change_counts = {}
        for change in changes:
            change_type = change.get("type", "unknown")
            change_counts[change_type] = change_counts.get(change_type, 0) + 1

        # 主要な変化を抽出
        major_changes = []
        for change in changes:
            change_rate = abs(change.get("change_rate", 0))
            if change_rate >= 30:  # 30%以上の変化を主要変化とする
                major_changes.append(change)

        # サマリーコンテンツを生成
        total_changes = len(changes)
        major_count = len(major_changes)

        content = f"""📊【企業優遇バイアス週次レポート】

📈 検知された変化: {total_changes}件
🚨 主要変化: {major_count}件
📅 分析期間: {current_date}

🔍 詳細分析: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #週次レポート #AI分析"""

        return content

    def generate_error_content(self, error_message: str, current_date: str) -> str:
        """
        エラー時の投稿コンテンツを生成

        Parameters:
        -----------
        error_message : str
            エラーメッセージ
        current_date : str
            現在の分析日（YYYYMMDD形式）

        Returns:
        --------
        str
            エラー投稿用テキスト
        """
        content = f"""⚠️【バイアス分析システム通知】

📋 内容: 分析処理中にエラーが発生しました
🔧 詳細: {error_message}
📅 発生日時: {current_date}

🔍 システム状況: {self._generate_analysis_url(current_date)}
#企業優遇バイアス #システム通知"""

        return content