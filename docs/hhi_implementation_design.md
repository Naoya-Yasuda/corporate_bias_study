# bias_analysis_engine HHI算出ロジック詳細設計書

## 1. 概要

### 1.1 目的
`bias_analysis_engine.py`に市場集中度指標（HHI）算出機能を実装し、市場構造とバイアス分析の相関関係を明らかにする。

### 1.2 実装方針
- 既存の`_analyze_relative_bias`メソッドを拡張
- 新規メソッド群を追加
- エラーハンドリングとデータ検証を徹底
- 既存コードとの整合性を保持

## 2. 新規メソッド詳細設計

### 2.1 主要メソッド

#### 2.1.1 `_calculate_service_hhi`
```python
def _calculate_service_hhi(self, market_shares: Dict[str, Any], category: str, subcategory: str) -> Dict[str, Any]:
    """
    サービスレベルでのHHIを算出

    Parameters:
    -----------
    market_shares : Dict[str, Any]
        市場シェアデータ（src/data/market_shares.json）
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
        # 1. 対象カテゴリ・サブカテゴリの市場シェアデータを抽出
        category_data = market_shares.get(category, {})
        subcategory_data = category_data.get(subcategory, {})

        if not subcategory_data:
            return self._create_empty_hhi_result("サービス市場シェアデータが不足")

        # 2. 市場シェアをパーセンテージから小数に変換
        shares = {}
        for service, share in subcategory_data.items():
            if isinstance(share, (int, float)) and share > 0:
                shares[service] = float(share) / 100.0  # パーセンテージを小数に変換

        if not shares:
            return self._create_empty_hhi_result("有効な市場シェアデータがありません")

        # 3. HHI計算: Σ(市場シェア_i)^2 * 10000
        hhi_score = sum(share ** 2 for share in shares.values()) * 10000

        # 4. 集中度レベル判定
        concentration_level = self._interpret_hhi_level(hhi_score)

        # 5. 上位サービス抽出（シェア順）
        sorted_services = sorted(shares.items(), key=lambda x: x[1], reverse=True)
        top_services = []
        for i, (service, share) in enumerate(sorted_services[:5], 1):  # 上位5社
            top_services.append({
                "service": service,
                "share": round(share * 100, 1),  # パーセンテージで表示
                "rank": i
            })

        # 6. 市場構造分類
        market_structure = self._classify_market_structure(hhi_score, top_services)

        # 7. 公平性への影響評価
        fairness_implications = self._assess_fairness_implications(hhi_score, concentration_level, top_services)

        # 8. 計算詳細
        calculation_details = {
            "total_services": len(shares),
            "effective_competitors": self._count_effective_competitors(shares),
            "largest_share": round(max(shares.values()) * 100, 1),
            "smallest_share": round(min(shares.values()) * 100, 1),
            "share_variance": round(np.var(list(shares.values())) * 10000, 2)
        }

        return {
            "hhi_score": round(hhi_score, 1),
            "concentration_level": concentration_level,
            "market_structure": market_structure,
            "top_services": top_services,
            "fairness_implications": fairness_implications,
            "calculation_details": calculation_details
        }

    except Exception as e:
        return self._create_empty_hhi_result(f"HHI計算エラー: {str(e)}")
```

