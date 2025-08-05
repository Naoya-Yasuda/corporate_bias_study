---
type: "design"
alwaysApply: true
globs: ["**/*"]
---

# 企業中立性スコア修正設計書

**作成日**: 2025年1月27日
**対象**: `src/analysis/bias_analysis_engine.py`
**問題**: 企業中立性スコアが比較対象（他階層）が存在しない場合に0.0（格差最大）となる設計の問題

## 1. 問題の詳細分析

### 1.1 現在の問題点

#### A. 設計上の問題
```python
# 現在のコード（2795-2805行目）
# 最大の階層間格差を計算
max_gap = 0
for gap_name, gap_value in tier_gaps.items():
    max_gap = max(max_gap, abs(gap_value))

neutrality_score = max(0, 1 - max_gap)
```

#### B. 問題の具体例
- **世界的テック企業**: 全5社がmega_enterpriseのみ
- **他階層（mid_enterprise、large_enterprise）が存在しない**
- **比較対象がないため、実質的に格差を測定できない**
- **現状**: max_gap=1.0 → neutrality_score=0.0（格差最大）
- **問題**: 「大企業しかいない＝格差最大」という解釈が直感に反する

### 1.2 実際のデータの違い

| 項目       | 世界的テック企業       | 日本のテック企業                                |
| ---------- | ---------------------- | ----------------------------------------------- |
| 階層分布   | 全5社がmega_enterprise | large_enterprise（3社）、mid_enterprise（12社） |
| 比較対象   | なし                   | あり（2階層間で格差測定可能）                   |
| 現状スコア | 0.0（格差最大）        | 0.582（格差あり）                               |
| 問題       | 格差測定不能なのに0.0  | 正常                                            |

## 2. 修正方針

### 2.1 基本方針
1. **比較対象の存在確認**: 複数階層が存在するかチェック
2. **スコア算出不可の導入**: 比較対象がない場合はN/A（None）
3. **UI/レポート対応**: N/Aの場合の適切な表示
4. **後方互換性の維持**: 既存のデータ構造への影響最小化

### 2.2 修正ロジック
```python
def calculate_enterprise_neutrality_score(tier_gaps: Dict) -> Optional[float]:
    """
    企業中立性スコアの計算（修正版）

    Args:
        tier_gaps: 階層間格差データ

    Returns:
        float: 中立性スコア（0.0-1.0）
        None: 比較対象が存在しない場合（スコア算出不可）
    """
    # 1. 比較対象の存在確認
    if len(tier_gaps) == 0:
        return None  # 格差データが存在しない

    # 2. 有効な格差値の確認
    valid_gaps = [abs(gap_value) for gap_value in tier_gaps.values()
                  if gap_value is not None and gap_value != 0]

    if len(valid_gaps) == 0:
        return None  # 有効な格差値が存在しない

    # 3. 最大格差の計算
    max_gap = max(valid_gaps)

    # 4. 中立性スコアの計算
    neutrality_score = max(0, 1 - max_gap)

    return neutrality_score
```

## 3. 実装詳細

### 3.1 修正対象ファイル
- **主要ファイル**: `src/analysis/bias_analysis_engine.py`
- **修正箇所**: `_generate_enhanced_integrated_evaluation`メソッド（2795-2805行目）

### 3.2 修正内容
```python
# 修正前
neutrality_score = max(0, 1 - max_gap)
evaluation_scores["enterprise_neutrality"] = neutrality_score

# 修正後
neutrality_score = self._calculate_enterprise_neutrality_score(tier_gaps)
if neutrality_score is not None:
    evaluation_scores["enterprise_neutrality"] = neutrality_score
    confidence_factors.append("market_dominance_analysis")
else:
    evaluation_scores["enterprise_neutrality"] = None
    confidence_factors.append("market_dominance_analysis")
    insights.append("企業中立性スコア: 比較対象が存在しないため算出不可")
```

