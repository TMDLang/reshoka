"""Site-wide index JSON (docs/data/songs.json), homepage fallback, and mkdocs.yml navigation builder."""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import (
    COLLECTIONS_ORDER,
    COLLECTION_TITLES,
    COLLECTION_VOLUME_TITLES,
    KYOYUSHO_1935_SECTIONS,
    VOLUME_NAV_TITLES,
    VOLUME_TITLES,
    get_volume_nav_title,
    get_volume_title,
    resolve_col_and_vol,
)
from .tmd_parser import parse_metadata
from .utils import AmbiguousMainTmdError, choose_main_tmd, natural_sort_key
from .volume_page import generate_volume_index

MKDOCS_CONFIG_HEADER: list[str] = [
    "site_name: Re:shoka — 日治時期唱歌教材數位重建計畫",
    "site_description: Re:shoka 是 TMD 電腦音樂語言的非官方子計畫，運用 AI 協助重建 1902–1945 年臺灣與日本唱歌教材的音樂史，收錄 42 冊、1,461 首歷史曲目，提供 MP3、五線譜、歌詞檢索與純文字 TMD 樂譜。",
    "site_author: TMD Contributors",
    "site_url: https://tmdlang.github.io/reshoka/",
    "copyright: Released under the MIT License. In memory of Chen, Chih-Han / aguai (阿怪, 1974–2019)",
    "repo_url: https://github.com/tmdlang/reshoka",
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
    "    - navigation.prune",
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
]

NavItem = tuple[str, str] | tuple[str, list["NavItem"]]


def _format_extra_nav_items(
    items: list[NavItem], docs_dir: Path, indent_level: int = 6
) -> list[str]:
    """Recursively formats custom extra nav items with existence checks."""
    lines: list[str] = []
    prefix = " " * indent_level
    for label, target in items:
        if isinstance(target, str):
            if (docs_dir / target).exists():
                lines.append(f"{prefix}- {label}: {target}")
        elif isinstance(target, list):
            sub_lines = _format_extra_nav_items(target, docs_dir, indent_level + 4)
            if sub_lines:
                lines.append(f"{prefix}- {label}:")
                lines.extend(sub_lines)
    return lines


