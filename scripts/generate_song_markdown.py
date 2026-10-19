#!/usr/bin/env python3
"""Generate song Markdown pages, volume indexes, and MkDocs nav from TMD score directories.

Usage:
    # Process a single song directory:
    python3 scripts/generate_song_markdown.py docs/kogakko_shoka/grade_3/1_awoba

    # Process an entire volume or all of docs/ (with caching & parallel workers):
    python3 scripts/generate_song_markdown.py docs/
    python3 scripts/generate_song_markdown.py --force
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


TITLE_RE = re.compile(r"^\s*\*\*\s*(.*?)\s*\*\*\s*$")
CREDIT_RE = re.compile(r'^\s*~\s*"(.*?)"\s*$')
KEY_RE = re.compile(r"^\s*\?=\s*(\S+)\s*$")
TEMPO_RE = re.compile(r"^\s*!=\s*(\S+)\s*$")
METER_RE = re.compile(r"^\s*<(\d+/\d+)>\s*$")
BLOCK_COMMENT_RE = re.compile(r"/\*(.*?)\*/", re.DOTALL)
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs"
DUPLICATE_INDEX_JSON = DOCS_ROOT / "duplicate_songs.json"
DUPLICATE_INDEX_MD = DOCS_ROOT / "duplicate_songs.md"

COLLECTION_TITLES: dict[str, str] = {
    "kogakko_shoka": "《公學校唱歌》",
    "shintei_jido_shoka": "《新定兒童唱歌》",
    "shokacho": "《楊金土手抄唱歌帖》",
}

VOLUME_TITLES: dict[str, str] = {
    "grade_3": "尋常科 第三學年用",
    "grade_1_2020.006.0847.0001": "尋常科 第一學年用（2020.006.0847.0001）",
    "grade_2_2020.006.0847.0002": "尋常科 第二學年用（2020.006.0847.0002）",
    "grade_3_2020.006.0847.0003": "尋常科 第三學年用（2020.006.0847.0003）",
    "grade_4_2020.006.0847.0004": "尋常科 第四學年用（2020.006.0847.0004）",
    "grade_5_2020.006.0847.0005": "尋常科 第五學年用（2020.006.0847.0005）",
    "grade_6_2020.006.0847.0006": "尋常科 第六學年用（2020.006.0847.0006）",
    "koto_boys_2020.006.0848": "高等科 男子一二年用（2020.006.0848）",
    "koto_girls_2020.006.0849": "高等科 女子一二年用（2020.006.0849）",
    "vol_01": "原編第 1 冊 — 選定唱歌筆記帳（2020.006.0843，P113–P187）",
    "vol_02": "原編第 2 冊・II（2020.006.0843，P065–P112）",
    "vol_03": "原編第 3 冊・I（2020.006.0843，P031–P064）",
    "vol_07": "原編第 7 冊・VII — 蓬萊唱歌集・上（2020.006.0843，P224–P259）",
    "vol_08": "原編第 8 冊・VIII — 蓬萊唱歌集・下（2020.006.0843，P001–P030）",
    "vol_09": "原編第 9 冊・IX — 支那曲（2020.006.0844，P001–P014）",
    "vol_10": "原編第 10 冊・X（2020.006.0843，P188–P223）",
}

VOLUME_NAV_TITLES: dict[str, str] = {
    "grade_3": "第三學年用",
    "grade_1_2020.006.0847.0001": "尋常科 第一學年",
    "grade_2_2020.006.0847.0002": "尋常科 第二學年",
    "grade_3_2020.006.0847.0003": "尋常科 第三學年",
    "grade_4_2020.006.0847.0004": "尋常科 第四學年",
    "grade_5_2020.006.0847.0005": "尋常科 第五學年",
    "grade_6_2020.006.0847.0006": "尋常科 第六學年",
    "koto_boys_2020.006.0848": "高等科 男子一二年",
    "koto_girls_2020.006.0849": "高等科 女子一二年",
    "vol_01": "第 1 冊（選定唱歌筆記帳）",
    "vol_02": "第 2 冊（II）",
    "vol_03": "第 3 冊（I）",
    "vol_07": "第 7 冊（VII・蓬萊唱歌集上）",
    "vol_08": "第 8 冊（VIII・蓬萊唱歌集下）",
    "vol_09": "第 9 冊（IX・支那曲）",
    "vol_10": "第 10 冊（X）",
}

SHOKACHO_VOL_NOTES: dict[str, str] = {
    "vol_01": "封面頂端標註 **`1`**（`/`），扉頁（`P115.jpg`）附楊金土親筆第 1～6 冊總目錄；臺北市北門町「臺灣子供世界社」吉川精馬發行《選定 唱歌筆記帳／唱歌筆記帖》。前半為五線譜＋簡譜雙行對照儀式歌，中段貼《子供の國》童謠剪報，後半手抄自一條慎三郎《小公學校唱歌教材集》（1915）與《音楽新潮》，卷末附昭和 3 年（1928）大禮奉祝唱歌伴奏譜。",
    "vol_02": "封面頂端標註 **`2`**、左上五線譜內標註 **`II`** 及鉛筆署名 **「楊金土」**（大正 12–14 年／1923–1925 年抄錄）。收錄《大正幼年唱歌》、《愛吟抄》、**臺灣傳統北管／藝旦小曲五線譜採譜〈嘆烟花〉（`P081.jpg`）**，以及多首五線譜二部合唱／輪唱貼頁。",
    "vol_03": "封面頂端標註 **`3`**、左上五線譜內標註 **`I`** 及鉛筆署名 **「楊金土」**、左框標註 **`Y`**（大正 12 年至昭和 3 年抄錄）。收錄《共益商社唱歌教科書教師用卷二》與多份臺灣皇室行啟／祝典樂譜夾頁（1923 年〈皇太子殿下奉迎の歌〉、1925 年一條慎三郎作曲〈銀婚式奉祝行進歌〉、〈秩父宮殿下奉迎行進歌〉等）。",
    "vol_07": "封面左上五線譜內標註 **`VII`** 及鉛筆署名 **「楊金土」**（昭和 2 年／1927 年 3 月 25 日前後抄錄）。全冊系統性抄錄 1920 年代臺灣本土童謠教材 **《蓬萊唱歌集》前半部（第 14～76 頁）**，含大稻埕蓬萊公學校訓導暨第一代西畫家**陳英聲**作曲〈牛よ牛よ〉（`P246.jpg`）、臺灣本土音樂家**郭水返**作曲〈水グルマ〉（`P231.jpg`）、**黑澤隆朝**作曲〈しゃぼん玉〉（`P252.jpg`）等。",
    "vol_08": "封面左上五線譜內標註 **`VIII`** 及鉛筆署名 **「楊金土」**（昭和 2 年／1927 年 2–11 月抄錄）。接續第 7 冊繼續抄錄 **《蓬萊唱歌集》後半部（第 77～115 頁及卷末曲目）**，並穿插一條慎三郎《一條歌集》與兒童雜誌《りす》歌曲。",
    "vol_09": "被臺史博單獨編為館藏號 **`2020.006.0844`**；封面左上五線譜內標註 **`IX`** 及鉛筆署名 **「楊金土」**、右側題 **「支那曲」**（昭和 2 年／1927 年 7 月 11–13 日抄錄）。全冊以五線譜採錄 4 首傳統戲曲／器樂曲牌（皆標註「合調」）：〈1. 思春〉、〈2. 柬甫寨人の戲曲〉、〈3. 小紅桃〉、〈4. 安南行進曲〉。",
    "vol_10": "封面左上五線譜內標註 **`X`** 及鉛筆署名 **「楊金土」**、鈐紅印 **「楊」**（大正 15 年 2 月至昭和 2 年 7 月抄錄）。前半抄自《澄宮殿下御作 童謡集》（本居長世、永井幸次作曲），中後段自 1915 年《小公學校唱歌教材集》第 423 頁倒序往前抄至第 195 頁（含〈新高山〉、〈南洋の歌〉、〈鄭成功〉等）。",
}

BOOK_INFO_IMAGE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "vol_08": {
        "P001.jpg": "本冊封面，可辨識出中央的「唱歌帖」題字與五線譜、花卉裝飾圖案；右下方可見冊次標記的一部分。",
        "P002.jpg": "空白內頁，未見手寫歌名或樂譜內容。",
        "P003.jpg": "樂典／發聲說明頁，標題為「音階圖解」與「口の開きかた」，以口形圖示說明ア、エ、イ、オ、ウ等母音的發音方式，並附音階位置圖。",
        "P004.jpg": "樂譜記號對照表，說明全音符、二分音符、四分音符、八分音符與十六分音符，以及休止符、強弱記號、漸強漸弱、延長、換氣、升降記號與反覆記號等基本符號。",
        "P013.jpg": "空白五線譜頁，應作為抄寫或補錄樂譜之用；本頁未見可辨識的歌名或手寫內容。",
        "P029.jpg": "空白內頁，未見可辨識的歌名或樂譜內容。",
        "P030.jpg": "封底，中央印有大象站在地球儀上的圖案及「BK. NO. 1」字樣，未見歌曲或目錄資訊。",
    },
}


def natural_sort_key(text: str) -> list[int | str]:
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", text)]


def resolve_binary(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for fallback_dir in ("/usr/local/bin", "/opt/homebrew/bin"):
        candidate = Path(fallback_dir) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return name


def run(command: list[str], *, cwd: Path | None = None) -> str:
    """Run a command and return stdout, preserving useful diagnostics on error."""
    cmd = [resolve_binary(command[0]), *command[1:]] if command else command
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"找不到外部工具：{command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stdout or "") + (exc.stderr or "")
        raise RuntimeError(
            f"指令失敗（{exc.returncode}）：{' '.join(cmd)}\n{detail.strip()}"
        ) from exc
    return result.stdout


def choose_main_tmd(folder: Path) -> Path:
    candidates = sorted(
        path for path in folder.glob("*.tmd") if not path.name.endswith("_piano.tmd")
    )
    if not candidates:
        raise RuntimeError(f"找不到主 TMD：{folder}")
    if len(candidates) == 1:
        return candidates[0]

    matching = [path for path in candidates if path.stem == folder.name]
    if len(matching) == 1:
        return matching[0]
    names = ", ".join(path.name for path in candidates)
    raise RuntimeError(f"找到多個可能的主 TMD，無法判斷：{names}")


def choose_piano_tmd(folder: Path, main_tmd: Path) -> Path | None:
    candidates = sorted(folder.glob("*_piano.tmd"))
    if not candidates:
        return None
    matching = [path for path in candidates if path.stem == f"{main_tmd.stem}_piano"]
    return matching[0] if matching else candidates[0]


def find_scanned_images(folder: Path) -> list[Path]:
    images = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    ]
    return sorted(images, key=lambda p: (natural_sort_key(p.stem), p.suffix.lower()))


def parse_metadata(text: str) -> tuple[str, list[str], list[str], dict[str, str]]:
    title = "未命名曲目"
    credits: list[str] = []
    sources: list[str] = []
    score_info: dict[str, str] = {}
    header_text = text.split("{", 1)[0]
    for line in header_text.splitlines():
        title_match = TITLE_RE.match(line)
        if title_match and title == "未命名曲目":
            title = title_match.group(1)
        credit_match = CREDIT_RE.match(line)
        if credit_match:
            value = credit_match.group(1).strip()
            if re.search(
                r"(?:^|[\s/／（(])(詞曲|作詞|作曲|編曲|選歌|詞\s*[：:]|曲\s*[：:])",
                value,
            ):
                credits.append(value)
            else:
                sources.append(value)
        key_match = KEY_RE.match(line)
        if key_match and "key" not in score_info:
            score_info["key"] = key_match.group(1)
        tempo_match = TEMPO_RE.match(line)
        if tempo_match and "tempo" not in score_info:
            score_info["tempo"] = tempo_match.group(1)
        meter_match = METER_RE.match(line)
        if meter_match and "meter" not in score_info:
            score_info["meter"] = meter_match.group(1)
    return title, credits, sources, score_info


def clean_comment(block: str) -> list[str]:
    lines = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("*"):
            line = line[1:].strip()
        if line and set(line) <= {"=", "-", "*"}:
            continue
        lines.append(line)
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def extract_notes_and_lyrics(
    main_text: str,
    piano_text: str = "",
    sources: list[str] | None = None,
    score_info: dict[str, str] | None = None,
) -> tuple[str, str]:
    header_text = main_text.split("{", 1)[0]
    comments = [clean_comment(block) for block in BLOCK_COMMENT_RE.findall(header_text)]
    comments = [block for block in comments if any(line.strip() for line in block)]

    note_markers = (
        "曲目說明",
        "版本說明",
        "出處註記",
        "調性與拍號",
        "原書資訊",
        "Reference Materials",
        "Source:",
        "Key:",
        "掃描檔",
    )
    explicit_lyric_headers = ("【原書歌詞", "【歌詞全文", "Lyrics:")

    note_texts: list[str] = []
    lyric_texts: list[str] = []

    for block in comments:
        joined = "\n".join(block)
        has_note = any(marker in joined for marker in note_markers)
        has_explicit_lyric = any(marker in joined for marker in explicit_lyric_headers)

        if has_explicit_lyric:
            split_idx = 0
            for index, line in enumerate(block):
                if any(marker in line for marker in explicit_lyric_headers):
                    split_idx = index
                    break
            note_part = [line for line in block[:split_idx] if line]
            lyric_part = [
                line
                for line in block[split_idx + 1 :]
                if not re.match(r"^\s*[（(]語譯", line)
            ]
            if note_part:
                note_texts.append("\n".join(note_part).strip())
            if lyric_part:
                lyric_texts.append("\n".join(lyric_part).strip())
        elif has_note:
            split_idx = None
            for index, line in enumerate(block):
                if index > 0 and re.match(
                    r"^(?:[一二三四五六七八九十]+(?:\s+|、|　|$)|[（(][一二三四五六七八九十1-9][)）]|1[\.\s])",
                    line,
                ):
                    split_idx = index
                    break
            if split_idx is None:
                for index, line in enumerate(block):
                    if index > 0 and not line.strip():
                        split_idx = index + 1
                        break
            if split_idx is not None and split_idx < len(block):
                note_part = [line for line in block[:split_idx] if line]
                lyric_part = [
                    line
                    for line in block[split_idx:]
                    if not re.match(r"^\s*[（(]語譯", line)
                ]
                if note_part:
                    note_texts.append("\n".join(note_part).strip())
                if lyric_part:
                    lyric_texts.append("\n".join(lyric_part).strip())
            else:
                note_texts.append("\n".join(block).strip())
        else:
            cleaned_lyrics = [
                line for line in block if not re.match(r"^\s*[（(]語譯", line)
            ]
            lyric_texts.append("\n".join(cleaned_lyrics).strip())

    if piano_text:
        piano_header = piano_text.split("{", 1)[0]
        for block in [clean_comment(b) for b in BLOCK_COMMENT_RE.findall(piano_header)]:
            joined = "\n".join(block)
            if "編曲說明" in joined:
                arr_lines: list[str] = []
                in_arr = False
                for line in block:
                    if "編曲說明" in line:
                        in_arr = True
                    elif in_arr and (
                        line.startswith("【")
                        or any(m in line for m in explicit_lyric_headers)
                    ):
                        break
                    if in_arr and line:
                        arr_lines.append(line)
                if arr_lines:
                    arr_text = "\n".join(arr_lines).strip()
                    if arr_text not in note_texts:
                        note_texts.append(arr_text)

    if not note_texts and (sources or score_info):
        fallback_lines: list[str] = []
        if sources:
            fallback_lines.extend(f"・出處：{src}" for src in sources)
        if score_info:
            parts = []
            if "key" in score_info:
                parts.append(f"調號 ?= {score_info['key']}")
            if "meter" in score_info:
                parts.append(f"拍號 <{score_info['meter']}>")
            if "tempo" in score_info:
                parts.append(f"速度 != {score_info['tempo']}")
            if parts:
                fallback_lines.append(f"・調性與拍號：{'，'.join(parts)}")
        if fallback_lines:
            note_texts.append("\n".join(fallback_lines))

    return "\n\n".join(note_texts).strip(), "\n\n".join(lyric_texts).strip()


def is_up_to_date(target: Path, source: Path) -> bool:
    if not target.exists() or target.stat().st_size == 0:
        return False
    return target.stat().st_mtime >= source.stat().st_mtime


def render_analysis(main_tmd: Path, folder: Path) -> str:
    return run(["tmd", "inspect", str(main_tmd), "--locale", "zh-Hant"], cwd=folder)


def render_studio_url(tmd_file: Path, folder: Path) -> str:
    return run(["tmd", "studio-url", str(tmd_file)], cwd=folder).strip()


def render_cross_references(folder: Path) -> str:
    """Return a Markdown section linking to duplicate/same-title songs across textbooks."""
    if not DUPLICATE_INDEX_JSON.is_file():
        return ""
    try:
        rel_dir = folder.resolve().relative_to(DOCS_ROOT.resolve()).as_posix()
    except ValueError:
        return ""

    data = json.loads(DUPLICATE_INDEX_JSON.read_text(encoding="utf-8"))
    matched_entry = None
    matched_cluster = None
    for cluster in data.get("clusters", []):
        for entry in cluster.get("entries", []):
            if entry.get("rel_dir") == rel_dir:
                matched_entry = entry
                matched_cluster = cluster
                break
        if matched_entry:
            break

    if not matched_entry or not matched_entry.get("peers"):
        return ""

    lines = [
        "## 跨冊／重複收錄參照",
        "",
        f"> {matched_cluster.get('description', '')}",
        "",
    ]
    for peer in matched_entry["peers"]:
        peer_md_abs = DOCS_ROOT / peer["md_file"]
        peer_tmd_abs = DOCS_ROOT / peer["tmd_file"]
        rel_md = Path(os.path.relpath(peer_md_abs, folder)).as_posix()
        rel_tmd = Path(os.path.relpath(peer_tmd_abs, folder)).as_posix()
        relation = peer.get("relation", "參照")
        book_label = peer.get("book_label", "")
        raw_title = peer.get("raw_title", peer.get("jp_title", ""))
        key_meter = f"`{peer.get('key', '?')}` / `{peer.get('meter', '?')}`"
        lines.append(
            f"- **[{relation}]** {book_label}：[**〈{raw_title}〉**]({rel_md})"
            f"（{key_meter} — [原始 TMD]({rel_tmd})）"
        )

    rel_index_md = Path(os.path.relpath(DUPLICATE_INDEX_MD, folder)).as_posix()
    lines.append(f"- 總表：[跨冊重複與同名歌曲總索引]({rel_index_md})")
    return "\n".join(lines) + "\n\n"


def generate_song_folder(
    folder: Path,
    *,
    keep_wav: bool = False,
    soundfont: Path | None = None,
    force: bool = False,
    no_audio: bool = False,
) -> Path:
    folder = folder.resolve()
    main_tmd = choose_main_tmd(folder)
    piano_tmd = choose_piano_tmd(folder, main_tmd)
    main_text = main_tmd.read_text(encoding="utf-8")
    piano_text = piano_tmd.read_text(encoding="utf-8") if piano_tmd else ""

    title, credits, sources, score_info = parse_metadata(main_text)
    notes, lyrics = extract_notes_and_lyrics(main_text, piano_text, sources, score_info)

    stem = main_tmd.stem
    abc_path = folder / f"{stem}.abc"
    mp3_path = folder / f"{stem}.mp3"
    wav_path = folder / f"{stem}.wav"
    markdown_path = folder / "index.md"
    legacy_md_path = folder / f"{stem}.md"

    if force or not is_up_to_date(abc_path, main_tmd):
        run(["tmd", str(main_tmd), "-a", str(abc_path)], cwd=folder)

    analysis = render_analysis(main_tmd, folder)

    audio_html = "*找不到鋼琴伴奏版 TMD，未產生音訊。*"
    if piano_tmd:
        if not no_audio and (force or not is_up_to_date(mp3_path, piano_tmd)):
            render_command = ["tmd", str(piano_tmd), "-w", str(wav_path)]
            if soundfont:
                render_command.extend(["--soundfont", str(soundfont.resolve())])
            run(render_command, cwd=folder)
            run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(wav_path),
                    "-codec:a",
                    "libmp3lame",
                    "-q:a",
                    "2",
                    str(mp3_path),
                ],
                cwd=folder,
            )
            if not keep_wav:
                wav_path.unlink(missing_ok=True)
        if mp3_path.exists():
            audio_html = f'<audio controls src="{html.escape(mp3_path.name)}"></audio>'
        else:
            audio_html = "*已略過音訊渲染（尚未產生 MP3）。*"

    meta_items = list(credits) + [s for s in sources if s not in credits]
    credits_block = (
        "\n".join(f"- {item}" for item in meta_items)
        or "- 詞曲作者：未在 TMD metadata 中提供"
    )
    notes_block = notes or "（TMD 檔案未包含額外 note）"
    lyrics_block = lyrics or "（TMD 檔案未包含歌詞註解）"
    abc_raw = abc_path.read_text(encoding="utf-8")
    abc = "\n".join(line for line in abc_raw.splitlines() if line.strip())
    if abc + "\n" != abc_raw:
        abc_path.write_text(abc + "\n", encoding="utf-8")

    images = find_scanned_images(folder)
    images_section = ""
    if images:
        img_lines = [f"![{img.name}]({img.name})" for img in images]
        images_section = "\n## 原書掃描頁\n\n" + "\n\n".join(img_lines) + "\n"

    main_studio_url = render_studio_url(main_tmd, folder)
    tmd_links = [
        f"- [主旋律 TMD 檔案]({main_tmd.name}) [[在 TMD Studio 編輯]({main_studio_url})]"
    ]
    if piano_tmd:
        piano_studio_url = render_studio_url(piano_tmd, folder)
        tmd_links.append(
            f"- [鋼琴伴奏 TMD 檔案]({piano_tmd.name}) [[在 TMD Studio 編輯]({piano_studio_url})]"
        )
    tmd_links_block = "\n".join(tmd_links)
    cross_ref_section = render_cross_references(folder)

    markdown = f"""# {title}

