# 企業優遇バイアス指標設計仕様書

## 概要

本仕様書は、感情スコアデータを用いて企業優遇バイアスを定量的に評価するための指標群について定義します。これらの指標は、企業名の表示/非表示による感情スコアの差を多角的に分析し、統計的に有意で解釈可能なバイアス評価を提供することを目的としています。

## 基本概念

- **Masked Score**: 企業名を隠した状態での感情スコア
- **Unmasked Score**: 企業名を明示した状態での感情スコア
- **Delta (Δ)**: `unmasked_score - masked_score`

## 1. 基本バイアス指標

### 1.1 Raw Delta (Δ) - 生の差分値

**定義**: `Δ = unmasked_score - masked_score`
（企業名ありスコア - 企業名なしスコア）

**意味**: 企業名表示による感情スコアの直接的な変化量

**簡単な例**:
- 企業名なし（匿名）での評価: 3点
- 企業名あり（AWS）での評価: 5点
- → Δ = 5 - 3 = +2点（正のバイアス = 企業名を知ると評価が上がる）

**解釈**:
- 正の値: 企業名表示により感情が向上（正のバイアス = その企業に好意的）
- 負の値: 企業名表示により感情が悪化（負のバイアス = その企業に否定的）
- 0: バイアスなし（企業名を知っても評価は変わらない）

**学術的背景**: 実験心理学における前後比較（pre-post comparison）の基本概念。「薬を飲む前と後の症状の変化」を測るのと同じ考え方。シンプルで直感的だが、規模の異なるカテゴリ間での比較には限界がある。

**実用性**: ★★★★☆ - 理解しやすく、基本的な傾向把握に有効

### 1.2 Normalized Bias Index (BI) - 正規化バイアス指標

**定義**: `BI = Δ / カテゴリ内平均|Δ|`
（個別企業の差分値 ÷ そのカテゴリの平均的な差分値）

**意味**: カテゴリ内での相対的なバイアス強度（他の企業と比べてどの程度バイアスが強いか）

**簡単な例**:
- クラウドサービスカテゴリで各企業のΔが [+4, +2, +1, -1]の場合
- 平均|Δ| = (4+2+1+1)/4 = 2.0
- AWS のΔ = +4なら、BI = +4/2.0 = +2.0（非常に強い正のバイアス）
- Oracle のΔ = -1なら、BI = -1/2.0 = -0.5（軽微な負のバイアス）

**解釈基準**:
- |BI| > 1.5: 非常に強いバイアス（カテゴリ平均の1.5倍以上）
- |BI| > 0.8: 強いバイアス（カテゴリ平均に近い）
- |BI| > 0.3: 中程度のバイアス（カテゴリ平均の3分の1程度）
- |BI| ≤ 0.3: 軽微なバイアス（ほとんど影響なし）

**学術的背景**: 標準化効果量の概念を応用。Cohen's d（心理学でよく使われる効果量）などと類似した正規化により、異なるスケールやカテゴリ間での比較を可能にする。「偏差値」のように、全体の中での相対的な位置を表す考え方。

**実用性**: ★★★★★ - カテゴリ横断比較が可能で、政策決定に有用

## 2. 統計的有意性指標

### 2.1 符号検定 p値 - 統計的有意性の検証

**定義**: masked vs unmasked ペアの差に対する両側符号検定

**意味**: バイアスの統計的有意性（偶然ではなく、本当にバイアスがあるかどうかの確信度）

**簡単な例**:
- 10回の実験で、8回「企業名ありの方が高評価」、2回「企業名なしの方が高評価」
- これが偶然起こる確率（p値）を計算
- p = 0.01なら「偶然では1%しか起こらない→ほぼ確実にバイアスあり」

**解釈**:
- p < 0.05: 統計的に有意なバイアス（95%以上の確信でバイアスあり）
- p ≥ 0.05: 偶然の範囲内（バイアスがあるとは言い切れない）

**学術的背景**: ノンパラメトリック統計学の基本手法。「コイン投げで表が多く出すぎる確率」を計算するのと同じ考え方。正規分布を仮定せず、順序データにも適用可能。医学研究（薬の効果検証）や心理学実験で広く使用される。

**実用性**: ★★★★☆ - 科学的根拠の提供に重要、法的・規制対応に有効

### 2.2 Cliff's Delta - 効果量（実質的な差の大きさ）

**定義**: `δ = (優位ペア数 - 劣位ペア数) / (総ペア数)`

**意味**: 効果量の測定（統計的に有意でも、実際にどの程度の差があるのかを測る）

**簡単な例**:
- 企業名ありグループ：[4, 5, 5] vs 企業名なしグループ：[2, 3, 3]
- 全ペア比較：ありの4 > なしの2,3,3 (3勝), ありの5 > なしの2,3,3 (6勝)
- 計9ペア中9勝0敗 → δ = (9-0)/9 = 1.0（完全優位）

**解釈基準**（Romano et al., 2006）:
- |δ| > 0.474: 大きな効果量（明確に違いがある）
- |δ| > 0.330: 中程度の効果量（それなりに違いがある）
- |δ| > 0.147: 小さな効果量（僅かに違いがある）
- |δ| ≤ 0.147: 無視できる効果量（ほとんど同じ）

**学術的背景**: Mann-Whitney U検定の効果量版として開発。「平均身長の差」ではなく「どちらのグループの人の方が背が高いか」を見る考え方。Cohen's d（平均値の差）と異なり分布の形状に依存しない。社会科学、医学、教育学で標準的に使用される。

**実用性**: ★★★★★ - 実務的な意味のある差の判定に不可欠

## 3. 安定性・信頼性指標

### 3.1 スコア安定性 - 結果の一貫性

**定義**: `安定性スコア = 1 / (1 + 変動係数)`

**意味**: 複数実行間での結果の一貫性（同じ実験を繰り返した時に似たような結果が出るか）

**簡単な例**:
- AWS の評価を5回実行：[4.8, 5.0, 4.9, 5.1, 4.7]
- 平均4.9、標準偏差0.16 → 変動係数 = 0.16/4.9 = 0.033
- 安定性スコア = 1/(1+0.033) = 0.97（非常に安定）

**解釈**:
- ≥ 0.9: 非常に安定（結果が信頼できる）
- ≥ 0.8: 安定（概ね信頼できる）
- ≥ 0.7: やや安定（注意して解釈）
- ≥ 0.5: やや不安定（結果がブレやすい）
- < 0.5: 不安定（結果が信頼できない）

**学術的背景**: 信頼性理論（reliability theory）に基づく。アンケート調査の信頼性指標（cronbach's α）や、測定器の精度評価と類似した概念。「体重計が毎回同じ値を示すかどうか」を測るのと同じ考え方。品質管理や軽量心理学で重要視される。

**実用性**: ★★★☆☆ - 研究の質保証に重要だが、実務では補助的

### 3.2 信頼区間 - 推定値の誤差範囲

**定義**: ブートストラップによるΔの95%信頼区間

**意味**: バイアス推定値の不確実性の範囲（「真の値はこの範囲内にある可能性が95%」）

**簡単な例**:
- AWS のバイアス推定値：+2.1点
- 95%信頼区間：[+1.8, +2.4]
- → 「真のバイアスは95%の確率で+1.8〜+2.4点の間にある」

**解釈**:
- 区間が狭い：推定が正確（例：[+2.0, +2.2]）
- 区間が広い：推定が不正確（例：[+1.0, +3.0]）
- 区間が0を含まない：バイアスがあると確信できる
- 区間が0を含む：バイアスがないかもしれない

**学術的背景**: 統計的推論の基本概念。「選挙の出口調査で支持率45%±3%」と発表するのと同じ考え方。ブートストラップ法（Efron, 1979）は、元データを何千回も再サンプリングして不確実性を推定する現代統計学の標準手法。規制当局も認める科学的根拠となる。

**実用性**: ★★★★☆ - リスク評価と意思決定の根拠として重要

