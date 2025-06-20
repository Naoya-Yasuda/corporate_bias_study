#!/usr/bin/env python
# coding: utf-8

'''
テキスト処理のユーティリティ関数

URLやテキスト処理の共通機能を提供します
'''

import re
import unicodedata
from urllib.parse import urlparse

def extract_domain(url):
    '''
    URLからドメインを抽出（www.を除去）

    Parameters:
    -----------
    url : str
        対象URL

    Returns:
    --------
    str
        抽出されたドメイン
    '''
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except:
        return ""

def is_negative(title, snippet):
    """タイトルとスニペットからネガティブコンテンツかを判定"""
    # ネガティブキーワードリスト（簡易版）
    negative_keywords = [
        "問題", "障害", "失敗", "リスク", "欠陥", "批判", "炎上", "トラブル",
        "不具合", "バグ", "遅延", "停止", "故障", "危険", "脆弱性", "違反",
        "disadvantage", "problem", "issue", "bug", "risk", "fail", "error",
        "vulnerability", "outage", "down", "criticism", "negative", "trouble"
    ]

    combined_text = (title + " " + snippet).lower()

    for keyword in negative_keywords:
        if keyword in combined_text:
            return True

    return False

def ratio(lst, pred_func):
    '''
    リストに対して述語関数を適用し、True の割合を返す

    Parameters:
    -----------
    lst : list
        対象リスト
    pred_func : callable
        適用する述語関数

    Returns:
    --------
    float
        True の割合
    '''
    if not lst:
        return 0
    return sum(1 for x in lst if pred_func(x)) / len(lst)

def extract_companies_from_text(text, companies):
    '''
    テキストから企業名を抽出

    Parameters:
    -----------
    text : str
        対象テキスト
    companies : list
        抽出する企業名リスト

    Returns:
    --------
    list
        テキスト内に見つかった企業名のリスト
    '''
    found_companies = []
    for company in companies:
        # 企業名の前後に単語境界があるかを確認するための正規表現
        pattern = r'(?<!\w)' + re.escape(company) + r'(?!\w)'
        if re.search(pattern, text, re.IGNORECASE):
            found_companies.append(company)
    return found_companies

def extract_ranking_and_reasons(text, original_services=None):
    """
    Perplexity等のAI回答からランキングと理由を正確に抽出
    - 多様なパターンに対応（マークダウン、見出し記法等）
    - サービス名の正規化とマッチング強化
    - デバッグ情報の詳細化
    - original_servicesリストとの厳密な照合
    """
    def normalize_service_name(s):
        """サービス名を正規化（全角→半角、空白除去、小文字化）"""
        s = unicodedata.normalize('NFKC', s)
        s = s.replace(' ', '').replace('　', '').strip()
        return s.lower()

    def find_matching_service(extracted_name, original_services):
        """抽出されたサービス名をoriginal_servicesと照合"""
        if not original_services:
            return extracted_name.strip()

        normalized_extracted = normalize_service_name(extracted_name)

        # 完全一致を最優先
        for service in original_services:
            if normalize_service_name(service) == normalized_extracted:
                return service

        # 部分一致（抽出名が正式名に含まれる）
        for service in original_services:
            normalized_service = normalize_service_name(service)
            if normalized_extracted in normalized_service or normalized_service in normalized_extracted:
                return service

        # マッチしない場合はNone
        return None

    def clean_service_name(name):
        """サービス名から不要な記号を除去"""
        # マークダウン記法を除去
        name = re.sub(r'\*\*([^*]+)\*\*', r'\1', name)  # **text** -> text
        name = re.sub(r'\*([^*]+)\*', r'\1', name)      # *text* -> text
        name = re.sub(r'#+\s*(.+)', r'\1', name)        # # text -> text

        # 前後の空白と句読点を除去
        name = name.strip().strip('.,。、')
        return name

    # 改良されたパターンリスト（prompt_config.ymlから取得）
    from ..prompts.prompt_manager import PromptManager
    prompt_manager = PromptManager()
    patterns = prompt_manager.get_rank_patterns()

    lines = text.splitlines()
    rankings = []
    reasons = []
    matched_lines = []
    unmatched_lines = []
    debug_info = []

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        matched = False

        for pattern_idx, pattern in enumerate(patterns):
            try:
                match = re.match(pattern, line)
                if match:
                    rank = int(match.group(1))
                    raw_service = match.group(2).strip()
                    reason = match.group(3).strip() if len(match.groups()) >= 3 else ""

                    # サービス名をクリーンアップ
                    cleaned_service = clean_service_name(raw_service)

                    # original_servicesと照合
                    matched_service = find_matching_service(cleaned_service, original_services)

                    if matched_service:
                        # 重複チェック
                        if matched_service not in [r[0] for r in rankings]:
                            rankings.append((matched_service, rank))
                            reasons.append(reason)
                            matched_lines.append(f"行{i}: {line}")
                            debug_info.append(f"✓ パターン{pattern_idx+1}でマッチ: '{raw_service}' -> '{matched_service}'")
                        else:
                            debug_info.append(f"⚠️ 重複スキップ: '{matched_service}' (行{i})")
                    else:
                        debug_info.append(f"⚠️ サービス名が未知: '{cleaned_service}' (行{i})")

                    matched = True
                    break

            except Exception as e:
                debug_info.append(f"❌ パターン{pattern_idx+1}でエラー (行{i}): {e}")
                continue

        if not matched and line.strip():
            # ノイズ行かどうかチェック（注意書きなど）
            noise_patterns = [
                r'^##?\s*注意',
                r'^注意[:：]',
                r'以下は.*ランキング',
                r'.*は有効なサービス名ではない',
                r'ランキングから除外',
                r'^[\-=]+$',  # 区切り線
            ]

            is_noise = any(re.search(pattern, line, re.IGNORECASE) for pattern in noise_patterns)
            if not is_noise:
                unmatched_lines.append(f"行{i}: {line}")

    # ランキングを順位でソート
    rankings.sort(key=lambda x: x[1])
    final_ranking = [service for service, _ in rankings]

    # デバッグ情報を出力
    if original_services:
        missing_services = set(original_services) - set(final_ranking)
        if missing_services:
            debug_info.append(f"⚠️ 抽出できなかったサービス: {list(missing_services)}")

        extracted_count = len(final_ranking)
        expected_count = len(original_services)
        if extracted_count != expected_count:
            debug_info.append(f"⚠️ 抽出数不一致: {extracted_count}/{expected_count}")

    # デバッグ情報の表示（詳細レベルに応じて）
    if not final_ranking:
        print("❌ ランキング抽出失敗")
        if unmatched_lines:
            print("未マッチ行:")
            for line in unmatched_lines[:5]:  # 最初の5行のみ表示
                print(f"  {line}")
        if debug_info:
            print("デバッグ情報:")
            for info in debug_info[-3:]:  # 最後の3つのみ表示
                print(f"  {info}")
    elif len(final_ranking) < len(original_services or []):
        print(f"⚠️ 部分抽出: {len(final_ranking)}/{len(original_services or [])}件")
        for info in debug_info[-2:]:  # 最後の2つのデバッグ情報を表示
            print(f"  {info}")

    return final_ranking, reasons

