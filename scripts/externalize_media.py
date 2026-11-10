#!/usr/bin/env python3
"""Rewrite built HTML media references to an external object-storage URL."""

from __future__ import annotations

import argparse
import posixpath
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit


MEDIA_EXTENSIONS = {".jpg", ".jpeg", ".png", ".mp3", ".wav", ".mid"}
ATTRIBUTE_RE = re.compile(
    r"(?P<prefix>\b(?:src|href|content)\s*=\s*[\"'])(?P<url>[^\"']+)(?P<suffix>[\"'])",
    re.IGNORECASE,
)
JSON_MEDIA_RE = re.compile(
    r'(?P<prefix>"(?:contentUrl|image)"\s*:\s*")(?P<url>[^"]+)(?P<suffix>")',
    re.IGNORECASE,
)


def is_media_url(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return False
    return Path(unquote(parsed.path)).suffix.lower() in MEDIA_EXTENSIONS


def rewrite_html(html_path: Path, site_root: Path, media_root: Path, base_url: str) -> bool:
    html_relative = html_path.relative_to(site_root).as_posix()
    html_directory = posixpath.dirname(html_relative)
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        original_url = match.group("url")
        if not is_media_url(original_url):
            return match.group(0)

        parsed = urlsplit(original_url)
        decoded_path = unquote(parsed.path)
        media_relative = posixpath.normpath(
            posixpath.join(html_directory, decoded_path)
        ).lstrip("/")
        source_path = media_root / Path(*media_relative.split("/"))
        if not source_path.is_file():
            return match.group(0)

        external_path = "/".join(
            quote(part, safe="-._~") for part in media_relative.split("/")
        )
        external_url = f"{base_url.rstrip('/')}/{external_path}"
        external_url = urlunsplit(
            ("", "", external_url, parsed.query, parsed.fragment)
        )
        changed = True
        return f"{match.group('prefix')}{external_url}{match.group('suffix')}"

    original = html_path.read_text(encoding="utf-8")
    rewritten = ATTRIBUTE_RE.sub(replace, original)
    rewritten = JSON_MEDIA_RE.sub(replace, rewritten)
    if changed:
        html_path.write_text(rewritten, encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    rewritten_count = 0
    for html_path in args.site.rglob("*.html"):
        if rewrite_html(html_path, args.site, args.media_root, args.base_url):
            rewritten_count += 1

    print(f"Externalized media references in {rewritten_count} HTML files")


if __name__ == "__main__":
    main()
