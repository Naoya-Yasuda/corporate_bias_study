# 市場シェアとバイアス相関の無相関化防止設計書（シンプル版）

## 1. 実施済み作業

### 1.1 データの追加（完了）
```
追加完了した企業（11社）:
- IBM: 15.2兆円（世界的テック企業）
- Oracle: 8.1兆円（世界的テック企業）
- Alibaba: 25.3兆円（世界的テック企業）
- Tencent: 30.1兆円（世界的テック企業）
- Netflix: 25.8兆円（世界的テック企業）
- Disney: 20.4兆円（世界的テック企業）
- X Corp: 15.6兆円（世界的テック企業）
- ByteDance: 20.0兆円（世界的テック企業）
- Warner Bros Discovery: 12.8兆円（世界的テック企業）
- LINE: 2.1兆円（日本のテック企業）
- U-NEXT: 0.8兆円（日本のテック企業）
```

### 1.2 既存実装の確認（完了）
```
確認済み: bias_analysis_engine.pyでmarket_shares.jsonのenterpriseフィールドが既に使用されている
- _determine_enterprise_name()メソッド: 企業名の取得
- _analyze_enterprise_level_bias()メソッド: 企業レベル分析
- _analyze_service_level_bias()メソッド: サービスレベル分析
```

## 2. 今回やるべきこと

### 2.1 データ不足時の「計算不能」対応

#### 2.1.1 問題の特定
```
現在の問題: データ不足時に相関を0.0（無相関）として扱うのは不適切

適切な対応: データ不足時は「計算不能」として扱う
```

#### 2.1.2 シンプルな対応策
```python
def _analyze_market_share_correlation_improved(self, entities, market_shares, category):
    """
    市場シェアとバイアスの相関分析（データ不足対応版）
    """
    # 1. 利用可能な企業数をチェック
    available_entities = []
    for entity_name, entity_data in entities.items():
        enterprise_name = self._determine_enterprise_name(entity_name)
        if enterprise_name and enterprise_name in market_caps:
            available_entities.append(entity_name)

    # 2. データ不足の場合は「計算不能」として扱う
    if len(available_entities) < 3:
        return {
            "correlation": None,
            "p_value": None,
            "status": "insufficient_data",
            "reason": f"データ不足: {len(available_entities)}企業（最低3企業必要）",
            "available_entities": available_entities
        }

    # 3. 十分なデータがある場合は通常の相関計算を実行
    return self._calculate_correlation(entities, market_shares, category)
```

## 3. 実装計画（シンプル版）

### 3.1 Phase 1: データ不足チェック機能追加（1日間）
```
Day 1: シンプルなデータ不足チェック機能の実装
- 利用可能企業数のチェック
- データ不足時の「計算不能」処理
- 既存メソッドの修正
```

### 3.2 Phase 2: テスト・検証（1日間）
```
Day 1: テスト・検証
- データ不足ケースのテスト
- 十分なデータがある場合のテスト
- 結果の検証・評価
```

## 4. 期待される効果

### 4.1 定量的効果
```
目標値:
- データ不足時の適切な処理: 100%
- 誤った解釈の防止: 100%
```

### 4.2 定性的効果
- データ不足時の適切な対応
- 誤った結論の防止

## 5. 成功指標

### 5.1 主要指標
```
1. データ不足時の適切な処理
   - 目標: 100%
   - 現在: 0%（未実装）

2. 誤った解釈の防止
   - 目標: 100%
   - 現在: 0%（未実装）
```

## 6. 次のステップ

### 6.1 即座に実行可能な作業
```
1. データ不足チェック機能の実装
2. 既存メソッドの修正
3. テスト・検証の実施
```

---

**作成日**: 2025年1月27日
**更新日**: 2025年1月27日
**作成者**: AI Assistant
**承認者**: 未承認
**ステータス**: シンプル設計完了