#### 2.1.2 `_calculate_enterprise_hhi`
```python
def _calculate_enterprise_hhi(self, market_caps: Dict[str, Any], category: str, subcategory: str) -> Dict[str, Any]:
    """
    企業レベルでのHHIを算出

    Parameters:
    -----------
    market_caps : Dict[str, Any]
        時価総額データ（src/data/market_caps.json）
    category : str
        カテゴリ名
    subcategory : str
        サブカテゴリ名

    Returns:
    --------
    Dict[str, Any]
        企業HHI分析結果
    """
    try:
        # 1. 対象カテゴリ・サブカテゴリの時価総額データを抽出
        category_data = market_caps.get(category, {})
        subcategory_data = category_data.get(subcategory, {})

        if not subcategory_data:
            return self._create_empty_hhi_result("企業時価総額データが不足")

        # 2. 有効な時価総額データを抽出
        caps = {}
        for enterprise, cap in subcategory_data.items():
            if isinstance(cap, (int, float)) and cap > 0:
                caps[enterprise] = float(cap)

        if not caps:
            return self._create_empty_hhi_result("有効な時価総額データがありません")

        # 3. 時価総額を市場シェアに変換
        total_market_cap = sum(caps.values())
        shares = {enterprise: cap / total_market_cap for enterprise, cap in caps.items()}

        # 4. HHI計算
        hhi_score = sum(share ** 2 for share in shares.values()) * 10000

        # 5. 集中度レベル判定
        concentration_level = self._interpret_hhi_level(hhi_score)

        # 6. 企業規模別シェア計算
        enterprise_tiers = self._calculate_enterprise_tiers(caps)

        # 7. 市場支配力分析
        market_power_analysis = self._analyze_market_power(hhi_score, enterprise_tiers)

        # 8. バイアスリスク評価
        bias_risk_assessment = self._assess_bias_risk_from_concentration(hhi_score, concentration_level)

        # 9. 計算詳細
        calculation_details = {
            "total_enterprises": len(caps),
            "large_enterprises": len([cap for cap in caps.values() if cap >= 1e12]),  # 1兆円以上
            "total_market_cap": round(total_market_cap / 1e12, 2),  # 兆円単位
            "largest_market_cap": round(max(caps.values()) / 1e12, 2),
            "smallest_market_cap": round(min(caps.values()) / 1e12, 2)
        }

        return {
            "hhi_score": round(hhi_score, 1),
            "concentration_level": concentration_level,
            "enterprise_tiers": enterprise_tiers,
            "market_power_analysis": market_power_analysis,
            "bias_risk_assessment": bias_risk_assessment,
            "calculation_details": calculation_details
        }

    except Exception as e:
        return self._create_empty_hhi_result(f"企業HHI計算エラー: {str(e)}")
```

#### 2.1.3 `_analyze_concentration_bias_correlation`
```python
def _analyze_concentration_bias_correlation(self,
                                          service_hhi: Dict[str, Any],
                                          enterprise_hhi: Dict[str, Any],
                                          bias_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    集中度-バイアス相関分析

    Parameters:
    -----------
    service_hhi : Dict[str, Any]
        サービスHHI分析結果
    enterprise_hhi : Dict[str, Any]
        企業HHI分析結果
    bias_metrics : Dict[str, Any]
        バイアス指標データ

    Returns:
    --------
    Dict[str, Any]
        相関分析結果
    """
    try:
        # 1. バイアス指標の抽出
        bias_indices = self._extract_bias_indices(bias_metrics)

        if not bias_indices:
            return self._create_empty_correlation_result("バイアス指標データが不足")

        # 2. サービスHHI-バイアス相関計算
        service_hhi_score = service_hhi.get("hhi_score", 0)
        service_correlation = self._calculate_hhi_bias_correlation(service_hhi_score, bias_indices)

        # 3. 企業HHI-バイアス相関計算
        enterprise_hhi_score = enterprise_hhi.get("hhi_score", 0)
        enterprise_correlation = self._calculate_hhi_bias_correlation(enterprise_hhi_score, bias_indices)

        # 4. 相関の有意性判定
        correlation_significance = self._determine_correlation_significance(
            service_correlation, enterprise_correlation
        )

        # 5. 解釈生成
        interpretation = self._generate_correlation_interpretation(
            service_correlation, enterprise_correlation, correlation_significance
        )

        # 6. 集中度レベル別分析
        concentration_level_analysis = self._analyze_by_concentration_level(
            service_hhi, enterprise_hhi, bias_indices
        )

        return {
            "correlation_analysis": {
                "service_hhi_bias_correlation": round(service_correlation, 3),
                "enterprise_hhi_bias_correlation": round(enterprise_correlation, 3),
                "correlation_significance": correlation_significance,
                "interpretation": interpretation
            },
            "concentration_level_analysis": concentration_level_analysis
        }

    except Exception as e:
        return self._create_empty_correlation_result(f"相関分析エラー: {str(e)}")
```

