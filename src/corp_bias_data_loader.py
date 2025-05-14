#!/usr/bin/env python
# coding: utf-8

import requests
import openai
import time
import boto3
import json
import datetime

from openai import OpenAI

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

# OpenAI APIを使用した処理
openAI_result = process_categories("openai", OPENAI_API_KEY, categories)

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

# AWS認証情報を直接設定
aws_access_key = userdata.get("aws_access_key")
aws_secret_key = userdata.get("aws_secret_key")
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
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        s3_key = f"{today_date}/{file_name}"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_data,
            ContentType="application/json"
        )
        print(f"S3に保存完了: s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"エラー: {e}")

# S3バケット名と保存するファイル名を設定
s3_bucket_name = "cu-study-297596174249"  # 自分のS3バケット名を指定
s3_file_name = "openai_results.json"  # S3に保存するファイル名

# S3にアップロード
upload_to_s3(s3_bucket_name, s3_file_name, openAI_result)