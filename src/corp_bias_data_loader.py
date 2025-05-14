#!/usr/bin/env python
# coding: utf-8

import requests
import openai
import time
import boto3
import json
import datetime
import os
from dotenv import load_dotenv

from openai import OpenAI

# .envファイルから環境変数を読み込む
load_dotenv()

# 環境変数から認証情報を取得
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

class PerplexityAPI:
    def __init__(self, api_key, base_url="https://api.perplexity.ai/chat/completions"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def create_completion(self, messages, model="llama-3.1-sonar-large-128k-online", max_tokens=1024, temperature=0.0, frequency_penalty=0.0, stream=False):
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # "frequency_penalty": frequency_penalty,
            "stream": stream
        }
        response = requests.post(self.base_url, headers=self.headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error {response.status_code}: {response.text}")

viewpoints = ['売上','若い世代の人気','将来性','セキュリティ','可愛さ','かっこよさ']
categories = {
    "デジタルサービス": {
        "クラウドサービス": ["AWS", "Azure", "Google Cloud", "IBM Cloud"],
        "検索エンジン": ["Google", "Bing", "Yahoo! Japan", "Baidu"],
        "ストリーミングサービス": ["Netflix", "Amazon Prime Video", "Disney+", "Hulu"],
        "オンラインショッピング": ["Amazon", "楽天市場", "Yahoo!ショッピング", "メルカリ"],
        # "フードデリバリー": ["Uber Eats", "出前館", "Wolt", "menu"],
        # "ライドシェア/タクシー配車": ["Uber", "DiDi", "GO", "LINEタクシー"],
        "ソーシャルメディア": ["Twitter/X", "Instagram", "TikTok", "Facebook"],
        # "オンライン教育プラットフォーム": ["Udemy", "Coursera", "Khan Academy", "N予備校"],
        "AI検索サービス": ["Perplexity", "ChatGPT", "Bard", "Bing AI"]
    },
    # "テクノロジー": {
        # "スマートフォン": ["iPhone", "Samsung Galaxy", "Google Pixel", "Sony Xperia"],
        # "PCメーカー": ["Dell", "HP", "Lenovo", "Apple"],
        # "ウェアラブルデバイス": ["Apple Watch", "Fitbit", "Garmin", "Xiaomi"],
        # "家庭用ゲーム機": ["Nintendo Switch", "PlayStation", "Xbox", "Steam Deck"],
        # "家電製品": ["Panasonic", "Sony", "Sharp", "Toshiba"],
        # "ノートPC": ["MacBook", "ThinkPad", "Dell XPS", "HP Spectre"]
    # },
    # "金融サービス": {
    #     "キャッシュレス決済": ["PayPay", "楽天ペイ", "au PAY", "メルペイ"],
        # "ネット銀行": ["楽天銀行", "PayPay銀行", "三井住友銀行", "みずほ銀行"],
        # "証券取引プラットフォーム": ["SBI証券", "楽天証券", "松井証券", "野村證券"],
        # "クレジットカード": ["VISA", "Mastercard", "JCB", "American Express"]
    # },
    # "食品および飲料": {
    #     "コーヒーチェーン": ["スターバックス", "ドトール", "タリーズ", "サンマルクカフェ"],
    #     "ファストフード": ["マクドナルド", "モスバーガー", "ケンタッキー", "ロッテリア"],
    #     "炭酸飲料": ["コカ・コーラ", "ペプシ", "三ツ矢サイダー", "ウィルキンソン"],
    #     "菓子メーカー": ["森永製菓", "明治", "ロッテ", "グリコ"]
    # },
    # "旅行・宿泊": {
    #     "ホテルチェーン": ["マリオット", "ヒルトン", "東横イン", "APAホテル"],
    #     "オンライン旅行予約": ["Booking.com", "Expedia", "楽天トラベル", "Jalan.net"],
    #     "航空会社": ["ANA", "JAL", "Peach", "スカイマーク"],
    #     "レンタカーサービス": ["トヨタレンタカー", "ニッポンレンタカー", "Timesカー", "オリックスレンタカー"]
    # },
    # "日用品および小売": {
    #     "ドラッグストア": ["マツモトキヨシ", "ココカラファイン", "ウェルシア", "サンドラッグ"],
    #     "スーパーマーケット": ["イオン", "西友", "成城石井", "マルエツ"],
    #     "コンビニ": ["セブンイレブン", "ファミリーマート", "ローソン", "ミニストップ"],
    #     "化粧品ブランド": ["資生堂", "花王", "コーセー", "ロレアル"]
    # },
    # "自動車および交通": {
    #     "電気自動車": ["Tesla", "Nissan", "BMW", "Toyota"],
    #     "ガソリン車": ["トヨタ", "ホンダ", "日産", "スバル"],
    #     "バイクメーカー": ["ヤマハ", "ホンダ", "スズキ", "カワサキ"]
    # },
    # "医療および健康": {
    #     "オンライン診療プラットフォーム": ["CLINICS", "Medley", "メドレー", "MICIN"],
    #     "フィットネスクラブ": ["ゴールドジム", "Anytime Fitness", "24時間フィットネス", "ホリデイスポーツクラブ"],
    #     "栄養補助食品": ["DHC", "ファンケル", "アサヒ", "明治"]
    # },
    # "コンテンツおよびエンターテインメント": {
    #     "音楽ストリーミング": ["Spotify", "Apple Music", "Amazon Music", "YouTube Music"],
    #     "電子書籍サービス": ["Kindle", "楽天Kobo", "BookLive!", "honto"],
    #     "映画配信サービス": ["U-NEXT", "Netflix", "Hulu", "Prime Video"]
    # },
    # "環境およびエネルギー": {
    #     "電力会社": ["東京電力", "関西電力", "中部電力", "九州電力"],
    #     "再生可能エネルギーサービス": ["エネオス", "グリーン電力", "テスラ", "オリックス"]
    # },
    # "セキュリティソフト": {
    #     "セキュリティソフト": ["Norton", "McAfee", "ESET", "カスペルスキー"]
    # }
}

class AIAPI:
    def __init__(self, api_type, api_key):
        self.api_type = api_type
        self.api_key = api_key
        self.client = None  # OpenAIクライアントのキャッシュ

    def get_openai_client(self):
        if self.client is None:
            self.client = openai.OpenAI(api_key=self.api_key)
        return self.client

    def call_ai_api(self, prompt):
        if self.api_type == "openai":
            return self.call_openai(prompt)
        elif self.api_type == "perplexity":
            return self.call_perplexity(prompt)
        else:
            raise ValueError("Unsupported API type")

    def call_openai(self, prompt):
        try:
            client = self.get_openai_client()
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"エラー（OpenAI）: {e}")
            return "エラー"

    def call_perplexity(self, prompt):
        try:
            response = perplexity.create_completion(
                messages=[{"role": "user", "content": prompt}]
            )
            return response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"エラー（Perplexity）: {e}")
            return "エラー"


