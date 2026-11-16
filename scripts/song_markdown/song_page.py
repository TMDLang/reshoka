"""Single song folder Markdown and cross-reference generator."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re

from .audio import AudioAsset, render_abc, render_analysis, render_song_audio, render_studio_url
from .catalog import (
    COLLECTION_TITLES,
    DOCS_ROOT,
    DUPLICATE_INDEX_JSON,
    DUPLICATE_INDEX_MD,
    VOLUME_NAV_TITLES,
    VOLUME_TITLES,
    resolve_col_and_vol,
)
from .tmd_parser import extract_notes_and_lyrics, parse_metadata
from .utils import choose_main_tmd, choose_piano_tmd, find_scanned_images


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


def build_song_frontmatter(
    *,
    title: str,
    song_id: str,
    col_name: str,
    vol_name: str,
    col_title: str,
    vol_title: str,
    vol_nav_title: str,
    credits: list[str],
    sources: list[str],
    score_info: dict[str, str],
    lyrics: str,
    images: list[Path],
    audio_assets: list[AudioAsset],
    tmd_sources: list[str],
) -> str:
    seo_title = f"{title} — {col_title} {vol_nav_title}"
    credit_summary = "、".join(credits) if credits else ""
    key_meter_summary = " ".join(
        p for p in [score_info.get("key", ""), score_info.get("meter", "")] if p
    )
    lyrics_preview = ""
    if lyrics:
        clean_lyric_lines = [
            ln.strip()
            for ln in lyrics.splitlines()
            if ln.strip()
            and not re.match(r"^[一二三四五六七八九十0-9]+[、\.\s]*$", ln.strip())
        ]
        if clean_lyric_lines:
            lyrics_preview = " ".join(clean_lyric_lines[:2])[:60]

    if col_name == "kyoeki_shoka":
        desc_parts = [
            f"〈{title}〉收錄於明治時期東京共益商社樂器店{col_title}（{vol_title}）"
        ]
    else:
        desc_parts = [f"〈{title}〉收錄於日治時期臺灣{col_title}（{vol_title}）"]
    if credit_summary:
        desc_parts.append(f"（{credit_summary}）")
    if key_meter_summary:
        desc_parts.append(f"，調號拍號：{key_meter_summary}")
    if audio_assets:
        audio_description = "、".join(asset.label for asset in audio_assets)
        desc_str = (
            "".join(desc_parts)
            + f"。提供{audio_description}等音訊版本線上試聽、五線譜、純文字 TMD 樂譜與原書掃描圖檔。"
        )
    else:
        desc_str = "".join(desc_parts) + "。提供五線譜、純文字 TMD 樂譜與原書掃描圖檔。"
    if lyrics_preview:
        desc_str += f"歌詞：{lyrics_preview}…"

    kw_list = [
        title,
        col_title.strip("《》"),
        vol_nav_title,
        "日治時期",
        "臺灣音樂史",
        "公學校唱歌",
        "五線譜",
        "TMD",
    ]
    if col_name == "kyoeki_shoka":
        kw_list = [
            title,
            col_title.strip("《》"),
            vol_nav_title,
            "明治時期",
            "唱歌教科書",
            "共益商社",
            "日本國立國會圖書館",
            "五線譜",
            "TMD",
        ]
    if col_name == "shokacho":
        kw_list.extend(["楊金土", "唱歌帖"])
        if vol_name in ("vol_07", "vol_08"):
            kw_list.append("蓬萊唱歌集")
    for c in credits:
        c_clean = re.sub(r"^(詞曲|作詞|作曲|詞|曲|編曲)[：:]\s*", "", c).strip()
        if c_clean and len(c_clean) <= 20:
            kw_list.append(c_clean)
    kw_str = ", ".join(dict.fromkeys(k for k in kw_list if k))

    fm_lines = [
        "---",
        f"title: {json.dumps(seo_title, ensure_ascii=False)}",
        f"song_title: {json.dumps(title, ensure_ascii=False)}",
        f"song_id: {json.dumps(song_id, ensure_ascii=False)}",
        f"collection: {json.dumps(col_name, ensure_ascii=False)}",
        f"volume: {json.dumps(vol_name, ensure_ascii=False)}",
        f"description: {json.dumps(desc_str, ensure_ascii=False)}",
        f"keywords: {json.dumps(kw_str, ensure_ascii=False)}",
        'schema_type: "MusicComposition"',
        f"is_part_of: {json.dumps(f'{col_title} {vol_title}', ensure_ascii=False)}",
    ]
    fm_lines.extend(_yaml_string_list("credits", credits))
    fm_lines.extend(_yaml_string_list("sources", sources))
    if score_info.get("key"):
        fm_lines.append(
            f"musical_key: {json.dumps(score_info['key'], ensure_ascii=False)}"
        )
    if score_info.get("meter"):
        fm_lines.append(f"meter: {json.dumps(score_info['meter'], ensure_ascii=False)}")
    if score_info.get("tempo"):
        fm_lines.append(f"tempo: {json.dumps(score_info['tempo'], ensure_ascii=False)}")
    if images:
        fm_lines.append("image:")
        fm_lines.extend(
            f"  - file: {json.dumps(image.name, ensure_ascii=False)}"
            for image in images
        )
    audio_frontmatter = build_audio_frontmatter(audio_assets)
    if audio_frontmatter:
        fm_lines.extend(audio_frontmatter.splitlines())
    fm_lines.extend(_yaml_string_list("tmd_source", tmd_sources))
    fm_lines.append("---")
    return "\n".join(fm_lines)


def _yaml_string_list(name: str, values: list[str]) -> list[str]:
    if not values:
        return []
    lines = [f"{name}:"]
    lines.extend(f"  - {json.dumps(value, ensure_ascii=False)}" for value in values)
    return lines


def build_audio_frontmatter(audio_assets: list[AudioAsset]) -> str:
    """Serialize discovered export files for MkDocs page metadata."""
    if not audio_assets:
        return ""
    lines = ["audio:"]
    for asset in audio_assets:
        lines.extend(
            [
                f"  - id: {json.dumps(asset.path.stem, ensure_ascii=False)}",
                f"    label: {json.dumps(asset.label, ensure_ascii=False)}",
                f"    file: {json.dumps(asset.path.name, ensure_ascii=False)}",
            ]
        )
    return "\n".join(lines)


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
    markdown_path = folder / "index.md"
    legacy_md_path = folder / f"{stem}.md"

    abc = render_abc(main_tmd, abc_path, folder, force=force)
    analysis = render_analysis(main_tmd, folder)
    audio_assets, audio_html = render_song_audio(
        folder,
        stem,
        main_tmd,
        piano_tmd,
        keep_wav=keep_wav,
        soundfont=soundfont,
        force=force,
        no_audio=no_audio,
    )

    meta_items = list(credits) + [s for s in sources if s not in credits]
    credits_block = (
        "\n".join(f"- {item}" for item in meta_items)
        or "- 詞曲作者：未在 TMD metadata 中提供"
    )
    if notes:
        original_notes = notes.splitlines()
        lines = ""
        for line in original_notes:
            if line.startswith("・編曲說明"):
                if lines.endswith("\n") == False:
                    lines += "\n"
                line = line.replace("・", "")
                lines += "### " + line + "\n\n"
            elif line.startswith("・"):
                line = line.replace("・", "- ")
                if lines.endswith("\n") == False:
                    lines += "\n"
                lines += line + "\n"
            elif line.startswith("【曲目說明】"):
                lines += "\n\n"
            else:
                lines += line + "\n"
        notes = lines

    notes_block = notes or "（TMD 檔案未包含額外 note）"
    lyrics_block = lyrics or "（TMD 檔案未包含歌詞註解）"

    col_name, vol_name = resolve_col_and_vol(folder)
    col_title = COLLECTION_TITLES.get(col_name, col_name)
    vol_title = VOLUME_TITLES.get(vol_name, vol_name)
    vol_nav_title = VOLUME_NAV_TITLES.get(vol_name, vol_name)

    images = find_scanned_images(folder)
    images_section = ""
    if images:
        img_lines = [
            f"![{title} — {col_title} {vol_nav_title} 原書掃描頁 {img.name}]({img.name})"
            for img in images
        ]
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

    frontmatter = build_song_frontmatter(
        title=title,
        song_id=f"{col_name}_{vol_name}_{folder.name}",
        col_name=col_name,
        vol_name=vol_name,
        col_title=col_title,
        vol_title=vol_title,
        vol_nav_title=vol_nav_title,
        credits=credits,
        sources=sources,
        score_info=score_info,
        lyrics=lyrics,
        images=images,
        audio_assets=audio_assets,
        tmd_sources=[p.name for p in [main_tmd, piano_tmd] if p],
    )

    markdown = f"""{frontmatter}

# {title}

> Re:Shōka 使用 AI 協助辨識與重建樂譜，可能會有錯誤。歡迎回報。

{audio_html}

{credits_block}

## 說明

{notes_block}

{cross_ref_section}## 歌詞

```text
{lyrics_block}
```

## ABC

<div class="abc-score" data-abc-src="{abc_path.name}" aria-label="五線譜載入中"></div>

[下載 ABC 原始檔]({abc_path.name})

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
