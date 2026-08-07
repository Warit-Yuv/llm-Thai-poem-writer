# llm-Thai-poem-writer

Turning สุนทรภู่'s **พระอภัยมณี** into training data for a small LLM that writes
กลอนแปด — with the จังหวะ (beat) structure marked, not just the text.

132 chapters, **97,379 วรรค**. The corpus is the easy part; getting the syllable
counts right is not.

## The problem

กลอนแปด is defined by syllable count and beat placement, so a training row is
only as good as its syllable count. Thai has no spaces between words, and the
tools that recover them are wrong often enough to matter:

- **`pronunciate(engine="w2p")` hallucinates on 2–4% of words**, worst on
  Pali/Sanskrit loanwords — `ใหญ่โต` comes back as `ผะ-หย่น`.
- **`newmm` shatters rare and proper nouns** — `อินทคาม` → `อิน|ท|คาม`, leaving
  an orphan consonant that w2p then invents syllables from (`น` → `นะ-โจน` = 2).
- Errors are **silent**. `อัปยศอดสูเสนาใน` once counted 6 instead of 8, which made
  it look like a legitimate short opener, and it left the review queue quietly.

So the design rule everywhere in this repo is: **when unsure, flag — never emit a
wrong slice silently.** The meter is the checksum. A miscount that survives
usually breaks the วรรค total, and a broken total gets flagged instead of shipped.

## Quickstart

```bash
pip install "pythainlp[ssg]" numpy     # Python 3.12, pythainlp 5.3.4
python CleanData.py PhraAphai/phraAphai_1.txt
```

Bare `pip install pythainlp` is **not** enough: it pulls in only `tzdata`, and
both syllable engines this pipeline leans on are optional extras — `ssg` backs
`syllable_tokenize(engine="ssg")`, `numpy` loads the w2p model. The first
`pronunciate()` call also downloads `thai_w2p_v0.2.npz` (9.3 MB) into
`~/pythainlp-data`, so the first run needs a network connection.

(`pandas` and `tqdm` are needed only by `build_overrides.py` and
`override_draft_cleaner.py`, not by the main pipeline.)

```
วรรค scanned: 491
flag rate:    7.1%  (35 flagged)
by kind:      body=479, irregular=12
๏ sections:   24, bad: 1
verdict:      foundation holds — grow OVERRIDES from flags
```

Probe a single line or word without a file:

```bash
python CleanData.py --wak "สนมนางแสนสุรางคนิกร"
```

## The review loop

Roughly 7% of วรรค can't be resolved automatically. They go to a spreadsheet, you
fix them, they come back:

```bash
python CleanData.py PhraAphai/phraAphai_1.txt --csv       # writes ok + not_ok CSVs
#   ... open Results/Export/not_ok/phraAphai_1_not_ok.csv in Excel,
#       type beat cuts into a/b/c (the machine's `guess` column is read-only)
python CleanData.py PhraAphai/phraAphai_1.txt --import    # merge answers
python CleanData.py PhraAphai/phraAphai_1.txt --csv       # fixed วรรค rejoin the export
```

`--resolve` does the same thing as an interactive terminal prompt if you prefer
that to Excel. Either way answers land in `<chapter>.txt.review.json`, keyed by
วรรค text, written immediately — quitting mid-chapter loses nothing.

**The a/b/c cells ship empty on purpose.** The machine's guess sits in a separate
read-only `guess` column, so importing an unedited file confirms *nothing*.
Prefilled cells would make "I reviewed this" and "I never opened the file"
indistinguishable — and unreviewed guesses would then be laundered into ground
truth. Copy `guess` across when you agree with it; put `x` in `a` to exclude a
วรรค; leave a row blank to defer it.

Cuts only, never edits: the beat cells must rejoin to the original วรรค exactly,
which is also what catches Excel autocorrect.

### What comes out

`Results/Export/ok/<chapter>_ok.csv` — 24 columns, `w1_a` … `w8_c`: two
consecutive บท (4 วรรค × 3 beats each), stride 1, so every สัมผัสระหว่างบท pair
appears. A บท holding an unresolved or excluded วรรค blocks its windows rather
than emitting a false rhyme pair.

### Validation data

```bash
python CleanData.py PhraAphai/phraAphai_7.txt --eval
```

`Results/Evaluate/<chapter>_ok.csv` — one บท per row, columns `w1`–`w4`.
Deliberately unlike the training export: **no beat marks** (the model generates
plain วรรค, so the reference must be plain too) and **no sliding windows** (an
interleaved window scores the same บท two or three times, weighting whatever it
overlaps).

It also blocks on a different rule. Training needs the จังหวะ resolved, so any
flagged วรรค blocks its บท. Eval never looks at จังหวะ, so only *text* problems
block: `irregular` (≥10 syllables — a merge or shatter) and `opener` (≤6). A วรรค
flagged "7 syllables — ambiguous" has sound text and an uncertain beat, so eval
keeps it. On chapter 1 that is 111 บท versus 90.

Consequence: **eval data needs no review pass.** The queue only fixes beats.

These are two **formats of the same corpus**, not a split — a chapter appears in
both folders. This repo only prepares data; nothing is trained here. Choosing the
held-out chapters belongs to the training code, which must not draw its eval set
from `Export/ok`.

## Layout

| Path | What |
|---|---|
| `PhraAphai/` | 132 source chapters, plus `.review.json` checkpoints |
| `CleanData.py` | จังหวะ marker + CSV review loop — the main pipeline |
| `test_cleandata.py` | self-checks (`pytest` or `python test_cleandata.py`) |
| `Noto_tokenizer.py` | `POETRY_OVERRIDES`, the hand-verified syllable map |
| `build_overrides.py`, `build_g2p_dict.py`, `override_draft_cleaner.py` | override generation, four guards against w2p hallucination — see `OVERRIDE_PIPELINE.md` |
| `poetry_overrides*.py` | generated override dicts (~3.5k and ~6k entries) |
| `Results/Export/ok/`, `Results/Export/not_ok/` | export rows, and the review queue |
| `Results/Evaluate/` | the same corpus in evaluation format |
| `core.py` | vendored PyThaiNLP `KhaveeVerifier` (Apache-2.0), kept for patching |

## Status

Working and tested: syllable counting, beat placement (including cuts that fall
mid-word — `ข้าชื่อวิ | เชียรโมรา`), the ๏-section checksum that catches a
*dropped* วรรค, and the CSV round trip.

Not done yet: the human review pass over the ~7% flagged วรรค across all 132
chapters, and the fine-tuning loop the export feeds.

Every entry in `OVERRIDES` is earned, not guessed — a dict entry applies to all
97k วรรค, and Thai runs words together, so a plausible-looking string silently
rewrites unrelated วรรค at the same syllable count. Add one only after a real
วรรค breaks, then re-check the corpus for collateral splits.

## Notes

No `LICENSE` file yet — worth adding before this is published. `core.py` is
third-party (PyThaiNLP, Apache-2.0) and carries its own SPDX headers.