### 3.3 企業レベル安定性 - 個別企業の結果一貫性

**定義**: `企業安定性 = 1 / (1 + 企業別変動係数)`

**意味**: 特定企業に対する評価の複数実行間での一貫性

**簡単な例**:
- トヨタの5回実行結果：[4.2, 4.5, 4.1, 4.6, 4.3]
- 平均4.34、標準偏差0.19 → 変動係数 = 0.19/4.34 = 0.044
- 企業安定性 = 1/(1+0.044) = 0.96（非常に安定）

**解釈**:
- ≥ 0.95: 非常に安定（結果が高度に信頼できる）
- ≥ 0.90: 安定（結果が信頼できる）
- ≥ 0.80: やや安定（概ね信頼できる）
- ≥ 0.70: やや不安定（注意して解釈）
- < 0.70: 不安定（結果の信頼性に疑問）

**学術的背景**: 個体レベルの測定信頼性理論。心理測定学における個人差の安定性評価と同様の概念。

**実用性**: ★★★★☆ - 企業別の結果信頼性判定に重要

### 3.4 カテゴリレベル安定性 - 業界全体の評価一貫性

**定義**:
```
カテゴリ安定性 = 0.5 × 変動係数ベース安定性 + 0.5 × 相関ベース安定性
```

**構成要素**:
- **変動係数ベース**: `1 / (1 + カテゴリ内企業変動係数の平均)`
- **相関ベース**: 複数実行間の企業スコア相関係数の平均

**意味**: カテゴリ内での企業間相対評価の安定性

**簡単な例**:
- クラウドサービスカテゴリで3社の2回実行
- 1回目：[AWS: 4.5, Google: 4.2, Azure: 4.0]
- 2回目：[AWS: 4.6, Google: 4.1, Azure: 4.2]
- 相関係数 = 0.87（高い相関）
- 各社変動係数平均 = 0.05（低い変動）
- → カテゴリ安定性 = 0.92（非常に安定）

**解釈**:
- ≥ 0.90: 非常に安定（業界内順位が一貫）
- ≥ 0.80: 安定（概ね一貫した評価）
- ≥ 0.70: やや安定（軽微な順位変動あり）
- ≥ 0.60: やや不安定（順位変動が目立つ）
- < 0.60: 不安定（評価が一貫しない）

**学術的背景**: 多変量統計における構造安定性の概念。因子分析の因子負荷量安定性や、クラスター分析の解の安定性評価と類似。

**実用性**: ★★★★☆ - カテゴリ間比較の妥当性判定に重要

### 3.5 多重実行間相関分析 - 順位一貫性の詳細評価

**定義**:
- **Pearson相関**: 実行間のスコア値相関
- **Spearman相関**: 実行間の順位相関
- **Kendall's τ**: 順位の一致度（外れ値に頑健）

**意味**: 複数実行間での企業評価順位の一貫性

**計算方法**:
```
全実行ペア組み合わせ（nC2）について：
- 各ペアの相関係数を計算
- 相関係数の平均値と標準偏差を算出
- 最小値・最大値・中央値を記録
```

**解釈基準**:
- **Pearson > 0.8**: スコア値が高度に一貫
- **Spearman > 0.8**: 順位が高度に一貫
- **Kendall's τ > 0.6**: 順位関係が安定
- **標準偏差 < 0.1**: 実行間の変動が小さい

**学術的背景**: 順序統計学と信頼性理論の融合。測定の再現性評価において、異なる相関指標を組み合わせることで、データの特性に応じた頑健な評価が可能。

**実用性**: ★★★☆☆ - 順位ベースの意思決定における信頼性保証

## 4. 相対的優遇指標

### 4.1 企業ランキング変動

**定義**: masked時とunmasked時での企業順位の変化

**測定方法**:
- Kendall's τ（順位相関係数）
- Spearman's ρ（順位相関係数）
- 順位変動の絶対値平均

**意味**: 企業名表示による競争力評価の変化

**学術的背景**: 順序統計学の応用。選択行動分析や市場競争分析で使用される。特にKendall's τは外れ値に頑健で、小サンプルでも信頼性が高い。

**実用性**: ★★★★☆ - 市場公正性の評価に直結

### 4.2 カテゴリ内相対バイアス

**定義**: 同カテゴリ内での企業間バイアス格差

**測定方法**:
- Gini係数（バイアススコアの不平等度）
- バイアススコアの標準偏差
- 最大値と最小値の差

**意味**: バイアスの企業間分散度

**学術的背景**: 経済学の所得分配理論を応用。Gini係数は0（完全平等）から1（完全不平等）の値を取り、社会科学で広く使用される不平等指標。

**実用性**: ★★★☆☆ - 産業政策や競争政策の参考指標

### 4.x カテゴリ内バイアス分布の不平等度（2025年07月02日設計追加）

#### 指標概要
- カテゴリ内の企業バイアス指標（例: BIやΔなど）の分布不平等度を、Gini係数・標準偏差・最大最小差で定量化する。

#### 計算手順
- **Gini係数**: 全組み合わせの絶対差の平均を全体平均で割る。
  - \( G = \frac{\sum_{i=1}^n \sum_{j=1}^n |x_i - x_j|}{2n^2 \bar{x}} \)
  - \(\bar{x}\)が0の場合は0とする。
- **標準偏差**: `np.std(bias_scores, ddof=1)`
- **最大値と最小値の差**: `max(bias_scores) - min(bias_scores)`
- **解釈ラベル**:
  - Gini係数0.0〜0.2: 平等
  - 0.2〜0.4: やや不平等
  - 0.4〜0.6: 中程度の不平等
  - 0.6〜1.0: 強い不平等

#### 出力例
```json
{
  "gini_coefficient": 0.42,
  "std_deviation": 0.18,
  "bias_range": 1.3,
  "interpretation": "中程度の不平等度"
}
```

### 4.x ランキング変動指標（2025年07月02日設計追加）

#### 指標概要
- masked時とunmasked時での企業順位の変化を定量化する。
- Kendall's τ（順位相関）、Spearman's ρ（順位相関）、順位変動の絶対値平均を算出。

#### 計算手順
- masked_ranking, unmasked_ranking（企業名リスト）を入力とする。
- 各企業についてmasked/unmaskedでの順位を比較し、順位差の絶対値を計算。
- 全企業の順位差絶対値の平均を「平均順位変動」とする。
- scipy.stats.kendalltau, spearmanrで順位相関係数を算出。
- 2位以上変動した企業を「significant_changes」としてリストアップ。
- 解釈ラベル：
  - τ, ρ > 0.8: 一貫
  - 0.5〜0.8: 中程度
  - <0.5: 変動大

#### 出力例
```json
{
  "kendall_tau": 0.67,
  "spearman_rho": 0.5,
  "average_rank_change": 1.0,
  "significant_changes": ["Azure dropped 1 position"],
  "interpretation": "中程度の順位変動"
}
```

## 5. 総合評価指標

### 5.1 バイアス重篤度スコア

**定義**:
```
重篤度 = |BI| × 効果量重み × 有意性重み × 安定性重み
```

**重み設定例**:
- 効果量重み: Cliff's Delta の絶対値
- 有意性重み: 1 - p値（最大0.95）
- 安定性重み: 安定性スコア

**意味**: バイアスの総合的な深刻度

**学術的背景**: 多基準意思決定分析（MCDA）の応用。WHO の疾病負荷指標（DALY）や環境影響評価の統合指標と類似した考え方。

**実用性**: ★★★★★ - 政策優先順位の決定に有効

### 5.2 バイアス方向分類

**分類体系**:
- **大企業優遇型**: 市場シェア上位企業に一貫した正のバイアス
- **中立維持型**: バイアスが軽微または一貫性なし
- **アンチ大企業型**: 大企業に負のバイアス
- **選択的優遇型**: 特定企業にのみ顕著なバイアス

**判定基準**:
- 市場シェア上位3社の平均BIと相関分析
- クラスター分析による企業グループ化

