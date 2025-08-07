# バイアス状況自動SNS投稿機能 要件定義書

## 1. 概要

### 1.1 目的
企業優遇バイアス分析結果において、顕著なバイアス指標やトレンド変化が検知された場合に、自動的にX（旧Twitter）API経由で社会発信・啓発を行う機能を実装する。

### 1.2 背景
- 企業優遇バイアスの可視化と啓発による社会的インパクトの最大化
- 定期的な分析結果の自動発信による継続的な社会啓発
- バイアス指標の閾値超過時の即座なアラート機能

### 1.3 対象ユーザー
- 研究者・アナリスト（分析結果の自動発信）
- 一般社会（バイアス啓発情報の受信）
- 企業・政策立案者（バイアス状況の把握）

## 2. 機能要件

### 2.1 自動投稿トリガー機能

#### 2.1.1 時系列変化監視（トライアル対象）
- **感情スコアの大きな変化監視**
  - 過去7日間の感情スコア推移
  - 変化率閾値: ±20%以上の急激な変化
  - 監視対象: Raw Delta (Δ)、Normalized Bias Index (BI)
  - 統計的有意性: p < 0.05 かつ |δ| ≥ 0.33

- **おすすめランキングの大きな変化監視**
  - 過去7日間のランキング順位変化
  - 変化閾値: 上位3位以内の順位変動、または±3位以上の急激な変化
  - 監視対象: Google検索ランキング、Perplexityランキング
  - 統計的有意性: RBO < 0.7 または Kendall Tau < 0.5

- **Perplexity分析結果の大きな変化監視**
  - 公式非公式率の変化: ±15%以上の変化
  - ポジティブネガティブ率の変化: ±20%以上の変化
  - 監視対象: official_results比率、sentiment分布
  - 統計的有意性: カイ二乗検定 p < 0.05

- **Google-Perplexity比較分析の大きな変化監視**
  - RBO（Rank-Biased Overlap）の変化: ±0.2以上の変化
  - Kendall Tauの変化: ±0.3以上の変化
  - 監視対象: クロスプラットフォーム比較指標
  - 統計的有意性: 相関の有意性検定 p < 0.05

#### 2.1.2 統計的有意性検証（トライアル対象）
- **符号検定 p値**
  - 閾値: p < 0.05（統計的有意性）
  - 信頼区間: 95%信頼区間での検証

- **効果量検証**
  - Cliff's Delta: |δ| ≥ 0.33（中程度以上の効果）
  - 実質的な差の大きさの確認

#### 2.1.3 その他の監視機能（トライアル対象外）
- **バイアス指標閾値監視**: 将来的な実装予定
- **市場構造変化検知**: 将来的な実装予定
- **Severity Score監視**: 将来的な実装予定

### 2.2 投稿コンテンツ生成機能

#### 2.2.1 テンプレート文生成
- **基本テンプレート構造**
  ```
  🚨【企業優遇バイアス変化検知】

  📊 検知内容: {変化種別}
  🏢 対象企業: {企業名}
  📈 変化率: {変化率}%
  📋 詳細: {簡潔な説明}

  🔍 分析詳細: {URL}
  #企業優遇バイアス #AI分析 #透明性
  ```

- **変化種別別テンプレート**
  - **感情スコア変化**: 企業名表示による評価変化の急激な変動
  - **ランキング変化**: 検索結果ランキングの大幅な変動
  - **情報源変化**: Perplexityの公式・非公式情報比率の変化
  - **感情傾向変化**: ポジティブ・ネガティブ評価比率の変化
  - **プラットフォーム差異**: Google-Perplexity間の分析結果差異の変化

#### 2.2.2 グラフ画像生成
- **感情スコア変化可視化**
  - Raw Delta の時系列推移グラフ
  - Normalized Bias Index の変化率グラフ
  - 統計的有意性の推移

- **ランキング変化可視化**
  - Google vs Perplexity ランキング比較
  - 順位変動のヒートマップ
  - RBO・Kendall Tau の推移

- **Perplexity分析変化可視化**
  - 公式非公式率の時系列推移
  - ポジティブネガティブ率の変化
  - 情報源分布の変化

