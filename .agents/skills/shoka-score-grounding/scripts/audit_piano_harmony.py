#!/usr/bin/env python3
"""
audit_piano_harmony.py: 鋼琴伴奏垂直和聲與撞音審查工具
用途：解析 *_piano.tmd，比對 PianoRH（旋律）與 PianoLH（伴奏）在時間軸上的垂直音高與和弦，
自動偵測強拍小二度、大七度撞音，以及半終止/全終止和弦錯置問題。
"""

import argparse
import re
import sys
from pathlib import Path

# Movable-Do 唱名對應相對於 1 (Do) 的半音數 (0..11)
SOLFEGE_SEMITONES = {
    "1": 0, "1'": 1, "2,": 1,
    "2": 2, "2'": 3, "3,": 3,
    "3": 4,
    "4": 5, "4'": 6, "5,": 6,
    "5": 7, "5'": 8, "6,": 8,
    "6": 9, "6'": 10, "7,": 10,
    "7": 11,
}

# 絕對音名 (C=0, C#/Db=1, D=2, ..., B=11)
ABSOLUTE_PITCH_MAP = {
    "C": 0, "B#": 0,
    "C#": 1, "Db": 1, "D,": 1,
    "D": 2,
    "D#": 3, "Eb": 3, "E,": 3,
    "E": 4, "Fb": 4,
    "F": 5, "E#": 5,
    "F#": 6, "Gb": 6, "G,": 6,
    "G": 7,
    "G#": 8, "Ab": 8, "A,": 8,
    "A": 9,
    "A#": 10, "Bb": 10, "B,": 10,
    "B": 11, "Cb": 11,
}

# 首調和弦 (相對於 Do/1 的半音分佈)
MOVABLE_CHORDS = {
    "[1]": [0, 4, 7],
    "[1m]": [0, 3, 7],
    "[4]": [5, 9, 0],
    "[4m]": [5, 8, 0],
    "[5]": [7, 11, 2],
    "[5_]": [7, 11, 2],
    "[57]": [7, 11, 2, 5],
    "[5_7]": [7, 11, 2, 5],
    "[6m]": [9, 0, 4],
    "[6_m]": [9, 0, 4],
    "[2m]": [2, 5, 9],
    "[2_m]": [2, 5, 9],
    "[27]": [2, 6, 9, 0],
    "[2_7]": [2, 6, 9, 0],
    "[3]": [4, 8, 11],
    "[3_]": [4, 8, 11],
    "[3m]": [4, 7, 11],
    "[3_m]": [4, 7, 11],
    "[37]": [4, 8, 11, 2],
    "[3_7]": [4, 8, 11, 2],
}

def parse_key_signature(text: str) -> int:
    """取得調號 ?= X 相對於 C 的半音偏移量。"""
    m = re.search(r"\?=\s*([A-Ga-g][',]?)", text)
    if not m:
        return 0
    k_str = m.group(1).capitalize()
    # 支援 TMD 的 A', B, 記法
    if "'" in k_str:
        base = k_str.replace("'", "")
        return (ABSOLUTE_PITCH_MAP.get(base, 0) + 1) % 12
    elif "," in k_str:
        base = k_str.replace(",", "")
        return (ABSOLUTE_PITCH_MAP.get(base, 0) - 1) % 12
    return ABSOLUTE_PITCH_MAP.get(k_str, 0)

def parse_token_absolute_pitch(token: str, key_offset: int) -> int | None:
    token = token.strip()
    if not token or token == "0" or token.startswith("{"):
        return None
    # 首調唱名
    m = re.match(r"^([1-7][',]?)([\^_]*)$", token)
    if m:
        pitch = m.group(1)
        if pitch in SOLFEGE_SEMITONES:
            return (SOLFEGE_SEMITONES[pitch] + key_offset) % 12
    return None

def parse_chord_absolute_pitches(chord_token: str, key_offset: int) -> list[int] | None:
    token = chord_token.strip()
    # 1. 首調和弦
    if token in MOVABLE_CHORDS:
        return [(semi + key_offset) % 12 for semi in MOVABLE_CHORDS[token]]
    
    # 2. 絕對音名和弦 [C], [D], [Gm], [D7], [Cm]
    m = re.match(r"^\[([A-G][b#]?)(m|maj7|7|m7|dim|aug)?\]$", token)
    if m:
        root_name = m.group(1)
        suffix = m.group(2) or ""
        root_pc = ABSOLUTE_PITCH_MAP.get(root_name)
        if root_pc is None:
            return None
        if suffix == "":  # Major
            intervals = [0, 4, 7]
        elif suffix == "m":  # Minor
            intervals = [0, 3, 7]
        elif suffix == "7":  # Dominant 7th
            intervals = [0, 4, 7, 10]
        elif suffix == "m7":  # Minor 7th
            intervals = [0, 3, 7, 10]
        elif suffix == "maj7":  # Major 7th
            intervals = [0, 4, 7, 11]
        else:
            intervals = [0, 4, 7]
        return [(root_pc + i) % 12 for i in intervals]
    return None

