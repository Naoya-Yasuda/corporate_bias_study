# Kendall Tau順位分析の詳細設計

## 概要

本ドキュメントは、Google検索結果とPerplexity引用データの順位相関分析におけるKendall Tau計算の詳細設計を記述します。現在の実装における問題点を解決し、より正確で意味のある順位相関分析を実現するための設計です。

## 1. 現状の問題分析

### 1.1 現在の実装の問題点

1. **順位情報の喪失**
   - 元データの`rank`情報が抽出時に失われる
   - 単純なドメイン名リストになっている

2. **統合方法の不明確性**
   - 企業内・企業間の順位統合方法が未定義
   - official_resultsとreputation_resultsの重み付けが不明

3. **重複ドメインの処理**
   - 複数企業で同じドメインが出た場合の順位決定方法が未定義
   - 統合時の順位計算ロジックが不明確

4. **分析の限界**
   - 単一の統合方法のみ
   - 詳細な分析機能が不足

### 1.2 影響

- Kendall Tauの値が実際の順位相関を反映していない可能性
- 分析結果の信頼性低下
- 詳細な洞察が得られない

## 2. Perplexity-Google比較の詳細設計

### 2.1 データ構造の定義

#### DomainRankingクラス

```python
class DomainRanking:
    """ドメインランキング情報を保持するクラス"""

    def __init__(self, domain: str, rank: int, source: str, entity: str, result_type: str):
        self.domain = domain
        self.rank = rank
        self.source = source  # "google" or "perplexity"
        self.entity = entity  # "AWS", "Azure", etc.
        self.result_type = result_type  # "official" or "reputation"
        self.weight = self._calculate_weight()

    def _calculate_weight(self) -> float:
        """結果タイプに基づく重み付け"""
        base_weight = 1.0
        if self.result_type == "official":
            return base_weight * 1.5  # 公式サイトを重視
        else:
            return base_weight * 1.0  # 評判サイト
```

### 2.2 順位付きドメイン抽出

```python
def extract_ranked_domains(self, subcategory_data: Dict) -> List[DomainRanking]:
    """サブカテゴリデータから順位付きドメインを抽出"""
    domain_rankings = []

    for entity_name, entity_data in subcategory_data["entities"].items():
        # official_results から抽出
        if "official_results" in entity_data:
            for i, result in enumerate(entity_data["official_results"]):
                domain = self._extract_domain_from_url(result.get("url", ""))
                if domain:
                    domain_rankings.append(DomainRanking(
                        domain=domain,
                        rank=i + 1,  # 1-based ranking
                        source="perplexity",
                        entity=entity_name,
                        result_type="official"
                    ))

        # reputation_results から抽出
        if "reputation_results" in entity_data:
            for i, result in enumerate(entity_data["reputation_results"]):
                domain = self._extract_domain_from_url(result.get("url", ""))
                if domain:
                    domain_rankings.append(DomainRanking(
                        domain=domain,
                        rank=i + 1,  # 1-based ranking
                        source="perplexity",
                        entity=entity_name,
                        result_type="reputation"
                    ))

    return domain_rankings
```

### 2.3 統合順位計算

```python
def calculate_integrated_ranking(self, domain_rankings: List[DomainRanking],
                                integration_method: str = "weighted_average") -> List[str]:
    """ドメインランキングを統合して最終順位を計算"""

    # ドメイン別にグループ化
    domain_groups = {}
    for ranking in domain_rankings:
        domain = ranking.domain
        if domain not in domain_groups:
            domain_groups[domain] = []
        domain_groups[domain].append(ranking)

    # 統合スコア計算
    domain_scores = {}
    for domain, rankings in domain_groups.items():
        if integration_method == "weighted_average":
            score = self._calculate_weighted_average_score(rankings)
        elif integration_method == "frequency_based":
            score = self._calculate_frequency_score(rankings)
        elif integration_method == "entity_priority":
            score = self._calculate_entity_priority_score(rankings)

        domain_scores[domain] = score

    # スコアでソートしてドメインリストを返す
    sorted_domains = sorted(domain_scores.keys(),
                           key=lambda x: domain_scores[x], reverse=True)

    return sorted_domains[:20]  # 上位20ドメイン
```

