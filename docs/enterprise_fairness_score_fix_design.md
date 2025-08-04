# 企業レベル公平性スコア修正設計書

**作成日**: 2025年1月27日
**対象**: `src/analysis/bias_analysis_engine.py`
**問題**: 企業レベル公平性スコアが全て0.5の固定値になっているロジックミス

## 1. 問題の詳細分析

### 1.1 現在の問題点

#### A. フォールバック値の固定
```python
# 現在のコード（4863行目）
if tier_analysis.get("available", False):
    return tier_analysis.get("integrated_fairness_score", 0.5)  # デフォルト値が0.5

if not tier_analysis.get("available", False):
    return 0.5  # 常に0.5を返す
```

#### B. データ構造の不整合
- 実際のデータでは`integrated_fairness_score`が0.5に固定されている
- 実際の計算ロジックが実行されていない
- 異なる市場構造を持つ企業グループが同じスコアになっている

### 1.2 実際のデータの違い

| 項目         | 世界的テック企業       | 日本のテック企業                                |
| ------------ | ---------------------- | ----------------------------------------------- |
| 相関係数     | 0.784（強い正の相関）  | 0.573（中程度の正の相関）                       |
| バイアス範囲 | 0.486～1.653           | 0.39～1.56                                      |
| 階層分布     | 全5社がmega_enterprise | large_enterprise（3社）、mid_enterprise（12社） |
| 格差         | 0（neutral）           | 0.418（大企業への優遇傾向）                     |
| 企業数       | 5社                    | 15社                                            |

## 2. 修正方針

### 2.1 基本方針
1. **フォールバック値の削除**: デフォルト値0.5の使用を廃止
2. **実際の計算ロジック実行**: データに基づく公平性スコアの計算
3. **階層別分析の活用**: 企業規模による格差を反映
4. **相関分析の統合**: 時価総額とバイアスの相関を考慮

### 2.2 計算ロジックの確認

#### A. 論文定義に基づく構成要素（既に正しく実装済み）
```python
WEIGHTS = {
    "gap_fairness_1": 0.35,    # 大企業vs小企業格差による公平性
    "gap_fairness_2": 0.35,    # 中企業vs小企業格差による公平性
    "variance_fairness": 0.30  # 全企業のバイアス分散による公平性
}
```

#### B. 各要素の計算方法（既に正しく実装済み）

**1. 格差による公平性**
```python
gap_fairness = 1.0 - min(gap_value, 1.0)  # 格差が小さいほど高スコア
```

**2. 分散による公平性**
```python
variance_fairness = max(0, 1.0 - (variance * 2))  # 分散が小さいほど高スコア
```

## 3. 実装計画

### 3.1 Phase 1: 関数修正
**対象ファイル**: `src/analysis/bias_analysis_engine.py`

#### A. `_calculate_enterprise_fairness_score`関数の修正
```python
def _calculate_enterprise_fairness_score(self, tier_analysis: Dict) -> float:
    """企業レベル公平性スコアの計算（論文定義準拠版）"""

    # データの検証
    if not tier_analysis.get("available", False):
        return 0.0  # データがない場合は0.0

    # 既存のintegrated_fairness_scoreが0.5の固定値の場合は計算を実行
    if tier_analysis.get("integrated_fairness_score") == 0.5:
        # 論文定義に基づく計算を実行
        return self._calculate_enterprise_fairness_score_actual(tier_analysis)

    # 既に正しく計算されている場合はその値を返す
    return tier_analysis.get("integrated_fairness_score", 0.0)

def _calculate_enterprise_fairness_score_actual(self, tier_analysis: Dict) -> float:
    """実際の企業レベル公平性スコア計算（論文定義準拠）"""

    tier_stats = tier_analysis.get("tier_stats", {})
    tier_gaps = tier_analysis.get("tier_gaps", {})

    # 論文定義に基づく重み係数
    WEIGHTS = {
        "gap_fairness_1": 0.35,    # 大企業vs小企業格差
        "gap_fairness_2": 0.35,    # 中企業vs小企業格差
        "variance_fairness": 0.30  # 全企業のバイアス分散
    }

    # 格差による公平性スコア計算
    gap_mega_vs_mid = tier_gaps.get("mega_vs_mid", 0.0)
    gap_large_vs_mid = tier_gaps.get("large_vs_mid", 0.0)

    gap_fairness_1 = self._calculate_gap_fairness_enhanced(gap_mega_vs_mid)
    gap_fairness_2 = self._calculate_gap_fairness_enhanced(gap_large_vs_mid)

    # 分散による公平性スコア計算
    all_entities_bias = []
    for tier, stats in tier_stats.items():
        if stats.get("count", 0) > 0:
            all_entities_bias.extend([stats["mean_bias"]] * stats["count"])

    variance_fairness = self._calculate_variance_fairness_enhanced(all_entities_bias)

    # 論文定義に基づく重み付け統合
    final_score = (
        WEIGHTS["gap_fairness_1"] * gap_fairness_1 +
        WEIGHTS["gap_fairness_2"] * gap_fairness_2 +
        WEIGHTS["variance_fairness"] * variance_fairness
    )

    return round(final_score, 3)
```

