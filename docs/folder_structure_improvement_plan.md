# フォルダ構成改善計画

## 概要

現在のフォルダ構成における問題点を分析し、保守性・拡張性・可読性を向上させる改善計画を策定しました。

## 現在の問題点

### 1. 設定ファイルの分散
- `config/` フォルダに分析設定ファイル
- `src/data/` にカテゴリ設定ファイル
- 設定ファイルが2箇所に分散している

### 2. スクリプトの位置と依存関係
- `scripts/` フォルダのスクリプトが `src/` を直接import
- プロジェクトルートをPythonパスに追加する必要がある
- スクリプトがsrcの内部構造に依存している

### 3. データと設定の混在
- `src/data/` に設定ファイル（categories.yml）とデータファイル（market_shares.json）が混在
- データと設定の責任が不明確

## 改善案

### 提案1: 設定ファイルの統合

```
config/
├── analysis/
│   ├── analysis_config.yml      # バイアス分析設定
│   ├── categories.yml           # 分析対象カテゴリ・エンティティ
│   └── thresholds.yml           # 閾値設定
├── sns/
│   ├── sns_monitoring_config.yml
│   └── simple_sns_config.yml
├── data/
│   ├── market_shares.json       # 市場シェアデータ
│   └── market_caps.json         # 時価総額データ
└── app/
    └── app_config.yml           # アプリケーション設定
```

### 提案2: スクリプトの再構成

```
scripts/
├── analysis/
│   └── run_bias_analysis.py     # 分析実行スクリプト
├── sns/
│   └── github_actions_sns_posting.py
├── data/
│   ├── collect_data.py          # データ収集スクリプト
│   └── integrate_data.py        # データ統合スクリプト
└── utils/
    ├── setup_environment.py     # 環境セットアップ
    └── validate_data.py         # データ検証
```

### 提案3: srcフォルダの整理

```
src/
├── analysis/                    # 分析エンジン（現状維持）
├── loader/                      # データローダー（現状維持）
├── integrator/                  # データ統合（現状維持）
├── sns/                         # SNS機能（現状維持）
├── utils/                       # ユーティリティ（現状維持）
├── auth/                        # 認証機能（現状維持）
├── components/                  # Webコンポーネント（現状維持）
├── prompts/                     # プロンプト管理（現状維持）
└── data/                        # データ定義（設定ファイルを削除）
    └── __init__.py
```

### 提案4: エントリーポイントの改善

```
bin/                             # 新しいエントリーポイントディレクトリ
├── bias-analysis               # 分析実行コマンド
├── sns-posting                 # SNS投稿コマンド
└── data-collection             # データ収集コマンド
```

## 改善手順

### Phase 1: 設定ファイル統合
1. `src/data/categories.yml` → `config/analysis/categories.yml`
2. `src/data/market_*.json` → `config/data/`
3. 設定ファイル読み込みパスの更新

### Phase 2: スクリプト整理
1. `scripts/` を機能別にサブディレクトリ分割
2. 共通の設定読み込み機能を実装
3. エントリーポイントの統一

### Phase 3: 依存関係の改善
1. `src/` 内のモジュール間依存関係の整理
2. 設定管理の一元化
3. エラーハンドリングの統一

## メリット

1. **設定の一元管理**: すべての設定ファイルが `config/` に集約
2. **責任の明確化**: データ、設定、スクリプトの役割が明確
3. **保守性向上**: 設定変更時の影響範囲が明確
4. **拡張性**: 新しい機能追加時の配置が明確

## 実装計画

### Phase 1 詳細タスク
- [x] `config/analysis/` ディレクトリ作成
- [x] `config/data/` ディレクトリ作成
- [x] `src/data/categories.yml` → `config/analysis/categories.yml` 移動
- [x] `src/data/market_shares.json` → `config/data/` 移動
- [x] `src/data/market_caps.json` → `config/data/` 移動
- [x] 設定ファイル読み込みパスの更新
- [x] 動作確認とテスト
- [x] 不要な`src/data`ディレクトリの削除

### Phase 2 詳細タスク
- [x] `scripts/` を機能別にサブディレクトリ分割
- [x] 共通の設定読み込み機能を実装
- [x] エントリーポイントの統一
- [x] 新しいスクリプトの作成（データ収集、統合、検証、環境セットアップ）
- [x] 既存スクリプトの更新（共通設定管理の使用）
- [x] GitHub Actions YAMLファイルの修正（新しいスクリプトパスに更新）
- [x] READMEの構成部分の修正（使用方法、システム構成図の更新）
- [x] 動作確認とテスト

### Phase 3 詳細タスク
- [ ] `src/` 内のモジュール間依存関係の分析と整理
- [ ] 設定管理の一元化（ConfigManagerの拡張）
- [ ] エラーハンドリングの統一
- [ ] ログ出力の標準化
- [ ] 型ヒントの追加と統一
- [ ] ドキュメンテーションの改善

### 影響範囲

#### Phase 1 影響範囲
- `src/categories.py` - カテゴリファイルパスの更新
- `src/analysis/bias_analysis_engine.py` - 設定ファイルパスの更新
- その他設定ファイルを参照しているモジュール

#### Phase 2 影響範囲
- `scripts/analysis/run_bias_analysis.py` - 共通設定管理の使用に更新
- `scripts/sns/github_actions_sns_posting.py` - 共通設定管理の使用に更新
- `.github/workflows/perplexity_bias_analysis.yml` - 新しいスクリプトパスに更新
- `README.md` - 使用方法、システム構成図、テスト手順の更新

#### Phase 3 影響範囲
- `src/` 内の全モジュール - 依存関係の整理、設定管理の統一
- `src/utils/` - 共通ユーティリティの拡張
- `src/analysis/` - エラーハンドリングとログ出力の統一
- `src/loader/` - 設定管理とエラーハンドリングの統一
- `src/integrator/` - 設定管理とエラーハンドリングの統一
- `src/sns/` - 設定管理とエラーハンドリングの統一

## 注意事項

- 設定ファイル移動時は、既存のコードが正しく新しいパスを参照するよう更新が必要
- スクリプトパス変更時は、GitHub ActionsワークフローとREADMEの更新が必要
- テスト環境での動作確認を必ず実施
- ドキュメントの更新も忘れずに実施

---

**作成日**: 2025年8月27日
**更新日**: 2025年8月27日
**作成者**: AI Assistant
**ステータス**: Phase 2完了、Phase 3実装準備中

## Phase 3 詳細計画

### 3.1 モジュール間依存関係の分析と整理
- `src/` 内の各モジュールの依存関係を可視化
- 循環依存の検出と解消
- 不要な依存関係の削除
- 依存関係の階層化

### 3.2 設定管理の一元化
- `ConfigManager` クラスの拡張
- 環境変数の統一管理
- 設定値のバリデーション機能
- 設定の動的更新機能

### 3.3 エラーハンドリングの統一
- 共通エラークラスの定義
- エラーメッセージの標準化
- エラーログの統一フォーマット
- リトライ機能の実装

### 3.4 ログ出力の標準化
- ログレベルの統一
- ログフォーマットの標準化
- 構造化ログの導入
- ログローテーション機能

### 3.5 型ヒントとドキュメンテーション
- 全関数・クラスに型ヒント追加
- docstringの統一フォーマット
- API仕様書の自動生成
- コードコメントの改善
