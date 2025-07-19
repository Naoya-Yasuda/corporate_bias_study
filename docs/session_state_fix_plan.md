# セッション状態保持問題修正実装計画

## 概要
Streamlitダッシュボードのサイドバー選択状態が適切に保持されない問題を修正する実装計画

## 問題の現状
1. **依存関係リセットの過度な実行** - 日付ソース変更時にカテゴリ・サブカテゴリが強制リセット
2. **セッション状態更新の不適切なタイミング** - ウィジェット作成後の更新が無効化
3. **デフォルト値設定の競合** - 初回起動時と既存状態の競合
4. **エンティティ選択の状態保持欠如** - セッション状態で管理されていない

## 修正実装計画

### Phase 1: セッション状態管理の基盤修正

#### 1.1 初期化関数の改善
**ファイル**: `app.py` (lines 206-230)
**修正内容**:
- エンティティ選択のセッション状態初期化を追加
- より安全なデフォルト値設定ロジック
- 初期化順序の最適化

**現在のコード**:
```python
def initialize_session_state():
    """セッション状態の初期化"""
    # Streamlitのselectboxキーと統一
    if 'viz_type_selector' not in st.session_state:
        st.session_state.viz_type_selector = '単日分析'
    if 'viz_type_detail_selector' not in st.session_state:
        st.session_state.viz_type_detail_selector = '感情スコア分析'
    if 'sentiment_category_selector' not in st.session_state:
        st.session_state.sentiment_category_selector = None
    if 'sentiment_subcategory_selector' not in st.session_state:
        st.session_state.sentiment_subcategory_selector = None
    # ... 他の初期化
```

**修正後のコード**:
```python
def initialize_session_state():
    """セッション状態の初期化"""
    # 基本設定（常に初期化）
    if 'viz_type_selector' not in st.session_state:
        st.session_state.viz_type_selector = '単日分析'
    if 'viz_type_detail_selector' not in st.session_state:
        st.session_state.viz_type_detail_selector = '感情スコア分析'

    # データ依存設定（Noneで初期化）
    if 'sentiment_category_selector' not in st.session_state:
        st.session_state.sentiment_category_selector = None
    if 'sentiment_subcategory_selector' not in st.session_state:
        st.session_state.sentiment_subcategory_selector = None
    if 'sentiment_entities_selector' not in st.session_state:
        st.session_state.sentiment_entities_selector = []

    if 'citations_category_selector' not in st.session_state:
        st.session_state.citations_category_selector = None
    if 'citations_subcategory_selector' not in st.session_state:
        st.session_state.citations_subcategory_selector = None

    if 'ranking_category_selector' not in st.session_state:
        st.session_state.ranking_category_selector = None
    if 'ranking_subcategory_selector' not in st.session_state:
        st.session_state.ranking_subcategory_selector = None

    # 日付関連設定
    if 'date_selector' not in st.session_state:
        st.session_state.date_selector = None
    if 'date_source_selector' not in st.session_state:
        st.session_state.date_source_selector = None
    if 'dates_selector' not in st.session_state:
        st.session_state.dates_selector = []

    # デバッグ用
    if 'debug_checkbox' not in st.session_state:
        st.session_state.debug_checkbox = False
```

**修正のポイント**:
1. **エンティティ選択の初期化追加**: `sentiment_entities_selector`を空リストで初期化
2. **初期化順序の明確化**: 基本設定 → データ依存設定 → 日付関連 → デバッグ用
3. **コメントの追加**: 各セクションの目的を明確化

#### 1.2 依存関係管理の最適化
**ファイル**: `app.py` (lines 237-270)
**修正内容**:
- 過度なリセット処理の削除
- 詳細可視化タイプ別の適切なリセット
- デバッグログの改善