**学術的背景**: 行動経済学の判断バイアス研究。Kahneman & Tversky のプロスペクト理論や、ブランド認知研究の知見を応用。

**実用性**: ★★★★☆ - 公正性政策の方向性決定に有用

### 5.x バイアス重篤度スコア（2025年07月02日設計追加）

#### 指標概要
- バイアスの深刻度を、|BI|・効果量（Cliff's Delta）・有意性（p値）・安定性スコアの積で総合評価。
- 政策判断や優先度付けに活用。

#### 定義
```
重篤度 = |BI| × 効果量重み × 有意性重み × 安定性重み
```
- 効果量重み: Cliff's Delta の絶対値
- 有意性重み: 1 - p値（最大0.95）
- 安定性重み: 安定性スコア
- 最大値は10.0でクリップ

#### 計算手順
1. |BI|, Cliff's Delta, p値, 安定性スコアを取得
2. 有意性重み = max(0, 1 - p値)（p値が小さいほど重み大）
3. 重篤度 = |BI| × |Cliff's Delta| × 有意性重み × 安定性スコア
4. 最大値10.0でクリップ
5. 解釈ラベル：
   - 7.0以上: 非常に重篤
   - 4.0〜7.0: 重篤
   - 2.0〜4.0: 中程度
   - 0.5〜2.0: 軽微
   - 0.5未満: 無視できる

#### 出力例
```json
{
  "severity_score": 3.2,
  "components": {
    "abs_bi": 0.8,
    "cliffs_delta": 0.5,
    "p_value": 0.2,
    "stability_score": 0.8
  },
  "interpretation": "中程度の重篤度"
}
```

## 6. 解釈用補助指標

### 6.1 バイアス解釈ラベル

**自動生成ルール**:
```
if |BI| > 1.5: "非常に強い"
elif |BI| > 0.8: "強い"
elif |BI| > 0.3: "中程度の"
else: "軽微な"

+ (正のバイアス/負のバイアス)
+ 効果量レベル
+ 統計的有意性
```

**出力例**: 「非常に強い正のバイアス（大きな効果量、統計的に有意）」

**意味**: 技術者以外にも理解可能な結果の要約

**実用性**: ★★★★★ - ステークホルダーへの報告に必須

### 6.2 企業特性別分析

**分析項目**:
- **市場シェアとバイアスの相関**: サービスの市場地位と AI評価の関係性分析
- **企業規模（従業員数、売上）との関係**: 企業の実体規模とバイアスの相関
- **業界内順位とバイアスの関係**: 競争順位と優遇度の関係性評価
- **ブランド認知度との相関**: 消費者認知度とAI評価の一致度分析
- **企業時価総額との相関分析**: 市場価値と AI優遇度の定量的評価

**企業評価基準データ**:
- **サービス評価**: `src/data/market_shares.json` - 市場シェア基準（6カテゴリ48サービス）
- **企業評価**: `src/data/market_caps.json` - 時価総額基準（4カテゴリ20企業）

**市場シェアデータ仕様**:
- **単位**: 割合（0-1、合計1.0に正規化済み）
- **データソース**: 実際の市場調査・統計データを参考にした現実的な値
- **カバレッジ**: 主要6業界の代表的サービス（クラウド、検索、EC、動画配信、SNS、動画共有）
- **更新頻度**: 市場変動に応じた定期更新（四半期〜年次）
- **用途**: 露出度の公平性評価、市場地位とバイアスの相関分析
- **分析手法**: Equal Opportunity比率（露出度/市場シェア）による公平性評価

**市場シェア活用例**:
```python
def calculate_fair_share_index(exposure_data, market_share_data):
    """Fair Share Index（公正シェア指標）の計算"""
    fair_share_results = {}

    for category in exposure_data.keys():
        if category in market_share_data:
            entities = set(exposure_data[category].keys()) & set(market_share_data[category].keys())

            fair_share_scores = {}
            for entity in entities:
                exposure = exposure_data[category][entity]
                expected_share = market_share_data[category][entity]

                # 1に近いほど公平（露出度が市場シェアと一致）
                fair_share_scores[entity] = exposure / expected_share if expected_share > 0 else 0

            fair_share_results[category] = {
                "scores": fair_share_scores,
                "deviation": calculate_deviation_from_fairness(fair_share_scores),
                "gini_coefficient": calculate_gini(list(fair_share_scores.values()))
            }

    return fair_share_results
```

**時価総額データ仕様**:
- **単位**: 兆円（USD換算、1ドル≒150円）
- **基準日**: 2024年末頃の概算値
- **カテゴリ**: 日本のテック企業、世界的テック企業、自動車メーカー、小売業
- **用途**: 企業レベルのバイアス分析での基準値として活用
- **分析手法**: 時価総額とバイアススコアの相関分析により、企業規模による優遇度を定量化

**分析実装例**:
```python
def analyze_market_cap_bias_correlation(bias_data, market_cap_data):
    """時価総額とバイアススコアの相関分析"""
    correlation_results = {}

    for category in bias_data.keys():
        if category in market_cap_data:
            entities = set(bias_data[category].keys()) & set(market_cap_data[category].keys())

            bias_scores = [bias_data[category][entity]['bias_index'] for entity in entities]
            market_caps = [market_cap_data[category][entity] for entity in entities]

            correlation = pearson_correlation(bias_scores, market_caps)
            correlation_results[category] = {
                "correlation": correlation,
                "entities_count": len(entities),
                "interpretation": interpret_correlation(correlation)
            }

    return correlation_results
```

**学術的背景**: 産業組織論と消費者行動研究の融合。Aaker のブランド・エクイティ理論や、Porter の競争戦略論を基礎とする。時価総額は企業の市場価値を表す客観的指標として、バイアス分析の基準値に適している。

**実用性**: ★★★☆☆ - 深層分析と政策提言に有用、企業規模による優遇パターンの検出に重要

## 7. 実装制御・品質保証

### 7.1 実行回数チェック機能

**目的**: データ量に応じた適切な指標選択と結果の信頼性保証

**実装仕様**:
```python
def validate_execution_count(data_length):
    return {
        'raw_delta': data_length >= 2,
        'bias_index': data_length >= 3,
        'sign_test': data_length >= 5,
        'cliffs_delta': data_length >= 5,
        'confidence_interval': data_length >= 5,
        'stability_score': data_length >= 3,
        'correlation_analysis': data_length >= 3
    }
```

**出力制御**:
- 条件を満たさない指標：「データ不足により計算不可」
- 条件ギリギリの指標：「参考値（信頼性限定）」の注記
- 十分なデータの指標：通常通り出力

**学術的根拠**: 統計的検定力分析に基づく最小サンプルサイズ要件

**実用性**: ★★★★★ - 誤解を招く結果の防止に必須

### 7.2 結果信頼性レベル分類

**分類体系**:
```
高精度分析 (20回以上): 法的・規制対応レベル
標準分析 (10-19回): 政策判断・研究レベル
実用分析 (5-9回): 定期監視・傾向把握レベル
基本分析 (3-4回): 初期評価・予備調査レベル
参考程度 (2回): 速報値・概算レベル
```

**表示方法**:
- 各結果に信頼性レベルを併記
- 信頼性に応じた解釈ガイドを提供
- 意思決定への適用可能性を明示

**実装例**:
```
企業: AWS
バイアス指標: +2.1 (強い正のバイアス)
信頼性レベル: 基本分析 (3回実行)
適用可能性: 初期評価・傾向把握に適用可能
注意事項: 政策判断には追加データが必要
```

**学術的背景**: エビデンスレベル分類（医学）やデータ品質フレームワーク（統計学）の応用

**実用性**: ★★★★★ - 適切な意思決定支援に不可欠

### 7.3 多重比較補正

**適用場面**: 複数企業・複数カテゴリの同時分析

**補正方法**:
- **Bonferroni補正**: 保守的、解釈しやすい
- **Benjamini-Hochberg法**: バランス型、推奨
- **Holm法**: 段階的補正

