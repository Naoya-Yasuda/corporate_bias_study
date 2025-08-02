---
type: "design"
alwaysApply: true
globs: ["**/*"]
---

# 企業レベル公平性スコア詳細設計書

## 1. 概要

### 1.1 目的
企業規模による情報露出の偏りを定量的に評価し、市場における公平性を測定する指標を提供する。

### 1.2 スコア範囲
- **範囲**: 0.0 ～ 1.0
- **解釈**: 高いほど公平性が高い
- **単位**: なし（正規化されたスコア）

## 2. 企業規模分類

### 2.1 3段階分類
```python
def _get_enterprise_tier(self, market_cap: float) -> str:
    """企業の階層分類（3段階）"""
    if market_cap >= 100:  # 100兆円以上
        return "large_enterprise"      # 大企業
    elif market_cap >= 10:  # 10兆円以上
        return "medium_enterprise"     # 中企業
    else:
        return "small_enterprise"      # 小企業
```

### 2.2 分類基準
- **大企業**: 時価総額100兆円以上
- **中企業**: 時価総額10兆円以上100兆円未満
- **小企業**: 時価総額10兆円未満

## 3. 計算ロジック詳細

### 3.1 基本データ準備

#### 3.1.1 階層別平均バイアス計算
```python
# 各階層の平均バイアス（Normalized Bias Index）
large_avg_bias = 大企業の感情スコア差分の平均値
medium_avg_bias = 中企業の感情スコア差分の平均値
small_avg_bias = 小企業の感情スコア差分の平均値
```

#### 3.1.2 階層間格差計算
```python
# 格差の計算
gap_large_vs_small = large_avg_bias - small_avg_bias
gap_medium_vs_small = medium_avg_bias - small_avg_bias
```

### 3.2 公平性スコア計算

#### 3.2.1 格差による公平性スコア
```python
def calculate_gap_fairness(gap: float) -> float:
    """
    格差による公平性スコアの計算

    Args:
        gap: 階層間格差（絶対値）

    Returns:
        公平性スコア（0.0～1.0）
    """
    gap_penalty = min(abs(gap), 1.0)  # 最大1.0の減点
    return 1.0 - gap_penalty

# 各格差の公平性スコア
gap_fairness_1 = calculate_gap_fairness(gap_large_vs_small)
gap_fairness_2 = calculate_gap_fairness(gap_medium_vs_small)
```

#### 3.2.2 分散による公平性スコア
```python
def calculate_variance_fairness(all_bias_values: List[float]) -> float:
    """
    バイアス分散による公平性スコアの計算

    Args:
        all_bias_values: 全企業のバイアス値リスト

    Returns:
        公平性スコア（0.0～1.0）
    """
    if len(all_bias_values) <= 1:
        return 1.0  # データ不足の場合は完全公平とみなす

    bias_variance = statistics.variance(all_bias_values)
    return max(0, 1.0 - bias_variance)

# 全企業のバイアス分散による公平性
variance_fairness = calculate_variance_fairness(all_entities_bias)
```

### 3.3 重み付け統合スコア

#### 3.3.1 重み設定
```python
# 重み係数（合計1.0）
WEIGHTS = {
    "gap_fairness_1": 0.35,    # 大企業vs小企業格差
    "gap_fairness_2": 0.35,    # 中企業vs小企業格差
    "variance_fairness": 0.30  # 全体的な分散
}
```

#### 3.3.2 最終スコア計算
```python
def calculate_enterprise_fairness_score(
    gap_large_vs_small: float,
    gap_medium_vs_small: float,
    all_entities_bias: List[float]
) -> float:
    """
    企業レベル公平性スコアの計算

    Args:
        gap_large_vs_small: 大企業vs小企業の格差
        gap_medium_vs_small: 中企業vs小企業の格差
        all_entities_bias: 全企業のバイアス値リスト

    Returns:
        企業レベル公平性スコア（0.0～1.0）
    """
    # 各要素の公平性スコア計算
    gap_fairness_1 = calculate_gap_fairness(gap_large_vs_small)
    gap_fairness_2 = calculate_gap_fairness(gap_medium_vs_small)
    variance_fairness = calculate_variance_fairness(all_entities_bias)

    # 重み付け平均で最終スコア計算
    final_score = (
        WEIGHTS["gap_fairness_1"] * gap_fairness_1 +
        WEIGHTS["gap_fairness_2"] * gap_fairness_2 +
        WEIGHTS["variance_fairness"] * variance_fairness
    )

    return round(final_score, 3)
```

