from pathlib import Path
import sys
import unittest


UI_ROOT = Path(__file__).resolve().parents[1]
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

from checker import analyze_wak, check_klon, compare_rhyme


VALID_EXAMPLE = """บาทหลวงงกตกประหม่าให้ล่าทัพ
จะย้อนกลับไปไม่ได้ดั่งใจหมาย
ให้รีบเร่งพวกพหลพลนิกาย
ไปหาดทรายเต็มกลัวหนังหัวพอง"""

VALID_KLON_4 = """ฉันชื่อหมูกรอบ
ฉันชอบกินไก่
แล้ววิ่งตามไป
ไล่หมาน้ำทอง"""


class CheckerTests(unittest.TestCase):
    def test_known_eight_syllable_wak(self):
        result = analyze_wak("พระอย่าได้ถือความข้าสามคน")
        self.assertEqual(result["syllable_count"], 8)
        self.assertEqual(result["rhythm"], [3, 2, 3])
        self.assertEqual(result["meter_status"], "ผ่าน")

    def test_rhyme_pair(self):
        self.assertTrue(compare_rhyme("หมาย", "กาย")["passed"])
        self.assertFalse(compare_rhyme("หมาย", "พอง")["passed"])

    def test_complete_poem_report_is_explainable(self):
        report = check_klon(VALID_EXAMPLE)
        self.assertTrue(report["complete_stanzas"])
        self.assertEqual(report["line_count"], 4)
        self.assertEqual(len(report["rhyme_checks"]), 3)
        self.assertEqual(report["summary"]["verdict"], "ผ่าน")
        self.assertEqual(report["summary"]["structural_score"], 100)
        self.assertTrue(all(check["passed"] for check in report["rhyme_checks"]))
        self.assertTrue(report["core_validation"]["passed"])
        self.assertEqual(report["summary"]["word_count_passed"], 4)

        first_line = report["lines"][0]
        self.assertTrue(first_line["word_count_passed"])
        self.assertGreater(len(first_line["core_tokens"]), 0)
        sound = first_line["words"][0]["sound_details"][0]
        self.assertEqual(set(sound), {"syllable", "vowel", "final_class", "weight", "tone_role"})
        self.assertNotEqual(sound["vowel"], "ไม่ทราบ")
        self.assertNotEqual(sound["final_class"], "ไม่ทราบ")

    def test_complete_klon_four_uses_its_own_meter_and_rhyme_rules(self):
        report = check_klon(VALID_KLON_4, k_type=4)
        self.assertEqual(report["klon_type"], 4)
        self.assertEqual(report["klon_name"], "กลอนสี่")
        self.assertEqual([line["syllable_count"] for line in report["lines"]], [4, 4, 4, 4])
        self.assertEqual([line["rhythm"] for line in report["lines"]], [[2, 2]] * 4)
        self.assertEqual(report["summary"]["meter_passed"], 4)
        self.assertEqual(report["summary"]["rhyme_passed"], 3)
        self.assertEqual(report["summary"]["verdict"], "ผ่าน")

    def test_unsupported_klon_type_is_rejected(self):
        with self.assertRaises(ValueError):
            check_klon(VALID_KLON_4, k_type=6)

    def test_line_failure_includes_a_human_readable_reason(self):
        result = analyze_wak(VALID_EXAMPLE.splitlines()[0], k_type=4)
        self.assertEqual(result["meter_status"], "ไม่ผ่าน")
        self.assertGreater(len(result["notes"]), 0)
        self.assertIn("พยางค์", result["notes"][0])

    def test_word_limit_failure_is_visible_at_line_level(self):
        long_line = VALID_KLON_4.splitlines()[0] + VALID_KLON_4.splitlines()[1]
        result = analyze_wak(long_line, k_type=4)
        self.assertFalse(result["word_count_passed"])
        self.assertEqual(result["status"], "ไม่ผ่าน")
        self.assertTrue(any("หน่วยคำ" in note for note in result["notes"]))

    def test_incomplete_poem_is_rejected(self):
        report = check_klon("หนึ่งบรรทัด\nสองบรรทัด")
        self.assertFalse(report["complete_stanzas"])
        self.assertEqual(report["summary"]["verdict"], "ไม่ผ่าน")

    def test_seven_syllables_are_review_not_silent_pass(self):
        result = analyze_wak("ดนตรีมีคุณที่ข้อไหน")
        self.assertEqual(result["syllable_count"], 7)
        self.assertEqual(result["meter_status"], "ควรตรวจ")


if __name__ == "__main__":
    unittest.main()
