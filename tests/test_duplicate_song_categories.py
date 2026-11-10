import unittest

from scripts.generate_duplicate_songs import (
    THEME_CATEGORY_LABELS,
    classify_theme_category,
    publication_sort_key,
)


class DuplicateSongCategoryTests(unittest.TestCase):
    def test_ritual_songs_are_separated(self):
        self.assertEqual(
            classify_theme_category("shiseikinenbi"),
            "ritual_and_commemoration",
        )
        self.assertEqual(
            THEME_CATEGORY_LABELS["ritual_and_commemoration"],
            "儀式與紀念",
        )

    def test_unmapped_title_is_explicitly_other(self):
        self.assertEqual(classify_theme_category("not_yet_classified"), "other")

    def test_occurrences_sort_by_publication_year(self):
        early = publication_sort_key("kyoeki_shoka/kan_1_854862/20_shingun")
        textbook = publication_sort_key(
            "shoka_kyozai_shu_1923/grade_1_2/01_hinomaru_no_hata"
        )
        late = publication_sort_key(
            "shintei_jido_shoka/grade_6_2020.006.0847.0006/2_05_suishiei_no_kaiken"
        )
        self.assertLess(early, late)
        self.assertEqual(textbook[0], 1923)


if __name__ == "__main__":
    unittest.main()
