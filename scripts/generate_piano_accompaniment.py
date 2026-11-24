#!/usr/bin/env python3
"""
generate_piano_accompaniment.py:
為 docs/izawa_shogaku_shoka/ 自動產生高音質雙手鋼琴伴奏版 TMD (*_piano.tmd)。
- PianoRH 保留旋律軌與歌詞 (L1|, L2|, etc.)
- PianoLH 產生調和對稱的伴奏低音與和弦 (符合各拍號傳統風格)
- 自動執行 audit_piano_harmony 審查，確保 0 和聲衝突
- 自動執行 tmd check 驗證小節節奏與語法
"""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import re
import subprocess
import sys

# 匯入 audit_piano_harmony
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_piano_harmony import (
    ABSOLUTE_PITCH_MAP,
    MOVABLE_CHORDS,
    SOLFEGE_SEMITONES,
    audit_piano_score,
    expand_track_timeline,
    parse_chord_absolute_pitches,
    parse_key_signature,
    parse_token_absolute_pitch,
)


def parse_score_metadata(content: str) -> dict:
    meter_m = re.search(r"<(\d+/\d+)>", content)
    meter = meter_m.group(1) if meter_m else "4/4"

    key_m = re.search(r"\?=\s*([^\s\n]+)", content)
    key_sig = key_m.group(1) if key_m else "C"

    key_mode_m = re.search(r"key=\s*([^\s\n]+)", content)
    key_name = key_mode_m.group(1) if key_mode_m else ""

    is_minor = bool("m" in key_name or (key_sig.endswith("m") and key_sig != "Bm"))
    return {
        "meter": meter,
        "key_sig": key_sig,
        "key_name": key_name,
        "is_minor": is_minor,
    }


def clean_measure_tokens(bar_str: str) -> list[str]:
    """清除小節內動態標記與屬性，取得純音符 token 串列。"""
    raw_toks = bar_str.split()
    clean = []
    for t in raw_toks:
        if t.startswith("{") and t.endswith("}"):
            continue
        if t.startswith("<") and t.endswith("*>"):
            continue
        clean.append(t)
    return clean


