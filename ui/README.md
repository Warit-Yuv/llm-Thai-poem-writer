# Klon Pad Rhyme Checker UI

This Streamlit research interface presents structural analysis for กลอนสี่ and
กลอนแปด. สัมผัส verification is provided by the repository's
`core.KhaveeVerifier`.
Pronunciation lookup prioritizes the curated `POETRY_OVERRIDES` dictionary and
falls back to the PyThaiNLP w2p and ssg engines when necessary.

## Run locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r ui\requirements.txt
.\ui\run_ui.ps1
```

Alternatively, start Streamlit directly:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui\app.py
```

Open the URL printed by Streamlit, normally `http://localhost:8501`.

The repository-level `.streamlit/config.toml` hides deployment and developer
controls so the demonstration exposes only the project interface.

## Run the test suite

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s ui\tests -v
```

## Interface capabilities

- Switch between กลอนสี่ and กลอนแปด rules.
- Paste an entire poem or edit individual พยางค์ cells.
- Normalize spaces and punctuation before arranging the poem in the diagram.
- Add one บาท (two วรรค) at a time and inspect multiple บท.
- Require four วรรค per บท.
- Display proposed พยางค์ counts and จังหวะ grouping for every วรรค.
- Count ssg subword units under the same limits used by `core.check_klon`.
- Check the final syllable of the first line against the permitted opening
  positions of the second line.
- Check the final syllables of the second and third lines against each other.
- Check the final syllable of the third line against the permitted opening
  positions of the fourth line.
- Check สัมผัสระหว่างบท when the input contains more than one บท.
- Report the direct result of `core.KhaveeVerifier.check_klon`.
- Compare two candidate สัมผัส words and display คำอ่าน, สระ, and มาตรา.
- Download machine-readable JSON reports and CSV summaries.

The primary workflow is intentionally linear: enter a poem, inspect the live
diagram, run the checker, review the results, and download the report. Secondary
research details use progressive disclosure so the main task remains readable
without removing analytical functionality.

## Live-preview boundary

The live-preview component returns only raw textarea content to Python after a
short input debounce. Python then applies `tokenize_editor_units`, the same
project tokenizer used by the editable diagram. The browser does not implement
an independent Thai tokenizer and does not decide whether a poem passes.

Structural evaluation begins only after the user activates the check button.
This separation prevents the responsive preview from being mistaken for an
experimental result.

## Meter rules represented in the UI

For กลอนแปด, the checker considers the first five พยางค์ of the receiving วรรค,
with positions three and five treated as the principal สัมผัส positions. For
กลอนสี่, it considers the first two พยางค์, or the first three when the วรรค
contains five พยางค์. These positions follow
`core.KhaveeVerifier.check_klon()` in this repository.

## Score interpretation

`structural_score` is the proportion of implemented structural checks that
pass. It is not a score for literary quality, meaning, creativity, aesthetics,
or cultural value. Research reports should not use it as an overall poem-quality
metric without an independent human evaluation.

## Programmatic output

The backend is implemented in `ui/checker.py` and returns a JSON-serializable
dictionary:

```python
from checker import check_klon

report_4 = check_klon(poem_text, k_type=4)
report_8 = check_klon(poem_text, k_type=8)
```

The interface provides both the complete JSON report and a compact CSV summary
for reproducibility, audit, and paper experiments.
