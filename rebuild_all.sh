#!/bin/sh

python3 scripts/generate_song_markdown.py
python3 scripts/generate_duplicate_songs.py
python3 scripts/generate_credits_index.py
python3 scripts/generate_same_title_songs.py
python3 scripts/generate_same_melody_songs.py
python3 scripts/generate_same_lyrics_songs.py

sh scripts/sync_media_to_r2.sh