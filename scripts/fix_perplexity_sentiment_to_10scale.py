import json
import re
import shutil
from pathlib import Path

def extract_score(text):
    """テキストから1～10点のスコアを抽出。5点満点なら2倍して10点満点に変換。"""
    if not text:
        return None
    # 例: "感情スコア: 3", "3点", "8点", "9点" など
    m = re.search(r'(\d+(?:\.\d+)?)\s*(?:点|/10|/5|[\u70b9])?', text)
    if m:
        score = float(m.group(1))
        # 1～5なら2倍、6～10はそのまま
        if 1 <= score <= 5:
            return round(score * 2, 2)
        elif 6 <= score <= 10:
            return round(score, 2)
        else:
            return None
    return None

def fix_perplexity_sentiment(json_path):
    # バックアップ
    backup_path = json_path.with_suffix('.bak.json')
    shutil.copy(json_path, backup_path)
    print(f"バックアップ作成: {backup_path}")

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    ps = data.get('perplexity_sentiment', {})
    for category, subcats in ps.items():
        for subcat, subdata in subcats.items():
            # masked
            masked_answers = subdata.get('masked_answer', [])
            masked_values = []
            for ans in masked_answers:
                score = extract_score(ans)
                masked_values.append(score if score is not None else None)
            subdata['masked_values'] = masked_values
            # entities
            entities = subdata.get('entities', {})
            for ent, entdata in entities.items():
                unmasked_answers = entdata.get('unmasked_answer', [])
                unmasked_values = []
                for ans in unmasked_answers:
                    score = extract_score(ans)
                    unmasked_values.append(score if score is not None else None)
                entdata['unmasked_values'] = unmasked_values
    # 保存
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"修正完了: {json_path}")

if __name__ == '__main__':
    # ファイルパスは必要に応じて変更
    target = Path('corporate_bias_datasets/integrated/20250714/corporate_bias_dataset.json')
    fix_perplexity_sentiment(target)