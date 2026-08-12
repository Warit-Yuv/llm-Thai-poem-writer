from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


class StreamlitSmokeTests(unittest.TestCase):
    def test_ui_keeps_project_link_but_hides_heading_links_and_input_instructions(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertIn('<a class="project-link"', source)
        self.assertIn('href="https://github.com/Warit-Yuv/llm-Thai-poem-writer"', source)
        self.assertIn('a[href^="#"]', source)
        self.assertIn('[data-testid="InputInstructions"]', source)
        for removed_copy in (
            "พิมพ์ทีละคำ หรือวางกลอนลงในช่องใดก็ได้",
            "ระบบจัดวรรคและตัดช่องว่างหรือเครื่องหมายคั่นให้",
            "เครื่องมือเรียนรู้เสียงสัมผัสของคำไทย",
        ):
            self.assertNotIn(removed_copy, source)

    def test_live_preview_bridge_sends_raw_text_without_browser_tokenization(self):
        bridge_path = (
            Path(__file__).resolve().parents[1]
            / "live_preview_bridge"
            / "index.html"
        )
        bridge = bridge_path.read_text(encoding="utf-8")

        self.assertIn('addEventListener("input", handlePoemInput', bridge)
        self.assertIn(".st-key-poem_input textarea", bridge)
        self.assertIn("hideStaleAnalysis", bridge)
        self.assertIn("streamlit:setComponentValue", bridge)
        self.assertIn("debounceMs", bridge)
        self.assertIn("poem-rhyme-overlay", bridge)
        self.assertIn("getBoundingClientRect", bridge)
        self.assertIn("ResizeObserver", bridge)
        self.assertIn("function lastSlot(cells, line)", bridge)
        self.assertIn("point(stanzaStart, lastSlot(cells, stanzaStart))", bridge)
        self.assertIn("point(stanzaStart + 3, lastSlot(cells, stanzaStart + 3))", bridge)
        self.assertNotIn("Intl.Segmenter", bridge)
        self.assertNotIn("segmentLine", bridge)

    def test_live_preview_callback_uses_project_tokenizer(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        source = app_path.read_text(encoding="utf-8")

        self.assertIn("def apply_live_preview_bridge()", source)
        self.assertIn("load_poem_into_grid(raw_text, klon_type, normalize_text=False)", source)
        self.assertIn("words = tokenize_editor_syllable_units(wak)", source)

    def test_simple_flow_loads_example_and_analyzes_without_exception(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.tabs), 0)
        self.assertEqual(app.segmented_control[0].value, 8)
        app.button(key="use_example").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            [app.text_area(key=f"poem_cell_8_0_{index}").value for index in range(9)],
            ["บาท", "หลวง", "งก", "ตก", "ประ", "หม่า", "ให้", "ล่า", "ทัพ"],
        )
        third_wak = [
            item.value
            for item in app.text_area
            if item.key.startswith("poem_cell_8_2_")
        ]
        self.assertEqual(
            third_wak,
            ["ให้", "รีบ", "เร่ง", "พวก", "พะ", "หน", "พล", "นิ", "กาย"],
        )
        app.button(key="analyze").click().run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        bridge = app.get("component_instance")[0]
        self.assertIn('"canonical_text":', bridge.proto.json_args)
        self.assertNotIn('"authoritative":', bridge.proto.json_args)
        self.assertIn("report", app.session_state)
        summaries = [
            item.value for item in app.markdown if 'class="result-section"' in item.value
        ]
        self.assertEqual(len(summaries), 1)
        for expected in ("พยางค์ผ่าน", "สัมผัสผ่าน", "<strong>บท</strong>", "<strong>บาท</strong>", "<strong>วรรค</strong>"):
            self.assertIn(expected, summaries[0])
        self.assertIn('class="rhyme-a"', summaries[0])
        self.assertIn('class="rhyme-b"', summaries[0])
        self.assertIn('class="rhyme-a">ทัพ</span>', summaries[0])
        self.assertIn('class="rhyme-a">กลับ</span>', summaries[0])
        self.assertNotIn('class="rhyme-a">ล่าทัพ</span>', summaries[0])

    def test_failed_result_shows_syllable_and_rhyme_issue_sections(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        poem = """บาทหลวงงกตกประหม่าให้ล่าทัพ
จะย้อนกลับไปไม่ได้ดั่งใจหมาย
ให้รีบเร่งพวกพหลพลนิกาย
สั้น"""
        app.text_area(key="poem_input").set_value(poem).run(timeout=30)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        dashboard = next(
            item.value for item in app.markdown if 'class="result-section"' in item.value
        )
        self.assertIn("พยางค์ไม่ผ่าน", dashboard)
        self.assertIn("สัมผัสไม่ผ่าน", dashboard)
        self.assertIn("rhyme-fail", dashboard)
        self.assertIn('class="result-rhyme-warning-icon"', dashboard)
        self.assertIn("<strong>ไม่สามารถตรวจจับสัมผัสได้ครบ</strong>", dashboard)
        issues = next(
            item.value for item in app.markdown if 'class="result-issue-section"' in item.value
        )
        self.assertIn("พยางค์ที่ต้องตรวจ", issues)
        self.assertIn("สัมผัสที่ต้องตรวจ", issues)
        self.assertIn("result-syllable-card", issues)
        self.assertNotIn("เกณฑ์ 7–9 พยางค์", issues)
        self.assertLess(issues.index("จำนวนทั้งหมด 1 พยางค์"), issues.index(">สั้น</div>"))
        self.assertLess(issues.index(">สั้น</div>"), issues.index("วรรค 4 · วรรคส่ง"))

    def test_klon_four_can_be_selected_and_analyzed(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        app.segmented_control[0].set_value(4).run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        app.button(key="use_example").click().run(timeout=30)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        summaries = [
            item.value for item in app.markdown if 'class="result-section"' in item.value
        ]
        self.assertEqual(len(summaries), 1)
        for expected in ("พยางค์ผ่าน", "สัมผัสผ่าน", "<strong>บท</strong>", "<strong>บาท</strong>", "<strong>วรรค</strong>"):
            self.assertIn(expected, summaries[0])

    def test_every_wak_of_a_multi_stanza_poem_is_rendered(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        stanza = """ทั้งสองถันสันทัดดอกบัวหลวง,เป็นพุ่มพวงงามสุดแรกผุดเผย,พลางประคองต้องเต้ามณฑาเชย,เจ้าพี่เอ๋ยนอนนิ่งไม่ติงองค์
โอบพระกรช้อนอุ้มแล้วจุมพิต,พระทรงฤทธิ์ปลุกชวนนวลหง,โฉมอำพันมาลาผวาองค์,เห็นพระทรงฤทธิไกรวิไลงาม"""
        stanza = stanza.replace(",", "\n")
        # A complete poem may be pasted directly into the first word cell.
        app.text_area(key="poem_cell_8_0_0").set_value(stanza).run(timeout=30)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["report"]["line_count"], 8)
        grid = next(m.value for m in app.markdown if 'class="result-section"' in m.value)
        wak_cards = grid.count('class="result-wak"') + grid.count('class="result-wak right"')
        self.assertEqual(wak_cards, 8)
        self.assertEqual(grid.count('class="result-stanza"'), 2)
        for expected in ("วรรคที่ 5", "วรรคที่ 8", "บาทที่ 3", "บาทที่ 4"):
            self.assertIn(expected, grid)

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
        self.assertEqual(len(wire_routes), 2)
        self.assertIn('class="rhyme-wire top"', wire_routes[0])
        self.assertIn('class="rhyme-wire middle"', wire_routes[1])
        self.assertEqual(wire_routes[0].count("wire-option"), 4)
        self.assertEqual(wire_routes[1].count("wire-option"), 4)
        self.assertIn("wire-extension", wire_routes[0])
        self.assertIn("--solid-resume:74.6%", wire_routes[1])
        self.assertIn("--edge:1.2%", wire_routes[1])
        self.assertFalse(any("inter-stanza" in route for route in wire_routes))

        app.segmented_control[0].set_value(4).run(timeout=30)
        klon4_cells = [item for item in app.text_area if item.key.startswith("poem_cell_4_")]
        self.assertEqual(len(klon4_cells), 16)
        self.assertEqual(klon4_cells[-1].label, "วรรคส่ง คำที่ 4")
        klon4_top_wire = next(
            item.value
            for item in app.markdown
            if 'class="rhyme-wire top"' in item.value
        )
        self.assertEqual(klon4_top_wire.count("wire-option"), 2)

    def test_each_line_adds_only_the_supported_extra_syllable_slot(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        # Blank Klon 8 starts at eight cells. Nine detected editable syllables
        # add a ninth cell only to the affected lines.
        self.assertEqual(
            len([item for item in app.text_area if item.key.startswith("poem_cell_8_")]),
            32,
        )
        app.button(key="use_example").click().run(timeout=30)
        first_line = [
            item.value for item in app.text_area if item.key.startswith("poem_cell_8_0_")
        ]
        third_line = [
            item.value for item in app.text_area if item.key.startswith("poem_cell_8_2_")
        ]
        self.assertEqual(len(first_line), 9)
        self.assertEqual(first_line[-2:], ["ล่า", "ทัพ"])
        self.assertEqual(len(third_line), 9)

        # Klon 4 follows the same rule: four by default, five when detected.
        app.segmented_control[0].set_value(4).run(timeout=30)
        five_syllable_poem = """ฉันชื่อหมูกรอบนะ
ฉันชอบกินไก่นะ
แล้ววิ่งตามไปนะ
ไล่หมาน้ำทองนะ"""
        app.text_area(key="poem_input").set_value(five_syllable_poem).run(timeout=30)
        for line_index in range(4):
            line_cells = [
                item
                for item in app.text_area
                if item.key.startswith(f"poem_cell_4_{line_index}_")
            ]
            self.assertEqual(len(line_cells), 5)
            self.assertEqual(line_cells[-1].label, f"{('วรรคสดับ', 'วรรครับ', 'วรรครอง', 'วรรคส่ง')[line_index]} คำที่ 5")

    def test_typing_two_syllables_in_the_last_default_cell_expands_and_shrinks(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        app.text_area(key="poem_cell_8_0_7").set_value("ล่าทัพ").run(timeout=30)
        expanded = [
            item.value for item in app.text_area if item.key.startswith("poem_cell_8_0_")
        ]
        self.assertEqual(len(expanded), 9)
        self.assertEqual(expanded[-2:], ["ล่า", "ทัพ"])

        app.text_area(key="poem_cell_8_0_8").set_value("").run(timeout=30)
        collapsed = [
            item.value for item in app.text_area if item.key.startswith("poem_cell_8_0_")
        ]
        self.assertEqual(len(collapsed), 8)
        self.assertEqual(collapsed[-1], "ล่า")

    def test_hidden_spoken_syllables_expand_without_rewriting_the_source_poem(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)
        poem = """เห็นเรือรบตบตีมหาสมุทร
ยิงพันคุดเลโอโอ้โหเอะ
เห็นเรือรบตบตีมหาสมุทร
ยิงพันคุดเลโอโอ้โหเอะ"""

        app.text_area(key="poem_input").set_value(poem).run(timeout=30)
        first_line = [
            item.value for item in app.text_area if item.key.startswith("poem_cell_8_0_")
        ]
        second_line = [
            item.value for item in app.text_area if item.key.startswith("poem_cell_8_1_")
        ]

        self.assertEqual(
            first_line,
            ["เห็น", "เรือ", "รบ", "ตบ", "ตี", "มะ", "หา", "สะ", "หมุด"],
        )
        self.assertEqual(second_line, ["ยิง", "พัน", "คุด", "เล", "โอ", "โอ้", "โห", "เอะ"])
        self.assertEqual(app.session_state["poem_input"], poem)

        app.button(key="analyze").click().run(timeout=30)
        self.assertEqual(app.session_state["report"]["lines"][0]["text"], "เห็นเรือรบตบตีมหาสมุทร")
        self.assertEqual(app.session_state["report"]["lines"][0]["syllable_count"], 9)
        self.assertEqual(app.session_state["report"]["lines"][1]["syllable_count"], 8)

    def test_text_box_normalizes_punctuation_and_populates_the_grid(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        stanza = """บาทหลวง งกตกประหม่าให้ล่าทัพ,
จะย้อนกลับไป ไม่ได้ดั่งใจหมาย,
ให้รีบเร่ง พวกพหลพลนิกาย,
ไปหาดทรายเต็ม กลัวหนังหัวพอง,"""
        app.text_area(key="poem_input").set_value(stanza)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.session_state["poem_input"].splitlines()), 4)
        self.assertNotIn(",", app.session_state["poem_input"])
        self.assertTrue(app.text_area(key="poem_cell_8_0_0").value)

    def test_text_box_updates_grid_before_analysis_is_requested(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        stanza = """บาทหลวง งกตกประหม่าให้ล่าทัพ,
จะย้อนกลับไป ไม่ได้ดั่งใจหมาย,
ให้รีบเร่ง พวกพหลพลนิกาย,
ไปหาดทรายเต็ม กลัวหนังหัวพอง,"""
        app.text_area(key="poem_input").set_value(stanza).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            [app.text_area(key=f"poem_cell_8_0_{index}").value for index in range(9)],
            ["บาท", "หลวง", "งก", "ตก", "ประ", "หม่า", "ให้", "ล่า", "ทัพ"],
        )
        self.assertNotIn("report", app.session_state)

    def test_commas_and_spaces_do_not_create_new_editor_lines(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        poem = """วันนี้เป็นวัน,ที่ดีที่จะ
ทำสิ่งใหม่ เราจะ"""
        app.text_area(key="poem_input").set_value(poem).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            [app.text_area(key=f"poem_cell_8_0_{index}").value for index in range(8)],
            ["วัน", "นี้", "เป็น", "วัน", "ที่", "ดี", "ที่", "จะ"],
        )
        self.assertEqual(
            [app.text_area(key=f"poem_cell_8_1_{index}").value for index in range(5)],
            ["ทำ", "สิ่ง", "ใหม่", "เรา", "จะ"],
        )
        self.assertTrue(
            all(
                not app.text_area(key=f"poem_cell_8_2_{index}").value
                for index in range(8)
            )
        )

    def test_replacing_poem_then_switching_type_never_restores_the_old_poem(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        old_poem = """บาทหลวงงกตกประหม่าให้ล่าทัพ
จะย้อนกลับไปไม่ได้ดั่งใจหมาย
ให้รีบเร่งพวกพหลพลนิกาย
ไปหาดทรายเต็มกลัวหนังหัวพอง"""
        new_poem = """ดอกไม้บานผ่านฝนบนทางฝัน
คืนและวันผันผ่านกาลสมัย
แม้เหนื่อยนักจักก้าวคราวต่อไป
ด้วยหัวใจใฝ่ดีมีศรัทธา"""

        app.text_area(key="poem_input").set_value(old_poem)
        app.button(key="analyze").click().run(timeout=30)
        app.segmented_control[0].set_value(4).run(timeout=30)
        app.text_area(key="poem_input").set_value("")
        app.text_area(key="poem_input").set_value(new_poem)
        app.button(key="analyze").click().run(timeout=30)
        latest_text = app.session_state["poem_input"]

        app.segmented_control[0].set_value(8).run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["poem_input"], latest_text)
        self.assertIn("ดอกไม้", app.session_state["poem_input"])
        self.assertNotIn("บาทหลวง", app.session_state["poem_input"])
        self.assertTrue(app.text_area(key="poem_cell_8_0_0").value)

    def test_analyze_submits_the_replacement_poem_without_requiring_clear_all(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)
        old_poem = """บาทหลวงงกตกประหม่าให้ล่าทัพ
จะย้อนกลับไปไม่ได้ดั่งใจหมาย
ให้รีบเร่งพวกพหลพลนิกาย
ไปหาดทรายเต็มกลัวหนังหัวพอง"""
        new_poem = """ดอกไม้บานผ่านฝนบนทางฝัน
คืนและวันผันผ่านกาลสมัย
แม้เหนื่อยนักจักก้าวคราวต่อไป
ด้วยหัวใจใฝ่ดีมีศรัทธา"""

        app.text_area(key="poem_input").set_value(old_poem)
        app.button(key="analyze").click().run(timeout=30)
        app.text_area(key="poem_input").set_value("")
        app.text_area(key="poem_input").set_value(new_poem)
        app.button(key="analyze").click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        self.assertIn("ดอกไม้", app.session_state["analyzed_input"])
        self.assertNotIn("บาทหลวง", app.session_state["analyzed_input"])
        self.assertEqual(
            app.session_state["report"]["lines"][0]["text"],
            "ดอกไม้บานผ่านฝนบนทางฝัน",
        )

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
        stanza_brackets = [
            item.value for item in app.markdown if 'class="stanza-bracket"' in item.value
        ]
        baht_labels = [
            item.value for item in app.markdown if 'class="baht-label"' in item.value
        ]
        self.assertEqual(len(stanza_brackets), 2)
        self.assertTrue(any("บทที่ 2" in bracket for bracket in stanza_brackets))
        self.assertEqual(len(baht_labels), 3)
        self.assertEqual(sum("บาทเอก" in label for label in baht_labels), 2)
        self.assertEqual(sum("บาทโท" in label for label in baht_labels), 1)

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