#### 統合方法の詳細

**重み付き平均方式**

```python
def _calculate_weighted_average_score(self, rankings: List[DomainRanking]) -> float:
    """重み付き平均スコア計算"""
    total_weight = 0
    weighted_sum = 0

    for ranking in rankings:
        # 順位をスコアに変換（1位=10点, 2位=9点, ...）
        score = 11 - ranking.rank
        weighted_score = score * ranking.weight
        weighted_sum += weighted_score
        total_weight += ranking.weight

    return weighted_sum / total_weight if total_weight > 0 else 0
```

**頻度ベース方式**

```python
def _calculate_frequency_score(self, rankings: List[DomainRanking]) -> float:
    """頻度ベーススコア計算"""
    entity_count = len(set(r.entity for r in rankings))
    avg_rank = sum(r.rank for r in rankings) / len(rankings)
    return entity_count * (11 - avg_rank)
```

**企業優先度方式**

```python
def _calculate_entity_priority_score(self, rankings: List[DomainRanking]) -> float:
    """企業優先度ベースのスコア計算"""
    # 市場シェア上位企業の結果を重視
    entity_weights = {
        "AWS": 1.5, "Azure": 1.3, "Google Cloud": 1.2, "Oracle Cloud": 1.0
    }

    total_score = 0
    for ranking in rankings:
        entity_weight = entity_weights.get(ranking.entity, 1.0)
        score = (11 - ranking.rank) * ranking.weight * entity_weight
        total_score += score

    return total_score
```

### 2.4 Kendall Tau計算の改善

```python
def compute_improved_ranking_metrics(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
    """改善されたランキングメトリクス計算"""

    # 1. 順位付きドメイン抽出
    google_rankings = self.extract_ranked_domains(google_data)
    citations_rankings = self.extract_ranked_domains(citations_data)

    # 2. 統合順位計算（複数方法で比較）
    integration_methods = ["weighted_average", "frequency_based", "entity_priority"]
    results = {}

    for method in integration_methods:
        google_domains = self.calculate_integrated_ranking(google_rankings, method)
        citations_domains = self.calculate_integrated_ranking(citations_rankings, method)

        # 3. Kendall Tau計算
        kendall_tau = self._compute_kendall_tau(google_domains, citations_domains)
        rbo_score = self._compute_rbo(google_domains, citations_domains)
        overlap_ratio = self._compute_overlap_ratio(google_domains, citations_domains)

        results[method] = {
            "kendall_tau": kendall_tau,
            "rbo_score": rbo_score,
            "overlap_ratio": overlap_ratio,
            "google_domains": google_domains,
            "citations_domains": citations_domains
        }

    return results

def _compute_kendall_tau(self, ranking1: List[str], ranking2: List[str]) -> float:
    """改善されたKendall Tau計算"""
    # 共通ドメインを抽出
    common_domains = set(ranking1) & set(ranking2)

    if len(common_domains) < 2:
        return 0.0

    # 共通ドメインの順位を抽出
    ranks1 = [ranking1.index(domain) for domain in common_domains]
    ranks2 = [ranking2.index(domain) for domain in common_domains]

    # Kendall Tau計算
    return self._calculate_kendall_tau_coefficient(ranks1, ranks2)
```

### 2.5 詳細分析機能