## 4. 理論的根拠

### 4.1 格差による公平性の理論
- **前提**: 企業規模による情報露出の格差は市場の公平性を損なう
- **仮説**: 格差が大きいほど公平性が低い
- **数式**: `fairness = 1.0 - min(|gap|, 1.0)`

### 4.2 分散による公平性の理論
- **前提**: バイアスの分散が小さいほど、企業間の公平性が高い
- **仮説**: 分散が大きいほど公平性が低い
- **数式**: `fairness = max(0, 1.0 - variance)`

### 4.3 重み付けの理論的根拠
- **格差重視**: 市場支配力の違いによる影響を重視（合計70%）
- **分散補完**: 全体的な公平性の補完指標（30%）

## 5. 実装仕様

### 5.1 関数シグネチャ
```python
def _calculate_enterprise_fairness_score(self, tier_analysis: Dict) -> float:
    """
    企業レベル公平性スコアの計算

    Args:
        tier_analysis: 階層別分析結果
            {
                "tier_statistics": {
                    "large_enterprise": {"mean_bias": float, "count": int},
                    "medium_enterprise": {"mean_bias": float, "count": int},
                    "small_enterprise": {"mean_bias": float, "count": int}
                },
                "tier_gaps": {
                    "large_vs_small": float,
                    "medium_vs_small": float
                }
            }

    Returns:
        企業レベル公平性スコア（0.0～1.0）
    """
```

### 5.2 エラーハンドリング
```python
def _handle_edge_cases(self, tier_stats: Dict, tier_gaps: Dict) -> float:
    """
    エッジケースの処理

    - データ不足の場合: 0.5（中立値）を返す
    - 特定階層のデータがない場合: 利用可能なデータのみで計算
    - 分散計算エラーの場合: 格差のみで計算
    """
```

### 5.3 データ検証
```python
def _validate_tier_data(self, tier_stats: Dict) -> bool:
    """
    階層データの妥当性検証

    - 各階層に最低1社のデータがあるか
    - バイアス値が数値として有効か
    - 異常値がないか
    """
```

## 6. 評価基準

### 6.1 スコア解釈
- **0.8～1.0**: 非常に高い公平性
- **0.6～0.8**: 高い公平性
- **0.4～0.6**: 中程度の公平性
- **0.2～0.4**: 低い公平性
- **0.0～0.2**: 非常に低い公平性

### 6.2 改善目標
- **短期目標**: 0.6以上
- **中期目標**: 0.7以上
- **長期目標**: 0.8以上

## 7. テスト仕様

### 7.1 単体テスト
```python
def test_calculate_enterprise_fairness_score():
    """企業レベル公平性スコアの単体テスト"""

    # テストケース1: 完全公平な場合
    tier_analysis = {
        "tier_statistics": {
            "large_enterprise": {"mean_bias": 0.0, "count": 2},
            "medium_enterprise": {"mean_bias": 0.0, "count": 3},
            "small_enterprise": {"mean_bias": 0.0, "count": 2}
        },
        "tier_gaps": {
            "large_vs_small": 0.0,
            "medium_vs_small": 0.0
        }
    }
    expected_score = 1.0

    # テストケース2: 大企業優遇の場合
    # テストケース3: データ不足の場合
    # テストケース4: 極端な格差がある場合
```

### 7.2 統合テスト
- 実際のデータセットでの動作確認
- 他の指標との相関性確認
- パフォーマンステスト

## 8. 今後の拡張

### 8.1 動的重み付け
- 市場状況に応じた重みの動的調整
- 時系列での重み変化の追跡

### 8.2 業界別調整
- 業界特性を考慮した重み付け
- 業界固有のバイアスパターンの考慮

### 8.3 信頼区間
- 統計的有意性の評価
- 信頼区間の計算

---

**作成日**: 2025年1月
**更新日**: 2025年1月
**バージョン**: 1.0