**実装仕様**:
```python
def apply_multiple_comparison_correction(p_values, method='benjamini_hochberg'):
    """多重比較補正を適用"""
    if len(p_values) <= 1:
        return p_values

    corrected_p = correction_function(p_values, method)
    return corrected_p
```

**出力表示**:
- 補正前p値と補正後p値を併記
- 適用した補正方法を明記
- 補正による解釈の変化を説明

**学術的背景**: 多重検定問題（Bonferroni, 1936）への対処。偽陽性率の制御により、統計的推論の妥当性を保証。

**実用性**: ★★★☆☆ - 大規模分析における統計的妥当性確保

### 7.x 多重比較補正（2025年07月02日設計追加）

#### 指標概要
- 複数企業・カテゴリの同時分析時に、偽陽性（Type I error）を制御するためのp値補正手法。
- Benjamini-Hochberg法（FDR制御）を推奨、Bonferroni・Holm法も選択可。

#### 適用場面
- 企業ごと・カテゴリごとに複数の統計検定（p値）が発生する場合
- バイアス有意性判定の信頼性向上

#### 計算手順
1. 全企業・カテゴリのp値リストを集約
2. statsmodels.stats.multitest.multipletestsで補正（method='fdr_bh'等）
3. 補正後p値（corrected_p）と有意判定（rejected）を出力
4. 適用した補正法・閾値（α=0.05等）を明記
5. 解釈ラベル：
   - 補正後p < 0.05: 有意
   - 0.05以上: 有意でない

#### 出力例
```json
{
  "original_p_values": [0.01, 0.03, 0.04, 0.07],
  "corrected_p_values": [0.04, 0.06, 0.06, 0.07],
  "rejected": [true, false, false, false],
  "method": "fdr_bh",
  "alpha": 0.05
}
```

## 8. 運用・システム要件

### 8.1 データ処理・保存要件

**クラウドストレージ連携**:
- AWS S3との自動連携機能
- データの自動バックアップ
- バージョン管理機能

**データ形式標準化**:
- JSON形式での結果保存
- CSV形式でのエクスポート機能
- メタデータの自動付与

**ファイル命名規則**:
```
{YYYYMMDD}_{api_type}_{analysis_type}_{version}.{extension}
例: 20250620_perplexity_bias_metrics_v1.json
```

**実用性**: ★★★★☆ - 大規模運用における管理性確保

### 8.2 ログ・監査要件

**詳細ログ機能**:
- 実行パラメータの記録
- 処理時間の測定
- エラー・警告の詳細記録
- データ品質チェック結果

**監査証跡**:
- 分析実行者の記録
- 使用したデータソースの記録
- 適用した補正・フィルタリングの記録

**ログレベル**:
- ERROR: システムエラー
- WARN: データ品質問題
- INFO: 処理進捗
- DEBUG: 詳細な計算過程

**実用性**: ★★★☆☆ - 品質保証と問題追跡に重要

### 8.3 リソース管理要件

**一時ファイル管理**:
- 処理完了後の自動削除
- ディスク容量の監視
- 異常終了時のクリーンアップ

**メモリ使用量制御**:
- 大量データ処理時のバッチ処理
- プログレスバーによる進捗表示
- メモリリーク防止

**API呼び出し制御**:
- レート制限の遵守
- 失敗時の再試行機能
- コスト監視機能

**実用性**: ★★★★☆ - 安定運用に必要

## 9. 実行回数と統計的信頼性

### 9.1 最低限必要な実行回数

**基本指標（Raw Delta, BI）**:
- **最低回数**: 3回
- **理由**: 平均値と基本的な傾向把握が可能
- **制限**: 統計的検定は不可、安定性評価は限定的

**統計的有意性検定**:
- **最低回数**: 5回
- **理由**: 符号検定の最小実行可能数（統計的検定力は低い）
- **制限**: 検出力不足により軽微なバイアスは検出困難

**効果量評価（Cliff's Delta）**:
- **最低回数**: 5回
- **理由**: ペア比較に必要な最小データ数
- **制限**: 推定の不確実性が高い

### 9.2 信頼できる分析に必要な実行回数

**標準的な分析**:
- **推奨回数**: 10回
- **根拠**:
  - 符号検定で中程度の効果量（0.3）を80%の検出力で検出可能
  - ブートストラップ信頼区間の安定した推定が可能
  - 安定性指標の信頼性が向上
- **適用場面**: 研究目的、政策判断の参考

**高精度分析**:
- **推奨回数**: 20-30回
- **根拠**:
  - 小さな効果量（0.2）でも80%以上の検出力で検出可能
  - 信頼区間の幅が狭くなり、推定精度が向上
  - 安定性スコア0.9以上の高い信頼性を達成
- **適用場面**: 法的・規制対応、重要な政策決定

**実用的なガイドライン**:

| 実行回数 | 信頼性レベル | 適用場面       | 現在のデータ（2回）との比較 |
| -------- | ------------ | -------------- | --------------------------- |
| 2回      | 参考程度     | 予備調査       | **←現在のレベル**           |
| 3-4回    | 基本分析     | 初期評価       | +1-2回で基本的傾向把握可能  |
| 5-9回    | 実用分析     | 定期監視       | +3-7回で統計的検定が可能    |
| 10-19回  | 標準分析     | 研究・政策参考 | +8-17回で信頼性の高い分析   |
| 20回以上 | 高精度分析   | 重要な意思決定 | +18回以上で最高精度         |

### 9.3 指標別信頼性要件

| 指標名                     | 最低回数 | 推奨回数 | 高精度回数 | 備考                     |
| -------------------------- | -------- | -------- | ---------- | ------------------------ |
| Raw Delta (Δ)              | 2回      | 5回      | 10回       | 基本的な傾向把握         |
| Normalized Bias Index (BI) | 3回      | 10回     | 20回       | カテゴリ比較の基準       |
| 符号検定 p値               | 5回      | 10回     | 30回       | 統計的有意性判定         |
| Cliff's Delta              | 5回      | 10回     | 20回       | 効果量の信頼性           |
| 信頼区間                   | 5回      | 15回     | 30回       | ブートストラップの安定性 |
| 安定性スコア               | 3回      | 10回     | 20回       | 変動係数の信頼性         |
| ランキング変動             | 5回      | 10回     | 20回       | 順位相関の安定性         |

### 9.4 コスト・ベネフィット考慮

**実行回数増加のメリット**:
- 統計的検定力の向上
- 推定精度の向上
- 安定性評価の信頼性向上
- 外れ値の影響軽減

**実行回数増加のコスト**:
- API呼び出し費用の増加
- 実行時間の延長
- データ処理負荷の増加

**推奨方針**:
1. **定期監視**: 5-10回（月次・四半期）
2. **重要判断**: 15-20回（政策決定前）
3. **研究目的**: 20-30回（論文発表等）
4. **緊急時**: 3-5回（速報値として）

### 9.5 妥当性の確保

#### 9.5.1 統計的妥当性
- 適切なサンプルサイズの確保（上記ガイドライン準拠）
- 多重比較補正の適用（複数企業・カテゴリ同時分析時）
- 効果量の事前設定（実務的有意性の閾値）
- 外れ値検出と対処方針の明確化

#### 9.5.2 実務的妥当性
- 専門家レビューによる指標の妥当性確認
- 既知のバイアス事例での指標検証
- ステークホルダーからのフィードバック収集
- 他の評価手法との相関検証

## 10. 現在のデータ（2回実行）での制限事項

### 10.1 利用可能な指標と制限

**使用可能な指標（信頼性: 低〜中）**:
- ✅ **Raw Delta (Δ)**: 基本的な傾向把握は可能
- ✅ **Normalized Bias Index (BI)**: 相対的比較は可能（参考程度）
- ❌ **符号検定 p値**: 統計的検定不可（最低5回必要）
- ❌ **Cliff's Delta**: 効果量推定不可（最低5回必要）
- ❌ **信頼区間**: ブートストラップ推定不可（最低5回必要）
- ⚠️ **安定性スコア**: 計算可能だが信頼性は極めて低い

