---
type: "design"
alwaysApply: true
globs: ["**/*"]
---

# 企業レベル公平性スコア再設計詳細書

## 1. 概要

### 1.1 背景
市場シェアデータが以下のように修正されたため、企業レベル公平性スコアの算出ロジックを再設計する必要があります：

- **修正前**: すべてのデータがパーセンテージ（0.0～1.0）で統一
- **修正後**: データタイプ別に異なる単位・範囲で管理
  - 市場シェア（%）: 0.0～1.0
  - 流通総額（億円）: 実数値
  - 月間アクティブユーザー数（万人）: 実数値
  - 利用率（%）: 0.0～1.0

### 1.2 再設計の目的
1. 異なるデータタイプに対応した公平性評価
2. データタイプ別の適切な正規化手法の実装
3. 統合的な公平性スコアの算出ロジック改善

## 2. データタイプ別対応方針

### 2.1 データタイプ分類

#### 2.1.1 比率系データ（0.0～1.0）
- **市場シェア（%）**: 既存ロジックを継続使用
- **利用率（%）**: 既存ロジックを継続使用

#### 2.1.2 絶対値系データ
- **流通総額（億円）**: 新規正規化ロジックが必要
- **月間アクティブユーザー数（万人）**: 新規正規化ロジックが必要

### 2.2 正規化手法の設計

#### 2.2.1 比率系データの処理
```python
def normalize_ratio_data(value: float) -> float:
    """比率系データの正規化（0.0～1.0）"""
    return max(0.0, min(1.0, value))
```

#### 2.2.2 絶対値系データの正規化
```python
def normalize_absolute_data(values: List[float], method: str = "min_max") -> List[float]:
    """
    絶対値系データの正規化

    Args:
        values: 正規化対象の値リスト
        method: 正規化手法 ("min_max", "z_score", "log_normal")

    Returns:
        正規化された値リスト（0.0～1.0）
    """
    if method == "min_max":
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            return [0.5] * len(values)  # 全値が同じ場合は中立値
        return [(v - min_val) / (max_val - min_val) for v in values]

    elif method == "z_score":
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values) if len(values) > 1 else 1.0
        z_scores = [(v - mean_val) / std_val for v in values]
        # Zスコアを0.0～1.0に変換
        min_z = min(z_scores)
        max_z = max(z_scores)
        if max_z == min_z:
            return [0.5] * len(values)
        return [(z - min_z) / (max_z - min_z) for z in z_scores]

    elif method == "log_normal":
        # 対数正規化（0や負の値を避けるため+1）
        log_values = [math.log(v + 1) for v in values]
        min_log = min(log_values)
        max_log = max(log_values)
        if max_log == min_log:
            return [0.5] * len(values)
        return [(log_v - min_log) / (max_log - min_log) for log_v in log_values]
```

## 3. 修正された公平性スコア算出ロジック

### 3.1 データタイプ別処理フロー

```python
def _analyze_service_level_bias_enhanced(self, entities: Dict[str, Any],
                                       market_shares: Dict[str, Any]) -> Dict[str, Any]:
    """拡張サービスレベルバイアス分析（データタイプ対応版）"""

    service_bias_data = []

    for category, services in market_shares.items():
        category_data = []

        # データタイプの判定
        data_type = self._determine_data_type(services)

        # データタイプ別の正規化処理
        normalized_shares = self._normalize_by_data_type(services, data_type)

        for service_name, service_data in services.items():
            if isinstance(service_data, dict):
                raw_share = self._extract_share_value(service_data)
                enterprise_name = service_data.get("enterprise")
                normalized_share = normalized_shares.get(service_name, 0.0)
            else:
                raw_share = service_data
                enterprise_name = None
                normalized_share = normalized_shares.get(service_name, 0.0)

            # エンティティ検索とバイアス計算
            entity_key, entity_data = self._find_entity_by_service_or_enterprise(service_name, entities)

            if entity_key and entity_data:
                bi = entity_data.get("basic_metrics", {}).get("normalized_bias_index", 0)

                category_data.append({
                    "service": service_name,
                    "mapped_entity": entity_key,
                    "category": category,
                    "data_type": data_type,
                    "raw_share": raw_share,
                    "normalized_share": normalized_share,
                    "normalized_bias_index": bi,
                    "fair_share_ratio": self._calculate_fair_share_ratio_enhanced(bi, normalized_share)
                })

        if category_data:
            service_bias_data.extend(category_data)

    return self._process_service_bias_analysis(service_bias_data)
```