def score_candidate(
    rh_bar_tokens: list[str],
    lh_bar_tokens: list[str],
    rh_grid: int,
    lh_grid: int,
    key_offset: int,
    is_minor: bool,
    is_final: bool,
    is_penultimate: bool,
    is_first: bool,
    prev_rh_tok: str = "0",
) -> tuple[float, list[str]]:
    """
    計算 LH 小節在 RH 旋律下的和聲協調度。
    若產生小二度/大七度衝突或和弦摩擦，給予嚴重扣分並列出警告。
    """
    # 展開 timeline
    unit_multiplier_rh = 16 // rh_grid if rh_grid <= 16 else 1
    unit_multiplier_lh = 16 // lh_grid if lh_grid <= 16 else 1

    rh_grid_tokens = []
    for tok in rh_bar_tokens:
        if tok == "-":
            if rh_grid_tokens:
                rh_grid_tokens.extend([rh_grid_tokens[-1]] * unit_multiplier_rh)
            else:
                rh_grid_tokens.extend([prev_rh_tok] * unit_multiplier_rh)
        else:
            rh_grid_tokens.extend([tok] * unit_multiplier_rh)

    lh_grid_tokens = []
    for tok in lh_bar_tokens:
        if tok == "-":
            if lh_grid_tokens:
                lh_grid_tokens.extend([lh_grid_tokens[-1]] * unit_multiplier_lh)
            else:
                lh_grid_tokens.extend(["0"] * unit_multiplier_lh)
        else:
            lh_grid_tokens.extend([tok] * unit_multiplier_lh)

    warnings = []
    score = 0.0
    min_len = min(len(rh_grid_tokens), len(lh_grid_tokens))

    # 檢查長度是否一致
    if len(rh_grid_tokens) != len(lh_grid_tokens):
        # 長度不符直接不合格
        return -99999.0, ["長度不符"]

    for tick in range(min_len):
        rh_tok = rh_grid_tokens[tick]
        lh_tok = lh_grid_tokens[tick]

        rh_pc = parse_token_absolute_pitch(rh_tok, key_offset)
        if rh_pc is None:
            continue

        # 1. 低音單音衝突檢查
        lh_pc = parse_token_absolute_pitch(lh_tok, key_offset)
        if lh_pc is not None:
            diff = abs(rh_pc - lh_pc) % 12
            if diff in (1, 11):
                warnings.append(f"低音衝突: RH={rh_tok}, LH={lh_tok}")
                score -= 1000.0
            elif diff == 0:
                score += 3.0  # 同度/八度
            elif diff in (7, 5):
                score += 2.0  # 純五度、純四度
            elif diff in (4, 3, 8, 9):
                score += 1.5  # 三六度協和

        # 2. 和弦摩擦檢查
        chord_pcs = parse_chord_absolute_pitches(lh_tok, key_offset)
        if chord_pcs is not None:
            chord_dists = [abs(rh_pc - c_pc) % 12 for c_pc in chord_pcs]
            if 0 in chord_dists:
                score += 5.0  # 和弦內音
            elif 1 in chord_dists or 11 in chord_dists:
                warnings.append(f"和弦摩擦: RH={rh_tok}, LH={lh_tok}")
                score -= 1000.0
            else:
                score += 1.0  # 協和外音 (如 9 音、6 音)

    # 和弦風格加權：強烈優先使用正三和弦 (I, IV, V)，副三和弦 (ii, vi) 次之
    lh_str = " ".join(lh_bar_tokens)
    if not is_minor:
        if "[1]" in lh_str:
            score += 6.0
        if "[5_]" in lh_str or "[5]" in lh_str:
            score += 5.0
        if "[4]" in lh_str:
            score += 4.0
        if "[6m]" in lh_str or "[2m]" in lh_str:
            score += 1.0
    else:
        if "[6_m]" in lh_str or "[6m]" in lh_str:
            score += 6.0
        if "[3_]" in lh_str or "[3]" in lh_str:
            score += 5.0
        if "[2m]" in lh_str:
            score += 4.0

    # 風格獎勵與懲罰
    if is_final:
        if is_minor:
            if "6__" in lh_str or "[6_m]" in lh_str:
                score += 50.0
        else:
            if "1_" in lh_str or "[1]" in lh_str:
                score += 50.0
    elif is_penultimate:
        if is_minor:
            if "3__" in lh_str or "[3_]" in lh_str:
                score += 25.0
        else:
            if "5__" in lh_str or "[5_]" in lh_str:
                score += 25.0
    elif is_first:
        if is_minor:
            if "6__" in lh_str or "[6_m]" in lh_str:
                score += 30.0
        else:
            if "1_" in lh_str or "[1]" in lh_str:
                score += 30.0

    return score, warnings


