---
type: "design"
alwaysApply: true
globs: ["**/*"]
---

# サービスレベル公平性スコア 階層的評価型詳細設計書

## 概要

本設計書では、NBI（Normalized Bias Index）と市場データを基にした階層的評価型サービスレベル公平性スコアの詳細仕様を定義します。市場シェアによる重み付けと全体の一貫性評価を組み合わせた、より本質的な公平性評価指標です。

## 1. 設計方針

### 1.1 基本コンセプト

サービスレベル公平性スコアは、各サービスの市場シェアに対してAI検索結果の露出度がどれだけ公平かを示す指標です。階層的評価型では以下の3段階で評価します：

1. **個別サービス公平性**: 各サービスのバイアス指標による個別評価
2. **市場構造重み付け**: 市場シェアによる重み付け
3. **全体一貫性評価**: 全サービス間のバイアス一貫性

### 1.2 技術的優位性

- **市場シェア反映**: 大きな市場シェアを持つサービスの影響を適切に反映
- **階層的評価**: 個別評価と全体評価の明確な分離
- **解釈可能性**: 各ステップの意味が明確で理解しやすい
- **実装の簡潔性**: 複雑すぎず、保守性が高い
- **統計的妥当性**: 分散分析による一貫性評価

## 2. 計算式詳細

### 2.1 ステップ1: 個別サービス公平性

各サービスのバイアス指標に基づく個別公平性を評価します。

```python
def calculate_individual_fairness(service_bias_data: List[Dict]) -> List[float]:
    """個別サービス公平性計算"""
    individual_scores = []

    for item in service_bias_data:
        bias_index = item.get("normalized_bias_index", 0)
        market_share = item.get("normalized_share", 0)

        if market_share > 0:
            # バイアス値の絶対値による減点
            bias_penalty = min(1.0, abs(bias_index))
            individual_score = 1.0 - bias_penalty
            individual_scores.append(individual_score)

    return individual_scores
```

**計算ロジック**:
- バイアス指標の絶対値に基づく減点
- 最大減点を1.0に制限（完全に0になることを防止）
- 市場シェアが0より大きいサービスのみを対象

**理論的根拠**:
- バイアス指標が0に近いほど公平性が高い
- 絶対値を使用することで、正負のバイアスを同等に評価
- 1.0の上限により異常値への耐性を確保

### 2.2 ステップ2: 市場構造による重み付け

市場シェアに基づいて個別公平性スコアに重みを付けます。

```python
def calculate_weighted_fairness(service_bias_data: List[Dict], individual_scores: List[float]) -> float:
    """市場構造による重み付け公平性計算"""

    if not individual_scores:
        return 0.0

    # 総市場シェアの計算
    total_share = sum(item.get("normalized_share", 0) for item in service_bias_data)
    if total_share <= 0:
        return statistics.mean(individual_scores)

    # 重み付けスコアの計算
    weighted_scores = []
    score_index = 0

    for item in service_bias_data:
        market_share = item.get("normalized_share", 0)
        if market_share > 0:
            weight = market_share / total_share
            weighted_scores.append(individual_scores[score_index] * weight)
            score_index += 1

    return sum(weighted_scores)
```

**計算ロジック**:
- 各サービスの市場シェアを総市場シェアで正規化
- 個別公平性スコアに市場シェアの重みを乗算
- 重み付けされたスコアの合計を算出

**理論的根拠**:
- 大きな市場シェアを持つサービスの影響を重視
- 市場構造を反映した相対的評価
- 経済的影響度に基づく重み付け

### 2.3 ステップ3: 全体の一貫性評価

全サービス間のバイアス一貫性を評価します。

```python
def calculate_consistency_score(service_bias_data: List[Dict]) -> float:
    """全体一貫性スコア計算"""

    if len(service_bias_data) < 2:
        return 1.0

    # バイアス指標の抽出
    biases = [item.get("normalized_bias_index", 0) for item in service_bias_data]

    # バイアス分散の計算
    bias_variance = statistics.variance(biases)

    # 一貫性スコアの計算（分散が小さいほど一貫性が高い）
    consistency_score = max(0.0, 1.0 - bias_variance)

    return consistency_score
```

**計算ロジック**:
- 全サービスのバイアス指標の分散を算出
- 分散が小さいほど一貫性が高い（1.0に近い）
- 分散が大きいほど一貫性が低い（0.0に近い）

**理論的根拠**:
- サービス間でバイアスに大きな格差がある場合、公平性が低い
- 分散による統計的根拠に基づく評価
- 全体の一貫性を定量的に測定

### 2.4 統合スコア計算

3つのステップを統合して最終スコアを算出します。