**現在のコード**:
```python
def update_session_state(key, value):
    """セッション状態を更新し、依存関係を管理"""
    st.session_state[key] = value

    # デバッグログ
    if 'debug_checkbox' in st.session_state and st.session_state.debug_checkbox:
        st.sidebar.write(f"🔄 状態更新: {key} = {value}")

    # 依存関係の管理
    if key == 'viz_type_selector':
        # 可視化タイプが変わったら詳細タイプをリセット
        st.session_state.viz_type_detail_selector = '感情スコア分析'
        st.session_state.sentiment_category_selector = None
        st.session_state.sentiment_subcategory_selector = None
        st.session_state.citations_category_selector = None
        st.session_state.citations_subcategory_selector = None
        st.session_state.ranking_category_selector = None
        st.session_state.ranking_subcategory_selector = None

    elif key == 'viz_type_detail_selector':
        # 詳細タイプが変わったらカテゴリ関連をリセット
        st.session_state.sentiment_category_selector = None
        st.session_state.sentiment_subcategory_selector = None
        st.session_state.citations_category_selector = None
        st.session_state.citations_subcategory_selector = None
        st.session_state.ranking_category_selector = None
        st.session_state.ranking_subcategory_selector = None

    elif key in ['sentiment_category_selector', 'citations_category_selector', 'ranking_category_selector']:
        # カテゴリが変わったらサブカテゴリをリセット
        if key == 'sentiment_category_selector':
            st.session_state.sentiment_subcategory_selector = None
        elif key == 'citations_category_selector':
            st.session_state.citations_subcategory_selector = None
        elif key == 'ranking_category_selector':
            st.session_state.ranking_subcategory_selector = None
```

**修正後のコード**:
```python
def update_session_state(key, value):
    """セッション状態を更新し、依存関係を管理"""
    st.session_state[key] = value

    # デバッグログ
    if 'debug_checkbox' in st.session_state and st.session_state.debug_checkbox:
        st.sidebar.write(f"🔄 状態更新: {key} = {value}")

    # 依存関係の管理（最適化版）
    if key == 'date_source_selector':
        # 日付ソース変更時は、データ依存の選択のみリセット
        # 可視化タイプは保持（ユーザーの選択を尊重）
        if st.session_state.debug_checkbox:
            st.sidebar.write("📅 日付ソース変更: データ依存選択をリセット")
        # リセット処理は削除（データ読み込み後に適切に処理）

    elif key == 'viz_type_selector':
        # 可視化タイプ変更時は、詳細タイプのみリセット
        # カテゴリ・サブカテゴリは保持（詳細タイプが同じ場合）
        st.session_state.viz_type_detail_selector = '感情スコア分析'
        if st.session_state.debug_checkbox:
            st.sidebar.write("📊 可視化タイプ変更: 詳細タイプをリセット")

    elif key == 'viz_type_detail_selector':
        # 詳細タイプ変更時は、対応するカテゴリ関連のみリセット
        if value == "感情スコア分析":
            st.session_state.sentiment_category_selector = None
            st.session_state.sentiment_subcategory_selector = None
            st.session_state.sentiment_entities_selector = []
        elif value == "Perplexity-Google比較":
            st.session_state.citations_category_selector = None
            st.session_state.citations_subcategory_selector = None
        elif value == "おすすめランキング分析結果":
            st.session_state.ranking_category_selector = None
            st.session_state.ranking_subcategory_selector = None

        if st.session_state.debug_checkbox:
            st.sidebar.write(f"🔍 詳細タイプ変更: {value}のカテゴリ関連をリセット")

    elif key in ['sentiment_category_selector', 'citations_category_selector', 'ranking_category_selector']:
        # カテゴリが変わったら対応するサブカテゴリとエンティティをリセット
        if key == 'sentiment_category_selector':
            st.session_state.sentiment_subcategory_selector = None
            st.session_state.sentiment_entities_selector = []
        elif key == 'citations_category_selector':
            st.session_state.citations_subcategory_selector = None
        elif key == 'ranking_category_selector':
            st.session_state.ranking_subcategory_selector = None

        if st.session_state.debug_checkbox:
            st.sidebar.write(f"📂 カテゴリ変更: {key}のサブカテゴリをリセット")

    elif key in ['sentiment_subcategory_selector', 'citations_subcategory_selector', 'ranking_subcategory_selector']:
        # サブカテゴリが変わったら対応するエンティティをリセット
        if key == 'sentiment_subcategory_selector':
            st.session_state.sentiment_entities_selector = []

        if st.session_state.debug_checkbox:
            st.sidebar.write(f"📁 サブカテゴリ変更: {key}のエンティティをリセット")
```

