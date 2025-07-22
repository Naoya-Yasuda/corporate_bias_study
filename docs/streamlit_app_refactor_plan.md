# Streamlitアプリ（app.py）分割・コンポーネント化設計案

## 目的
- コードの可読性・保守性・拡張性を高めるため、巨大化したapp.pyを機能ごとに分割し、コンポーネント化する。
- チーム開発や将来的な機能追加・修正を容易にする。

## 分割のメリット
- 1ファイルあたりの行数を削減し、見通しを良くする
- 機能ごとに責任範囲を明確化し、バグ修正や機能追加の影響範囲を限定できる
- グラフ描画やテーブル表示などの部品を再利用しやすくなる
- テストやセルフレビューがしやすくなる

## 推奨ディレクトリ・ファイル構成例

```
src/
  components/
    plots.py         # グラフ描画関数群
    sidebar.py       # サイドバーUI部品
    tables.py        # データテーブル表示部品
    tabs.py          # タブ切り替えUI部品
  views/
    single_day.py    # 単日分析ページ
    timeseries.py    # 時系列分析ページ
    integrated.py    # 統合分析ページ
  utils/
    streamlit_utils.py  # Streamlit共通ユーティリティ
    data_utils.py       # データ整形・前処理
app.py                # ルーティングと全体構成のみ
```

## 各ファイルの役割
- `components/`：グラフ・テーブル・サイドバーなどUI部品の集約
- `views/`：ページ単位のロジック（単日分析・時系列分析・統合分析など）
- `utils/`：共通的なデータ処理・Streamlitユーティリティ
- `app.py`：ページ切り替え・全体初期化・ルーティングのみ

## app.pyの実装イメージ

```python
import streamlit as st
from src.views import single_day, timeseries, integrated

st.set_page_config(...)
page = st.sidebar.selectbox("ページ選択", ["単日分析", "時系列分析", "統合分析"])

if page == "単日分析":
    single_day.render()
elif page == "時系列分析":
    timeseries.render()
elif page == "統合分析":
    integrated.render()
```

## 今後のリファクタリング方針
1. 現状のapp.pyの機能ブロックを洗い出し、上記構成にマッピングする
2. 各部品・ページごとに関数・クラス化し、該当ファイルへ移動
3. importパスや依存関係を整理し、動作確認
4. 必要に応じてテスト・セルフレビューを実施

---

（本ドキュメントは2024年7月時点の設計方針です。今後の要件追加や運用状況に応じて随時アップデートしてください）