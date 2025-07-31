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

### 2.1 基本方針

**シンプルな順位比較に戻す**
- 複雑な統合手法を削除
- Google検索結果の順位とPerplexity検索結果の順位を直接比較
- 共通ドメインの順位相関をKendall Tauで測定

### 2.2 データ構造の定義

#### SimpleRankingクラス

```python
class SimpleRanking:
    """シンプルな順位情報を保持するクラス"""

    def __init__(self, domain: str, rank: int, source: str, entity: str, result_type: str):
        self.domain = domain
        self.rank = rank
        self.source = source  # "google" or "perplexity"
        self.entity = entity  # "AWS", "Azure", etc.
        self.result_type = result_type  # "official" or "reputation"

    def __repr__(self):
        return f"SimpleRanking(domain='{self.domain}', rank={self.rank}, source='{self.source}', entity='{self.entity}', result_type='{self.result_type}')"
```

### 2.3 順位付きドメイン抽出

```python
def extract_simple_rankings(self, subcategory_data: Dict, source: str) -> List[SimpleRanking]:
    """サブカテゴリデータから順位付きドメインを抽出（シンプル版）"""
    rankings = []

    if "entities" not in subcategory_data:
        return rankings

    entities = subcategory_data["entities"]
    for entity_name, entity_data in entities.items():
        # official_results から抽出
        if "official_results" in entity_data:
            for i, result in enumerate(entity_data["official_results"]):
                domain = result.get("domain")
                if domain:
                    rankings.append(SimpleRanking(
                        domain=domain,
                        rank=i + 1,  # 1-based ranking
                        source=source,
                        entity=entity_name,
                        result_type="official"
                    ))

        # reputation_results から抽出
        if "reputation_results" in entity_data:
            for i, result in enumerate(entity_data["reputation_results"]):
                domain = result.get("domain")
                if domain:
                    rankings.append(SimpleRanking(
                        domain=domain,
                        rank=i + 1,  # 1-based ranking
                        source=source,
                        entity=entity_name,
                        result_type="reputation"
                    ))

    return rankings
```

### 2.4 シンプルな順位統合

```python
def calculate_simple_ranking(self, rankings: List[SimpleRanking]) -> Dict[str, int]:
    """シンプルな順位統合：ドメインごとの平均順位を計算"""
    domain_ranks = {}

    for ranking in rankings:
        domain = ranking.domain
        if domain not in domain_ranks:
            domain_ranks[domain] = []
        domain_ranks[domain].append(ranking.rank)

    # 平均順位を計算
    avg_ranks = {}
    for domain, ranks in domain_ranks.items():
        avg_ranks[domain] = sum(ranks) / len(ranks)

    # 平均順位でソート
    sorted_domains = sorted(avg_ranks.keys(), key=lambda x: avg_ranks[x])

    # 最終順位を付与
    final_ranks = {}
    for i, domain in enumerate(sorted_domains):
        final_ranks[domain] = i + 1

    return final_ranks
```

### 2.5 Kendall Tau計算

```python
def compute_simple_ranking_metrics(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
    """シンプルなランキングメトリクス計算"""

    # 1. 順位付きドメイン抽出
    google_rankings = self.extract_simple_rankings(google_data, "google")
    citations_rankings = self.extract_simple_rankings(citations_data, "perplexity")

    # 2. 統合順位計算
    google_final_ranks = self.calculate_simple_ranking(google_rankings)
    citations_final_ranks = self.calculate_simple_ranking(citations_rankings)

    # 3. 共通ドメインの特定
    common_domains = set(google_final_ranks.keys()) & set(citations_final_ranks.keys())

    if len(common_domains) < 2:
        return {
            "error": "共通ドメインが不足しています（最低2個必要）",
            "common_domains_count": len(common_domains)
        }

    # 4. 共通ドメインの順位リスト作成
    google_ranks_list = [google_final_ranks[domain] for domain in common_domains]
    citations_ranks_list = [citations_final_ranks[domain] for domain in common_domains]

    # 5. Kendall Tau計算
    kendall_tau = self._compute_kendall_tau(google_ranks_list, citations_ranks_list)

    # 6. RBO計算
    rbo_score = self._compute_rbo(google_ranks_list, citations_ranks_list)

    # 7. Overlap Ratio計算
    overlap_ratio = len(common_domains) / max(len(google_final_ranks), len(citations_final_ranks))

    return {
        "kendall_tau": kendall_tau,
        "rbo_score": rbo_score,
        "overlap_ratio": overlap_ratio,
        "common_domains": list(common_domains),
        "google_ranks": google_final_ranks,
        "citations_ranks": citations_final_ranks,
        "google_domains_count": len(google_final_ranks),
        "citations_domains_count": len(citations_final_ranks),
        "common_domains_count": len(common_domains)
    }

def _compute_kendall_tau(self, ranks1: List[int], ranks2: List[int]) -> float:
    """Kendall Tau計算"""
    from scipy.stats import kendalltau
    tau, p_value = kendalltau(ranks1, ranks2)
    return tau

def _compute_rbo(self, ranks1: List[int], ranks2: List[int]) -> float:
    """Rank-Biased Overlap計算"""
    from src.utils.rank_utils import rbo
    return rbo(ranks1, ranks2)
```

