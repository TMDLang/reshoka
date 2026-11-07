"""Site-wide index JSON (docs/data/songs.json), homepage fallback, and mkdocs.yml navigation builder."""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import (
    COLLECTIONS_ORDER,
    COLLECTION_TITLES,
    VOLUME_NAV_TITLES,
    VOLUME_TITLES,
    resolve_col_and_vol,
)
from .tmd_parser import parse_metadata
from .utils import AmbiguousMainTmdError, choose_main_tmd, natural_sort_key
from .volume_page import generate_volume_index

MKDOCS_CONFIG_HEADER: list[str] = [
    "site_name: Re:shoka — 日治時期臺灣公學校與小學校唱歌教材數位重建計畫",
    "site_description: Re:shoka 是 TMD 電腦音樂語言的非官方子計畫，運用 AI 協助重建 1902–1945 年臺灣與日本唱歌教材的音樂史，收錄 23 冊、795 首歷史曲目，提供 MP3、五線譜、歌詞檢索與純文字 TMD 樂譜。",
    "site_author: TMD Contributors",
    "site_url: https://tmdlang.github.io/reshoka/",
    "copyright: Released under the MIT License. In memory of Chen, Chih-Han / aguai (阿怪, 1974–2019)",
    "# repo_url: https://github.com/tmdlang/reshoka",
    "",
    "theme:",
    "  name: material",
    "  custom_dir: overrides",
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
    "    - navigation.top",
    "    - search.suggest",
    "    - search.highlight",
    "    - content.code.copy",
    "",
    "plugins:",
    "  - search:",
    "      lang:",
    "        - ja",
    "        - en",
    "      separator: '[\\s\\-\\.、，。／（）「」『』【】・]+'",
    "",
    "markdown_extensions:",
    "  - meta",
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
    "  - pymdownx.tasklist:",
    "      custom_checkbox: true",
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
    "  - javascripts/random-song.js",
    "",
    "nav:",
    "  - 首頁: index.md",
    "  - 跨冊重複與同名歌曲索引: duplicate_songs.md",
]

COLLECTION_EXTRA_NAV_ITEMS: dict[str, list[tuple[str, str]]] = {
    "shintei_jido_shoka": [("專題統計", "shintei_jido_shoka/index.md")],
    "kyoeki_shoka": [("專題統計", "kyoeki_shoka/index.md")],
    "shokacho": [
        ("考證與研究筆記", "shokacho/research_notes.md"),
        ("《蓬萊唱歌集》目次重建", "shokacho/horai_shokashu.md"),
        ("延伸館藏與日本國會圖書館調查", "archives/index.md"),
    ],
}


