---
type: "rule"
alwaysApply: true
globs: ["**/*"]
---

# HHI計算修正設計書

## 1. 問題の現状分析

### 1.1 現在の実装の問題点

#### 1.1.1 パーセンテージデータの誤処理
```python
# 現在の実装（問題あり）
elif isinstance(data, (int, float)) and data > 0:
    # 古い構造: {service: value} (パーセンテージ形式)
    shares[service] = float(data) / 100.0  # パーセンテージを小数に変換 ← 問題（データは既に小数形式）
```

**問題**：
- データは既に小数形式（例：0.8954）で保存されているのに、100で割る処理をしている
- この変換により、正しい値の1/100の値になってしまう
- HHI計算で誤った値を使用することになる

#### 1.1.2 データタイプ別処理の不統一
```python
# 現在の実装
if 'market_share' in data:
    # 市場シェア（%）
    share_value = data['market_share']  # パーセンテージ
elif 'gmv' in data:
    # 流通総額（億円）
    share_value = data['gmv']  # 絶対値
elif 'users' in data:
    # ユーザー数（万人）
    share_value = data['users']  # 絶対値
```

**問題**：
- パーセンテージと絶対値を同じように処理
- データタイプに応じた適切な正規化が行われていない

### 1.2 市場データの構造分析

#### 1.2.1 データタイプ別の構造
```json
{
  "検索エンジン": {
    "data_type": "市場シェア（%）",
    "Google": {"market_share": 0.8954, "enterprise": "Google"},
    "Bing": {"market_share": 0.0402, "enterprise": "Microsoft"}
  },
  "オンラインショッピング": {
    "data_type": "流通総額（億円）",
    "Amazon": {"gmv": 67937, "enterprise": "Amazon"},
    "楽天市場": {"gmv": 56301, "enterprise": "楽天"}
  },
  "SNS": {
    "data_type": "月間アクティブユーザー数（万人）",
    "LINE": {"users": 9800, "enterprise": "LINEヤフー"}
  }
}
```

#### 1.2.2 データタイプの分類
1. **比率データ**：市場シェア（%）- 既に相対シェア
2. **絶対値データ**：流通総額、ユーザー数 - 正規化が必要

## 2. 修正設計

### 2.1 データタイプ判定機能

#### 2.1.1 データタイプ判定関数
```python
def _determine_data_type(self, subcategory_data: Dict[str, Any]) -> str:
    """
    データタイプを判定

    Returns:
    --------
    str: "ratio" | "absolute"
    """
    data_type = subcategory_data.get("data_type", "")

    if "市場シェア" in data_type or "シェア" in data_type:
        return "ratio"
    elif "流通総額" in data_type or "ユーザー数" in data_type:
        return "absolute"
    else:
        # デフォルトは絶対値として扱う
        return "absolute"
```

### 2.2 データ抽出・正規化機能

#### 2.2.1 比率データの処理
```python
def _extract_ratio_data(self, subcategory_data: Dict[str, Any]) -> Dict[str, float]:
    """
    比率データ（パーセンテージ）を抽出・正規化

    Returns:
    --------
    Dict[str, float]: サービス名 -> 正規化されたシェア（0-1）
    """
    shares = {}

    for service, data in subcategory_data.items():
        if service in ["data_type", "region"]:
            continue

        if isinstance(data, dict) and 'market_share' in data:
            share_value = data['market_share']
            if isinstance(share_value, (int, float)) and share_value > 0:
                # データは既に小数形式（0.8954）なのでそのまま使用
                shares[service] = float(share_value)

    return shares
```

#### 2.2.2 絶対値データの処理
```python
def _extract_absolute_data(self, subcategory_data: Dict[str, Any]) -> Dict[str, float]:
    """
    絶対値データを抽出・正規化

    Returns:
    --------
    Dict[str, float]: サービス名 -> 正規化されたシェア（0-1）
    """
    raw_values = {}

    for service, data in subcategory_data.items():
        if service in ["data_type", "region"]:
            continue

        if isinstance(data, dict):
            # 各種絶対値を抽出
            if 'gmv' in data:
                raw_values[service] = data['gmv']
            elif 'users' in data:
                raw_values[service] = data['users']

    # 相対シェアに正規化
    if raw_values:
        total_value = sum(raw_values.values())
        return {service: value / total_value for service, value in raw_values.items()}

    return {}
```

### 2.3 統合HHI計算機能

