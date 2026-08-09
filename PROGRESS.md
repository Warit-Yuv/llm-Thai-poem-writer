# Progress Log — llm-Thai-poem-writer (Klon-8)

Tracked sessions and current state of the **Klon-8 rhyme-detection evaluation**.
This file is updated after each working session so progress is visible at a glance.

---

## Current status (2026-08-09)

| Area | State |
|---|---|
| Evaluate dataset reorganisation | ✅ Done |
| `build_overrides.py` corpus path / multi-poem ingestion | ✅ Done |
| Evaluation plan (design + metrics) | ✅ Done |
| Checker A (pythainlp 5.0.1) instrumented | ✅ Done |
| Checker B (pythainlp 5.3.5) instrumented | ✅ Done |
| Checker D (Klonpad overrides) instrumented | ✅ Done |
| Checker C (Kongfha `word_check`) wrapper | ✅ Runs via Python 3.12 subprocess worker |
| Data loader (`data_loading.py`) | ✅ Done |
| Parity validation (A & B vs original `check_klon`) | ✅ 0 mismatches |
| Smoke test A/B/C/D on gold sample | ✅ Done |
| Full-corpus gold re-eval (post data-completeness fix) | ✅ A 73.4% / B 87.5% / C 85.4% / D 87.2% (rX 89/97/97/96) |
| Cross-chapter boundary rX check | ✅ 181/186 = 97.3% rhyme (report-only) |
| Checker C slowness mitigation (persistent workers + G2P cache) | ✅ Done (~49 min wall) |
| Augmentation (hard pos/neg operators) | ⏳ Deferred by author until re-eval is final |
| Evaluation harness + metrics | ⏳ Planned, not built |
| Report notebook (`Method_evaluation_script.ipynb`) | ⏳ Stub only |

---

## Session 1 — Evaluate dataset reorganisation

Moved the flat `*.csv` files in `Results/Evaluate/` into per-story folders so
each work is self-contained and future corpus expansion is tidy.

```
Results/Evaluate/
  khobut/          14 files
  khunChangKhunPhaen/  43 files
  phraAphai/      132 files
  phukaoTong/       1 file
  SuphasaetSonYing/ 1 file
```

---

## Session 2 — `build_overrides.py`: new corpus path + all-poem ingestion

The override pipeline previously read only `phraAphai_*_*.csv` from
`Results/Export/ok`. It now:

- Defaults to `Results/Evaluate` (the reorganised corpus).
- Recursively ingests **every** `*_ok.csv` across **all** poem subfolders.
- Handles both CSV layouts: old 24-column (`w1_a..w8_c`) and new 4-column
  (`w1..w4`).

Verified: corpus builds to 29,762 rows / ~3.0 M characters and contains text
from all five poems.

---

## Session 3 — Klon-8 rhyme-detection evaluation (current focus)

### Goal

Objectively compare the rhyme-detection effectiveness of four Klon-8 checkers
using `Results/Evaluate` as a gold standard, reported as accuracy, precision,
recall and F1 (per rule, per corruption type, per story, and overall). Written
for a conference paper: methods are described neutrally and limitations are
reported.

### Dataset (gold-positive counts; file-by-file, no cross-chapter chaining)