### 2.6 メイン分析メソッド

```python
def _analyze_citations_google_comparison(self, google_data: Dict, citations_data: Dict) -> Dict[str, Any]:
    """Google検索とPerplexity引用データの比較分析（シンプル版）"""

    results = {}

    for category in google_data.keys():
        if category not in citations_data:
            continue

        category_results = {}
        google_category = google_data[category]
        citations_category = citations_data[category]

        for subcategory in google_category.keys():
            if subcategory not in citations_category:
                continue

            try:
                # シンプルなランキングメトリクス計算
                ranking_metrics = self.compute_simple_ranking_metrics(
                    google_category[subcategory], citations_category[subcategory]
                )

                # 公式ドメイン分析
                official_domain_analysis = self._analyze_official_domain_bias(
                    google_category[subcategory], citations_category[subcategory]
                )

                # 感情分析比較
                sentiment_comparison = self._compare_sentiment_distributions(
                    google_category[subcategory], citations_category[subcategory]
                )

                category_results[subcategory] = {
                    "ranking_similarity": ranking_metrics,
                    "official_domain_analysis": official_domain_analysis,
                    "sentiment_comparison": sentiment_comparison,
                    "data_quality": {
                        "google_data_complete": "google_domains_count" in ranking_metrics,
                        "citations_data_complete": "citations_domains_count" in ranking_metrics
                    }
                }

            except Exception as e:
                logger.error(f"比較分析エラー ({category}/{subcategory}): {e}")
                category_results[subcategory] = {
                    "error": str(e),
                    "analysis_failed": True
                }

        results[category] = category_results

    return results
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
1. **エンティティペアの特定**: 全エンティティの組み合わせ
2. **順位差計算**: 各ペアの平均順位差を計算
3. **統計的有意性**: 順位差の統計的有意性を検定

**実装箇所**:
- `_calculate_ranking_category_analysis()`: カテゴリレベル分析
- `_generate_ranking_insights()`: ランキング洞察生成

### 3.4 改善されたおすすめランキング分析

#### 3.4.1 実行回数間の完全比較

**現在の問題点**:
- 実行回数間の比較が不完全
- 一部のペアのみで比較

**改善案**:
```python
def _calculate_complete_inter_run_comparison(self, answer_list: List[Dict]) -> Dict[str, Any]:
    """実行回数間の完全比較"""

    # 各実行回のランキング抽出
    run_rankings = []
    for answer_data in answer_list:
        ranking = self._extract_ranking_from_answer(answer_data["answer"])
        run_rankings.append(ranking)

    # 全ペアのKendall Tau計算
    tau_values = []
    for i in range(len(run_rankings)):
        for j in range(i + 1, len(run_rankings)):
            tau = self._compute_kendall_tau_between_rankings(run_rankings[i], run_rankings[j])
            tau_values.append(tau)

    return {
        "avg_kendall_tau": np.mean(tau_values),
        "std_kendall_tau": np.std(tau_values),
        "min_kendall_tau": np.min(tau_values),
        "max_kendall_tau": np.max(tau_values),
        "tau_values": tau_values,
        "comparison_count": len(tau_values)
    }
```

#### 3.4.2 ランキング安定性の詳細分析

**現在の問題点**:
- 安定性指標が単純すぎる
- 変動パターンの分析が不足

**改善案**:
```python
def _analyze_ranking_stability_patterns(self, all_ranks: List[int]) -> Dict[str, Any]:
    """ランキング安定性パターン分析"""

    # 基本統計
    mean_rank = np.mean(all_ranks)
    std_rank = np.std(all_ranks)
    rank_range = max(all_ranks) - min(all_ranks)

    # 変動パターン分析
    rank_changes = [all_ranks[i+1] - all_ranks[i] for i in range(len(all_ranks)-1)]
    positive_changes = sum(1 for change in rank_changes if change > 0)
    negative_changes = sum(1 for change in rank_changes if change < 0)
    no_changes = sum(1 for change in rank_changes if change == 0)

    # 安定性レベル判定
    if std_rank < 0.5:
        stability_level = "非常に安定"
    elif std_rank < 1.0:
        stability_level = "安定"
    elif std_rank < 2.0:
        stability_level = "中程度"
    else:
        stability_level = "不安定"

    return {
        "mean_rank": mean_rank,
        "std_rank": std_rank,
        "rank_range": rank_range,
        "positive_changes": positive_changes,
        "negative_changes": negative_changes,
        "no_changes": no_changes,
        "stability_level": stability_level,
        "change_pattern": "上昇傾向" if positive_changes > negative_changes else "下降傾向" if negative_changes > positive_changes else "安定"
    }