#### 2.3.1 修正されたHHI計算関数
```python
def _calculate_service_hhi_fixed(self, market_shares: Dict[str, Any], category: str, subcategory: str) -> Dict[str, Any]:
    """
    修正版：サービスレベルでのHHIを算出

    Parameters:
    -----------
    market_shares : Dict[str, Any]
        市場シェアデータ
    category : str
        カテゴリ名
    subcategory : str
        サブカテゴリ名

    Returns:
    --------
    Dict[str, Any]
        HHI分析結果
    """
    try:
        # 1. 対象カテゴリの市場シェアデータを抽出
        subcategory_data = market_shares.get(category, {})

        if not subcategory_data:
            return self._create_empty_hhi_result("サービス市場シェアデータが不足")

        # 2. データタイプを判定
        data_type = self._determine_data_type(subcategory_data)

        # 3. データタイプに応じて適切に処理
        if data_type == "ratio":
            shares = self._extract_ratio_data(subcategory_data)
        else:  # absolute
            shares = self._extract_absolute_data(subcategory_data)

        if not shares:
            return self._create_empty_hhi_result("有効な市場シェアデータがありません")

        # 4. HHI計算: Σ(市場シェア_i)^2 * 10000
        hhi_score = sum(share ** 2 for share in shares.values()) * 10000

        # 5. 結果生成（既存の処理と同様）
        concentration_level = self._interpret_hhi_level(hhi_score)

        # 6. 上位サービス抽出（シェア順）
        sorted_services = sorted(shares.items(), key=lambda x: x[1], reverse=True)
        top_services = []
        for i, (service, share) in enumerate(sorted_services[:5], 1):
            top_services.append({
                "service": service,
                "share": round(share * 100, 1),  # パーセンテージで表示
                "rank": i
            })

        # 7. 計算詳細
        calculation_details = {
            "total_services": len(shares),
            "effective_competitors": self._count_effective_competitors(shares),
            "largest_share": round(max(shares.values()) * 100, 1),
            "smallest_share": round(min(shares.values()) * 100, 1),
            "share_variance": round(np.var(list(shares.values())) * 10000, 2) if len(shares) > 1 else 0,
            "data_type": data_type,
            "processing_method": "ratio" if data_type == "ratio" else "normalized_absolute"
        }

        return {
            "hhi_score": round(hhi_score, 1),
            "concentration_level": concentration_level,
            "market_structure": self._classify_market_structure(hhi_score, top_services),
            "top_services": top_services,
            "fairness_implications": self._assess_fairness_implications(hhi_score, concentration_level, top_services),
            "calculation_details": calculation_details
        }

    except Exception as e:
        logger.error(f"HHI計算エラー: {e}")
        return self._create_empty_hhi_result(f"HHI計算中にエラーが発生: {str(e)}")
```

## 3. 実装計画

### 3.1 Phase 1: 基盤機能実装
1. **データタイプ判定関数**の実装
2. **比率データ抽出関数**の実装
3. **絶対値データ抽出関数**の実装

### 3.2 Phase 2: HHI計算修正
1. **修正版HHI計算関数**の実装
2. **既存関数との置き換え**
3. **後方互換性の確保は不要**

### 3.3 Phase 3: テスト・検証
1. **単体テスト**の作成
2. **統合テスト**の実行
3. **結果比較**による検証

## 4. 期待される効果

### 4.1 計算精度の向上
- パーセンテージデータの正確な処理
- データタイプに応じた適切な正規化
- より正確なHHI値の算出

### 4.2 保守性の向上
- データタイプ別の明確な処理分離
- コードの可読性向上
- 将来のデータタイプ追加への対応

### 4.3 結果の一貫性
- 異なるデータタイプ間での一貫した処理
- 再現可能な計算結果
- 学術的妥当性の向上

## 5. リスク管理

### 5.1 後方互換性は不要

### 5.2 データ品質
- 入力データの妥当性チェック強化
- エラーハンドリングの改善
- ログ出力による追跡可能性向上

## 6. 実装スケジュール

### Week 1: 設計・実装
- 詳細設計の完了
- 基盤機能の実装
- 単体テストの作成

### Week 2: 統合・テスト
- 修正版HHI計算の統合
- 統合テストの実行
- 結果検証の実施

### Week 3: 検証・文書化
- パフォーマンステスト
- ドキュメント更新
- 最終検証・リリース

---

**作成日**: 2025年1月27日
**作成者**: AI Assistant
**バージョン**: 1.0
**ステータス**: 設計完了