{audio_html}

{credits_block}

## 說明

{notes_block}

{cross_ref_section}## 歌詞

```text
{lyrics_block}
```

## ABC

```abc
{abc.rstrip()}
```

## TMD 檔案連結

{tmd_links_block}

## 分析

```text
{analysis.rstrip()}
```

{images_section}

"""
    markdown_path.write_text(markdown, encoding="utf-8")
    if legacy_md_path.exists() and legacy_md_path != markdown_path:
        legacy_md_path.unlink()
    return markdown_path


def generate_book_info_folder(folder: Path) -> Path:
    folder = folder.resolve()
    vol_name = folder.parent.name
    col_name = folder.parent.parent.name
    col_title = COLLECTION_TITLES.get(col_name, col_name)
    vol_title = VOLUME_TITLES.get(vol_name, vol_name)

    images = find_scanned_images(folder)
    descriptions = BOOK_INFO_IMAGE_DESCRIPTIONS.get(vol_name, {})
    img_blocks = []
    for img in images:
        description = descriptions.get(img.name)
        block = f"### {img.name}\n\n"
        if description:
            block += f"{description}\n\n"
        block += f"![{img.name}]({img.name})"
        img_blocks.append(block)
    images_md = "\n\n".join(img_blocks) if img_blocks else "*（無掃描圖檔）*"

    markdown = f"""# 書訊與卷首／卷末掃描頁 — {col_title} {vol_title}

