#!/usr/bin/env python3
"""
render_neutrino_mix.py: 使用 NEUTRINO 將 TMD 樂譜中的歌詞軌合成為人聲，並透過 ffmpeg 混入鋼琴伴奏。

支援輸入：
  - 歌曲資料夾路徑（自動尋找 *_piano.tmd 與主旋律 .tmd）
  - 單一 *_piano.tmd 或主旋律 .tmd 檔案路徑

核心特性：
  1. 直接從完整 TMD 匯出 MusicXML，自動找出所有含歌詞之聲部（如 Soprano、Alto 或 PianoRH），確保前奏
     (Intro)、間奏、尾奏與多段反覆 (L1/L2) 的小節數與伴奏 WAV 100% 同步。
  2. 自動將無歌詞的器樂音符（如前奏 Intro 的右手旋律）在送入 NEUTRINO 前轉為同長度的休止符 (<rest/>)，
     避免 NEUTRINO 因空白歌詞報錯崩潰，同時保留精確的前奏/間奏等待秒數。
  3. 自動根據 NEUTRINO 產出的 timing.lab 對齊第一拍子音先行發聲 (Pre-utterance) 與伴奏正拍。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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


@dataclass(frozen=True)
class PreparedVocalPart:
    path: Path
    part_name: str
    converted_rests: int


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


def find_lyric_instruments(tmd_text: str) -> tuple[list[str], list[int]]:
    """找出所有含有歌詞的樂器軌道，以及共用的段落編號清單。"""
    stanzas_found: set[int] = set()
    lyric_instruments: list[str] = []
    for match in ENTRY_HEADER_RE.finditer(tmd_text):
        _section, instrument, body = match.group(1), match.group(2), match.group(3)
        lyric_matches = LYRIC_LINE_RE.findall(body)
        if lyric_matches:
            if instrument not in lyric_instruments:
                lyric_instruments.append(instrument)
            stanzas_found.update(int(num) for num in lyric_matches if num.isdigit())
    return lyric_instruments, sorted(stanzas_found)


def find_lyric_instrument(tmd_text: str) -> tuple[str | None, list[int]]:
    """Backward-compatible single-part view of :func:`find_lyric_instruments`."""
    instruments, stanzas = find_lyric_instruments(tmd_text)
    return (instruments[0] if instruments else None), stanzas


def resolve_part_model(
    part_name: str, default_model: str, overrides: dict[str, str]
) -> str:
    """Resolve a NEUTRINO model by part name, falling back to the default model."""
    return overrides.get(part_name.casefold(), default_model)


def parse_part_model_overrides(values: list[str]) -> dict[str, str]:
    """Parse repeated ``PART=MODEL`` CLI options into a case-insensitive map."""
    overrides: dict[str, str] = {}
    for value in values:
        part_name, separator, model_name = value.partition("=")
        if not separator or not part_name.strip() or not model_name.strip():
            raise ValueError(f"聲部 voice 設定格式錯誤：{value}（應為 PART=MODEL）")
        overrides[part_name.strip().casefold()] = model_name.strip()
    return overrides


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


def prepare_vocal_musicxml(
    raw_musicxml_path: Path,
    out_musicxml_path: Path,
    target_part_id: str | None = None,
) -> tuple[str, int]:
    """
    處理 TMD 匯出的 MusicXML 以供 NEUTRINO 使用：
    1. 僅保留指定的含有 `<lyric>` 的 `<part>`（例如 PianoRH），移除純伴奏聲部（如 PianoLH）。
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

    # 找出所有含有有效歌詞的 part；未指定目標時維持舊的單聲部行為。
    lyric_parts: list[tuple[ET.Element, int]] = []
    for p in parts:
        texts = [
            (lyr.findtext("text") or "").strip()
            for lyr in p.iter("lyric")
        ]
        valid_count = sum(1 for t in texts if t and t != "_")
        if valid_count > 0:
            lyric_parts.append((p, valid_count))

    if not lyric_parts:
        raise RuntimeError("MusicXML 中找不到任何含有日文歌詞的聲部")

    if target_part_id is None:
        best_part, _ = max(lyric_parts, key=lambda item: item[1])
    else:
        best_part = next(
            (part for part, _ in lyric_parts if part.attrib.get("id") == target_part_id),
            None,
        )
        if best_part is None:
            raise RuntimeError(f"MusicXML 中找不到指定歌詞聲部：{target_part_id}")

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


