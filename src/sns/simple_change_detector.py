#!/usr/bin/env python
# coding: utf-8

"""
シンプルな変化検知クラス

前回と今回の分析結果を比較して、閾値を超えた変化を検知します。
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleChangeDetector:
    """シンプルな変化検知クラス"""

    def __init__(self, thresholds: Optional[Dict] = None):
        """
        Parameters:
        -----------
        thresholds : Optional[Dict]
            変化検知の閾値設定
        """
        # デフォルト閾値
        self.thresholds = thresholds or {
            "bias_score": 0.1,      # バイアススコアの変化閾値
            "sentiment_score": 0.15, # センチメントスコアの変化閾値
            "ranking_change": 3,     # ランキング変化閾値
            "fairness_score": 0.1,   # 公平性スコアの変化閾値
            "neutrality_score": 0.1  # 中立性スコアの変化閾値
        }

        logger.info(f"変化検知閾値を設定しました: {self.thresholds}")

    def detect_changes(self, previous_data: Dict, current_data: Dict) -> List[Dict]:
        """
        前回と今回のデータを比較して閾値を超えた変化を検知

        Parameters:
        -----------
        previous_data : Dict
            前回の分析結果データ
        current_data : Dict
            今回の分析結果データ

        Returns:
        --------
        List[Dict]
            検知された変化のリスト
        """
        changes = []

        try:
            # 各エンティティの変化をチェック
            for entity_id, current_metrics in current_data.items():
                if entity_id in previous_data:
                    previous_metrics = previous_data[entity_id]
                    entity_changes = self._detect_entity_changes(
                        entity_id, previous_metrics, current_metrics
                    )
                    changes.extend(entity_changes)
                else:
                    # 新規エンティティの場合は新規追加として扱う
                    logger.info(f"新規エンティティを検出: {entity_id}")
                    changes.append({
                        "entity": entity_id,
                        "type": "new_entity",
                        "metric": "new",
                        "previous_value": None,
                        "current_value": current_metrics,
                        "change_rate": 100.0,
                        "significance": "high"
                    })

            # 変化の重要度でソート（重要度の高い順）
            changes.sort(key=lambda x: self._get_significance_score(x), reverse=True)

            logger.info(f"変化検知完了: {len(changes)}件の変化を検出")
            return changes

        except Exception as e:
            logger.error(f"変化検知エラー: {e}")
            return []

    def _detect_entity_changes(self, entity_id: str, previous_metrics: Dict, current_metrics: Dict) -> List[Dict]:
        """
        個別エンティティの変化を検知

        Parameters:
        -----------
        entity_id : str
            エンティティID
        previous_metrics : Dict
            前回の指標データ
        current_metrics : Dict
            今回の指標データ

        Returns:
        --------
        List[Dict]
            エンティティの変化リスト
        """
        changes = []

        # バイアススコアの変化チェック
        if "bias_score" in current_metrics and "bias_score" in previous_metrics:
            change = self._calculate_change(
                entity_id, "bias_score",
                previous_metrics["bias_score"],
                current_metrics["bias_score"],
                self.thresholds["bias_score"]
            )
            if change:
                changes.append(change)

        # センチメントスコアの変化チェック
        if "sentiment_score" in current_metrics and "sentiment_score" in previous_metrics:
            change = self._calculate_change(
                entity_id, "sentiment_score",
                previous_metrics["sentiment_score"],
                current_metrics["sentiment_score"],
                self.thresholds["sentiment_score"]
            )
            if change:
                changes.append(change)

        # ランキングの変化チェック
        if "ranking" in current_metrics and "ranking" in previous_metrics:
            change = self._calculate_ranking_change(
                entity_id,
                previous_metrics["ranking"],
                current_metrics["ranking"]
            )
            if change:
                changes.append(change)

        # 公平性スコアの変化チェック
        if "fairness_score" in current_metrics and "fairness_score" in previous_metrics:
            change = self._calculate_change(
                entity_id, "fairness_score",
                previous_metrics["fairness_score"],
                current_metrics["fairness_score"],
                self.thresholds["fairness_score"]
            )
            if change:
                changes.append(change)

        # 中立性スコアの変化チェック
        if "neutrality_score" in current_metrics and "neutrality_score" in previous_metrics:
            change = self._calculate_change(
                entity_id, "neutrality_score",
                previous_metrics["neutrality_score"],
                current_metrics["neutrality_score"],
                self.thresholds["neutrality_score"]
            )
            if change:
                changes.append(change)

        return changes

    def _calculate_change(self, entity_id: str, metric_name: str,
                         previous_value: float, current_value: float,
                         threshold: float) -> Optional[Dict]:
        """
        指標の変化を計算

        Parameters:
        -----------
        entity_id : str
            エンティティID
        metric_name : str
            指標名
        previous_value : float
            前回の値
        current_value : float
            今回の値
        threshold : float
            閾値

        Returns:
        --------
        Optional[Dict]
            変化データ（閾値を超えた場合のみ）
        """
        try:
            # 変化率を計算
            if previous_value == 0:
                change_rate = 100.0 if current_value > 0 else 0.0
            else:
                change_rate = abs((current_value - previous_value) / previous_value) * 100

            # 閾値を超えた場合のみ変化として記録
            if change_rate >= threshold * 100:  # 閾値をパーセンテージに変換
                change_type = "increase" if current_value > previous_value else "decrease"

                return {
                    "entity": entity_id,
                    "type": change_type,
                    "metric": metric_name,
                    "previous_value": previous_value,
                    "current_value": current_value,
                    "change_rate": round(change_rate, 2),
                    "significance": self._get_significance_level(change_rate)
                }

            return None

        except Exception as e:
            logger.error(f"変化計算エラー ({entity_id}, {metric_name}): {e}")
            return None

    def _calculate_ranking_change(self, entity_id: str, previous_ranking: int, current_ranking: int) -> Optional[Dict]:
        """
        ランキングの変化を計算

        Parameters:
        -----------
        entity_id : str
            エンティティID
        previous_ranking : int
            前回のランキング
        current_ranking : int
            今回のランキング

        Returns:
        --------
        Optional[Dict]
            ランキング変化データ（閾値を超えた場合のみ）
        """
        try:
            ranking_change = abs(current_ranking - previous_ranking)

            # 閾値を超えた場合のみ変化として記録
            if ranking_change >= self.thresholds["ranking_change"]:
                change_type = "improved" if current_ranking < previous_ranking else "declined"

                return {
                    "entity": entity_id,
                    "type": change_type,
                    "metric": "ranking",
                    "previous_value": previous_ranking,
                    "current_value": current_ranking,
                    "change_rate": ranking_change,
                    "significance": self._get_significance_level(ranking_change * 10)  # ランキング変化をスケール調整
                }

            return None

        except Exception as e:
            logger.error(f"ランキング変化計算エラー ({entity_id}): {e}")
            return None

    def _get_significance_level(self, change_rate: float) -> str:
        """
        変化の重要度レベルを判定

        Parameters:
        -----------
        change_rate : float
            変化率

        Returns:
        --------
        str
            重要度レベル（"high", "medium", "low"）
        """
        if change_rate >= 50:
            return "high"
        elif change_rate >= 20:
            return "medium"
        else:
            return "low"

    def _get_significance_score(self, change: Dict) -> float:
        """
        変化の重要度スコアを計算（ソート用）

        Parameters:
        -----------
        change : Dict
            変化データ

        Returns:
        --------
        float
            重要度スコア
        """
        significance_weights = {"high": 3, "medium": 2, "low": 1}
        base_score = significance_weights.get(change.get("significance", "low"), 1)

        # 変化率も考慮
        change_rate = change.get("change_rate", 0)
        return base_score * (1 + change_rate / 100)

    def update_thresholds(self, new_thresholds: Dict):
        """
        閾値を更新

        Parameters:
        -----------
        new_thresholds : Dict
            新しい閾値設定
        """
        self.thresholds.update(new_thresholds)
        logger.info(f"閾値を更新しました: {self.thresholds}")

    def get_thresholds(self) -> Dict:
        """
        現在の閾値を取得

        Returns:
        --------
        Dict
            現在の閾値設定
        """
        return self.thresholds.copy()