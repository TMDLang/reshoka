"""TMD CLI rendering (ABC, tonal analysis, Studio URL, WAV/MP3 audio, and NEUTRINO dual player)."""

from __future__ import annotations

import html
from pathlib import Path
import re
import subprocess

from .utils import is_up_to_date, run


def render_analysis(main_tmd: Path, folder: Path) -> str:
    return run(["tmd", "inspect", str(main_tmd), "--locale", "zh-Hant"], cwd=folder)


def render_studio_url(tmd_file: Path, folder: Path) -> str:
    return run(["tmd", "studio-url", str(tmd_file)], cwd=folder).strip()


def render_abc(
    main_tmd: Path, abc_path: Path, folder: Path, *, force: bool = False
) -> str:
    if force or not is_up_to_date(abc_path, main_tmd):
        run(["tmd", str(main_tmd), "-a", str(abc_path)], cwd=folder)
    abc_raw = abc_path.read_text(encoding="utf-8")
    abc = "\n".join(line for line in abc_raw.splitlines() if line.strip())
    if abc + "\n" != abc_raw:
        abc_path.write_text(abc + "\n", encoding="utf-8")
    return abc


def render_song_audio(
    folder: Path,
    stem: str,
    main_tmd: Path,
    piano_tmd: Path | None,
    *,
    keep_wav: bool = False,
    soundfont: Path | None = None,
    force: bool = False,
    no_audio: bool = False,
) -> tuple[Path | None, bool, str]:
    """Render MP3 audio if needed and return (audio_path, audio_is_piano, audio_html)."""
    mp3_path = folder / f"{stem}.mp3"
    wav_path = folder / f"{stem}.wav"
    audio_html = "*尚未產生音訊。*"

    # Prefer piano accompaniment.  If it is unavailable, keep an existing
    # original MP3; otherwise render the main melody TMD as a fallback.
    render_tmd = piano_tmd or main_tmd
    should_render_fallback = piano_tmd is not None or not mp3_path.exists()
    if (
        not no_audio
        and should_render_fallback
        and (force or not is_up_to_date(mp3_path, render_tmd))
    ):
        render_command = ["tmd", str(render_tmd), "-w", str(wav_path)]
        if soundfont:
            render_command.extend(["--soundfont", str(soundfont.resolve())])
        run(render_command, cwd=folder)

        # 偵測 WAV 峰值音量並線性增益至 -1.5 dB（保留曲內 mf/f 強弱對比，解決 tmd -w 預設音量過小問題）
        vol_proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-i",
                str(wav_path),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            cwd=folder,
            capture_output=True,
            text=True,
        )
        m_max = re.search(
            r"max_volume:\s*([-\d.]+)\s*dB",
            (vol_proc.stderr or "") + (vol_proc.stdout or ""),
        )
        gain_db = 0.0
        if m_max:
            max_vol = float(m_max.group(1))
            if max_vol < -1.5:
                gain_db = min(20.0, -1.5 - max_vol)

        ffmpeg_mp3_cmd = ["ffmpeg", "-y", "-i", str(wav_path)]
        if gain_db > 0.1:
            ffmpeg_mp3_cmd.extend(
                ["-af", f"volume={gain_db:.2f}dB,alimiter=limit=0.95"]
            )
        ffmpeg_mp3_cmd.extend(["-codec:a", "libmp3lame", "-q:a", "2", str(mp3_path)])
        run(ffmpeg_mp3_cmd, cwd=folder)
        if not keep_wav:
            wav_path.unlink(missing_ok=True)

    # Prefer the generated piano accompaniment, but keep using a pre-existing
    # same-stem MP3 when no accompaniment TMD is available (or rendering was
    # skipped/failed).  The latter is the original audio supplied with the song.
    audio_path = mp3_path if mp3_path.exists() else None
    neutrino_mp3_path = folder / f"{stem}_neutrino.mp3"
    if not neutrino_mp3_path.exists():
        neutrino_candidates = sorted(folder.glob("*_neutrino.mp3"))
        if neutrino_candidates:
            neutrino_mp3_path = neutrino_candidates[0]
    has_neutrino_audio = neutrino_mp3_path.exists()

    audio_is_piano = piano_tmd is not None and audio_path is not None
    if audio_path and has_neutrino_audio:
        piano_label = "鋼琴伴奏版" if audio_is_piano else "原曲伴奏版"
        audio_html = (
            f'- **NEUTRINO 歌聲合成版**：<br><audio controls src="{html.escape(neutrino_mp3_path.name)}"></audio>\n'
            f'- **{piano_label}**：<br><audio controls src="{html.escape(audio_path.name)}"></audio>\n'
        )
    elif has_neutrino_audio:
        audio_path = neutrino_mp3_path
        audio_html = (
            f'<audio controls src="{html.escape(neutrino_mp3_path.name)}"></audio>'
        )
    elif audio_path:
        audio_html = f'<audio controls src="{html.escape(audio_path.name)}"></audio>'
    elif piano_tmd:
        audio_html = "*已略過音訊渲染（尚未產生 MP3）。*"

    return audio_path, audio_is_piano, audio_html