```python
def analyze_ranking_details(self, google_rankings: List[DomainRanking],
                           citations_rankings: List[DomainRanking]) -> Dict[str, Any]:
    """ランキングの詳細分析"""

    analysis = {
        "domain_frequency": self._analyze_domain_frequency(google_rankings, citations_rankings),
        "entity_bias": self._analyze_entity_bias(google_rankings, citations_rankings),
        "result_type_distribution": self._analyze_result_type_distribution(google_rankings, citations_rankings),
        "ranking_stability": self._analyze_ranking_stability(google_rankings, citations_rankings)
    }

    return analysis

def _analyze_domain_frequency(self, google_rankings: List[DomainRanking],
                             citations_rankings: List[DomainRanking]) -> Dict[str, Any]:
    """ドメイン出現頻度分析"""
    google_freq = {}
    citations_freq = {}

    for ranking in google_rankings:
        google_freq[ranking.domain] = google_freq.get(ranking.domain, 0) + 1

    for ranking in citations_rankings:
        citations_freq[ranking.domain] = citations_freq.get(ranking.domain, 0) + 1

    return {
        "google_frequency": google_freq,
        "citations_frequency": citations_freq,
        "common_domains": set(google_freq.keys()) & set(citations_freq.keys())
    }
```

## 3. おすすめランキング分析の詳細設計

### 3.1 おすすめランキング分析の特徴

**Perplexity-Google比較とは全く異なる仕組みです：**

1. **データソース**: `perplexity_rankings` データのみ
2. **比較対象**: 同一プロンプトの複数回実行結果間の比較
3. **目的**: ランキングの安定性・品質・一貫性の評価
4. **Kendall Tau使用**: 実行回数間の順位相関分析

### 3.2 データ構造の理解

**おすすめランキングデータの構造：**

```json
{
  "デジタルサービス": {
    "クラウドサービス": {
      "ranking_summary": {
        "avg_ranking": ["AWS", "Azure", "Google Cloud", "Oracle Cloud", "diulshvfisdhfjjasfj"],
        "entities": {
          "AWS": {
            "avg_rank": 1.0,
            "all_ranks": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]  // 15回実行
          },
          "Azure": {
            "avg_rank": 2.0,
            "all_ranks": [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
          }
        }
      },
      "answer_list": [
        {"answer": "1. AWS: ...", "url": [...]},
        {"answer": "1. AWS: ...", "url": [...]}
        // 15回分の回答
      ]
    }
  }
}
```

### 3.3 Kendall Tau等の算出対象

**おすすめランキング分析では、以下の比較でKendall Tau等を算出しています：**

#### 3.3.1 実行回数間の比較

**比較対象**: 同一プロンプトの複数回実行結果間の順位相関

**具体的な比較方法**:
1. **各実行回のランキング抽出**: `answer_list`から各回のランキングを抽出
2. **ペア比較**: 全実行回の組み合わせでKendall Tau計算
3. **平均値算出**: 全ペアのKendall Tauの平均値を算出

**実装箇所**:
- `_calculate_ranking_stability()`: ランキング安定性分析
- `_calculate_ranking_quality()`: ランキング品質分析
- `compare_entity_rankings()`: 2つのランキング間の比較

#### 3.3.2 エンティティペア間の比較

**比較対象**: 異なるエンティティ間の順位差分析

**具体的な比較方法**:
```python
# ranking_comparisonの計算（line 1446-1463）
for i, e1 in enumerate(avg_ranking):
    for j, e2 in enumerate(avg_ranking):
        if i < j and e1 in entities and e2 in entities:
            arr1 = np.array(entities[e1].get('all_ranks', []))
            arr2 = np.array(entities[e2].get('all_ranks', []))
            if len(arr1) == len(arr2) and len(arr1) > 0:
                mean_diff = float(np.mean(arr1 - arr2))
                ranking_comparison[f"{e1}_vs_{e2}"] = {"mean_diff": mean_diff}
```

### 3.4 現在の実装の問題点

#### 3.4.1 実行回数間比較の問題

**問題**: 現在の実装では、実行回数間のKendall Tau計算が不完全

**具体的な問題**:
1. **比較対象の不明確性**: どの実行回同士を比較しているか不明
2. **統計的有意性の欠如**: 複数回実行の統計的検定が不十分
3. **安定性指標の限界**: 単純な標準偏差のみで安定性を評価

#### 3.4.2 改善が必要な箇所