### 3.2 データタイプ判定ロジック

```python
def _determine_data_type(self, services: Dict[str, Any]) -> str:
    """サービスデータのタイプを判定"""

    # サンプル値でデータタイプを判定
    sample_values = []
    for service_name, service_data in services.items():
        if isinstance(service_data, dict):
            value = self._extract_share_value(service_data)
        else:
            value = service_data
        sample_values.append(value)

    # 判定ロジック
    if all(0 <= v <= 1 for v in sample_values):
        return "ratio"  # 比率系
    elif any(v > 1000 for v in sample_values):
        return "monetary"  # 金額系（億円単位）
    elif any(v > 100 for v in sample_values):
        return "user_count"  # ユーザー数系（万人単位）
    else:
        return "unknown"
```

### 3.3 データタイプ別正規化

```python
def _normalize_by_data_type(self, services: Dict[str, Any], data_type: str) -> Dict[str, float]:
    """データタイプ別の正規化処理"""

    # 値の抽出
    values = {}
    for service_name, service_data in services.items():
        if isinstance(service_data, dict):
            value = self._extract_share_value(service_data)
        else:
            value = service_data
        values[service_name] = value

    # データタイプ別正規化
    if data_type == "ratio":
        # 比率系はそのまま使用
        return values

    elif data_type == "monetary":
        # 金額系は対数正規化
        return dict(zip(values.keys(),
                       self._normalize_absolute_data(list(values.values()), "log_normal")))

    elif data_type == "user_count":
        # ユーザー数系はmin-max正規化
        return dict(zip(values.keys(),
                       self._normalize_absolute_data(list(values.values()), "min_max")))

    else:
        # 不明な場合はmin-max正規化
        return dict(zip(values.keys(),
                       self._normalize_absolute_data(list(values.values()), "min_max")))
```

### 3.4 拡張Fair Share Ratio計算

```python
def _calculate_fair_share_ratio_enhanced(self, bias_index: float, normalized_share: float) -> float:
    """拡張公正シェア比率の計算（データタイプ対応版）"""

    if normalized_share <= 0:
        return 0.0

    # バイアス指標から期待露出度を逆算
    expected_exposure = normalized_share * (1 + bias_index)

    # 比率計算（理想値=1.0）
    fair_ratio = expected_exposure / normalized_share

    # 異常値の制限（0.1～10.0の範囲に制限）
    return max(0.1, min(10.0, fair_ratio))
```

## 4. 企業レベル公平性スコアの修正

### 4.1 階層別分析の拡張

```python
def _analyze_enterprise_tier_bias_enhanced(self, enterprise_bias_data: List[Dict]) -> Dict[str, Any]:
    """拡張企業階層別バイアス分析（データタイプ対応版）"""

    # データタイプ別の階層分析
    tier_analysis_by_type = {}

    for data_type in ["ratio", "monetary", "user_count"]:
        type_data = [item for item in enterprise_bias_data if item.get("data_type") == data_type]

        if type_data:
            tier_analysis_by_type[data_type] = self._analyze_tier_by_data_type(type_data)

    # 統合分析
    return self._integrate_tier_analysis(tier_analysis_by_type)
```

### 4.2 データタイプ別階層分析

```python
def _analyze_tier_by_data_type(self, tier_data: List[Dict]) -> Dict[str, Any]:
    """データタイプ別の階層分析"""

    # 階層別データの集約
    tier_stats = {"mega_enterprise": [], "large_enterprise": [], "mid_enterprise": []}

    for item in tier_data:
        tier = item.get("enterprise_tier", "mid_enterprise")
        if tier in tier_stats:
            tier_stats[tier].append(item)

    # 階層別統計計算
    tier_statistics = {}
    for tier, data in tier_stats.items():
        if data:
            biases = [item["normalized_bias_index"] for item in data]
            tier_statistics[tier] = {
                "count": len(data),
                "mean_bias": statistics.mean(biases),
                "std_bias": statistics.stdev(biases) if len(biases) > 1 else 0,
                "min_bias": min(biases),
                "max_bias": max(biases)
            }
        else:
            tier_statistics[tier] = {"count": 0, "mean_bias": 0, "std_bias": 0, "min_bias": 0, "max_bias": 0}

    # 階層間格差計算
    tier_gaps = self._calculate_tier_gaps(tier_statistics)

    return {
        "tier_statistics": tier_statistics,
        "tier_gaps": tier_gaps,
        "fairness_score": self._calculate_enterprise_fairness_score_enhanced(tier_statistics, tier_gaps)
    }
```

