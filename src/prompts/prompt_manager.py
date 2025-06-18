#!/usr/bin/env python
# coding: utf-8

"""
プロンプト管理モジュール
プロンプトの一元管理と動的生成を担当するモジュール
"""

import os
import yaml
from typing import Dict, Optional, List

class PromptManager:
    """プロンプトの一元管理と動的生成を担当するクラス"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Parameters
        ----------
        config_path : str, optional
            プロンプト設定ファイルのパス。指定がない場合はデフォルトパスを使用
        """
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "prompt_config.yml")

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """プロンプト設定ファイルを読み込む"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"プロンプト設定ファイルの読み込みに失敗しました: {e}")

    def get_sentiment_prompt(self, subcategory: str, masked: bool = True, competitor: Optional[str] = None) -> str:
        """
        感情評価用プロンプトを取得

        Parameters
        ----------
        subcategory : str
            サブカテゴリ名
        masked : bool, optional
            マスクありかどうか（デフォルト: True）
        competitor : str, optional
            競合サービス名（masked=Falseの場合に必要）

        Returns
        -------
        str
            生成されたプロンプト
        """
        if masked:
            template = self.config["sentiment"]["masked"]["template"]
            return template.format(subcategory=subcategory)
        else:
            if competitor is None:
                raise ValueError("competitorは必須です")
            template = self.config["sentiment"]["unmasked"]["template"]
            return template.format(subcategory=subcategory, competitor=competitor)

    def get_ranking_prompt(self, subcategory: str, services: List[str]) -> str:
        """
        ランキング抽出用プロンプトを取得

        Parameters
        ----------
        subcategory : str
            サブカテゴリ名
        services : List[str]
            サービス名のリスト

        Returns
        -------
        str
            生成されたプロンプト
        """
        template = self.config["ranking"]["template"]
        services_str = ", ".join(services)
        return template.format(subcategory=subcategory, services_str=services_str)

    def get_citations_summary_prompt(self, subcategory: str, services: List[str], answers: List[Dict]) -> str:
        """
        引用要約用プロンプトを取得

        Parameters
        ----------
        subcategory : str
            サブカテゴリ名
        services : List[str]
            サービス名のリスト
        answers : List[Dict]
            回答のリスト

        Returns
        -------
        str
            生成されたプロンプト
        """
        template = self.config["citations"]["summary"]["template"]
        services_str = ", ".join(services)
        max_length = self.config["citations"]["summary"]["max_length"]
        snippet_length = self.config["citations"]["summary"]["answer_snippet_length"]

        # 回答を整形
        formatted_answers = []
        current_length = len(template)
        for i, answer in enumerate(answers):
            answer_snippet = f"\n--- 回答 {i+1} ---\n{answer['answer'][:snippet_length]}..."
            if current_length + len(answer_snippet) > max_length:
                formatted_answers.append("\n(回答の一部は長さの制限のため省略されました)")
                break
            formatted_answers.append(answer_snippet)
            current_length += len(answer_snippet)

        return template.format(
            num_answers=len(answers),
            subcategory=subcategory,
            services_str=services_str,
            answers="".join(formatted_answers)
        )

    def get_sentiment_analysis_prompt(self, texts: List[str]) -> str:
        """
        感情分析用プロンプトを取得

        Parameters
        ----------
        texts : List[str]
            分析対象のテキストリスト

        Returns
        -------
        str
            生成されたプロンプト
        """
        template = self.config["sentiment_analysis"]["template"]
        numbered_texts = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
        return template.format(numbered_texts=numbered_texts)

    def get_score_pattern(self) -> str:
        """
        感情スコア抽出用の正規表現パターンを取得

        Returns
        -------
        str
            正規表現パターン
        """
        return self.config["sentiment"]["masked"]["score_pattern"]

    def get_rank_patterns(self) -> List[str]:
        """
        ランキング抽出用の正規表現パターンリストを取得

        Returns
        -------
        List[str]
            正規表現パターンのリスト
        """
        return self.config["ranking"]["rank_patterns"]