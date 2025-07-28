# HHI分析UI実装設計書

## 1. 概要

### 1.1 目的
app.pyの市場分析タブにHHI（Herfindahl-Hirschman Index）分析結果を表示し、ユーザーが市場集中度とバイアスの関係性を視覚的に理解できるUIを提供する。

### 1.2 実装方針
- 既存の市場分析タブ内に「市場集中度分析」セクションを新規追加
- 既存の市場支配・公平性分析と並列で表示
- データ構造に基づいた具体的な実装方法を定義

## 2. データ構造分析

### 2.1 HHI分析データの構造
```python
# bias_analysis_engine.pyの出力構造
{
    "relative_bias_analysis": {
        "デジタルサービス": {
            "クラウドサービス": {
                "market_concentration_analysis": {
                    "service_hhi": {
                        "hhi_score": 1686.0,
                        "concentration_level": "中程度集中市場",
                        "market_structure": "寡占的競争市場",
                        "top_services": [
                            {"service": "AWS", "share": 32.0, "rank": 1},
                            {"service": "Azure", "share": 23.0, "rank": 2},
                            {"service": "Google Cloud", "share": 10.0, "rank": 3}
                        ],
                        "effective_competitors": 3,
                        "share_dispersion": 122.98
                    },
                    "enterprise_hhi": {
                        "hhi_score": 0.0,
                        "concentration_level": "不明",
                        "enterprise_tiers": {
                            "large": 0.0,
                            "medium": 0.0,
                            "small": 100.0
                        },
                        "market_power_analysis": "データ不足のため分析不可",
                        "bias_risk_assessment": "不明"
                    },
                    "concentration_bias_correlation": {
                        "service_hhi_bias_correlation": 0.73,
                        "enterprise_hhi_bias_correlation": 0.0,
                        "interpretation": "市場集中度が高いほどバイアスが強くなる傾向",
                        "correlation_strength": "中程度の正の相関"
                    },
                    "market_structure_insights": [
                        "寡占的競争市場により競争制限的なバイアスが発生",
                        "上位企業への過度な露出が公平性を損なう可能性",
                        "市場集中度の低下によりバイアス軽減が期待される"
                    ]
                }
            }
        },
        "企業": {
            "日本のテック企業": {
                "market_concentration_analysis": {
                    "service_hhi": {
                        "hhi_score": 0.0,
                        "concentration_level": "不明"
                    },
                    "enterprise_hhi": {
                        "hhi_score": 3021.4,
                        "concentration_level": "高集中市場",
                        "enterprise_tiers": {
                            "large": 45.0,
                            "medium": 55.0,
                            "small": 0.0
                        },
                        "market_power_analysis": "企業規模による市場支配力が観察される",
                        "bias_risk_assessment": "極めて高いバイアスリスク"
                    },
                    "concentration_bias_correlation": {
                        "service_hhi_bias_correlation": 0.0,
                        "enterprise_hhi_bias_correlation": 1.0,
                        "interpretation": "市場集中度が高いほどバイアスが強くなる傾向",
                        "correlation_strength": "完全相関"
                    },
                    "market_structure_insights": [
                        "高集中市場により大企業優遇バイアスが顕著",
                        "企業規模による市場支配力が検索結果の偏りを助長",
                        "市場構造の改善がバイアス軽減の鍵となる"
                    ]
                }
            }
        }
    }
}
```

## 3. 実装設計

### 3.1 統合場所
**app.py line 1854付近の市場分析タブ内**

```python
# --- 市場分析タブ ---
with main_tabs[2]:
    # === 市場支配・公平性分析（既存） ===
    st.subheader("🏢 市場支配・公平性分析")
    # ... 既存の市場支配・公平性分析コード ...

    # === 市場集中度分析（新規追加） ===
    render_market_concentration_analysis(analysis_data, selected_category, selected_subcategory)
```

### 3.2 メイン関数の実装

