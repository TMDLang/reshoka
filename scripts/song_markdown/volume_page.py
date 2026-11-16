"""Book info (0_book_info) and volume index page generators."""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import (
    BOOK_INFO_EXTRA_SECTIONS,
    BOOK_INFO_IMAGE_DESCRIPTIONS,
    BOOK_INFO_SEO_TEMPLATES,
    COLLECTION_TITLES,
    DEFAULT_BOOK_INFO_SEO_TEMPLATE,
    DEFAULT_VOLUME_SEO_TEMPLATE,
    FLAT_TABLE_FIRST_COL,
    VOLUME_BLOCKQUOTES,
    VOLUME_EXTRA_LINKS,
    VOLUME_SEO_OVERRIDES,
    VOLUME_SEO_TEMPLATES,
    VOLUME_TITLES,
    classify_song_section,
    resolve_col_and_vol,
)
from .tmd_parser import parse_metadata
from .utils import choose_main_tmd, find_scanned_images, natural_sort_key

SCORE_INFO_BADGES: tuple[tuple[str, str], ...] = (
    ("key", "?={}"),
    ("meter", "<{}>"),
    ("tempo", "!={}"),
)


def _format_frontmatter(fields: list[tuple[str, str]]) -> str:
    body = [f"{key}: {json.dumps(val, ensure_ascii=False)}" for key, val in fields if val]
    return "\n".join(["---", *body, "---"])


def _format_image_block(
    img: Path, col_title: str, vol_title: str, description: str | None
) -> str:
    parts = [f"### {img.name}"]
    if description:
        parts.append(description)
    parts.append(f"![{col_title} {vol_title} 原書掃描頁 {img.name}]({img.name})")
    return "\n\n".join(parts)


def generate_book_info_folder(folder: Path) -> Path:
    folder = folder.resolve()
    col_name, vol_name = resolve_col_and_vol(folder)
    col_title = COLLECTION_TITLES.get(col_name, col_name)
    vol_title = VOLUME_TITLES.get(vol_name, vol_name)

    images = find_scanned_images(folder)
    descriptions = BOOK_INFO_IMAGE_DESCRIPTIONS.get(vol_name, {})
    img_blocks = [
        _format_image_block(img, col_title, vol_title, descriptions.get(img.name))
        for img in images
    ]
    images_md = "\n\n".join(img_blocks) or "*（無掃描圖檔）*"

    seo_title = f"書訊與卷首／卷末掃描頁 — {col_title} {vol_title}"
    seo_template = BOOK_INFO_SEO_TEMPLATES.get(col_name, DEFAULT_BOOK_INFO_SEO_TEMPLATE)
    seo_desc = seo_template.format(
        col_title=col_title, vol_title=vol_title, img_count=len(images)
    )
    frontmatter = _format_frontmatter(
        [
            ("title", seo_title),
            ("description", seo_desc),
            ("image", images[0].name if images else ""),
        ]
    )
    extra_meta = BOOK_INFO_EXTRA_SECTIONS.get(col_name, "")

    markdown = f"""{frontmatter}

# 書訊與卷首／卷末掃描頁 — {col_title} {vol_title}

本頁收錄本冊之封面、扉頁、目次（もくろく）、樂典大要、版權頁與封底等原書掃描圖檔（共 {len(images)} 頁）。
{extra_meta}
{images_md}
"""
    output = folder / "index.md"
    output.write_text(markdown, encoding="utf-8")
    return output


def format_song_table_row(sdir: Path, num_label: str) -> str:
    main_tmd = choose_main_tmd(sdir)
    title, credits, _, score_info = parse_metadata(main_tmd.read_text(encoding="utf-8"))
    credit_str = " / ".join(credits) or "—"
    info_str = (
        " ".join(
            f"`{fmt.format(score_info[key])}`"
            for key, fmt in SCORE_INFO_BADGES
            if score_info.get(key)
        )
        or "—"
    )
    imgs = find_scanned_images(sdir)
    img_str = ", ".join(img.name for img in imgs) or "—"
    return f"| {num_label} | [**{title}**]({sdir.name}/index.md) | {credit_str} | {info_str} | {img_str} |"


def _render_song_table(first_col: str, items: list[tuple[Path, str]]) -> list[str]:
    return [
        f"| {first_col} | 曲名 | 詞曲 / 出處 | 調號・拍號・速度 | 掃描頁 |",
        "| :--- | :--- | :--- | :--- | :--- |",
        *(format_song_table_row(sdir, num_label) for sdir, num_label in items),
        "",
    ]