def prepare_vocal_musicxml_parts(
    raw_musicxml_path: Path, output_dir: Path
) -> list[PreparedVocalPart]:
    """Split every lyric-bearing MusicXML part into an independent NEUTRINO input."""
    tree = ET.parse(raw_musicxml_path)
    root = tree.getroot()
    parts = root.findall("part")
    part_list = root.find("part-list")
    if not parts:
        raise RuntimeError(f"MusicXML 中找不到任何 <part>：{raw_musicxml_path}")

    lyric_part_ids: list[tuple[str, str]] = []
    for part in parts:
        valid_count = sum(
            1
            for lyric in part.iter("lyric")
            if (lyric.findtext("text") or "").strip() not in ("", "_")
        )
        if valid_count <= 0:
            continue
        part_id = part.attrib.get("id", "P1")
        part_name = part_id
        if part_list is not None:
            score_part = next(
                (item for item in part_list.findall("score-part") if item.attrib.get("id") == part_id),
                None,
            )
            if score_part is not None:
                part_name = (score_part.findtext("part-name") or part_id).strip()
        lyric_part_ids.append((part_id, part_name))

    if not lyric_part_ids:
        raise RuntimeError("MusicXML 中找不到任何含有日文歌詞的聲部")

    output_dir.mkdir(parents=True, exist_ok=True)
    prepared: list[PreparedVocalPart] = []
    for index, (part_id, part_name) in enumerate(lyric_part_ids, start=1):
        safe_name = re.sub(r"[^a-z0-9]+", "_", part_name.lower()).strip("_") or f"part_{index}"
        output_path = output_dir / f"vocal_{index:02d}_{safe_name}.musicxml"
        prepared_name, converted_rests = prepare_vocal_musicxml(
            raw_musicxml_path,
            output_path,
            target_part_id=part_id,
        )
        prepared.append(
            PreparedVocalPart(
                path=output_path,
                part_name=prepared_name,
                converted_rests=converted_rests,
            )
        )
    return prepared


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