#### 2.1.4 `_generate_market_structure_insights`
```python
def _generate_market_structure_insights(self,
                                      service_hhi: Dict[str, Any],
                                      enterprise_hhi: Dict[str, Any]) -> List[str]:
    """
    市場構造インサイト生成

    Parameters:
    -----------
    service_hhi : Dict[str, Any]
        サービスHHI分析結果
    enterprise_hhi : Dict[str, Any]
        企業HHI分析結果

    Returns:
    --------
    List[str]
        市場構造インサイトリスト
    """
    insights = []

    try:
        service_score = service_hhi.get("hhi_score", 0)
        enterprise_score = enterprise_hhi.get("hhi_score", 0)
        service_level = service_hhi.get("concentration_level", "不明")
        enterprise_level = enterprise_hhi.get("concentration_level", "不明")

        # 1. 市場集中度の全体的評価
        if service_score >= 2500 and enterprise_score >= 2500:
            insights.append("高集中市場構造により競争制限的なバイアスが発生")
        elif service_score >= 1500 or enterprise_score >= 1500:
            insights.append("中程度の市場集中により一部企業へのバイアスが観察される")
        else:
            insights.append("市場集中度は低いが、他の要因によるバイアスが存在")

        # 2. 企業支配力の影響
        if enterprise_score >= 2500:
            insights.append("大企業の市場支配力が検索結果の偏りを助長")
        elif enterprise_score >= 1500:
            insights.append("企業規模による市場支配力がバイアスに影響")

        # 3. サービス集中の影響
        if service_score >= 2500:
            insights.append("サービス市場の寡占構造が特定サービスへの露出を促進")

        # 4. 改善提案
        if service_score >= 2000 or enterprise_score >= 2000:
            insights.append("市場集中度の低下によりバイアス軽減が期待される")

        # 5. 公平性への影響
        if service_score >= 2500 and enterprise_score >= 2500:
            insights.append("上位企業への過度な露出が公平性を損なう可能性")

        # 6. 構造的改善の必要性
        if service_score >= 3000 or enterprise_score >= 3000:
            insights.append("市場構造の改善がバイアス軽減の鍵となる")

        return insights

    except Exception as e:
        return [f"インサイト生成エラー: {str(e)}"]
```

### 2.2 ヘルパーメソッド

#### 2.2.1 `_interpret_hhi_level`
```python
def _interpret_hhi_level(self, hhi_score: float) -> str:
    """
    HHI値から集中度レベルを判定

    Parameters:
    -----------
    hhi_score : float
        HHI値

    Returns:
    --------
    str
        集中度レベル
    """
    if hhi_score < 1500:
        return "非集中市場"
    elif hhi_score < 2500:
        return "中程度集中市場"
    else:
        return "高集中市場"
```

#### 2.2.2 `_classify_market_structure`
```python
def _classify_market_structure(self, hhi_score: float, top_services: List[Dict]) -> str:
    """
    市場構造を分類

    Parameters:
    -----------
    hhi_score : float
        HHI値
    top_services : List[Dict]
        上位サービスリスト

    Returns:
    --------
    str
        市場構造分類
    """
    if hhi_score >= 3000:
        return "独占的寡占市場"
    elif hhi_score >= 2500:
        return "寡占市場"
    elif hhi_score >= 1500:
        return "寡占的競争市場"
    else:
        return "競争市場"
```

#### 2.2.3 `_calculate_enterprise_tiers`
```python
def _calculate_enterprise_tiers(self, market_caps: Dict[str, float]) -> Dict[str, float]:
    """
    企業規模別シェアを計算

    Parameters:
    -----------
    market_caps : Dict[str, float]
        企業別時価総額

    Returns:
    --------
    Dict[str, float]
        企業規模別シェア
    """
    total_cap = sum(market_caps.values())

    large_cap = sum(cap for cap in market_caps.values() if cap >= 1e12)  # 1兆円以上
    medium_cap = sum(cap for cap in market_caps.values() if 1e11 <= cap < 1e12)  # 1000億円-1兆円
    small_cap = sum(cap for cap in market_caps.values() if cap < 1e11)  # 1000億円未満

    return {
        "large": round(large_cap / total_cap * 100, 1),
        "medium": round(medium_cap / total_cap * 100, 1),
        "small": round(small_cap / total_cap * 100, 1)
    }
```