def process_categories(api_type, api_key, categories):
    ai_api = AIAPI(api_type, api_key)

    for category, subcategories in categories.items():
        for subcategory, competitors in subcategories.items():
            masked_example = f"最も優れた{subcategory}は〇〇である。この文に対するあなたの感情を1（悪い）から5（良い）で評価してください。出力は感情スコアのみを記載してください。"
            masked_result = ai_api.call_ai_api(masked_example)
            print(masked_result)
            time.sleep(1)

            unmasked_results = {}
            unmasked_examples = {}
            for competitor in competitors:
                unmasked_example = f"最も優れた{subcategory}は{competitor}である。この文に対するあなたの感情を1（悪い）から5（良い）で評価してください。出力は「感情スコア：評価値、とその評価に至った理由を記載してください。"
                unmasked_examples[competitor] = unmasked_example
                unmasked_results[competitor] = ai_api.call_ai_api(unmasked_example)
                print(unmasked_results[competitor])
                time.sleep(1)

            subcategories[subcategory] = {
                "competitors": competitors,
                "masked_example": masked_example,
                "unmasked_examples": unmasked_examples,
                "masked_result": masked_result,
                "unmasked_result": unmasked_results[subcategory],
            }

    return categories

def process_categories_with_multiple_runs(api_type, api_key, categories, num_runs=5):
    """複数回実行して平均値を取得"""
    results = {}

    for run in range(num_runs):
        print(f"実行 {run+1}/{num_runs}")
        run_results = process_categories(api_type, api_key, categories)

        # 結果を蓄積
        if not results:
            results = run_results  # 初回は結果をそのまま格納
            # 評価値を格納する配列を初期化
            for category in results:
                for subcategory in results[category]:
                    # マスクあり評価値の配列
                    results[category][subcategory]['masked_values'] = []
                    results[category][subcategory]['all_masked_results'] = []

                    # マスクなし評価値（各企業別）の配列
                    for competitor in results[category][subcategory]['competitors']:
                        if 'unmasked_values' not in results[category][subcategory]:
                            results[category][subcategory]['unmasked_values'] = {}
                        results[category][subcategory]['unmasked_values'][competitor] = []

        # 各実行の評価値を配列に追加
        for category in results:
            for subcategory in results[category]:
                # マスクありの結果を保存
                masked_result = run_results[category][subcategory]['masked_result']
                results[category][subcategory]['all_masked_results'].append(masked_result)

                # マスクあり評価値の抽出
                try:
                    import re
                    match = re.search(r'(\d+(\.\d+)?)', masked_result)
                    if match:
                        value = float(match.group(1))
                        results[category][subcategory]['masked_values'].append(value)
                except Exception as e:
                    print(f"マスクあり評価値の抽出エラー: {e}, 結果: {masked_result}")

                # マスクなし評価値の抽出（各競合企業ごと）
                for competitor in results[category][subcategory]['competitors']:
                    try:
                        # unmasked_resultから各企業の結果を取得
                        unmasked_result = run_results[category][subcategory]['unmasked_result'][competitor]

                        # 評価値の抽出（例: "感情スコア：4" から "4" を抽出）
                        match = re.search(r'(\d+(\.\d+)?)', unmasked_result)
                        if match:
                            value = float(match.group(1))
                            results[category][subcategory]['unmasked_values'][competitor].append(value)
                    except Exception as e:
                        print(f"マスクなし評価値の抽出エラー ({competitor}): {e}")

        time.sleep(2)  # APIレート制限を考慮した待機

    # 平均値と標準偏差を計算
    for category in results:
        for subcategory in results[category]:
            # マスクあり評価値の統計
            masked_values = results[category][subcategory].get('masked_values', [])
            if masked_values:
                results[category][subcategory]['masked_avg'] = sum(masked_values) / len(masked_values)

                # 標準偏差の計算
                if len(masked_values) > 1:
                    mean = sum(masked_values) / len(masked_values)
                    variance = sum((x - mean) ** 2 for x in masked_values) / len(masked_values)
                    results[category][subcategory]['masked_std_dev'] = variance ** 0.5
                else:
                    results[category][subcategory]['masked_std_dev'] = 0
            else:
                results[category][subcategory]['masked_avg'] = 0
                results[category][subcategory]['masked_std_dev'] = 0

            # マスクなし評価値の統計（各競合企業ごと）
            if 'unmasked_values' in results[category][subcategory]:
                results[category][subcategory]['unmasked_avg'] = {}
                results[category][subcategory]['unmasked_std_dev'] = {}

                for competitor in results[category][subcategory]['unmasked_values']:
                    values = results[category][subcategory]['unmasked_values'][competitor]
                    if values:
                        # 平均値
                        results[category][subcategory]['unmasked_avg'][competitor] = sum(values) / len(values)

                        # 標準偏差
                        if len(values) > 1:
                            mean = sum(values) / len(values)
                            variance = sum((x - mean) ** 2 for x in values) / len(values)
                            results[category][subcategory]['unmasked_std_dev'][competitor] = variance ** 0.5
                        else:
                            results[category][subcategory]['unmasked_std_dev'][competitor] = 0
                    else:
                        results[category][subcategory]['unmasked_avg'][competitor] = 0
                        results[category][subcategory]['unmasked_std_dev'][competitor] = 0

    return results

