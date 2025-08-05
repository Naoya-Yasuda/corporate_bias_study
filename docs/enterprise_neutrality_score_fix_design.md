---
type: "design"
alwaysApply: true
globs: ["**/*"]
---

# 企業中立性スコア修正の詳細設計書

**作成日**: 2025年1月5日
**更新日**: 2025年1月5日
**バージョン**: 1.0
**担当者**: AI Assistant

## 1. 概要

### 1.1 目的
企業中立性スコアの計算ロジックにおける残存問題を解決し、より正確で論理的に一貫したスコア算出を実現する。

### 1.2 背景
現在の企業中立性スコア計算において、以下の問題が確認されている：
- 単一階層の場合に不適切なスコアが算出される
- 階層内格差と階層間格差の混同
- データ構造の理解不足による論理エラー

## 2. 現状の問題分析

### 2.1 問題の詳細

#### 2.1.1 単一階層の場合の不適切な処理
**問題**: 世界的テック企業（mega_enterprise階層のみ）の場合に、階層内格差（`max_min_gap: 1.167`）に基づいてスコアが計算されている。

**現在の動作**:
```json
{
  "enterprise_neutrality": 0.0
}
```

**期待される動作**:
```json
{
  "enterprise_neutrality": null
}
```

#### 2.1.2 階層内格差と階層間格差の混同
**問題**: `max_min_gap`は階層内での最大・最小バイアスの差を表しているが、企業中立性スコアでは階層間の格差を評価すべき。

**現在のデータ構造**:
```json
{
  "tier_gaps": {
    "max_min_gap": 1.167  // 階層内格差（最大バイアス1.653 - 最小バイアス0.486）
  }
}
```

**正しいデータ構造**:
```json
{
  "tier_gaps": {
    "large_vs_mid_gap": 0.418,  // 階層間格差
    "mega_vs_mid_gap": 0.583    // 階層間格差
  }
}
```

### 2.2 影響範囲
- 企業中立性スコアの信頼性低下
- 分析結果の解釈ミス
- データ品質の不整合

## 3. 解決策の設計

### 3.1 基本方針

#### 3.1.1 階層間格差の明確化
企業中立性スコアは、異なる企業階層間の格差を評価する指標として定義する。

**定義**:
- **階層間格差**: 異なる企業階層（mega_enterprise, large_enterprise, mid_enterprise等）間のバイアス格差
- **階層内格差**: 同一階層内での企業間バイアス格差

#### 3.1.2 単一階層の処理
単一階層が存在する場合（比較対象なし）は、企業中立性スコアを`null`として返す。

### 3.2 データ構造の修正

#### 3.2.1 tier_gapsの構造変更
現在の`max_min_gap`ベースから、階層間格差ベースに変更する。

**現在の構造**:
```json
{
  "tier_gaps": {
    "max_min_gap": 1.167
  }
}
```

**修正後の構造**:
```json
{
  "tier_gaps": {
    "large_vs_mid_gap": 0.418,
    "mega_vs_mid_gap": 0.583,
    "mega_vs_large_gap": 0.165
  }
}
```

#### 3.2.2 階層統計の活用
`tier_stats`の情報を活用して、階層間格差を計算する。

**tier_statsの例**:
```json
{
  "mega_enterprise": {
    "count": 5,
    "avg_bias": 1.069,
    "min_bias": 0.486,
    "max_bias": 1.653
  },
  "large_enterprise": {
    "count": 3,
    "avg_bias": 0.651,
    "min_bias": 0.235,
    "max_bias": 1.067
  }
}
```

### 3.3 計算ロジックの修正

#### 3.3.1 階層間格差の計算
```python
def _calculate_tier_gaps(self, tier_stats: Dict) -> Dict[str, float]:
    """
    階層間格差を計算する

    Args:
        tier_stats: 階層別統計データ

    Returns:
        Dict[str, float]: 階層間格差データ
    """
    gaps = {}
    tiers = list(tier_stats.keys())

    # 階層が1つ以下の場合は空の辞書を返す
    if len(tiers) <= 1:
        return gaps

    # 全階層間の組み合わせで格差を計算
    for i in range(len(tiers)):
        for j in range(i + 1, len(tiers)):
            tier1, tier2 = tiers[i], tiers[j]
            avg_bias1 = tier_stats[tier1]["avg_bias"]
            avg_bias2 = tier_stats[tier2]["avg_bias"]

            gap_key = f"{tier1}_vs_{tier2}_gap"
            gap_value = abs(avg_bias1 - avg_bias2)
            gaps[gap_key] = gap_value

    return gaps
```