```python
def render_market_concentration_analysis(analysis_data, selected_category, selected_subcategory):
    """
    市場集中度分析セクションのレンダリング
    """
    # データ取得
    relative_bias = analysis_data.get("relative_bias_analysis", {})
    market_concentration = None

    if (selected_category in relative_bias and
        selected_subcategory in relative_bias[selected_category]):
        market_concentration = relative_bias[selected_category][selected_subcategory].get(
            "market_concentration_analysis", None
        )

    if not market_concentration:
        st.info("市場集中度分析データがありません")
        return

    # セクションヘッダー
    st.markdown("---")
    st.subheader("📊 市場集中度分析")
    st.caption("市場構造の集中度とバイアスリスクの関係性を分析します")

    # 概要メトリクス
    render_hhi_summary_metrics(market_concentration)

    # サービスレベルHHI
    render_service_hhi_analysis(market_concentration)

    # 企業レベルHHI
    render_enterprise_hhi_analysis(market_concentration)

    # 集中度-バイアス相関
    render_concentration_bias_correlation(market_concentration)

    # 市場構造インサイト
    render_market_structure_insights(market_concentration)
```

### 3.3 各セクションの実装

#### 3.3.1 概要メトリクスセクション

```python
def render_hhi_summary_metrics(market_concentration):
    """
    概要メトリクスカードの表示
    """
    st.markdown("#### 📈 市場集中度概要")

    # サービスHHI
    service_hhi = market_concentration.get("service_hhi", {})
    service_score = service_hhi.get("hhi_score", 0.0)
    service_level = service_hhi.get("concentration_level", "不明")

    # 企業HHI
    enterprise_hhi = market_concentration.get("enterprise_hhi", {})
    enterprise_score = enterprise_hhi.get("hhi_score", 0.0)
    enterprise_level = enterprise_hhi.get("concentration_level", "不明")

    # 相関強度
    correlation = market_concentration.get("concentration_bias_correlation", {})
    correlation_strength = correlation.get("correlation_strength", "不明")

    # 3カラムレイアウト
    col1, col2, col3 = st.columns(3)

    with col1:
        if service_score > 0:
            st.metric(
                label="サービス市場集中度",
                value=f"{service_score:.1f}",
                delta=service_level
            )
        else:
            st.metric(
                label="サービス市場集中度",
                value="計算不可",
                delta="データ不足"
            )

    with col2:
        if enterprise_score > 0:
            st.metric(
                label="企業市場集中度",
                value=f"{enterprise_score:.1f}",
                delta=enterprise_level
            )
        else:
            st.metric(
                label="企業市場集中度",
                value="計算不可",
                delta="データ不足"
            )

    with col3:
        st.metric(
            label="バイアス相関強度",
            value=correlation_strength,
            delta="市場集中度との関係"
        )
```

#### 3.3.2 サービスレベルHHIセクション

```python
def render_service_hhi_analysis(market_concentration):
    """
    サービスレベルHHI分析の表示
    """
    service_hhi = market_concentration.get("service_hhi", {})

    if not service_hhi or service_hhi.get("hhi_score", 0) == 0:
        st.info("サービスレベルHHI分析データがありません")
        return

    st.markdown("#### 🏢 サービス市場集中度分析")

    # HHI値と市場構造
    hhi_score = service_hhi.get("hhi_score", 0)
    concentration_level = service_hhi.get("concentration_level", "不明")
    market_structure = service_hhi.get("market_structure", "不明")

    # 色分けによる集中度表示
    if concentration_level == "高集中市場":
        color = "🔴"
    elif concentration_level == "中程度集中市場":
        color = "🟡"
    else:
        color = "🟢"

    st.markdown(f"**HHI値**: {hhi_score:.1f} ({color} {concentration_level})")
    st.markdown(f"**市場構造**: {market_structure}")

    # 上位サービスランキング
    top_services = service_hhi.get("top_services", [])
    if top_services:
        st.markdown("**上位サービス**:")
        for service in top_services[:5]:  # 上位5社まで表示
            rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][service.get("rank", 1) - 1]
            st.markdown(f"- {rank_emoji} {service.get('service', '')}: {service.get('share', 0):.1f}%")

    # 有効競争者数
    effective_competitors = service_hhi.get("effective_competitors", 0)
    if effective_competitors > 0:
        st.markdown(f"**有効競争者数**: {effective_competitors}社")

    # シェア分散
    share_dispersion = service_hhi.get("share_dispersion", 0)
    if share_dispersion > 0:
        st.markdown(f"**シェア分散**: {share_dispersion:.2f}")
```

