---
title: 企業バイアス分析ダッシュボード「統合分析」画面仕様書
date: 2025-01-19
type: "specification"
alwaysApply: true
globs: ["**/app.py", "**/plot_utils.py"]
---

# 企業バイアス分析ダッシュボード「統合分析」画面仕様書

## 1. 目的・背景

### 1.1 統合分析の目的
- **カテゴリ横断的な分析**: 複数の分析タイプ（感情分析・ランキング分析・引用比較）の結果を統合し、全体的なバイアスパターンを把握
- **クロスプラットフォーム比較**: Google Custom SearchとPerplexity APIの結果を比較し、プラットフォーム間の一貫性を評価
- **統合インサイト生成**: 個別分析では見えない全体的な傾向や異常値を自動検出
- **政策判断支援**: 複数の分析結果を統合した信頼性の高い判断材料を提供

### 1.2 背景・必要性
- **個別分析の限界**: 感情分析・ランキング分析・引用比較はそれぞれ異なる観点からの分析であり、統合的な視点が必要
- **プラットフォームバイアス**: 異なる情報源（Google vs Perplexity）での結果差異を定量的に評価
- **企業規模・市場支配力との関連**: バイアス分析結果と企業の市場ポジションの相関を分析
- **時系列変化の把握**: 複数回の分析結果から安定性・一貫性を評価

## 2. 画面構成・UI設計

