# クロス分析（Cross Analysis Insights）設計書

## 1. 現状の問題点と改善方針

### 1.1 sentiment_ranking_correlationの不備
- **問題**: 空のオブジェクト`{}`として出力、相関分析未実行
- **改善方針**:
  - 感情分析とランキング分析の相関を正確に計算
  - 統計的有意性の検定を追加
  - カテゴリ別の詳細な分析を実装

### 1.2 一貫したリーダー/ラガードの識別不備
- **問題**: 明確な一貫性が見られる企業が未検出
  - クラウドサービス：AWSが常に上位（bias_index: 2.733, rank: 1）
  - 日本のテック企業：ソニーが一貫して高評価（bias_index: 1.267, rank: 1-2）
- **改善方針**:
  - 業界別の一貫性評価の導入
  - 時系列での安定性評価
  - 統計的信頼性の考慮

### 1.3 プラットフォーム間一致度の評価
- **問題**: 極端な差異（kendall_tau=1.0 vs 0.0）が"moderate"と評価
- **改善方針**:
  - より詳細な5段階評価の導入
  - 業界特性を考慮した評価基準
  - 信頼性指標の追加

### 1.4 バイアスパターン評価
- **問題**: 業界による差異が無視された一元的な評価
- **改善方針**:
  - 業界別の評価基準導入
  - 市場構造の考慮
  - 時系列変化の分析

### 1.5 分析カバレッジ
- **問題**: 基本的な3項目のみをカバー
- **改善方針**:
  - 統計的有意性の分析追加
  - 市場シェア相関の分析
  - 時系列データの活用

## 2. 実装設計

### 2.1 データ構造
```python
class EntityMetrics(TypedDict):
    bias_index: float
    avg_rank: float
    execution_count: int
    stability_score: float
    statistical_significance: Dict[str, Union[float, bool, str]]

class CrossAnalysisResult(TypedDict):
    sentiment_ranking_correlation: Dict[str, Dict[str, CorrelationResult]]
    consistent_leaders: List[str]
    consistent_laggards: List[str]
    google_citations_alignment: Literal["very_strong", "strong", "moderate", "weak", "very_weak"]
    overall_bias_pattern: Dict[str, Dict[str, any]]
    cross_platform_consistency: Dict[str, any]
```

### 2.2 主要機能
```python
class CrossAnalysisEngine:
    def calculate_correlation(self, category: str, subcategory: str) -> Dict:
        """業界別の相関分析"""
        return {
            "pearson": self._calculate_pearson(),
            "spearman": self._calculate_spearman(),
            "significance": self._calculate_significance()
        }

    def identify_patterns(self, window_size: int = 5) -> Dict:
        """一貫したパターンの検出"""
        return {
            "leaders": self._find_consistent_leaders(),
            "laggards": self._find_consistent_laggards(),
            "stability": self._calculate_stability()
        }

    def analyze_by_industry(self) -> Dict:
        """業界別分析"""
        return {
            "cloud_services": self._analyze_cloud_services(),
            "tech_companies": self._analyze_tech_companies(),
            "cross_industry": self._analyze_cross_industry()
        }
```

### 2.3 エラー処理
```python
class CrossAnalysisError(Exception):
    """基本例外クラス"""
    pass

class ErrorHandler:
    def handle_validation_error(self, error: Exception) -> Dict:
        """検証エラーの処理"""
        return {
            "error_type": "validation",
            "message": str(error),
            "recovery_action": self._suggest_recovery()
        }
```

## 3. 実装計画

### Phase 1: 基盤整備（2週間）
- データ構造の定義と検証
- 基本メトリクス計算の実装
- エラー処理の基盤実装

### Phase 2: 主要機能（3週間）
- 相関分析の実装
- パターン検出の実装
- 業界別分析の実装

### Phase 3: 拡張機能（2週間）
- 時系列分析の追加
- 市場シェア相関の実装
- 信頼性評価の強化

### Phase 4: 最適化（2週間）
- パフォーマンス最適化
- テストの拡充
- ドキュメント整備

## 4. 品質基準

### 4.1 機能要件
- 全ての分析機能が実装完了
- テストカバレッジ90%以上
- エラー処理の完備

### 4.2 性能要件
- 実行時間: 5秒以内
- メモリ使用: 1GB以下
- CPU使用率: 50%以下

### 4.3 信頼性要件
- エラー発生率: 0.1%以下
- データ整合性: 100%
- 結果の再現性: 100%

## 5. リスク管理

### 5.1 技術リスク
- データ構造の変更対応
- パフォーマンス低下
- メモリリーク

### 5.2 品質リスク
- テストカバレッジ不足
- エッジケース見落とし
- バグの混入

### 5.3 対策
- 継続的なテスト実施
- コードレビューの徹底
- 段階的なリリース