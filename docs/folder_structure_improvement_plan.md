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

### 影響範囲
- `src/categories.py` - カテゴリファイルパスの更新
- `src/analysis/bias_analysis_engine.py` - 設定ファイルパスの更新
- その他設定ファイルを参照しているモジュール

## 注意事項

- 設定ファイル移動時は、既存のコードが正しく新しいパスを参照するよう更新が必要
- テスト環境での動作確認を必ず実施
- ドキュメントの更新も忘れずに実施

---

**作成日**: 2025年8月27日
**更新日**: 2025年8月27日
**作成者**: AI Assistant
**ステータス**: Phase 1完了、Phase 2実装準備中