### 2.1 全体構成
```
┌─────────────────────────────────────────────────────────────┐
│ 📊 統合分析結果                                              │
├─────────────────────────────────────────────────────────────┤
│ [📈 感情-ランキング相関] [🔗 Google-Citations整合性] [🎯 全体的バイアスパターン] │
│     相関係数: 0.xxx          整合性レベル: high/low       パターン: pattern_name │
├─────────────────────────────────────────────────────────────┤
│ [重篤度ランキング] [相関マトリクス]                          │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ タブ内容（動的可視化）                                   │ │
│ └─────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ [詳細データ] (expander)                                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 主要指標セクション（3カラム）

#### 2.2.1 感情-ランキング相関
- **表示内容**: 感情分析結果とランキング分析結果の相関係数
- **データソース**: `cross_analysis_insights.sentiment_ranking_correlation`
- **表示形式**: メトリクス表示（相関係数: 0.xxx）
- **解釈**:
  - 正の相関: 感情スコアが高い企業ほど上位にランクされる
  - 負の相関: 感情スコアが低い企業ほど上位にランクされる
  - 相関なし: 感情とランキングに明確な関係なし

#### 2.2.2 Google-Citations整合性
- **表示内容**: Google Custom SearchとPerplexity Citationsの結果整合性
- **データソース**: `cross_analysis_insights.google_citations_alignment`
- **表示形式**: メトリクス表示（整合性レベル: high/medium/low）
- **解釈**:
  - high: 両プラットフォームで類似の結果
  - medium: 部分的に類似
  - low: 大きく異なる結果

#### 2.2.3 全体的バイアスパターン
- **表示内容**: 統合分析から導出される全体的なバイアスパターン
- **データソース**: `cross_analysis_insights.overall_bias_pattern`
- **表示形式**: メトリクス表示（パターン: pattern_name）
- **パターン例**:
  - `strong_large_enterprise_favoritism`: 大企業への強い優遇
  - `moderate_service_bias`: サービスレベルの適度なバイアス
  - `balanced_analysis`: バランスの取れた分析結果

## 2.3 市場支配・公平性分析セクション（market_dominance_analysisの可視化・詳細設計）

### 2.3.1 目的
- 選択中カテゴリ・サブカテゴリにおける市場支配・公平性の状況を、企業粒度・サービス粒度の両面から直感的に把握できるようにする。
- バイアスと市場データ（シェア・時価総額等）の関係や、優遇傾向・改善推奨を明示する。

### 2.3.2 データ取得フロー
1. サイドバーでカテゴリ・サブカテゴリを選択（例：「デジタルサービス」＞「クラウドサービス」）
2. bias_analysis_results.json の
   `relative_bias_analysis.[カテゴリ].[サブカテゴリ].market_dominance_analysis`
   を取得
3. 企業レベル（enterprise_level）、サービスレベル（service_level）、統合スコア（integrated_fairness）を分離して利用

### 2.3.3 UI構成

#### 2.3.3.1 サマリーカード（上部）
- 統合市場公平性スコア（0〜1、小数第3位まで）
- 信頼度（high/medium/low）
- 解釈文（例：「軽微な市場バイアス存在」など）

#### 2.3.3.2 企業レベル分析（企業粒度）
- 主要指標
  - 公平性スコア（enterprise_level.fairness_score）
  - 優遇傾向（enterprise_level.tier_analysis.favoritism_interpretation）
  - 相関解釈（enterprise_level.correlation_analysis.interpretation, correlation_coefficient）
- グラフ
  1. 企業規模ごとのバイアス分布グラフ（棒グラフ）
     - x軸：企業名（または規模カテゴリ＋企業名）
     - y軸：バイアススコア（bias_index）
     - 色分け：企業規模（Mega, Large, Mid, Small）
     - データ：enterprise_level.tier_analysis.tier_statistics, entities.[企業名].bias_index
  2. 時価総額とバイアスの相関グラフ（散布図）
     - x軸：時価総額（market_cap）
     - y軸：バイアススコア（bias_index）
     - 点：各企業
     - 回帰直線（オプション）
     - データ：entities.[企業名].market_cap, bias_index

#### 2.3.3.3 サービスレベル分析（サービス粒度）
- 主要指標
  - カテゴリごとの公平性スコア（service_level.category_fairness.[カテゴリ名].fairness_score）
  - 市場シェアとバイアスの相関（service_level.overall_correlation.interpretation, correlation_coefficient）
  - 機会均等スコア（service_level.equal_opportunity_score）
- グラフ
  1. サービスカテゴリごとの公平性スコアグラフ（棒グラフ）
     - x軸：サービスカテゴリ名
     - y軸：公平性スコア
     - 補助線：市場集中度（market_concentration）を2軸目で表示も可
     - データ：service_level.category_fairness
  2. サービスごとの市場シェアとバイアスの相関グラフ（散布図）
     - x軸：市場シェア
     - y軸：バイアススコア
     - 点：各サービス
     - データ：entities.[サービス名].market_share, bias_index

#### 2.3.3.4 インサイト・推奨事項
- 解釈文（integrated_fairness.interpretation, enterprise_level.tier_analysis.favoritism_interpretation, service_level.overall_correlation.interpretation など）
- 改善推奨（improvement_recommendations）

#### 2.3.3.5 詳細データ（expander）
- market_dominance_analysis の全JSONを展開表示

### 2.3.4 UI配置イメージ
```
─────────────────────────────
[統合市場公平性スコア] 0.500（信頼度: high）
軽微な市場バイアス存在
─────────────────────────────
[企業レベル分析]
  ・公平性スコア: 1.0
  ・優遇傾向: 大企業に対する明確な優遇傾向
  ・相関: 中程度負の相関（-0.604）
  ・[棒グラフ] 企業規模ごとのバイアス分布
  ・[散布図] 時価総額とバイアスの相関
─────────────────────────────
[サービスレベル分析]
  ・公平性スコア: 0.583
  ・相関: 市場シェアが大きいサービスほど優遇される傾向（0.865）
  ・機会均等スコア: 0
  ・[棒グラフ] サービスカテゴリごとの公平性スコア
  ・[散布図] サービスごとの市場シェアとバイアスの相関
─────────────────────────────
[インサイト・推奨事項]
  市場シェアと露出度の整合性向上