def render_single_song(
    target: Path,
    args: argparse.Namespace,
    neutrino_dir: Path,
    model_dir: Path,
    model_dirs: dict[str, Path] | None = None,
) -> Path:
    vocal_src_tmd, accomp_tmd, base_stem = resolve_song_tmds(target)
    song_dir = accomp_tmd.parent

    if args.output and (not Path(args.target).resolve().is_dir() or list(Path(args.target).resolve().glob("*.tmd"))):
        output_path = Path(args.output).resolve()
    elif getattr(args, "vocal_only", False):
        output_path = song_dir / f"{base_stem}_vocal.wav"
    elif args.replace_song_mp3:
        output_path = song_dir / f"{base_stem}.mp3"
    else:
        output_path = song_dir / f"{base_stem}_neutrino.mp3"

    if args.skip_existing and output_path.exists() and output_path.stat().st_size > 0:
        print(f"⏭️  略過已存在的檔案：{output_path.name} ({song_dir.name})")
        return output_path

    vocal_tmd_text = vocal_src_tmd.read_text(encoding="utf-8")
    accomp_tmd_text = accomp_tmd.read_text(encoding="utf-8")

    vocal_instruments, stanzas = find_lyric_instruments(vocal_tmd_text)
    if not vocal_instruments:
        raise RuntimeError(f"在 {vocal_src_tmd} 找不到含有歌詞 (L| / L1|) 的軌道")

    bpm, beats, beat_type = parse_tempo_and_meter(accomp_tmd_text)
    measure_duration_sec = beats * (4.0 / beat_type) * (60.0 / bpm)

    vocal_only = getattr(args, "vocal_only", False)
    print(f"🎵 歌曲：{base_stem} ({song_dir.name})")
    print(f"   - 人聲來源：{vocal_src_tmd.name} (軌道: {', '.join(vocal_instruments)}, 段落: {stanzas or ['L']})")
    if vocal_only:
        print("   - 輸出模式：純人聲（略過伴奏渲染與混音）")
    else:
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

        vocal_musicxml_dir = work_dir / "vocal_parts"
        prepared_parts = prepare_vocal_musicxml_parts(raw_musicxml, vocal_musicxml_dir)
        for prepared_part in prepared_parts:
            if prepared_part.converted_rests > 0:
                print(
                    f"   ℹ️  已將 {prepared_part.part_name} 軌中 {prepared_part.converted_rests} 個無歌詞器樂音符（前奏/間奏）轉為休止符以對齊時間軸"
                )

        # 2. 渲染鋼琴伴奏 WAV（純人聲模式略過）
        piano_wav = work_dir / "piano.wav"
        if not vocal_only:
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

        vocal_tracks: list[dict[str, float | Path | str]] = []
        for index, prepared_part in enumerate(prepared_parts, start=1):
            prefix = work_dir / f"vocal_{index:02d}"
            full_lab = prefix.with_suffix(".lab")
            mono_lab = work_dir / f"vocal_{index:02d}.mono.lab"
            timing_lab = work_dir / f"vocal_{index:02d}.timing.lab"
            out_f0 = work_dir / f"vocal_{index:02d}.f0"
            out_melspec = work_dir / f"vocal_{index:02d}.melspec"
            vocal_wav = work_dir / f"vocal_{index:02d}.wav"

            print(f"🔤 [1/3] {prepared_part.part_name}：執行 musicXMLtoLabel...")
            label_res = run_cmd(
                [
                    str(neutrino_dir / "bin" / "musicXMLtoLabel"),
                    str(prepared_part.path),
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

            prepended_rest_sec = 0.0
            if (
                "Added a rest to the first measure" in combined_label_out
                or "最初の小節に休符を追加しました" in combined_label_out
            ):
                prepended_rest_sec = measure_duration_sec
                print(
                    f"   ℹ️  {prepared_part.part_name} 偵測到 NEUTRINO 自動插入前導 1 小節休止符 ({prepended_rest_sec:.4f}s)"
                )

            part_model_name = resolve_part_model(
                prepared_part.part_name,
                args.model,
                getattr(args, "part_model_overrides", {}),
            )
            part_model_dir = (model_dirs or {}).get(part_model_name, model_dir)
            print(
                f"🎤 [2/3] {prepared_part.part_name}：執行 NEUTRINO ({part_model_name})..."
            )
            neutrino_cmd = [
                str(neutrino_dir / "bin" / "neutrino"),
                str(full_lab),
                str(timing_lab),
                str(out_f0),
                str(out_melspec),
                str(vocal_wav),
                f"{part_model_dir}/",
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

            vocal_trim_sec = 0.0
            piano_delay_ms = 0.0
            if prepended_rest_sec > 0:
                first_phoneme_sec = prepended_rest_sec
                if timing_lab.exists():
                    timing_lines = timing_lab.read_text(encoding="utf-8").splitlines()
                    if timing_lines:
                        first_line = timing_lines[0].split()
                        if len(first_line) >= 3 and first_line[2] == "pau":
                            first_phoneme_sec = int(first_line[1]) / 10_000_000.0
                vocal_trim_sec = max(0.0, min(prepended_rest_sec, first_phoneme_sec - 0.030))
                piano_delay_ms = max(0.0, (prepended_rest_sec - vocal_trim_sec) * 1000.0)
                print(
                    f"   🎯 {prepared_part.part_name} 對齊校正：裁切前導空白 {vocal_trim_sec:.4f}s，伴奏基準延遲 {piano_delay_ms:.1f}ms"
                )

            vocal_max_db = detect_max_volume_db(vocal_wav)
            vocal_gain_db = (-2.0 - vocal_max_db) if vocal_max_db is not None else 0.0
            vocal_tracks.append(
                {
                    "path": vocal_wav,
                    "part_name": prepared_part.part_name,
                    "trim_sec": prepended_rest_sec if vocal_only else vocal_trim_sec,
                    "delay_ms": 0.0 if vocal_only else piano_delay_ms,
                    "gain_db": vocal_gain_db,
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_cmd = ["ffmpeg", "-y"]
        for track in vocal_tracks:
            trim_sec = float(track["trim_sec"])
            if trim_sec > 0:
                ffmpeg_cmd += ["-ss", f"{trim_sec:.6f}"]
            ffmpeg_cmd += ["-i", str(track["path"])]

        if vocal_only:
            print(f"🎚️  [3/3] 匯出純人聲至 {output_path}...")
            filter_parts = []
            for index, track in enumerate(vocal_tracks):
                vocal_filter = (
                    f"[{index}:a]volume={float(track['gain_db']):.2f}dB,"
                    f"volume={args.vocal_volume}"
                )
                if len(vocal_tracks) == 1:
                    vocal_filter += ",alimiter=limit=0.95"
                else:
                    vocal_filter += f"[v{index}];"
                filter_parts.append(vocal_filter)
            if len(vocal_tracks) > 1:
                mix_inputs = "".join(f"[v{index}]" for index in range(len(vocal_tracks)))
                filter_parts.append(
                    f"{mix_inputs}amix=inputs={len(vocal_tracks)}:duration=longest:"
                    "dropout_transition=0:normalize=0,alimiter=limit=0.95"
                )
            ffmpeg_cmd += ["-filter_complex", "".join(filter_parts)]
            if output_path.suffix.lower() == ".mp3":
                ffmpeg_cmd += ["-c:a", "libmp3lame", "-q:a", "2"]
            elif output_path.suffix.lower() == ".wav":
                ffmpeg_cmd += ["-c:a", "pcm_s16le", "-ar", "48000"]
            ffmpeg_cmd.append(str(output_path))
            run_cmd(ffmpeg_cmd)
            print(f"✅ 完成！已輸出純人聲：{output_path}\n", flush=True)
            return output_path

        # 5. 自動偵測各聲部與伴奏峰值，並以最晚的伴奏校正點統一對齊。
        piano_max_db = detect_max_volume_db(piano_wav)
        piano_gain_db = min(20.0, -4.5 - piano_max_db) if piano_max_db is not None else 10.0
        print(
            f"   🔊 音量平衡：{len(vocal_tracks)} 個人聲聲部 | "
            f"伴奏原始峰值 {piano_max_db:.1f}dB (補償 {piano_gain_db:+.1f}dB)"
            if piano_max_db is not None
            else "   🔊 音量平衡：套用預設增益"
        )

        # 6. 使用 ffmpeg 混音
        print(f"🎚️  [3/3] 使用 ffmpeg 混音輸出至 {output_path}...")
        ffmpeg_cmd += ["-i", str(piano_wav)]

        max_delay_ms = max(float(track["delay_ms"]) for track in vocal_tracks)
        filter_parts = []
        for index, track in enumerate(vocal_tracks):
            delay_ms = max_delay_ms - float(track["delay_ms"])
            vocal_filter = f"[{index}:a]volume={float(track['gain_db']):.2f}dB,volume={args.vocal_volume}"
            if delay_ms > 0.5:
                vocal_filter += f",adelay={int(round(delay_ms))}:all=1"
            vocal_filter += f"[v{index}];"
            filter_parts.append(vocal_filter)

        piano_index = len(vocal_tracks)
        piano_filter = f"[{piano_index}:a]volume={piano_gain_db:.2f}dB,volume={args.piano_volume}"
        if max_delay_ms > 0.5:
            piano_filter += f",adelay={int(round(max_delay_ms))}:all=1"
        piano_filter += "[p];"
        filter_parts.append(piano_filter)
        mix_inputs = "".join(f"[v{index}]" for index in range(len(vocal_tracks))) + "[p]"
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(vocal_tracks) + 1}:duration=longest:"
            "dropout_transition=0:normalize=0,alimiter=limit=0.95"
        )
        ffmpeg_cmd += ["-filter_complex", "".join(filter_parts)]
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
        "--part-model",
        action="append",
        default=[],
        metavar="PART=MODEL",
        help="指定聲部使用的 NEUTRINO 模型，可重複使用（例如 --part-model Piano2=NAKUMO）",
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
        "--vocal-only",
        action="store_true",
        help="僅匯出 NEUTRINO 合成之純人聲（略過伴奏渲染與混音；未指定 -o 時預設輸出 <stem>_vocal.wav）",
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

    try:
        args.part_model_overrides = parse_part_model_overrides(args.part_model)
    except ValueError as exc:
        sys.exit(f"❌ {exc}")

    model_names = {args.model, *args.part_model_overrides.values()}
    model_dirs: dict[str, Path] = {}
    available = [p.name for p in sorted((neutrino_dir / "model").iterdir()) if p.is_dir()]
    for model_name in model_names:
        candidate = neutrino_dir / "model" / model_name
        if not candidate.exists():
            sys.exit(f"❌ 找不到歌手模型 '{model_name}'（可用模型：{', '.join(available)}）")
        model_dirs[model_name] = candidate
    model_dir = model_dirs[args.model]

    target_path = Path(args.target).resolve()
    if target_path.is_dir() and not list(target_path.glob("*.tmd")):
        # 批次處理整冊或整個目錄下的所有歌曲子資料夾
        song_dirs = sorted({p.parent for p in target_path.rglob("*.tmd")})
        if not song_dirs:
            sys.exit(f"❌ 在目錄 {target_path} 下找不到任何 .tmd 檔案")
        print(f"📚 批次處理目錄：{target_path}（共 {len(song_dirs)} 首曲目）\n")
        failures: list[tuple[Path, Exception]] = []
        for idx, s_dir in enumerate(song_dirs, start=1):
            print(f"==================== [{idx}/{len(song_dirs)}] {s_dir.name} ====================", flush=True)
            try:
                render_single_song(s_dir, args, neutrino_dir, model_dir, model_dirs)
            except Exception as exc:
                failures.append((s_dir, exc))
                print(f"⚠️ 失敗，略過並繼續：{s_dir}\n{exc}\n", file=sys.stderr, flush=True)

        if failures:
            print(f"⚠️ 批次處理完成，但有 {len(failures)} 首曲目失敗：", file=sys.stderr)
            for song_dir, exc in failures:
                print(f"   - {song_dir}: {exc}", file=sys.stderr)
        else:
            print("✅ 批次處理完成，所有曲目皆成功。")
    else:
        render_single_song(target_path, args, neutrino_dir, model_dir, model_dirs)


if __name__ == "__main__":
    main()
