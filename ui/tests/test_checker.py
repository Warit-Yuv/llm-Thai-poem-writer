import ast
from pathlib import Path
import sys
import textwrap
import unittest
from unittest.mock import patch


UI_ROOT = Path(__file__).resolve().parents[1]
if str(UI_ROOT) not in sys.path:
    sys.path.insert(0, str(UI_ROOT))

from checker import (
    analyze_wak,
    check_klon,
    compare_rhyme,
    parse_waks,
    tokenize_editor_units,
    _rhyme_checks,
)
from core import KhaveeVerifier


VALID_EXAMPLE = """บาทหลวงงกตกประหม่าให้ล่าทัพ
จะย้อนกลับไปไม่ได้ดั่งใจหมาย
ให้รีบเร่งพวกพหลพลนิกาย
ไปหาดทรายเต็มกลัวหนังหัวพอง"""

VALID_KLON_4 = """ฉันชื่อหมูกรอบ
ฉันชอบกินไก่
แล้ววิ่งตามไป
ไล่หมาน้ำทอง"""


class CheckerTests(unittest.TestCase):
    def test_editor_uses_readable_units_without_changing_the_spelling(self):
        self.assertEqual(
            tokenize_editor_units("ฉันชื่อหมูกรอบ"),
            ["ฉัน", "ชื่อ", "หมู", "กรอบ"],
        )
        self.assertEqual(
            tokenize_editor_units("บาทหลวงงกตกประหม่าให้ล่าทัพ"),
            ["บาท", "หลวง", "งก", "ตก", "ประ", "หม่า", "ให้", "ล่า", "ทัพ"],
        )
        irregular = "ให้รีบเร่งพวกพหลพลนิกาย"
        units = tokenize_editor_units(irregular)
        self.assertEqual(units, ["ให้", "รีบ", "เร่ง", "พวก", "พหล", "พล", "นิ", "กาย"])
        self.assertEqual("".join(units), irregular)

    def test_known_eight_syllable_wak(self):
        result = analyze_wak("พระอย่าได้ถือความข้าสามคน")
        self.assertEqual(result["syllable_count"], 8)
        self.assertEqual(result["rhythm"], [3, 2, 3])
        self.assertEqual(result["meter_status"], "ผ่าน")

    def test_rhyme_pair(self):
        self.assertTrue(compare_rhyme("หมาย", "กาย")["passed"])
        self.assertFalse(compare_rhyme("หมาย", "พอง")["passed"])

    def test_rhyme_pair_exposes_pronunciation_and_each_syllable(self):
        result = compare_rhyme("ความหมาย", "ร่างกาย")

        self.assertTrue(result["passed"])
        self.assertEqual(result["first_analysis"]["pronunciation"], "ความ-หมาย")
        self.assertEqual(result["first_analysis"]["rhyme_syllable"], "หมาย")
        self.assertEqual(result["second_analysis"]["rhyme_syllable"], "กาย")
        self.assertEqual(len(result["first_analysis"]["sound_details"]), 2)
        self.assertEqual(
            set(result["first_analysis"]["sound_details"][0]),
            {"syllable", "vowel", "final_class", "weight", "tone_role"},
        )

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

    def test_klon_eight_checks_every_candidate_position_one_through_five(self):
        lines = [
            {"spoken_syllables": ["ก", "ข", "ค", "ง", "จ", "ฉ", "ช", "ส่ง"]},
            {"spoken_syllables": ["รับหนึ่ง", "รับสอง", "รับสาม", "รับสี่", "รับห้า", "หก", "เจ็ด", "ปลายรับ"]},
            {"spoken_syllables": ["ก", "ข", "ค", "ง", "จ", "ฉ", "ช", "ปลายรอง"]},
            {"spoken_syllables": ["ส่งหนึ่ง", "ส่งสอง", "ส่งสาม", "ส่งสี่", "ส่งห้า", "หก", "เจ็ด", "ปลายส่ง"]},
        ]

        def fake_rhyme(source, target):
            return (source, target) in {
                ("ส่ง", "รับหนึ่ง"),
                ("ส่ง", "รับสี่"),
                ("ปลายรับ", "ปลายรอง"),
                ("ปลายรอง", "ส่งสอง"),
                ("ปลายรอง", "ส่งห้า"),
            }

        with patch("checker._safe_rhyme", side_effect=fake_rhyme):
            checks = _rhyme_checks(lines, k_type=8)

        self.assertEqual([item["position"] for item in checks[0]["candidates"]], [1, 2, 3, 4, 5])
        self.assertEqual(checks[0]["matched_positions"], [1, 4])
        self.assertEqual(checks[2]["matched_positions"], [2, 5])

    def test_incomplete_poem_is_rejected(self):
        report = check_klon("หนึ่งบรรทัด\nสองบรรทัด")
        self.assertFalse(report["complete_stanzas"])
        self.assertEqual(report["summary"]["verdict"], "ไม่ผ่าน")

    def test_seven_syllables_are_review_not_silent_pass(self):
        result = analyze_wak("ดนตรีมีคุณที่ข้อไหน")
        self.assertEqual(result["syllable_count"], 7)
        self.assertEqual(result["meter_status"], "ควรตรวจ")


