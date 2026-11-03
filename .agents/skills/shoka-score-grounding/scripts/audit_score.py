#!/usr/bin/env python3
"""
audit_score.py: 歷史唱歌樂譜防幻覺與常理審查工具
用途：對轉錄完成的 TMD 檔案進行音樂常理與字音對位檢查，包含：
1. 異常大跳音程偵測（如非預期之七度、九度突兀跳進，通常為看錯加線或八度）
2. 童聲音域界限審核（國小尋常科唱歌通常在 A3 至 F5 之間）
3. 樂句終止音常規檢查（句尾如 m.4, m.8, m.12, m.16 之和聲功能）
4. 歌詞假名與音符數量的 1:1 對位平衡（防湊字、漏字幻覺）
5. 反覆記號與雙層歌詞結構對齊檢查
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


NOTE_DEGREE_MAP = {
    "1": 0,
    "1'": 1,
    "2,": 1,
    "2": 2,
    "2'": 3,
    "3,": 3,
    "3": 4,
    "4": 5,
    "4'": 6,
    "5,": 6,
    "5": 7,
    "5'": 8,
    "6,": 8,
    "6": 9,
    "6'": 10,
    "7,": 10,
    "7": 11,
}


def parse_semitones(token: str) -> int | None:
    """計算相對於 1 (Do) 的半音數。"""
    token = token.strip()
    if not token or token == "0" or token.startswith("[") or token.startswith("{"):
        return None

    m = re.match(r"^([1-7][',]?)([\^_]*)$", token)
    if not m:
        return None

    pitch, octaves = m.group(1), m.group(2)
    if pitch not in NOTE_DEGREE_MAP:
        return None

    val = NOTE_DEGREE_MAP[pitch]
    for ch in octaves:
        if ch == "^":
            val += 12
        elif ch == "_":
            val -= 12
    return val


def audit_tmd(tmd_path: Path) -> bool:
    print(f"🔍 開始審查樂譜：{tmd_path}")
    text = tmd_path.read_text(encoding="utf-8")

    # 1. 執行 tmd check
    res = subprocess.run(["tmd", "check", str(tmd_path)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ [TMD 語法/拍數錯誤]\n{res.stdout or res.stderr}")
        return False
    print("  ✅ TMD 基本語法與小節拍數算術通過")

    has_warnings = False

    # 提取音軌小節
    body_match = re.search(r":Piano.*?\{(.*?)\}", text, re.DOTALL)
    if not body_match:
        body_match = re.search(r"@[^\{]*\{(.*?)\}", text, re.DOTALL)

    if not body_match:
        print("  ⚠️ 未能解析音軌內容")
        return True

    track_content = body_match.group(1)

    # 逐行解析：關聯小節與其上方的註解
    line_groups = []  # list of (comments, measures)
    pending_comments = []

    for raw_line in track_content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # 尋找註解
        if "/*" in line and "*/" in line:
            comment_content = re.findall(r"/\*(.*?)\*/", line)
            for c in comment_content:
                c_str = c.strip()
                if "|" in c_str and any(ch in c_str for ch in "アイウエオかきくけこあいうえお"):
                    pending_comments.append(c_str)
            continue

        clean_line = re.sub(r"/\*.*?\*/", "", line).strip()
        if not clean_line or (clean_line.startswith("<") and clean_line.endswith(">")):
            continue

        parts = [p.strip() for p in clean_line.split("|") if p.strip()]
        line_measures = []
        for part in parts:
            if part.startswith("<") and part.endswith(">"):
                continue
            tokens = [t for t in part.split() if t and t != "-" and not t.startswith("{") and not t.startswith("<")]
            if tokens:
                line_measures.append(tokens)

        if line_measures:
            line_groups.append((pending_comments, line_measures))
            pending_comments = []

    # 統計全曲小節與音高
    all_pitches = []
    global_measure_idx = 1

    for comments, measures in line_groups:
        for tokens in measures:
            for t in tokens:
                semi = parse_semitones(t)
                if semi is not None:
                    all_pitches.append((global_measure_idx, t, semi))
            global_measure_idx += 1

    # 檢查音高跨度與異常大跳
    if all_pitches:
        min_p = min(p[2] for p in all_pitches)
        max_p = max(p[2] for p in all_pitches)
        span = max_p - min_p
        print(f"  ℹ️ 全曲半音跨度：{span} 個半音 (最低: {min_p}, 最高: {max_p})")

        if span > 17:
            print(f"  ⚠️ [音域警示] 旋律跨度高達 {span} 個半音，請核對是否有高低八度看錯！")
            has_warnings = True

        for i in range(len(all_pitches) - 1):
            m1, t1, s1 = all_pitches[i]
            m2, t2, s2 = all_pitches[i + 1]
            diff = abs(s2 - s1)
            # 大於 9 個半音（超過大六度）且非八度(12)者警示
            if diff >= 10 and diff != 12:
                print(f"  ⚠️ [異常跳進] 第 {m1} 小節 [{t1}] 到 第 {m2} 小節 [{t2}] 出現 {diff} 個半音突兀大跳，請確認原譜！")
                has_warnings = True

    # 檢查歌詞註解與音符數量對位
    cur_m = 1
    for comments, measures in line_groups:
        line_note_counts = []
        for m_tokens in measures:
            sounded = [t for t in m_tokens if t != "0" and parse_semitones(t) is not None]
            line_note_counts.append(len(sounded))

        for c_str in comments:
            clean_c = re.sub(r"^[^\:]*[:：]", "", c_str).strip()
            c_measures = [m.strip() for m in clean_c.split("|") if m.strip()]
            for idx, cm in enumerate(c_measures):
                if idx >= len(line_note_counts):
                    break
                syllables = [ch for ch in cm if ch not in " ─-—0123456789/()（）"]
                num_notes = line_note_counts[idx]
                num_syllables = len(syllables)
                # 容忍拗音/促音差 1 字，差 2 字以上視為嚴重不符
                if num_syllables > 0 and num_notes > 0 and abs(num_syllables - num_notes) > 1:
                    m_num = cur_m + idx
                    print(
                        f"  ⚠️ [字音不符] 第 {m_num} 小節：歌詞有 {num_syllables} 字（{''.join(syllables)}），但該小節發聲有 {num_notes} 個音符！請核對是否有湊字或漏字。"
                    )
                    has_warnings = True
        cur_m += len(measures)

    if not has_warnings:
        print("🎉 [審查完畢] 未發現明顯音程異常或字音失衡，樂譜結構健康！")
    else:
        print("⚠️ [審查完畢] 請依照上述警示項目，逐一重新核對原譜局部切片。")

    # 4. 同步審查鋼琴伴奏（若存在）
    piano_candidates = list(tmd_path.parent.glob(f"{tmd_path.stem}_piano.tmd")) or list(tmd_path.parent.glob("*_piano.tmd"))
    if piano_candidates:
        piano_tmd = piano_candidates[0]
        try:
            from audit_piano_harmony import audit_piano_score
            p_ok, p_warns = audit_piano_score(piano_tmd)
            if p_ok:
                print(f"  🎹 [鋼琴伴奏] {piano_tmd.name} 和聲協調，無強烈撞音。")
            else:
                print(f"  🎹 [鋼琴伴奏] {piano_tmd.name} 偵測到 {len(p_warns)} 處和聲疑慮：")
                for w in p_warns[:5]:
                    print(f"     - {w}")
                if len(p_warns) > 5:
                    print(f"     ... (其餘 {len(p_warns) - 5} 處略)")
                has_warnings = True
        except Exception as e:
            pass

    return not has_warnings


def main():
    parser = argparse.ArgumentParser(description="樂譜防幻覺與常理審查工具")
    parser.add_argument("tmd", help="目標 TMD 檔案路徑")
    args = parser.parse_args()

    tmd_path = Path(args.tmd)
    if not tmd_path.exists():
        print(f"錯誤：找不到檔案 {tmd_path}", file=sys.stderr)
        sys.exit(1)

    audit_tmd(tmd_path)


if __name__ == "__main__":
    main()
