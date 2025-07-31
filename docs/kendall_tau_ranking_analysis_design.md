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

## 2. 詳細設計

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

### 2.2 順位抽出・統合アルゴリズム

#### 順位抽出機能

```python
def extract_ranked_domains(self, subcategory_data: Dict) -> List[DomainRanking]:
    """サブカテゴリデータから順位付きドメインを抽出"""
    domain_rankings = []

    for entity_name, entity_data in subcategory_data["entities"].items():
        # official_results から抽出
        if "official_results" in entity_data:
            for result in entity_data["official_results"]:
                domain = result.get("domain")
                rank = result.get("rank", 0)
                if domain and rank > 0:
                    domain_rankings.append(DomainRanking(
                        domain=domain,
                        rank=rank,
                        source="google",  # or "perplexity"
                        entity=entity_name,
                        result_type="official"
                    ))

        # reputation_results から抽出
        if "reputation_results" in entity_data:
            for result in entity_data["reputation_results"]:
                domain = result.get("domain")
                rank = result.get("rank", 0)
                if domain and rank > 0:
                    domain_rankings.append(DomainRanking(
                        domain=domain,
                        rank=rank,
                        source="google",  # or "perplexity"
                        entity=entity_name,
                        result_type="reputation"
                    ))

    return domain_rankings
```

#### 統合順位計算アルゴリズム

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

### 2.3 統合方法の詳細

#### 重み付き平均方式

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

#### 頻度ベース方式

```python
def _calculate_frequency_score(self, rankings: List[DomainRanking]) -> float:
    """出現頻度ベースのスコア計算"""
    # より多くの企業で上位に出現するドメインを重視
    entity_count = len(set(r.entity for r in rankings))
    avg_rank = sum(r.rank for r in rankings) / len(rankings)
    return entity_count * (11 - avg_rank)
```

#### 企業優先度方式

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
    """共通ドメインのみでKendall Tau計算"""
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
        "frequency_correlation": self._calculate_correlation(google_freq, citations_freq)
    }
```

## 3. 実装計画

### Phase 1: 基本構造実装（1-2週間）

1. **DomainRankingクラスの実装**
   - クラス定義とメソッド実装
   - 重み付け計算機能

2. **順位抽出機能の実装**
   - extract_ranked_domains関数
   - データ検証機能

3. **基本的な統合順位計算**
   - 重み付き平均方式の実装
   - 基本的なテスト

### Phase 2: 統合アルゴリズム実装（2-3週間）

1. **複数統合方式の実装**
   - 頻度ベース方式
   - 企業優先度方式
   - 比較機能

2. **Kendall Tau計算の改善**
   - 正確な順位相関計算
   - 共通ドメイン処理

3. **RBO・Overlap計算の改善**
   - 順位情報を活用した計算
   - 精度向上

### Phase 3: 分析機能実装（2-3週間）

1. **詳細分析機能**
   - ドメイン頻度分析
   - 企業バイアス分析
   - 結果タイプ分布分析

2. **可視化機能**
   - ランキング比較チャート
   - 頻度分布グラフ
   - 相関分析図

3. **レポート生成機能**
   - 詳細分析レポート
   - 比較結果サマリー
   - 推奨事項生成

### Phase 4: 検証・最適化（1-2週間）

1. **既存データでの検証**
   - 現在のデータセットでの動作確認
   - 結果の妥当性検証

2. **パフォーマンス最適化**
   - 計算速度の改善
   - メモリ使用量の最適化

3. **エラーハンドリング強化**
   - 例外処理の追加
   - ログ機能の強化

## 4. 期待される効果

### 4.1 技術的効果

1. **正確な順位相関**
   - 実際の順位情報を反映したKendall Tau
   - より信頼性の高い分析結果

2. **多角的分析**
   - 複数の統合方法による比較
   - より深い洞察の獲得

3. **詳細な分析**
   - ドメイン頻度分析
   - 企業バイアス分析
   - 結果タイプ分布分析

### 4.2 実用的効果

1. **透明性向上**
   - 順位決定プロセスの明確化
   - 分析結果の説明可能性向上

2. **柔軟性向上**
   - 複数の統合方法による分析
   - 用途に応じた方法選択

3. **品質向上**
   - より正確なバイアス検出
   - 信頼性の高い分析結果

## 5. リスクと対策

### 5.1 技術的リスク

1. **計算複雑度の増加**
   - 対策: 効率的なアルゴリズム設計
   - 対策: キャッシュ機能の実装

2. **データ品質の問題**
   - 対策: データ検証機能の強化
   - 対策: エラーハンドリングの改善

### 5.2 実用的リスク

1. **実装時間の延長**
   - 対策: 段階的実装計画
   - 対策: 優先度の明確化

2. **既存機能への影響**
   - 対策: 後方互換性の維持
   - 対策: 段階的移行計画

## 6. 成功指標

### 6.1 技術指標

1. **精度向上**
   - Kendall Tauの信頼性向上
   - 分析結果の一貫性向上

2. **機能拡張**
   - 複数統合方式の実装
   - 詳細分析機能の実装

### 6.2 実用指標

1. **分析品質**
   - より詳細な洞察の獲得
   - 分析結果の説明可能性向上

2. **運用効率**
   - 分析時間の短縮
   - 結果の信頼性向上

## 7. 今後の展開

### 7.1 短期展開（3-6ヶ月）

1. **基本機能の実装完了**
2. **既存システムとの統合**
3. **初期ユーザーフィードバック収集**

### 7.2 中期展開（6-12ヶ月）

1. **機能の拡張・最適化**
2. **他分析指標との統合**
3. **ユーザビリティの向上**

### 7.3 長期展開（1年以上）

1. **AI・機械学習との統合**
2. **リアルタイム分析機能**
3. **他プラットフォームへの展開**

---

**作成日**: 2025年7月31日
**作成者**: AI Assistant
**バージョン**: 1.0
**ステータス**: 設計完了