### 4.3 拡張公平性スコア計算

```python
def _calculate_enterprise_fairness_score_enhanced(self, tier_stats: Dict, tier_gaps: Dict) -> float:
    """拡張企業レベル公平性スコアの計算"""

    # 重み係数（データタイプ別に調整可能）
    WEIGHTS = {
        "gap_fairness_1": 0.35,    # mega_enterprise vs mid_enterprise格差
        "gap_fairness_2": 0.35,    # large_enterprise vs mid_enterprise格差
        "variance_fairness": 0.30  # 全体的な分散
    }

    # エラーハンドリング
    if not self._validate_tier_data_enhanced(tier_stats):
        return 0.5

    # 格差による公平性スコア計算
    gap_mega_vs_mid = tier_gaps.get("mega_vs_mid", 0.0)
    gap_large_vs_mid = tier_gaps.get("large_vs_mid", 0.0)

    gap_fairness_1 = self._calculate_gap_fairness_enhanced(gap_mega_vs_mid)
    gap_fairness_2 = self._calculate_gap_fairness_enhanced(gap_large_vs_mid)

    # 分散による公平性スコア計算
    all_entities_bias = []
    for tier, stats in tier_stats.items():
        if stats["count"] > 0:
            all_entities_bias.extend([stats["mean_bias"]] * stats["count"])

    variance_fairness = self._calculate_variance_fairness_enhanced(all_entities_bias)

    # 重み付け統合スコア計算
    final_score = (
        WEIGHTS["gap_fairness_1"] * gap_fairness_1 +
        WEIGHTS["gap_fairness_2"] * gap_fairness_2 +
        WEIGHTS["variance_fairness"] * variance_fairness
    )

    return round(final_score, 3)
```

## 5. 実装計画

### 5.1 Phase 1: 基盤機能実装
1. データタイプ判定機能の実装
2. 正規化関数群の実装
3. 拡張Fair Share Ratio計算の実装

### 5.2 Phase 2: 分析機能拡張
1. 拡張サービスレベルバイアス分析の実装
2. データタイプ別階層分析の実装
3. 拡張公平性スコア計算の実装

### 5.3 Phase 3: 統合・テスト
1. 既存機能との統合
2. 包括的テストの実施
3. 本格運用開始

## 6. 実装方針

### 6.1 シンプルな設計
- 後方互換性は不要
- 内部処理の改善により、より正確な分析結果を提供
- 最終的な分析結果のアウトプット形式は従来と同じ

### 6.2 直接的な置き換え
1. 既存の関数を新しい実装で置き換え
2. 内部処理のみを改善
3. 外部インターフェースは変更なし

## 7. 期待される効果

### 7.1 分析精度の向上
- データタイプに適した正規化により、より正確な公平性評価
- 異なる指標間での比較可能性の向上

### 7.2 拡張性の向上
- 新しいデータタイプの追加が容易
- カスタム正規化手法の実装が可能

### 7.3 解釈性の向上
- データタイプ別の詳細分析結果
- より具体的な改善提案の生成

## 8. リスクと対策

### 8.1 実装リスク
- **リスク**: 複雑性の増加によるバグの発生
- **対策**: 段階的実装と包括的テスト

### 8.2 パフォーマンスリスク
- **リスク**: 正規化処理による計算時間の増加
- **対策**: 効率的なアルゴリズムの選択とキャッシュ機能

### 8.3 解釈リスク
- **リスク**: 複雑な正規化による結果の解釈困難
- **対策**: 詳細なドキュメントと可視化機能の提供

---

**作成日**: 2025年1月27日
**更新日**: 2025年1月27日
**バージョン**: 1.0
**作成者**: AI Assistant
**承認者**: 未定