```python
def calculate_service_level_fairness_hierarchical(service_bias_data: List[Dict]) -> float:
    """サービスレベル公平性スコア計算（階層的評価型）"""

    if not service_bias_data:
        return 0.0

    # ステップ1: 個別サービス公平性
    individual_scores = calculate_individual_fairness(service_bias_data)

    if not individual_scores:
        return 0.0

    # ステップ2: 市場構造による重み付け
    weighted_fairness = calculate_weighted_fairness(service_bias_data, individual_scores)

    # ステップ3: 全体の一貫性評価
    consistency_score = calculate_consistency_score(service_bias_data)

    # 最終スコア: 重み付け個別スコア × 一貫性スコア
    final_score = weighted_fairness * consistency_score

    return round(final_score, 3)
```

## 3. 計算式の理論的根拠

### 3.1 乗算統合の理由

最終スコアを加算ではなく乗算で統合する理由：

1. **厳格性**: どちらか一方が低い場合、全体スコアも低くなる
2. **相乗効果**: 個別公平性と一貫性の両方が高い場合のみ高スコア
3. **解釈可能性**: 各要素の寄与度が明確

### 3.2 重み付けの理論的根拠

市場シェアによる重み付けの根拠：

1. **経済的影響度**: 大きな市場シェアを持つサービスの不公平性は社会的影響が大きい
2. **市場構造反映**: 実際の市場構造を評価に反映
3. **相対的重要性**: 市場における各サービスの相対的重要性を考慮

## 4. スコアの解釈

### 4.1 スコア範囲

- **0.8～1.0**: 非常に高い公平性
- **0.6～0.8**: 高い公平性
- **0.4～0.6**: 中程度の公平性
- **0.2～0.4**: 低い公平性
- **0.0～0.2**: 非常に低い公平性

### 4.2 解釈ガイドライン

- **重み付け公平性が低い場合**: 大きな市場シェアを持つサービスで不公平性が存在
- **一貫性スコアが低い場合**: サービス間でバイアスに大きな格差が存在
- **両方が低い場合**: 全体的に深刻な不公平性が存在

## 5. 実装上の注意点

### 5.1 データ要件

- 最低1つのサービスデータが必要
- 市場シェアが0より大きいサービスのみを対象
- バイアス指標（normalized_bias_index）が必須

### 5.2 エラーハンドリング

- データ不足時は0.0を返す
- 市場シェアが0の場合、そのサービスは評価対象外
- 分散計算エラー時は1.0（完全一貫性）を返す

### 5.3 パフォーマンス考慮

- 計算量: O(n) （n: サービス数）
- メモリ使用量: 最小限（データのコピーなし）
- 並列化可能性: 各ステップは独立して計算可能

## 6. 既存実装との比較

### 6.1 論文アプローチとの違い

- **重み付け**: 市場シェアによる重み付けを導入
- **一貫性評価**: 全体の一貫性を追加評価
- **乗算統合**: より厳格な統合方式

### 6.2 現在の実装との違い

- **階層的構造**: 明確な3段階評価
- **市場シェア反映**: 市場構造を評価に反映
- **解釈可能性**: 各ステップの意味が明確

## 7. 検証方法

### 7.1 単体テスト

```python
def test_hierarchical_fairness():
    """階層的公平性スコアのテスト"""

    # テストケース1: 完全公平
    test_data_1 = [
        {"normalized_bias_index": 0.0, "normalized_share": 0.5},
        {"normalized_bias_index": 0.0, "normalized_share": 0.5}
    ]
    score_1 = calculate_service_level_fairness_hierarchical(test_data_1)
    assert score_1 == 1.0

    # テストケース2: 不公平
    test_data_2 = [
        {"normalized_bias_index": 0.8, "normalized_share": 0.8},
        {"normalized_bias_index": -0.8, "normalized_share": 0.2}
    ]
    score_2 = calculate_service_level_fairness_hierarchical(test_data_2)
    assert score_2 < 0.5
```

### 7.2 実際データでの検証

- 既存データセットでの動作確認
- スコア分布の分析
- 異常値への耐性確認

## 8. 今後の拡張可能性

### 8.1 動的重み付け

市場構造の変化に応じて重みを動的に調整

### 8.2 時系列分析

時間経過による公平性の変化を追跡

### 8.3 業界別調整

業界特性に応じた調整係数の導入

## 9. 実装計画

### 9.1 Phase 1: 基本実装

- 階層的評価型計算関数の実装
- 単体テストの作成
- 既存関数との置き換え

### 9.2 Phase 2: 検証・調整

- 実際データでの動作確認
- パフォーマンス最適化
- ドキュメント更新

### 9.3 Phase 3: 統合・展開

- 既存システムへの統合
- 運用開始
- 継続的改善

---

**作成日**: 2025年1月
**更新日**: 2025年1月
**バージョン**: 1.0
**作成者**: AI Assistant