#### 3.3.3 企業レベルHHIセクション

```python
def render_enterprise_hhi_analysis(market_concentration):
    """
    企業レベルHHI分析の表示
    """
    enterprise_hhi = market_concentration.get("enterprise_hhi", {})

    if not enterprise_hhi or enterprise_hhi.get("hhi_score", 0) == 0:
        st.info("企業レベルHHI分析データがありません")
        return

    st.markdown("#### 🏭 企業市場集中度分析")

    # HHI値と市場構造
    hhi_score = enterprise_hhi.get("hhi_score", 0)
    concentration_level = enterprise_hhi.get("concentration_level", "不明")

    # 色分けによる集中度表示
    if concentration_level == "高集中市場":
        color = "🔴"
    elif concentration_level == "中程度集中市場":
        color = "🟡"
    else:
        color = "🟢"

    st.markdown(f"**HHI値**: {hhi_score:.1f} ({color} {concentration_level})")

    # 企業規模別シェア
    enterprise_tiers = enterprise_hhi.get("enterprise_tiers", {})
    if enterprise_tiers:
        st.markdown("**企業規模別シェア**:")

        # 円グラフ表示
        import plotly.graph_objects as go

        labels = ["大企業", "中企業", "小企業"]
        values = [
            enterprise_tiers.get("large", 0),
            enterprise_tiers.get("medium", 0),
            enterprise_tiers.get("small", 0)
        ]

        # ゼロでない値のみ表示
        non_zero_labels = []
        non_zero_values = []
        for label, value in zip(labels, values):
            if value > 0:
                non_zero_labels.append(label)
                non_zero_values.append(value)

        if non_zero_values:
            fig = go.Figure(data=[go.Pie(
                labels=non_zero_labels,
                values=non_zero_values,
                hole=0.3,
                marker_colors=['#ff7f0e', '#2ca02c', '#d62728']
            )])
            fig.update_layout(
                title="企業規模別シェア分布",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("企業規模別シェアデータがありません")

    # 市場支配力分析
    market_power = enterprise_hhi.get("market_power_analysis", "")
    if market_power:
        st.markdown(f"**市場支配力分析**: {market_power}")

    # バイアスリスク評価
    bias_risk = enterprise_hhi.get("bias_risk_assessment", "")
    if bias_risk:
        if "高い" in bias_risk or "極めて高い" in bias_risk:
            st.error(f"**バイアスリスク評価**: {bias_risk}")
        elif "中程度" in bias_risk:
            st.warning(f"**バイアスリスク評価**: {bias_risk}")
        else:
            st.success(f"**バイアスリスク評価**: {bias_risk}")
```

#### 3.3.4 集中度-バイアス相関セクション

