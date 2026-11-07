"""Filesystem discovery, natural sorting, binary resolution, and shell command helpers."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess


class AmbiguousMainTmdError(RuntimeError):
    """A song folder has multiple possible main TMD files and should be skipped."""


def natural_sort_key(text: str) -> list[int | str]:
    return [
        int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", text)
    ]


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


def is_up_to_date(target: Path, source: Path, *, tolerance_sec: float = 2.0) -> bool:
    if not target.exists() or target.stat().st_size == 0:
        return False
    return target.stat().st_mtime + tolerance_sec >= source.stat().st_mtime


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
    raise AmbiguousMainTmdError(f"找到多個可能的主 TMD，跳過：{names}")


def choose_piano_tmd(folder: Path, main_tmd: Path) -> Path | None:
    candidates = sorted(folder.glob("*_piano.tmd"))
    if not candidates:
        return None
    matching = [path for path in candidates if path.stem == f"{main_tmd.stem}_piano"]
    return matching[0] if matching else candidates[0]


def find_scanned_images(folder: Path) -> list[Path]:
    images = []
    for p in folder.iterdir():
        if not p.is_file() or p.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        try:
            header = p.read_bytes()[:8]
        except OSError:
            continue
        if p.suffix.lower() in {".jpg", ".jpeg"} and not header.startswith(b"\xff\xd8"):
            continue
        if p.suffix.lower() == ".png" and not header.startswith(b"\x89PNG"):
            continue
        images.append(p)
    return sorted(images, key=lambda p: (natural_sort_key(p.stem), p.suffix.lower()))


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
        if "recreations" in tmd.parts:
            continue
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
