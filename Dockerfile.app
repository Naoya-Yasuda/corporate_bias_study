# 認証機能専用軽量Dockerfile
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# 最小限のシステムパッケージのみインストール
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# アプリ用requirements.txtをコピー
COPY requirements-app.txt .

# Pythonパッケージをインストール
RUN pip install --no-cache-dir -r requirements-app.txt

# 必要なファイルをコピー
COPY src/auth/ ./src/auth/
COPY src/components/auth_ui.py ./src/components/
COPY src/utils/auth_utils.py ./src/utils/
COPY src/utils/plot_utils.py ./src/utils/
COPY src/utils/storage_utils.py ./src/utils/
COPY src/utils/storage_config.py ./src/utils/
COPY src/analysis/hybrid_data_loader.py ./src/analysis/
COPY src/prompts/ ./src/prompts/
COPY app.py .

# ポート8501を公開
EXPOSE 8501

# 環境変数を設定
ENV PYTHONPATH=/app
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Streamlitアプリを起動
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]