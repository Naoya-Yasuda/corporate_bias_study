# Corporate Bias Datasets

本ディレクトリには、AI検索サービスにおける企業優遇バイアス研究のデータセットが格納されています。

## データセット構造

```
corporate_bias_datasets/
├── LICENSE-DATASETS              # データセット用MITライセンス
├── README.md                     # このファイル
├── raw_data/                     # API別・日付別の生データ
│   └── YYYYMMDD/
│       ├── google/               # Google系API結果
│       ├── perplexity/           # Perplexity API結果
│       └── metadata/             # 収集メタデータ
├── integrated/                   # 統合データセット
│   └── YYYYMMDD/
│       ├── corporate_bias_dataset.json    # メイン統合データセット
│       ├── dataset_schema.json            # データ構造定義
│       ├── collection_summary.json        # 収集サマリー
│       └── integration_metadata.json      # 統合処理メタデータ
├── analysis/                     # 分析結果
│   └── YYYYMMDD/
│       ├── bias_analysis_*.json          # バイアス分析結果
│       ├── rank_comparison_*.csv         # ランキング比較データ
│       └── *.png                         # 可視化結果
├── publications/                 # 研究成果物
│   ├── LICENSE-REPORTS           # 論文・レポート用CC-BY-NC-SA 4.0
│   ├── papers/                   # 学術論文・研究レポート
│   └── datasets/                 # 公開用データセット
└── temp/                         # 一時ファイル・キャッシュ
```

## データセットの特徴

### API中立性
- Google、Perplexity等の特定APIに依存しない汎用設計
- 将来的なAPI追加（OpenAI、Anthropic等）に対応

### 研究標準対応
- 学術研究での利用を前提とした構造
- 再現性確保のためのメタデータ管理
- データセット配布の簡便性を考慮

### 時系列管理
- 日付ベース（YYYYMMDD）でのデータ管理
- 時系列バイアス分析への対応

## ライセンス

### データセット: MIT License
- 商用・非商用問わず自由に使用・改変可能
- 学術研究での活用を促進
- 引用要件付きで品質確保

**引用方法:**
```
Yasuda, N. (2025). Corporate Bias in AI Search Services Dataset.
Graduate Special Research Project, University [Name].
Available under MIT License.
```

### 論文・レポート: CC-BY-NC-SA 4.0
- 学術的利用を促進しつつ商用利用を制限
- 改変時の同一ライセンス継承で品質維持

## 使用方法

### データ収集
```bash
# Google検索データ収集
python -m src.loader.google_search_loader --perplexity-date 20251201

# Perplexity分析データ収集
python -m src.loader.perplexity_sentiment_loader --runs 3
python -m src.loader.perplexity_ranking_loader --runs 3
python -m src.loader.perplexity_citations_loader --runs 5

# 統合データセット作成
python -m src.integrator.create_integrated_dataset --date 20251201
```

### データ分析
```bash
# バイアス分析実行
python -m src.analysis.bias_ranking_pipeline --perplexity-date 20251201 --data-type citations
```

## データ品質

- **検証済み**: 各データセットは品質チェック済み
- **メタデータ**: 収集条件・処理履歴を完全記録
- **再現性**: 同一条件での結果再現が可能

## 注意事項

1. **API利用規約**: 元データの取得に使用したAPIの利用規約に従ってください
2. **第三者著作権**: 収集データに含まれる第三者コンテンツの権利に注意
3. **学術倫理**: 適切な学術倫理ガイドラインに従って使用してください
4. **更新情報**: 最新のデータセット情報はGitコミット履歴を参照

---

**データセット管理者:** 安田直也 (Naoya Yasuda)
**研究監督者:** 田中頼人教授 (Prof. Yorihito Tanaka)
**最終更新:** 2025年06月