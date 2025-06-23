# Corporate Bias Study - Licensing Guide

本プロジェクトは学術研究目的で設計されており、用途に応じて複数のライセンスを使い分けています。

## ライセンス構造

### 1. ソースコード - MIT License
**対象:** すべてのPythonコード、設定ファイル、スクリプト
**ライセンスファイル:** `LICENSE`
**用途:**
- 商用・非商用問わず自由に使用・改変可能
- 学術研究での引用・改変が容易
- geniac-prise等のコンテスト提出に制限なし
- 査読者による検証がしやすい

### 2. データセット - MIT License
**対象:** `corporate_bias_datasets/`内の生データ・統合データ
**ライセンスファイル:** `corporate_bias_datasets/LICENSE-DATASETS`
**用途:**
- 学術データセットとして広く活用可能
- 再配布・改変が自由
- 論文引用時の煩雑さを回避
- 引用要件付きで品質確保

### 3. 学術論文・レポート - CC-BY-NC-SA 4.0
**対象:** `corporate_bias_datasets/publications/papers/`内の論文・分析レポート
**ライセンスファイル:** `corporate_bias_datasets/publications/LICENSE-REPORTS`
**用途:**
- 学術的利用を促進しつつ商用利用を制限
- 改変時の同一ライセンス継承で品質維持
- 適切な帰属表示の確保

## 具体的な利用シーン

### 学術研究での利用
- **論文引用:** ソースコード（MIT）、データセット（MIT + Citation）を自由に使用
- **改変・拡張:** すべてのコンポーネントで改変可能
- **再配布:** ライセンス表示を維持して再配布可能

### geniac-prise提出
- **制限なし:** MIT Licenseにより商用利用・改変・再配布すべて可能
- **帰属表示:** LICENSE表示の維持のみ必要
- **コンテスト特性:** オープンソース精神に合致

### 商用利用
- **ソースコード:** MIT Licenseにより制限なし
- **データセット:** MIT Licenseにより制限なし（引用推奨）
- **論文・レポート:** CC-BY-NC-SA 4.0により非商用のみ

## ファイル構造とライセンス対応

```
.
├── LICENSE                                    # MIT (ソースコード)
├── src/                                      # MIT License
├── corporate_bias_datasets/
│   ├── LICENSE-DATASETS                      # MIT (データセット)
│   ├── raw_data/                            # MIT License
│   ├── integrated/                          # MIT License
│   ├── analysis/                            # MIT License
│   └── publications/
│       ├── LICENSE-REPORTS                  # CC-BY-NC-SA 4.0
│       ├── papers/                          # CC-BY-NC-SA 4.0
│       └── datasets/                        # MIT License
└── LICENSING.md                             # このファイル
```

## 引用方法

### ソースコード利用時
```
Yasuda, N. (2025). Corporate Bias Study Project [Computer software].
Available under MIT License.
```

### データセット利用時
```
Yasuda, N. (2025). Corporate Bias in AI Search Services Dataset.
Graduate Special Research Project, University [Name].
Available under MIT License.
```

### 論文・レポート引用時
```
Yasuda, N. (2025). Corporate Bias in AI Search Services: A Quantitative Analysis.
Graduate Special Research Project, under supervision of Prof. Yorihito Tanaka.
Licensed under CC-BY-NC-SA 4.0.
```

## 注意事項

1. **API使用:** 本プロジェクトはPerplexity API、Google Search API等のサードパーティAPIを使用します。これらのAPIには独自の利用規約が適用されます。

2. **データ収集:** 収集されたデータには第三者の著作権が含まれる場合があります。商用利用時は追加の権利確認が必要な場合があります。

3. **学術倫理:** 本プロジェクトの成果を利用する際は、適切な学術倫理ガイドラインに従ってください。

4. **更新情報:** ライセンス条項の変更については、GitHubのcommit履歴を参照してください。

---

**ライセンス管理者:** 安田直也 (Naoya Yasuda)
**監督者:** 田中頼人教授 (Prof. Yorihito Tanaka)
**最終更新:** 2025年06月