def is_official_domain(domain: str, company: str, companies_dict: dict) -> str:
    """
    指定ドメインが公式サイトかどうか判定する関数
    - domain: 判定対象（例 'blog.example.com'）
    - company: 企業名（例 'AWS'）
    - companies_dict: 企業名と公式ドメインのリストの辞書
    戻り値: 'official' / 'unofficial' / 'n/a'
    """
    if not domain or not company or not companies_dict:
        return "n/a"

    # ドメインの正規化
    domain = domain.lower().rstrip('.')  # 末尾ピリオドが付くケース対策

    # 企業名の正規化（小文字化、スペース除去）
    company = company.lower().replace(' ', '')

    # 全公式ドメインを収集して正規化
    official_domains = []
    for domains in companies_dict.values():
        official_domains.extend([od.lower().rstrip('.') for od in domains])

    # 企業名を含むドメインのパターン
    company_patterns = [
        company,                    # 完全一致
        company.replace('+', ''),   # '+'を除去
        company.replace('-', ''),   # '-'を除去
        company.replace('.', ''),   # '.'を除去
    ]

    # 判定ロジック
    for official_domain in official_domains:
        # ① 完全一致
        if domain == official_domain:
            return "official"

        # ② サブドメイン判定
        if domain.endswith("." + official_domain):
            # サブドメインの部分を取得
            subdomain = domain[:-len(official_domain)-1]

            # 一般的なサブドメインを許可
            allowed_subdomains = [
                'www', 'blog', 'docs', 'help', 'support', 'developer',
                'developers', 'api', 'status', 'community', 'forum',
                'news', 'media', 'press', 'about', 'jobs', 'careers'
            ]

            # 許可されたサブドメインまたは企業名を含む場合は公式と判定
            if subdomain in allowed_subdomains or any(pattern in subdomain for pattern in company_patterns):
                return "official"

            # その他のサブドメインは非公式と判定
            return "unofficial"

    # ③ 企業名を含むドメインの判定
    if any(pattern in domain for pattern in company_patterns):
        # 企業名を含むが、公式ドメインリストにない場合は非公式と判定
        return "unofficial"

    # ④ その他のドメインは非公式と判定
    return "unofficial"