def generate_candidate_bars(
    meter: str,
    is_minor: bool,
    is_final: bool,
    is_penultimate: bool,
) -> tuple[int, list[list[str]]]:
    """針對不同拍號與調性，產生候選伴奏型。回傳 (lh_grid, candidates)。"""
    if meter == "2/4":
        lh_grid = 4
        if is_minor:
            if is_final:
                return lh_grid, [
                    ["6__", "0"],
                    ["6__", "[6_m]"],
                    ["6__", "-"],
                ]
            cands = [
                ["6__", "[6_m]"],
                ["3__", "[3_]"],
                ["2_", "[2m]"],
                ["1_", "[1]"],
                ["6__", "3__"],
                ["3__", "6__"],
                ["2_", "3__"],
                ["6__", "0"],
                ["3__", "0"],
            ]
            return lh_grid, cands
        else:
            if is_final:
                return lh_grid, [
                    ["1_", "0"],
                    ["1_", "[1]"],
                    ["1_", "-"],
                ]
            cands = [
                ["1_", "[1]"],
                ["5__", "[5_]"],
                ["4__", "[4]"],
                ["6__", "[6m]"],
                ["2_", "[2m]"],
                ["1_", "5__"],
                ["5__", "1_"],
                ["4__", "1_"],
                ["1_", "0"],
                ["5__", "0"],
            ]
            return lh_grid, cands

    elif meter == "4/4":
        lh_grid = 4
        if is_minor:
            if is_final:
                return lh_grid, [
                    ["6__", "[6_m]", "6__", "0"],
                    ["6__", "0", "6__", "0"],
                    ["6__", "[6_m]", "6__", "-"],
                ]
            cands = [
                ["6__", "[6_m]", "6__", "[6_m]"],
                ["6__", "[6_m]", "3__", "[3_]"],
                ["3__", "[3_]", "3__", "[3_]"],
                ["3__", "[3_]", "6__", "[6_m]"],
                ["2_", "[2m]", "3__", "[3_]"],
                ["2_", "[2m]", "6__", "[6_m]"],
                ["1_", "[1]", "3__", "[3_]"],
                ["1_", "[1]", "6__", "[6_m]"],
                ["6__", "[6_m]", "6__", "0"],
                ["3__", "[3_]", "3__", "0"],
            ]
            return lh_grid, cands
        else:
            if is_final:
                return lh_grid, [
                    ["1_", "[1]", "1_", "0"],
                    ["1_", "[1]", "0", "0"],
                    ["1_", "0", "1_", "0"],
                    ["5__", "[5_]", "1_", "0"],
                ]
            cands = [
                ["1_", "[1]", "5__", "[1]"],
                ["1_", "[1]", "1_", "[1]"],
                ["1_", "[1]", "5__", "[5_]"],
                ["5__", "[5_]", "5__", "[5_]"],
                ["5__", "[5_]", "1_", "[1]"],
                ["4__", "[4]", "4__", "[4]"],
                ["4__", "[4]", "1_", "[1]"],
                ["4__", "[4]", "5__", "[5_]"],
                ["6__", "[6m]", "1_", "[1]"],
                ["2_", "[2m]", "5__", "[5_]"],
                ["1_", "[1]", "4__", "[4]"],
                ["1_", "[1]", "1_", "0"],
                ["5__", "[5_]", "5__", "0"],
            ]
            return lh_grid, cands

    elif meter == "3/4":
        lh_grid = 4
        if is_minor:
            if is_final:
                return lh_grid, [
                    ["6__", "[6_m]", "0"],
                    ["6__", "0", "0"],
                ]
            cands = [
                ["6__", "[6_m]", "[6_m]"],
                ["3__", "[3_]", "[3_]"],
                ["2_", "[2m]", "[2m]"],
                ["1_", "[1]", "[1]"],
                ["6__", "[6_m]", "0"],
                ["3__", "[3_]", "0"],
            ]
            return lh_grid, cands
        else:
            if is_final:
                return lh_grid, [
                    ["1_", "[1]", "0"],
                    ["1_", "0", "0"],
                ]
            cands = [
                ["1_", "[1]", "[1]"],
                ["5__", "[5_]", "[5_]"],
                ["4__", "[4]", "[4]"],
                ["6__", "[6m]", "[6m]"],
                ["2_", "[2m]", "[2m]"],
                ["1_", "[1]", "0"],
                ["5__", "[5_]", "0"],
            ]
            return lh_grid, cands

    elif meter == "6/8":
        lh_grid = 8
        if is_minor:
            if is_final:
                return lh_grid, [
                    ["6__", "[6_m]", "[6_m]", "6__", "-", "0"],
                    ["6__", "-", "-", "6__", "-", "0"],
                ]
            cands = [
                ["6__", "[6_m]", "[6_m]", "3__", "[6_m]", "[6_m]"],
                ["6__", "[6_m]", "[6_m]", "6__", "[6_m]", "[6_m]"],
                ["3__", "[3_]", "[3_]", "3__", "[3_]", "[3_]"],
                ["3__", "[3_]", "[3_]", "6__", "[6_m]", "[6_m]"],
                ["2_", "[2m]", "[2m]", "3__", "[3_]", "[3_]"],
                ["6__", "-", "-", "3__", "-", "-"],
                ["6__", "-", "-", "6__", "-", "0"],
            ]
            return lh_grid, cands
        else:
            if is_final:
                return lh_grid, [
                    ["1_", "[1]", "[1]", "1_", "-", "0"],
                    ["1_", "-", "-", "1_", "-", "0"],
                ]
            cands = [
                ["1_", "[1]", "[1]", "5__", "[1]", "[1]"],
                ["1_", "[1]", "[1]", "1_", "[1]", "[1]"],
                ["1_", "[1]", "[1]", "5__", "[5_]", "[5_]"],
                ["5__", "[5_]", "[5_]", "5__", "[5_]", "[5_]"],
                ["5__", "[5_]", "[5_]", "1_", "[1]", "[1]"],
                ["4__", "[4]", "[4]", "4__", "[4]", "[4]"],
                ["4__", "[4]", "[4]", "1_", "[1]", "[1]"],
                ["6__", "[6m]", "[6m]", "1_", "[1]", "[1]"],
                ["1_", "-", "-", "5__", "-", "-"],
                ["1_", "-", "-", "1_", "-", "0"],
            ]
            return lh_grid, cands

    elif meter == "3/2":
        lh_grid = 8
        if is_final:
            return lh_grid, [
                ["1_", "-", "-", "-", "[1]", "-", "-", "-", "1_", "-", "-", "-"],
                ["1_", "-", "-", "-", "[1]", "-", "-", "-", "1_", "-", "0", "0"],
            ]
        cands = [
            ["1_", "-", "-", "-", "[1]", "-", "-", "-", "[1]", "-", "-", "-"],
            ["1_", "-", "-", "-", "[1]", "-", "-", "-", "5__", "-", "-", "-"],
            ["1_", "-", "-", "-", "[5_]", "-", "-", "-", "[1]", "-", "-", "-"],
            ["1_", "-", "-", "-", "[4]", "-", "-", "-", "[1]", "-", "-", "-"],
            ["5__", "-", "-", "-", "[5_]", "-", "-", "-", "[5_]", "-", "-", "-"],
            ["5__", "-", "-", "-", "[5_]", "-", "-", "-", "1_", "-", "-", "-"],
            ["4__", "-", "-", "-", "[4]", "-", "-", "-", "[4]", "-", "-", "-"],
            ["4__", "-", "-", "-", "[4]", "-", "-", "-", "1_", "-", "-", "-"],
            ["1_", "-", "-", "-", "5__", "-", "-", "-", "1_", "-", "-", "-"],
        ]
        return lh_grid, cands

    # Default fallback to 4/4
    return 4, [["1_", "[1]", "5__", "[1]"]]