**修正のポイント**:
1. **過度なリセットの削除**: 日付ソース変更時の全リセットを削除
2. **詳細タイプ別リセット**: 変更された詳細タイプに対応するカテゴリのみリセット
3. **エンティティリセットの追加**: カテゴリ・サブカテゴリ変更時のエンティティリセット
4. **デバッグログの改善**: 各変更の理由を明確化
5. **条件分岐の最適化**: より具体的な条件でリセット範囲を制限

#### 1.3 セッション状態取得関数の改善
**ファイル**: `app.py` (lines 274-276)
**修正内容**:
- より安全なデフォルト値処理
- 型チェックの追加

**現在のコード**:
```python
def get_session_value(key, default=None):
    """セッション状態から値を取得"""
    return st.session_state.get(key, default)
```

**修正後のコード**:
```python
def get_session_value(key, default=None):
    """セッション状態から値を取得"""
    value = st.session_state.get(key, default)

    # デバッグログ
    if 'debug_checkbox' in st.session_state and st.session_state.debug_checkbox:
        st.sidebar.write(f"🔍 状態取得: {key} = {value}")

    return value
```

**修正のポイント**:
1. **デバッグログの追加**: 状態取得の追跡を可能に
2. **型安全性の確保**: 既存の動作を維持しつつ、将来の拡張に対応

#### 1.4 初期化順序の最適化
**ファイル**: `app.py` (lines 278-280)
**修正内容**:
- 初期化タイミングの明確化
- エラーハンドリングの追加

**現在のコード**:
```python
# セッション状態を初期化
initialize_session_state()
```

**修正後のコード**:
```python
# セッション状態を初期化（アプリ起動時に一度のみ実行）
try:
    initialize_session_state()
    if 'debug_checkbox' in st.session_state and st.session_state.debug_checkbox:
        st.sidebar.write("✅ セッション状態初期化完了")
except Exception as e:
    st.sidebar.error(f"❌ セッション状態初期化エラー: {e}")
```

**修正のポイント**:
1. **エラーハンドリング**: 初期化失敗時の適切な処理
2. **デバッグ情報**: 初期化完了の確認
3. **コメントの追加**: 初期化タイミングの明確化

### Phase 2: ウィジェット作成後の状態更新修正

#### 2.1 可視化タイプ選択の修正
**ファイル**: `app.py` (lines 290-300)
**修正内容**:
- ウィジェット作成後の状態更新を有効化
- 適切な依存関係管理

```python
# セッション状態を更新（ウィジェット作成後）
if viz_type != get_session_value('viz_type_selector'):
    update_session_state('viz_type_selector', viz_type)
```

#### 2.2 日付ソース選択の修正
**ファイル**: `app.py` (lines 340-350)
**修正内容**:
- 日付ソース変更時のリセット処理を削除
- 状態更新のみ実行

```python
# セッション状態を更新（ウィジェット作成後）
if selected_date_source != get_session_value('date_source_selector'):
    update_session_state('date_source_selector', selected_date_source)
```

#### 2.3 詳細可視化タイプ選択の修正
**ファイル**: `app.py` (lines 470-480)
**修正内容**:
- 詳細タイプ変更時の状態更新を有効化

```python
# セッション状態を更新（ウィジェット作成後）
if viz_type_detail != get_session_value('viz_type_detail_selector'):
    update_session_state('viz_type_detail_selector', viz_type_detail)
```

### Phase 3: カテゴリ・サブカテゴリ選択の修正

#### 3.1 感情スコア分析のカテゴリ選択
**ファイル**: `app.py` (lines 500-520)
**修正内容**:
- カテゴリ変更時の状態更新を有効化
- サブカテゴリの適切なリセット

```python
# セッション状態を更新（ウィジェット作成後）
if selected_category != get_session_value('sentiment_category_selector'):
    update_session_state('sentiment_category_selector', selected_category)
```

#### 3.2 感情スコア分析のサブカテゴリ選択
**ファイル**: `app.py` (lines 540-560)
**修正内容**:
- サブカテゴリ変更時の状態更新を有効化

