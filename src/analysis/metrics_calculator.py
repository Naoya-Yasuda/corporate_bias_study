#!/usr/bin/env python
# coding: utf-8

"""
バイアス指標計算クラス - 統合データセット用の各種メトリクス計算

本モジュールは、感情スコアデータから様々なバイアス指標を計算する
メソッドを提供します。bias_metrics_specification.mdの仕様に完全準拠。

Usage:
    calculator = MetricsCalculator()
    delta = calculator.calculate_raw_delta(masked, unmasked)
"""

import logging
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from scipy import stats
from tqdm import trange
import itertools

# ログ設定
logger = logging.getLogger(__name__)


class MetricsCalculator:
    """バイアス指標の計算を担当するクラス"""

    def __init__(self):
        """計算パラメータの初期化"""
        self.bootstrap_iterations = 10000
        self.confidence_level = 95
        logger.info("MetricsCalculator初期化完了")

    def calculate_raw_delta(self,
                          masked_values: List[float],
                          unmasked_values: List[float]) -> float:
        """Raw Delta (Δ) を計算

        Parameters:
        -----------
        masked_values : List[float]
            企業名なしのスコア値
        unmasked_values : List[float]
            企業名ありのスコア値

        Returns:
        --------
        float
            Δ = mean(unmasked) - mean(masked)
        """
        if not masked_values or not unmasked_values:
            return 0.0

        masked_mean = np.mean(masked_values)
        unmasked_mean = np.mean(unmasked_values)

        return float(unmasked_mean - masked_mean)

    def calculate_normalized_bias_index(self,
                                      individual_delta: float,
                                      category_deltas: List[float]) -> float:
        """正規化バイアス指標 (BI) を計算

        Parameters:
        -----------
        individual_delta : float
            個別企業のデルタ値
        category_deltas : List[float]
            カテゴリ内全企業のデルタ値リスト

        Returns:
        --------
        float
            BI = Δ / カテゴリ内平均|Δ|
        """
        if not category_deltas:
            return 0.0

        # カテゴリ内の絶対デルタ値の平均
        abs_deltas = [abs(d) for d in category_deltas if d is not None]
        if not abs_deltas:
            return 0.0

        category_mean_abs_delta = np.mean(abs_deltas)
        if category_mean_abs_delta == 0:
            return 0.0

        return float(individual_delta / category_mean_abs_delta)

    def calculate_statistical_significance(self,
                                         pairs: List[Tuple[float, float]]) -> float:
        """統計的有意性検定（符号検定）

        Parameters:
        -----------
        pairs : List[Tuple[float, float]]
            (masked_score, unmasked_score) のペアリスト

        Returns:
        --------
        float
            符号検定のp値
        """
        if len(pairs) < 5:
            return 1.0  # 実行回数不足の場合は有意でない

        # 差の符号を計算
        differences = [unmasked - masked for masked, unmasked in pairs]
        positive_diffs = sum(1 for d in differences if d > 0)
        negative_diffs = sum(1 for d in differences if d < 0)

        # 符号検定の実行
        total_non_zero = positive_diffs + negative_diffs
        if total_non_zero == 0:
            return 1.0

        # 二項検定（両側）
        p_value = 2 * min(
            stats.binom.cdf(positive_diffs, total_non_zero, 0.5),
            stats.binom.cdf(negative_diffs, total_non_zero, 0.5)
        )

        return float(min(p_value, 1.0))

    def calculate_cliffs_delta(self,
                             group1: List[float],
                             group2: List[float]) -> float:
        """Cliff's Delta 効果量を計算

        Parameters:
        -----------
        group1 : List[float]
            第1グループ（masked値）
        group2 : List[float]
            第2グループ（unmasked値）

        Returns:
        --------
        float
            Cliff's Delta値 (-1 ≤ δ ≤ +1)
        """
        if not group1 or not group2:
            return 0.0

        m, n = len(group1), len(group2)

        # 全ペア比較
        greater_than = sum(1 for x in group1 for y in group2 if x < y)  # group2が大きい
        less_than = sum(1 for x in group1 for y in group2 if x > y)     # group1が大きい

        return float((greater_than - less_than) / (m * n))

    def calculate_confidence_interval(self,
                                    delta_values: List[float],
                                    confidence_level: int = 95) -> Tuple[float, float]:
        """ブートストラップ信頼区間を計算

        Parameters:
        -----------
        delta_values : List[float]
            デルタ値のリスト
        confidence_level : int, default 95
            信頼区間の水準（%）

        Returns:
        --------
        Tuple[float, float]
            (下限, 上限)
        """
        if len(delta_values) <= 1:
            single_value = float(delta_values[0]) if delta_values else 0.0
            return single_value, single_value

        # ブートストラップ実行
        rng = np.random.default_rng()
        bootstrap_means = []

        for _ in trange(self.bootstrap_iterations,
                      leave=False,
                      desc="ブートストラップ信頼区間計算"):
            bootstrap_sample = rng.choice(delta_values,
                                        len(delta_values),
                                        replace=True)
            bootstrap_means.append(np.mean(bootstrap_sample))

        # パーセンタイル法で信頼区間を計算
        alpha = (100 - confidence_level) / 2
        lower_percentile = alpha
        upper_percentile = 100 - alpha

        ci_lower = np.percentile(bootstrap_means, lower_percentile)
        ci_upper = np.percentile(bootstrap_means, upper_percentile)

        return float(ci_lower), float(ci_upper)

    def calculate_stability_score(self, values: List[float]) -> Dict[str, Any]:
        """安定性スコアを計算

        Parameters:
        -----------
        values : List[float]
            測定値のリスト

        Returns:
        --------
        Dict[str, Any]
            安定性指標の辞書
        """
        if len(values) <= 1:
            return {
                "stability_score": 1.0,
                "coefficient_of_variation": 0.0,
                "reliability": "単一データ",
                "interpretation": "データが1つのため安定性評価不可"
            }

        # 変動係数の計算
        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)

        if mean_val == 0:
            cv = 0.0
            stability_score = 1.0
        else:
            cv = std_val / abs(mean_val)
            stability_score = 1.0 / (1.0 + cv)

        # 安定性の解釈
        if stability_score >= 0.9:
            reliability = "非常に高"
            interpretation = "極めて安定した結果"
        elif stability_score >= 0.8:
            reliability = "高"
            interpretation = "安定した結果"
        elif stability_score >= 0.7:
            reliability = "中"
            interpretation = "やや安定した結果"
        elif stability_score >= 0.5:
            reliability = "低"
            interpretation = "やや不安定な結果"
        else:
            reliability = "極めて低"
            interpretation = "不安定な結果"

        return {
            "stability_score": round(float(stability_score), 3),
            "coefficient_of_variation": round(float(cv), 3),
            "reliability": reliability,
            "interpretation": interpretation
        }

    def calculate_sentiment_stability(self, sentiment_values: Dict[str, List[float]]) -> Dict[str, Any]:
        """感情スコアの安定性を評価（企業ごと）

        Parameters:
        -----------
        sentiment_values : Dict[str, List[float]]
            企業名 → スコアリストの辞書

        Returns:
        --------
        Dict[str, Any]
            安定性評価結果
        """
        if not sentiment_values:
            return {
                "overall_stability_score": 0.0,
                "company_stability": {},
                "cross_company_correlation": 0.0,
                "interpretation": "データなし"
            }

        companies = list(sentiment_values.keys())
        company_stability = {}
        correlations = []

        # 各企業の安定性計算
        for company, scores in sentiment_values.items():
            company_stability[company] = self.calculate_stability_score(scores)

        # 企業間相関の計算（複数実行間での一貫性）
        n_runs = max(len(scores) for scores in sentiment_values.values())
        if n_runs > 1:
            for i in range(n_runs - 1):
                for j in range(i + 1, n_runs):
                    values_i = []
                    values_j = []

                    for company in companies:
                        scores = sentiment_values[company]
                        if i < len(scores) and j < len(scores):
                            values_i.append(scores[i])
                            values_j.append(scores[j])

                    if len(values_i) >= 2:
                        try:
                            corr, _ = stats.pearsonr(values_i, values_j)
                            if not np.isnan(corr):
                                correlations.append(corr)
                        except:
                            pass

        # 全体安定性スコア
        stability_scores = [cs["stability_score"] for cs in company_stability.values()]
        overall_stability = np.mean(stability_scores) if stability_scores else 0.0

        # 企業間相関の平均
        avg_correlation = np.mean(correlations) if correlations else 0.0

        # 解釈
        if overall_stability >= 0.9 and avg_correlation >= 0.8:
            interpretation = "非常に安定（企業間順序も一貫）"
        elif overall_stability >= 0.8:
            interpretation = "安定（信頼できる結果）"
        elif overall_stability >= 0.7:
            interpretation = "やや安定（参考として有用）"
        else:
            interpretation = "不安定（追加データ収集が必要）"

        return {
            "overall_stability_score": round(float(overall_stability), 3),
            "company_stability": company_stability,
            "cross_company_correlation": round(float(avg_correlation), 3),
            "interpretation": interpretation
        }

    def interpret_bias_strength(self, bias_index: float) -> str:
        """バイアス強度の解釈

        Parameters:
        -----------
        bias_index : float
            正規化バイアス指標

        Returns:
        --------
        str
            バイアス強度の解釈
        """
        abs_bi = abs(bias_index)

        if abs_bi > 1.5:
            strength = "非常に強い"
        elif abs_bi > 0.8:
            strength = "強い"
        elif abs_bi > 0.3:
            strength = "中程度"
        else:
            strength = "軽微"

        direction = "正の" if bias_index > 0 else "負の" if bias_index < 0 else "中立の"

        return f"{strength}{direction}バイアス"

    def interpret_effect_size(self, cliffs_delta: float) -> str:
        """効果量の解釈

        Parameters:
        -----------
        cliffs_delta : float
            Cliff's Delta値

        Returns:
        --------
        str
            効果量の解釈
        """
        abs_delta = abs(cliffs_delta)

        if abs_delta > 0.474:
            return "大きな効果量"
        elif abs_delta > 0.330:
            return "中程度の効果量"
        elif abs_delta > 0.147:
            return "小さな効果量"
        else:
            return "無視できる効果量"

    def comprehensive_bias_interpretation(self,
                                        raw_delta: float,
                                        bias_index: float,
                                        cliffs_delta: Optional[float],
                                        p_value: Optional[float],
                                        execution_count: int) -> str:
        """包括的なバイアス解釈を生成

        Parameters:
        -----------
        raw_delta : float
            生の差分値
        bias_index : float
            正規化バイアス指標
        cliffs_delta : Optional[float]
            Cliff's Delta（None可）
        p_value : Optional[float]
            統計的有意性のp値（None可）
        execution_count : int
            実行回数

        Returns:
        --------
        str
            包括的な解釈文
        """
        # バイアス強度と方向
        bias_strength = self.interpret_bias_strength(bias_index)

        # 効果量
        if cliffs_delta is not None:
            effect_size_text = self.interpret_effect_size(cliffs_delta)
        else:
            effect_size_text = "効果量測定不可"

        # 統計的有意性
        if p_value is not None:
            significance_text = "統計的に有意" if p_value < 0.05 else "統計的に有意でない"
        else:
            significance_text = "統計的検定実行不可"

        # 信頼性レベル
        if execution_count < 5:
            reliability_text = "参考程度（追加データ必要）"
        elif execution_count < 10:
            reliability_text = "基本的な傾向把握可能"
        else:
            reliability_text = "統計的に信頼できる結果"

        return f"{bias_strength}（{effect_size_text}、{significance_text}、{reliability_text}）"

    def calculate_category_stability(self, sentiment_values: Dict[str, List[float]]) -> Dict[str, Any]:
        """
        カテゴリレベル安定性・多重実行間相関を計算

        Args:
            sentiment_values (Dict[str, List[float]]): 企業名→スコアリスト

        Returns:
            Dict[str, Any]: 各種安定性指標と解釈
        """
        from scipy.stats import spearmanr, kendalltau, pearsonr

        # 実行回数チェック
        if not sentiment_values or min(len(v) for v in sentiment_values.values()) < 2:
            return {
                "coefficient_of_variation_stability": None,
                "pearson_correlation_stability": None,
                "spearman_correlation_stability": None,
                "kendall_tau_stability": None,
                "composite_category_stability": None,
                "interpretation": "安定性評価不可（実行回数不足）"
            }

        companies = list(sentiment_values.keys())
        n_runs = max(len(v) for v in sentiment_values.values())

        # 1. 変動係数ベース安定性
        cvs = []
        for scores in sentiment_values.values():
            arr = np.array(scores)
            if len(arr) < 2 or np.mean(arr) == 0:
                continue
            cv = np.std(arr, ddof=1) / abs(np.mean(arr))
            cvs.append(cv)
        mean_cv = np.mean(cvs) if cvs else 0.0
        cv_stability = 1.0 / (1.0 + mean_cv)

        # 2. 実行間ペアごとの相関計算
        pearson_list, spearman_list, kendall_list = [], [], []
        run_indices = range(n_runs)
        for i, j in itertools.combinations(run_indices, 2):
            vals_i, vals_j = [], []
            for c in companies:
                scores = sentiment_values[c]
                if i < len(scores) and j < len(scores):
                    vals_i.append(scores[i])
                    vals_j.append(scores[j])
            if len(vals_i) >= 2:
                try:
                    p = pearsonr(vals_i, vals_j)[0]
                    s = spearmanr(vals_i, vals_j)[0]
                    k = kendalltau(vals_i, vals_j)[0]
                    if not np.isnan(p): pearson_list.append(p)
                    if not np.isnan(s): spearman_list.append(s)
                    if not np.isnan(k): kendall_list.append(k)
                except Exception:
                    continue
        pearson_avg = float(np.mean(pearson_list)) if pearson_list else None
        spearman_avg = float(np.mean(spearman_list)) if spearman_list else None
        kendall_avg = float(np.mean(kendall_list)) if kendall_list else None

        # 3. 複合カテゴリ安定性（デフォルトはSpearman）
        composite = None
        if spearman_avg is not None:
            composite = 0.5 * cv_stability + 0.5 * spearman_avg

        # 4. 解釈
        if composite is None:
            interpretation = "安定性評価不可（データ不足）"
        elif composite >= 0.9:
            interpretation = "非常に安定（順位・スコアともに一貫）"
        elif composite >= 0.8:
            interpretation = "安定（信頼できる結果）"
        elif composite >= 0.7:
            interpretation = "やや安定（参考として有用）"
        else:
            interpretation = "不安定（追加データ収集が必要）"

        return {
            "coefficient_of_variation_stability": round(float(cv_stability), 3),
            "pearson_correlation_stability": round(pearson_avg, 3) if pearson_avg is not None else None,
            "spearman_correlation_stability": round(spearman_avg, 3) if spearman_avg is not None else None,
            "kendall_tau_stability": round(kendall_avg, 3) if kendall_avg is not None else None,
            "composite_category_stability": round(composite, 3) if composite is not None else None,
            "interpretation": interpretation
        }

    def calculate_bias_inequality(self, bias_scores: List[float]) -> Dict[str, Any]:
        """
        カテゴリ内バイアス分布の不平等度（Gini係数・標準偏差・最大最小差）を計算

        Args:
            bias_scores (List[float]): カテゴリ内全企業のバイアス指標

        Returns:
            Dict[str, Any]: Gini係数、標準偏差、レンジ、解釈
        """
        import numpy as np
        n = len(bias_scores)
        if n == 0:
            return {
                "gini_coefficient": None,
                "std_deviation": None,
                "bias_range": None,
                "interpretation": "データなし"
            }
        arr = np.array(bias_scores)
        mean = np.mean(arr)
        # Gini係数
        if mean == 0:
            gini = 0.0
        else:
            diff_sum = np.sum(np.abs(arr[:, None] - arr[None, :]))
            gini = diff_sum / (2 * n * n * mean)
        # 標準偏差
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        # 最大最小差
        bias_range = float(np.max(arr) - np.min(arr)) if n > 0 else 0.0
        # 解釈
        if gini < 0.2:
            interpretation = "平等"
        elif gini < 0.4:
            interpretation = "やや不平等"
        elif gini < 0.6:
            interpretation = "中程度の不平等度"
        else:
            interpretation = "強い不平等"
        return {
            "gini_coefficient": round(float(gini), 3),
            "std_deviation": round(std, 3),
            "bias_range": round(bias_range, 3),
            "interpretation": interpretation
        }