class ParseWaksTests(unittest.TestCase):
    WAKS = VALID_EXAMPLE.splitlines()

    def test_newlines(self):
        self.assertEqual(parse_waks(VALID_EXAMPLE), self.WAKS)

    def test_commas_on_one_line(self):
        self.assertEqual(parse_waks(",".join(self.WAKS)), self.WAKS)

    def test_spaces_on_one_line(self):
        self.assertEqual(parse_waks(" ".join(self.WAKS)), self.WAKS)

    def test_four_lines_of_four_commas_is_sixteen_waks(self):
        # Evaluate-CSV shape: one บท per line, วรรค separated by commas.
        pasted = """ทั้งสองถันสันทัดดอกบัวหลวง,เป็นพุ่มพวงงามสุดแรกผุดเผย,พลางประคองต้องเต้ามณฑาเชย,เจ้าพี่เอ๋ยนอนนิ่งไม่ติงองค์
โอบพระกรช้อนอุ้มแล้วจุมพิต,พระทรงฤทธิ์ปลุกชวนนวลหง,โฉมอำพันมาลาผวาองค์,เห็นพระทรงฤทธิไกรวิไลงาม
เบือนสะบัดหัตถาผวาหวาด,ลงจากอาสน์เมียงเมินให้เขินขาม,พระกุมกรวอนว่าพะงางาม,ขอฝากความรักเจ้าอย่าเฝ้าเคือง
กุศลพี่ชี้ช่วยอำนวยชัก,ให้สมรักชิดเชื้อแม่เนื้อเหลือง,มาอยู่สวนโศกศัลย์ถึงขวัญเมือง,พี่ร่างเรื่องให้สาลิกามา"""
        waks = parse_waks(pasted)
        self.assertEqual(len(waks), 16)
        self.assertEqual(waks[0], "ทั้งสองถันสันทัดดอกบัวหลวง")
        self.assertEqual(waks[-1], "พี่ร่างเรื่องให้สาลิกามา")
        self.assertTrue(all("," not in wak for wak in waks))

    def test_mixed_separators_and_stray_padding(self):
        messy = f"  {self.WAKS[0]} , {self.WAKS[1]}\n\n{self.WAKS[2]} / {self.WAKS[3]},  "
        self.assertEqual(parse_waks(messy), self.WAKS)

    def test_a_wak_may_contain_an_internal_space(self):
        # Four lines already form a บท, so the line split wins and the spaced
        # วรรค stays whole instead of being torn into two.
        spaced = list(self.WAKS)
        spaced[2] = "ให้รีบเร่ง พวกพหลพลนิกาย"
        self.assertEqual(parse_waks("\n".join(spaced)), spaced)

    def test_incomplete_input_still_reports_its_real_count(self):
        self.assertEqual(len(parse_waks(",".join(self.WAKS[:3]))), 3)

    def test_app_and_checker_agree_on_the_count(self):
        # The วรรค count app.py shows must be the count check_klon analyzes.
        for text in (VALID_EXAMPLE, ",".join(self.WAKS), " ".join(self.WAKS)):
            self.assertEqual(check_klon(text)["line_count"], len(parse_waks(text)))


class KlonMapTests(unittest.TestCase):
    """The diagrams in app.py are transcribed from core.py. Catch any drift.

    Read app.py with ast rather than importing it, so this runs without
    streamlit installed.
    """

    @staticmethod
    def app_maps() -> dict[int, str]:
        tree = ast.parse((UI_ROOT / "app.py").read_text(encoding="utf-8"))
        for node in tree.body:
            targets = getattr(node, "targets", [])
            if targets and getattr(targets[0], "id", None) == "KLON_MAPS":
                return ast.literal_eval(node.value)
        raise AssertionError("KLON_MAPS not found in app.py")

    @staticmethod
    def core_maps() -> dict[int, str]:
        doc = KhaveeVerifier.check_klon.__doc__ or ""
        maps = {}
        for block in doc.split("═" * 72):
            if "Diagram:" not in block:
                continue
            lines = textwrap.dedent(block).strip("\n").split("\n")
            maps[4 if "Klon 4" in lines[0] else 8] = "\n".join(lines[1:]).strip("\n")
        return maps

    def test_diagrams_match_core_docstring_exactly(self):
        self.assertEqual(self.app_maps(), self.core_maps())

    def test_each_supported_klon_type_has_a_diagram(self):
        self.assertEqual(set(self.app_maps()), {4, 8})

    def test_diagrams_need_no_html_escaping(self):
        # The app injects these raw into a <pre>; escape() must be a no-op.
        for diagram in self.app_maps().values():
            self.assertNotRegex(diagram, r"[<>&]")


if __name__ == "__main__":
    unittest.main()
