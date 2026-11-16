import json
from pathlib import Path
import tempfile
import unittest

from scripts.externalize_media import rewrite_html
from scripts.song_markdown.audio import AudioAsset, discover_audio_assets
from scripts.song_markdown.song_page import build_audio_frontmatter
from scripts.song_markdown.song_page import build_song_frontmatter


class AudioMetadataTests(unittest.TestCase):
    def test_song_frontmatter_contains_discoverable_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "P216.jpg"
            image.write_bytes(b"image")
            frontmatter = build_song_frontmatter(
                title="水牛",
                song_id="shoka_kyozai_shu_1923_grade_3_4_44_suigyu",
                col_name="shoka_kyozai_shu_1923",
                vol_name="grade_3_4",
                col_title="《新編 小學校・公學校 唱歌教材集》",
                vol_title="尋常科 第三、四學年",
                vol_nav_title="尋常科 第三、四學年",
                credits=["曲：一條慎三郎"],
                sources=["book: 新編 小學校・公學校 唱歌教材集", "P216–P217"],
                score_info={"key": "F", "meter": "2/4", "tempo": "96"},
                lyrics="山の麓の青草原に",
                images=[image],
                audio_assets=[
                    AudioAsset(path=Path("suigyu.mp3"), label="原曲伴奏版")
                ],
                tmd_sources=["suigyu.tmd", "suigyu_piano.tmd"],
            )

            self.assertIn('song_id: "shoka_kyozai_shu_1923_grade_3_4_44_suigyu"', frontmatter)
            self.assertIn('collection: "shoka_kyozai_shu_1923"', frontmatter)
            self.assertIn('volume: "grade_3_4"', frontmatter)
            self.assertIn('sources:', frontmatter)
            self.assertIn('credits:', frontmatter)
            self.assertIn('tempo: "96"', frontmatter)
            self.assertIn('image:', frontmatter)
            self.assertIn('file: "P216.jpg"', frontmatter)
            self.assertIn('tmd_source:', frontmatter)

    def test_discover_audio_assets_returns_all_exported_mp3s(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            for filename in (
                "suigyu.mp3",
                "suigyu_neutrino.mp3",
                "suigyu_piano.mp3",
            ):
                (tmp_path / filename).write_bytes(b"audio")

            assets = discover_audio_assets(tmp_path, "suigyu", audio_is_piano=True)

            self.assertEqual(
                [asset.path.name for asset in assets],
                ["suigyu.mp3", "suigyu_neutrino.mp3", "suigyu_piano.mp3"],
            )
            self.assertEqual(
                [asset.label for asset in assets],
                ["鋼琴伴奏版", "NEUTRINO 歌聲合成版", "suigyu_piano"],
            )


    def test_build_audio_frontmatter_uses_a_list_of_export_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            first = tmp_path / "suigyu.mp3"
            second = tmp_path / "suigyu_neutrino.mp3"
            first.write_bytes(b"audio")
            second.write_bytes(b"audio")
            assets = discover_audio_assets(tmp_path, "suigyu", audio_is_piano=False)

            frontmatter = build_audio_frontmatter(assets)

            self.assertIn("audio:", frontmatter)
            self.assertIn('file: "suigyu.mp3"', frontmatter)
            self.assertIn('file: "suigyu_neutrino.mp3"', frontmatter)


    def test_externalize_media_rewrites_json_ld_audio_url(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            site_root = tmp_path / "site"
            media_root = tmp_path / "docs"
            html_path = site_root / "song" / "index.html"
            media_path = media_root / "song" / "suigyu.mp3"
            image_path = media_root / "song" / "P216.jpg"
            html_path.parent.mkdir(parents=True)
            media_path.parent.mkdir(parents=True)
            media_path.write_bytes(b"audio")
            image_path.write_bytes(b"image")
            html_path.write_text(
                '<meta property="og:image" content="P216.jpg">'
                '<script type="application/ld+json">'
                + json.dumps(
                    {
                        "image": "P216.jpg",
                        "audio": {"contentUrl": "suigyu.mp3"},
                    }
                )
                + "</script>",
                encoding="utf-8",
            )

            changed = rewrite_html(
                html_path,
                site_root,
                media_root,
                "https://pub.example/reshoka",
            )

            self.assertTrue(changed)
            self.assertIn(
                "https://pub.example/reshoka/song/suigyu.mp3",
                html_path.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "https://pub.example/reshoka/song/P216.jpg",
                html_path.read_text(encoding="utf-8"),
            )