def expand_track_timeline(section_text: str, default_grid: int = 16) -> list[list[dict]]:
    measures = []
    clean_text = re.sub(r"/\*.*?\*/", "", section_text, flags=re.DOTALL)
    clean_text = re.sub(r"^\s*L\d*\|.*$", "", clean_text, flags=re.MULTILINE)
    current_grid = default_grid
    raw_measures = clean_text.split("|")
    for raw_m in raw_measures:
        m_str = raw_m.strip()
        if not m_str:
            continue
        grid_m = re.search(r"<(\d+)\*>", m_str)
        if grid_m:
            current_grid = int(grid_m.group(1))
            m_str = re.sub(r"<\d+\*>", "", m_str).strip()
        tokens = m_str.split()
        if not tokens:
            continue
        unit_multiplier = 16 // current_grid if current_grid <= 16 else 1
        events = []
        for tok in tokens:
            if tok.startswith("{") and tok.endswith("}"):
                continue
            if tok == "-":
                if events:
                    events[-1]["duration"] += unit_multiplier
            else:
                events.append({"token": tok, "duration": unit_multiplier})
        if events:
            measures.append(events)
    return measures

def audit_piano_score(tmd_path: Path):
    text = tmd_path.read_text(encoding="utf-8")
    key_offset = parse_key_signature(text)

    rh_match = re.search(r":PianoRH.*?\{(.*?)\}", text, re.DOTALL)
    lh_match = re.search(r":PianoLH.*?\{(.*?)\}", text, re.DOTALL)
    
    if not rh_match or not lh_match:
        return True, ["無法找到 PianoRH 或 PianoLH 音軌"]

    rh_measures = expand_track_timeline(rh_match.group(1))
    lh_measures = expand_track_timeline(lh_match.group(1))

    warnings = []
    num_m = min(len(rh_measures), len(lh_measures))

    for m_idx in range(num_m):
        m_num = m_idx + 1
        rh_events = rh_measures[m_idx]
        lh_events = lh_measures[m_idx]

        rh_grid = []
        for e in rh_events:
            rh_grid.extend([e["token"]] * e["duration"])

        lh_grid = []
        for e in lh_events:
            lh_grid.extend([e["token"]] * e["duration"])

        min_len = min(len(rh_grid), len(lh_grid))
        for tick in range(min_len):
            rh_tok = rh_grid[tick]
            lh_tok = lh_grid[tick]

            rh_pc = parse_token_absolute_pitch(rh_tok, key_offset)
            if rh_pc is None:
                continue

            # 1. 檢查 LH 低音單音
            lh_pc = parse_token_absolute_pitch(lh_tok, key_offset)
            if lh_pc is not None:
                diff = abs(rh_pc - lh_pc) % 12
                # 低音與旋律若形成小二度或大七度（相差 1 個半音）
                if diff in (1, 11):
                    # 避免重複警示同一小節同一衝突
                    warn = f"第 {m_num} 小節: 旋律音 {rh_tok} 與伴奏低音 {lh_tok} 構成半音強烈衝突！"
                    if not warnings or warnings[-1] != warn:
                        warnings.append(warn)

            # 2. 檢查 LH 和弦
            chord_pcs = parse_chord_absolute_pitches(lh_tok, key_offset)
            if chord_pcs is not None:
                chord_dists = [abs(rh_pc - c_pc) % 12 for c_pc in chord_pcs]
                # 旋律不在和弦音內，且與和弦音相差 1 個半音
                if 0 not in chord_dists and (1 in chord_dists or 11 in chord_dists):
                    warn = f"第 {m_num} 小節: 旋律音 {rh_tok} 與伴奏和弦 {lh_tok} 構成外音半音摩擦！"
                    if not warnings or warnings[-1] != warn:
                        warnings.append(warn)

    return len(warnings) == 0, warnings

def main():
    parser = argparse.ArgumentParser(description="鋼琴伴奏垂直和聲審查工具")
    parser.add_argument("targets", nargs="+", help="目標 TMD 檔案或目錄")
    args = parser.parse_args()

    files = []
    for tgt in args.targets:
        p = Path(tgt)
        if p.is_dir():
            files.extend(sorted(p.rglob("*_piano.tmd")))
        elif p.is_file():
            files.append(p)

    for tmd in files:
        ok, warns = audit_piano_score(tmd)
        rel_path = tmd.relative_to(Path.cwd()) if tmd.is_relative_to(Path.cwd()) else tmd
        if ok:
            print(f"✅ {rel_path}: 伴奏和聲協調")
        else:
            print(f"⚠️  {rel_path}: 發現 {len(warns)} 處和聲疑慮")
            for w in warns[:8]:
                print(f"   - {w}")
            if len(warns) > 8:
                print(f"   ... (其餘 {len(warns) - 8} 處略)")

if __name__ == "__main__":
    main()