Each CSV row = one บท (4 waks). Inter-stanza rhyme (Wak4 → next row's Wak2) is
checked only between consecutive rows **within** a chapter; the first row of
each chapter is N/A for that rule. **Data-completeness fix (commit 53c6b29):**
`CleanData.write_eval` no longer drops waks with ≥10 syllables, so no บท is
removed and the inter-stanza rhyme chains (บท→บท, and chapter→chapter across
files) are preserved. Only the 3-วรรค opener at chapter start is cut and ๏ acts
are ignored. Counts below are the **updated, data-complete corpus**.

| story | files | บท | วรรค | within rhymes (×3) | inter links (rows−files) | **total rhyme checks** |
|---|---|---|---|---|---|---|
| SuphasaetSonYing | 1 | 200 | 800 | 600 | 199 | 799 |
| khobut | 14 | 1,303 | 5,212 | 3,909 | 1,289 | 5,198 |
| khunChangKhunPhaen | 43 | 10,543 | 42,172 | 31,629 | 10,500 | 42,129 |
| phraAphai | 132 | 24,342 | 97,368 | 73,026 | 24,210 | 97,236 |
| phukaoTong | 1 | 87 | 348 | 261 | 86 | 347 |
| **TOTAL** | **191** | **36,475** | **145,900** | **109,425** | **36,284** | **145,709** |

Per-rule gold positives: `r1`=36,475 · `r2`=36,475 · `r3`=36,475 · `rX`=36,284.
The dataset grew ~22% versus the pre-fix corpus (29,762 → 36,475 บท).

### The four checkers under evaluation

| ID | System | Basis | Rule set | Notes |
|---|---|---|---|---|
| A | Original PyThaiNLP | pythainlp **5.0.1** `check_klon` | r1, r2, rX | `subword_tokenize(engine="dict")`; no r3 |
| B | Rule-based PyThaiNLP | pythainlp **5.3.5** `check_klon` (merged KhaveeVerifier) | r1, r2, r3, rX | ssg tokenizer; improved `is_sumpus` |
| C | Kongfha `word_check` | `KlonSuphap-LM` `sumpass_eval.py` + `word_check.py` | r1, r2, r3, rX (+extra `รับ-ส่ง`) | tltk G2P romanisation; vowel-mattra compare |
| D | Klonpad | `extract_poetic_syllables` + `POETRY_OVERRIDES` | same as B (isolation) | override-enhanced segmentation |

Canonical rules: `r1_w1_w2`, `r2_w2_w3`, `r3_w3_w4`, `rX_inter`.

### Environment facts

- Project venv: `.venv` → **Python 3.14.3**, pythainlp **5.3.5** (release with the
  merged KhaveeVerifier; this is Checker B, importable directly).
- Global Python: **3.12.0**, has working `tltk.g2p` (used for Checker C).
- `ssg` installed; `tltk` installed in global only (see Blocker 1).

### Files created (Session 3)

```
Paper/
  data_loading.py                  # Evaluate -> Stanza records (per-file, N/A links)
  eval_checkers/
    __init__.py
    common.py                      # CheckerResult contract, canonical rule IDs
    _orig_core.py                  # vendored pythainlp 5.0.1 khavee/core.py (verbatim)
    _dev_core.py                   # vendored pythainlp 5.3.5 khavee/core.py (verbatim)
    original_khavee.py             # Checker A (instrumented, 5.0.1 logic)
    dev_khavee.py                  # Checker B (instrumented, 5.3.5 logic)
    klonpad_syllables.py           # extract_poetic_syllables + process_w2p (from notebook)
    klonpad_checker.py             # Checker D
    kongfha_checker.py             # Checker C (needs tltk; see Blocker 1)
third_party/KlonSuphap-LM/         # cloned reference repo
```

Vendoring rationale: both `check_klon` implementations are self-contained
pure-Python classes; vendoring them (with each version's **own** `is_sumpus`)
lets A and B run in one process and be instrumented per-rule without venv
switching.

### Design decisions / assumptions

1. **Stanza = 1 CSV row (4 waks)**, matching the checkers' internal model.
2. **File-by-file evaluation**; no cross-chapter chaining.
3. **N/A handling**: `rX_inter` is excluded from denominators when no previous
   stanza exists.
4. **Hard-positive probes (recall)** from normalization words
   (ไทย/ทัย/ฤทัย/ไท, กำ/กรรม/กัม, บัน/บรร — these *should* rhyme when correctly
   normalized) and tricky-word buckets (karun, ฤ, clusters, true-final).
5. **Hard-negative probes (precision)** from targeted corruption operators
   (mattra swap incl. ล/ย, long/short vowel swap, karun traps, ฤ traps,
   cluster traps, true-final traps). All constructed negatives are verified
   against the 5.3.5 oracle `is_sumpus` before acceptance.
6. Checker C maps `สดับ-รับ/รับ-รอง/รอง-ส่ง/cross` → `r1/r2/r3/rX`; its extra
   `รับ-ส่ง` rule is reported separately in `meta`.
7. Tone (เอก/โท) is out of scope for the primary rhyme metrics (reported
   optionally as a secondary table).

### Known weaknesses reported for Checker C (Kongfha)

- Vowel-mattra comparison **ignores the final consonant** → likely false
  accepts mattra swaps (incl. ล/ย).
- Long/short vowels collapsed (`replace_long_short`) → false accepts vowel
  length swaps.
- Any `tltk` G2P `<Fail>` drops the whole 8-wak unit (`WordFail`); waks with
  <5 or >10 romanised syllables drop the unit (`LengthFail`) → coverage loss on
  karun/ฤ/rare words.
- 8-wak chunking skips every-other inter-stanza link (only `Wak4↔Wak6` inside
  each chunk).
- Two divergent copies of `sumpass_score` exist in the repo; we use the
  `sumpass_eval.py` version.

### Blocker 1 — `tltk` / `gensim` on Python 3.14

`pip install tltk` in the venv fails because `gensim` has **no prebuilt wheel
for Python 3.14** and fails to compile from source. Resolution adopted:
**run Checker C under the global Python 3.12** (where `tltk.g2p` works) via a
small subprocess worker (`kongfha_worker.py`, stdin/stdout JSON), invoked from
the venv-based harness. The interpreter path is configurable via the
`KONGFHA_PYTHON` environment variable (default: the global Python 3.12).
This environment constraint will be documented in the paper's reproducibility
section.

---

## Session 5 — Full-corpus gold re-evaluation after the data-completeness fix (2026-08-09)

### Why re-evaluate

The user fixed the ≥10-syllable-wak truncation bug (commit 53c6b29), which had
severed inter-stanza rhyme chains and made gold rX look ~72% "valid". With the
corpus now complete (36,475 บท / 145,900 วรรค / 145,709 gold checks), all four
checkers were re-run over the **entire** corpus.

### Full-corpus gold acceptance (per story) — stanza_ok% and r1/r2/r3/rX

**A = pythainlp 5.0.1** (no r3 — N/A):

| story | stanza_ok | r1 | r2 | r3 | rX | n (drop) |
|---|---|---|---|---|---|---|
| SuphasaetSonYing | 76.9% | 90 | 88 | – | 89 | 199 (1) |
| khobut | 70.5% | 86 | 87 | – | 88 | 1,301 (2) |
| khunChangKhunPhaen | 76.2% | 86 | 92 | – | 92 | 10,532 (11) |
| phraAphai | 72.4% | 87 | 88 | – | 87 | 24,307 (35) |
| phukaoTong | 67.8% | 86 | 80 | – | 83 | 87 (0) |
| **TOTAL** | **73.4%** | **86** | **89** | **–** | **89** | **36,426 (49)** |

**B = pythainlp 5.3.5:**

| story | stanza_ok | r1 | r2 | r3 | rX | n (drop) |
|---|---|---|---|---|---|---|
| SuphasaetSonYing | 91.0% | 98 | 97 | 96 | 97 | 200 (0) |
| khobut | 86.6% | 94 | 97 | 94 | 97 | 1,303 (0) |
| khunChangKhunPhaen | 87.3% | 94 | 98 | 95 | 98 | 10,543 (0) |
| phraAphai | 87.6% | 95 | 96 | 96 | 96 | 24,342 (0) |
| phukaoTong | 81.6% | 91 | 94 | 95 | 94 | 87 (0) |
| **TOTAL** | **87.5%** | **95** | **96** | **95** | **97** | **36,475 (0)** |

**D = Klonpad (overrides):**

| story | stanza_ok | r1 | r2 | r3 | rX | n (drop) |
|---|---|---|---|---|---|---|
| SuphasaetSonYing | 89.0% | 98 | 95 | 96 | 95 | 200 (0) |
| khobut | 85.6% | 94 | 97 | 93 | 97 | 1,303 (0) |
| khunChangKhunPhaen | 83.2% | 93 | 97 | 93 | 97 | 10,543 (0) |
| phraAphai | 89.1% | 97 | 96 | 96 | 96 | 24,342 (0) |
| phukaoTong | 77.0% | 90 | 92 | 93 | 93 | 87 (0) |
| **TOTAL** | **87.2%** | **95** | **96** | **95** | **96** | **36,475 (0)** |

**C = Kongfha word_check** (evaluates 2 stanzas per 8-wak unit; drops =
WordFail/LengthFail/WorkerError → coverage reported separately):

| story | stanza_ok | r1 | r2 | r3 | rX | n (drop, we) | coverage |
|---|---|---|---|---|---|---|---|
| SuphasaetSonYing | 87.1% | 95 | 99 | 92 | 98 | 394 (4, 0) | 99.0% |
| khobut | 83.7% | 92 | 96 | 93 | 96 | 2,546 (32, 0) | 98.8% |
| khunChangKhunPhaen | 80.5% | 91 | 97 | 90 | 97 | 19,244 (1,756, 0) | 91.6% |
| phraAphai | 87.6% | 94 | 96 | 96 | 96 | 47,134 (1,284, 2) | 97.4% |
| phukaoTong | 80.0% | 92 | 94 | 92 | 92 | 160 (12, 0) | 93.0% |
| **TOTAL** | **85.4%** | **93** | **97** | **94** | **97** | **69,478 (3,088, 2)** | **95.7%** |

C's coverage loss concentrates in khunChangKhunPhaen (8.4% dropped — older,
more archaic wording trips tltk G2P `<Fail>`/length rules). All results are
saved in `Paper/eval_checkers/full_gold_results.json` (per story, per rule).

### Key finding: the rX fix is confirmed

On the complete corpus the inter-stanza rule (rX) holds at **~96–97%** for
B/C/D (A 89% — its weaker `is_sumpus`/tokenizer, not the gold). This confirms
the ~72% pre-fix figure was entirely a data-completeness artifact. Per-story rX
(B): khunChangKhunPhaen 98%, khobut/SuphasaetSonYing 97%, phraAphai 96%,
phukaoTong 94%.

### Cross-chapter boundary rX check (report-only; checker B; primary metric stays file-by-file)

**181/186 = 97.3%** of chapter boundaries rhyme (last w4 of chapter N vs first
w2 of chapter N+1). This **confirms the author's observation** that the fixed
data is correct even across chapters. The 5 non-rhyming boundaries:
- 3 are **genuine chapter resets** (all of A/B/D agree): khobut_5→6 (ตัว→ได้),
  khunChangKhunPhaen_30→31 (เพลา→ษา), phraAphai_22→23 (ศี→ศา).
- 2 are **checker-B edge cases** that likely rhyme: KCKP_33→34 (นิทรา→นาถา,
  A,D=Y) and phraAphai_88→89 (แพง→แข็ง, A=Y) — same-matra open-แ-/แม่กง pairs
  that B's `is_sumpus` rejects. Including these, true rate ≈ 183/186 (98.4%).

### Bug found & fixed during the cross-chapter check

`data_loading._chapter_num` ran its digit regex on the **full path**; the path
contains `SIIT_Year_4`, so every chapter's sort key was the constant `4` and the
stable sort silently kept lexicographic order (e.g. khobut: `10..14,1..9`). This
corrupted the report-only cross-chapter check (bogus book-end "boundaries"
like khobut_14→khobut_1) but **not** any per-file metric (chapter grouping and
in-chapter row order are independent of file ordering). Fixed to sort on the
basename; cross-chapter results above are post-fix.

### Status

- A/B/D full-corpus gold acceptance: ✅ done (tables above).
- C full-corpus gold acceptance: ✅ done (table above; 10 persistent workers,
  ~49 min total, coverage 95.7%).
- Cross-chapter boundary rX check: ✅ done — 181/186 rhyme (97.3%), ~98% incl.
  B edge cases; confirms data completeness across chapters too.

### Bug found & fixed during the full run

Checker A (5.0.1) crashed on single-character tokens: its vendored
`check_marttra` does `word[-2]`, raising `IndexError` (the original `check_klon`
bails via try/except and emits a generic error). A/B/D now mark such stanzas as
**dropped (no prediction)** instead of crashing — the same contract Checker C
already used for WordFail/LengthFail. A drops 49/36,475 (0.13%), B/D drop 0.

### Checker C is slow — stated honestly, and mitigated

tltk's G2P is a single-threaded pure-Python model. Measured on the full corpus
the worker sustains only ~2 units/s (~0.5 s per 8-wak unit), so the 36,284-unit
corpus is **~5 CPU-hours** of work; a naive sequential run takes hours and
*looks hung*. Mitigations adopted (and this slowness will be reported in the
paper's reproducibility/limitations sections):

- **Persistent worker pool** (`Paper/eval_checkers/run_c_full.py`): N long-lived
  tltk subprocesses under the global Python 3.12. tltk/gensim import **once per
  worker**, not once per chunk (previously 13 imports ≈ minutes of waste).
- **Per-wak G2P cache** (`kongfha_worker.py`): the reference's `Get_Vow_and_Syl`
  is wrapped in an `lru_cache(200_000)`; repeated waks across a worker's share
  of the corpus are romanised once.
- **Parallelism**: `--workers 10` on the author's 10-core/16-thread machine
  (each worker ≈ 420 MB RAM ≈ 4.2 GB total). Actual run: **~49 min wall** for
  all 13 chunks (first wave of 10 chunks ≈ 32 min, remaining 3 ≈ 15 min).
- **Checkpointing + progress**: results saved per chunk to
  `Paper/eval_checkers/_c_chunks/chunk_*.jsonl` (resume-safe); per-chunk lines
  show units/s and elapsed time.
- Worker is pipe-deadlock-free (stdout reader thread per worker).

### D fallback ablation: w2p hurts, plain ssg helps (2026-08-09)

Investigation into why D (Klonpad, w2p fallback) trailed B. A controlled
variant `KlonpadSsgChecker` (overrides + **plain ssg** fallback, no w2p) was
added (`klonpad_checker.py`; `fallback` param threaded through
`extract_poetic_syllables` in `klonpad_syllables.py`) and run on the full corpus:

| checker | stanza_ok | r1 | r2 | r3 | rX |
|---|---|---|---|---|---|
| B (ssg, no overrides) | 87.5% | 95 | 96 | 95 | 97 |
| D w2p fallback (original) | 87.2% | 95 | 96 | 95 | 96 |
| **D ssg fallback** | **88.4%** | **96** | **97** | **95** | **97** |

1. **The w2p fallback strictly hurts.** D_ssg > D_w2p on *every* story (+1.2pp
   overall: SuphasaetSonYing +0.5, khobut +0.5, khunChangKhunPhaen +1.4,
   phraAphai +1.1, phukaoTong +2.3). The w2p `pronunciate`-romanise-then-ssg
   fallback introduces segmentation/pronunciation errors ("hallucinations") on
   words missing from the override dictionary; plain ssg on the Thai text is
   more reliable there.
2. **D_ssg beats B overall (88.4 vs 87.5)** — driven by phraAphai (90.2 vs 87.6,
   +2.6pp), the source corpus where override coverage is highest (92.8% of
   syllables). On out-of-corpus older texts B still leads: khunChangKhunPhaen
   87.3 vs 84.6 (coverage 85.6%), phukaoTong 81.6 vs 79.3 (80.5%),
   SuphasaetSonYing 91.0 vs 89.5 (88.0%), khobut 86.6 vs 86.1 (89.0%). The
   override dictionary helps most exactly where it was built; and the
   newmm+override path can mis-segment archaic karun words (ปฏิสนธิ์,
   ศพิธราชธรรม์) that pure ssg handles.
3. **w2p LRU cache size is not the bottleneck.** Full-corpus `process_w2p`
   working set = only **5,703 distinct words** (120,792 calls → 95.3% hit
   rate), which fits in the old `maxsize=8192`; the bump to 200,000 is
   unnecessary for the current corpus (kept as harmless future-proofing, and to
   match `Get_Vow_and_Syl`).
4. **Paper note**: D is reported two ways — `D_klonpad_w2p` (faithful to the
   original Klonpad notebook) and `D_klonpad_ssg_fallback` (ablation; best
   Klonpad configuration). Both are in `full_gold_results.json`.

## Session 4 — Checker runtime, parity validation, smoke test (2026-08-09)

### Checker C runtime (resolved)
- `Paper/eval_checkers/kongfha_worker.py` — standalone worker (runs under
global Python 3.12 with `tltk`): reads 8-wak units as JSON lines, outputs
Kongfha scores/fails. The reference splits waks on newline/tab, so the worker
joins the 8 waks with `\n`.
- `kongfha_checker.py` refactored into a subprocess client (no `tltk` import
at module level), so the whole package imports cleanly in the venv.

### Parity validation (passing)
- `Paper/parity_check.py` calls the original `check_klon` methods (still
present verbatim in the vendored `_orig_core`/`_dev_core`) and asserts the
instrumented checkers reproduce them.
- Result: **A: 0 mismatches (544 within + 538 inter), B: 0 mismatches**.
- One parser subtlety fixed: the 5.0.1 checker can emit two *identical*
error strings for a stanza when `w3_last == prev_w4_last` (e.g. จิต-ฤทธิ์ in
`khobut_11`), meaning both r2 and rX fail; the parser now flags both.

### Smoke test (gold sample: phukaoTong + phraAphai_1 + khobut_1 heads; 144 stanzas)

| checker | stanza_ok | r1 | r2 | r3 | rX |
|---|---|---|---|---|---|
| A (5.0.1) | 49.3% | 88% | 81% | – | 62% |
| B (5.3.5) | 63.9% | 96% | 95% | 94% | 72% |
| D (klonpad) | 67.4% | 97% | 95% | 94% | 73% |
| C (kongfha) | 83.2% (n=274, 8 dropped, cov≈97%) | 92% | 95% | 94% | 74% |

Ordering D ≥ B > A is consistent with the improved KhaveeVerifier. A bug in
Checker A's `stanza_ok` (always True due to `bool(na or ...)`) was found and
fixed.

### Finding: gold inter-stanza (rX) assumption is weak — **RESOLVED (data bug)**

On the *pre-fix* sample the inter-stanza rule held at only ~72% on gold, which
looked like a genuine weakness (e.g. phraAphai_1: 14/110 rX links such as
ปี -> หา). **Author diagnosis (2026-08-09):** this was a **data-completeness
bug**, not a checker error. `CleanData.write_eval` was dropping waks with ≥10
syllables, which severs the บท→บท (and chapter→chapter) rhyme chains, so rX
links were evaluated against a fragmented sequence. Fixed in commit 53c6b29
(nothing filtered; completeness is the requirement — dropping any บท breaks the
chain). Re-evaluation on the full fixed corpus now shows rX holding at ~97%
per the strongest checkers (see Session 5), confirming the fix. The
per-rule gold-validity check remains part of the pipeline; augmentation is
deferred by the author.

### Decisions from author review (2026-08-09)

- **Checker A has no r3.** Confirmed by reading 5.0.1 `check_klon`: it implements
  only r1 (สดับ→รับ), r2 (รับ→รอง) and the inter-stanza rule (rX); the
  วรรครอง→ส่ง rule (r3) is absent. Checker A therefore reports r3 as
  **not-applicable**; r3 comparisons include only B, C, D (and this is reported
  explicitly, not hidden).
- **Checker C's extra รับ-ส่ง rule is redundant** (implied when รับ-รอง and
  รอง-ส่ง hold). It is kept only in `meta`, excluded from canonical rules and
  from `stanza_ok`.
- **Dropped-stanza handling (Checker C).** Checker C can fail to emit a rhyme
  verdict (tltk G2P `<Fail>` → WordFail; <5/>10 romanised syllables → LengthFail;
  <8 waks → WakNumberFail). These are "dropped" (no prediction). Resolved: report
  **coverage** (share of stanzas evaluated) separately, compute precision/recall/
  F1 on the evaluated subset, and additionally show a conservative variant where
  a drop counts as fail. A/B/D effectively never drop.
- **Negative volume.** 1–2k negatives total would be too thin for per-rule
  precision (~250–500/rule; precision is estimated from the negative set, unlike
  recall which uses the 118k positives). Target **~2–3k negatives per rule**
  (≈8–12k total), stratified by corruption type and story (≈±1–2% precision CI);
  a workable minimum is ~1k/rule (≈4k total, ≈±2–3%).
- **Negative-review gate.** After generating the augmented negatives, the author
  will review the saved file (original, corrupted stanza, rule broken, corruption
  type, oracle verdict) **before** the harness/metrics run proceeds.

### Next steps

1. Build `eval_harness.py` (gold + negatives × all checkers).
2. Build `metrics.py` (confusion, acc/prec/recall/F1, coverage, buckets, CIs).
3. Assemble `Paper/Method_evaluation_script.ipynb` report (tables + plots),
   including the documented Checker C slowness in reproducibility/limitations.
4. **Augmentation deferred by the author** (hard pos/neg operators); revisit
   after the gold re-evaluation is final.

### Open questions for the author

- Confirm oracle = 5.3.5 `is_sumpus` for verifying constructed negatives.
- Confirm notebook structure (see Session 3 notes / author review): core logic
  stays in `.py`; report notebook drives it with verification blocks — OK, or
  add a separate interactive dev notebook?