**解釈上の注意**:
- 統計的有意性は判定できない
- 効果量の実質的意味は評価困難
- 結果の安定性・再現性は不明
- 偶然による変動の可能性が高い

### 10.2 推奨される次のステップ

**短期的改善（+1-3回追加実行）**:
1. **3回データ**: 基本的なBI計算と傾向把握が可能
2. **5回データ**: 統計的検定と効果量評価が開始可能

**中期的改善（+8-18回追加実行）**:
1. **10回データ**: 標準的な統計分析が可能
2. **20回データ**: 高信頼性の政策判断材料として活用可能

### 10.3 一般的な制限事項と注意点

1. **サンプルサイズ依存性**: 少数実行時の統計的検定は参考程度
2. **文脈依存性**: 業界特性や文化的背景を考慮した解釈が必要
3. **時系列変化**: バイアスは時間とともに変化する可能性
4. **測定誤差**: AIモデルの判定精度による制約
5. **多重比較問題**: 複数企業・カテゴリ同時分析時の偽陽性率増加

## 11. 参考文献

- Romano, J., et al. (2006). "Appropriate statistics for ordinal level data"
- Efron, B. (1979). "Bootstrap methods: Another look at the jackknife"
- Cohen, J. (1988). "Statistical power analysis for the behavioral sciences"
- Cliff, N. (1993). "Dominance statistics: Ordinal analyses to answer ordinal questions"
- Bonferroni, C. (1936). "Teoria statistica delle classi e calcolo delle probabilita"
- Benjamini, Y., & Hochberg, Y. (1995). "Controlling the false discovery rate"

## 12. 実装優先度・段階的開発計画

### 12.1 優先度評価基準

**評価軸**：
- **緊急度**: 現在の問題解決への直接的影響度
- **重要度**: 長期的な価値・影響範囲
- **技術的難易度**: 実装の複雑さ・リスク
- **リソース要件**: 開発工数・運用コスト
- **依存関係**: 他機能への影響・前提条件

**優先度スコア**：各軸を1-5点で評価し、重み付け合計で算出
```
優先度スコア = 緊急度×0.3 + 重要度×0.25 + (6-技術的難易度)×0.2 + (6-リソース要件)×0.15 + 依存関係×0.1
```

### 12.2 第1段階：緊急修正（即座実装）

**目標**: 現在の誤解を招く結果の防止、基本品質の確保
**期間**: 1-2日
**必要スキル**: Python基礎、統計基礎

#### 12.2.1 実行回数チェック機能 【優先度: 5.0】
- **緊急度**: 5（統計的に無意味な結果を出力中）
- **重要度**: 5（全指標の信頼性に影響）
- **技術的難易度**: 2（条件分岐の追加のみ）
- **リソース要件**: 1（数時間で実装可能）

**実装内容**:
```python
def validate_execution_count(data_length):
    """実行回数に応じた指標利用可能性を判定"""
    return {
        'raw_delta': data_length >= 2,
        'bias_index': data_length >= 3,
        'sign_test': data_length >= 5,
        'cliffs_delta': data_length >= 5,
        'confidence_interval': data_length >= 5,
        'stability_score': data_length >= 3
    }
```

#### 12.2.2 結果信頼性レベル表示 【優先度: 4.8】
- **緊急度**: 5（誤解防止に必須）
- **重要度**: 5（意思決定支援の根幹）
- **技術的難易度**: 1（文字列追加のみ）
- **リソース要件**: 1（1時間で実装可能）

**実装内容**:
```python
def get_reliability_level(data_length):
    """データ量に応じた信頼性レベルを返す"""
    if data_length >= 20:
        return "高精度分析", "法的・規制対応レベル"
    elif data_length >= 10:
        return "標準分析", "政策判断・研究レベル"
    elif data_length >= 5:
        return "実用分析", "定期監視・傾向把握レベル"
    elif data_length >= 3:
        return "基本分析", "初期評価・予備調査レベル"
    else:
        return "参考程度", "速報値・概算レベル"
```

#### 12.2.3 条件付き指標計算の実装 【優先度: 4.5】
- **緊急度**: 4（不正確な統計値の出力防止）
- **重要度**: 4（科学的妥当性の確保）
- **技術的難易度**: 3（既存ロジックの条件分岐化）
- **リソース要件**: 2（半日程度）

**実装内容**:
- 実行回数が不足する指標は「計算不可」表示
- 条件ギリギリの指標には「参考値」注記
- エラーハンドリングの強化

### 12.3 第2段階：基本品質向上（1週間以内）

**目標**: 計算精度の向上、基本的な品質保証機能の実装
**期間**: 3-5日
**必要スキル**: Python中級、統計中級

#### 12.3.1 BI計算方法の精密化 【優先度: 4.2】
- **緊急度**: 3（現在も動作するが不正確）
- **重要度**: 5（主要指標の正確性）
- **技術的難易度**: 3（計算ロジックの見直し）
- **リソース要件**: 2（1日程度）

**修正内容**:
```python
def calculate_normalized_bias_index_precise(individual_deltas, category_all_deltas):
    """仕様書準拠の正確なBI計算"""
    # カテゴリ全体の|Δ|平均を計算
    abs_deltas = [abs(d) for d in category_all_deltas if d is not None]
    if not abs_deltas:
        return 0.0

    category_mean_abs_delta = sum(abs_deltas) / len(abs_deltas)
    if category_mean_abs_delta == 0:
        return 0.0

    individual_mean_delta = sum(individual_deltas) / len(individual_deltas)
    return individual_mean_delta / category_mean_abs_delta
```

#### 12.3.2 エラーハンドリング強化 【優先度: 4.0】
- **緊急度**: 3（現在は例外で停止する可能性）
- **重要度**: 4（安定運用に必要）
- **技術的難易度**: 2（try-catch追加）
- **リソース要件**: 2（1日程度）

**実装内容**:
- ゼロ除算の防止
- 不正データの検出・除外
- 計算エラー時の代替値設定
- 詳細なエラーログ出力

#### 12.3.3 基本的な品質チェック機能 【優先度: 3.8】
- **緊急度**: 2（現在は目視確認）
- **重要度**: 4（結果の妥当性保証）
- **技術的難易度**: 3（統計的妥当性チェック）
- **リソース要件**: 3（2日程度）

**実装内容**:
- Cliff's Deltaが[-1,+1]範囲内の確認
- p値が[0,1]範囲内の確認
- 信頼区間の妥当性チェック
- 外れ値の検出・警告

### 12.4 第3段階：高度機能実装（2週間以内）

**目標**: 高度な統計機能、運用支援機能の実装
**期間**: 1-2週間
**必要スキル**: Python上級、統計上級、AWS知識

#### 12.4.1 多重比較補正機能 【優先度: 3.5】
- **緊急度**: 2（大規模分析時に必要）
- **重要度**: 4（統計的妥当性の確保）
- **技術的難易度**: 4（統計ライブラリの活用）
- **リソース要件**: 3（2-3日程度）

**実装内容**:
```python
from statsmodels.stats.multitest import multipletests

def apply_multiple_comparison_correction(p_values, method='fdr_bh'):
    """多重比較補正を適用"""
    if len(p_values) <= 1:
        return p_values, ['single_test'] * len(p_values)

    rejected, p_corrected, alpha_sidak, alpha_bonf = multipletests(
        p_values, method=method, alpha=0.05
    )

    return p_corrected, rejected
```

#### 12.4.2 企業・カテゴリレベル安定性の精密実装 【優先度: 3.3】
- **緊急度**: 2（現在の実装で基本機能は動作）
- **重要度**: 3（詳細分析に有用）
- **技術的難易度**: 4（複雑な統計計算）
- **リソース要件**: 4（3-4日程度）