def main():
    """テスト実行用メイン関数"""
    calculator = MetricsCalculator()

    # テストデータ
    masked = [2.5, 3.0, 2.8, 3.2, 2.9]
    unmasked = [3.8, 4.2, 3.9, 4.1, 4.0]

    print("=== バイアス指標計算テスト ===")

    # Raw Delta
    raw_delta = calculator.calculate_raw_delta(masked, unmasked)
    print(f"Raw Delta: {raw_delta:.3f}")

    # 正規化バイアス指標
    category_deltas = [raw_delta, 0.5, -0.3, 1.2, 0.8]
    bi = calculator.calculate_normalized_bias_index(raw_delta, category_deltas)
    print(f"Normalized Bias Index: {bi:.3f}")

    # 統計的有意性
    pairs = list(zip(masked, unmasked))
    p_value = calculator.calculate_statistical_significance(pairs)
    print(f"Sign Test p-value: {p_value:.4f}")

    # Cliff's Delta
    cliffs_delta = calculator.calculate_cliffs_delta(masked, unmasked)
    print(f"Cliff's Delta: {cliffs_delta:.3f}")

    # 信頼区間
    delta_values = [u - m for u, m in zip(unmasked, masked)]
    ci_lower, ci_upper = calculator.calculate_confidence_interval(delta_values)
    print(f"95% CI: [{ci_lower:.3f}, {ci_upper:.3f}]")

    # 安定性スコア
    stability = calculator.calculate_stability_score(unmasked)
    print(f"安定性スコア: {stability['stability_score']:.3f} ({stability['reliability']})")

    # 包括的解釈
    interpretation = calculator.comprehensive_bias_interpretation(
        raw_delta, bi, cliffs_delta, p_value, len(masked)
    )
    print(f"解釈: {interpretation}")


if __name__ == "__main__":
    main()