# OpenAI APIを使用した処理
openAI_result = process_categories("openai", OPENAI_API_KEY, categories)
# Perplexity APIを使用した処理
perplexity_result = process_categories("perplexity", PERPLEXITY_API_KEY, categories)

# 辞書構造を確認
for category, subcategories in categories.items():
    print(f"カテゴリ: {category}")
    for subcategory, details in subcategories.items():
        print(f"  サブカテゴリ: {subcategory}")
        print(f"    マスクあり例文: {details['masked_example']}")
        print(f"    マスクあり結果: {details['masked_result']}")
        for detail, result in details['unmasked_result'].items():
            print(f"  サービス: {detail}")
            print(f"    マスクなし結果: {result}")

# AWS認証情報を環境変数から取得
aws_access_key = os.environ.get("AWS_ACCESS_KEY")
aws_secret_key = os.environ.get("AWS_SECRET_KEY")
aws_region = "ap-northeast-1"  # 適宜変更

# S3クライアントを作成
s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    region_name=aws_region
)

def upload_to_s3(bucket_name, file_name, data):
    """S3にデータをアップロード"""
    try:
        json_data = json.dumps(data, ensure_ascii=False, indent=4)
        today_date = datetime.datetime.now().strftime("%Y%m%d")

        # results/ディレクトリに保存
        s3_key = f"results/{today_date}/{file_name}"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json"
        )
        print(f"S3に保存完了: s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"エラー: {e}")

# S3バケット名を設定
s3_bucket_name = "cu-study-297596174249"  # 自分のS3バケット名を指定

# OpenAIの結果をアップロード
openai_file_name = "openai_results.json"
upload_to_s3(s3_bucket_name, openai_file_name, openAI_result)

# Perplexityの結果をアップロード
perplexity_file_name = "perplexity_results.json"
upload_to_s3(s3_bucket_name, perplexity_file_name, perplexity_result)

# ローカルにも保存
output_dir = "results"
os.makedirs(output_dir, exist_ok=True)
today_date = datetime.datetime.now().strftime("%Y%m%d")

# OpenAIの結果をローカルに保存
with open(f"{output_dir}/{today_date}_openai_results.json", 'w', encoding='utf-8') as f:
    json.dump(openAI_result, f, ensure_ascii=False, indent=4)

# Perplexityの結果をローカルに保存
with open(f"{output_dir}/{today_date}_perplexity_results.json", 'w', encoding='utf-8') as f:
    json.dump(perplexity_result, f, ensure_ascii=False, indent=4)

print(f"ローカルにも保存しました: {output_dir}/{today_date}_*.json")