#!/usr/bin/env python3
"""
將 docs/kyoyusho_shoka_1935/**/_piano.tmd 伴奏譜歌詞行中的歷史假名遣與殘留漢字轉為現代發音假名。
僅針對伴奏譜（NEUTRINO 合成演唱版），絕對不更動原始單軌文獻轉錄版本。
同時確保小節線、換行、縮排等排版格式完整保持。
"""

import glob
import re
from pathlib import Path

CHAR_MAP = {
    'ゐ': 'い', 'ヰ': 'イ',
    'ゑ': 'え', 'ヱ': 'エ',
    'ぢ': 'じ', 'ヂ': 'ジ',
    'づ': 'ず', 'ヅ': 'ズ',
}

def modernize_text(text: str) -> str:
    # 0. 殘留漢字替換（確保純假名）
    text = re.sub(r'オ(\s*(-|\s)*\s*)日(\s*(-|\s)*\s*)サ', r'オ\1ヒ\3サ', text)
    text = re.sub(r'お(\s*(-|\s)*\s*)日(\s*(-|\s)*\s*)さ', r'お\1ひ\3さ', text)
    text = text.replace('日 - - - - - ノ', 'ヒ - - - - - ノ')
    text = text.replace('日 - - - - - は', 'ひ - - - - - わ')
    text = text.replace('身 - - - - - ニ', 'ミ - - - - - ニ')
    text = text.replace('血 - - - - - ハ', 'チ - - - - - ハ')

    # 1. 詞彙級別的正則替換（處理帶延音線或空格的文字）
    # こゑ / コヱ (こえ)
    text = re.sub(r'こ(\s*(-|\s)*\s*)ゑ', r'こ\1え', text)
    text = re.sub(r'コ(\s*(-|\s)*\s*)ヱ', r'コ\1エ', text)

    # かへる、かへり、かへす、かへし、かへら、かへろ、かへて
    text = re.sub(r'か(\s*(-|\s)*\s*)へ(\s*(-|\s)*\s*[るりすしれらろて])', r'か\1え\3', text)
    text = re.sub(r'カ(\s*(-|\s)*\s*)ヘ(\s*(-|\s)*\s*[ルリスシレラロテ])', r'カ\1エ\3', text)

    # まへ / マヘ (まえ)
    text = re.sub(r'ま(\s*(-|\s)*\s*)へ', r'ま\1え', text)
    text = re.sub(r'マ(\s*(-|\s)*\s*)ヘ', r'マ\1エ', text)

    # うへ / ウヘ (うえ)
    text = re.sub(r'う(\s*(-|\s)*\s*)へ', r'う\1え', text)
    text = re.sub(r'ウ(\s*(-|\s)*\s*)ヘ', r'ウ\1エ', text)

    # ゆふ (ゆうべ、夕焼け、夕日、夕暮れ)
    text = re.sub(r'ゆ(\s*(-|\s)*\s*)ふ(\s*(-|\s)*\s*[べやけひぐら])', r'ゆ\1う\3', text)
    text = re.sub(r'ユ(\s*(-|\s)*\s*)フ(\s*(-|\s)*\s*[ベヤケヒグラ])', r'ユ\1ウ\3', text)

    # けふ / ケフ (きょう)
    text = re.sub(r'け(\s*(-|\s)*\s*)ふ', r'きょ\1う', text)
    text = re.sub(r'ケ(\s*(-|\s)*\s*)フ', r'キョ\1ウ', text)

    # おもひ / オモヒ (おもい)
    text = re.sub(r'お(\s*(-|\s)*\s*)も(\s*(-|\s)*\s*)ひ', r'お\1も\3い', text)
    text = re.sub(r'オ(\s*(-|\s)*\s*)モ(\s*(-|\s)*\s*)ヒ', r'オ\1モ\3イ', text)

    # あふぎ / アフギ (おうぎ)
    text = re.sub(r'あ(\s*(-|\s)*\s*)ふ(\s*(-|\s)*\s*)ぎ', r'お\1う\3ぎ', text)
    text = re.sub(r'ア(\s*(-|\s)*\s*)フ(\s*(-|\s)*\s*)ギ', r'オ\1ウ\3ギ', text)

    # あふぐ / アフグ (おおぐ)
    text = re.sub(r'あ(\s*(-|\s)*\s*)ふ(\s*(-|\s)*\s*)ぐ', r'あ\1お\3ぐ', text)
    text = re.sub(r'ア(\s*(-|\s)*\s*)フ(\s*(-|\s)*\s*)グ', r'ア\1オ\3グ', text)

    # おほ / オホ (おお)
    text = re.sub(r'お(\s*(-|\s)*\s*)ほ(\s*(-|\s)*\s*[みきぞさ])', r'お\1お\3', text)
    text = re.sub(r'オ(\s*(-|\s)*\s*)ホ(\s*(-|\s)*\s*[ミキゾサ])', r'オ\1オ\3', text)

    # とほ / トホ (とお)
    text = re.sub(r'と(\s*(-|\s)*\s*)ほ(\s*(-|\s)*\s*[くき])', r'と\1お\3', text)
    text = re.sub(r'ト(\s*(-|\s)*\s*)ホ(\s*(-|\s)*\s*[クキ])', r'ト\1オ\3', text)

    # なほ / ナホ (なお)
    text = re.sub(r'な(\s*(-|\s)*\s*)ほ(\s*(-|\s)*\s*[ひみさ])', r'な\1お\3', text)
    text = re.sub(r'ナ(\s*(-|\s)*\s*)ホ(\s*(-|\s)*\s*[ヒミサ])', r'ナ\1オ\3', text)

    # うたへ / ウタヘ (うたえ)
    text = re.sub(r'う(\s*(-|\s)*\s*)た(\s*(-|\s)*\s*)へ', r'う\1た\3え', text)
    text = re.sub(r'ウ(\s*(-|\s)*\s*)タ(\s*(-|\s)*\s*)ヘ', r'ウ\1タ\3エ', text)

    # たぐひ / タグヒ (たぐい)
    text = re.sub(r'た(\s*(-|\s)*\s*)ぐ(\s*(-|\s)*\s*)ひ', r'た\1ぐ\3い', text)
    text = re.sub(r'タ(\s*(-|\s)*\s*)グ(\s*(-|\s)*\s*)ヒ', r'タ\1グ\3イ', text)

    # もとゐ / モトヰ (もとい)
    text = re.sub(r'も(\s*(-|\s)*\s*)と(\s*(-|\s)*\s*)ゐ', r'も\1と\3い', text)
    text = re.sub(r'モ(\s*(-|\s)*\s*)ト(\s*(-|\s)*\s*)ヰ', r'モ\1ト\3イ', text)

    # にほひ / ニホヒ (におい)
    text = re.sub(r'に(\s*(-|\s)*\s*)ほ(\s*(-|\s)*\s*)ひ', r'に\1お\3い', text)
    text = re.sub(r'ニ(\s*(-|\s)*\s*)ホ(\s*(-|\s)*\s*)ヒ', r'ニ\1オ\3イ', text)

    # はらひ / ハラヒ (はらい)
    text = re.sub(r'は(\s*(-|\s)*\s*)ら(\s*(-|\s)*\s*)ひ', r'は\1ら\3い', text)
    text = re.sub(r'ハ(\s*(-|\s)*\s*)ラ(\s*(-|\s)*\s*)ヒ', r'ハ\1ラ\3イ', text)

    # にはお / にはとり
    text = re.sub(r'に(\s*(-|\s)*\s*)は(\s*(-|\s)*\s*)と(\s*(-|\s)*\s*)り', r'に\1わ\3と\5り', text)
    text = re.sub(r'ニ(\s*(-|\s)*\s*)ハ(\s*(-|\s)*\s*)ト(\s*(-|\s)*\s*)リ', r'ニ\1ワ\3ト\5リ', text)

    # けぶり / ケブリ (けむり)
    text = re.sub(r'け(\s*(-|\s)*\s*)ぶ(\s*(-|\s)*\s*)り', r'け\1む\3り', text)
    text = re.sub(r'ケ(\s*(-|\s)*\s*)ブ(\s*(-|\s)*\s*)リ', r'ケ\1ム\3リ', text)

    # ユークワイ / クワイ (カイ)
    text = re.sub(r'クワ(\s*(-|\s)*\s*)イ', r'カ\1イ', text)
    text = re.sub(r'くわ(\s*(-|\s)*\s*)い', r'か\1い', text)

    # 2. 單字映射 (ゐ, ゑ, ぢ, づ, ヰ, ヱ, ヂ, ヅ)
    for k, v in CHAR_MAP.items():
        text = text.replace(k, v)

    return text

