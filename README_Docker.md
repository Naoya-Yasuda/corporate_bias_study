# 企業バイアス分析ダッシュボード - Docker版

## 🐳 Dockerでの起動方法

### 前提条件
- Docker Desktop がインストールされていること
- Docker Compose が利用可能であること

### 1. クイックスタート（推奨）

```bash
# アプリを起動（パイプラインは起動しない）
docker-compose up -d

# ログを確認
docker-compose logs -f

# アプリにアクセス
# http://localhost:8501
```

### 2. データ分析パイプラインの実行

```bash
# パイプラインも含めて起動
docker-compose --profile pipeline up -d

# パイプラインのみ実行
docker-compose --profile pipeline up data-pipeline

# パイプライン実行後にログを確認
docker-compose logs data-pipeline
```

### 3. 手動ビルド

```bash
# イメージをビルド
docker build -t corporate-bias-dashboard .

# コンテナを起動
docker run -d \
  --name corporate-bias-dashboard \
  -p 8501:8501 \
  -v $(pwd)/corporate_bias_datasets:/app/corporate_bias_datasets \
  -v $(pwd)/logs:/app/logs \
  corporate-bias-dashboard
```

### 4. 管理コマンド

```bash
# アプリを停止
docker-compose down

# アプリを再起動
docker-compose restart

# ログを確認
docker-compose logs -f app-dashboard

# コンテナ内でシェルを実行
docker-compose exec app-dashboard bash

# イメージを再ビルド
docker-compose build --no-cache

# パイプラインのログを確認
docker-compose logs data-pipeline
```

### 5. 環境変数の設定

必要に応じて、`.env`ファイルを作成して環境変数を設定できます：

```bash
# .envファイルの例
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-1
PERPLEXITY_API_KEY=your_perplexity_api_key
```

### 6. データディレクトリのマウント

Docker Composeでは以下のディレクトリが自動的にマウントされます：

- `./corporate_bias_datasets` → `/app/corporate_bias_datasets`
- `./logs` → `/app/logs`

### 7. トラブルシューティング

#### ポートが既に使用されている場合
```bash
# 別のポートで起動
docker-compose up -d -p 8502:8501
```

#### 権限エラーが発生する場合
```bash
# データディレクトリの権限を確認
ls -la corporate_bias_datasets/
ls -la logs/

# 必要に応じて権限を変更
chmod 755 corporate_bias_datasets/
chmod 755 logs/
```

#### アプリが起動しない場合
```bash
# ログを詳細確認
docker-compose logs app-dashboard

# コンテナの状態を確認
docker-compose ps

# コンテナ内で直接確認
docker-compose exec app-dashboard python -c "import plotly; print('OK')"
```

### 8. 開発用設定

開発時は、ソースコードの変更を即座に反映させるために、ソースディレクトリをマウントできます：

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app-dashboard:
    build:
      context: .
      dockerfile: Dockerfile.app
    volumes:
      - .:/app  # ソースコードをマウント
      - ./corporate_bias_datasets:/app/corporate_bias_datasets
      - ./logs:/app/logs
    ports:
      - "8501:8501"
```

```bash
# 開発用に起動
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

## 🎯 メリット

1. **環境の一貫性**: どの環境でも同じ動作を保証
2. **依存関係の解決**: plotlyなどの環境問題を完全に回避
3. **簡単なデプロイ**: ワンコマンドで起動可能
4. **分離された環境**: システム環境に影響を与えない
5. **スケーラビリティ**: 必要に応じて複数インスタンスを起動可能

## 📝 注意事項

- 初回起動時はイメージのビルドに時間がかかります
- データディレクトリの権限設定に注意してください
- 本番環境では適切なセキュリティ設定を行ってください