from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class StreamlitSmokeTests(unittest.TestCase):
    def test_simple_flow_loads_example_and_analyzes_without_exception(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.tabs), 0)
        self.assertEqual(app.segmented_control[0].value, 8)
        app.button(key="use_example").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            [app.text_area(key=f"poem_cell_8_0_{index}").value for index in range(8)],
            ["บาท", "หลวง", "งก", "ตก", "ประ", "หม่า", "ให้", "ล่าทัพ"],
        )
        third_wak = [
            item.value
            for item in app.text_area
            if item.key.startswith("poem_cell_8_2_")
        ]
        self.assertEqual(
            third_wak,
            ["ให้", "รีบ", "เร่ง", "พวก", "พหล", "พล", "นิ", "กาย"],
        )
        app.button(key="analyze").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        summaries = [
            item.value for item in app.markdown if 'class="inspection-grid"' in item.value
        ]
        self.assertEqual(len(summaries), 1)
        for expected in ("จำนวนวรรค", ">4<", "พยางค์ผ่าน", "4/4", "สัมผัสผ่าน", "3/3"):
            self.assertIn(expected, summaries[0])
        app.button(key="expand_sound_table").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)

    def test_klon_four_can_be_selected_and_analyzed(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        app.segmented_control[0].set_value(4).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        app.button(key="use_example").click().run(timeout=30)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        summaries = [
            item.value for item in app.markdown if 'class="inspection-grid"' in item.value
        ]
        self.assertEqual(len(summaries), 1)
        for expected in ("จำนวนวรรค", ">4<", "พยางค์ผ่าน", "4/4", "สัมผัสผ่าน", "3/3"):
            self.assertIn(expected, summaries[0])

    def test_every_wak_of_a_multi_stanza_poem_is_rendered(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        stanza = """ทั้งสองถันสันทัดดอกบัวหลวง,เป็นพุ่มพวงงามสุดแรกผุดเผย,พลางประคองต้องเต้ามณฑาเชย,เจ้าพี่เอ๋ยนอนนิ่งไม่ติงองค์
โอบพระกรช้อนอุ้มแล้วจุมพิต,พระทรงฤทธิ์ปลุกชวนนวลหง,โฉมอำพันมาลาผวาองค์,เห็นพระทรงฤทธิไกรวิไลงาม"""
        # A complete poem may be pasted directly into the first word cell.
        app.text_area(key="poem_cell_8_0_0").set_value(stanza).run(timeout=30)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["report"]["line_count"], 8)
        grid = next(m.value for m in app.markdown if 'class="inspection-grid"' in m.value)
        # One card per วรรค — zip() against the 4 summary tiles used to cut this to 4.
        self.assertEqual(grid.count('class="line-card"'), 8)

    def test_editable_word_grid_follows_the_selected_klon_type(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        klon8_cells = [item for item in app.text_area if item.key.startswith("poem_cell_8_")]
        self.assertEqual(len(klon8_cells), 32)
        self.assertEqual(klon8_cells[0].label, "วรรคสดับ คำที่ 1")
        self.assertEqual(klon8_cells[-1].label, "วรรคส่ง คำที่ 8")
        wire_routes = [
            item.value for item in app.markdown if 'class="rhyme-wire ' in item.value
        ]
        self.assertEqual(len(wire_routes), 3)
        self.assertIn('class="rhyme-wire top"', wire_routes[0])
        self.assertIn('class="rhyme-wire middle"', wire_routes[1])
        self.assertIn('class="rhyme-wire bottom"', wire_routes[2])
        self.assertFalse(any("inter-stanza" in route for route in wire_routes))

        app.segmented_control[0].set_value(4).run(timeout=30)
        klon4_cells = [item for item in app.text_area if item.key.startswith("poem_cell_4_")]
        self.assertEqual(len(klon4_cells), 16)
        self.assertEqual(klon4_cells[-1].label, "วรรคส่ง คำที่ 4")

    def test_text_box_normalizes_punctuation_and_populates_the_grid(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        stanza = "บาทหลวงงกตกประหม่าให้ล่าทัพ, จะย้อนกลับไปไม่ได้ดั่งใจหมาย, ให้รีบเร่งพวกพหลพลนิกาย, ไปหาดทรายเต็มกลัวหนังหัวพอง"
        app.text_area(key="poem_input").set_value(stanza).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.session_state["poem_input"].splitlines()), 4)
        self.assertNotIn(",", app.session_state["poem_input"])
        self.assertTrue(app.text_area(key="poem_cell_8_0_0").value)

    def test_add_button_adds_one_baht_with_two_waks(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        app.button(key="add_baht").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["editor_baht_count"], 3)
        cells = [item for item in app.text_area if item.key.startswith("poem_cell_8_")]
        self.assertEqual(len(cells), 48)
        wire_routes = [
            item.value for item in app.markdown if 'class="rhyme-wire ' in item.value
        ]
        self.assertTrue(any('class="rhyme-wire inter-stanza"' in route for route in wire_routes))

    def test_rhyme_research_tool_explains_a_pair(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        app.text_input(key="rhyme_first").set_value("หมาย").run(timeout=30)
        app.text_input(key="rhyme_second").set_value("กาย").run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        results = [item.value for item in app.markdown if 'class="rhyme-lab-result"' in item.value]
        self.assertEqual(len(results), 1)
        self.assertIn("สัมผัสกัน", results[0])
        self.assertIn("คำอ่าน", results[0])
        self.assertNotIn("<th>คำ</th>", results[0])
        self.assertNotIn("<th>พยางค์</th>", results[0])
        self.assertIn("สระ", results[0])
        self.assertIn("มาตรา", results[0])


if __name__ == "__main__":
    unittest.main()