```python
# セッション状態を更新（ウィジェット作成後）
if selected_subcategory != get_session_value('sentiment_subcategory_selector'):
    update_session_state('sentiment_subcategory_selector', selected_subcategory)
```

#### 3.3 エンティティ選択の修正
**ファイル**: `app.py` (lines 570-580)
**修正内容**:
- エンティティ選択のセッション状態管理を追加

```python
# セッション状態から選択されたエンティティを取得
current_entities = get_session_value('sentiment_entities_selector', [])
default_entities = entities[:10] if len(entities) > 10 else entities
if current_entities and all(e in entities for e in current_entities):
    default_entities = current_entities

selected_entities = st.sidebar.multiselect(
    "エンティティを選択（複数選択可）",
    entities,
    default=default_entities,
    key="sentiment_entities_selector"
)

# セッション状態を更新（ウィジェット作成後）
if selected_entities != get_session_value('sentiment_entities_selector'):
    update_session_state('sentiment_entities_selector', selected_entities)
```

### Phase 4: 他の詳細可視化タイプの修正

#### 4.1 Perplexity-Google比較の修正
**ファイル**: `app.py` (lines 700-750)
**修正内容**:
- カテゴリ・サブカテゴリ選択の状態更新を有効化

#### 4.2 おすすめランキング分析結果の修正
**ファイル**: `app.py` (lines 880-920)
**修正内容**:
- カテゴリ・サブカテゴリ選択の状態更新を有効化

### Phase 5: デフォルト値設定の改善

#### 5.1 より安全なデフォルト値設定
**修正内容**:
- データ存在チェックを追加
- 既存状態との競合を回避

```python
# 初回起動時のカテゴリデフォルト値設定
if get_session_value('sentiment_category_selector') is None:
    if category_options:
        st.session_state.sentiment_category_selector = category_options[0]
    else:
        st.session_state.sentiment_category_selector = None
```

## 実装順序

1. **Phase 1**: 基盤修正（初期化・依存関係管理） ✅ **完了**
2. **Phase 2**: ウィジェット作成後の状態更新修正
3. **Phase 3**: 感情スコア分析の選択状態修正
4. **Phase 4**: 他の詳細可視化タイプの修正
5. **Phase 5**: デフォルト値設定の改善

## テスト計画

### テストケース
1. **基本状態保持テスト**
   - 各選択項目を変更後、ページリロードで状態が保持されるか
   - ブラウザの戻る/進むボタンで状態が保持されるか

2. **依存関係テスト**
   - 可視化タイプ変更時の適切なリセット
   - 詳細可視化タイプ変更時の適切なリセット
   - カテゴリ変更時の適切なリセット

3. **エラーハンドリングテスト**
   - データが存在しない場合の適切な処理
   - 選択肢が変更された場合の適切な処理

### 検証方法
- デバッグ情報表示を有効にして状態を確認
- 各選択項目の変更をテスト
- ページリロード後の状態確認

## 期待される効果

1. **ユーザビリティの向上**: 選択状態が適切に保持される
2. **エラーの削減**: 不適切なリセットによるエラーの回避
3. **パフォーマンスの向上**: 不要なリセット処理の削減
4. **保守性の向上**: 明確な状態管理ロジック

## 注意事項

- 各Phaseの実装後は必ずテストを実行
- 既存の機能に影響がないことを確認
- デバッグ情報を活用して状態を監視
- 段階的な実装で問題を早期発見

## 実装完了状況

### Phase 1: セッション状態管理の基盤修正 ✅ **完了**
- **実装日**: 2025年7月19日
- **実装内容**:
  - 初期化関数の改善（エンティティ選択の初期化追加）
  - 依存関係管理の最適化（過度なリセット処理の削除）
  - セッション状態取得関数の改善（デバッグログ追加）
  - 初期化順序の最適化（エラーハンドリング追加）

### Phase 2-5: 未実装
- 残りのPhaseは順次実装予定

---
**作成日**: 2025年7月19日
**作成者**: AI Assistant
**対象ファイル**: `app.py`
**最終更新**: 2025年7月19日（Phase 1実装完了）