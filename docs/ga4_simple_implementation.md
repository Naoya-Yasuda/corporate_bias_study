# GA4 Analytics シンプル実装ガイド

## 概要

このドキュメントでは、StreamlitアプリケーションでのGoogle Analytics 4（GA4）のシンプルな実装方法について説明します。

## 実装方法

### 1. ファイル構成

```
├── app.py              # メインアプリケーション
├── ga4.html            # GA4トラッキングコード
└── .env                # 環境変数設定
```

### 2. GA4 HTMLファイル

`ga4.html`ファイルにGA4のトラッキングコードを記述：

```html
<!-- ga4.html -->
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-9GSKL97QXW"></script>
<script>
    window.dataLayer = window.dataLayer || [];
    function gtag() { dataLayer.push(arguments); }
    gtag('js', new Date());

    gtag('config', 'G-9GSKL97QXW', {
        page_title: document.title,
        page_location: window.location.href,
        custom_map: {
            'custom_parameter_1': 'streamlit_app',
            'custom_parameter_2': 'user_action'
        }
    });
</script>
```

### 3. アプリケーション統合

`app.py`でGA4スクリプトを読み込み：

```python
import streamlit.components.v1 as components
import os

# GA4 Analytics 設定
GA4_MEASUREMENT_ID = os.getenv('GA4_MEASUREMENT_ID', 'G-9GSKL97QXW')
GA4_ENABLED = os.getenv('GA4_ENABLED', 'true').lower() == 'true'

# GA4 トラッキング（設定が有効な場合のみ）
if GA4_ENABLED and GA4_MEASUREMENT_ID:
    try:
        # HTML ファイルからGA4スクリプトを読み込み
        with open("ga4.html", "r") as f:
            ga4_js = f.read()

        # スクリプトを埋め込み（高さ 0 で表示上は非表示に）
        components.html(ga4_js, height=0)
    except FileNotFoundError:
        st.warning("GA4設定ファイルが見つかりません")
    except Exception as e:
        st.warning(f"GA4設定でエラーが発生しました: {e}")
```

### 4. 環境変数設定

`.env`ファイルに以下を追加：

```bash
# GA4 Analytics設定
GA4_MEASUREMENT_ID=G-9GSKL97QXW
GA4_ENABLED=true
```

## 設定手順

### 1. GA4アカウント準備
- [Google Analytics](https://analytics.google.com/) にアクセス
- 新しいプロパティを作成（GA4形式）
- 測定ID（G-XXXXXXXXXX）を取得

### 2. ファイル設定
- `ga4.html`の測定IDを実際のIDに変更
- `.env`ファイルの測定IDを更新

### 3. 動作確認
- Streamlitアプリを起動
- ブラウザの開発者ツールでネットワークタブを確認
- GA4のリアルタイムレポートでイベントを確認

## メリット

✅ **シンプル**: 複雑なライブラリ不要
✅ **軽量**: 最小限のコードで実装
✅ **確実**: GA4の標準的な実装方法
✅ **カスタマイズ可能**: 必要に応じてイベントトラッキングも追加可能
✅ **環境変数対応**: 開発・本番環境での設定管理が容易

## トラッキング対象

- **ページビュー**: 各ページへのアクセス
- **ユーザーセッション**: アプリケーションの利用状況
- **デバイス情報**: ブラウザ、OS、デバイス種別
- **地理的情報**: 国・地域（IPアドレスベース）

## プライバシー配慮

- 個人情報は一切送信しない
- 匿名化されたユーザー行動のみ追跡
- 環境変数による完全無効化可能
- 適切なプライバシーポリシーの策定が必要

## 拡張案

### カスタムイベントトラッキング

必要に応じて、特定のユーザーアクションを追跡：

```javascript
// ボタンクリック時のイベント送信例
gtag('event', 'button_click', {
    'button_name': 'analyze_button',
    'section': 'dashboard'
});
```

### エラー追跡

```javascript
// エラー発生時のイベント送信例
gtag('event', 'error', {
    'error_type': 'data_loading_error',
    'error_message': 'Failed to load data'
});
```

---

**注意**: この実装は研究目的のアプリケーション用に設計されています。商用利用時は、適切なプライバシーポリシーと利用規約の策定が必要です。