**修正が必要なメソッド**:
1. `_calculate_ranking_stability()`: 実行回数間のKendall Tau計算を追加
2. `_calculate_ranking_quality()`: 一貫性指標の改善
3. `compare_entity_rankings()`: 複数実行回の比較機能強化

### 3.5 改善設計

#### 3.5.1 実行回数間Kendall Tau計算の改善

```python
def _calculate_execution_ranking_correlation(self, answer_list: List[Dict]) -> Dict[str, Any]:
    """実行回数間のランキング相関分析"""

    # 各実行回のランキングを抽出
    execution_rankings = []
    for answer in answer_list:
        ranking = self._extract_ranking_from_answer(answer["answer"])
        execution_rankings.append(ranking)

    # 全ペアのKendall Tau計算
    kendall_taus = []
    for i in range(len(execution_rankings)):
        for j in range(i + 1, len(execution_rankings)):
            tau = self._compute_kendall_tau(execution_rankings[i], execution_rankings[j])
            kendall_taus.append(tau)

    # 統計的指標
    avg_tau = np.mean(kendall_taus) if kendall_taus else 0.0
    std_tau = np.std(kendall_taus) if kendall_taus else 0.0

    return {
        "average_kendall_tau": avg_tau,
        "kendall_tau_std": std_tau,
        "execution_consistency": "高" if avg_tau > 0.8 else "中" if avg_tau > 0.5 else "低",
        "all_kendall_taus": kendall_taus
    }
```

#### 3.5.2 ランキング安定性の詳細分析

```python
def _analyze_ranking_stability_detailed(self, entities: Dict[str, Any]) -> Dict[str, Any]:
    """詳細なランキング安定性分析"""

    stability_metrics = {}
    for entity, data in entities.items():
        all_ranks = data.get('all_ranks', [])

        if len(all_ranks) >= 2:
            # 基本統計
            mean_rank = np.mean(all_ranks)
            std_rank = np.std(all_ranks)
            rank_range = max(all_ranks) - min(all_ranks)

            # 順位変動パターン
            rank_changes = [all_ranks[i+1] - all_ranks[i] for i in range(len(all_ranks)-1)]
            positive_changes = sum(1 for c in rank_changes if c > 0)
            negative_changes = sum(1 for c in rank_changes if c < 0)

            stability_metrics[entity] = {
                "mean_rank": mean_rank,
                "rank_std": std_rank,
                "rank_range": rank_range,
                "stability_score": max(0, 1 - std_rank / 3),  # 0-1の安定性スコア
                "rank_trend": "上昇" if positive_changes > negative_changes else "下降" if negative_changes > positive_changes else "安定",
                "consistency_level": "高" if std_rank < 0.5 else "中" if std_rank < 1.0 else "低"
            }

    return stability_metrics
```

#### 3.5.3 エンティティ間比較の改善

```python
def _analyze_entity_ranking_relationships(self, entities: Dict[str, Any]) -> Dict[str, Any]:
    """エンティティ間のランキング関係分析"""

    entity_names = list(entities.keys())
    relationships = {}

    for i, entity1 in enumerate(entity_names):
        for j, entity2 in enumerate(entity_names):
            if i < j:
                ranks1 = entities[entity1].get('all_ranks', [])
                ranks2 = entities[entity2].get('all_ranks', [])

                if len(ranks1) == len(ranks2) and len(ranks1) > 0:
                    # 平均順位差
                    mean_diff = np.mean(np.array(ranks1) - np.array(ranks2))

                    # 順位差の変動
                    rank_diffs = [ranks1[k] - ranks2[k] for k in range(len(ranks1))]
                    diff_std = np.std(rank_diffs)

                    # 順位関係の安定性
                    consistent_relationship = all(diff > 0 for diff in rank_diffs) or all(diff < 0 for diff in rank_diffs)

                    relationships[f"{entity1}_vs_{entity2}"] = {
                        "mean_rank_difference": mean_diff,
                        "rank_difference_std": diff_std,
                        "consistent_relationship": consistent_relationship,
                        "relationship_strength": "強" if abs(mean_diff) > 2 else "中" if abs(mean_diff) > 1 else "弱"
                    }

    return relationships
```