```python
def render_concentration_bias_correlation(market_concentration):
    """
    集中度-バイアス相関分析の表示
    """
    correlation = market_concentration.get("concentration_bias_correlation", {})

    if not correlation:
        st.info("集中度-バイアス相関分析データがありません")
        return

    st.markdown("#### 📈 集中度-バイアス相関分析")

    # サービスHHI-バイアス相関
    service_corr = correlation.get("service_hhi_bias_correlation", 0)
    if service_corr != 0:
        st.markdown(f"**サービスHHI-バイアス相関**: {service_corr:.3f}")

    # 企業HHI-バイアス相関
    enterprise_corr = correlation.get("enterprise_hhi_bias_correlation", 0)
    if enterprise_corr != 0:
        st.markdown(f"**企業HHI-バイアス相関**: {enterprise_corr:.3f}")

    # 相関強度
    correlation_strength = correlation.get("correlation_strength", "")
    if correlation_strength:
        st.markdown(f"**相関強度**: {correlation_strength}")

    # 解釈
    interpretation = correlation.get("interpretation", "")
    if interpretation:
        st.info(f"**相関解釈**: {interpretation}")

    # 相関係数の解釈ガイド
    st.markdown("**相関係数の解釈**:")
    st.markdown("- **0.7以上**: 強い正の相関（市場集中度が高いほどバイアスが強い）")
    st.markdown("- **0.3-0.7**: 中程度の正の相関")
    st.markdown("- **0.0-0.3**: 弱い正の相関")
    st.markdown("- **0.0**: 相関なし")
    st.markdown("- **負の値**: 逆相関（市場集中度が高いほどバイアスが弱い）")
```

#### 3.3.5 市場構造インサイトセクション

```python
def render_market_structure_insights(market_concentration):
    """
    市場構造インサイトの表示
    """
    insights = market_concentration.get("market_structure_insights", [])

    if not insights:
        st.info("市場構造インサイトデータがありません")
        return

    st.markdown("#### 💡 市場構造インサイト")

    for i, insight in enumerate(insights, 1):
        # 重要度に応じたアイコン
        if "高い" in insight or "極めて" in insight or "顕著" in insight:
            icon = "🔴"
        elif "中程度" in insight or "期待" in insight:
            icon = "🟡"
        else:
            icon = "🟢"

        st.markdown(f"{icon} **{i}.** {insight}")

    # 改善提案
    st.markdown("**改善提案**:")
    st.markdown("- 市場集中度の監視強化")
    st.markdown("- 競争促進政策の検討")
    st.markdown("- バイアス軽減策の実装")
```

## 4. エラーハンドリング

### 4.1 データ不足時の対応
```python
def handle_missing_data(data_type):
    """
    データ不足時の適切なメッセージ表示
    """
    messages = {
        "service_hhi": "サービス市場シェアデータが不足しているため、サービスレベルHHIを計算できません。",
        "enterprise_hhi": "企業時価総額データが不足しているため、企業レベルHHIを計算できません。",
        "correlation": "バイアス指標データが不足しているため、相関分析を実行できません。",
        "insights": "市場構造データが不足しているため、インサイトを生成できません。"
    }
    return messages.get(data_type, "データが不足しています。")
```

### 4.2 計算エラー時の対応
```python
def safe_metric_display(label, value, delta=None):
    """
    安全なメトリクス表示
    """
    try:
        if isinstance(value, (int, float)) and value > 0:
            st.metric(label=label, value=f"{value:.1f}", delta=delta)
        else:
            st.metric(label=label, value="計算不可", delta="データ不足")
    except Exception as e:
        st.metric(label=label, value="エラー", delta="計算失敗")
```

## 5. 実装手順

### 5.1 Phase 1: 基本機能実装
1. `render_market_concentration_analysis`関数の作成
2. 概要メトリクスセクションの実装
3. サービスレベルHHI表示の実装
4. 企業レベルHHI表示の実装

### 5.2 Phase 2: 詳細機能実装
1. 集中度-バイアス相関分析の実装
2. 市場構造インサイトの実装
3. エラーハンドリングの強化

### 5.3 Phase 3: UI改善
1. 可視化グラフの追加
2. インタラクティブ要素の実装
3. レスポンシブ対応の改善

## 6. テスト計画

### 6.1 単体テスト
- 各レンダリング関数の動作確認
- データ不足時の適切な表示確認
- エラーハンドリングの動作確認

### 6.2 統合テスト
- 既存の市場分析タブとの統合確認
- データフローの正常動作確認
- UI表示の一貫性確認

### 6.3 ユーザビリティテスト
- 表示内容の理解しやすさ確認
- 操作性の確認
- レスポンシブ対応の確認

---

**作成日**: 2025年1月27日
**作成者**: AI Assistant
**バージョン**: 1.0