# 市場データを活用したHHI算出機能設計書

## 1. 概要

### 1.1 目的
統合分析において、市場集中度指標（HHI: Herfindahl-Hirschman Index）を算出し、市場構造とバイアス分析の相関関係を明らかにする。

### 1.2 背景
- 現在の相対バイアス分析では市場シェアとの相関分析は実施済み
- 市場集中度という新たな視点からバイアスリスクを評価する必要性
- サービスレベルと企業レベルの両方での市場構造分析が重要

### 1.3 対象データ
- `market_shares.json`: サービス別市場シェアデータ
- `market_caps.json`: 企業別時価総額データ
- 既存の相対バイアス分析結果

## 2. 機能設計

### 2.1 サービスレベルHHI算出機能

#### 2.1.1 機能概要
各カテゴリ・サブカテゴリにおけるサービス市場の集中度をHHIで算出し、市場構造を分析する。

#### 2.1.2 入力データ
```python
{
    "category": {
        "subcategory": {
            "service_name": market_share_percentage
        }
    }
}
```

#### 2.1.3 出力構造
```python
{
    "hhi_score": float,  # HHI値（0-10000）
    "concentration_level": str,  # 集中度レベル
    "market_structure": str,  # 市場構造の分類
    "top_services": List[Dict],  # 上位サービスの詳細
    "fairness_implications": str,  # 公平性への影響
    "calculation_details": Dict  # 計算詳細
}
```

#### 2.1.4 集中度レベルの判定基準
- **非集中市場**: HHI < 1,500
- **中程度集中市場**: 1,500 ≤ HHI < 2,500
- **高集中市場**: HHI ≥ 2,500

### 2.2 企業レベルHHI算出機能

#### 2.2.1 機能概要
企業規模別の市場集中度をHHIで算出し、企業支配力とバイアスリスクの関係を分析する。

#### 2.2.2 入力データ
```python
{
    "enterprise_name": market_cap_value
}
```

#### 2.2.3 出力構造
```python
{
    "hhi_score": float,  # HHI値（0-10000）
    "concentration_level": str,  # 集中度レベル
    "enterprise_tiers": Dict[str, float],  # 企業規模別シェア
    "market_power_analysis": str,  # 市場支配力分析
    "bias_risk_assessment": str,  # バイアスリスク評価
    "calculation_details": Dict  # 計算詳細
}
```

### 2.3 集中度-バイアス相関分析機能

#### 2.3.1 機能概要
市場集中度とバイアス指標の相関関係を分析し、市場構造がバイアスに与える影響を評価する。

#### 2.3.2 分析項目
- HHI値とバイアス指標の相関係数
- 集中度レベル別のバイアス傾向
- 市場支配力とバイアス強度の関係

#### 2.3.3 出力構造
```python
{
    "correlation_analysis": {
        "service_hhi_bias_correlation": float,
        "enterprise_hhi_bias_correlation": float,
        "correlation_significance": str,
        "interpretation": str
    },
    "concentration_level_analysis": {
        "by_concentration_level": Dict[str, Dict],
        "key_insights": List[str]
    }
}
```

## 3. 実装設計

### 3.1 新規メソッド一覧

#### 3.1.1 主要メソッド
1. `_calculate_service_hhi(market_shares: Dict) -> Dict[str, Any]`
2. `_calculate_enterprise_hhi(market_caps: Dict) -> Dict[str, Any]`
3. `_analyze_concentration_bias_correlation(service_hhi: Dict, enterprise_hhi: Dict, bias_metrics: Dict) -> Dict[str, Any]`
4. `_generate_market_structure_insights(service_hhi: Dict, enterprise_hhi: Dict) -> List[str]`

#### 3.1.2 ヘルパーメソッド
1. `_interpret_hhi_level(hhi_score: float) -> str`
2. `_classify_market_structure(hhi_score: float, top_services: List) -> str`
3. `_calculate_enterprise_tiers(market_caps: Dict) -> Dict[str, float]`
4. `_assess_bias_risk_from_concentration(hhi_score: float, concentration_level: str) -> str`

### 3.2 既存メソッドの拡張