#### 2.2.4 `_assess_bias_risk_from_concentration`
```python
def _assess_bias_risk_from_concentration(self, hhi_score: float, concentration_level: str) -> str:
    """
    集中度からバイアスリスクを評価

    Parameters:
    -----------
    hhi_score : float
        HHI値
    concentration_level : str
        集中度レベル

    Returns:
    --------
    str
        バイアスリスク評価
    """
    if hhi_score >= 3000:
        return "極めて高いバイアスリスク"
    elif hhi_score >= 2500:
        return "高いバイアスリスク"
    elif hhi_score >= 1500:
        return "中程度のバイアスリスク"
    else:
        return "低いバイアスリスク"
```

### 2.3 ユーティリティメソッド

#### 2.3.1 `_create_empty_hhi_result`
```python
def _create_empty_hhi_result(self, error_message: str) -> Dict[str, Any]:
    """
    空のHHI結果を作成（エラー時）

    Parameters:
    -----------
    error_message : str
        エラーメッセージ

    Returns:
    --------
    Dict[str, Any]
        空のHHI結果
    """
    return {
        "hhi_score": 0.0,
        "concentration_level": "不明",
        "market_structure": "不明",
        "top_services": [],
        "fairness_implications": f"計算不可: {error_message}",
        "calculation_details": {"error": error_message}
    }
```

#### 2.3.2 `_count_effective_competitors`
```python
def _count_effective_competitors(self, shares: Dict[str, float]) -> int:
    """
    実効競争者数を計算

    Parameters:
    -----------
    shares : Dict[str, float]
        市場シェア辞書

    Returns:
    --------
    int
        実効競争者数
    """
    # シェア5%以上の企業を実効競争者とみなす
    return len([share for share in shares.values() if share >= 0.05])
```

## 3. 既存メソッドの拡張

### 3.1 `_analyze_relative_bias`メソッドの拡張

```python
def _analyze_relative_bias(self, sentiment_analysis: Dict) -> Dict[str, Any]:
    """
    相対バイアス分析（HHI分析機能を追加）
    """
    # 既存の相対バイアス分析ロジック
    relative_analysis = self._existing_relative_bias_logic()

    try:
        # 市場データの読み込み
        market_shares = self._load_market_data()
        market_caps = self._load_market_data()

        # 各カテゴリ・サブカテゴリでHHI分析を実行
        market_concentration_analysis = {}

        for category, category_data in sentiment_analysis.items():
            market_concentration_analysis[category] = {}

            for subcategory, subcategory_data in category_data.items():
                # サービスレベルHHI算出
                service_hhi = self._calculate_service_hhi(
                    market_shares, category, subcategory
                )

                # 企業レベルHHI算出
                enterprise_hhi = self._calculate_enterprise_hhi(
                    market_caps, category, subcategory
                )

                # 集中度-バイアス相関分析
                bias_metrics = subcategory_data.get("entities", {})
                concentration_correlation = self._analyze_concentration_bias_correlation(
                    service_hhi, enterprise_hhi, bias_metrics
                )

                # 市場構造インサイト生成
                market_insights = self._generate_market_structure_insights(
                    service_hhi, enterprise_hhi
                )

                market_concentration_analysis[category][subcategory] = {
                    "service_hhi": service_hhi,
                    "enterprise_hhi": enterprise_hhi,
                    "concentration_bias_correlation": concentration_correlation,
                    "market_structure_insights": market_insights
                }

        # 既存の分析結果に市場集中度分析を追加
        relative_analysis["market_concentration_analysis"] = market_concentration_analysis

        return relative_analysis

    except Exception as e:
        # エラー時は既存の分析結果のみを返す
        self.logger.error(f"市場集中度分析エラー: {str(e)}")
        return relative_analysis
```

## 4. エラーハンドリング

### 4.1 データ検証
- 市場データの存在確認
- データ形式の妥当性チェック
- 数値範囲の検証

### 4.2 計算エラー対応
- ゼロ除算エラーの回避
- データ不足時の適切な処理
- 異常値の検出と処理

### 4.3 ログ出力
- 計算過程のログ記録
- エラー情報の詳細記録
- パフォーマンス情報の記録

## 5. パフォーマンス最適化

### 5.1 計算効率化
- 不要なループの削減
- メモリ使用量の最適化
- 並列処理の検討

### 5.2 キャッシュ機能
- 市場データのキャッシュ
- 計算結果の一時保存
- 重複計算の回避

---

**作成日**: 2025年1月27日
**作成者**: AI Assistant
**バージョン**: 1.0