#### B. `_calculate_enterprise_fairness_score_enhanced`関数の修正
同様の修正を適用し、拡張版も更新

### 3.2 Phase 2: データ再生成
**対象**: 既存の分析結果データ

#### A. 再分析の実行
```bash
python scripts/run_bias_analysis.py --date 20250803 --force
```

#### B. 結果の検証
- 世界的テック企業と日本のテック企業で異なるスコアが算出されることを確認
- 各要素の寄与度を確認

### 3.3 Phase 3: テスト実装
**対象ファイル**: `tests/test_enterprise_fairness_score.py`

#### A. テストケース
```python
def test_worldwide_tech_companies_fairness():
    """世界的テック企業の公平性スコアテスト"""
    # 相関0.784、格差0、分散0.195 → 期待値: 約0.65

def test_japanese_tech_companies_fairness():
    """日本のテック企業の公平性スコアテスト"""
    # 相関0.573、格差0.418、分散0.087 → 期待値: 約0.45
```

## 4. 期待される結果

### 4.1 修正後の予想スコア

| 企業グループ     | 現在のスコア | 修正後の予想スコア | 主な要因                                 |
| ---------------- | ------------ | ------------------ | ---------------------------------------- |
| 世界的テック企業 | 0.5          | 0.70               | 格差なし（0）、分散が小さい（0.195）     |
| 日本のテック企業 | 0.5          | 0.58               | 格差あり（0.418）、分散が小さい（0.087） |

### 4.2 スコアの解釈

- **0.8以上**: 非常に公平
- **0.6-0.8**: 比較的公平
- **0.4-0.6**: 中程度の公平性
- **0.2-0.4**: 不公平
- **0.2未満**: 非常に不公平

## 5. リスク管理

### 5.1 潜在リスク
1. **既存データとの整合性**: 過去の分析結果との比較が困難になる可能性
2. **計算負荷**: より複雑な計算による処理時間の増加
3. **解釈の変更**: スコアの意味が変わることによる混乱

### 5.2 対策
1. **バージョン管理**: 分析結果にバージョン番号を付与
2. **パフォーマンス監視**: 計算時間の測定と最適化
3. **ドキュメント更新**: スコアの解釈方法の明確化

## 6. 実装スケジュール

### 6.1 即座に実行可能な修正
- [ ] `_calculate_enterprise_fairness_score`関数の修正
- [ ] 基本的なテストケースの実装
- [ ] 単体テストの実行

### 6.2 段階的実装
- [ ] データ再生成の実行
- [ ] 結果の検証と調整
- [ ] ドキュメントの更新

### 6.3 完了条件
- [ ] 世界的テック企業と日本のテック企業で異なるスコアが算出される
- [ ] スコアが実際のデータ特性を反映している
- [ ] テストケースが全て通過する
- [ ] ドキュメントが更新されている

## 7. 検証方法

### 7.1 機能検証
1. 修正後の関数で既存データを再計算
2. 期待されるスコアとの比較
3. 各要素の寄与度の確認

### 7.2 品質検証
1. エッジケースのテスト
2. パフォーマンステスト
3. メモリ使用量の確認

### 7.3 統合検証
1. 全分析パイプラインでの動作確認
2. UIでの表示確認
3. レポート生成の確認

---

**承認者**: [要承認]
**実装者**: [要指定]
**完了予定日**: [要設定]