COLLECTION_EXTRA_NAV_ITEMS: dict[str, list[NavItem]] = {
    "jinjo_shogaku_shoka": [("專題統計", "jinjo_shogaku_shoka/index.md")],
    "shintei_jido_shoka": [
        ("專題統計", "shintei_jido_shoka/index.md"),
        ("《新定兒童唱歌》與大正新童謠", "shintei_jido_shoka/taisho_doyo.md"),
        (
            "史料考證：《臺灣教育》出版介紹全文翻刻",
            "shintei_jido_shoka/taiwan_kyoiku_1930/index.md",
        ),
    ],
    "kyoeki_shoka": [("專題統計", "kyoeki_shoka/index.md")],
    "kogakko_shokashu_1915": [
        ("專題統計", "kogakko_shokashu_1915/analysis.md"),
        (
            "1904年公學校唱歌制度起點公文全紀錄",
            [
                (
                    "歷史總覽（七大官廳公文全紀錄）",
                    "kogakko_shokashu_1915/begin/1904_shoka_origins/index.md",
                ),
                (
                    "基隆廳訓令第七號（必須科目加設）",
                    "kogakko_shokashu_1915/begin/1904_shoka_compulsory/index.md",
                ),
                (
                    "宜蘭廳訓令第十八號（科目加設）",
                    "kogakko_shokashu_1915/begin/1904_yilan_shoka_compulsory/index.md",
                ),
                (
                    "深坑廳訓令第三號（抽撥漢文二小時）",
                    "kogakko_shokashu_1915/begin/1904_shenkeng_shoka/index.md",
                ),
                (
                    "嘉義廳訓令甲第十四號（全學年唱歌科）",
                    "kogakko_shokashu_1915/begin/1904_chiayi_shoka/index.md",
                ),
                (
                    "斗六廳訓令第二十號（唱歌科加設）",
                    "kogakko_shokashu_1915/begin/1904_douliu_shoka/index.md",
                ),
                (
                    "鹽水港廳廳令第十號（官附漢文諭告）",
                    "kogakko_shokashu_1915/begin/1904_ensuiko_shoka/index.md",
                ),
                (
                    "蕃薯藔廳達第七號（旗山等三校加設）",
                    "kogakko_shokashu_1915/begin/1904_banshoro_shoka/index.md",
                ),
            ],
        ),
        (
            "官方定價告示史料",
            [
                (
                    "大正6年告示第62號（1917定價追加）",
                    "kogakko_shokashu_1915/official_price_1917/index.md",
                ),
                (
                    "大正10年告示第66號（1921官方定價）",
                    "kogakko_shokashu_1915/official_price_1921/index.md",
                ),
            ],
        ),
    ],
    "shoka_kyozai_shu_1923": [
        ("總覽與書訊", "shoka_kyozai_shu_1923/index.md"),
        ("專題統計", "shoka_kyozai_shu_1923/analysis.md"),
    ],
    "kogakko_shoka": [
        ("專題統計", "kogakko_shoka/statistics.md"),
        (
            "懸賞募集與公報史料",
            [
                (
                    "昭和8年歌詞募集告示",
                    "kogakko_shoka/lyrics_call/index.md",
                ),
                (
                    "昭和8年入選歌詞告示",
                    "kogakko_shoka/official_selection/index.md",
                ),
                (
                    "昭和8年懸賞募集入選歌詞與作詞者名單",
                    "kogakko_shoka/lyrics_contest/index.md",
                ),
                (
                    "昭和8年歌曲募集告示",
                    "kogakko_shoka/melody_call/index.md",
                ),
                (
                    "昭和8年歌曲募集訂正公告",
                    "kogakko_shoka/melody_call_errata/index.md",
                ),
                (
                    "昭和8年歌曲入選者告示",
                    "kogakko_shoka/official_melody_selection/index.md",
                ),
                (
                    "昭和10年高等科歌詞募集告示",
                    "kogakko_shoka/koto_lyrics_call/index.md",
                ),
                (
                    "昭和10年高等科歌詞入選者告示",
                    "kogakko_shoka/koto_official_selection/index.md",
                ),
            ],
        ),
    ],
    "kyoyusho_shoka_1935": [
        ("選曲特色與專題考證", "kyoyusho_shoka_1935/analysis.md"),
        ("教材統計專題", "kyoyusho_shoka_1935/statistics.md"),
        ("《教育所用唱歌教材集》與大正新童謠", "kyoyusho_shoka_1935/taisho_doyo.md"),
        (
            "蕃童教育所唱歌史料考釋",
            [
                (
                    "〈新作臺灣青年歌、歌曲發表〉（昭和5年《社會教育》）",
                    "kyoyusho_shoka_1935/kyoikusho_shoka/taiwan_seinen_ka_1930/index.md",
                ),
                (
                    "岡本新市《教育所の唱歌教授／教材論》（1933–1934）",
                    "kyoyusho_shoka_1935/kyoikusho_shoka/index.md",
                ),
                (
                    "〈唱歌遊戯教材集委員會開催〉與紀念合照（昭和9年）",
                    "kyoyusho_shoka_1935/kyoikusho_shoka/shoka_iinkai_1934/index.md",
                ),
                (
                    "〈國語普及唱歌入選發表〉（昭和8年）",
                    "kyoyusho_shoka_1935/kyoikusho_shoka/kokugo_fukyu_shoka_1933/index.md",
                ),
                (
                    "《教育所用 遊戲教材集》（昭和12年姐妹教材考釋）",
                    "kyoyusho_shoka_1935/kyoikusho_shoka/yugi_kyozai_1937/index.md",
                ),
            ],
        ),
    ],
    "shokacho": [
        ("史料整理筆記", "shokacho/research_notes.md"),
        ("《楊金土手抄唱歌帖》編年時間軸", "shokacho/timeline.md"),
        ("《蓬萊唱歌集》目次重建", "shokacho/horai_shokashu.md"),
        ("《蓬萊唱歌集》與大正新童謠", "shokacho/horai_taisho_doyo.md"),
        ("1926年蓬萊公學校唱歌研究會紀事", "shokacho/1926_horai_study_meeting.md"),
        ("延伸館藏與日本國會圖書館調查", "archives/index.md"),
    ],
    "hyojun_shoka_gakushucho": [
        ("專題導覽與各冊目錄", "hyojun_shoka_gakushucho/index.md"),
    ],
    "taiwan_no_uta": [
        (
            "史料考證：〈臺灣の歌審査員の作曲發表〉（1930年）",
            "taiwan_no_uta/shinsain_sakkyoku_1930/index.md",
        ),
    ],
}


CEREMONIAL_CANONICAL_NAMES = {
    # 八大祝日大祭日與總督府三大儀式歌
    "君が代", "キミガヨ", "きみがよ",
    "一月一日", "イチガツイチジツ",
    "紀元節", "キゲンセツ", "きげん節",
    "天長節", "テンチャウセツ", "てんちょうせつ",
    "明治節", "メイジセツ",
    "始政記念日", "始政紀念日", "シセイキネンビ",
    "地久節",
    "神武天皇祭",
    "元始祭",
    "新嘗祭",
    # 學校特定儀式與奉答/奉祝歌
    "勅語奉答", "チョクゴホウタウ",
    "令旨奉答", "令旨奉答の歌", "レウシホウタウ",
    "金剛石", "金剛石・水は器", "金剛石、水は器", "金剛石・水はうつは",
    "みがかずば",
    "卒業式歌", "卒業式の歌", "送別の歌（卒業式の歌）",
    "大禮奉祝歌", "大禮奉祝唱歌", "文部省選定 大禮奉祝唱歌",
    "青年團御大禮奉祝歌",
    "銀婚式奉祝行進歌",
    "皇太子殿下御成婚奉祝歌",
    "皇太子殿下御成婚奉祝提燈行列進行歌",
}