```

#### 3.4.3 ランキング品質の包括的評価

**現在の問題点**:
- 品質指標が限定的
- データの完全性チェックが不十分

**改善案**:
```python
def _calculate_comprehensive_ranking_quality(self, ranking_summary: Dict, answer_list: List[Dict]) -> Dict[str, Any]:
    """包括的なランキング品質評価"""

    entities = ranking_summary.get("entities", {})
    avg_ranking = ranking_summary.get("avg_ranking", [])

    # 完全性スコア
    completeness_score = len(avg_ranking) / len(entities) if entities else 0.0

    # 一貫性スコア
    consistency_scores = []
    for entity_data in entities.values():
        all_ranks = entity_data.get("all_ranks", [])
        if len(all_ranks) > 1:
            std = np.std(all_ranks)
            consistency = max(0.0, 1.0 - std / 3.0)
            consistency_scores.append(consistency)

    consistency_score = np.mean(consistency_scores) if consistency_scores else 0.0

    # データ品質スコア
    data_quality_score = 0.0
    quality_factors = []

    # 公式URLの存在
    official_url_count = sum(1 for entity_data in entities.values() if entity_data.get("official_url"))
    official_url_ratio = official_url_count / len(entities) if entities else 0.0
    if official_url_ratio >= 0.8:
        quality_factors.append("公式URL充足")
        data_quality_score += 0.3

    # 実行回数の充足
    execution_count = len(answer_list)
    if execution_count >= 10:
        quality_factors.append("実行回数充足")
        data_quality_score += 0.3
    elif execution_count >= 5:
        quality_factors.append("実行回数中程度")
        data_quality_score += 0.2

    # 順位変動の適切性
    avg_std = np.mean([np.std(entity_data.get("all_ranks", [])) for entity_data in entities.values()])
    if avg_std < 2.0:
        quality_factors.append("順位安定性良好")
        data_quality_score += 0.4

    return {
        "completeness_score": completeness_score,
        "consistency_score": consistency_score,
        "data_quality_score": data_quality_score,
        "quality_factors": quality_factors,
        "official_url_ratio": official_url_ratio,
        "execution_count": execution_count,
        "avg_rank_std": avg_std,
        "overall_quality_score": (completeness_score + consistency_score + data_quality_score) / 3
    }
```

## 4. 実装計画

### 4.1 Phase 1: Perplexity-Google比較の簡素化

1. **複雑な統合手法の削除**
   - `weighted_average`、`frequency_based`、`entity_priority`を削除
   - `DomainRanking`クラスを`SimpleRanking`クラスに変更

2. **シンプルな順位比較の実装**
   - `extract_simple_rankings()`の実装
   - `calculate_simple_ranking()`の実装
   - `compute_simple_ranking_metrics()`の実装

3. **メイン分析メソッドの更新**
   - `_analyze_citations_google_comparison()`の簡素化
   - 不要な複雑な処理の削除

### 4.2 Phase 2: おすすめランキング分析の改善

1. **実行回数間の完全比較**
   - `_calculate_complete_inter_run_comparison()`の実装
   - 全ペアのKendall Tau計算

2. **ランキング安定性の詳細分析**
   - `_analyze_ranking_stability_patterns()`の実装
   - 変動パターンの分析

3. **ランキング品質の包括的評価**
   - `_calculate_comprehensive_ranking_quality()`の実装
   - 多角的な品質評価

### 4.3 Phase 3: テストと検証

1. **単体テスト**
   - 各関数の動作確認
   - エッジケースの処理確認

2. **統合テスト**
   - 実際のデータでの動作確認
   - 結果の妥当性検証

3. **パフォーマンステスト**
   - 大規模データでの動作確認
   - 処理時間の測定

## 5. 期待される効果

### 5.1 Perplexity-Google比較

1. **分析の簡素化**
   - 複雑な統合手法を削除し、理解しやすい分析に
   - 本来の目的である順位比較に集中

2. **結果の信頼性向上**
   - シンプルで透明性の高い計算方法
   - 結果の解釈が容易

3. **保守性の向上**
   - コードの複雑さを削減
   - バグの可能性を低減

### 5.2 おすすめランキング分析

1. **分析の深さ向上**
   - 実行回数間の完全比較
   - 詳細な安定性パターン分析

2. **品質評価の充実**
   - 多角的な品質指標
   - データの信頼性評価

3. **洞察の向上**
   - より詳細な分析結果
   - 実用的な改善提案

## 6. リスクと対策

### 6.1 リスク

1. **既存機能への影響**
   - 既存の分析結果との整合性
   - ユーザーインターフェースの変更

2. **性能への影響**
   - 計算量の変化
   - メモリ使用量の変化

### 6.2 対策

1. **段階的実装**
   - 既存機能を保持しながら段階的に改善
   - 後方互換性の確保

2. **十分なテスト**
   - 単体テスト、統合テストの充実
   - 実際のデータでの検証

3. **ドキュメント更新**
   - 変更内容の明確な記録
   - ユーザー向け説明の更新