def _format_song_nav_prefix(col_slug: str, folder_name: str) -> str:
    parts = folder_name.split("_")
    if col_slug == "shokacho":
        return parts[1].upper() if folder_name.startswith("0844_p") else parts[0].upper()
    digit_parts = [p for p in parts[:3] if p.isdigit()]
    if len(digit_parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return "-".join(parts[:3] if len(parts) >= 4 and parts[2].isdigit() else parts[:2])
    return parts[0]


def write_song_index_json(docs_dir: Path) -> Path:
    """Write the lightweight song index used by the homepage random picker."""
    songs: list[dict[str, str]] = []
    for main_tmd in sorted(
        (p for p in docs_dir.rglob("*.tmd") if not p.name.endswith("_piano.tmd")),
        key=lambda p: natural_sort_key(str(p)),
    ):
        folder = main_tmd.parent
        try:
            chosen_main_tmd = choose_main_tmd(folder)
        except AmbiguousMainTmdError:
            continue
        if chosen_main_tmd != main_tmd:
            continue
        title, _, _, _ = parse_metadata(main_tmd.read_text(encoding="utf-8"))
        rel_folder = folder.relative_to(docs_dir).as_posix()
        col_name, vol_name = resolve_col_and_vol(folder)
        songs.append(
            {
                "title": title,
                "collection": COLLECTION_TITLES.get(col_name, col_name),
                "volume": VOLUME_TITLES.get(vol_name, vol_name),
                "url": f"{rel_folder}/",
            }
        )

    output = docs_dir / "data" / "songs.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(songs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return output


def update_site_indexes_and_mkdocs(docs_dir: Path, mkdocs_path: Path) -> None:
    docs_dir = docs_dir.resolve()
    home_lines = [
        "# Re:shoka — 百年歌曲重建計畫",
        "",
        "TMD 電腦音樂語言的非官方子計畫，運用 AI 協助重建 1902–1945 年臺灣與日本唱歌教材的音樂史，並提供 TMD 樂譜、MP3 與調性分析。",
        "",
        "> **專案定位**：Re:shoka 是 **TMD 電腦音樂語言的子計畫**，由個人／社群維護，並非政府機關、博物館或任何官方計畫。資料主要整理自公開典藏與公版史料，供研究、教育與欣賞使用。",
        "",
        '<div class="lucky-song" data-lucky-song>',
        "  <div>",
        "    <strong>隨機聽見一段歷史</strong>",
        '    <button type="button" data-lucky-song-button>讓命運選一首</button>',
        "  </div>",
        "  <p data-lucky-song-result>從 788 首歷史曲目中隨機探索。</p>",
        "</div>",
        "",
    ]

    nav_lines = list(MKDOCS_CONFIG_HEADER)

    for col_slug, col_short in COLLECTIONS_ORDER:
        col_dir = docs_dir / col_slug
        if not col_dir.is_dir():
            continue
        col_title = COLLECTION_TITLES.get(col_slug, col_short)
        home_lines.extend([f"## {col_title}", ""])
        nav_lines.append(f"  - {col_short}:")
        nav_lines.extend(
            f"      - {label}: {rel_path}"
            for label, rel_path in COLLECTION_EXTRA_NAV_ITEMS.get(col_slug, [])
            if (docs_dir / rel_path).exists()
        )

        if col_slug == "kogakko_shokashu_1915":
            generate_volume_index(col_dir)
            vol_title = VOLUME_TITLES.get(col_slug, col_slug)
            song_dirs = sorted(
                (
                    d
                    for d in col_dir.iterdir()
                    if d.is_dir() and d.name != "0_book_info" and list(d.glob("*.tmd"))
                ),
                key=lambda d: natural_sort_key(d.name),
            )
            home_lines.append(
                f"- [**{vol_title}**]({col_slug}/index.md)（共 {len(song_dirs)} 首）"
            )
            nav_lines.append(f"      - 總覽: {col_slug}/index.md")
            if (col_dir / "0_book_info" / "index.md").exists():
                nav_lines.append(f"      - 書訊與掃描頁: {col_slug}/0_book_info/index.md")
            for sdir in song_dirs:
                main_tmd = choose_main_tmd(sdir)
                title, _, _, _ = parse_metadata(main_tmd.read_text(encoding="utf-8"))
                prefix = _format_song_nav_prefix(col_slug, sdir.name)
                label = f"{prefix} {title}".replace(":", "：").replace('"', '\\"')
                nav_lines.append(f'      - "{label}": {col_slug}/{sdir.name}/index.md')
            home_lines.append("")
            continue

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

            nav_lines.extend(
                [
                    f"      - {vol_nav_title}:",
                    f"          - 總覽: {col_slug}/{vol_dir.name}/index.md",
                ]
            )
            if (vol_dir / "0_book_info" / "index.md").exists():
                nav_lines.append(
                    f"          - 書訊與掃描頁: {col_slug}/{vol_dir.name}/0_book_info/index.md"
                )
            for sdir in song_dirs:
                main_tmd = choose_main_tmd(sdir)
                title, _, _, _ = parse_metadata(main_tmd.read_text(encoding="utf-8"))
                prefix = _format_song_nav_prefix(col_slug, sdir.name)
                label = f"{prefix} {title}".replace(":", "：").replace('"', '\\"')
                nav_lines.append(
                    f'          - "{label}": {col_slug}/{vol_dir.name}/{sdir.name}/index.md'
                )
        home_lines.append("")

    if (
        docs_dir / "recreations" / "kogakko_shoka_grade3_suite" / "index.md"
    ).exists():
        nav_lines.extend(
            [
                '  - "重新創作":',
                '      - "公學校唱歌第三年學年組曲": recreations/kogakko_shoka_grade3_suite/index.md',
            ]
        )

    index_md = docs_dir / "index.md"
    write_song_index_json(docs_dir)
    if not index_md.exists():
        index_md.write_text("\n".join(home_lines), encoding="utf-8")
    mkdocs_path.write_text("\n".join(nav_lines) + "\n", encoding="utf-8")