def _render_flat_sections(
    col_name: str, vol_name: str, first_col: str, song_dirs: list[Path]
) -> list[str]:
    items = [
        (sdir, classify_song_section(col_name, vol_name, sdir.name)[2])
        for sdir in song_dirs
    ]
    return [
        f"## 曲目列表（共 {len(song_dirs)} 首）",
        "",
        *_render_song_table(first_col, items),
    ]


def _render_grouped_sections(
    col_name: str, vol_name: str, song_dirs: list[Path]
) -> list[str]:
    groups: list[tuple[str | None, str | None, list[tuple[Path, str]]]] = []
    for sdir in song_dirs:
        yr_head, sec_head, num_label = classify_song_section(
            col_name, vol_name, sdir.name
        )
        if not groups or groups[-1][:2] != (yr_head, sec_head):
            groups.append((yr_head, sec_head, []))
        groups[-1][2].append((sdir, num_label))

    year_counts: dict[str, int] = {}
    for yr_head, _, items in groups:
        if yr_head:
            year_counts[yr_head] = year_counts.get(yr_head, 0) + len(items)

    summary_parts = (
        [f"{yr} {cnt} 首" for yr, cnt in year_counts.items()]
        if year_counts
        else [f"{sec} {len(items)} 首" for _, sec, items in groups if sec]
    )
    summary_str = f"（{'、'.join(summary_parts)}）" if summary_parts else ""
    lines = [f"本冊共收錄 **{len(song_dirs)} 首**曲目{summary_str}。", ""]

    seen_years: set[str] = set()
    for yr_head, sec_head, items in groups:
        if yr_head and yr_head not in seen_years:
            seen_years.add(yr_head)
            lines.extend([f"## {yr_head}（共 {year_counts[yr_head]} 首）", ""])
        sec_prefix = "###" if yr_head else "##"
        lines.extend(
            [
                f"{sec_prefix} {sec_head}（共 {len(items)} 首）",
                "",
                *_render_song_table("編號", items),
            ]
        )
    return lines


def generate_volume_index(vol_dir: Path) -> Path:
    vol_dir = vol_dir.resolve()
    col_name, vol_name = resolve_col_and_vol(vol_dir)
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

    book_info_dir = vol_dir / "0_book_info"
    book_imgs = find_scanned_images(book_info_dir) if book_info_dir.is_dir() else []
    cover_img_rel = f"0_book_info/{book_imgs[0].name}" if book_imgs else ""

    vol_seo_title = f"{col_title} {vol_title}（共 {len(song_dirs)} 首曲目總覽與線上試聽）"
    vol_seo_desc = VOLUME_SEO_OVERRIDES.get(
        (col_name, vol_name)
    ) or VOLUME_SEO_TEMPLATES.get(col_name, DEFAULT_VOLUME_SEO_TEMPLATE).format(
        col_title=col_title, vol_title=vol_title, song_count=len(song_dirs)
    )

    frontmatter = _format_frontmatter(
        [
            ("title", vol_seo_title),
            ("description", vol_seo_desc),
            ("image", cover_img_rel),
        ]
    )
    blockquote = VOLUME_BLOCKQUOTES.get((col_name, vol_name))
    extra_links = [
        bullet
        for bullet, rel_target in VOLUME_EXTRA_LINKS.get((col_name, vol_name), [])
        if (vol_dir / rel_target).exists()
    ]
    book_info_link = (
        [
            f"- 📖 **[書訊與卷首／卷末掃描頁（共 {len(book_imgs)} 頁）](0_book_info/index.md)**",
            "",
        ]
        if book_info_dir.is_dir()
        else []
    )

    first_col = FLAT_TABLE_FIRST_COL.get(col_name)
    table_lines = (
        _render_flat_sections(col_name, vol_name, first_col, song_dirs)
        if first_col
        else _render_grouped_sections(col_name, vol_name, song_dirs)
    )

    lines = [
        frontmatter,
        "",
        f"# {col_title} {vol_title}",
        "",
    ]
    if blockquote:
        lines.extend([f"> {blockquote}", ""])
    lines.extend(extra_links)
    lines.extend(book_info_link)
    lines.extend(table_lines)

    output = vol_dir / "index.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
