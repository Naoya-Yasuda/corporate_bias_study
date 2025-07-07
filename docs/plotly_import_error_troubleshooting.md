# Plotly Import Error 解決手順書

## 概要
Streamlitアプリでplotlyのimportエラーが発生した場合の解決手順です。

## 1. requirements.txtにplotlyを明記 ✅ 完了
- `requirements.txt`に`plotly>=5.0.0`が既に記載済み

## 2. 環境を再構築する場合の手順

### 2.1 仮想環境の確認・再構築
```bash
# 現在のPython環境を確認
which python
which pip
which streamlit

# 仮想環境が有効になっているか確認
echo $VIRTUAL_ENV

# 環境を再構築する場合
# 1. 現在の環境を無効化
deactivate

# 2. 新しい環境を作成（例：condaの場合）
conda create -n cu_study_new python=3.12
conda activate cu_study_new

# 3. 依存関係をインストール
pip install --upgrade pip setuptools
pip install -r requirements.txt
```

### 2.2 環境変数の確認
```bash
# Pythonパスを確認
python -c "import sys; print(sys.executable)"

# インストール済みパッケージを確認
pip list | grep plotly
```

## 3. importエラーが出る場合の確認手順

### 3.1 エラー発生時の確認項目
**必ず以下の情報を確認してください：**

1. **どのPython環境で発生しているか**
   ```bash
   which python
   python --version
   echo $VIRTUAL_ENV
   ```

2. **どのコマンドで発生しているか**
   ```bash
   # Streamlit実行時
   streamlit run app.py

   # 直接Python実行時
   python -c "import plotly"

   # モジュール実行時
   python -m src.utils.plot_utils
   ```

3. **plotlyのインストール状況**
   ```bash
   pip show plotly
   python -c "import plotly; print(plotly.__version__)"
   ```

### 3.2 よくある問題と解決策

#### 問題1: 異なるPython環境で実行
**症状**: `ModuleNotFoundError: No module named 'plotly'`
**原因**: Streamlitが異なるPython環境で実行されている
**解決策**:
```bash
# 正しい環境でStreamlitを実行
conda activate cu_study
streamlit run app.py
```

#### 問題2: パッケージがインストールされていない
**症状**: `ModuleNotFoundError: No module named 'plotly'`
**原因**: plotlyがインストールされていない
**解決策**:
```bash
pip install plotly>=5.0.0
# または
pip install -r requirements.txt
```

#### 問題3: 環境変数の問題
**症状**: 環境によって動作が異なる
**原因**: PATHやPYTHONPATHの設定問題
**解決策**:
```bash
# 環境変数を確認
echo $PATH
echo $PYTHONPATH

# 必要に応じて設定
export PYTHONPATH="${PYTHONPATH}:/path/to/project"
```

### 3.3 デバッグ用コマンド
```bash
# 環境情報を一括確認
python -c "
import sys
import plotly
print(f'Python: {sys.executable}')
print(f'Python version: {sys.version}')
print(f'Plotly version: {plotly.__version__}')
print(f'Virtual env: {sys.prefix}')
"

# Streamlitの環境確認
streamlit --version
which streamlit
```

## 4. 推奨解決手順

### Step 1: 環境確認
```bash
which python
which streamlit
pip list | grep plotly
```

### Step 2: 環境統一
```bash
# 同じ環境でPythonとStreamlitを実行
conda activate cu_study
pip install -r requirements.txt
streamlit run app.py
```

### Step 3: テスト実行
```bash
# plotlyが正常にimportできるかテスト
python -c "import plotly; print('OK')"
```

## 5. 注意事項

- **条件付きimportは根本解決ではない**: `try/except`での条件付きimportは一時的な回避策であり、根本的な環境問題を隠す可能性があります
- **環境の一貫性**: Python、pip、streamlitが全て同じ環境で動作していることを確認してください
- **requirements.txtの更新**: 新しいパッケージを追加した場合は必ずrequirements.txtを更新してください

---

**作成日**: 2025年1月4日
**バージョン**: v1.0