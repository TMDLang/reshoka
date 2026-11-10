from pathlib import Path
import tempfile
import unittest

from scripts.render_neutrino_mix import (
    find_lyric_instruments,
    parse_part_model_overrides,
    resolve_part_model,
    prepare_vocal_musicxml_parts,
)


class NeutrinoRendererTests(unittest.TestCase):
    def test_part_model_override_is_selected_by_voice_name(self):
        overrides = parse_part_model_overrides(["Piano2=NAKUMO", "Soprano=MERROW"])

        self.assertEqual(
            resolve_part_model("Piano2", "MERROW", overrides), "NAKUMO"
        )
        self.assertEqual(
            resolve_part_model("Alto", "MERROW", overrides), "MERROW"
        )

    def test_part_model_override_rejects_invalid_format(self):
        with self.assertRaises(ValueError):
            parse_part_model_overrides(["Piano2"])

    def test_find_lyric_instruments_returns_all_vocal_parts(self):
        tmd = """
        Song:Soprano@|0|{
            <4*>
            1 2 3 4
            L1| は な の あ |
        }
        Song:Alto@|0|{
            <4*>
            3 4 5 6
            L1| は な の あ |
        }
        """

        instruments, stanzas = find_lyric_instruments(tmd)

        self.assertEqual(instruments, ["Soprano", "Alto"])
        self.assertEqual(stanzas, [1])

    def test_prepare_vocal_musicxml_parts_keeps_each_lyric_part(self):
        musicxml = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="3.1">
  <part-list>
    <score-part id="P1"><part-name>Soprano</part-name></score-part>
    <score-part id="P2"><part-name>Alto</part-name></score-part>
    <score-part id="P3"><part-name>PianoLH</part-name></score-part>
  </part-list>
  <part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type><lyric><text>ハ</text></lyric></note></measure></part>
  <part id="P2"><measure number="1"><note><pitch><step>A</step><octave>3</octave></pitch><duration>1</duration><type>quarter</type><lyric><text>ハ</text></lyric></note></measure></part>
  <part id="P3"><measure number="1"><note><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration><type>quarter</type></note></measure></part>
</score-partwise>
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "raw.musicxml"
            output_dir = root / "parts"
            source.write_text(musicxml, encoding="utf-8")

            prepared = prepare_vocal_musicxml_parts(source, output_dir)

            self.assertEqual([item.part_name for item in prepared], ["Soprano", "Alto"])
            self.assertEqual(
                [item.path.name for item in prepared],
                ["vocal_01_soprano.musicxml", "vocal_02_alto.musicxml"],
            )
            self.assertEqual(
                [len(item.path.read_text(encoding="utf-8")) > 0 for item in prepared],
                [True, True],
            )


if __name__ == "__main__":
    unittest.main()
