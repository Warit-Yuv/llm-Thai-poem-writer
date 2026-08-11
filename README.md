# llm-Thai-poem-writer

This project converts **พระอภัยมณี** by สุนทรภู่ into training data for a
compact language model that writes กลอนแปด. The dataset records the จังหวะ
(beat) structure as well as the original text.

The source collection contains 132 chapters and **97,379 วรรค**. Corpus
size is not the main challenge; reliable syllable counts and beat boundaries
are.

## Research problem

กลอนแปด is constrained by syllable count, จังหวะ placement, and สัมผัส. A
training row is therefore only as reliable as its syllable analysis. Thai
normally has no spaces between words, and automatic segmentation and
pronunciation tools can fail often enough to affect the dataset:

- `pronunciate(engine="w2p")` can hallucinate pronunciations, especially for
  Pali and Sanskrit loanwords.
- `newmm` can split rare words and proper nouns into invalid fragments. A
  pronunciation model may then invent syllables for an orphan consonant.
- These errors are silent and can make an invalid วรรค appear metrically valid.

The repository follows one safety rule: **when the system is uncertain, it
flags the วรรค instead of silently emitting a potentially incorrect split.**
The expected meter acts as a checksum; most segmentation errors alter the
total syllable count and are routed to review.

## Quick start

```bash
pip install "pythainlp[ssg]==5.3.5" numpy
python CleanData.py Dataset/PhraAphai/phraAphai_1.txt
```

The project targets Python 3.12 and PyThaiNLP 5.3.5. Installing base
`pythainlp` alone is not sufficient because the pipeline uses optional
components. The `ssg` extra supports `syllable_tokenize(engine="ssg")`, and
`numpy` is required by the w2p model. The first `pronunciate()` call downloads
`thai_w2p_v0.2.npz` (about 9.3 MB) to the local PyThaiNLP data directory, so the
first run requires a network connection.

`pandas` and `tqdm` are required only by `build_overrides.py` and
`override_draft_cleaner.py`, not by the main pipeline.

Example summary:

```text
วรรค scanned:       491
flag rate:          7.1% (35 flagged)
by kind:            body=479, irregular=12
ฟองมัน sections:    24, bad=1
verdict:            foundation holds; grow OVERRIDES from reviewed flags
```

Probe a single วรรค without loading a file:

```bash
python CleanData.py --wak "<THAI_VERSE_LINE>"
```

## Review workflow

Approximately 7% of วรรค cannot be resolved automatically. The pipeline
exports them for human review and can then import the reviewed beat cuts:

```bash
python CleanData.py Dataset/PhraAphai/phraAphai_1.txt --csv
# Open Results/Export/not_ok/phraAphai_1_not_ok.csv in a spreadsheet editor.
# Enter beat cuts in columns a, b, and c. Treat the guess column as read-only.
python CleanData.py Dataset/PhraAphai/phraAphai_1.txt --import
python CleanData.py Dataset/PhraAphai/phraAphai_1.txt --csv
```

Use `--resolve` for the equivalent interactive terminal workflow. Reviewed
answers are saved immediately in `<chapter>.txt.review.json`, keyed by the
original วรรค, so interrupting a review does not discard completed work.

The `a`, `b`, and `c` cells are empty by design. Machine suggestions remain in
a separate read-only `guess` column. This prevents an untouched spreadsheet
from being mistaken for human-confirmed ground truth. Copy the suggestion when
it is correct, enter `x` in column `a` to exclude a วรรค, or leave the row blank
to defer it.

Reviewers may insert beat boundaries but must not edit the text. The three beat
cells must concatenate to the exact original วรรค; this check also detects
spreadsheet autocorrection.

### Training export

`Results/Export/ok/<chapter>_ok.csv` contains 24 columns, from `w1_a` through
`w8_c`. Each row represents two consecutive บท (four วรรค each) with three
จังหวะ per วรรค. The export uses a stride of one บท so every สัมผัสระหว่างบท
pair appears. A บท containing an unresolved or excluded วรรค blocks its windows
instead of emitting a false สัมผัส pair.

### Evaluation data

```bash
python CleanData.py Dataset/PhraAphai/phraAphai_7.txt --eval
```

`Results/Evaluate/<work>/<chapter>_ok.csv` stores one four-วรรค บท per row
in columns `w1` through `w4`, with one subdirectory per literary work. Unlike
the training export, evaluation rows contain no beat marks and use no sliding
windows. A generated วรรค is plain text, so the reference must also be plain
text; avoiding overlapping windows also prevents repeated scoring of the same
บท.

Training and evaluation apply different blocking rules. Training requires
resolved จังหวะ, so any flagged วรรค blocks its บท. Evaluation does not use
beat cuts; it blocks only textual problems: `irregular` for ten or more
syllables and `opener` for six or fewer. A seven-syllable วรรค with an ambiguous
จังหวะ remains usable for evaluation. In chapter 1, this yields 111 evaluation
บท compared with 90 training บท.

Evaluation data therefore requires no beat-review pass. The review queue exists
to establish reliable จังหวะ boundaries.

The training and evaluation directories are two formats of the same corpus,
not a predefined train/test split. This repository prepares data but does not
train a model. Held-out chapters must be selected by the training code and must
not be sampled from `Export/ok` as if it were an independent corpus.

## Repository layout

| Path | Purpose |
|---|---|
| `Dataset/` | Source works and `.review.json` checkpoints |
| `CleanData.py` | จังหวะ annotation and CSV review pipeline |
| `test_cleandata.py` | Pipeline self-checks |
| `Noto_tokenizer.py` | `POETRY_OVERRIDES`, the curated syllable map |
| `build_overrides.py`, `build_g2p_dict.py`, `override_draft_cleaner.py` | Override generation and safeguards against pronunciation hallucinations; see `OVERRIDE_PIPELINE.md` |
| `poetry_overrides*.py` | Generated override dictionaries |
| `Results/Export/ok/` | Reviewed training rows |
| `Results/Export/not_ok/` | Human-review queue |
| `Results/Evaluate/<work>/` | Evaluation-format corpus, grouped by work |
| `core.py` | Vendored and patched PyThaiNLP `KhaveeVerifier` |
| `ui/` | Streamlit research interface and UI tests |

## Current status

Implemented and tested:

- syllable counting;
- จังหวะ placement, including boundaries inside a lexical word;
- ฟองมัน-section checksums that detect dropped วรรค;
- the CSV export/import round trip;
- กลอนสี่ and กลอนแปด structural and สัมผัส inspection in the Streamlit UI.

Outstanding work includes human review of the flagged วรรค across all 132
chapters and the downstream fine-tuning workflow.

Every entry in `POETRY_OVERRIDES` must be supported by an observed failure and
human verification. An override applies corpus-wide, so a plausible but
incorrect entry can silently alter unrelated lines with the same surface form.
After adding an override, re-check the entire corpus for collateral splits.

## License note

The repository does not yet contain a top-level `LICENSE` file. Add one before
public release. `core.py` contains third-party PyThaiNLP code under Apache-2.0
and retains its SPDX notices.