def process_song_tmd(source_tmd: Path, output_tmd: Path) -> bool:
    content = source_tmd.read_text(encoding="utf-8")
    meta = parse_score_metadata(content)
    key_offset = parse_key_signature(content)

    # 1. 產生標頭
    # 標題加上（鋼琴伴奏版）
    header_lines = []
    in_header = True
    body_text = ""

    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if in_header:
            if re.match(r"^\w+(?::\w+)?@.*?\{", line):
                in_header = False
                body_text = "\n".join(lines[i:])
                break
            # 處理標籤
            if line.startswith("~ \"tag: evidence:scan_verified\""):
                header_lines.append("~ \"tag: evidence:accompaniment\"")
            elif line.startswith("** ") and line.endswith(" **"):
                t_str = line[3:-3].strip()
                if not t_str.endswith("（鋼琴伴奏版）"):
                    header_lines.append(f"** {t_str}（鋼琴伴奏版） **")
                else:
                    header_lines.append(line)
            else:
                header_lines.append(line)
        i += 1

    # 2. 擷取旋律軌
    # 尋找第一條軌道（主旋律），以獨佔一行的 } 結尾，避免內嵌動態或調號 {!= 100} 截斷
    track_m = re.search(r"(\w+)(?::\w+)?(@\|-?\d+\|)\s*\{(.*?)\n\}", body_text, re.DOTALL)
    if not track_m:
        print(f"❌ {source_tmd}: 無法找到主音軌")
        return False

    track_name = track_m.group(1)
    track_oct = track_m.group(2)
    track_content = track_m.group(3)

    # 尋找網格 <N*>
    rh_grid_m = re.search(r"<(\d+)\*>", track_content)
    rh_grid = int(rh_grid_m.group(1)) if rh_grid_m else 4

    # 清除軌道內容註解與歌詞以取出小節
    # 但保留原始 track_content 稍後用於 PianoRH
    # 分解各小節
    raw_bars = []
    # 依 | 切分小節
    # 注意避免註解中的 |
    clean_notes = re.sub(r"/\*.*?\*/", "", track_content, flags=re.DOTALL)
    clean_notes = re.sub(r"^\s*L\d*\|.*$", "", clean_notes, flags=re.MULTILINE)
    clean_notes = re.sub(r"<\d+\*>", "", clean_notes)

    for bar in clean_notes.split("|"):
        tokens = clean_measure_tokens(bar)
        if tokens:
            raw_bars.append(tokens)

    num_bars = len(raw_bars)
    if num_bars == 0:
        print(f"❌ {source_tmd}: 無有效小節")
        return False

    # 3. 伴奏小節求解
    lh_grid, _ = generate_candidate_bars(meta["meter"], meta["is_minor"], False, False)
    chosen_lh_bars = []
    prev_rh_tok = "0"

    for b_idx, bar_tokens in enumerate(raw_bars):
        is_first = (b_idx == 0)
        is_final = (b_idx == num_bars - 1)
        is_penultimate = (b_idx == num_bars - 2)

        _, candidates = generate_candidate_bars(
            meta["meter"], meta["is_minor"], is_final, is_penultimate
        )

        best_bar = candidates[0]
        best_score = -999999.0
        best_warns = []

        for cand in candidates:
            sc, warns = score_candidate(
                bar_tokens,
                cand,
                rh_grid,
                lh_grid,
                key_offset,
                meta["is_minor"],
                is_final,
                is_penultimate,
                is_first,
                prev_rh_tok=prev_rh_tok,
            )
            if sc > best_score:
                best_score = sc
                best_bar = cand
                best_warns = warns

        # 如果最佳仍有警示（衝突），嘗試安全單音低音回退（避免撞音）
        if best_warns:
            # 嘗試純八度根音或五度低音
            fallback_cands = []
            if meta["meter"] == "4/4":
                fallback_cands = [
                    ["1_", "0", "1_", "0"],
                    ["1_", "0", "5__", "0"],
                    ["5__", "0", "5__", "0"],
                    ["6__", "0", "6__", "0"],
                    ["4__", "0", "4__", "0"],
                    ["2_", "0", "2_", "0"],
                    ["1_", "0", "0", "0"],
                ]
            elif meta["meter"] == "2/4":
                fallback_cands = [
                    ["1_", "0"],
                    ["5__", "0"],
                    ["6__", "0"],
                    ["4__", "0"],
                    ["2_", "0"],
                ]
            elif meta["meter"] == "3/4":
                fallback_cands = [
                    ["1_", "0", "0"],
                    ["5__", "0", "0"],
                    ["6__", "0", "0"],
                    ["4__", "0", "0"],
                ]
            elif meta["meter"] == "6/8":
                fallback_cands = [
                    ["1_", "-", "-", "5__", "-", "-"],
                    ["1_", "-", "-", "1_", "-", "0"],
                    ["6__", "-", "-", "3__", "-", "-"],
                    ["6__", "-", "-", "6__", "-", "0"],
                ]

            for fb in fallback_cands:
                sc, warns = score_candidate(
                    bar_tokens,
                    fb,
                    rh_grid,
                    lh_grid,
                    key_offset,
                    meta["is_minor"],
                    is_final,
                    is_penultimate,
                    is_first,
                    prev_rh_tok=prev_rh_tok,
                )
                if not warns and sc > best_score:
                    best_score = sc
                    best_bar = fb
                    best_warns = warns
                    break

        chosen_lh_bars.append(best_bar)
        # 更新 prev_rh_tok
        for t in reversed(bar_tokens):
            if t != "-":
                prev_rh_tok = t
                break

    # 4. 組裝 PianoRH 與 PianoLH
    rh_body = track_content.strip()

    # 排版 PianoLH 小節，每 4 小節一行（或每行相符）
    lh_lines = []
    curr_line = []
    for i, bar in enumerate(chosen_lh_bars):
        curr_line.append(" ".join(bar))
        if len(curr_line) == 4 or i == len(chosen_lh_bars) - 1:
            lh_lines.append("    | " + " | ".join(curr_line) + " |")
            curr_line = []

    lh_body = "\n".join(lh_lines)

    # 5. 處理多聲部（若是二部合唱）
    other_tracks = []
    if "Piano_2" in body_text:
        # 保留第二聲部
        p2_m = re.search(r"(\w+:Piano_2@.*?\{.*?\})", body_text, re.DOTALL)
        if p2_m:
            other_tracks.append(p2_m.group(1))

    # 6. 回放指令 Flowchart
    play_lines = [l for l in content.splitlines() if l.strip().startswith("->")]
    if not play_lines:
        play_lines = [f"-> {track_name} -> #"]

    # 組合全文
    result_parts = []
    result_parts.append("\n".join(header_lines).strip())
    result_parts.append("")
    result_parts.append(f"{track_name}:PianoRH{track_oct}" + "{\n    " + rh_body + "\n}")
    result_parts.append("")
    for ot in other_tracks:
        result_parts.append(ot)
        result_parts.append("")
    result_parts.append(f"{track_name}:PianoLH{track_oct}" + "{\n    " + f"<{lh_grid}*>\n" + lh_body + "\n}")
    result_parts.append("")
    result_parts.append("\n".join(play_lines))
    result_parts.append("")

    full_output = "\n".join(result_parts)
    output_tmd.write_text(full_output, encoding="utf-8")

    # 7. 驗證審查
    ok, warns = audit_piano_score(output_tmd)
    if not ok:
        print(f"⚠️  {output_tmd.name}: 發現 {len(warns)} 處和聲警示")
        for w in warns[:3]:
            print(f"   {w}")
    else:
        print(f"✅ {output_tmd.name}: 和聲審查通過 (0 衝突)")

    # 執行 tmd check
    res = subprocess.run(["tmd", "check", str(output_tmd)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"❌ {output_tmd.name}: tmd check 失敗！\n{res.stdout}\n{res.stderr}")
        return False

    return ok


def main():
    parser = argparse.ArgumentParser(description="產生鋼琴伴奏版 TMD")
    parser.add_argument("targets", nargs="*", help="目標資料夾或 TMD 檔案（預設 docs/izawa_shogaku_shoka）")
    args = parser.parse_args()

    targets = args.targets if args.targets else ["docs/izawa_shogaku_shoka"]
    tmd_files = []
    for tgt in targets:
        p = Path(tgt)
        if p.is_dir():
            for f in sorted(p.rglob("*.tmd")):
                if not f.name.endswith("_piano.tmd"):
                    tmd_files.append(f)
        elif p.is_file():
            tmd_files.append(p)

    print(f"找到 {len(tmd_files)} 首歌曲需產生伴奏...")
    success_count = 0
    warn_count = 0

    for f in tmd_files:
        stem = f.stem
        out_path = f.parent / f"{stem}_piano.tmd"
        ok = process_song_tmd(f, out_path)
        if ok:
            success_count += 1
        else:
            warn_count += 1

    print(f"\n🎉 伴奏產生完成！成功: {success_count}, 警告: {warn_count}, 總計: {len(tmd_files)}")


if __name__ == "__main__":
    main()