def is_ceremonial_song(p: Path, title: str) -> bool:
    """Check if a song is a ceremonial/ritual song (儀式歌/祝祭日唱歌)."""
    clean_title = title.replace(" ", "").replace("　", "")
    for name in CEREMONIAL_CANONICAL_NAMES:
        if name in clean_title:
            return True
    if "kyoyusho_shoka_1935" in p.parts:
        if p.parent.name.startswith("0_") and p.parent.name != "0_book_info":
            return True
    if "shintei_jido_shoka" in p.parts:
        if p.parent.name.startswith("0_") and p.parent.name != "0_book_info":
            return True
    return False


def _format_song_nav_prefix(col_slug: str, folder_name: str) -> str:
    parts = folder_name.split("_")
    if col_slug == "shokacho":
        return (
            parts[1].upper() if folder_name.startswith("0844_p") else parts[0].upper()
        )
    digit_parts = [p for p in parts[:3] if p.isdigit()]
    if len(digit_parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
        return "-".join(
            parts[:3] if len(parts) >= 4 and parts[2].isdigit() else parts[:2]
        )
    return parts[0]


def write_song_index_json(docs_dir: Path) -> Path:
    """Write the lightweight song index used by the homepage random picker."""
    songs: list[dict[str, str]] = []
    for main_tmd in sorted(
        (
            p
            for p in docs_dir.rglob("*.tmd")
            if not p.name.endswith("_piano.tmd")
            and "recreations" not in p.parts
            and "fun" not in p.parts
        ),
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
        if is_ceremonial_song(main_tmd, title):
            continue
        rel_folder = folder.relative_to(docs_dir).as_posix()
        col_name, vol_name = resolve_col_and_vol(folder)
        songs.append(
            {
                "title": title,
                "collection": COLLECTION_TITLES.get(col_name, col_name),
                "volume": get_volume_title(col_name, vol_name),
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
        "> **專案定位**：Re:shoka 是 **TMD 電腦音樂語言的民間子計畫**，由個人／社群維護，並非政府機關、博物館或任何官方計畫。資料主要整理自公開典藏與公版史料，供查閱、教育與欣賞使用。",
        "",
        '<div class="lucky-song" data-lucky-song>',
        "  <div>",
        "    <strong>隨機聽見一段歷史</strong>",
        '    <button type="button" data-lucky-song-button>讓命運選一首</button>',
        "  </div>",
        "  <p data-lucky-song-result>從 1,461 首歷史曲目中隨機探索。</p>",
        "</div>",
        "",
    ]

    nav_lines = list(MKDOCS_CONFIG_HEADER)

    info_items: list[NavItem] = [
        ("資料來源與各冊導覽", "sources.md"),
        ("詞曲作者索引", "credits_index.md"),
        ("內容產生過程", "workflow.md"),
        ("人工校對進度", "proofreading.md"),
        ("工具與腳本手冊", "tooling_and_scripts.md"),
        ("唱歌教材的流動與變化", "shoka_genealogy.md"),
        ("跨冊重複與同名歌曲索引", "duplicate_songs.md"),
        ("同一歌名的多個版本", "same_title_songs.md"),
        ("同詞異曲歌曲", "same_lyrics_songs.md"),
    ]
    same_melody_dir = docs_dir / "same_melody_songs"
    if (docs_dir / "same_melody_songs.md").exists():
        melody_subitems: list[NavItem] = [("總覽", "same_melody_songs.md")]
        if same_melody_dir.is_dir():
            for m_path in sorted(
                same_melody_dir.glob("*.md"), key=lambda p: natural_sort_key(p.name)
            ):
                title = m_path.name
                for line in m_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("title:"):
                        raw_title = line.split("title:", 1)[1].strip().strip('"').strip("'")
                        if raw_title.startswith("同曲異詞："):
                            raw_title = raw_title.split("同曲異詞：", 1)[1].strip()
                        title = raw_title
                        break
                label = f"{m_path.stem[:3]} {title}".replace(":", "：").replace('"', '\\"')
                melody_subitems.append((label, f"same_melody_songs/{m_path.name}"))
        info_items.append(
            (
                "同曲異詞歌曲",
                melody_subitems if len(melody_subitems) > 1 else "same_melody_songs.md",
            )
        )

    info_items.extend(
        [
            ("《小學校唱歌教授書》", "archives/kogakko_shoka_kyoju/index.md"),
            ("赤尾寅吉編《拔萃兒童唱歌集》（1933）", "archives/akao_torakichi_1933/index.md"),
            ("延伸館藏與日本國會圖書館調查筆記", "archives/index.md"),
        ]
    )

    info_lines = _format_extra_nav_items(info_items, docs_dir, indent_level=6)
    if info_lines:
        nav_lines.append("  - 資料與說明:")
        nav_lines.extend(info_lines)

    for col_slug, col_short in COLLECTIONS_ORDER:
        col_dir = docs_dir / col_slug
        if not col_dir.is_dir():
            continue
        col_title = COLLECTION_TITLES.get(col_slug, col_short)
        home_lines.extend([f"## {col_title}", ""])
        nav_lines.append(f"  - {col_short}:")
        extra_items = COLLECTION_EXTRA_NAV_ITEMS.get(col_slug, [])
        nav_lines.extend(_format_extra_nav_items(extra_items, docs_dir, indent_level=6))

        if col_slug in (
            "kogakko_shokashu_1915",
            "taiwan_shuyu_shoka",
            "taiwan_no_uta",
            "kyoyusho_shoka_1935",
        ):
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
                nav_lines.append(
                    f"      - 書訊與掃描頁: {col_slug}/0_book_info/index.md"
                )
            if col_slug == "kyoyusho_shoka_1935":
                current_sec = None
                for sdir in song_dirs:
                    sec_key = sdir.name.split("_", 1)[0]
                    sec_title = KYOYUSHO_1935_SECTIONS.get(sec_key, f"單元 {sec_key}")
                    if sec_title != current_sec:
                        nav_lines.append(f"      - {sec_title}:")
                        current_sec = sec_title
                    main_tmd = choose_main_tmd(sdir)
                    title, _, _, _ = parse_metadata(main_tmd.read_text(encoding="utf-8"))
                    prefix = _format_song_nav_prefix(col_slug, sdir.name)
                    label = f"{prefix} {title}".replace(":", "：").replace('"', '\\"')
                    nav_lines.append(
                        f'          - "{label}": {col_slug}/{sdir.name}/index.md'
                    )
            else:
                for sdir in song_dirs:
                    main_tmd = choose_main_tmd(sdir)
                    title, _, _, _ = parse_metadata(main_tmd.read_text(encoding="utf-8"))
                    prefix = _format_song_nav_prefix(col_slug, sdir.name)
                    label = f"{prefix} {title}".replace(":", "：").replace('"', '\\"')
                    nav_lines.append(f'      - "{label}": {col_slug}/{sdir.name}/index.md')
            home_lines.append("")
            continue

        vol_dirs = sorted(
            (
                d
                for d in col_dir.iterdir()
                if d.is_dir()
                and (
                    d.name in VOLUME_TITLES
                    or (col_slug, d.name) in COLLECTION_VOLUME_TITLES
                )
            ),
            key=lambda d: natural_sort_key(d.name),
        )
        for vol_dir in vol_dirs:
            song_dirs = sorted(
                (
                    d
                    for d in vol_dir.iterdir()
                    if d.is_dir() and d.name != "0_book_info" and list(d.glob("*.tmd"))
                ),
                key=lambda d: natural_sort_key(d.name),
            )
            if song_dirs:
                generate_volume_index(vol_dir)
            vol_title = get_volume_title(col_slug, vol_dir.name)
            vol_nav_title = get_volume_nav_title(col_slug, vol_dir.name)
            if song_dirs:
                home_lines.append(
                    f"- [**{vol_title}**]({col_slug}/{vol_dir.name}/index.md)（共 {len(song_dirs)} 首）"
                )
            else:
                home_lines.append(
                    f"- [**{vol_title}**]({col_slug}/{vol_dir.name}/index.md)"
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

    archives_items: list[NavItem] = [
        ("《小學校唱歌教授書》", "archives/kogakko_shoka_kyoju/index.md"),
        ("赤尾寅吉編《拔萃兒童唱歌集》（1933）", "archives/akao_torakichi_1933/index.md"),
        ("延伸館藏與日本國會圖書館調查筆記", "archives/index.md"),
    ]
    archive_lines = _format_extra_nav_items(
        archives_items, docs_dir, indent_level=6
    )
    if archive_lines:
        nav_lines.append("  - 典藏檔案與文獻:")
        nav_lines.extend(archive_lines)

    if (docs_dir / "recreations" / "kogakko_shoka_grade3_suite" / "index.md").exists():
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
