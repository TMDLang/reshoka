#!/usr/bin/env python3
"""批次渲染《教科書唱歌 1935》目錄中的 *piano.tmd。"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SONG_ROOT = PROJECT_ROOT / "docs" / "kyoyusho_shoka_1935"
RENDER_SCRIPT = PROJECT_ROOT / "scripts" / "render_neutrino_mix.py"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="找出 kyoyusho_shoka_1935 下所有 *piano.tmd 並逐一執行 NEUTRINO render。"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="將 --skip-existing 傳給 render_neutrino_mix.py。",
    )
    parser.add_argument(
        "--lh-only",
        action="store_true",
        help="將 --lh-only 傳給 render_neutrino_mix.py。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出即將執行的檔案，不實際合成。",
    )
    args = parser.parse_args()

    if not SONG_ROOT.is_dir():
        print(f"找不到歌曲目錄：{SONG_ROOT}", file=sys.stderr)
        return 1
    if not RENDER_SCRIPT.is_file():
        print(f"找不到 render script：{RENDER_SCRIPT}", file=sys.stderr)
        return 1

    piano_files = sorted(SONG_ROOT.rglob("*piano.tmd"))
    if not piano_files:
        print(f"在 {SONG_ROOT} 找不到 *piano.tmd", file=sys.stderr)
        return 1

    print(f"共找到 {len(piano_files)} 個 *piano.tmd。")
    failures: list[tuple[Path, int]] = []

    for index, piano_file in enumerate(piano_files, start=1):
        command = [sys.executable, str(RENDER_SCRIPT), str(piano_file)]
        if args.skip_existing:
            command.append("--skip-existing")
        if args.lh_only:
            command.append("--lh-only")

        print(f"\n===== [{index}/{len(piano_files)}] {piano_file} =====", flush=True)
        if args.dry_run:
            print(" ".join(command))
            continue

        result = subprocess.run(command, cwd=PROJECT_ROOT)
        if result.returncode != 0:
            failures.append((piano_file, result.returncode))
            print(f"⚠️ 失敗，繼續下一首：{piano_file}", file=sys.stderr, flush=True)

    if failures:
        print(f"\n完成，但有 {len(failures)} 首失敗：", file=sys.stderr)
        for piano_file, returncode in failures:
            print(f"  - ({returncode}) {piano_file}", file=sys.stderr)
        return 1

    print("\n✅ 全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
