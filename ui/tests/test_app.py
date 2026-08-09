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

    def test_rhyme_research_tool_explains_a_pair(self):
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run(timeout=30)

        app.text_input[0].set_value("หมาย")
        app.text_input[1].set_value("กาย")
        rhyme_button = next(button for button in app.button if button.label == "เปรียบเทียบสัมผัส")
        rhyme_button.click().run(timeout=30)

        self.assertEqual(len(app.exception), 0)
        results = [item.value for item in app.markdown if "สัมผัสกัน" in item.value]
        self.assertEqual(len(results), 1)
        self.assertIn("มาตรา เกย", results[0])


if __name__ == "__main__":
    unittest.main()