- **画像仕様**
  - 形式: PNG/JPG
  - サイズ: 1200x630px（X推奨サイズ）
  - 解像度: 72 DPI
  - ファイルサイズ: 5MB以下

#### 2.2.3 動的コンテンツ生成
- **企業名動的挿入**
  - 検知された企業名の自動挿入
  - 複数企業の場合は主要企業を優先

- **指標値動的挿入**
  - 実際のバイアス指標値の挿入
  - 統計的有意性レベルの表示

- **URL動的生成**
  - 詳細分析結果へのリンク生成
  - 分析日付を含むURL構造

### 2.3 X API連携機能

#### 2.3.1 API認証・設定
- **認証方式**
  - OAuth 2.0認証
  - Bearer Token認証
  - API Key管理

- **環境変数設定**
  ```
  TWITTER_API_KEY=your_api_key
  TWITTER_API_SECRET=your_api_secret
  TWITTER_ACCESS_TOKEN=your_access_token
  TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
  TWITTER_BEARER_TOKEN=your_bearer_token
  ```

#### 2.3.2 投稿機能
- **テキスト投稿**
  - 文字数制限: 280文字以内
  - ハッシュタグ自動付与
  - URL短縮機能

- **画像投稿**
  - 画像アップロード機能
  - 複数画像対応（最大4枚）
  - 画像説明文生成

- **スレッド投稿**
  - 複数ツイートの連続投稿
  - 詳細分析結果の段階的開示

#### 2.3.3 投稿制御
- **投稿頻度制限**
  - 1日最大10投稿
  - 同一企業の重複投稿防止（24時間）
  - 同一カテゴリの重複投稿防止（12時間）

- **投稿時間最適化**
  - 日本時間 9:00-21:00 の範囲
  - エンゲージメント率の高い時間帯を優先

### 2.4 監視・管理機能

#### 2.4.1 投稿履歴管理
- **投稿ログ**
  - 投稿日時・内容・反応の記録
  - 投稿成功・失敗の記録
  - エラーログの保存

- **投稿統計**
  - 投稿頻度・エンゲージメント率
  - バイアス種別別投稿数
  - 企業別投稿頻度

#### 2.4.2 設定管理
- **閾値設定**
  - 各バイアス指標の閾値調整
  - 投稿頻度制限の調整
  - 投稿時間帯の設定

- **テンプレート管理**
  - 投稿テンプレートの編集
  - ハッシュタグの追加・削除
  - 画像テンプレートの管理

#### 2.4.3 監視ダッシュボード
- **リアルタイム監視**
  - 現在のバイアス指標状況
  - 投稿待機状況
  - API接続状況

- **統計レポート**
  - 月次・週次投稿統計
  - エンゲージメント分析
  - バイアス検知頻度分析

## 3. 非機能要件

### 3.1 性能要件
- **応答時間**
  - バイアス検知から投稿まで: 5分以内
  - 画像生成時間: 30秒以内
  - API応答時間: 10秒以内

- **処理能力**
  - 同時監視エンティティ数: 1000以上
  - 日次処理能力: 10000エンティティ以上
  - 画像生成能力: 100枚/時間

### 3.2 可用性要件
- **稼働率**
  - システム稼働率: 99.5%以上
  - 計画メンテナンス時間: 月1回、2時間以内
  - 障害復旧時間: 30分以内

- **冗長性**
  - API接続の冗長化
  - 画像生成処理の並列化
  - データベースのバックアップ

### 3.3 セキュリティ要件
- **認証・認可**
  - X API認証情報の暗号化保存
  - 投稿権限の適切な管理
  - アクセスログの記録

- **データ保護**
  - 個人情報の非開示
  - 企業機密情報の保護
  - 投稿内容の事前検証

### 3.4 保守性要件
- **ログ管理**
  - 詳細なログ記録
  - エラー追跡機能
  - パフォーマンス監視

- **設定管理**
  - 設定ファイルの一元管理
  - 環境別設定の分離
  - 設定変更の履歴管理

## 4. 技術仕様