本頁收錄本冊之封面、扉頁、目次（もくろく）、樂典大要、版權頁與封底等原書掃描圖檔（共 {len(images)} 頁）。

{images_md}
"""
    output = folder / "index.md"
    output.write_text(markdown, encoding="utf-8")
    return output


def classify_song_section(col_name: str, vol_name: str, folder_name: str) -> tuple[str | None, str | None, str]:
    """Return (year_heading, section_heading, number_label) for a song directory."""
    parts = folder_name.split("_")
    if col_name == "kogakko_shoka":
        num = f"第 {int(parts[0])} 課" if parts[0].isdigit() else parts[0]
        return None, None, num

    if col_name == "shokacho":
        if folder_name.startswith("0844_p"):
            num = parts[1].upper()
        elif parts[0].lower().startswith("p"):
            num = parts[0].upper()
        else:
            num = parts[0]
        return None, None, num

    if vol_name.startswith("koto_"):
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
            yr = parts[0]
            cat = parts[1]
            num = f"({int(parts[2])})"
            year_label = "高等科 第一學年" if yr == "1" else "高等科 第二學年"
            if cat == "1":
                sec_label = "第一學期"
            elif cat == "2":
                sec_label = "第二學期"
            elif cat == "3":
                sec_label = "第三學期"
            elif yr == "1" and cat == "4":
                sec_label = "輪唱"
            elif (yr == "1" and cat == "5") or (yr == "2" and cat == "4"):
                sec_label = "重音（合唱）"
            else:
                sec_label = f"單元 {cat}"
            return year_label, sec_label, num

    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        cat = parts[0]
        num = f"({int(parts[1])})"
        sec_map = {
            "0": "儀式歌",
            "1": "第一學期",
            "2": "第二學期",
            "3": "第三學期",
            "4": "參考教材",
        }
        return None, sec_map.get(cat, f"單元 {cat}"), num

    return None, None, folder_name


def format_song_table_row(sdir: Path, num_label: str) -> str:
    main_tmd = choose_main_tmd(sdir)
    title, credits, _, score_info = parse_metadata(
        main_tmd.read_text(encoding="utf-8")
    )
    credit_str = " / ".join(credits) if credits else "—"
    info_parts = []
    if score_info.get("key"):
        info_parts.append(f"`?={score_info['key']}`")
    if score_info.get("meter"):
        info_parts.append(f"`<{score_info['meter']}>`")
    if score_info.get("tempo"):
        info_parts.append(f"`!={score_info['tempo']}`")
    info_str = " ".join(info_parts) if info_parts else "—"
    imgs = find_scanned_images(sdir)
    img_str = ", ".join(img.name for img in imgs) if imgs else "—"
    return f"| {num_label} | [**{title}**]({sdir.name}/index.md) | {credit_str} | {info_str} | {img_str} |"


def generate_volume_index(vol_dir: Path) -> Path:
    vol_dir = vol_dir.resolve()
    vol_name = vol_dir.name
    col_name = vol_dir.parent.name
    col_title = COLLECTION_TITLES.get(col_name, col_name)
    vol_title = VOLUME_TITLES.get(vol_name, vol_name)

    song_dirs = sorted(
        (
            d
            for d in vol_dir.iterdir()
            if d.is_dir() and d.name != "0_book_info" and list(d.glob("*.tmd"))
        ),
        key=lambda d: natural_sort_key(d.name),
    )

    lines = [
        f"# {col_title} {vol_title}",
        "",
    ]

    if col_name == "shokacho" and vol_name in SHOKACHO_VOL_NOTES:
        lines.extend(
            [
                f"> {SHOKACHO_VOL_NOTES[vol_name]}",
                "",
                "- 📄 **[《楊金土手抄唱歌帖》考證與研究筆記（含全 10 冊結構與 `P115.jpg` 第 1–6 冊親筆總目錄）](../research_notes.md)**",
            ]
        )

    book_info_dir = vol_dir / "0_book_info"
    if book_info_dir.is_dir():
        img_count = len(find_scanned_images(book_info_dir))
        lines.extend(
            [
                f"- 📖 **[書訊與卷首／卷末掃描頁（共 {img_count} 頁）](0_book_info/index.md)**",
                "",
            ]
        )

    if col_name in ("kogakko_shoka", "shokacho"):
        first_col = "課次" if col_name == "kogakko_shoka" else "原書頁碼"
        lines.extend(
            [
                f"## 曲目列表（共 {len(song_dirs)} 首）",
                "",
                f"| {first_col} | 曲名 | 詞曲 / 出處 | 調號・拍號・速度 | 掃描頁 |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ]
        )
        for sdir in song_dirs:
            _, _, num_label = classify_song_section(col_name, vol_name, sdir.name)
            lines.append(format_song_table_row(sdir, num_label))
        lines.append("")
    else:
        # Group by (year_heading, section_heading) preserving order
        groups: list[tuple[str | None, str | None, list[tuple[Path, str]]]] = []
        for sdir in song_dirs:
            yr_head, sec_head, num_label = classify_song_section(
                col_name, vol_name, sdir.name
            )
            if not groups or groups[-1][0] != yr_head or groups[-1][1] != sec_head:
                groups.append((yr_head, sec_head, []))
            groups[-1][2].append((sdir, num_label))

        has_years = any(g[0] is not None for g in groups)
        if not has_years:
            summary_parts = [
                f"{sec} {len(items)} 首" for _, sec, items in groups if sec
            ]
            summary_str = f"（{'、'.join(summary_parts)}）" if summary_parts else ""
            lines.extend(
                [
                    f"本冊共收錄 **{len(song_dirs)} 首**曲目{summary_str}。",
                    "",
                ]
            )
            for _, sec_head, items in groups:
                lines.extend(
                    [
                        f"## {sec_head}（共 {len(items)} 首）",
                        "",
                        "| 編號 | 曲名 | 詞曲 / 出處 | 調號・拍號・速度 | 掃描頁 |",
                        "| :--- | :--- | :--- | :--- | :--- |",
                    ]
                )
                for sdir, num_label in items:
                    lines.append(format_song_table_row(sdir, num_label))
                lines.append("")
        else:
            # Koto volumes have Year 1 and Year 2
            year_counts: dict[str, int] = {}
            for yr_head, _, items in groups:
                if yr_head:
                    year_counts[yr_head] = year_counts.get(yr_head, 0) + len(items)
            summary_parts = [f"{yr} {cnt} 首" for yr, cnt in year_counts.items()]
            summary_str = f"（{'、'.join(summary_parts)}）" if summary_parts else ""
            lines.extend(
                [
                    f"本冊共收錄 **{len(song_dirs)} 首**曲目{summary_str}。",
                    "",
                ]
            )
            current_year: str | None = None
            for yr_head, sec_head, items in groups:
                if yr_head != current_year:
                    current_year = yr_head
                    lines.extend(
                        [
                            f"## {yr_head}（共 {year_counts.get(yr_head or '', 0)} 首）",
                            "",
                        ]
                    )
                lines.extend(
                    [
                        f"### {sec_head}（共 {len(items)} 首）",
                        "",
                        "| 編號 | 曲名 | 詞曲 / 出處 | 調號・拍號・速度 | 掃描頁 |",
                        "| :--- | :--- | :--- | :--- | :--- |",
                    ]
                )
                for sdir, num_label in items:
                    lines.append(format_song_table_row(sdir, num_label))
                lines.append("")

    output = vol_dir / "index.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def update_site_indexes_and_mkdocs(docs_dir: Path, mkdocs_path: Path) -> None:
    docs_dir = docs_dir.resolve()
    home_lines = [
        "# Re:shoka — 百年歌曲重建計畫",
        "",
        "日治時期臺灣公學校與小學校音樂教材數位化、TMD 樂譜重建、雙手鋼琴伴奏編曲與調性分析資料庫。",
        "",
    ]

    nav_lines = [
        "site_name: Re:shoka — 百年歌曲重建計畫",
        "site_description: 日治時期臺灣公學校與小學校音樂教材數位化、TMD 樂譜重建、雙手鋼琴伴奏編曲與調性分析資料庫。",
        "site_author: TMD Contributors",
        "site_url: https://tmdlang.github.io/reshoka/",
        "copyright: Released under the MIT License. In memory of Chen, Chih-Han / aguai (阿怪, 1974–2019)",
        "# repo_url: https://github.com/tmdlang/reshoka",
        "",
        "theme:",
        "  name: material",
        "  language: zh-Hant",
        "  palette:",
        "    # Light mode",
        '    - media: "(prefers-color-scheme: light)"',
        "      scheme: default",
        "      primary: white",
        "      accent: indigo",
        "      toggle:",
        "        icon: material/brightness-7",
        "        name: 切換為深色模式",
        "    # Dark mode",
        '    - media: "(prefers-color-scheme: dark)"',
        "      scheme: slate",
        "      primary: black",
        "      accent: indigo",
        "      toggle:",
        "        icon: material/brightness-4",
        "        name: 切換為淺色模式",
        "  features:",
        "    - navigation.instant",
        "    - navigation.tracking",
        "    - navigation.sections",
        "    - navigation.top",
        "    - search.suggest",
        "    - search.highlight",
        "    - content.code.copy",
        "",
        "markdown_extensions:",
        "  - admonition",
        "  - pymdownx.details",
        "  - pymdownx.superfences:",
        "      custom_fences:",
        "        - name: mermaid",
        "          class: mermaid",
        "          format: !!python/name:pymdownx.superfences.fence_code_format",
        "        - name: abc",
        "          class: abc",
        "          format: !!python/name:pymdownx.superfences.fence_code_format",
        "  - pymdownx.highlight:",
        "      anchor_linenums: true",
        "      line_spans: __span",
        "      pygments_lang_class: true",
        "  - pymdownx.inlinehilite",
        "  - pymdownx.snippets",
        "  - pymdownx.tabbed:",
        "      alternate_style: true",
        "  - attr_list",
        "  - md_in_html",
        "  - tables",
        "  - toc:",
        "      permalink: true",
        "",
        "extra_css:",
        "  - stylesheets/extra.css",
        "",
        "extra_javascript:",
        "  - https://cdn.jsdelivr.net/npm/abcjs@6.4.4/dist/abcjs-basic-min.js",
        "  - javascripts/abc-render.js",
        "",
        "nav:",
        "  - 首頁: index.md",
        "  - 跨冊重複與同名歌曲索引: duplicate_songs.md",
    ]

    collections = [
        ("kogakko_shoka", "公學校唱歌"),
        ("shintei_jido_shoka", "新定兒童唱歌"),
        ("shokacho", "楊金土手抄唱歌帖"),
    ]

    for col_slug, col_short in collections:
        col_dir = docs_dir / col_slug
        if not col_dir.is_dir():
            continue
        col_title = COLLECTION_TITLES.get(col_slug, col_short)
        home_lines.append(f"## {col_title}")
        home_lines.append("")
        nav_lines.append(f"  - {col_short}:")
        if col_slug == "shokacho" and (col_dir / "research_notes.md").exists():
            nav_lines.append("      - 考證與研究筆記: shokacho/research_notes.md")

        vol_dirs = sorted(
            (d for d in col_dir.iterdir() if d.is_dir()),
            key=lambda d: natural_sort_key(d.name),
        )
        for vol_dir in vol_dirs:
            generate_volume_index(vol_dir)
            vol_title = VOLUME_TITLES.get(vol_dir.name, vol_dir.name)
            vol_nav_title = VOLUME_NAV_TITLES.get(vol_dir.name, vol_dir.name)
            song_dirs = sorted(
                (
                    d
                    for d in vol_dir.iterdir()
                    if d.is_dir() and d.name != "0_book_info" and list(d.glob("*.tmd"))
                ),
                key=lambda d: natural_sort_key(d.name),
            )
            home_lines.append(
                f"- [**{vol_title}**]({col_slug}/{vol_dir.name}/index.md)（共 {len(song_dirs)} 首）"
            )

            nav_lines.append(f"      - {vol_nav_title}:")
            nav_lines.append(
                f"          - 總覽: {col_slug}/{vol_dir.name}/index.md"
            )
            if (vol_dir / "0_book_info" / "index.md").exists():
                nav_lines.append(
                    f"          - 書訊與掃描頁: {col_slug}/{vol_dir.name}/0_book_info/index.md"
                )
            for sdir in song_dirs:
                main_tmd = choose_main_tmd(sdir)
                title, _, _, _ = parse_metadata(main_tmd.read_text(encoding="utf-8"))
                parts = sdir.name.split("_")
                if col_slug == "shokacho":
                    prefix = parts[1].upper() if sdir.name.startswith("0844_p") else parts[0].upper()
                elif len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    if len(parts) >= 4 and parts[2].isdigit():
                        prefix = f"{parts[0]}-{parts[1]}-{parts[2]}"
                    else:
                        prefix = f"{parts[0]}-{parts[1]}"
                else:
                    prefix = parts[0]
                label = f"{prefix} {title}".replace(":", "：").replace('"', '\\"')
                nav_lines.append(
                    f'          - "{label}": {col_slug}/{vol_dir.name}/{sdir.name}/index.md'
                )
        home_lines.append("")

    index_md = docs_dir / "index.md"
    if not index_md.exists():
        index_md.write_text("\n".join(home_lines), encoding="utf-8")
    mkdocs_path.write_text("\n".join(nav_lines) + "\n", encoding="utf-8")


def discover_targets(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """Return (song_folders, book_info_folders, volume_folders) under root."""
    root = root.resolve()
    if root.name == "0_book_info":
        return [], [root], []
    if list(root.glob("*.tmd")):
        return [root], [], []

    song_folders: list[Path] = []
    book_info_folders: list[Path] = []
    volume_folders: set[Path] = set()

    for tmd in root.rglob("*.tmd"):
        if not tmd.name.endswith("_piano.tmd"):
            song_folders.append(tmd.parent)
            volume_folders.add(tmd.parent.parent)

    for bdir in root.rglob("0_book_info"):
        if bdir.is_dir():
            book_info_folders.append(bdir)
            volume_folders.add(bdir.parent)

    song_folders = sorted(set(song_folders), key=lambda p: natural_sort_key(str(p)))
    book_info_folders = sorted(
        set(book_info_folders), key=lambda p: natural_sort_key(str(p))
    )
    vol_list = sorted(volume_folders, key=lambda p: natural_sort_key(str(p)))
    return song_folders, book_info_folders, vol_list


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("docs"),
        help="要處理的單曲資料夾、冊別資料夾或 docs 根目錄（預設：docs）",
    )
    parser.add_argument("--keep-wav", action="store_true", help="保留中間 WAV 檔")
    parser.add_argument(
        "--soundfont",
        type=Path,
        help="傳給 tmd -w 的 SoundFont（.sf2/.dls）路徑",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="強制重新轉檔所有 .abc 與 .mp3（忽略修改時間快取）",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="略過 WAV/MP3 音訊渲染（僅產生 .abc 與 Markdown）",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=os.cpu_count() or 4,
        help="批次處理時的平行執行緒數量",
    )
    args = parser.parse_args()

    target = args.directory.resolve()
    if not target.is_dir():
        print(f"錯誤：不是資料夾：{target}", file=sys.stderr)
        return 1

    song_folders, book_info_folders, volume_folders = discover_targets(target)
    if not song_folders and not book_info_folders:
        print(f"錯誤：在 {target} 下找不到任何 TMD 曲目或 0_book_info 資料夾", file=sys.stderr)
        return 1

    for bdir in book_info_folders:
        out = generate_book_info_folder(bdir)
        print(f"[書訊] 已產生：{out}")

    errors: list[str] = []
    if len(song_folders) == 1:
        try:
            out = generate_song_folder(
                song_folders[0],
                keep_wav=args.keep_wav,
                soundfont=args.soundfont,
                force=args.force,
                no_audio=args.no_audio,
            )
            print(f"[單曲] 已產生：{out}")
        except RuntimeError as exc:
            print(f"錯誤：{exc}", file=sys.stderr)
            return 1
    elif song_folders:
        total = len(song_folders)
        print(f"開始批次處理 {total} 首曲目（jobs={args.jobs}, force={args.force}）...")
        done = 0
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_to_folder = {
                executor.submit(
                    generate_song_folder,
                    folder,
                    keep_wav=args.keep_wav,
                    soundfont=args.soundfont,
                    force=args.force,
                    no_audio=args.no_audio,
                ): folder
                for folder in song_folders
            }
            for future in as_completed(future_to_folder):
                folder = future_to_folder[future]
                done += 1
                try:
                    out = future.result()
                    if done % 25 == 0 or done == total:
                        print(f"  進度：{done}/{total}（最新：{folder.name}）")
                except Exception as exc:
                    err_msg = f"{folder}: {exc}"
                    errors.append(err_msg)
                    print(f"  [失敗] {err_msg}", file=sys.stderr)

    for vdir in volume_folders:
        out = generate_volume_index(vdir)
        print(f"[冊別總覽] 已產生：{out}")

    repo_root = Path(__file__).resolve().parent.parent
    docs_root = repo_root / "docs"
    mkdocs_yml = repo_root / "mkdocs.yml"
    if target == docs_root or target == repo_root or len(volume_folders) > 1:
        update_site_indexes_and_mkdocs(docs_root, mkdocs_yml)
        print(f"[網站導覽] 已更新：{docs_root / 'index.md'} 與 {mkdocs_yml}")

    if errors:
        print(f"\n完成，但有 {len(errors)} 首發生錯誤：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
