# LLM解釈機能設計書

## 概要

### 目的
HHI分析結果や企業規模分類などの複雑な数値データから、LLM（Large Language Model）を使用して自動的に解釈コメントを生成し、分析結果の理解性と洞察力を向上させる。

### 背景
- 現在の分析結果は数値データ中心で、非技術者にとって理解しにくい
- データの背景や意味を深く理解した解釈が必要
- 政策立案者や意思決定者にとって実用的な洞察が不足

### 期待効果
- 分析結果の理解性向上
- 隠れたパターンや関係性の発見
- 実用的な洞察の自動生成
- 多様なユーザー層への対応

## 機能仕様

### 1. HHI分析解釈機能

#### 1.1 機能概要
HHIスコア、市場構造、上位サービス、バイアス相関から自動的に解釈コメントを生成

#### 1.2 入力データ
```python
{
    "hhi_score": 3021.4,
    "concentration_level": "高集中市場",
    "market_structure": "高集中市場",
    "top_services": [
        {"service": "ソニー", "share": 45.0, "rank": 1},
        {"service": "任天堂", "share": 25.0, "rank": 2}
    ],
    "bias_correlation": 1.0
}
```

#### 1.3 出力形式
```python
{
    "hhi_insights": "HHI 3021.4は高集中市場を示しており...",
    "market_structure_analysis": "この市場構造は寡占的競争の特徴を示し...",
    "bias_risk_assessment": "市場集中度とバイアスの完全相関は...",
    "policy_recommendations": "この市場構造を改善するためには..."
}
```

### 2. 企業規模分類解釈機能

#### 2.1 機能概要
企業規模分布（大企業・中企業・小企業の割合）から市場構造の解釈を生成

#### 2.2 入力データ
```python
{
    "enterprise_tiers": {
        "large": 45.0,
        "medium": 55.0,
        "small": 0.0
    },
    "market_caps": {
        "ソニー": 15.2,
        "任天堂": 7.8,
        "楽天": 1.2
    }
}
```

#### 2.3 出力形式
```python
{
    "tier_distribution_analysis": "大企業45%、中企業55%の分布は...",
    "market_power_assessment": "大企業の市場支配力は...",
    "competitive_environment": "この企業規模分布は競争環境に...",
    "bias_implications": "企業規模によるバイアスの可能性は..."
}
```

### 3. バイアス相関解釈機能

#### 3.1 機能概要
サービスレベルと企業レベルのバイアス相関から関係性の解釈を生成

#### 3.2 入力データ
```python
{
    "service_correlation": 1.0,
    "enterprise_correlation": 0.786,
    "bias_data": {
        "aws_bias": 0.933,
        "azure_bias": 0.533,
        "sony_bias": 0.8
    }
}
```

#### 3.3 出力形式
```python
{
    "correlation_strength_analysis": "サービスレベルでの完全相関は...",
    "market_structure_relationship": "市場構造とバイアスの関係性は...",
    "risk_assessment": "この相関パターンが示すリスクは...",
    "mitigation_strategies": "バイアス軽減のための戦略は..."
}
```

## 技術仕様

### 1. LLM呼び出し機能

#### 1.1 基本設計
```python
def _call_llm_for_interpretation(self, prompt: str, context: Dict = None) -> str:
    """
    LLMを使用して解釈コメントを生成

    Parameters:
    -----------
    prompt : str
        解釈生成用のプロンプト
    context : Dict, optional
        追加のコンテキスト情報

    Returns:
    --------
    str
        生成された解釈コメント
    """
```

#### 1.2 エラーハンドリング
- LLM呼び出し失敗時のフォールバック処理
- タイムアウト処理（30秒）
- レート制限対応

#### 1.3 プロンプトテンプレート
```python
HHI_INTERPRETATION_TEMPLATE = """
以下の市場集中度分析結果を解釈してください：

- HHIスコア: {hhi_score}
- 市場構造: {market_structure}
- 上位サービス: {top_services}
- バイアス相関: {bias_correlation}

この結果が示す市場の特徴、競争環境、バイアスリスクについて
具体的で実用的な洞察を提供してください。

出力形式：
1. 市場構造の特徴
2. 競争環境の評価
3. バイアスリスクの評価
4. 政策推奨事項
"""
```

### 2. 解釈生成メソッド

