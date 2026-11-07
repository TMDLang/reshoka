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
import os
from pathlib import Path
import sys

from song_markdown import (
    AmbiguousMainTmdError,
    DOCS_ROOT,
    REPO_ROOT,
    discover_targets,
    generate_book_info_folder,
    generate_song_folder,
    generate_volume_index,
    update_site_indexes_and_mkdocs,
)


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
        print(
            f"錯誤：在 {target} 下找不到任何 TMD 曲目或 0_book_info 資料夾",
            file=sys.stderr,
        )
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
            if isinstance(exc, AmbiguousMainTmdError):
                print(f"跳過：{exc}", file=sys.stderr)
                return 0
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
                    future.result()
                    if done % 25 == 0 or done == total:
                        print(f"  進度：{done}/{total}（最新：{folder.name}）")
                except Exception as exc:
                    if isinstance(exc, AmbiguousMainTmdError):
                        print(f"  [跳過] {folder}: {exc}", file=sys.stderr)
                        continue
                    err_msg = f"{folder}: {exc}"
                    errors.append(err_msg)
                    print(f"  [失敗] {err_msg}", file=sys.stderr)

    for vdir in volume_folders:
        out = generate_volume_index(vdir)
        print(f"[冊別總覽] 已產生：{out}")

    mkdocs_yml = REPO_ROOT / "mkdocs.yml"
    if target == DOCS_ROOT or target == REPO_ROOT or len(volume_folders) > 1:
        update_site_indexes_and_mkdocs(DOCS_ROOT, mkdocs_yml)
        print(f"[網站導覽] 已更新：{DOCS_ROOT / 'index.md'} 與 {mkdocs_yml}")

    if errors:
        print(f"\n完成，但有 {len(errors)} 首發生錯誤：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