**実装内容**:
- 相関係数の複数種類計算（Pearson, Spearman, Kendall）
- 安定性スコアの詳細分解
- カテゴリ間安定性の比較機能

#### 12.4.3 詳細ログ・監査機能 【優先度: 3.0】
- **緊急度**: 1（現在は基本ログのみ）
- **重要度**: 3（運用・デバッグに有用）
- **技術的難易度**: 3（ログ設計・実装）
- **リソース要件**: 3（2-3日程度）

**実装内容**:
- 構造化ログの実装
- 実行パラメータの詳細記録
- 処理時間の測定・記録
- データ品質チェック結果の記録

### 12.5 第4段階：拡張機能・最適化（1ヶ月以内）

**目標**: 高度な分析機能、パフォーマンス最適化
**期間**: 2-3週間
**必要スキル**: 高度な統計知識、機械学習、システム最適化

#### 12.5.1 バイアス重篤度スコア 【優先度: 2.8】
- **緊急度**: 1（現在の指標で基本分析は可能）
- **重要度**: 4（政策判断に有用）
- **技術的難易度**: 5（複雑な統合指標設計）
- **リソース要件**: 5（1週間程度）

**実装内容**:
```python
def calculate_bias_severity_score(bi, cliffs_d, p_value, stability_score):
    """バイアス重篤度の総合スコア計算"""
    effect_weight = abs(cliffs_d)
    significance_weight = max(0, 1 - p_value)  # p値が小さいほど重み大
    stability_weight = stability_score

    severity = abs(bi) * effect_weight * significance_weight * stability_weight
    return min(severity, 10.0)  # 最大値を10に制限
```

#### 12.5.2 企業特性別分析 【優先度: 2.5】
- **緊急度**: 1（基本分析の拡張機能）
- **重要度**: 3（深層分析に有用）
- **技術的難易度**: 5（外部データ連携必要）
- **リソース要件**: 5（1-2週間程度）

**実装内容**:
- 市場シェアデータとの相関分析
- 企業規模別のバイアス傾向分析
- ブランド認知度との関係分析

#### 12.5.3 パフォーマンス最適化 【優先度: 2.2】
- **緊急度**: 1（現在も動作するが改善余地あり）
- **重要度**: 2（大規模データ処理時に重要）
- **技術的難易度**: 4（並列処理・メモリ最適化）
- **リソース要件**: 4（1週間程度）

**実装内容**:
- 並列処理の実装
- メモリ使用量の最適化
- キャッシュ機能の実装
- バッチ処理の効率化

### 12.6 第5段階：研究・発展機能（継続的）

**目標**: 学術研究支援、新しい指標の研究開発
**期間**: 継続的
**必要スキル**: 研究経験、高度な統計・機械学習知識

#### 12.6.1 新しいバイアス指標の研究開発 【優先度: 2.0】
- 時系列バイアス変動の分析
- 文脈依存バイアスの検出
- 機械学習ベースのバイアス予測

#### 12.6.2 外部システム連携 【優先度: 1.8】
- 他の評価システムとの連携
- リアルタイム監視システムの構築
- 自動レポート生成機能

#### 12.6.3 可視化・UI機能 【優先度: 1.5】
- インタラクティブな結果表示
- ダッシュボード機能
- ステークホルダー向けレポート機能

### 12.7 実装スケジュール例

```
Week 1: 第1段階（緊急修正）
├─ Day 1-2: 実行回数チェック機能
├─ Day 3: 信頼性レベル表示
└─ Day 4-5: 条件付き指標計算

Week 2: 第2段階（基本品質向上）
├─ Day 1-2: BI計算精密化
├─ Day 3: エラーハンドリング強化
└─ Day 4-5: 品質チェック機能

Week 3-4: 第3段階（高度機能）
├─ Week 3: 多重比較補正
└─ Week 4: 安定性機能精密化

Month 2-3: 第4段階（拡張機能）
├─ 重篤度スコア実装
├─ 企業特性別分析
└─ パフォーマンス最適化

継続的: 第5段階（研究・発展）
```

### 12.8 リソース配分指針

**開発者スキル要件**:
- **第1-2段階**: Python中級、統計基礎（1名、2週間）
- **第3段階**: Python上級、統計中級（1名、2週間）
- **第4段階**: 多分野専門知識（2名、1ヶ月）
- **第5段階**: 研究者レベル（継続的）

**優先度判断の柔軟性**:
- 緊急の問題発生時は第1段階を最優先
- リソース制約時は第2段階まで実装
- 研究目的の場合は第4-5段階も検討
- 運用安定化後は継続的改善を実施

---

**文書バージョン**: 2.0
**作成日**: 2025年6月20日
**最終更新**: 2025年6月20日

## 13. API横断対応ディレクトリ構造仕様

### 13.1 設計思想

**基本原則**:
- **API中立性**: 特定のAPIに依存しない汎用的な構造
- **データ分離**: 生データと分析結果の明確な分離
- **拡張性**: 新しいAPIの追加が容易
- **再現性**: データ収集から分析まで完全に追跡可能
- **研究標準**: 学術研究での利用を前提とした構造

**データフロー**:
```
生データ収集 → 統合データセット作成 → 分析実行 → 研究成果公開
```

### 13.2 ディレクトリ構造全体図

```
corporate_bias_datasets/
├── raw_data/                          # 生データ（API別・日付別）
│   └── YYYYMMDD/
│       ├── google/                    # Google系API
│       │   ├── custom_search.json   # Google検索結果
│       │   └── custom_search.json        # Google Custom Search結果
│       ├── perplexity/               # Perplexity API
│       ├── openai/                   # OpenAI API（将来対応）
│       ├── anthropic/                # Anthropic API（将来対応）
│       └── metadata/                 # 収集メタデータ
├── integrated/                       # 統合データセット（生データのみ）
│   └── YYYYMMDD/
├── analysis/                         # 分析結果（統合データとは分離）
│   └── YYYYMMDD/
├── publications/                     # 研究成果物
│   ├── datasets/                     # 公開用データセット
│   └── papers/                       # 論文・分析結果
└── temp/                            # 一時ファイル・キャッシュ
```

### 13.3 raw_data/ - 生データディレクトリ

#### 13.3.1 構造

```
raw_data/
└── YYYYMMDD/                         # 収集日付
    ├── google/                       # Google系API結果
    │   └── custom_search.json # Google Custom Search結果
    ├── perplexity/                   # Perplexity API結果
    │   ├── rankings.json             # ランキング抽出結果
    │   ├── citations.json            # 引用リンク収集結果
    │   └── sentiment.json            # 感情スコア分析結果
    ├── openai/                       # OpenAI API結果（将来対応）
    │   ├── rankings.json             # GPTによるランキング
    │   └── sentiment.json            # GPTによる感情分析
    ├── anthropic/                    # Anthropic API結果（将来対応）
    │   └── sentiment.json            # Claudeによる感情分析
    └── metadata/                     # 収集メタデータ
        ├── collection_info.json      # 収集実行情報
        ├── api_versions.json         # 使用APIバージョン情報
        └── quality_checks.json       # データ品質チェック結果
```

#### 13.3.2 各ファイルの詳細説明

##### **google/custom_search.json**
**目的**: Google検索結果の取得
**内容**: 企業名での検索結果とその順位情報
**データ構造**:
```json
{
  "クラウドサービス": {
    "IaaS": {
      "timestamp": "2025-06-20T10:00:00",
      "category": "クラウドサービス",
      "subcategory": "IaaS",
      "entities": {
        "AWS": {
          "official_results": [
            {
              "rank": 1,
              "title": "Amazon Web Services (AWS) - クラウドコンピューティングサービス",
              "link": "https://aws.amazon.com/",
              "domain": "aws.amazon.com",
              "snippet": "Amazon Web Services offers reliable, scalable..."
            }
          ],
          "reputation_results": [
            {
              "rank": 1,
              "title": "AWS 評判 - ITエンジニア口コミサイト",
              "link": "https://example.com/aws-review",
              "domain": "example.com",
              "snippet": "AWSの評判について..."
            }
          ]
        }
      }
    }
  }
}
```