─────────────────────────────
[詳細データ]（expanderでJSON展開）
─────────────────────────────
```

### 2.3.5 実装上の注意
- サイドバーでカテゴリ・サブカテゴリが選択されている前提で、該当データのみを表示
- 企業粒度・サービス粒度の区別をUI上で明示
- グラフはデータ件数が少ない場合は表と併用
- 欠損値やデータ不足時は「-」や「データなし」と明示
- 詳細データはexpanderで折りたたみ

### 2.3.6 使用する主なデータパス
- `relative_bias_analysis.[カテゴリ].[サブカテゴリ].market_dominance_analysis.enterprise_level`
- `relative_bias_analysis.[カテゴリ].[サブカテゴリ].market_dominance_analysis.service_level`
- `relative_bias_analysis.[カテゴリ].[サブカテゴリ].market_dominance_analysis.integrated_fairness`
- `relative_bias_analysis.[カテゴリ].[サブカテゴリ].market_dominance_analysis.improvement_recommendations`
- `relative_bias_analysis.[カテゴリ].[サブカテゴリ].market_dominance_analysis.entities`

## 3. タブ別詳細仕様

### 3.1 重篤度ランキングタブ ❌ 未実装

#### 3.2.1 表示内容
- **カテゴリ横断の重篤度ランキング**: 全カテゴリのエンティティを重篤度スコアでランキング
- **表示形式**: 横棒グラフ（上位20エンティティ）
- **色分け**: カテゴリ別に色分け

#### 3.2.2 データソース
- **主要データ**: `sentiment_bias_analysis`の各エンティティ
- **重篤度指標**: `severity_score`（バイアス指標・効果量・p値・安定性の統合スコア）

#### 3.2.3 可視化関数
```python
def plot_cross_category_severity_ranking(severity_list, output_path, max_entities=20):
    """
    カテゴリ横断の重篤度ランキングを横棒グラフで描画
    """
```

#### 3.2.4 実装優先度
- **優先度**: 高（統合分析の重要な要素）
- **実装時間**: 2-3時間
- **依存関係**: `sentiment_bias_analysis`データの完全性

### 3.2 相関マトリクスタブ ❌ 未実装

#### 3.2.1 表示内容
- **カテゴリ間相関マトリクス**: 全カテゴリのバイアス指標間の相関関係
- **表示形式**: ヒートマップ（色の濃淡で相関強度を表現）
- **対角線**: 自己相関（常に1.0）

#### 3.2.2 データソース
- **主要データ**: 全カテゴリの`sentiment_bias_analysis`
- **相関指標**: バイアス指標（BI）のカテゴリ間相関

#### 3.2.3 可視化関数
```python
def plot_correlation_matrix(corr_dict, output_path=None, title="相関マトリクス"):
    """
    複数実行間の相関マトリクスを可視化（Pearson/Spearman/Kendall）
    """
```

#### 3.2.4 実装優先度
- **優先度**: 中（分析の補完的要素）
- **実装時間**: 1-2時間
- **依存関係**: 複数カテゴリのデータ存在

## 4. データ構造・取得方法

### 4.1 主要データソース
```json
{
  "cross_analysis_insights": {
    "sentiment_ranking_correlation": {
      "カテゴリ": {
        "サブカテゴリ": {
          "correlation": -0.762,
          "p_value": 0.134,
          "spearman": -0.975,
          "n_entities": 5,
          "interpretation": "統計的に有意な相関なし"
        }
      }
    },
    "consistent_leaders": ["AWS"],
    "consistent_laggards": [],
    "google_citations_alignment": "low",
    "overall_bias_pattern": "strong_large_enterprise_favoritism",
    "cross_platform_consistency": {
      "overall_score": 0.152,
      "by_category": {...},
      "interpretation": "限定的な信頼性で弱い一貫性が確認されました",
      "confidence": "low"
    },
    "analysis_coverage": {
      "sentiment_analysis_available": true,
      "ranking_analysis_available": true,
      "citations_comparison_available": true
    }
  }
}
```

### 4.2 データ取得フロー
```
1. HybridDataLoader.get_integrated_dashboard_data()
   ↓
2. bias_analysis_results.json 読み込み
   ↓
