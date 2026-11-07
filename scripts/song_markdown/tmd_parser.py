"""TMD header metadata, block comments, and lyric extraction."""

from __future__ import annotations

import re

TITLE_RE = re.compile(r"^\s*\*\*\s*(.*?)\s*\*\*\s*$")
CREDIT_RE = re.compile(r'^\s*~\s*"(.*?)"\s*$')
TAG_RE = re.compile(r"^tag:\s*[^\s:]+:[^\s:]+$")
KEY_RE = re.compile(r"^\s*\?=\s*(\S+)\s*$")
TEMPO_RE = re.compile(r"^\s*!=\s*(\S+)\s*$")
METER_RE = re.compile(r"^\s*<(\d+/\d+)>\s*$")
BLOCK_COMMENT_RE = re.compile(r"/\*(.*?)\*/", re.DOTALL)


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
            if TAG_RE.match(value):
                continue
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
