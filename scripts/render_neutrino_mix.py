#!/usr/bin/env python3
"""
render_neutrino_mix.py: 使用 NEUTRINO 將 TMD 樂譜中的歌詞軌合成為人聲，並透過 ffmpeg 混入鋼琴伴奏。

支援輸入：
  - 歌曲資料夾路徑（自動尋找 *_piano.tmd 與主旋律 .tmd）
  - 單一 *_piano.tmd 或主旋律 .tmd 檔案路徑

核心特性：
  1. 直接從完整 TMD 匯出 MusicXML，自動鎖定含歌詞之聲部（如 PianoRH），確保前奏 (Intro)、間奏、尾奏
     與多段反覆 (L1/L2) 的小節數與伴奏 WAV 100% 同步。
  2. 自動將無歌詞的器樂音符（如前奏 Intro 的右手旋律）在送入 NEUTRINO 前轉為同長度的休止符 (<rest/>)，
     避免 NEUTRINO 因空白歌詞報錯崩潰，同時保留精確的前奏/間奏等待秒數。
  3. 自動根據 NEUTRINO 產出的 timing.lab 對齊第一拍子音先行發聲 (Pre-utterance) 與伴奏正拍。
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


DEFAULT_NEUTRINO_DIR = Path("/Applications/NEUTRINO")
LYRIC_LINE_RE = re.compile(r"^\s*L(\d*)\|", re.MULTILINE)
ENTRY_HEADER_RE = re.compile(
    r"^\s*([A-Za-z0-9_]+)\s*:\s*([A-Za-z0-9_-]+)(?:\[[^\]]*\])?\s*@\|?[^\{]*\|?\s*\{(.*?)\n\s*\}",
    re.MULTILINE | re.DOTALL,
)
TEMPO_RE = re.compile(r"^\s*!=\s*([0-9]+(?:\.[0-9]+)?)\s*$", re.MULTILINE)
METER_RE = re.compile(r"^\s*<(\d+)\s*/\s*(\d+)>\s*$", re.MULTILINE)
PLAYBACK_RE = re.compile(r"^\s*->.*->\s*#\s*$", re.MULTILINE)


def parse_tempo_and_meter(tmd_text: str) -> tuple[float, int, int]:
    """從 TMD 內容解析 BPM 與拍號 (beats, beat_type)。"""
    bpm = 120.0
    beats, beat_type = 4, 4

    m_tempo = TEMPO_RE.search(tmd_text)
    if m_tempo:
        bpm = float(m_tempo.group(1))

    m_meter = METER_RE.search(tmd_text)
    if m_meter:
        beats = int(m_meter.group(1))
        beat_type = int(m_meter.group(2))

    return bpm, beats, beat_type


def find_lyric_instrument(tmd_text: str) -> tuple[str | None, list[int]]:
    """找出含有 L| 或 L1|..L64| 歌詞行的樂器軌道名稱，以及出現的段落編號清單。"""
    stanzas_found: set[int] = set()
    lyric_inst: str | None = None
    for match in ENTRY_HEADER_RE.finditer(tmd_text):
        _section, instrument, body = match.group(1), match.group(2), match.group(3)
        lyric_matches = LYRIC_LINE_RE.findall(body)
        if lyric_matches:
            if lyric_inst is None:
                lyric_inst = instrument
            stanzas_found.update(int(num) for num in lyric_matches if num.isdigit())
    return lyric_inst, sorted(stanzas_found)


def ensure_stanza_playback_selectors(tmd_text: str, stanzas: list[int], target_repeats: int | None = None) -> str:
    """
    若軌道內有多段歌詞 (L1|, L2|...)，但播放順序僅寫 `-> Section -> #` 或 `-> Section -> Section -> #`，
    自動補齊為 `-> Section[L1] -> Section[L2] -> #` 以供匯出完整歌詞。
    """
    if not stanzas:
        return tmd_text

    m_play = PLAYBACK_RE.search(tmd_text)
    if not m_play:
        return tmd_text

    play_line = m_play.group(0)
    if "[L" in play_line:
        return tmd_text

    tokens = [
        tok.strip()
        for tok in play_line.replace("->", " ").replace("#", " ").split()
        if tok.strip() and not tok.strip().startswith("{")
    ]
    if not tokens:
        return tmd_text

    section_name = tokens[-1]
    prefix_tokens = [t for t in tokens if t != section_name]
    section_count = sum(1 for t in tokens if t == section_name)

    if target_repeats is not None and target_repeats > 1:
        selected_stanzas = stanzas[:target_repeats]
    elif section_count > 1:
        selected_stanzas = stanzas[:section_count]
    else:
        selected_stanzas = stanzas

    ordered = prefix_tokens + [f"{section_name}[L{s}]" for s in selected_stanzas]
    new_play = "-> " + " -> ".join(ordered) + " -> #"
    return tmd_text[: m_play.start()] + new_play + tmd_text[m_play.end() :]


def prepare_vocal_musicxml(raw_musicxml_path: Path, out_musicxml_path: Path) -> tuple[str, int]:
    """
    處理 TMD 匯出的 MusicXML 以供 NEUTRINO 使用：
    1. 僅保留含有 `<lyric>` 的 `<part>`（例如 PianoRH），移除純伴奏聲部（如 PianoLH）。
    2. 將該聲部中所有「無歌詞且非連音線延續 (`<tie type="stop"/>`)」的純器樂音符（如 Intro 前奏、間奏）
       轉為同等時值的 `<rest/>`，確保時間軸與伴奏 100% 對齊且不觸發 NEUTRINO 空白歌詞錯誤。
    回傳 (保留的 part 名稱, 轉為休止符的器樂音符數量)。
    """
    tree = ET.parse(raw_musicxml_path)
    root = tree.getroot()

    part_list = root.find("part-list")
    parts = root.findall("part")
    if not parts:
        raise RuntimeError(f"MusicXML 中找不到任何 <part>：{raw_musicxml_path}")

    # 找出含有最多有效歌詞的 part
    best_part = None
    best_lyric_count = -1
    for p in parts:
        texts = [
            (lyr.findtext("text") or "").strip()
            for lyr in p.iter("lyric")
        ]
        valid_count = sum(1 for t in texts if t and t != "_")
        if valid_count > best_lyric_count:
            best_lyric_count = valid_count
            best_part = p

    if best_part is None or best_lyric_count <= 0:
        raise RuntimeError("MusicXML 中找不到任何含有日文歌詞的聲部")

    target_part_id = best_part.attrib.get("id", "P1")
    target_part_name = target_part_id

    # 移除其他 part 與 score-part
    if part_list is not None:
        for sp in list(part_list.findall("score-part")):
            if sp.attrib.get("id") == target_part_id:
                target_part_name = (sp.findtext("part-name") or target_part_id).strip()
            else:
                part_list.remove(sp)

    for p in list(parts):
        if p is not best_part:
            root.remove(p)

    # 遍歷保留聲部中的所有 <note>，將無歌詞的器樂音符轉為 <rest/>，並為同小節一字多音圓滑線補上「ー」
    converted_notes = 0
    melisma_notes = 0
    in_lyric_tie = False
    in_melisma = False
    prev_lyric_by_num: dict[str, str] = {}

    kanji_to_kana = {
        "出": "デ",
        "野": "ノ",
        "汽": "キ",
        "車": "シャ",
        "一": "イ",
        "十": "ジュウ",
        "五": "ゴ",
    }
    dakuten_map = str.maketrans(
        "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ",
        "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボ",
    )
    seion_map = str.maketrans(
        "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボ",
        "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ",
    )

    for measure in best_part.findall("measure"):
        # 移除和弦標記 <harmony>，避免干擾單旋律解析
        for harmony in list(measure.findall("harmony")):
            measure.remove(harmony)

        measure_has_lyric = any(
            (lyr.findtext("text") or "").strip() not in ("", "_")
            for note in measure.findall("note")
            if note.find("rest") is None
            for lyr in note.findall("lyric")
        )

        for note in measure.findall("note"):
            if note.find("rest") is not None:
                in_lyric_tie = False
                in_melisma = False
                for lyr in list(note.findall("lyric")):
                    note.remove(lyr)
                continue

            ties = {t.attrib.get("type") for t in note.findall("tie")}
            has_tie_start = "start" in ties
            has_tie_stop = "stop" in ties

            # 檢查是否有有效歌詞
            lyric_texts = []
            for lyr in list(note.findall("lyric")):
                lyr_num = lyr.attrib.get("number", "1")
                t_el = lyr.find("text")
                txt = (t_el.text or "").strip() if t_el is not None else ""
                if not txt or txt == "_":
                    note.remove(lyr)
                else:
                    # 清理特殊標點（保留平假名、片假名、長音符「ー」）
                    cleaned = re.sub(r"[「」『』（）()・、。，,\s]", "", txt)
                    for k, v in kanji_to_kana.items():
                        cleaned = cleaned.replace(k, v)
                    # 展開疊字號（踊り字：ヽ ヾ ゝ ゞ）
                    if cleaned in ("ヽ", "ゝ"):
                        prev = prev_lyric_by_num.get(lyr_num, "ア")
                        cleaned = prev[-1].translate(seion_map) if prev else "ア"
                    elif cleaned in ("ヾ", "ゞ"):
                        prev = prev_lyric_by_num.get(lyr_num, "ア")
                        cleaned = prev[-1].translate(dakuten_map) if prev else "ア"

                    if t_el is not None:
                        t_el.text = cleaned
                    if cleaned:
                        prev_lyric_by_num[lyr_num] = cleaned
                        lyric_texts.append(cleaned)
                    else:
                        note.remove(lyr)

            has_valid_lyric = len(lyric_texts) > 0

            if has_valid_lyric:
                in_lyric_tie = has_tie_start
                in_melisma = True
            elif has_tie_stop and in_lyric_tie:
                # 這是前一個有歌詞音符的連音線延音 (Tie continuation)，保留音高
                in_lyric_tie = has_tie_start
                in_melisma = True
            elif measure_has_lyric and in_melisma:
                # 歌唱小節內的一字多音圓滑線延音 (Slur / Melisma continuation)，補上長音「ー」
                lyr_el = ET.SubElement(note, "lyric", {"number": "1"})
                syl_el = ET.SubElement(lyr_el, "syllabic")
                syl_el.text = "single"
                txt_el = ET.SubElement(lyr_el, "text")
                txt_el.text = "ー"
                in_lyric_tie = has_tie_start
                in_melisma = True
                melisma_notes += 1
            else:
                # 無歌詞且非歌詞延音 -> 純器樂音符（例如前奏 Intro / 間奏），轉為 <rest/>
                in_lyric_tie = False
                in_melisma = False
                pitch_el = note.find("pitch")
                if pitch_el is not None:
                    # 將 <pitch> 替換為 <rest/>（保持在 duration 之前以符合 MusicXML DTD 順序）
                    idx = list(note).index(pitch_el)
                    note.remove(pitch_el)
                    note.insert(idx, ET.Element("rest"))
                    converted_notes += 1

                # 移除器樂音符上的 tie / notations / stem / beam / accidental
                for tag in ("tie", "notations", "stem", "beam", "accidental", "lyric"):
                    for el in list(note.findall(tag)):
                        note.remove(el)

    tree.write(out_musicxml_path, encoding="utf-8", xml_declaration=True)
    return target_part_name, converted_notes


def resolve_song_tmds(target: Path) -> tuple[Path, Path, str]:
    """
    回傳 (vocal_source_tmd, accompaniment_tmd, base_stem)。
    優先使用 *_piano.tmd 作為人聲與伴奏的唯一時間軸來源。
    """
    target = target.resolve()
    if target.is_dir():
        piano_tmds = sorted(target.glob("*_piano.tmd"))
        main_tmds = sorted(p for p in target.glob("*.tmd") if not p.name.endswith("_piano.tmd"))
        if not main_tmds and not piano_tmds:
            raise FileNotFoundError(f"在目錄 {target} 中找不到任何 .tmd 檔案")

        main_tmd = main_tmds[0] if main_tmds else piano_tmds[0]
        piano_tmd = piano_tmds[0] if piano_tmds else main_tmd
        base_stem = main_tmd.stem.removesuffix("_piano")
    else:
        if not target.exists():
            raise FileNotFoundError(f"找不到檔案：{target}")
        if target.name.endswith("_piano.tmd"):
            piano_tmd = target
            base_stem = target.stem.removesuffix("_piano")
            candidate_main = target.parent / f"{base_stem}.tmd"
            main_tmd = candidate_main if candidate_main.exists() else target
        else:
            main_tmd = target
            base_stem = target.stem
            candidate_piano = target.parent / f"{base_stem}_piano.tmd"
            piano_tmd = candidate_piano if candidate_piano.exists() else target

    piano_text = piano_tmd.read_text(encoding="utf-8")
    inst_in_piano, _ = find_lyric_instrument(piano_text)
    if inst_in_piano is not None:
        return piano_tmd, piano_tmd, base_stem

    main_text = main_tmd.read_text(encoding="utf-8")
    inst_in_main, _ = find_lyric_instrument(main_text)
    if inst_in_main is not None:
        return main_tmd, piano_tmd, base_stem

    raise RuntimeError(
        f"在 {piano_tmd.name} 與 {main_tmd.name} 中皆找不到任何 `L|` 或 `L1|` 歌詞軌，無法合成人聲。"
    )


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"指令執行失敗 ({' '.join(cmd)}):\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
    return res


def detect_max_volume_db(audio_path: Path) -> float | None:
    """使用 ffmpeg volumedetect 取得音訊檔案的 max_volume (dB)。"""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(audio_path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", (res.stderr or "") + (res.stdout or ""))
    return float(m.group(1)) if m else None


def render_single_song(target: Path, args: argparse.Namespace, neutrino_dir: Path, model_dir: Path) -> Path:
    vocal_src_tmd, accomp_tmd, base_stem = resolve_song_tmds(target)
    song_dir = accomp_tmd.parent

    if args.output and (not Path(args.target).resolve().is_dir() or list(Path(args.target).resolve().glob("*.tmd"))):
        output_path = Path(args.output).resolve()
    elif args.replace_song_mp3:
        output_path = song_dir / f"{base_stem}.mp3"
    else:
        output_path = song_dir / f"{base_stem}_neutrino.mp3"

    if args.skip_existing and output_path.exists() and output_path.stat().st_size > 0:
        print(f"⏭️  略過已存在的檔案：{output_path.name} ({song_dir.name})")
        return output_path

    vocal_tmd_text = vocal_src_tmd.read_text(encoding="utf-8")
    accomp_tmd_text = accomp_tmd.read_text(encoding="utf-8")

    vocal_inst, stanzas = find_lyric_instrument(vocal_tmd_text)
    if not vocal_inst:
        raise RuntimeError(f"在 {vocal_src_tmd} 找不到含有歌詞 (L| / L1|) 的軌道")

    bpm, beats, beat_type = parse_tempo_and_meter(accomp_tmd_text)
    measure_duration_sec = beats * (4.0 / beat_type) * (60.0 / bpm)

    print(f"🎵 歌曲：{base_stem} ({song_dir.name})")
    print(f"   - 人聲來源：{vocal_src_tmd.name} (軌道: {vocal_inst}, 段落: {stanzas or ['L']})")
    print(f"   - 伴奏來源：{accomp_tmd.name} ({'僅 PianoLH' if args.lh_only else '完整伴奏'})")
    print(f"   - 歌手模型：{args.model} | 速度：{bpm} BPM (<{beats}/{beat_type}>, 單小節 {measure_duration_sec:.4f}s)")

    tmp_ctx = tempfile.TemporaryDirectory(prefix=f"neutrino_{base_stem}_")
    work_dir = Path(tmp_ctx.name)
    if args.keep_temp:
        work_dir = Path(tempfile.mkdtemp(prefix=f"neutrino_{base_stem}_"))
        tmp_ctx.cleanup()
        print(f"📂 暫存目錄：{work_dir}")

    try:
        # 1. 將 TMD 匯出為原始 MusicXML，並將無歌詞之器樂小節（如 Intro 前奏）自動轉為 <rest/>
        normalized_vocal_text = ensure_stanza_playback_selectors(vocal_tmd_text, stanzas)
        temp_vocal_source = work_dir / "vocal_source.tmd"
        temp_vocal_source.write_text(normalized_vocal_text, encoding="utf-8")

        raw_musicxml = work_dir / "raw.musicxml"
        run_cmd(["tmd", str(temp_vocal_source), "-x", str(raw_musicxml)])

        vocal_musicxml = work_dir / "vocal.musicxml"
        part_name, converted_rests = prepare_vocal_musicxml(raw_musicxml, vocal_musicxml)
        if converted_rests > 0:
            print(f"   ℹ️  已將 {part_name} 軌中 {converted_rests} 個無歌詞器樂音符（前奏/間奏）轉為休止符以對齊時間軸")

        # 2. 渲染鋼琴伴奏 WAV
        piano_wav = work_dir / "piano.wav"
        if args.lh_only and "PianoLH" in accomp_tmd_text:
            lh_only_tmd = work_dir / "lh_only.tmd"
            run_cmd(
                [
                    "tmd",
                    "refactor",
                    "extract-instrument",
                    str(accomp_tmd),
                    "--instrument",
                    "PianoLH",
                    "-o",
                    str(lh_only_tmd),
                ]
            )
            run_cmd(["tmd", str(lh_only_tmd), "-w", str(piano_wav)])
        else:
            run_cmd(["tmd", str(accomp_tmd), "-w", str(piano_wav)])

        # 3. 呼叫 NEUTRINO musicXMLtoLabel 與 neutrino
        env = os.environ.copy()
        dyld_path = str(neutrino_dir / "bin")
        env["DYLD_LIBRARY_PATH"] = (
            f"{dyld_path}:{env['DYLD_LIBRARY_PATH']}" if env.get("DYLD_LIBRARY_PATH") else dyld_path
        )

        full_lab = work_dir / "full.lab"
        mono_lab = work_dir / "mono.lab"
        timing_lab = work_dir / "timing.lab"
        out_f0 = work_dir / "output.f0"
        out_melspec = work_dir / "output.melspec"
        vocal_wav = work_dir / "vocal.wav"

        print("🔤 [1/3] 執行 musicXMLtoLabel 轉換音素與標籤...")
        label_res = run_cmd(
            [
                str(neutrino_dir / "bin" / "musicXMLtoLabel"),
                str(vocal_musicxml),
                str(full_lab),
                str(mono_lab),
            ],
            cwd=neutrino_dir,
            env=env,
        )

        combined_label_out = (label_res.stdout or "") + "\n" + (label_res.stderr or "")
        for line in combined_label_out.splitlines():
            if "warning:" in line and "Undefined lyric" in line:
                print(f"   ⚠️  {line.strip()}")

        # 檢查 musicXMLtoLabel 是否自動在開頭插入了 1 小節休止符
        prepended_rest_sec = 0.0
        if (
            "Added a rest to the first measure" in combined_label_out
            or "最初の小節に休符を追加しました" in combined_label_out
        ):
            prepended_rest_sec = measure_duration_sec
            print(f"   ℹ️  偵測到 NEUTRINO 自動插入前導 1 小節休止符 ({prepended_rest_sec:.4f}s)")

        print(f"🎤 [2/3] 執行 NEUTRINO ({args.model}) 合成人聲...")
        neutrino_cmd = [
            str(neutrino_dir / "bin" / "neutrino"),
            str(full_lab),
            str(timing_lab),
            str(out_f0),
            str(out_melspec),
            str(vocal_wav),
            f"{model_dir}/",
            "-k",
            str(args.style_shift),
            "-f",
            str(args.transpose),
            "-s",
            "48000",
            "-b",
            "16",
            "-t",
        ]
        if args.threads > 0:
            neutrino_cmd.extend(["-n", str(args.threads)])

        # 即時串流輸出 NEUTRINO 各階段進度 (timing / pitch / melspec / vocoder)
        proc = subprocess.Popen(
            neutrino_cmd,
            cwd=neutrino_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        neutrino_out_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            neutrino_out_lines.append(line)
            stripped = line.rstrip()
            if stripped:
                print(f"   {stripped}", flush=True)
        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                f"NEUTRINO 執行失敗 ({' '.join(neutrino_cmd)}):\n{''.join(neutrino_out_lines)}"
            )

        # 4. 根據 timing.lab 計算精確對齊（保留第一拍前的子音先行發聲 Pre-utterance）
        vocal_trim_sec = 0.0
        piano_delay_ms = 0.0
        if prepended_rest_sec > 0:
            first_phoneme_sec = prepended_rest_sec
            if timing_lab.exists():
                first_line = timing_lab.read_text(encoding="utf-8").splitlines()[0].split()
                if len(first_line) >= 3 and first_line[2] == "pau":
                    first_phoneme_sec = int(first_line[1]) / 10_000_000.0
            vocal_trim_sec = max(0.0, min(prepended_rest_sec, first_phoneme_sec - 0.030))
            piano_delay_ms = max(0.0, (prepended_rest_sec - vocal_trim_sec) * 1000.0)
            print(
                f"   🎯 對齊校正：人聲首子音於 {first_phoneme_sec:.4f}s 發聲（第一拍母音落點 {prepended_rest_sec:.4f}s），"
                f"裁切人聲前導空白 {vocal_trim_sec:.4f}s 並延遲伴奏 {piano_delay_ms:.1f}ms"
            )

        # 5. 自動偵測人聲與伴奏峰值，先把 tmd -w 偏小的伴奏拉回基準峰值 (-4.5 dB)，人聲對齊至 (-2.0 dB)
        vocal_max_db = detect_max_volume_db(vocal_wav)
        piano_max_db = detect_max_volume_db(piano_wav)
        vocal_gain_db = (-2.0 - vocal_max_db) if vocal_max_db is not None else 0.0
        piano_gain_db = min(20.0, -4.5 - piano_max_db) if piano_max_db is not None else 10.0
        print(
            f"   🔊 音量平衡：人聲原始峰值 {vocal_max_db:.1f}dB (補償 {vocal_gain_db:+.1f}dB) | "
            f"伴奏原始峰值 {piano_max_db:.1f}dB (補償 {piano_gain_db:+.1f}dB)"
            if (vocal_max_db is not None and piano_max_db is not None)
            else "   🔊 音量平衡：套用預設增益"
        )

        # 6. 使用 ffmpeg 混音
        print(f"🎚️  [3/3] 使用 ffmpeg 混音輸出至 {output_path}...")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        ffmpeg_cmd = ["ffmpeg", "-y"]
        if vocal_trim_sec > 0:
            ffmpeg_cmd += ["-ss", f"{vocal_trim_sec:.6f}"]
        vocal_filter = f"[0:a]volume={vocal_gain_db:.2f}dB,volume={args.vocal_volume}[v];"
        piano_filter = f"[1:a]volume={piano_gain_db:.2f}dB,volume={args.piano_volume}"
        if piano_delay_ms > 0.5:
            delay_int = int(round(piano_delay_ms))
            piano_filter += f",adelay={delay_int}:all=1"
        piano_filter += "[p];"

        ffmpeg_cmd += [
            "-i",
            str(vocal_wav),
            "-i",
            str(piano_wav),
            "-filter_complex",
            (
                f"{vocal_filter}"
                f"{piano_filter}"
                f"[v][p]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0,"
                f"alimiter=limit=0.95"
            ),
        ]
        if output_path.suffix.lower() == ".mp3":
            ffmpeg_cmd += ["-c:a", "libmp3lame", "-q:a", "2"]
        ffmpeg_cmd.append(str(output_path))

        run_cmd(ffmpeg_cmd)
        print(f"✅ 完成！已輸出：{output_path}\n", flush=True)
        return output_path

    finally:
        if not args.keep_temp:
            tmp_ctx.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="將 TMD 伴奏版/主旋律中的歌詞軌透過 NEUTRINO 轉為人聲，並用 ffmpeg 混入伴奏。"
    )
    parser.add_argument("target", help="歌曲目錄、冊別目錄或 .tmd 檔案路徑")
    parser.add_argument(
        "-m",
        "--model",
        default="MERROW",
        help="NEUTRINO 歌手模型目錄名稱（例如 MERROW, NAKUMO, REINA, RUNO, SOMA，預設：MERROW）",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="輸出音訊路徑（預設：<song_dir>/<stem>_neutrino.mp3）",
    )
    parser.add_argument(
        "--replace-song-mp3",
        action="store_true",
        help="直接覆寫歌曲目錄下的 <stem>.mp3（供網站頁面直接播放）",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="若目標輸出 MP3 已存在且非空檔案，則直接略過不重新合成",
    )
    parser.add_argument(
        "--lh-only",
        action="store_true",
        help="伴奏僅渲染左手軌 (PianoLH)，避免右手鋼琴旋律與人聲重疊",
    )
    parser.add_argument(
        "--vocal-volume",
        type=float,
        default=1.0,
        help="峰值正規化後的人聲音量倍率（預設：1.0，基準峰值 -2.0 dB）",
    )
    parser.add_argument(
        "--piano-volume",
        type=float,
        default=1.0,
        help="峰值正規化後的鋼琴伴奏音量倍率（預設：1.0，基準峰值 -4.5 dB）",
    )
    parser.add_argument(
        "--style-shift",
        type=int,
        default=0,
        help="NEUTRINO -k style shift 參數（預設：0）",
    )
    parser.add_argument(
        "--transpose",
        type=int,
        default=0,
        help="NEUTRINO -f transpose 半音移調參數（預設：0）",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="NEUTRINO 執行緒數量 -n（預設：0 = 自動使用全部 CPU 核心 [max]）",
    )
    parser.add_argument(
        "--neutrino-dir",
        type=Path,
        default=DEFAULT_NEUTRINO_DIR,
        help=f"NEUTRINO 安裝路徑（預設：{DEFAULT_NEUTRINO_DIR}）",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留暫存工作目錄以便除錯",
    )

    args = parser.parse_args()
    neutrino_dir: Path = args.neutrino_dir.resolve()
    if not (neutrino_dir / "bin" / "neutrino").exists():
        sys.exit(f"❌ 找不到 NEUTRINO 執行檔：{neutrino_dir / 'bin' / 'neutrino'}")

    model_dir = neutrino_dir / "model" / args.model
    if not model_dir.exists():
        available = [p.name for p in sorted((neutrino_dir / "model").iterdir()) if p.is_dir()]
        sys.exit(f"❌ 找不到歌手模型 '{args.model}'（可用模型：{', '.join(available)}）")

    target_path = Path(args.target).resolve()
    if target_path.is_dir() and not list(target_path.glob("*.tmd")):
        # 批次處理整冊或整個目錄下的所有歌曲子資料夾
        song_dirs = sorted({p.parent for p in target_path.rglob("*.tmd")})
        if not song_dirs:
            sys.exit(f"❌ 在目錄 {target_path} 下找不到任何 .tmd 檔案")
        print(f"📚 批次處理目錄：{target_path}（共 {len(song_dirs)} 首曲目）\n")
        for idx, s_dir in enumerate(song_dirs, start=1):
            print(f"==================== [{idx}/{len(song_dirs)}] {s_dir.name} ====================", flush=True)
            render_single_song(s_dir, args, neutrino_dir, model_dir)
    else:
        render_single_song(target_path, args, neutrino_dir, model_dir)


if __name__ == "__main__":
    main()
