#!/usr/bin/env python3
"""
render_neutrino_wav.py: 使用 NEUTRINO 將 TMD 樂譜中的歌詞軌合成為純人聲 WAV。

支援輸入：
  - 歌曲資料夾路徑（自動尋找含有歌詞的 .tmd 或 *_piano.tmd）
  - 單一 .tmd 檔案路徑
  - 萬用字元（如 docs/shokacho/vol_01/*）

核心特色：
  1. 僅輸出純人聲 WAV，不渲染鋼琴伴奏，不進行伴奏混音，不壓縮為 MP3。
  2. 自動將無歌詞的器樂音符（如 Intro 前奏、間奏）轉為休止符，避免 NEUTRINO 空白歌詞崩潰，
     同時精確保留前奏與間奏的時間長度。
  3. 自動偵測並裁切 NEUTRINO 在第一小節前插入的多餘休止符，使音訊開頭與樂譜小節完全對齊。
  4. 支援多段歌詞 (L1/L2) 依播放順序自動串接，支援多聲部合唱混音與個別模型指定。
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import tempfile

# 確保可自腳本所在目錄載入共享模組
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_neutrino_mix import (
    DEFAULT_NEUTRINO_DIR,
    PreparedVocalPart,
    detect_max_volume_db,
    ensure_stanza_playback_selectors,
    expand_target_paths,
    find_lyric_instruments,
    parse_part_model_overrides,
    parse_tempo_and_meter,
    prepare_vocal_musicxml_parts,
    resolve_part_model,
    run_cmd,
    target_song_key,
)


def resolve_vocal_tmd(target: Path) -> tuple[Path, str]:
    """
    解析目標路徑，回傳 (vocal_tmd, base_stem)。
    - 若 target 為 .tmd 檔案：
      優先使用該檔案（若含有歌詞軌）；若無歌詞軌，則嘗試在同目錄下尋找含歌詞的伴生 .tmd。
    - 若 target 為資料夾：
      優先使用 *_piano.tmd（若有歌詞），否則使用主旋律 .tmd。
    """
    target = target.resolve()
    if target.is_dir():
        piano_tmds = sorted(target.glob("*_piano.tmd"))
        main_tmds = sorted(p for p in target.glob("*.tmd") if not p.name.endswith("_piano.tmd"))
        if not main_tmds and not piano_tmds:
            raise FileNotFoundError(f"在目錄 {target} 中找不到任何 .tmd 檔案")

        # 優先檢查鋼琴伴奏版是否有歌詞（例如多聲部或現代發音版）
        for ptmd in piano_tmds:
            instruments, _ = find_lyric_instruments(ptmd.read_text(encoding="utf-8"))
            if instruments:
                return ptmd, ptmd.stem.removesuffix("_piano")

        # 否則檢查主旋律 TMD
        for mtmd in main_tmds:
            instruments, _ = find_lyric_instruments(mtmd.read_text(encoding="utf-8"))
            if instruments:
                return mtmd, mtmd.stem

        raise RuntimeError(f"在目錄 {target} 中的 TMD 檔案皆找不到歌詞軌道 (L| / L1|)")

    if not target.exists():
        raise FileNotFoundError(f"找不到檔案：{target}")

    text = target.read_text(encoding="utf-8")
    instruments, _ = find_lyric_instruments(text)
    if instruments:
        base_stem = target.stem.removesuffix("_piano")
        return target, base_stem

    # 若指定檔案無歌詞，嘗試在同目錄找對應檔案
    parent = target.parent
    base_stem = target.stem.removesuffix("_piano")
    alt_tmd = parent / f"{base_stem}.tmd" if target.name.endswith("_piano.tmd") else parent / f"{base_stem}_piano.tmd"
    if alt_tmd.exists():
        alt_instruments, _ = find_lyric_instruments(alt_tmd.read_text(encoding="utf-8"))
        if alt_instruments:
            return alt_tmd, base_stem

    raise RuntimeError(f"在檔案 {target.name} 中找不到任何歌詞軌道 (L| / L1|)")


def render_single_song_wav(
    target: Path,
    args: argparse.Namespace,
    neutrino_dir: Path,
    model_dir: Path,
    model_dirs: dict[str, Path] | None = None,
) -> Path:
    """將單一歌曲目標的歌詞軌合成為純人聲 WAV 檔案。"""
    vocal_tmd, base_stem = resolve_vocal_tmd(target)
    song_dir = vocal_tmd.parent

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = song_dir / f"{base_stem}_neutrino.wav"

    if args.skip_existing and output_path.exists() and output_path.stat().st_size > 0:
        print(f"⏭️  略過已存在的人聲檔案：{output_path.name} ({song_dir.name})")
        return output_path

    vocal_tmd_text = vocal_tmd.read_text(encoding="utf-8")
    vocal_instruments, stanzas = find_lyric_instruments(vocal_tmd_text)
    if not vocal_instruments:
        raise RuntimeError(f"在 {vocal_tmd} 找不到含有歌詞 (L| / L1|) 的軌道")

    bpm, beats, beat_type = parse_tempo_and_meter(vocal_tmd_text)
    measure_duration_sec = beats * (4.0 / beat_type) * (60.0 / bpm)

    print(f"🎤 NEUTRINO 純人聲合成：{base_stem} ({song_dir.name})")
    print(f"   - 樂譜來源：{vocal_tmd.name} (軌道: {', '.join(vocal_instruments)}, 段落: {stanzas or ['L']})")
    print(f"   - 歌手模型：{args.model} | 速度：{bpm} BPM (<{beats}/{beat_type}>, 單小節 {measure_duration_sec:.4f}s)")
    print(f"   - 輸出目標：{output_path}")

    tmp_ctx = tempfile.TemporaryDirectory(prefix=f"neutrino_wav_{base_stem}_")
    work_dir = Path(tmp_ctx.name)
    if args.keep_temp:
        work_dir = Path(tempfile.mkdtemp(prefix=f"neutrino_wav_{base_stem}_"))
        tmp_ctx.cleanup()
        print(f"📂 暫存目錄：{work_dir}")

    try:
        # 1. 將 TMD 匯出為 MusicXML，展開反覆與段落選擇器
        normalized_vocal_text = ensure_stanza_playback_selectors(vocal_tmd_text, stanzas)
        temp_vocal_source = work_dir / "vocal_source.tmd"
        temp_vocal_source.write_text(normalized_vocal_text, encoding="utf-8")

        flattened_musicxml = work_dir / "flattened.musicxml"
        run_cmd(
            [
                "tmd",
                str(temp_vocal_source),
                "--flatten-repeats",
                "-x",
                str(flattened_musicxml),
            ]
        )

        # 2. 依聲部與段落拆解為個別 MusicXML
        vocal_musicxml_dir = work_dir / "vocal_parts"
        prepared_parts = prepare_vocal_musicxml_parts(flattened_musicxml, vocal_musicxml_dir)
        for prepared_part in prepared_parts:
            if prepared_part.converted_rests > 0:
                print(
                    f"   ℹ️  已將 {prepared_part.part_name} 軌中 {prepared_part.converted_rests} 個無歌詞器樂音符轉為休止符以對齊時間軸"
                )

        # 3. 呼叫 NEUTRINO 工具鏈合成音訊
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

            print(f"🔤 [1/2] {prepared_part.part_name}：執行 musicXMLtoLabel...")
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
                f"🎶 [2/2] {prepared_part.part_name}：執行 NEUTRINO 合成 ({part_model_name})..."
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
                str(args.sample_rate),
                "-b",
                str(args.bit_depth),
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

            # 計算前導休止裁切長度（若未指定 --no-trim 且偵測到前導休止）
            auto_trim_sec = 0.0
            if not args.no_trim and prepended_rest_sec > 0:
                auto_trim_sec = prepended_rest_sec
                print(f"   🎯 {prepared_part.part_name}：裁切 NEUTRINO 前導多餘空白 ({auto_trim_sec:.4f}s)")

            # 音量計算
            if args.no_normalize:
                gain_db = 0.0
            else:
                vocal_max_db = detect_max_volume_db(vocal_wav)
                gain_db = (args.target_peak - vocal_max_db) if vocal_max_db is not None else 0.0

            vocal_tracks.append(
                {
                    "path": vocal_wav,
                    "part_name": prepared_part.part_name,
                    "lyric_number": prepared_part.lyric_number or "1",
                    "leading_rest_sec": prepared_part.leading_rest_measures * measure_duration_sec,
                    "auto_trim_sec": auto_trim_sec,
                    "gain_db": gain_db,
                }
            )

        # 4. 使用 ffmpeg 混音組合各聲部與段落，輸出純人聲 WAV
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_cmd = ["ffmpeg", "-y"]
        stanza_numbers = sorted(
            {str(track["lyric_number"]) for track in vocal_tracks},
            key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
        )
        first_stanza = stanza_numbers[0] if stanza_numbers else "1"

        for track in vocal_tracks:
            trim_sec = float(track["auto_trim_sec"])
            if str(track["lyric_number"]) != first_stanza:
                trim_sec += float(track["leading_rest_sec"])
            if trim_sec > 0:
                ffmpeg_cmd += ["-ss", f"{trim_sec:.6f}"]
            ffmpeg_cmd += ["-i", str(track["path"])]

        # 組合濾波鏈
        filter_parts = []
        stanza_labels: list[str] = []
        for stanza_index, stanza_number in enumerate(stanza_numbers):
            track_indices = [
                index
                for index, track in enumerate(vocal_tracks)
                if str(track["lyric_number"]) == stanza_number
            ]
            voice_labels = []
            for index in track_indices:
                track = vocal_tracks[index]
                label = f"v{index}"
                vol_gain = float(track["gain_db"])
                filter_parts.append(
                    f"[{index}:a]volume={vol_gain:.2f}dB,volume={args.volume}[{label}]"
                )
                voice_labels.append(f"[{label}]")

            stanza_label = f"s{stanza_index}"
            if len(voice_labels) > 1:
                filter_parts.append(
                    f"{''.join(voice_labels)}amix=inputs={len(voice_labels)}:"
                    f"duration=longest:dropout_transition=0:normalize=0[{stanza_label}]"
                )
            else:
                filter_parts.append(f"{voice_labels[0]}anull[{stanza_label}]")
            stanza_labels.append(f"[{stanza_label}]")

        if len(stanza_labels) > 1:
            filter_parts.append(
                f"{''.join(stanza_labels)}concat=n={len(stanza_labels)}:v=0:a=1[vocals]"
            )
        else:
            filter_parts.append(f"{stanza_labels[0]}anull[vocals]")

        filter_parts.append("[vocals]alimiter=limit=0.98[output]")
        ffmpeg_cmd += ["-filter_complex", ";".join(filter_parts), "-map", "[output]"]

        # 設定 WAV 編碼參數
        if args.bit_depth == 24:
            ffmpeg_cmd += ["-c:a", "pcm_s24le"]
        else:
            ffmpeg_cmd += ["-c:a", "pcm_s16le"]
        ffmpeg_cmd += ["-ar", str(args.sample_rate)]
        ffmpeg_cmd.append(str(output_path))

        run_cmd(ffmpeg_cmd)
        print(f"✅ 完成！已輸出純人聲 WAV：{output_path}\n", flush=True)
        return output_path

    finally:
        if not args.keep_temp:
            tmp_ctx.cleanup()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="使用 NEUTRINO 將 TMD 樂譜中的歌詞軌合成為純人聲 WAV 檔案（不渲染伴奏、不轉 MP3）。"
    )
    parser.add_argument(
        "target",
        nargs="+",
        help="歌曲目錄、冊別目錄或 .tmd 檔案路徑；支援 *、?、[] 與 ** 萬用字元",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="MERROW",
        help="NEUTRINO 歌手模型名稱（例如 MERROW, NAKUMO, REINA, RUNO, SOMA，預設：MERROW）",
    )
    parser.add_argument(
        "--part-model",
        action="append",
        default=[],
        metavar="PART=MODEL",
        help="指定特定聲部使用的 NEUTRINO 模型（例如 --part-model Piano2=NAKUMO）",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="輸出 WAV 檔案路徑（僅在單一目標時可用；未指定時預設為 <song_dir>/<stem>_neutrino.wav）",
    )
    parser.add_argument(
        "--neutrino-dir",
        type=Path,
        default=DEFAULT_NEUTRINO_DIR,
        help=f"NEUTRINO 安裝目錄路徑（預設：{DEFAULT_NEUTRINO_DIR}）",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="輸出 WAV 取樣頻率 Hz（預設：48000）",
    )
    parser.add_argument(
        "--bit-depth",
        type=int,
        choices=[16, 24],
        default=16,
        help="輸出 WAV 位元深度（預設：16）",
    )
    parser.add_argument(
        "--style-shift",
        "-k",
        type=int,
        default=0,
        help="NEUTRINO -k style shift 參數（預設：0）",
    )
    parser.add_argument(
        "--transpose",
        "-f",
        type=int,
        default=0,
        help="NEUTRINO -f transpose 半音移調參數（預設：0）",
    )
    parser.add_argument(
        "--threads",
        "-n",
        type=int,
        default=0,
        help="NEUTRINO 執行緒數量（預設：0 = 自動使用全部 CPU 核心）",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=1.0,
        help="人聲音量倍率（預設：1.0）",
    )
    parser.add_argument(
        "--target-peak",
        type=float,
        default=-2.0,
        help="峰值正規化基準 dB（預設：-2.0 dB）",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="不進行音量峰值正規化，保留 NEUTRINO 原始音量輸出",
    )
    parser.add_argument(
        "--no-trim",
        action="store_true",
        help="不裁切 NEUTRINO 自動插入的第一小節前導空白",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="若目標輸出 WAV 已存在且非空檔案，則直接略過不重新合成",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="保留暫存檔案目錄供除錯檢視",
    )

    args = parser.parse_args()

    # 驗證 NEUTRINO 目錄與模型
    neutrino_dir: Path = args.neutrino_dir.resolve()
    if not (neutrino_dir / "bin" / "neutrino").exists():
        sys.exit(f"❌ 找不到 NEUTRINO 執行檔：{neutrino_dir / 'bin' / 'neutrino'}")

    model_dir = neutrino_dir / "model" / args.model
    if not model_dir.is_dir():
        available = [p.name for p in sorted((neutrino_dir / "model").iterdir()) if p.is_dir()]
        sys.exit(
            f"❌ 找不到歌手模型 '{args.model}'（路徑：{model_dir}）。\n"
            f"   可用模型：{', '.join(available)}"
        )

    try:
        args.part_model_overrides = parse_part_model_overrides(args.part_model)
    except ValueError as exc:
        sys.exit(f"❌ {exc}")

    model_dirs: dict[str, Path] = {args.model: model_dir}
    for model_name in set(args.part_model_overrides.values()):
        candidate = neutrino_dir / "model" / model_name
        if not candidate.is_dir():
            available = [p.name for p in sorted((neutrino_dir / "model").iterdir()) if p.is_dir()]
            sys.exit(
                f"❌ 聲部指定的歌手模型 '{model_name}' 不存在。\n"
                f"   可用模型：{', '.join(available)}"
            )
        model_dirs[model_name] = candidate

    # 展開目標路徑
    try:
        expanded_targets = expand_target_paths(args.target)
    except FileNotFoundError as exc:
        sys.exit(f"❌ {exc}")

    unique_targets: list[Path] = []
    seen_keys: set[Path] = set()
    for target_path in expanded_targets:
        key = target_song_key(target_path)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_targets.append(target_path)

    if args.output and len(unique_targets) > 1:
        sys.exit("❌ 指定多個處理目標時，不可使用 -o / --output 指定單一輸出路徑")

    failures: list[tuple[Path, Exception]] = []
    for target_path in unique_targets:
        if target_path.is_dir() and not (target_path / "index.md").exists():
            # 冊別或包含多首歌曲的大目錄
            sub_dirs = sorted(
                d for d in target_path.iterdir()
                if d.is_dir() and list(d.glob("*.tmd"))
            )
            for s_dir in sub_dirs:
                try:
                    render_single_song_wav(s_dir, args, neutrino_dir, model_dir, model_dirs)
                except Exception as exc:
                    failures.append((s_dir, exc))
                    print(f"⚠️ 失敗，略過並繼續：{s_dir}\n{exc}\n", file=sys.stderr, flush=True)
        else:
            if len(unique_targets) == 1:
                render_single_song_wav(target_path, args, neutrino_dir, model_dir, model_dirs)
            else:
                try:
                    render_single_song_wav(target_path, args, neutrino_dir, model_dir, model_dirs)
                except Exception as exc:
                    failures.append((target_path, exc))
                    print(f"⚠️ 失敗，略過並繼續：{target_path}\n{exc}\n", file=sys.stderr, flush=True)

    if failures:
        print(f"⚠️ 批次處理完成，但有 {len(failures)} 首曲目失敗：", file=sys.stderr)
        for song_dir, exc in failures:
            print(f"   - {song_dir}: {exc}", file=sys.stderr)
    elif len(unique_targets) > 1:
        print("✅ 批次處理完成，所有曲目皆成功。")


if __name__ == "__main__":
    main()