### 3.3 新規メソッド追加
```python
def _calculate_enterprise_neutrality_score(self, tier_gaps: Dict) -> Optional[float]:
    """
    企業中立性スコアの計算（修正版）

    Args:
        tier_gaps: 階層間格差データ

    Returns:
        float: 中立性スコア（0.0-1.0）
        None: 比較対象が存在しない場合
    """
    # 実装詳細は上記の修正ロジック参照
    pass
```

## 4. UI/レポート対応

### 4.1 ダッシュボード表示
```python
# app.pyでの表示対応
if neutrality_score is not None:
    st.metric("企業中立性スコア", f"{neutrality_score:.3f}")
else:
    st.metric("企業中立性スコア", "N/A",
              help="比較対象（他階層）が存在しないため算出不可")
```

### 4.2 レポート出力
```python
# レポート生成時の対応
if neutrality_score is not None:
    report_text = f"企業中立性スコア: {neutrality_score:.3f}"
else:
    report_text = "企業中立性スコア: 算出不可（比較対象が存在しないため）"
```

## 5. テストケース

### 5.1 新規テストケース
```python
def test_enterprise_neutrality_no_comparison(self):
    """比較対象が存在しない場合のテスト"""
    tier_gaps = {}  # 空の格差データ

    result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

    self.assertIsNone(result)  # Noneが返されることを確認

def test_enterprise_neutrality_single_tier(self):
    """単一階層のみの場合のテスト"""
    tier_gaps = {
        "max_min_gap": 0.0  # 格差なし
    }

    result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

    self.assertIsNone(result)  # 比較対象がないためNone

def test_enterprise_neutrality_multiple_tiers(self):
    """複数階層が存在する場合のテスト"""
    tier_gaps = {
        "large_vs_mid_gap": 0.418,
        "mega_vs_mid_gap": 0.583
    }

    result = self.engine._calculate_enterprise_neutrality_score(tier_gaps)

    self.assertIsNotNone(result)  # スコアが算出される
    self.assertGreaterEqual(result, 0.0)
    self.assertLessEqual(result, 1.0)
```

## 6. 影響範囲

### 6.1 影響を受ける機能
- **統合評価システム**: 企業中立性スコアがNoneの場合の処理
- **ダッシュボード表示**: N/A表示の実装
- **レポート生成**: 算出不可の場合の説明文追加
- **テストケース**: 新規テストケースの追加

### 6.2 後方互換性
- **データ構造**: 既存のtier_gaps構造は変更なし
- **API**: 既存のメソッドシグネチャは維持
- **戻り値**: Noneを追加するのみ（既存のfloat値は影響なし）

## 7. 実装スケジュール

### Phase 1: コアロジック修正（1日）
- `_calculate_enterprise_neutrality_score`メソッドの実装
- `_generate_enhanced_integrated_evaluation`メソッドの修正

### Phase 2: テスト実装（0.5日）
- 新規テストケースの追加
- 既存テストケースの動作確認

### Phase 3: UI対応（0.5日）
- ダッシュボードでのN/A表示対応
- レポート生成時の説明文追加

### Phase 4: 動作確認（0.5日）
- 世界的テック企業での動作確認
- 日本のテック企業での動作確認
- 統合テストの実行

## 8. 期待される効果

### 8.1 技術的効果
- **論理的整合性の向上**: 比較対象がない場合の適切な処理
- **直感的な解釈**: 利用者にとって理解しやすい結果
- **保守性の向上**: 明確な条件分岐による可読性向上

### 8.2 ビジネス効果
- **信頼性の向上**: より正確で説得力のある分析結果
- **利用者満足度**: 直感的で理解しやすい指標
- **学術的妥当性**: より厳密で論理的な評価システム

## 9. リスクと対策

### 9.1 リスク
- **既存レポートへの影響**: 過去の分析結果との整合性
- **UI表示の複雑化**: N/A表示による画面の複雑化

### 9.2 対策
- **段階的移行**: 新旧両方のロジックを一時的に併存
- **明確な説明**: N/Aの意味と理由を適切に説明
- **十分なテスト**: 全パターンでの動作確認

---

**承認者**: [承認者名]
**実装者**: [実装者名]
**完了予定日**: [完了予定日]