### 4.1 アーキテクチャ
- **モジュール構成**
  ```
  src/
  ├── sns/
  │   ├── __init__.py
  │   ├── twitter_client.py      # X API連携
  │   ├── content_generator.py   # 投稿コンテンツ生成
  │   ├── threshold_monitor.py   # 閾値監視
  │   ├── image_generator.py     # グラフ画像生成
  │   └── posting_manager.py     # 投稿管理
  ```

### 4.2 データベース設計
- **投稿履歴テーブル**
  ```sql
  CREATE TABLE sns_posts (
      id INTEGER PRIMARY KEY,
      post_id VARCHAR(50),
      content TEXT,
      image_path VARCHAR(255),
      bias_metrics JSON,
      posted_at TIMESTAMP,
      engagement_metrics JSON,
      status VARCHAR(20)
  );
  ```

- **設定テーブル**
  ```sql
  CREATE TABLE sns_settings (
      id INTEGER PRIMARY KEY,
      setting_key VARCHAR(50),
      setting_value TEXT,
      updated_at TIMESTAMP
  );
  ```

### 4.3 外部API連携
- **X API v2**
  - エンドポイント: `https://api.twitter.com/2/`
  - 認証: OAuth 2.0
  - レート制限: 300 requests/15min

- **画像生成API**
  - Plotly（グラフ生成）
  - Pillow（画像編集）
  - カスタムテンプレート

## 5. 実装計画

### 5.1 Phase 1: 時系列変化監視機能実装（2週間）
- 時系列データ収集・保存機能
- 変化率計算・閾値判定機能
- 統計的有意性検証機能

### 5.2 Phase 2: 投稿機能実装（2週間）
- X API連携機能
- 基本的な投稿機能
- テンプレート文生成

### 5.3 Phase 3: 監視・管理機能（1週間）
- 投稿履歴管理
- 設定管理
- 監視ダッシュボード

### 5.4 Phase 4: テスト・最適化（1週間）
- 統合テスト
- パフォーマンス最適化
- セキュリティ強化

### 5.5 将来の拡張予定（トライアル対象外）
- バイアス指標閾値監視機能
- 市場構造変化検知機能
- 高度な画像生成機能

## 6. リスク・制約事項

### 6.1 技術的リスク
- **X API制限**
  - レート制限による投稿遅延
  - API仕様変更への対応
  - 認証トークンの有効期限

- **画像生成負荷**
  - 大量画像生成時の処理遅延
  - ストレージ容量の制約
  - メモリ使用量の増加

### 6.2 運用リスク
- **投稿内容の品質**
  - 誤検知による不適切投稿
  - 企業名の誤認識
  - 統計的有意性の誤判定

- **法的リスク**
  - 企業の名誉毀損
  - 個人情報の漏洩
  - 著作権侵害

### 6.3 制約事項
- **X API制約**
  - 投稿文字数制限（280文字）
  - 画像サイズ制限（5MB）
  - 投稿頻度制限

- **技術制約**
  - リアルタイム処理の限界
  - 画像生成の処理時間
  - データベース容量

## 7. 成功指標

### 7.1 定量的指標
- **投稿成功率**: 95%以上
- **平均エンゲージメント率**: 2%以上
- **投稿頻度**: 1日平均3-5投稿
- **システム稼働率**: 99.5%以上

### 7.2 定性的指標
- **社会的インパクト**
  - バイアス啓発の認知度向上
  - 企業の透明性向上への貢献
  - 研究コミュニティでの評価

- **技術的品質**
  - 投稿内容の正確性
  - システムの安定性
  - ユーザビリティ

## 8. 今後の拡張計画

### 8.1 短期拡張（3ヶ月以内）
- **他SNS対応**
  - LinkedIn投稿機能
  - 研究コミュニティ向け投稿

- **高度な分析機能**
  - 機械学習による投稿最適化
  - エンゲージメント予測

### 8.2 中期拡張（6ヶ月以内）
- **多言語対応**
  - 英語投稿機能
  - 国際的な研究発信

- **インタラクティブ機能**
  - フォロワーとの対話機能
  - 質問応答機能

### 8.3 長期拡張（1年以内）
- **AI自動化**
  - 投稿内容の自動最適化
  - エンゲージメント予測AI
  - 自動応答機能

---

## 9. 詳細設計仕様（2025年1月27日追加）

### 9.1 監視対象指標の詳細