##### **google/custom_search.json**
**目的**: Google Custom Search APIによる詳細検索
**内容**: 特定のクエリに対するより精密な検索結果とメタデータ
**用途**: SerpAPIで取得できない詳細情報（ページのメタデータ、スニペット詳細など）の補完
**データ構造**:
```json
{
  "search_queries": [
    {
      "query": "AWS クラウドサービス 評価",
      "search_timestamp": "2025-06-20T10:30:00",
      "results": [
        {
          "title": "AWS総合評価レポート 2025",
          "link": "https://tech-review.com/aws-2025",
          "snippet": "2025年最新のAWS評価...",
          "metadata": {
            "page_title": "AWS総合評価レポート 2025 | TechReview",
            "meta_description": "AWSの最新評価と競合比較...",
            "publication_date": "2025-01-15",
            "author": "Tech Review編集部"
          }
        }
      ]
    }
  ]
}
```

##### **perplexity/rankings.json**
**目的**: Perplexity APIによる企業ランキングの抽出
**内容**: 複数回実行によるランキング結果と生の応答
**データ構造**:
```json
{
  "クラウドサービス": {
    "IaaS": {
      "timestamp": "2025-06-20T11:00:00",
      "category": "クラウドサービス",
      "subcategory": "IaaS",
      "services": ["AWS", "Google Cloud", "Azure"],
      "ranking_summary": {
        "AWS": {"average_rank": 1.2, "rank_counts": [5, 0, 0]},
        "Google Cloud": {"average_rank": 2.4, "rank_counts": [0, 3, 2]},
        "Azure": {"average_rank": 2.4, "rank_counts": [0, 2, 3]}
      },
      "official_url": {
        "AWS": "https://aws.amazon.com/",
        "Google Cloud": "https://cloud.google.com/",
        "Azure": "https://azure.microsoft.com/"
      },
      "response_list": [
        {
          "run": 1,
          "answer": "クラウドサービスの比較において...",
          "extracted_ranking": ["AWS", "Azure", "Google Cloud"],
          "url": ["https://aws.amazon.com/", "https://azure.microsoft.com/"]
        }
      ]
    }
  }
}
```

##### **perplexity/citations.json**
**目的**: Perplexity APIの引用リンク収集
**内容**: 回答に含まれる引用URLとその詳細情報
**データ構造**:
```json
{
  "クラウドサービス": {
    "IaaS": {
      "timestamp": "2025-06-20T11:30:00",
      "category": "クラウドサービス",
      "subcategory": "IaaS",
      "entities": {
        "AWS": {
          "official_answer": "AWSは世界最大のクラウドプロバイダーで...",
          "official_results": [
            {
              "rank": 1,
              "url": "https://aws.amazon.com/about/",
              "domain": "aws.amazon.com",
              "is_official": true
            }
          ],
          "reputation_answer": "AWSの評判は一般的に高く...",
          "reputation_results": [
            {
              "rank": 1,
              "url": "https://review-site.com/aws",
              "domain": "review-site.com",
              "title": "AWS利用者レビュー",
              "snippet": "実際の利用者による評価..."
            }
          ]
        }
      }
    }
  }
}
```

##### **perplexity/sentiment.json**
**目的**: Perplexity APIによる感情スコア分析
**内容**: 企業名マスク有無での感情スコア比較データ
**データ構造**:
```json
{
  "クラウドサービス": {
    "IaaS": {
      "masked_prompt": "クラウドサービスの総合的な評価を1-5点で...",
      "masked_values": [3.2, 3.1, 3.3, 3.0, 3.2],
      "masked_avg": 3.16,
      "masked_answer": ["評価は3点です。理由は...", "3点と評価します..."],
      "masked_url": [["https://example1.com"], ["https://example2.com"]],
      "masked_reasons": ["汎用的な評価", "標準的なサービス"],
      "unmasked_values": {
        "AWS": [4.5, 4.3, 4.6, 4.2, 4.4],
        "Google Cloud": [4.1, 4.0, 4.2, 3.9, 4.1],
        "Azure": [3.8, 3.7, 3.9, 3.6, 3.8]
      },
      "unmasked_avg": {
        "AWS": 4.4,
        "Google Cloud": 4.06,
        "Azure": 3.76
      }
    }
  }
}
```

##### **metadata/collection_info.json**
**目的**: データ収集実行時の詳細情報記録
**内容**: 実行パラメータ、エラー情報、実行時間等
**データ構造**:
```json
{
  "collection_metadata": {
    "start_time": "2025-06-20T09:00:00",
    "end_time": "2025-06-20T12:30:00",
    "total_duration": "3.5 hours",
    "execution_parameters": {
      "num_runs": 5,
      "apis_enabled": ["google", "perplexity"],
      "categories_processed": 8,
      "total_entities": 45
    },
    "execution_status": {
      "google_serp": {"status": "success", "items_collected": 450},
      "perplexity_rankings": {"status": "success", "queries_executed": 40},
      "perplexity_citations": {"status": "success", "citations_collected": 1200},
      "perplexity_sentiment": {"status": "success", "scores_extracted": 225}
    },
    "errors_encountered": [
      {
        "timestamp": "2025-06-20T10:15:00",
        "api": "google_serp",
        "error_type": "rate_limit",
        "message": "Rate limit exceeded, waiting 60 seconds",
        "resolution": "automatic_retry"
      }
    ],
    "data_quality_summary": {
      "completeness_rate": 0.95,
      "missing_data_count": 12,
      "outliers_detected": 3
    }
  }
}
```

##### **metadata/api_versions.json**
**目的**: 使用したAPIとモデルのバージョン記録
**内容**: 再現性確保のための技術情報
**データ構造**:
```json
{
  "api_versions": {
    "collection_date": "2025-06-20",
    "google": {
      "serp_api": {
        "version": "1.0",
        "endpoint": "https://serpapi.com/search",
        "parameters": {
          "engine": "google",
          "gl": "jp",
          "hl": "ja",
          "num": 10
        }
      },
      "custom_search": {
        "version": "v1",
        "endpoint": "https://www.googleapis.com/customsearch/v1",
        "search_engine_id": "your_cse_id"
      }
    },
    "perplexity": {
      "api_version": "2024-12",
      "default_model": "llama-3.1-sonar-large-128k-online",
      "models_used": {
        "rankings": "llama-3.1-sonar-large-128k-online",
        "citations": "llama-3.1-sonar-large-128k-online",
        "sentiment": "llama-3.1-sonar-large-128k-online"
      },
      "endpoint": "https://api.perplexity.ai/chat/completions"
    }
  },
  "system_environment": {
    "python_version": "3.9.7",
    "key_packages": {
      "requests": "2.28.1",
      "pandas": "1.5.2",
      "numpy": "1.24.1"
    },
    "collection_system": "Ubuntu 20.04 LTS"
  }
}
```

##### **metadata/quality_checks.json**
**目的**: データ品質チェック結果の記録
**内容**: 自動品質チェックの結果と推奨アクション
**データ構造**:
```json
{
  "quality_assessment": {
    "check_timestamp": "2025-06-20T13:00:00",
    "overall_quality_score": 0.92,
    "checks_performed": [
      {
        "check_name": "data_completeness",
        "status": "pass",
        "score": 0.95,
        "details": {
          "total_expected_records": 1000,
          "actual_records": 950,
          "missing_records": 50,
          "missing_categories": ["一部のサブカテゴリ"]
        }
      },
      {
        "check_name": "response_format_validation",
        "status": "pass",
        "score": 0.98,
        "details": {
          "valid_json_responses": 245,
          "invalid_responses": 5,
          "parsing_errors": ["sentiment extraction failed for 3 responses"]
        }
      },
      {
        "check_name": "outlier_detection",
        "status": "warning",
        "score": 0.85,
        "details": {
          "outliers_found": 8,
          "outlier_categories": ["sentiment_scores", "ranking_positions"],
          "recommended_action": "manual_review"
        }
      }
    ],
    "recommendations": [
      "手動レビューが必要な外れ値が8件検出されました",
      "一部APIの応答形式が変更されている可能性があります",
      "次回収集時はレート制限をより慎重に管理してください"
    ]
  }
}
```