#### 3.3.2 企業中立性スコアの修正
```python
def _calculate_enterprise_neutrality_score(self, tier_gaps: Dict) -> Optional[float]:
    """
    企業中立性スコアの計算（修正版）

    Args:
        tier_gaps: 階層間格差データ

    Returns:
        float: 中立性スコア（0.0-1.0、小数点以下3桁）
        None: 比較対象が存在しない場合（スコア算出不可）
    """
    # 1. 比較対象の存在確認
    if len(tier_gaps) == 0:
        return None  # 格差データが存在しない

    # 2. 有効な格差値の確認（0以外の値のみ）
    valid_gaps = [abs(gap_value) for gap_value in tier_gaps.values()
                  if gap_value is not None and gap_value != 0]

    if len(valid_gaps) == 0:
        return None  # 有効な格差値が存在しない

    # 3. 最大格差の計算
    max_gap = max(valid_gaps)

    # 4. 単一階層の場合の処理（格差が0の場合は比較対象なし）
    if max_gap == 0:
        return None  # 単一階層のため比較対象なし

    # 5. 中立性スコアの計算（小数点以下3桁に調整）
    neutrality_score = round(max(0, 1 - max_gap), 3)

    return neutrality_score
```

### 3.4 データフローの修正

#### 3.4.1 市場支配力分析の修正
`_analyze_enterprise_level_bias`メソッドで、階層間格差の計算を追加する。

```python
def _analyze_enterprise_level_bias(self, entities: Dict[str, Any],
                                 market_caps: Dict[str, Any],
                                 market_shares: Dict[str, Any],
                                 subcategory: str = None) -> Dict[str, Any]:
    """
    企業レベルバイアス分析（修正版）
    """
    # ... 既存のコード ...

    # 階層間格差の計算を追加
    tier_gaps = self._calculate_tier_gaps(tier_analysis["tier_stats"])
    tier_analysis["tier_gaps"] = tier_gaps

    # ... 既存のコード ...
```

## 4. 実装計画

### 4.1 Phase 1: データ構造の修正
**期間**: 1日
**内容**:
- `_calculate_tier_gaps`メソッドの実装
- `_analyze_enterprise_level_bias`メソッドの修正
- 階層間格差計算の統合

### 4.2 Phase 2: テストケースの更新
**期間**: 1日
**内容**:
- 新しいデータ構造に対応したテストケースの作成
- 単一階層ケースのテスト強化
- 階層間格差計算のテスト追加

### 4.3 Phase 3: 統合テスト
**期間**: 1日
**内容**:
- Dockerパイプラインでの動作確認
- 実際のデータでの結果検証
- パフォーマンステスト

## 5. 期待される効果

### 5.1 技術的効果
- 企業中立性スコアの論理的整合性向上
- データ構造の明確化
- 計算ロジックの透明性向上

### 5.2 ビジネス効果
- 分析結果の信頼性向上
- 意思決定の質向上
- ユーザー理解の促進

## 6. リスクと対策

### 6.1 技術的リスク
**リスク**: 既存の分析結果との整合性
**対策**: 段階的な移行と後方互換性の確保

### 6.2 データリスク
**リスク**: 階層間格差計算の精度
**対策**: 十分なテストと検証の実施

## 7. 成功指標

### 7.1 技術指標
- 単一階層の場合の`null`返却率: 100%
- 階層間格差計算の精度: 95%以上
- テストカバレッジ: 90%以上

### 7.2 品質指標
- 分析結果の論理的整合性: 100%
- ユーザー理解度の向上: 定性的評価

## 8. 今後の展開

### 8.1 短期（1ヶ月以内）
- 実装とテストの完了
- ドキュメントの更新
- ユーザーへの説明

### 8.2 中期（3ヶ月以内）
- 他の分析指標への適用検討
- パフォーマンス最適化
- 機能拡張の検討

---

**文書管理**:
- 作成者: AI Assistant
- 承認者: 未定
- 最終更新: 2025年1月5日