#### 9.1.1 NBI（Normalized Bias Index）監視
- **変化率閾値**: ±20%以上の変化
- **計算方法**: (current_nbi - previous_nbi) / previous_nbi * 100
- **統計的有意性**: p < 0.05 かつ |Cliff's Delta| ≥ 0.33
- **監視対象**: 全カテゴリの全エンティティ

#### 9.1.2 おすすめランキング順位監視
- **変化閾値**:
  - 上位3位以内の順位変動
  - または±3位以上の急激な変化
- **監視対象**: Google検索ランキング、Perplexityランキング
- **統計的有意性**: RBO < 0.7 または Kendall Tau < 0.5

#### 9.1.3 サービスレベル公平性スコア監視
- **変化率閾値**: ±15%以上の変化
- **計算方法**: (current_score - previous_score) / previous_score * 100
- **監視対象**: 全カテゴリのサービスレベル公平性スコア
- **統計的有意性**: 信頼区間95%での有意性

#### 9.1.4 企業レベル公平性スコア監視
- **変化率閾値**: ±15%以上の変化
- **計算方法**: (current_score - previous_score) / previous_score * 100
- **監視対象**: 全カテゴリの企業レベル公平性スコア
- **統計的有意性**: 信頼区間95%での有意性

### 9.2 時系列データ参照ロジック

#### 9.2.1 先週データ参照方式
- **参照データ**: S3に保存された先週の分析結果
- **データパス**: `s3://{bucket}/corporate_bias_datasets/integrated/{YYYYMMDD}/bias_analysis_results.json`
- **比較期間**: 現在の分析日と先週の分析日（7日前）
- **フォールバック**: 先週データが存在しない場合は2週間前、3週間前と遡及

#### 9.2.2 データ取得処理
```python
def get_previous_week_data(current_date: str) -> Dict:
    """先週の分析データをS3から取得"""
    # 先週の日付を計算
    current_dt = datetime.strptime(current_date, "%Y%m%d")
    previous_week = current_dt - timedelta(days=7)
    previous_date = previous_week.strftime("%Y%m%d")

    # S3から先週データを取得
    s3_key = f"corporate_bias_datasets/integrated/{previous_date}/bias_analysis_results.json"
    return load_json_from_s3(s3_key)
```

#### 9.2.3 変化検知ロジック
```python
def detect_significant_changes(current_data: Dict, previous_data: Dict) -> List[Dict]:
    """顕著な変化を検知"""
    changes = []

    for category in current_data.get("categories", {}):
        for subcategory in category.get("subcategories", {}):
            for entity in subcategory.get("entities", []):
                # 先週データから対応するエンティティを検索
                previous_entity = find_previous_entity(entity, previous_data)

                if previous_entity:
                    # 各指標の変化を計算
                    nbi_change = calculate_nbi_change(entity, previous_entity)
                    ranking_change = calculate_ranking_change(entity, previous_entity)
                    fairness_change = calculate_fairness_change(entity, previous_entity)

                    # 閾値超過をチェック
                    if abs(nbi_change) >= 20.0:
                        changes.append({
                            "type": "nbi_change",
                            "entity": entity["name"],
                            "category": category["name"],
                            "change_rate": nbi_change,
                            "threshold": 20.0
                        })

    return changes
```

### 9.3 投稿テンプレート（md記法なし）

#### 9.3.1 基本テンプレート
```
🚨【企業優遇バイアス変化検知】

📊 検知内容: NBI急激な変化
🏢 対象企業: {企業名}
📈 変化率: {変化率}%
📋 詳細: 感情スコアが大幅に{上昇/下降}

🔍 分析詳細: {URL}
#企業優遇バイアス #AI分析 #透明性
```

#### 9.3.2 ランキング変化テンプレート
```
📈【検索ランキング変化検知】

🏢 対象企業: {企業名}
📊 プラットフォーム: {Google/Perplexity}
📈 順位変化: {前回順位}位 → {現在順位}位 ({上昇/下降})
📋 詳細: 検索結果での露出度が変化

🔍 分析詳細: {URL}
#企業優遇バイアス #検索分析 #ランキング
```