### 3.6 実装計画

#### Phase 1: 基本構造の改善（1-2週間）
1. 実行回数間Kendall Tau計算の実装
2. ランキング安定性分析の詳細化
3. エンティティ間関係分析の追加

#### Phase 2: 統計的検定の強化（1週間）
1. 複数実行回の統計的有意性検定
2. 信頼区間の計算
3. 効果量の算出

#### Phase 3: 可視化・解釈の改善（1週間）
1. 実行回数間相関の可視化
2. 安定性パターンの解釈
3. 推奨事項の生成

### 3.7 期待される効果

1. **精度向上**: 実行回数間の相関を正確に測定
2. **安定性評価**: ランキングの一貫性を定量的に評価
3. **統計的信頼性**: 複数実行の統計的検定による信頼性向上
4. **詳細分析**: エンティティ間の関係性を詳細に分析
5. **実用性向上**: より実用的なランキング品質評価

## 4. 実装計画

### 4.1 Phase 1: 基本構造実装（1-2週間）

1. **DomainRankingクラスの実装**
2. **extract_ranked_domains関数の実装**
3. **calculate_integrated_ranking関数の実装**
4. **基本的なKendall Tau計算の改善**

### 4.2 Phase 2: 統合アルゴリズム実装（1-2週間）

1. **重み付き平均方式の実装**
2. **頻度ベース方式の実装**
3. **企業優先度方式の実装**
4. **複数方式の比較機能**

### 4.3 Phase 3: 分析機能拡張（1週間）

1. **詳細分析機能の実装**
2. **ドメイン頻度分析**
3. **エンティティバイアス分析**
4. **結果タイプ分布分析**

### 4.4 Phase 4: 検証・最適化（1週間）

1. **既存データでの動作確認**
2. **パフォーマンス最適化**
3. **エラーハンドリングの強化**
4. **ドキュメント更新**

## 5. 期待される効果

### 5.1 精度向上

- **正確な順位情報の保持**: 元データの順位情報を適切に保持
- **適切な統合方法**: 複数の統合方法による多角的な分析
- **統計的信頼性**: より信頼性の高いKendall Tau値

### 5.2 多角的分析

- **複数統合方法**: 3つの異なる統合方法による比較
- **詳細分析**: ドメイン頻度、エンティティバイアス等の詳細分析
- **透明性向上**: 統合プロセスの透明性確保

### 5.3 柔軟性向上

- **設定可能な統合方法**: 用途に応じた統合方法の選択
- **拡張可能な設計**: 新しい統合方法の追加が容易
- **カスタマイズ可能**: 重み付けやパラメータの調整が可能

### 5.4 品質向上

- **エラーハンドリング**: 堅牢なエラーハンドリング
- **バリデーション**: 入力データの適切な検証
- **ログ機能**: 詳細なログによる追跡可能性

## 6. リスクと対策

### 6.1 実装リスク

**リスク**: 複雑な統合ロジックによるバグ
**対策**: 段階的な実装と十分なテスト

### 6.2 パフォーマンスリスク

**リスク**: 大量データでの処理時間増加
**対策**: 効率的なアルゴリズムとキャッシュ機能

### 6.3 互換性リスク

**リスク**: 既存機能への影響
**対策**: 後方互換性の確保と段階的移行

## 7. 成功指標

### 7.1 技術的指標

- **Kendall Tau精度**: 既知のデータセットでの精度向上
- **処理時間**: 既存実装と同等以下の処理時間
- **エラー率**: 1%以下のエラー率

### 7.2 機能指標

- **分析深度**: より詳細な分析結果の提供
- **ユーザビリティ**: 直感的な結果解釈
- **拡張性**: 新しい分析機能の追加が容易

---

**作成日**: 2025年7月31日
**作成者**: AI Assistant
**バージョン**: 1.0
**ステータス**: 設計完了