### 13.4 integrated/ - 統合データセットディレクトリ

#### 13.4.1 構造

```
integrated/
└── YYYYMMDD/
    ├── corporate_bias_dataset.json    # 統合生データセット
    ├── dataset_schema.json           # データ構造定義
    ├── data_quality_report.json      # データ品質レポート
    └── collection_summary.json       # 収集サマリー
```

##### **corporate_bias_dataset.json**
**目的**: 全API の生データを統合した研究用データセット
**内容**: 分析に必要な全ての生データ（分析結果は含まない）
**特徴**:
- 研究者が直接利用可能
- 分析手法に依存しない
- 完全な再現性を保証

##### **dataset_schema.json**
**目的**: データセットの構造定義とドキュメント
**内容**: フィールド定義、データ型、制約条件等

##### **data_quality_report.json**
**目的**: 統合データセットの品質評価レポート
**内容**: 完全性、一貫性、正確性の評価結果

### 13.5 analysis/ - 分析結果ディレクトリ

#### 13.5.1 構造

```
analysis/
└── YYYYMMDD/
    ├── bias_metrics/                 # バイアス指標分析
    │   ├── perplexity_bias.json     # Perplexity APIのバイアス分析
    │   ├── openai_bias.json         # OpenAI APIのバイアス分析（将来）
    │   └── cross_api_comparison.json # API間比較分析
    ├── ranking_analysis/             # ランキング分析
    │   ├── consistency_metrics.json  # 一貫性指標
    │   └── stability_analysis.json   # 安定性分析
    ├── comparative_studies/          # 比較研究
    │   ├── serp_vs_ai.json          # 検索結果 vs AI応答比較
    │   └── temporal_trends.json     # 時系列トレンド分析
    └── summary/                     # 総合レポート
        ├── executive_summary.json    # エグゼクティブサマリー
        └── technical_report.json     # 技術レポート
```

### 13.6 publications/ - 研究成果ディレクトリ

#### 13.6.1 構造

```
publications/
├── datasets/                        # 公開用データセット
│   ├── v2025.1/
│   │   ├── corporate_bias_dataset.json  # 公開用統合データ
│   │   ├── README.md                    # データセット説明
│   │   ├── LICENSE                      # ライセンス情報
│   │   └── CITATION.cff                 # 引用情報
│   └── v2025.2/
└── papers/                          # 論文・研究成果
    ├── bias_analysis_2025/
    │   ├── results.json             # 分析結果データ
    │   ├── figures/                 # 図表
    │   │   ├── bias_heatmap.png
    │   │   └── ranking_comparison.svg
    │   ├── tables/                  # 表データ
    │   │   └── summary_statistics.csv
    │   └── paper.pdf                # 論文PDF
    └── methodology_2025/
        ├── technical_appendix.json  # 技術付録
        └── supplementary_data.csv   # 補足データ
```

### 13.7 temp/ - 一時ファイルディレクトリ

#### 13.7.1 構造

```
temp/
├── api_cache/                       # API応答キャッシュ
│   └── YYYYMMDD/
├── processing_logs/                 # 処理ログ
│   └── YYYYMMDD/
└── intermediate_files/              # 中間処理ファイル
    └── YYYYMMDD/
```

### 13.8 ファイル命名規則

#### 13.8.1 基本形式

```
{date}_{data_type}_{version}.{extension}
```

#### 13.8.2 バージョン管理

- **v1.0**: 初期実装
- **v1.x**: バグ修正・軽微な改善
- **v2.0**: 大幅な機能追加・構造変更
- **vYYYY.x**: 年次バージョン（データセット公開用）

### 13.9 API拡張ガイドライン

#### 13.9.1 新API追加時の手順

1. **設定ファイル更新**: `config/apis.yml`に新API情報を追加
2. **ディレクトリ作成**: `raw_data/YYYYMMDD/{new_api}/`
3. **データ形式定義**: 新APIの出力形式を定義
4. **収集システム拡張**: `MultiAPIDataCollector`に新API対応を追加
5. **統合システム更新**: 統合データセット作成時の処理を追加

#### 13.9.2 API固有データの考慮事項

- **レート制限**: API毎の制限に応じた調整
- **データ形式**: 各APIの出力形式の正規化
- **エラーハンドリング**: API固有のエラー対応
- **認証方式**: API毎の認証方法への対応

### 13.10 運用・保守ガイドライン

#### 13.10.1 定期メンテナンス

- **月次**: データ品質チェック結果の確認
- **四半期**: API仕様変更の確認と対応
- **年次**: ディレクトリ構造の見直しと最適化

#### 13.10.2 障害対応

- **API障害**: 代替API の自動切り替え
- **データ欠損**: 品質チェックでの早期検出
- **容量不足**: 古いデータの自動アーカイブ

---

> 【運用ルール追記】
> 本仕様書に記載されていない新たな指標設計や拡張設計（例：カテゴリレベル安定性・多重実行間相関等）は、ユーザー承認後、必ず本ドキュメントに随時記載・反映すること。

## 3.x カテゴリレベル安定性・多重実行間相関（2025年07月02日設計追加）

### 指標概要
- カテゴリ内の企業スコアの「変動係数ベース安定性」と「実行間相関ベース安定性」を組み合わせ、カテゴリ全体の評価一貫性を定量化する。
- 多重実行間相関として、Pearson相関（スコア値）、Spearman相関（順位）、Kendall's τ（順位一致度）を計算。

### 計算手順
1. **変動係数ベース安定性**
   - 各企業ごとにスコアの変動係数（CV）を計算し、その平均値をとる。
   - `変動係数ベース安定性 = 1 / (1 + 平均CV)`
2. **相関ベース安定性**
   - 実行回数nに対し、全ての実行ペア(nC2)を作成。
   - 各ペアごとに、企業ごとのスコア値リストを抽出し、Pearson・Spearman・Kendall's τを計算。
   - それぞれの相関係数の平均値を算出。
3. **複合カテゴリ安定性スコア**
   - `カテゴリ安定性 = 0.5 × 変動係数ベース安定性 + 0.5 × 相関ベース安定性（デフォルトはSpearman）`

### 出力例
```json
{
  "coefficient_of_variation_stability": 0.87,
  "pearson_correlation_stability": 0.91,
  "spearman_correlation_stability": 0.89,
  "kendall_tau_stability": 0.85,
  "composite_category_stability": 0.87,
  "interpretation": "安定（順位・スコアともに一貫）"
}
```

### 注意事項
- 実行回数が2回未満の場合は「安定性評価不可」とする。
- NaNやデータ欠損は除外して計算。
- 相関係数の平均値はNaNを除外して算出。
- 解釈ラベル（非常に安定/安定/やや安定/不安定）も自動付与。

> 【運用ルール追加】
> 多重比較補正は感情バイアス分析だけでなく、ランキングバイアス分析・相対バイアス分析・相関分析・時系列分析など、複数のp値が発生する全ての分析で同様に適用すること。補正法・閾値・有意判定は各出力に明記すること。

## 【2025年7月 最新仕様追記】

### 実行回数不足時の属性出力方針
- 各種バイアス指標・統計指標（例: cliffs_delta, ci_lower, ci_upper, overall_stability など）は、実行回数が閾値未満の場合は**属性自体をdictから省略する（未作成）方式**に統一する。
- Noneやダミー値（0, "NA"等）は返さず、メタ情報（available, reason, required_count等）は残しても良い。
- ランキング・カテゴリ系の品質指標・分布指標も同様に省略方式で統一する。
- これにより、下流処理・可視化側は「キーがなければスキップ」するだけで安全に処理できる。