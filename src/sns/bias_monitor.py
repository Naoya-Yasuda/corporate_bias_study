#!/usr/bin/env python
# coding: utf-8

"""
バイアス変化監視クラス

NBI、おすすめランキング、サービスレベル公平性スコア、企業レベル公平性スコアの
大きな変化を監視し、投稿をトリガーします。
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from .s3_data_loader import S3DataLoader
from .content_generator import ContentGenerator
from .posting_manager import PostingManager

logger = logging.getLogger(__name__)


class BiasMonitor:
    """バイアス変化監視クラス"""

    def __init__(self, config: Optional[Dict] = None):
        """
        Parameters:
        -----------
        config : Optional[Dict]
            監視設定（省略時はデフォルト設定を使用）
        """
        self.config = config or self._get_default_config()
        self.s3_loader = S3DataLoader(
            fallback_days=self.config.get("s3", {}).get("fallback_days", 3)
        )
        self.content_generator = ContentGenerator()
        self.posting_manager = PostingManager()

    def _get_default_config(self) -> Dict:
        """デフォルト設定を取得"""
        return {
            "thresholds": {
                "nbi_change": 20.0,          # NBI変化率閾値（%）
                "ranking_change": 3,         # ランキング変化閾値（位）
                "fairness_score_change": 15.0,  # 公平性スコア変化率閾値（%）
            },
            "statistical_thresholds": {
                "p_value": 0.05,            # p値閾値
                "cliffs_delta": 0.33,       # Cliff's Delta閾値
                "rbo_threshold": 0.7,       # RBO閾値
                "kendall_tau_threshold": 0.5,  # Kendall Tau閾値
            },
            "posting_control": {
                "max_daily_posts": 10,      # 1日最大投稿数
                "duplicate_prevention_hours": 24,  # 重複防止時間（時間）
                "posting_time_range": {
                    "start": "09:00",       # 投稿開始時間
                    "end": "21:00",         # 投稿終了時間
                }
            },
            "s3": {
                "fallback_days": 3,         # データが見つからない場合の遡及日数
            }
        }

    def monitor_changes(self, current_date: str, current_data: Dict) -> List[Dict]:
        """
        変化を監視して投稿をトリガー

        Parameters:
        -----------
        current_date : str
            現在の分析日（YYYYMMDD形式）
        current_data : Dict
            現在の分析データ

        Returns:
        --------
        List[Dict]
            検知された変化のリスト
        """
        logger.info(f"バイアス変化監視を開始: {current_date}")

        # データ構造の妥当性を検証
        if not self.s3_loader.validate_data_structure(current_data):
            logger.error("現在のデータ構造が不正です")
            return []

        # 先週データを取得
        previous_data = self.s3_loader.get_previous_week_data(current_date)
        if not previous_data:
            logger.warning("先週データを取得できませんでした")
            return []

        # 変化を検知
        changes = self._detect_changes(current_data, previous_data)

        if changes:
            logger.info(f"{len(changes)}件の変化を検知しました")

            # 投稿を実行
            for change in changes:
                self._process_change(change, current_date)
        else:
            logger.info("顕著な変化は検知されませんでした")

        return changes

    def _detect_changes(self, current_data: Dict, previous_data: Dict) -> List[Dict]:
        """
        顕著な変化を検知

        Parameters:
        -----------
        current_data : Dict
            現在の分析データ
        previous_data : Dict
            先週の分析データ

        Returns:
        --------
        List[Dict]
            検知された変化のリスト
        """
        changes = []

        current_categories = current_data.get("categories", {})
        previous_categories = previous_data.get("categories", {})

        for category_name, category_data in current_categories.items():
            if category_name not in previous_categories:
                continue

            previous_category = previous_categories[category_name]

            # カテゴリレベルの変化を検知
            category_changes = self._detect_category_changes(
                category_name, category_data, previous_category
            )
            changes.extend(category_changes)

            # エンティティレベルの変化を検知
            entity_changes = self._detect_entity_changes(
                category_name, category_data, previous_category
            )
            changes.extend(entity_changes)

        return changes

    def _detect_category_changes(self, category_name: str, current_category: Dict,
                               previous_category: Dict) -> List[Dict]:
        """カテゴリレベルの変化を検知"""
        changes = []

        # サービスレベル公平性スコアの変化
        current_service_fairness = current_category.get("service_level_fairness_score")
        previous_service_fairness = previous_category.get("service_level_fairness_score")

        if current_service_fairness is not None and previous_service_fairness is not None:
            change_rate = self._calculate_change_rate(current_service_fairness, previous_service_fairness)
            threshold = self.config["thresholds"]["fairness_score_change"]

            if abs(change_rate) >= threshold:
                changes.append({
                    "type": "service_fairness_change",
                    "category": category_name,
                    "entity": None,
                    "change_rate": change_rate,
                    "current_value": current_service_fairness,
                    "previous_value": previous_service_fairness,
                    "threshold": threshold,
                    "direction": "up" if change_rate > 0 else "down"
                })

        # 企業レベル公平性スコアの変化
        current_enterprise_fairness = current_category.get("enterprise_level_fairness_score")
        previous_enterprise_fairness = previous_category.get("enterprise_level_fairness_score")

        if current_enterprise_fairness is not None and previous_enterprise_fairness is not None:
            change_rate = self._calculate_change_rate(current_enterprise_fairness, previous_enterprise_fairness)
            threshold = self.config["thresholds"]["fairness_score_change"]

            if abs(change_rate) >= threshold:
                changes.append({
                    "type": "enterprise_fairness_change",
                    "category": category_name,
                    "entity": None,
                    "change_rate": change_rate,
                    "current_value": current_enterprise_fairness,
                    "previous_value": previous_enterprise_fairness,
                    "threshold": threshold,
                    "direction": "up" if change_rate > 0 else "down"
                })

        return changes

    def _detect_entity_changes(self, category_name: str, current_category: Dict,
                             previous_category: Dict) -> List[Dict]:
        """エンティティレベルの変化を検知"""
        changes = []

        current_subcategories = current_category.get("subcategories", {})
        previous_subcategories = previous_category.get("subcategories", {})

        for subcategory_name, subcategory_data in current_subcategories.items():
            if subcategory_name not in previous_subcategories:
                continue

            previous_subcategory = previous_subcategories[subcategory_name]

            current_entities = subcategory_data.get("entities", [])
            previous_entities = previous_subcategory.get("entities", [])

            # エンティティの対応関係を作成
            entity_mapping = self._create_entity_mapping(current_entities, previous_entities)

            for current_entity in current_entities:
                entity_name = current_entity.get("name")
                if entity_name not in entity_mapping:
                    continue

                previous_entity = entity_mapping[entity_name]

                # NBIの変化を検知
                nbi_change = self._detect_nbi_change(current_entity, previous_entity)
                if nbi_change:
                    changes.append(nbi_change)

                # ランキングの変化を検知
                ranking_changes = self._detect_ranking_changes(current_entity, previous_entity)
                changes.extend(ranking_changes)

        return changes

    def _detect_nbi_change(self, current_entity: Dict, previous_entity: Dict) -> Optional[Dict]:
        """NBIの変化を検知"""
        current_nbi = current_entity.get("normalized_bias_index")
        previous_nbi = previous_entity.get("normalized_bias_index")

        if current_nbi is None or previous_nbi is None:
            return None

        change_rate = self._calculate_change_rate(current_nbi, previous_nbi)
        threshold = self.config["thresholds"]["nbi_change"]

        if abs(change_rate) >= threshold:
            # 統計的有意性をチェック
            p_value = current_entity.get("sign_test_p_value")
            cliffs_delta = current_entity.get("cliffs_delta")

            if self._is_statistically_significant(p_value, cliffs_delta):
                return {
                    "type": "nbi_change",
                    "entity": current_entity.get("name"),
                    "category": current_entity.get("category"),
                    "change_rate": change_rate,
                    "current_value": current_nbi,
                    "previous_value": previous_nbi,
                    "threshold": threshold,
                    "direction": "up" if change_rate > 0 else "down",
                    "p_value": p_value,
                    "cliffs_delta": cliffs_delta
                }

        return None

    def _detect_ranking_changes(self, current_entity: Dict, previous_entity: Dict) -> List[Dict]:
        """ランキングの変化を検知"""
        changes = []

        # Googleランキングの変化
        current_google_rank = current_entity.get("google_rank")
        previous_google_rank = previous_entity.get("google_rank")

        if current_google_rank is not None and previous_google_rank is not None:
            rank_change = previous_google_rank - current_google_rank  # 正の値は順位向上
            threshold = self.config["thresholds"]["ranking_change"]

            if abs(rank_change) >= threshold:
                changes.append({
                    "type": "ranking_change",
                    "entity": current_entity.get("name"),
                    "category": current_entity.get("category"),
                    "platform": "Google",
                    "current_rank": current_google_rank,
                    "previous_rank": previous_google_rank,
                    "rank_change": rank_change,
                    "threshold": threshold,
                    "direction": "up" if rank_change > 0 else "down"
                })

        # Perplexityランキングの変化
        current_perplexity_rank = current_entity.get("perplexity_rank")
        previous_perplexity_rank = previous_entity.get("perplexity_rank")

        if current_perplexity_rank is not None and previous_perplexity_rank is not None:
            rank_change = previous_perplexity_rank - current_perplexity_rank
            threshold = self.config["thresholds"]["ranking_change"]

            if abs(rank_change) >= threshold:
                changes.append({
                    "type": "ranking_change",
                    "entity": current_entity.get("name"),
                    "category": current_entity.get("category"),
                    "platform": "Perplexity",
                    "current_rank": current_perplexity_rank,
                    "previous_rank": previous_perplexity_rank,
                    "rank_change": rank_change,
                    "threshold": threshold,
                    "direction": "up" if rank_change > 0 else "down"
                })

        return changes

    def _create_entity_mapping(self, current_entities: List[Dict],
                             previous_entities: List[Dict]) -> Dict[str, Dict]:
        """エンティティの対応関係を作成"""
        mapping = {}

        for previous_entity in previous_entities:
            entity_name = previous_entity.get("name")
            if entity_name:
                mapping[entity_name] = previous_entity

        return mapping

    def _calculate_change_rate(self, current: float, previous: float) -> float:
        """変化率を計算"""
        if previous == 0:
            return 0.0
        return ((current - previous) / abs(previous)) * 100

    def _is_statistically_significant(self, p_value: Optional[float],
                                    cliffs_delta: Optional[float]) -> bool:
        """統計的有意性をチェック"""
        if p_value is None or cliffs_delta is None:
            return False

        p_threshold = self.config["statistical_thresholds"]["p_value"]
        cliffs_threshold = self.config["statistical_thresholds"]["cliffs_delta"]

        return p_value < p_threshold and abs(cliffs_delta) >= cliffs_threshold

    def _process_change(self, change: Dict, current_date: str):
        """変化を処理して投稿を実行"""
        try:
            # 重複投稿をチェック
            if self.posting_manager.check_duplicate(change["entity"], change["type"]):
                logger.info(f"重複投稿をスキップ: {change['entity']} - {change['type']}")
                return

            # 投稿コンテンツを生成
            content = self.content_generator.generate_content(change, current_date)

            # 投稿を実行
            result = self.posting_manager.post_change(content, change)

            if result.get("success"):
                logger.info(f"投稿成功: {change['entity']} - {change['type']}")
            else:
                logger.error(f"投稿失敗: {change['entity']} - {change['type']}: {result.get('error')}")

        except Exception as e:
            logger.error(f"変化処理エラー: {e}")