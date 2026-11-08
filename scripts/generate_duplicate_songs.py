#!/usr/bin/env python3
"""Generate docs/duplicate_songs.json and docs/duplicate_songs.md using macOS CoreFoundation/Foundation.

Uses macOS CoreFoundation (`CFStringTransform` and `CFStringTokenizer` with Japanese locale)
to normalize song titles and lyrics into unified Hiragana / Katakana, then detects and
classifies duplicate, variant, and same-title song clusters across all historical collections.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from song_markdown.catalog import COLLECTION_TITLES, VOLUME_TITLES
from song_markdown.tmd_parser import parse_metadata


# =============================================================================
# 1. macOS Foundation / CoreFoundation Kana Normalization Bridge
# =============================================================================

_cf = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
)

_kCFStringEncodingUTF8 = 0x08000100
_kCFStringTokenizerAttributeLatinTranscription = 1 << 16


class _CFRange(ctypes.Structure):
    _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]


_cf.CFStringCreateWithCString.restype = ctypes.c_void_p
_cf.CFStringCreateWithCString.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_uint32,
]
_cf.CFStringCreateMutableCopy.restype = ctypes.c_void_p
_cf.CFStringCreateMutableCopy.argtypes = [
    ctypes.c_void_p,
    ctypes.c_long,
    ctypes.c_void_p,
]
_cf.CFStringTransform.restype = ctypes.c_bool
_cf.CFStringTransform.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_bool,
]
_cf.CFStringGetLength.restype = ctypes.c_long
_cf.CFStringGetLength.argtypes = [ctypes.c_void_p]
_cf.CFStringGetMaximumSizeForEncoding.restype = ctypes.c_long
_cf.CFStringGetMaximumSizeForEncoding.argtypes = [ctypes.c_long, ctypes.c_uint32]
_cf.CFStringGetCString.restype = ctypes.c_bool
_cf.CFStringGetCString.argtypes = [
    ctypes.c_void_p,
    ctypes.c_char_p,
    ctypes.c_long,
    ctypes.c_uint32,
]
_cf.CFRelease.restype = None
_cf.CFRelease.argtypes = [ctypes.c_void_p]
_cf.CFLocaleCreate.restype = ctypes.c_void_p
_cf.CFLocaleCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_cf.CFStringTokenizerCreate.restype = ctypes.c_void_p
_cf.CFStringTokenizerCreate.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    _CFRange,
    ctypes.c_ulong,
    ctypes.c_void_p,
]
_cf.CFStringTokenizerAdvanceToNextToken.restype = ctypes.c_ulong
_cf.CFStringTokenizerAdvanceToNextToken.argtypes = [ctypes.c_void_p]
_cf.CFStringTokenizerCopyCurrentTokenAttribute.restype = ctypes.c_void_p
_cf.CFStringTokenizerCopyCurrentTokenAttribute.argtypes = [
    ctypes.c_void_p,
    ctypes.c_ulong,
]


def _cf_str(text: str) -> ctypes.c_void_p:
    return _cf.CFStringCreateWithCString(
        None, text.encode("utf-8"), _kCFStringEncodingUTF8
    )


def _from_cf(ref: ctypes.c_void_p) -> str:
    length = _cf.CFStringGetLength(ref)
    max_sz = _cf.CFStringGetMaximumSizeForEncoding(length, _kCFStringEncodingUTF8) + 1
    buf = ctypes.create_string_buffer(max_sz)
    _cf.CFStringGetCString(ref, buf, max_sz, _kCFStringEncodingUTF8)
    return buf.value.decode("utf-8")


_JA_LOCALE_NAME = _cf_str("ja")
_JA_LOCALE = _cf.CFLocaleCreate(None, _JA_LOCALE_NAME)
_TR_FULLWIDTH_HALFWIDTH = _cf_str("Fullwidth-Halfwidth")
_TR_HIRAGANA_KATAKANA = _cf_str("Hiragana-Katakana")
_TR_LATIN_HIRAGANA = _cf_str("Latin-Hiragana")


def cf_transform(text: str, transform_ref: ctypes.c_void_p, reverse: bool = False) -> str:
    """Apply a CoreFoundation `CFStringTransform` to `text`."""
    if not text:
        return ""
    src = _cf_str(text)
    mut = _cf.CFStringCreateMutableCopy(None, 0, src)
    _cf.CFStringTransform(mut, None, transform_ref, reverse)
    out = _from_cf(mut)
    _cf.CFRelease(mut)
    _cf.CFRelease(src)
    return out


def to_hiragana(text: str) -> str:
    """Unify halfwidth/fullwidth Katakana & Hiragana into standard Hiragana via CoreFoundation."""
    if not text:
        return ""
    fw = cf_transform(text, _TR_FULLWIDTH_HALFWIDTH, reverse=True)
    return cf_transform(fw, _TR_HIRAGANA_KATAKANA, reverse=True)


def to_katakana(text: str) -> str:
    """Unify halfwidth/fullwidth Hiragana & Katakana into standard Katakana via CoreFoundation."""
    if not text:
        return ""
    fw = cf_transform(text, _TR_FULLWIDTH_HALFWIDTH, reverse=True)
    return cf_transform(fw, _TR_HIRAGANA_KATAKANA, reverse=False)


# Kyujitai (pre-war kanji) -> Shinjitai table so macOS Japanese tokenizer recognizes compound readings
_KYUJITAI_MAP = str.maketrans(
    {
        "兒": "児",
        "臺": "台",
        "灣": "湾",
        "國": "国",
        "學": "学",
        "會": "会",
        "氣": "気",
        "聲": "声",
        "廣": "広",
        "瀨": "瀬",
        "櫻": "桜",
        "燈": "灯",
        "螢": "蛍",
        "鶯": "うぐいす",
        "燕": "つばめ",
        "豐": "豊",
        "勅": "敕",
        "禮": "礼",
        "樂": "楽",
        "舍": "舎",
        "懷": "懐",
        "曉": "暁",
        "德": "徳",
        "圓": "円",
        "圖": "図",
        "晝": "昼",
        "蟲": "虫",
        "鯉": "こい",
    }
)

# Historical kana orthography (歴史的仮名遣い) -> modern Hiragana reading
_HISTORICAL_KANA_REPLACEMENTS: list[tuple[str, str]] = [
    ("ゐ", "い"),
    ("ゑ", "え"),
    ("を", "お"),
    ("づ", "ず"),
    ("ぢ", "じ"),
    ("くわ", "か"),
    ("ぐわ", "が"),
    ("てふ", "ちょう"),
    ("けふ", "きょう"),
    ("ぎう", "ぎゅう"),
    ("きう", "きゅう"),
    ("しう", "しゅう"),
    ("ちう", "ちゅう"),
    ("にう", "にゅう"),
    ("ひう", "ひゅう"),
    ("みう", "みゅう"),
    ("りう", "りゅう"),
    ("あう", "おう"),
    ("かう", "こう"),
    ("さう", "そう"),
    ("たう", "とう"),
    ("なう", "のう"),
    ("はう", "ほう"),
    ("まう", "もう"),
    ("やう", "よう"),
    ("らう", "ろう"),
    ("わう", "おう"),
    ("がう", "ごう"),
    ("ざう", "ぞう"),
    ("だう", "どう"),
    ("ばう", "ぼう"),
    ("ぱう", "ぽう"),
    ("ゆふ", "ゆう"),
    ("いふ", "いう"),
    ("おほ", "おお"),
    ("こほ", "こお"),
    ("とほ", "とお"),
    ("うぐひす", "うぐいす"),
    ("おもひ", "おもい"),
    ("かへる", "かえる"),
    ("こひ", "こい"),
    ("ならひ", "ならい"),
    ("いはひ", "いわい"),
    ("あはて", "あわて"),
    ("うるはし", "うるわし"),
    ("うつは", "うつわ"),
]


def to_hiragana_reading(text: str) -> str:
    """Convert Japanese text (Kanji + Kana) to normalized Hiragana reading via CFStringTokenizer."""
    if not text:
        return ""
    prepped = (
        text.replace("雲雀", "ひばり")
        .replace("紙鳶", "たこ")
        .replace("案山子", "かかし")
        .translate(_KYUJITAI_MAP)
    )
    prepped = to_hiragana(prepped)
    src = _cf_str(prepped)
    length = _cf.CFStringGetLength(src)
    tok = _cf.CFStringTokenizerCreate(
        None, src, _CFRange(0, length), 0, _JA_LOCALE
    )
    parts: list[str] = []
    while _cf.CFStringTokenizerAdvanceToNextToken(tok) != 0:
        lat = _cf.CFStringTokenizerCopyCurrentTokenAttribute(
            tok, _kCFStringTokenizerAttributeLatinTranscription
        )
        if lat:
            latin_str = _from_cf(lat)
            _cf.CFRelease(lat)
            parts.append(cf_transform(latin_str, _TR_LATIN_HIRAGANA, reverse=False))
    _cf.CFRelease(tok)
    _cf.CFRelease(src)
    hira = to_hiragana("".join(parts)) if parts else prepped
    hira = re.sub(r"[^ぁ-んー]", "", hira)
    for old, new in _HISTORICAL_KANA_REPLACEMENTS:
        hira = hira.replace(old, new)
    return hira


# =============================================================================
# 2. Book Labels, Aliases & Curated Metadata
# =============================================================================

BOOK_LABELS: dict[str, str] = {
    "kogakko_shokashu_1915": "《公學校唱歌集》（大正4年／1915，國臺圖 0725 26）",
    "shoka_kyozai_shu_1923/grade_1_2": "《新編小公學校唱歌教材集》第一、二學年（大正12年／1923，國臺圖 0725-41）",
    "shoka_kyozai_shu_1923/grade_3_4": "《新編小公學校唱歌教材集》第三、四學年（大正12年／1923，國臺圖 0725-41）",
    "shoka_kyozai_shu_1923/grade_5_6": "《新編小公學校唱歌教材集》第五、六學年（大正12年／1923，國臺圖 0725-41）",
    "shoka_kyozai_shu_1923/koto_1_2": "《新編小公學校唱歌教材集》高等一、二學年（大正12年／1923，國臺圖 0725-41）",
    "taiwan_shuyu_shoka": "《臺灣周遊唱歌》（明治43年／1910，國臺圖 0786 10）",
    "taiwan_no_uta": "《臺灣の歌》（昭和4年／1929，國臺圖 0786 8）",
    "kogakko_shoka/grade_1": "《公學校唱歌》第一學年用（昭和10年／1935）",
    "kogakko_shoka/grade_2": "《公學校唱歌》第二學年用（昭和11年／1936）",
    "kogakko_shoka/grade_3": "《公學校唱歌》第三學年（昭和10年／1935）",
    "kogakko_shoka/grade_4": "《公學校唱歌》第四學年用（昭和12年／1937）",
    "kogakko_shoka/grade_5": "《公學校唱歌》第五學年用（昭和13年／1938）",
    "kogakko_shoka/grade_6": "《公學校唱歌》第六學年用（昭和15年／1940，國臺圖 523.37 4322-4）",
    "shintei_jido_shoka/grade_1_2020.006.0847.0001": "《新定兒童唱歌》尋常科第一學年用（2020.006.0847.0001）",
    "shintei_jido_shoka/grade_2_2020.006.0847.0002": "《新定兒童唱歌》尋常科第二學年用（2020.006.0847.0002）",
    "shintei_jido_shoka/grade_3_2020.006.0847.0003": "《新定兒童唱歌》尋常科第三學年用（2020.006.0847.0003）",
    "shintei_jido_shoka/grade_4_2020.006.0847.0004": "《新定兒童唱歌》尋常科第四學年用（2020.006.0847.0004）",
    "shintei_jido_shoka/grade_5_2020.006.0847.0005": "《新定兒童唱歌》尋常科第五學年用（2020.006.0847.0005）",
    "shintei_jido_shoka/grade_6_2020.006.0847.0006": "《新定兒童唱歌》尋常科第六學年用（2020.006.0847.0006）",
    "shintei_jido_shoka/koto_boys_2020.006.0848": "《新定兒童唱歌》高等科男子用（2020.006.0848）",
    "shintei_jido_shoka/koto_girls_2020.006.0849": "《新定兒童唱歌》高等科女子用（2020.006.0849）",
    "utanohon/ge_2006.006.0878": "《うたのほん》（唱歌課本）下卷（2006.006.0878）",
    "kyoeki_shoka/kan_1_854862": "《共益商社唱歌教科書》卷一・生徒用（明治38年／1905）",
    "kyoeki_shoka/kan_2_854863": "《共益商社唱歌教科書》卷二・教師用（明治33年／1900）",
    "kyoeki_shoka/kan_3_854864": "《共益商社唱歌教科書》卷三・教師用（明治33年／1900）",
    "kyoeki_shoka/kan_4_854865": "《共益商社唱歌教科書》卷四・教師用（明治33年／1900）",
    "shokacho/vol_01": "楊金土手抄《唱歌帖》第 1 冊（2020.006.0843）",
    "shokacho/vol_02": "楊金土手抄《唱歌帖》第 2 冊・II（2020.006.0843）",
    "shokacho/vol_03": "楊金土手抄《唱歌帖》第 3 冊・I（2020.006.0843）",
    "shokacho/vol_07": "楊金土手抄《唱歌帖》第 7 冊・VII（2020.006.0843）",
    "shokacho/vol_08": "楊金土手抄《唱歌帖》第 8 冊・VIII（2020.006.0843）",
    "shokacho/vol_09": "楊金土手抄《唱歌帖》第 9 冊・IX（2020.006.0843）",
    "shokacho/vol_10": "楊金土手抄《唱歌帖》第 10 冊・X（2020.006.0843）",
}

# Cross-title or variant-stem aliases discovered via melody + Foundation Hiragana lyrics matching
SLUG_ALIASES: dict[str, str] = {
    "karen": "kaaren",
    "karensan": "kaaren",
    "kongosekimizuwautsuwa": "kongoseki",
    "meijisetsushoka": "meijisetsu",
    "meijisetsushokaprinted": "meijisetsu",
    "shiseikinembi": "shiseikinenbi",
    "sotsugyoshikiuta": "sotsugyoshiki",
    "taireihoshukuka": "taireihoshukushoka",
    "tennennobi": "utsukushikitennen",
    "otsukisama": "otsukisan",
    "jugoyaotsukisan": "jugoya",
    "hotarunohikari": "kokubetsu",
    "sobetsunouta": "kokubetsu",
    "yukedomo": "kokyonosora",
    "mudai": "buto",
    "chikamenoshikujiri": "kingannoshikujiri",
    "chokugohoto2": "chokugohoto",
    "tanoshikiwagaie": "tanoshikiwagaya",
    "tako": "takonouta",
    "tokei": "tokeinouta",
    "omoiyari": "dojo",
    "sakurainoketsubetsu": "shonanko",
    "sakurainowakare": "shonanko",
    "ninomiyakinjiro": "ninomiyasontoku",
    "gunkanmachi": "gunkan",
}

# Clusters where all entries are historically the same song (`同曲`), including
# cases where one textbook entry uses an `evidence:editorial` reconstruction or polyphonic part.
PURE_SAME_SONG_IDS: set[str] = {
    "ameagari",
    "asa",
    "funako",
    "gyokei",
    "hanyunoyado",
    "hatsuuguisu",
    "hirosechusa",
    "kishanotabi",
    "kongoseki",
    "matsushima",
    "meijitennogyosei",
    "myogisan",
    "nanyonouta",
    "natsugeshiki",
    "nigimitama",
    "nihonkaikaisen",
    "noshoko",
    "oborozukiyo",
    "rokushisensei",
    "shinboku",
    "shiseikinenbi",
    "suishieinokaiken",
    "taiwannofukei",
    "tasukebune",
    "teiseiko",
    "wagakuniheishi",
    "wakare",
    "yudachi",
}

# Explicit subgroup partitions for multi-version clusters (`mixed_or_variant`)
CLUSTER_RELATION_RULES: dict[str, dict[str, list[set[str]]]] = {
    "ame": {
        "同曲": [
            {
                "kyoeki_shoka/kan_2_854863/3_ame",
                "shokacho/vol_03/p036_ame",
            }
        ],
    },
    "asakaze": {
        "同曲": [
            {
                "shintei_jido_shoka/koto_boys_2020.006.0848/1_5_01_asakaze",
                "shintei_jido_shoka/koto_girls_2020.006.0849/1_5_01_asakaze",
            }
        ],
    },
    "awatetokoya": {
        "同詞異曲": [
            {
                "shintei_jido_shoka/grade_2_2020.006.0847.0002/4_04_awate_tokoya",
                "shokacho/vol_01/p164_awate_tokoya",
            }
        ],
    },
    "buto": {
        "同曲": [
            {
                "shokacho/vol_03/p040_mudai",
                "shokacho/vol_01/p171_buto",
            }
        ],
    },
    "gunkan": {
        "同曲": [
            {
                "shintei_jido_shoka/grade_5_2020.006.0847.0005/3_04_gunkan",
                "shokacho/vol_08/p012_gunkan",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shoka/grade_6/9_gunkan",
                "shintei_jido_shoka/koto_boys_2020.006.0848/1_3_07_gunkan_machi",
            }
        ],
    },
    "ikadakazura": {
        "同詞異曲": [
            {
                "kogakko_shoka/grade_4/15_ikadakazura",
                "shintei_jido_shoka/grade_4_2020.006.0847.0004/3_03_ikadakazura",
            }
        ],
    },
    "inakanoyugure": {
        "同曲": [
            {
                "shintei_jido_shoka/koto_boys_2020.006.0848/2_2_07_inaka_no_yugure",
                "shokacho/vol_08/p022_inaka_no_yugure",
            }
        ],
    },
    "kaiyu": {
        "同曲": [
            {
                "shintei_jido_shoka/koto_girls_2020.006.0849/2_3_05_kaiyu",
                "shokacho/vol_10/p206_kaiyu",
            }
        ],
    },
    "kokubetsu": {
        "同曲異詞": [
            {
                "shintei_jido_shoka/grade_5_2020.006.0847.0005/4_19_kokubetsu",
                "shokacho/vol_03/p042_hotaru_no_hikari",
                "shokacho/vol_10/p197_sobetsu_no_uta",
            }
        ],
    },
    "kokyonosora": {
        "同曲異詞": [
            {
                "shintei_jido_shoka/grade_6_2020.006.0847.0006/2_01_kokyo_no_sora",
                "shokacho/vol_03/p043_yukedomo",
            }
        ],
    },
    "mizuguruma": {
        "同曲": [
            {
                "kogakko_shoka/grade_2/1_mizuguruma",
                "shintei_jido_shoka/grade_2_2020.006.0847.0002/1_03_mizuguruma",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shoka/grade_2/1_mizuguruma",
                "shintei_jido_shoka/grade_2_2020.006.0847.0002/1_03_mizuguruma",
                "shokacho/vol_07/p231_mizuguruma",
            }
        ],
    },
    "niitakayama": {
        "同曲": [
            {
                "kogakko_shoka/grade_5/14_niitakayama",
                "shintei_jido_shoka/grade_5_2020.006.0847.0005/2_06_niitakayama",
            }
        ],
    },
    "niji": {
        "同曲": [
            {
                "kogakko_shoka/grade_3/9_niji",
                "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_11_niji",
            }
        ],
    },
    "ninomiyasontoku": {},  # all pairs 同名異曲
    "omatsuribi": {
        "同曲": [
            {
                "kogakko_shoka/grade_3/8_omatsuribi",
                "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_04_omatsuribi",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shoka/grade_3/8_omatsuribi",
                "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_04_omatsuribi",
                "taiwan_no_uta/2_omatsuribi",
            }
        ],
    },
    "shonanko": {
        "同曲": [
            {
                "kogakko_shoka/grade_4/9_sakurai_no_ketsubetsu",
                "shintei_jido_shoka/grade_6_2020.006.0847.0006/1_07_sho_nanko",
                "shokacho/vol_02/p089_sho_nanko",
            }
        ],
    },
    "sotsugyonouta": {
        "同曲": [
            {
                "shintei_jido_shoka/koto_girls_2020.006.0849/2_3_07_sotsugyo_no_uta",
                "shokacho/vol_10/p201_sotsugyo_no_uta",
            }
        ],
    },
    "suigyu": {
        "同曲": [
            {
                "kogakko_shoka/grade_2/6_suigyu",
                "shintei_jido_shoka/grade_2_2020.006.0847.0002/2_08_suigyu",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shoka/grade_2/6_suigyu",
                "shintei_jido_shoka/grade_2_2020.006.0847.0002/2_08_suigyu",
                "taiwan_no_uta/3_suigyu",
            }
        ],
    },
    "tanoshikiwagaya": {
        "同曲": [
            {
                "kogakko_shoka/grade_6/15_tanoshiki_wagaya",
                "shintei_jido_shoka/grade_6_2020.006.0847.0006/3_04_tanoshiki_wagaya",
                "kyoeki_shoka/kan_4_854865/12_tanoshiki_wagaya",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shoka/grade_6/15_tanoshiki_wagaya",
                "shintei_jido_shoka/grade_6_2020.006.0847.0006/3_04_tanoshiki_wagaya",
                "kyoeki_shoka/kan_4_854865/12_tanoshiki_wagaya",
                "shokacho/vol_08/p027_tanoshiki_waga_ie",
            }
        ],
    },
    "todai": {
        "同詞異曲": [
            {
                "kogakko_shoka/grade_4/13_todai",
                "shintei_jido_shoka/grade_4_2020.006.0847.0004/2_08_todai",
            }
        ],
    },
    "tsuyutomushi": {
        "同詞異曲": [
            {
                "kogakko_shoka/grade_4/11_tsuyu_to_mushi",
                "shintei_jido_shoka/grade_4_2020.006.0847.0004/2_06_tsuyu_to_mushi",
            }
        ],
    },
    "umi": {
        "同曲": [
            {
                "kogakko_shoka/grade_5/7_umi",
                "shintei_jido_shoka/grade_5_2020.006.0847.0005/1_08_umi",
                "shokacho/vol_03/p039_umi",
            },
            {
                "kyoeki_shoka/kan_2_854863/9_umi",
                "shokacho/vol_03/p037_umi",
            }
        ],
    },
    "undokai": {
        "同曲": [
            {
                "kogakko_shoka/grade_3/10_undokai",
                "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_08_undokai",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shoka/grade_3/10_undokai",
                "shintei_jido_shoka/grade_3_2020.006.0847.0003/2_08_undokai",
                "kogakko_shokashu_1915/3_05_undokai",
            }
        ],
    },
    "urashimataro": {
        "同曲": [
            {
                "kogakko_shokashu_1915/2_07_urashima_taro",
                "shintei_jido_shoka/grade_2_2020.006.0847.0002/2_09_urashima_taro",
            }
        ],
    },
    "ushiwakamaru": {
        "同曲": [
            {
                "kogakko_shokashu_1915/2_09_ushiwakamaru",
                "utanohon/ge_2006.006.0878/12_ushiwakamaru",
            }
        ],
        "同詞異曲": [
            {
                "kogakko_shokashu_1915/2_09_ushiwakamaru",
                "utanohon/ge_2006.006.0878/12_ushiwakamaru",
                "shintei_jido_shoka/grade_1_2020.006.0847.0001/2_04_ushiwakamaru",
            }
        ],
    },
}

# Curated cluster descriptions (overrides / enriches auto-generated descriptions)
CURATED_DESCRIPTIONS: dict[str, str] = {
    "akinokoe": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "akinokojo": "同曲（〈秋の湖上／秋ノ湖上〉；收錄於《新定兒童唱歌》高等科女子用與《唱歌帖》P026《蓬萊唱歌集》抄譜，高女用為イ調、手抄本為ト調）",
    "ame": "同曲＋同名異曲（《共益商社唱歌教科書》卷二與《唱歌帖》P036 為同曲；《新定兒童唱歌》第一學年〈アメ〉與《唱歌帖》P229a 為同名異曲）",
    "ameagari": "同曲（二部合唱曲〈雨上り〉；《公學校唱歌》與《新定兒童唱歌》第六學年共用教材）",
    "arahitogami": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "asa": "同曲（〈朝〉；收錄於《新定兒童唱歌》六年級與《唱歌帖》P213《小公學校唱歌教材集》抄譜）",
    "asagao": "同曲（文部省『尋常小學唱歌』第一學年〈朝顔〉；《公學校唱歌集》與《新定兒童唱歌》第一學年共用教材）",
    "asakaze": "同曲＋同名異曲（《新定兒童唱歌》高等科男、女用為同曲；《共益商社唱歌教科書》卷三〈朝風〉為同名異曲）",
    "ashigarayama": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "awatetokoya": "同詞異曲（北原白秋作詞〈あわて床屋〉；《新定兒童唱歌》二年級為山田耕筰作曲版，《唱歌帖》P164 為佐佐木すぐる作曲版）",
    "banzai": "同曲（臺灣總督府《公學校唱歌》第二學年與《うたのほん》下卷共用教材）",
    "buto": "同曲＋同名異曲（《唱歌帖》P040〈無題・三拍子曲〉與 P171〈舞踏〉為同曲；《新定兒童唱歌》五年級、高女用及《唱歌帖》P230b 為同名異曲）",
    "chiyodanomiya": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "chocho": "同曲（西班牙民謠改編唱歌〈蝶々／てふてふ〉；《公學校唱歌集》與《新定兒童唱歌》第一學年共用教材）",
    "chokugohoto": "同曲＋同名異曲（《公學校唱歌集》、《新定兒童唱歌》卷首與《唱歌帖》P122 為「あな尊しや」同曲；《唱歌帖》P121 為小山作之助曲「あやにかしこき」另一版本）",
    "chushin": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "dainippon": "同曲（山本壽作曲；《公學校唱歌》第三學年、《新定兒童唱歌》第三學年與楊金土《唱歌帖》P008 皆收錄同曲）",
    "dojo": "同曲（文部省『尋常小學唱歌』〈同情〉；《公學校唱歌集》題為〈同情〉，《新定兒童唱歌》第三學年題為〈おもひやり〉）",
    "donburiko": "同曲（〈どんぶりこ〉；收錄於《新定兒童唱歌》四年級與《唱歌帖》P243《蓬萊唱歌集》抄譜）",
    "fujisan": "同曲＋同名異曲（《公學校唱歌》第三學年、《公學校唱歌集》與《新定兒童唱歌》第二學年為文部省『尋常小學唱歌』「あたまを雲の上に出し…」同曲；《公學校唱歌》第二學年〈フヂサン〉為低學年別曲）",
    "fuyunoyoru": "同曲（文部省『尋常小學唱歌』第三學年〈冬の夜〉；《公學校唱歌》第四學年與《新定兒童唱歌》第三學年共用教材）",
    "gunkan": "同曲＋同詞異曲＋同名異曲（《新定兒童唱歌》五年級與《唱歌帖》P012 為加藤義清詞・Carey 曲同曲；《公學校唱歌》六年級〈軍艦〉為山田源一郎曲，與《新定兒童唱歌》高男用瀨戶口藤吉曲〈軍艦マーチ〉同採鳥山啓「守るも攻むるも…」歌詞；《うたのほん》下卷與《唱歌帖》P074 為同名異曲）",
    "gyokei": "同曲（二部輪唱曲〈曉景〉；收錄於《公學校唱歌》六年級、《新定兒童唱歌》六年級與《唱歌帖》P090）",
    "hagoromo": "同曲（〈羽衣〉；收錄於《新定兒童唱歌》四年級與《唱歌帖》P157《小公學校唱歌教材集》抄譜）",
    "hana": "同曲＋同名異曲（《公學校唱歌集》〈花〉與《新定兒童唱歌》第一學年〈ハナ〉為同曲；《新定兒童唱歌》高等科女子用〈花〉為瀧廉太郎作曲同名異曲）",
    "hanyunoyado": "同曲（里見義詞・Bishop 曲〈埴生の宿〉*Home! Sweet Home!*；收錄於《公學校唱歌》六年級、《新定兒童唱歌》六年級與高等科女子用，以及《唱歌帖》P097）",
    "harugakita": "同曲（高野辰之詞・岡野貞一曲『尋常小學唱歌』〈春が來た〉；《公學校唱歌》第二學年與《新定兒童唱歌》第二學年共同收錄）",
    "harunoogawa": "同曲（高野辰之詞・岡野貞一曲『尋常小學唱歌』〈春の小川〉；《公學校唱歌》第五學年、《公學校唱歌集》與《新定兒童唱歌》第四學年共同收錄）",
    "hato": "同曲（文部省『尋常小學唱歌』第一學年〈鳩〉；《公學校唱歌》第一學年與《新定兒童唱歌》第一學年共同收錄）",
    "hatsuuguisu": "同曲（〈初鶯〉；收錄於《新定兒童唱歌》五年級與《唱歌帖》P241《蓬萊唱歌集》抄譜）",
    "hibari": "同曲＋同名異曲（《公學校唱歌》與《新定兒童唱歌》第二學年〈ヒバリ〉為同曲；《新定兒童唱歌》五年級與《共益商社唱歌教科書》卷一〈雲雀〉為同名異曲）",
    "hikoki": "同曲＋同名異曲（《公學校唱歌》與《新定兒童唱歌》第一學年〈ヒカウキ〉為同曲；《うたのほん》下卷〈ひかうき〉與《新定兒童唱歌》第五學年〈飛行機〉為同名異曲）",
    "hinomarunohata": "同曲＋同名異曲（《公學校唱歌》第一學年、《公學校唱歌集》與《新定兒童唱歌》第一學年為文部省『尋常小學唱歌』〈日の丸の旗〉同曲；《新定兒童唱歌》第三學年為同名異曲）",
    "hirosechusa": "同曲（文部省『尋常小學唱歌』第四學年〈廣瀨中佐〉；《公學校唱歌》與《新定兒童唱歌》第五學年共同收錄）",
    "hiyoko": "同曲＋同名異曲（《公學校唱歌》與《新定兒童唱歌》第一學年〈ヒヨコ〉為同曲；《新定兒童唱歌》第二學年與《唱歌帖》P070b 為同名異曲）",
    "hotaru": "同曲＋同名異曲（《公學校唱歌》第一學年〈ホタル〉與《うたのほん》下卷〈ほたる〉為同曲；《公學校唱歌集》〈螢〉為文部省『尋常小學唱歌』同名異曲）",
    "ichigatsuichijitsu": "同曲（儀式歌〈一月一日〉；收錄於《公學校唱歌集》、《新定兒童唱歌》卷首與《唱歌帖》P123）",
    "ikadakazura": "同詞異曲（同採臺灣九重葛題材歌詞「みどりの葉かげにむらさきの…」；《公學校唱歌》第四學年為 F 大調 3/4 拍，《新定兒童唱歌》第四學年為 a 小調 2/4 拍）",
    "ikenokoi": "同名異曲（《新定兒童唱歌》第一學年〈イケノコヒ〉與國民學校《うたのほん》下卷〈池の 鯉〉為不同詞曲版本）",
    "inakanoyugure": "同曲＋同名異曲（《新定兒童唱歌》高等科男子用與《唱歌帖》P022 為北村季晴作曲同曲；《共益商社唱歌教科書》卷四為同名異曲）",
    "inakaoshogatsu": "同曲（《公學校唱歌》與《新定兒童唱歌》第四學年共用臺灣農村新年教材）",
    "janken": "同曲（丸山十郎詞・一條慎三郎曲；臺灣總督府《公學校唱歌》第一學年與《うたのほん》下卷共用在地童謠）",
    "kaaren": "同曲＋同名異曲（竹中重雄詞・一條慎三郎曲〈カアレン／かあれん〉於《公學校唱歌》第一學年與《うたのほん》下卷為同曲；《新定兒童唱歌》第一學年〈カーレンサン〉為同名異曲）",
    "kaerutokumo": "同曲（文部省『新訂尋常小學唱歌』第二學年〈かへるとくも〉；《公學校唱歌集》、《新定兒童唱歌》第二學年與《うたのほん》下卷共同收錄）",
    "kaiyu": "同曲＋同名異曲（《新定兒童唱歌》高等科女子用與《唱歌帖》P206 為《小公學校唱歌教材集》同曲；《共益商社唱歌教科書》卷二為同名異曲）",
    "kaki": "同曲（臺灣總督府《公學校唱歌》第二學年與《うたのほん》下卷共用教材）",
    "kanariya": "同曲（西條八十作詞、成田為三作曲〈かなりや〉；收錄於《新定兒童唱歌》四年級與《唱歌帖》P106）",
    "kangaemono": "同曲（文部省『尋常小學唱歌』〈考へ物〉；《公學校唱歌》第二學年、《公學校唱歌集》與《新定兒童唱歌》第二學年共同收錄）",
    "katatsumuri": "同曲＋同名異曲（《公學校唱歌》第一學年與《新定兒童唱歌》第一學年為文部省『尋常小學唱歌』〈かたつむり〉同曲；《唱歌帖》P079 為《大正幼年唱歌》同名異曲）",
    "kazoeuta": "同曲（臺灣總督府《公學校唱歌》第一學年與《うたのほん》下卷共用教材）",
    "kigensetsu": "同曲（儀式歌〈紀元節〉；收錄於《公學校唱歌集》、《新定兒童唱歌》卷首與《唱歌帖》P124）",
    "kimigayo": "同曲（國歌／儀式歌〈君が代〉；收錄於《公學校唱歌集》、《新定兒童唱歌》卷首與《唱歌帖》P048、P120）",
    "kingannoshikujiri": "同曲（滑稽唱歌〈近眼のしくじり〉；《唱歌帖》P080 與 P257）",
    "kingyo": "同曲＋同名異曲（《公學校唱歌》與《新定兒童唱歌》第二學年〈キンギョ／キンギヨ〉為同曲；《唱歌帖》P193a 為同名異曲）",
    "kisha": "同曲＋同名異曲（《公學校唱歌》第三學年、《公學校唱歌集》與《新定兒童唱歌》三年級為大和田愛羅作曲同曲；《唱歌帖》P071 為《大正幼年唱歌》同名異曲）",
    "kishanotabi": "同曲（〈汽車の旅〉；收錄於《新定兒童唱歌》六年級及《唱歌帖》P009、P212《小公學校唱歌教材集》抄譜）",
    "koganemushi": "同名異曲（《公學校唱歌》第二學年〈コガネムシ〉與《唱歌帖》P230a 中山晉平曲〈黃金虫〉為不同詞曲版本）",
    "koinobori": "同曲＋同名異曲（《公學校唱歌》第五學年、《公學校唱歌集》與《新定兒童唱歌》第三學年為文部省『尋常小學唱歌』「甍の波と雲の波…」同曲；《うたのほん》下卷為國民學校「大キイ マゴヒハ…」新版）",
    "kokai": "同曲＋同名異曲（《公學校唱歌》第六學年與《新定兒童唱歌》第四學年〈航海〉「今日船出して…」為同曲；《新定兒童唱歌》第五學年與《共益商社唱歌教科書》卷一為同名異曲）",
    "kokubetsu": "同曲異詞＋同名異曲（《新定兒童唱歌》五年級〈告別〉、《唱歌帖》P042〈螢の光〉與 P197〈送別の歌〉同採蘇格蘭民謠 *Auld Lang Syne* 旋律；高等科女子用〈告別〉為同名異曲）",
    "kokyonosora": "同曲異詞＋同名異曲（《新定兒童唱歌》六年級〈故郷の空〉與《唱歌帖》P043〈行けども〉同採蘇格蘭民謠 *Comin' Thro' the Rye* 旋律；高等科男子用〈故郷の空〉為同名異曲）",
    "kongoseki": "同曲（昭憲皇太后御歌、奧好義作曲〈金剛石・水は器〉；收錄於《公學校唱歌》第五學年、《公學校唱歌集》、《新定兒童唱歌》卷首與《唱歌帖》P051）",
    "kosuzume": "同曲（金子奔水詞；臺灣總督府《公學校唱歌》第一學年與《うたのほん》下卷共用臺灣在地童謠）",
    "kumo": "同名異曲（《新定兒童唱歌》第四學年〈雲〉與《うたのほん》下卷〈くも（蜘蛛）〉為不同題材與詞曲）",
    "kusunokimasatsura": "同曲（《公學校唱歌》與《新定兒童唱歌》第四學年共用教材）",
    "kyuryu": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "makiba": "同曲（《公學校唱歌》與《新定兒童唱歌》第四學年共用教材）",
    "matsushima": "同曲（〈松島〉；收錄於《新定兒童唱歌》五年級與《唱歌帖》P215《小公學校唱歌教材集》抄譜）",
    "meijisetsu": "同曲（堀澤周安作詞、杉江秀作曲〈明治節〉；收錄於《新定兒童唱歌》卷首及《唱歌帖》P182 謄寫版、P185 印刷伴奏譜）",
    "meijitennogyosei": "同曲（明治天皇御製和歌吟唱譜；《公學校唱歌集》收錄二首，《新定兒童唱歌》六年級收錄二首，《公學校唱歌》六年級擴充收錄五首並包含臺灣新高山御製「新高の山のふもとの民草も…」）",
    "mejironoko": "同曲（新原キミ子詞・一條慎三郎曲；臺灣總督府《公學校唱歌》第一學年與《うたのほん》下卷共用臺灣綠繡眼童謠）",
    "mizuguruma": "同曲＋同詞異曲（《公學校唱歌》與《新定兒童唱歌》第二學年〈水グルマ〉為同曲；《唱歌帖》P231 同採「お米つかうよ…」歌詞而旋律不同）",
    "momotaro": "同曲＋同名異曲（《公學校唱歌》第一學年與《うたのほん》下卷為文部省詞・岡野貞一曲『尋常小學唱歌』同曲；《新定兒童唱歌》第二學年為田邊友三郎詞・田村虎藏曲『幼年唱歌』版）",
    "muranokajiya": "同曲（文部省『尋常小學唱歌』〈村の鍛冶屋〉；《公學校唱歌》與《新定兒童唱歌》第三學年共用教材）",
    "myogisan": "同曲（〈妙義山〉；收錄於《新定兒童唱歌》五年級與《唱歌帖》P216《小公學校唱歌教材集》抄譜）",
    "nagaioyasumi": "同曲（《公學校唱歌》與《新定兒童唱歌》第三學年共用教材）",
    "nanyonouta": "同曲（〈南洋の歌〉；收錄於《新定兒童唱歌》六年級與《唱歌帖》P207《小公學校唱歌教材集》抄譜）",
    "natsugeshiki": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "niitakayama": "同曲＋同名異曲（《公學校唱歌》與《新定兒童唱歌》第五學年〈新高山〉為同曲；《唱歌帖》P202 為 1915 年《小公學校唱歌教材集》3/4 拍同名異曲）",
    "nigimitama": "同曲（芝葛鎮作曲〈にぎみたま〉；收錄於《公學校唱歌》六年級、《公學校唱歌集》與《新定兒童唱歌》六年級）",
    "nihonkaikaisen": "同曲（文部省『尋常小學唱歌』第六學年〈日本海海戰〉；《公學校唱歌》與《新定兒童唱歌》第六學年共用教材）",
    "niji": "同曲＋同名異曲（《公學校唱歌》第三學年〈にじ〉與《新定兒童唱歌》第三學年〈にじ〉同採臺灣總督府讀本歌詞；《新定兒童唱歌》第三學年〈虹〉與《共益商社唱歌教科書》卷一〈虹〉為同名異曲）",
    "ningyo": "同曲＋同名異曲（《公學校唱歌》第一學年、《公學校唱歌集》與《新定兒童唱歌》第一學年為文部省『尋常小學唱歌』〈人形〉同曲；《共益商社唱歌教科書》卷三〈人形〉為同名異曲）",
    "ninomiyasontoku": "同名異曲（《公學校唱歌集》〈二宮金次郎〉為文部省『尋常小學唱歌』版；《新定兒童唱歌》四年級〈二宮尊徳〉為桑田春風詞・田村虎藏曲版；《唱歌帖》P196 為《小公學校唱歌教材集》3/4 拍版）",
    "noryo": "同曲＋同名異曲（《新定兒童唱歌》高等科男、女用為同曲；尋常科五年級為同名異曲）",
    "oborozukiyo": "同曲（高野辰之作詞、岡野貞一作曲〈朧月夜〉；收錄於《新定兒童唱歌》六年級與《唱歌帖》P195）",
    "okyakusama": "同曲（《大正幼年唱歌》第七集〈お客様〉；收錄於《新定兒童唱歌》二年級與《唱歌帖》P161）",
    "omatsuribi": "同曲＋同詞異曲（田村富士雄作詞；《公學校唱歌》與《新定兒童唱歌》第三學年為同曲，《臺灣の歌》為昭和4年御大典記念陳華提原創譜曲版）",
    "osaru": "同曲（《大正幼年唱歌》第六集〈オサル〉；收錄於《新定兒童唱歌》一年級與《唱歌帖》P069）",
    "oshogatsu": "同曲（東クメ詞・瀧廉太郎曲〈お正月〉；《公學校唱歌》第一學年、《新定兒童唱歌》第一學年與《うたのほん》下卷共同收錄）",
    "semi": "同曲＋同名異曲（《公學校唱歌》第一學年〈セミ〉與《うたのほん》下卷〈せみ〉為同曲；《公學校唱歌》第三學年〈せみ〉為另曲）",
    "shika": "同曲（《公學校唱歌》與《新定兒童唱歌》第四學年共用教材）",
    "shinboku": "同曲（《公學校唱歌》與《新定兒童唱歌》第五學年共用阿里山神木題材教材）",
    "shiseikinenbi": "同曲（6月17日臺灣始政紀念日唱歌；收錄於《公學校唱歌集》、《新定兒童唱歌》卷首及《唱歌帖》P047、P125）",
    "shonanko": "同曲＋同名異曲（《公學校唱歌》第四學年〈櫻井の訣別〉、《新定兒童唱歌》六年級〈小楠公〉與《唱歌帖》P089 皆為落合直文詞・奧山朝恭曲同曲；《公學校唱歌集》〈櫻井のわかれ〉為文部省『尋常小學唱歌』同名異曲）",
    "sotsugyonouta": "同曲＋同名異曲（《新定兒童唱歌》高等科女子用與《唱歌帖》P201 為蘆田惠之助詞・Schulz 曲同曲；《公學校唱歌集》〈卒業の歌〉為同名異曲）",
    "sotsugyoshiki": "同曲（收錄於《新定兒童唱歌》卷首〈卒業式歌〉與《唱歌帖》P179〈卒業式〉，詞曲相同）",
    "suigyu": "同曲＋同詞異曲＋同名異曲（御船武作詞；《公學校唱歌》與《新定兒童唱歌》第二學年為同曲，《臺灣の歌》為郭明峯原創譜曲版；《新定兒童唱歌》第一學年〈スヰギウ〉為同名異曲）",
    "suishieinokaiken": "同曲（佐佐木信綱詞・岡野貞一曲『尋常小學唱歌』〈水師營の會見〉；《公學校唱歌》與《新定兒童唱歌》第六學年共用教材）",
    "sumiyaki": "同曲（《公學校唱歌》與《新定兒童唱歌》第三學年共用教材）",
    "tachibana": "同曲（《公學校唱歌》與《新定兒童唱歌》第四學年共用教材）",
    "taireihoshukushoka": "同曲（高田耕一作詞、平岡均之作曲〈大禮奉祝唱歌〉；《唱歌帖》P181 謄寫版與 P184 印刷伴奏譜）",
    "taiwannofukei": "同曲（《公學校唱歌集》與《新定兒童唱歌》第六學年共用教材）",
    "taiwannouta": "同曲＋同名異曲（《新定兒童唱歌》高等科男、女用為同曲；《臺灣の歌》同名主題曲為竹中重雄詞・一條慎三郎曲另一作品）",
    "takonouta": "同曲（文部省『尋常小學唱歌』〈凧の歌〉；《公學校唱歌集》題為〈紙鳶〉，《新定兒童唱歌》第二學年題為〈たこのうた〉）",
    "tanabata": "同曲（《公學校唱歌》與《新定兒童唱歌》第二學年共用教材）",
    "tanoshikiwagaya": "同曲＋同詞異曲＋同名異曲（《公學校唱歌》六年級、《新定兒童唱歌》六年級與《共益商社唱歌教科書》卷四為同曲；《唱歌帖》P027 同採「花こそ薫らね…」歌詞而譜曲不同；《唱歌帖》P102 則採 *Home! Sweet Home!* 旋律）",
    "tasukebune": "同曲（〈助船／助け船〉；收錄於《公學校唱歌》第五學年、《新定兒童唱歌》第五學年與《唱歌帖》P211《小公學校唱歌教材集》抄譜）",
    "taue": "同曲＋同名異曲（《公學校唱歌》第三學年、《公學校唱歌集》與《新定兒童唱歌》第二學年為同曲；《共益商社唱歌教科書》卷二〈田植〉為同名異曲）",
    "teiseiko": "同曲（〈鄭成功〉；收錄於《公學校唱歌》第五學年、《新定兒童唱歌》第五學年與《唱歌帖》P217《小公學校唱歌教材集》簡譜草稿）",
    "tenchosetsu": "同曲（儀式歌〈天長節〉；收錄於《公學校唱歌集》、《新定兒童唱歌》卷首與《唱歌帖》P126）",
    "todai": "同詞異曲（同採文部省『尋常小學唱歌』「遠く見ゆるは沖の島…」歌詞；《公學校唱歌》第四學年為文部省 G 大調原曲，《新定兒童唱歌》第四學年為田村虎藏 e 小調曲）",
    "tokeinouta": "同曲（文部省『尋常小學唱歌』〈時計の歌〉；《公學校唱歌集》題為〈時計〉，《新定兒童唱歌》第二學年題為〈とけいのうた〉）",
    "tonbi": "同曲（《大正幼年唱歌》第一集〈とんび〉；收錄於《新定兒童唱歌》四年級與《唱歌帖》P109）",
    "torinosu": "同名異曲（《公學校唱歌》第二學年〈トリ ノ ス〉與《うたのほん》下卷〈とりの す〉為不同詞曲版本）",
    "tsubame": "同曲＋同名異曲（《公學校唱歌》第三學年與《公學校唱歌集》為文部省『尋常小學唱歌』〈燕〉同曲；《新定兒童唱歌》六年級、高女用及《唱歌帖》P208、P245 為同名異曲）",
    "tsuki": "同曲＋同名異曲（《公學校唱歌》第一學年、《公學校唱歌集》與《新定兒童唱歌》第一學年為文部省『尋常小學唱歌』〈月〉「出た出た月が…」同曲；《共益商社唱歌教科書》卷二與《唱歌帖》P155 為同名異曲）",
    "tsukinose": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "tsuyutomushi": "同詞異曲（同採「草の葉末におくつゆの…」歌詞；《公學校唱歌》第四學年為 F 大調 2/4 拍，《新定兒童唱歌》第四學年為 Eb 大調 6/8 拍）",
    "umi": "同曲＋同名異曲（《公學校唱歌》五年級、《新定兒童唱歌》五年級與《唱歌帖》P039 為文部省『尋常小學唱歌』〈海〉同曲；《共益商社唱歌教科書》卷二與《唱歌帖》P037 為共益商社版〈海〉同曲；《新定兒童唱歌》一年級〈ウミ〉為同名異曲）",
    "unabara": "同曲（《新定兒童唱歌》高等科男、女共用教材）",
    "undokai": "同曲＋同詞異曲＋同名異曲（《公學校唱歌》與《新定兒童唱歌》三年級為同曲，與《公學校唱歌集》一條慎三郎作曲版同採臺灣總督府讀本歌詞；《新定兒童唱歌》高男用與《共益商社唱歌教科書》卷一為同名異曲）",
    "urashimataro": "同曲＋同名異曲（《公學校唱歌》第二學年、《新定兒童唱歌》第二學年與《うたのほん》下卷為 1911 年『尋常小學唱歌』「むかしむかし浦島は…」同曲；《公學校唱歌集》〈浦島太郎〉為同名異曲）",
    "ushiwakamaru": "同曲＋同詞異曲（《公學校唱歌集》與《うたのほん》下卷為文部省『尋常小學唱歌』五聲小調／都節音階原曲；《新定兒童唱歌》第一學年同採第一節歌詞並改譜為 G 大調旋律）",
    "utsukushikitennen": "同曲＋同名異曲（武島羽衣詞・田中穗積曲〈美しき天然／天然の美〉於《唱歌帖》P104 與 P131 為同曲；《共益商社唱歌教科書》卷三〈美しき天然〉為同名異曲）",
    "wagakuniheishi": "同曲（〈我國兵士〉；收錄於《新定兒童唱歌》六年級與《唱歌帖》P159《小公學校唱歌教材集》抄譜）",
    "wakare": "同曲（畢業惜別歌〈別れ〉「春のあしたの花の陰…」；《公學校唱歌》與《新定兒童唱歌》第六學年共用教材）",
    "waterloo": "同曲（《新定兒童唱歌》高等科男、女共用教材，男子用為ト調、女子用移為變ロ調）",
    "yudachi": "同曲（文部省唱歌〈夕立〉；收錄於《公學校唱歌》第四學年、《新定兒童唱歌》第四學年與《唱歌帖》P128）",
    "yudachiyanda": "同曲（大澤貞吉詞・一條慎三郎曲；臺灣總督府《公學校唱歌》第一學年與《うたのほん》下卷共用臺灣午後西北雨童謠）",
    "yuhi": "同曲（葛原齒作詞、室崎琴月作曲〈夕日／ユフヒ〉；收錄於《新定兒童唱歌》二年級與《唱歌帖》P236）",
    "yuki": "同曲＋同名異曲（《公學校唱歌集》與《新定兒童唱歌》第二學年為文部省『尋常小學唱歌』〈雪〉「雪やこんこ…」同曲；《共益商社唱歌教科書》卷二〈雪〉為同名異曲）",
}


# =============================================================================
# 3. Song Parsing & Feature Extraction
# =============================================================================


@dataclass
class SongEntry:
    rel_dir: str
    stem: str
    tmd_file: str
    md_file: str
    collection: str
    volume: str
    book_key: str
    book_label: str
    raw_title: str
    jp_title: str
    hira_title: str
    kata_title: str
    hira_reading: str
    norm_slug: str
    key: str
    meter: str
    tempo: str
    melody_degrees: str = field(repr=False, default="")
    lyrics_hira: str = field(repr=False, default="")


def strip_chinese_gloss(raw_title: str) -> str:
    """Keep Japanese title and meaningful Japanese parentheticals while removing Chinese/Kanji glosses."""
    m = re.match(r"^(.*?)\s*[（(]([^）)]+)[）)]\s*$", raw_title)
    if not m:
        return raw_title.strip()
    base, paren = m.group(1).strip(), m.group(2).strip()
    if paren.startswith("あな") or paren in {"其一", "其二", "二部輪唱", "二部合唱"}:
        return raw_title.strip()
    return base


def extract_melody_degrees(tmd_text: str) -> str:
    """Extract sequence of movable-do scale degrees (1-7) from the first voice block."""
    no_comments = re.sub(r"/\*.*?\*/", "", tmd_text, flags=re.S)
    no_inline_tags = re.sub(r"\{[^{}\n]*\}", "", no_comments)
    if "{" not in no_inline_tags:
        return ""
    body = no_inline_tags.split("{", 1)[1].split("}", 1)[0]
    deg_chars: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("L") or s.startswith("<") or s.startswith("~"):
            continue
        if "|" in s:
            deg_chars.extend(re.findall(r"[1-7]", s))
    return "".join(deg_chars[:64])


def extract_lyrics_hiragana(tmd_text: str) -> str:
    """Extract first-stanza lyrics and normalize to Hiragana using macOS CoreFoundation."""
    no_comments = re.sub(r"/\*.*?\*/", "", tmd_text, flags=re.S)
    l1_parts: list[str] = []
    for line in no_comments.splitlines():
        s = line.strip()
        if s.startswith("L1|") or (s.startswith("L|") and not l1_parts):
            l1_parts.append(s.split("|", 1)[1])
    raw = "".join(l1_parts)
    from_comment = False
    if not raw:
        # Fallback: handwritten/transcribed scores often keep lyrics in a
        # comment instead of L1/L2 lines. Prefer lines immediately following
        # stanza markers (一、二、三...) so explanatory prose such as
        # "原典語釋" is not mistaken for lyrics.
        stanza_lines: list[str] = []
        for m in re.finditer(r"/\*.*?\*/", tmd_text, flags=re.S):
            lines = m.group(0).splitlines()
            for index, line in enumerate(lines):
                s = line.strip()
                if not re.match(r"^[一二三四五六七八九十百]+[、．.]", s):
                    continue
                for lyric_line in lines[index + 1 :]:
                    lyric = lyric_line.strip()
                    if not lyric:
                        continue
                    if re.match(r"^[一二三四五六七八九十百]+[、．.]", lyric):
                        break
                    if len(re.findall(r"[ぁ-んァ-ヶ]", lyric)) >= 3 and not any(
                        k in lyric for k in ("Source", "調", "拍", "速度", "原書", "詞", "曲", "語釋")
                    ):
                        stanza_lines.append(lyric)
                if stanza_lines:
                    break
        raw = "".join(stanza_lines)
        from_comment = bool(raw)
    if not raw:
        # Last-resort fallback for comments without explicit stanza markers.
        for m in re.finditer(r"/\*.*?\*/", tmd_text, flags=re.S):
            for line in m.group(0).splitlines():
                s = line.strip()
                if re.search(r"[ぁ-んァ-ヶ]{4,}", s) and not any(
                    k in s for k in ("Source", "調", "拍", "速度", "原書", "詞", "曲", "語釋")
                ):
                    raw += s
            from_comment = bool(raw)
    if from_comment:
        # Comment transcriptions may use kanji where another score writes the
        # historical kana reading.  These readings are intentionally limited
        # to common lyric vocabulary rather than treating every kanji reading
        # as certain.
        for kanji, reading in (
            ("海國兒", "かいこくじ"),
            ("海國", "かいこく"),
            ("男兒", "だんじ"),
            ("東洋", "とうよう"),
            ("萬里", "ばんり"),
            ("潮", "しほ"),
            ("風", "かぜ"),
            ("浪", "なみ"),
            ("舟", "ふね"),
            ("魚", "さかな"),
            ("鳥", "とり"),
            ("羽", "はね"),
            ("爪", "つめ"),
        ):
            raw = raw.replace(kanji, reading)
        raw = to_hiragana_reading(raw)
    hira = to_hiragana(raw)
    hira = re.sub(r"[^ぁ-ん]", "", hira)
    for old, new in _HISTORICAL_KANA_REPLACEMENTS:
        hira = hira.replace(old, new)
    return hira[:80]


def compute_book_key(collection: str, volume: str) -> str:
    if collection == "shintei_jido_shoka":
        return f"shintei_jido_shoka/scores/{volume}"
    if collection == "shokacho":
        return f"shokacho_scores/{volume}"
    if volume:
        return f"{collection}/{volume}"
    return collection


def compute_book_label(collection: str, volume: str) -> str:
    lookup = f"{collection}/{volume}" if volume else collection
    if lookup in BOOK_LABELS:
        return BOOK_LABELS[lookup]
    col_title = COLLECTION_TITLES.get(collection, collection)
    vol_title = VOLUME_TITLES.get(volume, volume)
    return f"{col_title} {vol_title}".strip()


def canonical_cluster_id(stem: str, raw_title: str, hira_reading: str) -> str:
    slug = stem.replace("_", "").lower()
    # Disambiguate homograph stems using CoreFoundation Japanese reading:
    # e.g., `yuki` ("雪" -> ゆき) vs `yuuki` ("勇氣" -> ゆうき)
    if slug == "yuki" and ("勇" in raw_title or hira_reading.startswith("ゆうき")):
        return "yuuki"
    return SLUG_ALIASES.get(slug, slug)


def load_all_song_entries(docs_dir: Path) -> list[SongEntry]:
    entries: list[SongEntry] = []
    tmd_files = sorted(
        p
        for p in docs_dir.rglob("*.tmd")
        if not p.name.endswith("_piano.tmd")
    )
    for tmd_path in tmd_files:
        rel_tmd = tmd_path.relative_to(docs_dir).as_posix()
        rel_dir = tmd_path.parent.relative_to(docs_dir).as_posix()
        parts = Path(rel_dir).parts
        collection = parts[0]
        volume = parts[1] if len(parts) >= 3 else ""

        folder_name = tmd_path.parent.name
        stem = re.sub(
            r"^(?:p\d+[a-z]?_|\d+(?:_\d+)*_)", "", folder_name
        )

        tmd_text = tmd_path.read_text(encoding="utf-8")
        raw_title, _credits, _sources, score_info = parse_metadata(tmd_text)
        raw_title = raw_title or stem
        jp_title = strip_chinese_gloss(raw_title)

        hira_title = to_hiragana(jp_title)
        kata_title = to_katakana(jp_title)
        hira_reading = to_hiragana_reading(jp_title)
        norm_slug = canonical_cluster_id(stem, raw_title, hira_reading)

        key = score_info.get("key", "C")
        meter = score_info.get("meter", "4/4")
        tempo = score_info.get("tempo", "100")

        entries.append(
            SongEntry(
                rel_dir=rel_dir,
                stem=stem,
                tmd_file=rel_tmd,
                md_file=f"{rel_dir}/index.md",
                collection=collection,
                volume=volume,
                book_key=compute_book_key(collection, volume),
                book_label=compute_book_label(collection, volume),
                raw_title=raw_title,
                jp_title=jp_title,
                hira_title=hira_title,
                kata_title=kata_title,
                hira_reading=hira_reading,
                norm_slug=norm_slug,
                key=key,
                meter=meter,
                tempo=tempo,
                melody_degrees=extract_melody_degrees(tmd_text),
                lyrics_hira=extract_lyrics_hiragana(tmd_text),
            )
        )
    return entries


# =============================================================================
# 4. Pairwise & Cluster Classification
# =============================================================================


def classify_pair_relation(cid: str, a: SongEntry, b: SongEntry) -> str:
    """Determine pairwise relation (`同曲`, `同詞異曲`, `同曲異詞`, `同名異曲`) between two entries."""
    if cid in PURE_SAME_SONG_IDS:
        return "同曲"

    if cid in CLUSTER_RELATION_RULES:
        rules = CLUSTER_RELATION_RULES[cid]
        for group in rules.get("同曲", []):
            if a.rel_dir in group and b.rel_dir in group:
                return "同曲"
        for group in rules.get("同詞異曲", []):
            if a.rel_dir in group and b.rel_dir in group:
                return "同詞異曲"
        for group in rules.get("同曲異詞", []):
            if a.rel_dir in group and b.rel_dir in group:
                return "同曲異詞"
        return "同名異曲"

    # Automatic comparison via movable-do melody degrees + CoreFoundation Hiragana lyrics
    msim = (
        SequenceMatcher(None, a.melody_degrees[:40], b.melody_degrees[:40]).ratio()
        if a.melody_degrees and b.melody_degrees
        else 0.0
    )
    lsim = (
        SequenceMatcher(None, a.lyrics_hira[:50], b.lyrics_hira[:50]).ratio()
        if a.lyrics_hira and b.lyrics_hira
        else 0.0
    )

    if msim >= 0.72 or (msim >= 0.58 and lsim >= 0.55):
        return "同曲"
    if lsim >= 0.72:
        return "同詞異曲"
    return "同名異曲"


def classify_cluster_category(cid: str, items: list[SongEntry], relations: set[str]) -> str:
    """Assign cluster to one of the 6 index categories."""
    if relations == {"同名異曲"}:
        return "same_title_different_song"
    if relations != {"同曲"}:
        return "mixed_or_variant"

    vols = {f"{e.collection}/{e.volume}".rstrip("/") for e in items}
    cols = {e.collection for e in items}

    if vols == {
        "shintei_jido_shoka/koto_boys_2020.006.0848",
        "shintei_jido_shoka/koto_girls_2020.006.0849",
    }:
        return "same_song_koto"

    if cols == {"shokacho"}:
        return "same_song_internal"

    if "shokacho" in cols or "kyoeki_shoka" in cols:
        # Keep dainippon in section 1 as historically highlighted, or shokacho if primarily shokacho
        if cid == "dainippon":
            return "same_song_g3"
        return "same_song_shokacho"

    return "same_song_g3"


def build_display_title(items: list[SongEntry]) -> str:
    seen: list[str] = []
    for item in items:
        t = item.jp_title.strip()
        if t not in seen:
            seen.append(t)
    return "／".join(seen)


def auto_describe_cluster(
    cid: str,
    display_title: str,
    category: str,
    relation_type: str,
    items: list[SongEntry],
) -> str:
    if cid in CURATED_DESCRIPTIONS:
        return CURATED_DESCRIPTIONS[cid]

    col_names: list[str] = []
    for e in items:
        c_title = COLLECTION_TITLES.get(e.collection, e.collection)
        if c_title not in col_names:
            col_names.append(c_title)
    joined_cols = "、".join(col_names)

    if relation_type == "同曲":
        return f"同曲（{joined_cols}共同收錄教材）"
    if relation_type == "同名異曲":
        return "同名異曲（各冊收錄之不同詞曲版本）"
    return f"{relation_type}（{joined_cols}跨冊對照曲目）"


def build_clusters(entries: list[SongEntry]) -> list[dict]:
    by_cid: dict[str, list[SongEntry]] = {}
    for entry in entries:
        by_cid.setdefault(entry.norm_slug, []).append(entry)

    clusters: list[dict] = []
    for cid in sorted(by_cid):
        items = by_cid[cid]
        if len(items) < 2:
            continue

        pair_relations: set[str] = set()
        entry_dicts: list[dict] = []

        for idx, item in enumerate(items):
            peers: list[dict] = []
            for jdx, other in enumerate(items):
                if idx == jdx:
                    continue
                rel = classify_pair_relation(cid, item, other)
                pair_relations.add(rel)
                peers.append(
                    {
                        "rel_dir": other.rel_dir,
                        "md_file": other.md_file,
                        "tmd_file": other.tmd_file,
                        "book_label": other.book_label,
                        "raw_title": other.raw_title,
                        "jp_title": other.jp_title,
                        "key": other.key,
                        "meter": other.meter,
                        "relation": rel,
                    }
                )
            entry_dicts.append(
                {
                    "rel_dir": item.rel_dir,
                    "stem": item.stem,
                    "tmd_file": item.tmd_file,
                    "md_file": item.md_file,
                    "book_key": item.book_key,
                    "book_label": item.book_label,
                    "raw_title": item.raw_title,
                    "jp_title": item.jp_title,
                    "hira_title": item.hira_title,
                    "kata_title": item.kata_title,
                    "norm_slug": item.norm_slug,
                    "key": item.key,
                    "meter": item.meter,
                    "tempo": item.tempo,
                    "peers": peers,
                }
            )

        ordered_rels = [
            r
            for r in ("同曲", "同詞異曲", "同曲異詞", "同名異曲")
            if r in pair_relations
        ]
        relation_type = "＋".join(ordered_rels)
        category = classify_cluster_category(cid, items, pair_relations)
        display_title = build_display_title(items)
        description = auto_describe_cluster(
            cid, display_title, category, relation_type, items
        )

        clusters.append(
            {
                "id": cid,
                "display_title": display_title,
                "category": category,
                "relation_type": relation_type,
                "description": description,
                "entries": entry_dicts,
            }
        )

    return clusters


# =============================================================================
# 5. Markdown Index Generation
# =============================================================================

def build_duplicate_groups(clusters: list[dict]) -> list[dict]:
    """Build groups using only exact `同曲` relationships."""
    parent: dict[str, str] = {}
    entry_by_path: dict[str, dict] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for cluster in clusters:
        for entry in cluster["entries"]:
            entry_by_path[entry["rel_dir"]] = entry
            for peer in entry["peers"]:
                if peer["relation"] == "同曲":
                    union(entry["rel_dir"], peer["rel_dir"])

    components: dict[str, list[str]] = {}
    for path in parent:
        components.setdefault(find(path), []).append(path)

    groups: list[dict] = []
    for paths in components.values():
        if len(paths) < 2:
            continue
        source_entries = [entry_by_path[path] for path in sorted(paths)]
        titles: list[str] = []
        for entry in source_entries:
            if entry["jp_title"] not in titles:
                titles.append(entry["jp_title"])
        entries = [
            {
                "rel_dir": entry["rel_dir"],
                "md_file": entry["md_file"],
                "book_label": entry["book_label"],
                "raw_title": entry["raw_title"],
            }
            for entry in source_entries
        ]
        groups.append(
            {"id": source_entries[0]["norm_slug"], "title": "／".join(titles), "entries": entries}
        )

    return sorted(groups, key=lambda group: (group["title"], group["id"]))


def render_duplicate_songs_markdown(
    duplicate_groups: list[dict], total_corpus_songs: int, total_volumes: int
) -> str:
    duplicate_occurrences = sum(len(group["entries"]) for group in duplicate_groups)
    duplicate_extras = sum(len(group["entries"]) - 1 for group in duplicate_groups)
    unique_song_count = total_corpus_songs - duplicate_extras
    lines: list[str] = [
        "---",
        f"title: 全站歌曲去重統計（{unique_song_count} 首不重複歌曲、{len(duplicate_groups)} 組重複歌曲）",
        f"description: 全站 {total_volumes} 冊、{total_corpus_songs} 首曲目中，不重複歌曲數與同一首歌曲的出現位置。",
        "keywords: 歷史歌曲, 跨冊重複歌曲, 公學校唱歌, 新定兒童唱歌, 唱歌帖",
        "---",
        "",
        "# 全站歌曲去重統計",
        "",
        f"全站目前掃描 **{total_volumes} 冊、{total_corpus_songs} 首曲目**，去除跨冊重複後共有 **{unique_song_count} 首不重複歌曲**。",
        "",
        "## 統計總覽",
        "",
        "| 項目 | 數量 |",
        "| :--- | ---: |",
        f"| 全站曲目（含再創作） | **{total_corpus_songs}** |",
        f"| 去重後歌曲 | **{unique_song_count}** |",
        f"| 重複歌曲組 | **{len(duplicate_groups)}** |",
        f"| 重複出現次數 | **{duplicate_occurrences}** |",
        "",
        "## 重複歌曲出處",
        "",
        "以下每一列是一首歌曲；同列的連結是它在全站出現的地方。相同曲名但詞曲不同者不列入。",
        "",
        "| # | 歌曲 | 出現處 |",
        "| :---: | :--- | :--- |",
    ]
    for idx, group in enumerate(duplicate_groups, 1):
        locations = "<br>".join(
            f"**{entry['book_label']}**：[〈{entry['raw_title']}〉]({entry['md_file']})"
            for entry in group["entries"]
        )
        lines.append(f"| {idx} | **{group['title']}** | {locations} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    repo_root = SCRIPT_DIR.parent
    docs_dir = repo_root / "docs"

    entries = load_all_song_entries(docs_dir)
    clusters = build_clusters(entries)
    duplicate_groups = build_duplicate_groups(clusters)

    total_volumes = len({f"{e.collection}/{e.volume}".rstrip("/") for e in entries})
    duplicate_occurrences = sum(len(group["entries"]) for group in duplicate_groups)
    duplicate_extras = sum(len(group["entries"]) - 1 for group in duplicate_groups)

    payload = {
        "total_corpus_songs": len(entries),
        "unique_song_count": len(entries) - duplicate_extras,
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_occurrence_count": duplicate_occurrences,
        "duplicate_groups": duplicate_groups,
    }

    json_path = docs_dir / "duplicate_songs.json"
    md_path = docs_dir / "duplicate_songs.md"

    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(
        render_duplicate_songs_markdown(duplicate_groups, len(entries), total_volumes),
        encoding="utf-8",
    )

    print(
        f"Scanned {len(entries)} songs across {total_volumes} volumes -> "
        f"{len(entries) - duplicate_extras} unique songs, "
        f"{len(duplicate_groups)} duplicate groups ({duplicate_occurrences} occurrences)."
    )
    print(f"Updated {json_path.relative_to(repo_root)} and {md_path.relative_to(repo_root)}.")


if __name__ == "__main__":
    main()