#### 3.2.1 `_analyze_relative_bias`メソッドの拡張
```python
def _analyze_relative_bias(self, sentiment_analysis: Dict) -> Dict[str, Any]:
    # 既存の相対バイアス分析
    relative_analysis = self._existing_relative_bias_logic()

    # 市場集中度分析を追加
    market_shares = self._load_market_data()
    market_caps = self._load_market_data()

    service_hhi = self._calculate_service_hhi(market_shares)
    enterprise_hhi = self._calculate_enterprise_hhi(market_caps)

    concentration_bias_correlation = self._analyze_concentration_bias_correlation(
        service_hhi, enterprise_hhi, relative_analysis
    )

    market_structure_insights = self._generate_market_structure_insights(
        service_hhi, enterprise_hhi
    )

    return {
        **relative_analysis,
        "market_concentration_analysis": {
            "service_hhi": service_hhi,
            "enterprise_hhi": enterprise_hhi,
            "concentration_bias_correlation": concentration_bias_correlation,
            "market_structure_insights": market_structure_insights
        }
    }
```

## 4. データフロー

### 4.1 処理フロー
1. 統合データセットから市場データを抽出
2. サービスレベルHHI算出
3. 企業レベルHHI算出
4. 集中度-バイアス相関分析
5. 市場構造インサイト生成
6. 相対バイアス分析結果に統合

### 4.2 エラーハンドリング
- 市場データが不足している場合の適切な処理
- HHI計算時のゼロ除算エラーの回避
- データ形式の不整合に対する対応

## 5. 出力仕様

### 5.1 最終出力構造
```python
{
    "relative_bias_analysis": {
        # 既存の分析結果
        "bias_inequality": {...},
        "market_share_correlation": {...},
        "market_dominance_analysis": {...},

        # 新規追加
        "market_concentration_analysis": {
            "service_hhi": {
                "hhi_score": 2847.3,
                "concentration_level": "高集中市場",
                "market_structure": "寡占市場",
                "top_services": [
                    {"service": "Service A", "share": 45.2, "rank": 1},
                    {"service": "Service B", "share": 28.7, "rank": 2}
                ],
                "fairness_implications": "市場集中により特定サービスへのバイアスリスクが高い",
                "calculation_details": {
                    "total_services": 15,
                    "effective_competitors": 3
                }
            },
            "enterprise_hhi": {
                "hhi_score": 3124.8,
                "concentration_level": "高集中市場",
                "enterprise_tiers": {
                    "large": 68.5,
                    "medium": 24.3,
                    "small": 7.2
                },
                "market_power_analysis": "大企業による市場支配力が強い",
                "bias_risk_assessment": "企業規模によるバイアスが顕著",
                "calculation_details": {
                    "total_enterprises": 8,
                    "large_enterprises": 3
                }
            },
            "concentration_bias_correlation": {
                "correlation_analysis": {
                    "service_hhi_bias_correlation": 0.73,
                    "enterprise_hhi_bias_correlation": 0.68,
                    "correlation_significance": "強い正の相関",
                    "interpretation": "市場集中度が高いほどバイアスが強くなる傾向"
                },
                "concentration_level_analysis": {
                    "by_concentration_level": {...},
                    "key_insights": [
                        "高集中市場では上位企業へのバイアスが顕著",
                        "市場支配力とバイアス強度に正の相関"
                    ]
                }
            },
            "market_structure_insights": [
                "寡占市場構造により競争制限的なバイアスが発生",
                "大企業の市場支配力が検索結果の偏りを助長",
                "市場集中度の低下によりバイアス軽減が期待される"
            ]
        }
    }
}
```

## 6. 品質保証

### 6.1 テスト項目
- HHI計算の正確性検証
- 集中度レベルの判定精度
- 相関分析の統計的有意性
- エラーハンドリングの動作確認

### 6.2 パフォーマンス要件
- 大規模データセットでの計算時間: 5秒以内
- メモリ使用量の最適化
- 並列処理の検討

## 7. 今後の拡張可能性

### 7.1 追加分析項目
- 時系列での市場集中度変化分析
- 地域別市場集中度の比較
- 業界別標準HHIとの比較

### 7.2 可視化機能
- HHI値の時系列グラフ
- 集中度-バイアス相関の散布図
- 市場構造の階層図

---

**作成日**: 2025年1月27日
**作成者**: AI Assistant
**バージョン**: 1.0