#### 2.1 HHI解釈生成
```python
def _generate_hhi_interpretation(self, hhi_score: float, market_structure: str,
                               top_services: List[Dict], bias_correlation: float) -> str:
    """
    HHI分析結果からLLMによる解釈コメントを生成
    """
```

#### 2.2 企業規模解釈生成
```python
def _generate_enterprise_tier_interpretation(self, enterprise_tiers: Dict[str, float],
                                           market_caps: Dict[str, float]) -> str:
    """
    企業規模分布からLLMによる解釈を生成
    """
```

#### 2.3 相関解釈生成
```python
def _generate_correlation_interpretation(self, service_correlation: float,
                                       enterprise_correlation: float,
                                       bias_data: Dict) -> str:
    """
    バイアス相関からLLMによる解釈を生成
    """
```

### 3. 統合機能

#### 3.1 市場集中度分析への統合
```python
def _analyze_market_concentration(self, market_shares: Dict, market_caps: Dict,
                                category: str, subcategory: str, entities: Dict) -> Dict:
    # 既存のHHI分析
    hhi_analysis = self._existing_hhi_analysis()

    # LLM解釈を追加
    hhi_analysis['llm_interpretation'] = {
        'hhi_insights': self._generate_hhi_interpretation(...),
        'enterprise_tier_insights': self._generate_enterprise_tier_interpretation(...),
        'correlation_insights': self._generate_correlation_interpretation(...),
        'overall_assessment': self._generate_overall_assessment(...)
    }

    return hhi_analysis
```

## データフロー

### 1. 解釈生成フロー
```
1. 分析結果データ取得
   ↓
2. プロンプトテンプレート適用
   ↓
3. LLM呼び出し
   ↓
4. 解釈結果生成
   ↓
5. 結果統合・保存
```

### 2. エラーハンドリングフロー
```
1. LLM呼び出し試行
   ↓
2. 成功 → 解釈結果返却
   ↓
3. 失敗 → フォールバック処理
   ↓
4. デフォルト解釈返却
```

## 設定項目

### 1. LLM設定
```yaml
llm_interpretation:
  model: "llama-3.1-sonar-large-128k-online"
  max_tokens: 500
  temperature: 0.7
  timeout: 30
  retry_count: 3
```

### 2. プロンプト設定
```yaml
prompts:
  hhi_interpretation: "HHI分析結果の解釈プロンプト"
  enterprise_tier_interpretation: "企業規模分類の解釈プロンプト"
  correlation_interpretation: "バイアス相関の解釈プロンプト"
```

### 3. 出力設定
```yaml
output:
  include_llm_interpretation: true
  interpretation_language: "ja"
  max_interpretation_length: 1000
```

## 実装計画

### Phase 1: 基本機能実装
1. LLM呼び出し機能の実装
2. 基本的な解釈生成メソッドの実装
3. エラーハンドリングの実装

### Phase 2: 統合・テスト
1. 既存分析機能への統合
2. 単体テストの実装
3. 統合テストの実行

### Phase 3: 最適化・拡張
1. プロンプトの最適化
2. パフォーマンス改善
3. 多言語対応

## 期待される効果

### 1. 分析結果の理解性向上
- 非技術者でも理解しやすい解釈
- データの背景や意味の明確化
- 実用的な洞察の提供

### 2. 意思決定支援
- 政策立案者向けの推奨事項
- リスク評価の自動化
- 戦略的洞察の提供

### 3. 分析効率の向上
- 手動解釈作業の削減
- 一貫性のある解釈の提供
- スケーラブルな分析対応

## リスク・課題

### 1. 技術的課題
- LLMの応答品質の不安定性
- API呼び出しコスト
- レート制限への対応

### 2. 品質管理
- 解釈の正確性確保
- バイアスの混入防止
- 一貫性の維持

### 3. 運用課題
- システム負荷の増加
- メンテナンスコスト
- 依存関係の管理

## 今後の拡張予定

### 1. 多言語対応
- 英語、中国語など複数言語での解釈生成
- 地域特性に応じた解釈調整

### 2. 業界特化
- 特定業界の知識を組み込んだ解釈
- 業界固有の指標や基準の反映

### 3. インタラクティブ機能
- ユーザーからの質問への回答
- 解釈の詳細化・カスタマイズ

---

**作成日**: 2025年7月28日
**作成者**: AI Assistant
**バージョン**: v1.0
**ステータス**: 設計完了