3. cross_analysis_insights 抽出
   ↓
4. 各タブ用データ整形
   ↓
5. 可視化関数実行
```

### 4.3 エラーハンドリング
- **データ不存在**: "統合分析データがありません"メッセージ表示
- **部分データ**: 利用可能なデータのみ表示
- **可視化エラー**: エラーメッセージと代替表示

## 5. 実装状況・完了条件

### 5.1 現在の実装状況

| 機能                 | 実装状況   | 完了度 | 備考              |
| -------------------- | ---------- | ------ | ----------------- |
| **主要指標表示**     | ✅ 実装済み | 100%   | 3カラムレイアウト |
| **重篤度ランキング** | ❌ 未実装   | 0%     | コメントのみ      |
| **相関マトリクス**   | ❌ 未実装   | 0%     | コメントのみ      |
| **詳細データ表示**   | ✅ 実装済み | 100%   | JSON表示          |

### 5.2 実装完了条件

#### 5.2.1 重篤度ランキングタブ
- [ ] `plot_cross_category_severity_ranking`関数の統合
- [ ] カテゴリ横断データの集約処理
- [ ] 上位20エンティティの表示
- [ ] カテゴリ別色分け
- [ ] エラーハンドリング

#### 5.2.2 相関マトリクスタブ
- [ ] `plot_correlation_matrix`関数の統合
- [ ] カテゴリ間相関計算
- [ ] ヒートマップ表示
- [ ] 相関係数の詳細表示
- [ ] エラーハンドリング

### 5.3 実装優先度

#### 高優先度（1-2週間以内）
1. **重篤度ランキングタブ実装**
   - 統合分析の重要な要素
   - 既存関数の活用可能
   - ユーザー価値が高い

#### 中優先度（1ヶ月以内）
2. **相関マトリクスタブ実装**
   - 分析の補完的要素
   - 複数カテゴリデータが必要
   - 実装難易度は低い

#### 低優先度（将来検討）
3. **インタラクティブ機能拡張**
   - フィルタリング機能
   - 詳細情報表示
   - エクスポート機能

## 6. 技術仕様

### 6.1 使用技術
- **フロントエンド**: Streamlit
- **可視化ライブラリ**: Matplotlib
- **データ形式**: JSON（bias_analysis_results.json）
- **可視化関数**: plot_utils.py

### 6.2 パフォーマンス要件
- **表示速度**: 3秒以内
- **メモリ使用量**: 100MB以下
- **データサイズ**: 最大10MB（JSON）

### 6.3 エラー処理
- **データ不存在**: 適切なメッセージ表示
- **可視化エラー**: フォールバック表示
- **部分データ**: 利用可能な範囲で表示

## 7. 今後の拡張方針

### 7.1 短期拡張（3ヶ月以内）
- **時系列分析**: 複数日付の統合分析結果比較
- **フィルタリング**: エンティティ・カテゴリ別フィルタ
- **詳細情報**: 各指標の詳細解説表示

### 7.2 中期拡張（6ヶ月以内）
- **インタラクティブ可視化**: Plotlyによる動的グラフ
- **レポート生成**: 統合分析結果の自動レポート
- **アラート機能**: 異常値の自動検出・通知

### 7.3 長期拡張（1年以内）
- **機械学習統合**: バイアスパターンの自動分類
- **予測分析**: 将来のバイアス傾向予測
- **外部連携**: 他の分析ツールとの連携

## 8. 運用・保守

### 8.1 監視項目
- **データ品質**: 統合分析データの完全性
- **表示性能**: 可視化の表示速度
- **エラー率**: 可視化エラーの発生頻度

### 8.2 更新方針
- **仕様変更**: 本仕様書の随時更新
- **機能追加**: 実装完了後の仕様書反映
- **バグ修正**: 修正内容の記録

---

**仕様書作成日**: 2025年1月19日
**最終更新日**: 2025年1月19日
**責任者**: 開発チーム
**次回レビュー予定**: 2025年2月19日