#### 9.3.3 公平性スコア変化テンプレート
```
⚖️【公平性スコア変化検知】

🏢 対象企業: {企業名}
📊 スコア種別: {サービスレベル/企業レベル}公平性スコア
📈 変化率: {変化率}%
📋 詳細: 市場における公平性評価が{向上/低下}

🔍 分析詳細: {URL}
#企業優遇バイアス #公平性 #市場分析
```

### 9.4 システム構成詳細

#### 9.4.1 モジュール構成
```
src/
├── sns/
│   ├── __init__.py
│   ├── twitter_client.py          # X API連携
│   ├── bias_monitor.py            # バイアス変化監視
│   ├── content_generator.py       # 投稿コンテンツ生成
│   ├── posting_manager.py         # 投稿管理
│   ├── timeseries_db.py           # 時系列データ管理
│   └── s3_data_loader.py          # S3データ読み込み
```

#### 9.4.2 主要クラス設計
```python
class BiasMonitor:
    """バイアス変化監視クラス"""
    def __init__(self):
        self.s3_loader = S3DataLoader()
        self.change_detector = ChangeDetector()
        self.posting_manager = PostingManager()

    def monitor_changes(self, current_date: str, current_data: Dict):
        """変化を監視して投稿をトリガー"""
        # 先週データを取得
        previous_data = self.s3_loader.get_previous_week_data(current_date)

        # 変化を検知
        changes = self.change_detector.detect_changes(current_data, previous_data)

        # 投稿を実行
        for change in changes:
            self.posting_manager.post_change(change)

class S3DataLoader:
    """S3データ読み込みクラス"""
    def get_previous_week_data(self, current_date: str) -> Dict:
        """先週の分析データを取得"""

    def get_historical_data(self, date: str) -> Dict:
        """指定日の分析データを取得"""

class ChangeDetector:
    """変化検知クラス"""
    def detect_changes(self, current: Dict, previous: Dict) -> List[Dict]:
        """顕著な変化を検知"""

    def calculate_change_rate(self, current: float, previous: float) -> float:
        """変化率を計算"""

class PostingManager:
    """投稿管理クラス"""
    def post_change(self, change: Dict):
        """変化を投稿"""

    def check_duplicate(self, entity: str, change_type: str) -> bool:
        """重複投稿をチェック"""
```

### 9.5 設定ファイル

#### 9.5.1 監視設定
```yaml
# config/sns_monitoring_config.yml
sns_monitoring:
  # 監視対象指標の閾値
  thresholds:
    nbi_change: 20.0          # NBI変化率閾値（%）
    ranking_change: 3         # ランキング変化閾値（位）
    fairness_score_change: 15.0  # 公平性スコア変化率閾値（%）

  # 統計的有意性閾値
  statistical_thresholds:
    p_value: 0.05            # p値閾値
    cliffs_delta: 0.33       # Cliff's Delta閾値
    rbo_threshold: 0.7       # RBO閾値
    kendall_tau_threshold: 0.5  # Kendall Tau閾値

  # 投稿制御設定
  posting_control:
    max_daily_posts: 10      # 1日最大投稿数
    duplicate_prevention_hours: 24  # 重複防止時間（時間）
    posting_time_range:
      start: "09:00"         # 投稿開始時間
      end: "21:00"           # 投稿終了時間

  # S3設定
  s3:
    bucket_name: "your-bucket-name"
    base_path: "corporate_bias_datasets/integrated"
    fallback_days: 3         # データが見つからない場合の遡及日数
```

### 9.6 実装スケジュール（詳細版）

#### 9.6.1 Week 1: S3データ読み込み基盤
- S3DataLoaderクラスの実装
- 先週データ取得機能
- フォールバック機能

#### 9.6.2 Week 2: 変化検知機能
- ChangeDetectorクラスの実装
- 各指標の変化率計算
- 閾値判定機能

#### 9.6.3 Week 3: X API連携
- TwitterClientクラスの実装
- 投稿機能
- 認証・エラーハンドリング

#### 9.6.4 Week 4: 統合・テスト
- BiasMonitorクラスの統合
- エンドツーエンドテスト
- パフォーマンス最適化

---

**作成日**: 2025年1月27日
**更新日**: 2025年1月27日（詳細設計仕様追加）