def process_file(file_path: Path) -> bool:
    content = file_path.read_text(encoding='utf-8')
    orig_content = content

    # 1. 先修復先前可能被意外串連在一行的多重 L2|, L3|
    # 如果同一行中出現 `|    L2|`，換行拆開
    content = re.sub(r'\|\s+(L\d+\|)', r'|\n    \1', content)
    # 修復被黏在小節線後方的 `}`
    content = re.sub(r'\|\s*\}', '|\n}', content)

    # 2. 逐行處理歌詞
    lines = content.splitlines()
    new_lines = []

    for line in lines:
        line = line.rstrip()
        m = re.match(r'^(\s*L\d+\|)(.*)$', line)
        if m:
            prefix = m.group(1)
            raw_lyrics = m.group(2)
            mod_lyrics = modernize_text(raw_lyrics)
            new_lines.append(prefix + mod_lyrics)
        else:
            new_lines.append(line)

    # 移除連續多餘空行
    res_text = '\n'.join(new_lines) + '\n'
    res_text = re.sub(r'\n{3,}', '\n\n', res_text)

    # 如果有在音符行與 L1| 之間被插入多餘空行，清理它
    res_text = re.sub(r'(\|\s*\n)\s*\n(\s*L1\|)', r'\1\2', res_text)

    if res_text != orig_content:
        file_path.write_text(res_text, encoding='utf-8')
        return True
    return False

def main():
    root = Path('docs/kyoyusho_shoka_1935')
    files = sorted(root.glob('**/*_piano.tmd'))
    modified = []

    for f in files:
        if process_file(f):
            modified.append(f)

    print(f'共檢查 {len(files)} 個伴奏譜檔案，已成功更新 {len(modified)} 個檔案。')

if __name__ == '__main__':
    main()
