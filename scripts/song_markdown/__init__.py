"""Modular song Markdown, audio, volume index, and MkDocs navigation generator package."""

from __future__ import annotations

from .catalog import DOCS_ROOT, REPO_ROOT
from .site_nav import update_site_indexes_and_mkdocs, write_song_index_json
from .song_page import generate_song_folder
from .utils import AmbiguousMainTmdError, discover_targets
from .volume_page import generate_book_info_folder, generate_volume_index

__all__ = [
    "AmbiguousMainTmdError",
    "DOCS_ROOT",
    "REPO_ROOT",
    "discover_targets",
    "generate_book_info_folder",
    "generate_song_folder",
    "generate_volume_index",
    "update_site_indexes_and_mkdocs",
    "write_song_index_json",
]
