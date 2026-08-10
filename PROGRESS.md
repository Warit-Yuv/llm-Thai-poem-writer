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
| Parallel A/B/D eval (`--workers`/`--dw-workers`, `parallel_eval.py`) | ✅ Done (95s -> ~33s: `--workers 10 --dw-workers 4`) |
| Augmentation (mixed neg operators + standalone positives) | 🔄 Redesigned (Session 8); author review pending |
| Augmentation review (word lists + readable TSVs) | 🔄 Written on next run; author gate |
| Evaluation harness + metrics (`eval_harness.py`, `metrics.py`) | ✅ Done |
| Report notebook (`Method_evaluation_script.ipynb`) | ⏳ Stub only |
| Final full eval incl. Checker C on augment | ⏳ After author approves augmentation |

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

## Session 6 — Paper framing, W2P failure taxonomy, parallel A/B/D (2026-08-09)

### Authorship & paper narrative

The author wrote **both B and D** (they are the paper's contribution), so the
paper should be framed as: B = the general-purpose KhaveeVerifier shipped in
pythainlp 5.3.5 (pure ssg, no dictionary — "good enough for most text");
D = the dictionary-enhanced Klonpad variant = B's rules + a gold-standard G2P
override dictionary (built on phraAphai) + a fallback segmenter. A (5.0.1) and
C (Kongfha) are the external baselines. The ablation (Session 5) supports this
story: overrides help in-domain (phraAphai coverage 92.8% -> D beats B +2.6pp),
the w2p fallback hurts everywhere, and the best Klonpad config is D_ssg
(88.4% vs B 87.5%).

### W2P failure taxonomy (for the paper's limitations / future-work sections)

The w2p `pronunciate` fallback fails in four documented modes:

1. **Greedy newmm -> w2p hallucinates** on over-long compound tokens:
   `ทศพิธราชธรรม์` tokenized as one word -> 9-syllable garbage
   (`ทด-สะ-พิด-ทะ-ราด-ชะ-ดา-มะ-รัด`); split as `ทศพิธ ราชธรรม์` it is correct
   (`ทด-สะ-พิด / ราด-ชะ-ทำ`).
2. **Very short words (<=2-3 chars)**: `ก->กะ-โหฺมด`, `ก็->ก็อย`, `บ่->บ่อ`,
   `ธ->ทอน`.
3. **Long (>=3 syllable) compounds**: `ใจน้ำ->ไจ-น้าม`, `น้ำตา->น้าม-ตา`.
4. **Consonant/final + long/short vowel swaps**: `ได้->ด้าย`.

Future work (author-deferred, documented for the paper): expand the G2P
override dictionary to more corpora (currently phraAphai-optimised); a better
word segmenter to avoid greedy-newmm over-merging; context-sensitive
pronunciation for words with multiple valid pronunciations.

### Parallel A/B/D (`--workers`) — measured scaling

Added `Paper/eval_checkers/parallel_eval.py` (`run_checkers`): splits stanzas
into contiguous slices and evaluates them in a `multiprocessing.Pool`, returning
compact per-story aggregates. One-time per-process overhead is tiny (~0.5 s:
imports + data load + ssg model + override trie + w2p model).

Per-checker scaling over the full corpus (results identical at every count):

| checker | 1 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|
| A (dict) | 17.7s | 5.8s | – | – | 4.4s |
| B (ssg) | 34.8s | 11.0s | – | – | 7.8s |
| D_ssg | 26.3s | 9.5s | – | – | 6.3s |
| D_w2p | 32.7s | 18.9s | 20.4s | 23.9s | 24.1s |
| **all four** | **94.8s** | **40.3s** | **40.0s** | **40.9s** | **38.5s** |
| **all four, mixed (D_w2p=4, rest=10)** | – | – | – | – | **~33s** |

- B / A / D_ssg scale ~4x. **D_w2p does not scale** (best at 4 workers; worse at
  6+). Root cause: the w2p engine is a **pure-numpy GRU RNN**
  (`pythainlp/transliterate/w2p.py`); under concurrent numpy/BLAS load the
  per-call cost inflates (CPU frequency/power throttling), so extra processes
  hurt rather than help. BLAS thread capping (`OMP_NUM_THREADS=1` etc.) is set
  in the parallel path before the pool spawns — it helps a little but does not
  fully fix w2p.
- **Best setting: mixed workers** — `--workers 10 --dw-workers 4` caps D_w2p
  at its 4-worker optimum while B/A/D_ssg use 10: all-four 95s -> ~33s.
  (`--dw-workers N` sets the worker count for D_w2p only.)

### Flags / usage guide

- `Paper/eval_checkers/consolidate_results.py`
  - `--workers N` — parallel processes for the A/B/D/Dssg eval loop (default 1;
    recommended 10). B/A/D_ssg scale up to ~10x; D_w2p does not.
  - `--dw-workers N` — worker count for **D_w2p only** (defaults to `--workers`);
    D_w2p is fastest at 4, so the optimal combo is
    `--workers 10 --dw-workers 4` (~95s -> ~33s).
  - `--skip-c` — skip reading the Checker C checkpoint files (use before
    `run_c_full` has been run; C is omitted from the JSON).
  - `--out PATH` — output JSON path (default `full_gold_results.json`).
- `Paper/eval_checkers/compare_d_fallbacks.py`
  - `--workers N` — parallel processes for B/D_w2p/D_ssg (default 1). The
    single-process diagnostics (w2p `cache_info`, syllable-source stats) only
    run with `--workers 1`.
  - `--dw-workers N` — worker count for D_w2p only (defaults to `--workers`).
- `Paper/eval_checkers/run_c_full.py`
  - `--workers N` — persistent tltk subprocesses for Checker C (default 10).
  - `--chunk N` — units per checkpoint chunk (default 3000).
- `Paper/eval_checkers/parallel_eval.py` — shared helper (`run_checkers`); not
  a CLI.

## Session 7 — Metrics, eval harness, and augmentation (2026-08-09)

### New modules

- `Paper/eval_checkers/metrics.py` — confusion-metric functions: Wilson 95%
  CIs, coverage, accuracy/precision/recall/F1, and a conservative
  drop-as-fail variant. Handles mixed 0/1 gold (so negatives merge cleanly).
- `Paper/eval_checkers/eval_harness.py` — per-instance evaluation harness:
  collects verdicts for A/B/D_w2p/D_ssg (parallel) and C (gold from the
  `run_c_full` checkpoints; augment via the tltk worker pool), computes
  per-rule + per-stanza metrics, and merges the augmentation for
  precision/F1. Flags: `--workers`, `--dw-workers`, `--skip-c`,
  `--augment PATH`, `--out`.
- `Paper/augment/tricky_words.py` — curated hard-positive pairs (oracle-True)
  and trap-category syllables (karun / ฤ / clusters / true-final ล-ย); also
  `ORACLE_LIMITATIONS` (pairs that linguistically rhyme but the 5.3.5 oracle
  rejects, e.g. เพชร/เพ็ด — karun).
- `Paper/augment/corrupt.py` — hard negative/positive generator. Oracle = 5.3.5
  `is_sumpus` with canonical rule semantics; inventory = all corpus syllables +
  override syllables + traps, indexed by mattra/vowel. Each corruption is
  oracle-verified and written to a review TSV for the author gate. Flags:
  `--per-rule`, `--positives`, `--seed`, `--out-dir`.

### Augmentation generated (author review gate)

`Paper/augment/output/` — **6,000 negatives + 1,200 positives (7,200
instances)** in ~75 s:

| kind | r1 | r2 | r3 | rX | total |
|---|---|---|---|---|---|
| negatives | 1,500 | 1,500 | 1,500 | 1,500 | 6,000 |
| positives | 300 | 300 | 300 | 300 | 1,200 |

- **Every negative is `C0_same_mattra`** (same mattra as the original, different
  vowel, oracle-confirmed non-rhyme) — the candidate search returns at the
  first bucket, so no trap-category negatives were produced. Positives are
  `HP_trap` (trap syllable the oracle confirms rhymes).
- **Oracle limitation (confirmed by author):** เพชร/เพ็ด genuinely rhyme but
  the 5.3.5 `is_sumpus` rejects them (karun ร). Documented in
  `ORACLE_LIMITATIONS`; excluded from hard positives; the residual risk for
  negatives (a C0 candidate against a karun avoid-syllable) is rare and is what
  the author review gate is for.
- **`review.tsv`** (7,200 rows: original vs corrupted waks, op, candidate,
  broken rules) — the author reviews this before the augmentation is used.

### Preview: precision/recall/F1 with gold + augment (A/B/D/Dssg)

Stanza-level (n = 36,475 gold + 7,200 augment; C pending in the full run):

| checker | precision | recall | F1 |
|---|---|---|---|
| A (5.0.1) | 99.8% | 73.4% | 84.6% |
| B (5.3.5) | 99.9% | 87.5% | 93.3% |
| D_w2p | 99.5% | 87.0% | 92.8% |
| D_ssg | 99.6% | 88.2% | 93.6% |

Per-rule precision is ~99.6-100% for every checker. **Honest reading:** with
all negatives being the same easy type (C0 different-vowel), precision is
near-ceiling for everyone and does not differentiate the checkers — recall is
what separates them (73.4% vs 87-88%). If the paper wants precision to
discriminate, the negatives need harder/diverse operators (e.g. ล/ย mattra
swaps, long/short vowel swaps, karun/ฤ traps that specific checkers falsely
accept) — this is a decision for the author review. The current dataset is
valid as-is (genuine non-rhymes, oracle-verified) and will be reported with the
"oracle-defined truth" caveat.

### Status

- `metrics.py`, `eval_harness.py`: ✅ done (gold + augment pipeline works).
- Augmentation: ✅ generated (7,200 instances) — ⏳ **author review gate**
  (`Paper/augment/output/review.tsv`) before it is used in the final report.
- Report notebook (`Method_evaluation_script.ipynb`): ⏳ next.

## Session 8 — Augmentation redesign: taxonomy, mixed negatives, standalone positives, review UX (2026-08-10)

### Augmentation taxonomy (full)

**Negatives — precision probes (gold=0, oracle-confirmed non-rhyme).** Mixed
operators so precision is not saturated by one easy family:

| op | what it tests | share |
|---|---|---|
| `C6_random` | different สระ AND มาตรา (trivial baseline) | ~5% |
| `C0_same_mattra` | same มาตรา, different สระ (saturates; minor) | ~8% (last-resort fill → ~10-15%) |
| `C1_same_vowel` | same สระ, different มาตรา (saturates for A/B/D, but is where Checker C fails — it ignores the final consonant) | ~8% |
| `C3_short_long` | short↔long สระ swap, same มาตรา (เจ็ด/เชด, แข็ง/แขง) | ~22% |
| `C4_liquid_final` | ร/ล/ว finals where old pythainlp disagrees (ตัว: old (อะ,เกอว) vs new (อัว,กา); ทร: old กด vs new กน; หงส์: old returns error string) | ~15% |
| `C5_lead_head` | ห/อ นำ (leading) words (หงส์ หน อยาก อย่า อยู่) | ~9% |
| `C2_trap` | karun / ฤ / cluster traps (เพชร ฤทธิ์ สวรรค์...) | ~22% |
| `C8_oracle_blind` | known oracle misses — genuine rhymes the 5.3.5 oracle labels non-rhyme (เพชร/เพ็ด, วิศวกรรม/กำ, ฤทัย/ไท) → precision probes so precision is not 100% everywhere | ~11% |

Simple baselines (`C6`+`C0`+`C1`) ≈ 21-25%; edge cases dominate the rest.
Leftover quota (when an edge pool is exhausted) is redistributed to the OTHER
edge families first; `C0` only absorbs what is still missing.

**Positives — recall probes (gold=1, oracle-confirmed rhyme).**

- `P_tricky`: swap the source syllable of a genuine gold rhyme with a tricky
  rhyming candidate from the same (สระ, มาตรา) rhyme class. **Standalone:**
  every other rule's truth must be unchanged, so only the target rule is
  tested and inter-stanza (rX) / other rhymes are never disturbed.
- Tags: `sara_norm` (สระลดรูป/เปลี่ยนรูป), `rue` (ฤ), `karun` (การันต์ the
  oracle handles), `true_final` (-าย/-าว glides), `mattra_family` (plain),
  `both_normalize` (BOTH sides need the `is_sumpus` phonetic normalisation;
  emitted ~3:1 old_fail:old_pass so the genuine 5.0.1-vs-5.3.5 differentiators
  dominate but are not exclusive).
- Source balance: classical corpus ~50% / dictionary incl. loanwords ~50%
  (loanwords are fine — they appear in modern Thai poetry — every pair is
  oracle-verified).

**Oracle blind spots documented (precision not 100%):** `first_sara` —
`check_sara` returns only `sara[0]`, so a multi-syllable word passed whole
loses its final (rhyming) syllable's vowel (วิศวกรรม → อิ, loses กรรม);
`silent_r` — เพชร = /phet/ (silent ร from Pali/Sanskrit, NOT การันต์); the
oracle keeps the long เอ because the dead final has no ็; `rue_2syl` — ฤ read
as a single รึ (ฤทัย = รึ-ไท, the final ไท is never seen). เจ็ด/เชด, แข็ง/แขง,
ปฏิสนธิ์/สัน, พฤษภ/พิด are NOT rhymes (different สระ) and are excluded.

### Review UX (readable)

- `Paper/augment/output/candidates_review.tsv` — the candidate **word list**
  per rhyme class, with every word's สระ/มาตรา spelled out (raw,
  post-normalisation, and old pythainlp), an `old_differs` flag, phenomenon
  tags and source (classical/dict). Review the pool once instead of 7,000+
  rows.
- `Paper/augment/output/review_negatives.tsv` / `review_positives.tsv` —
  compact instances: `swap(S->C)`, `orig_wak`, `new_wak`, `S_sara`, `S_mat`,
  `C_sara`, `C_mat`, `tag`, `both_norm`, `oldA_fail`, `broken`, `loc`, `note`.

### Status

- `tricky_words.py`: dictionaries (thai_words + orst + **thai_syllables**
  whitelist; **icu dropped** as it flooded transliterated loanwords),
  `VOWEL_LENGTH_SWAP`, liquid/lead/oracle-blind pools, combination-based
  both-normalise builder, `is_clean_syllable`/`clean_syllables` filters
  (pure-Thai, single-ssg-syllable, length ≤ 6; whitelisted against the
  curated `thai_syllables` list so ssg over-merges like แลลอด and fragments
  like ทธิ์/หัตถ์น never enter). ✅
- `corrupt.py`: per-op quota passes; leftover redistributed only to true edge
  families (baselines capped); C8 restricted to the author-confirmed
  silent-ร/เอะ+กด family and only fires when the rhyme target is in that
  family (real precision probes); standalone positives; readable review +
  candidates files. ✅
- **Curated ฤ (2026-08-10):** `RUE_PRONUNCIATION` table (ตฤณ->ติน, ฤทธิ์->ริด,
  ฤกษ์->เริก, กฤษ->กิด, ฤา/ฤๅ->รือ, and multi-sound ฤดู->รึ-ดู, ฤทัย->รึ-ไท,
  พฤษภ->พรึก-สบ, ฤๅษี->รือ-สี). ฤ words are candidates **only when curated**;
  single-sound ones feed positives+negatives, multi-sound ones feed negatives
  only (oracle-gated, probing the oracle's ฤ mis-read). The `thai_syllables`
  whitelist now applies to **all** candidates (corpus + dict) so ssg
  artifacts (แลลอด, กกง, ไหม้ร), digits and single chars never enter.
  Deferred (author): 2-3 syllable-word handling (ศาสนา สาด-สะ-หนา) and a
  dedicated loanword-negative op (~1%, agent-checked later).

### Final generated profile (2026-08-10, `Paper/augment/output/`)

- Negatives 6,000 / positives 1,200 (7,200 instances), ~2-4 min per run.
- **Rule-slice fix (important):** the generator's `oracle_rules` used
  `Wak2[1:6]`/`Wak4[1:6]` while every checker uses `Wak2[:5]`/`Wak4[:5]`
  (B/D and the 5.3.5 core; A uses `[1:5]`). This caused *phantom FPs* -- a
  negative verified broken against `[1:6]` could still rhyme with Wak2's
  FIRST syllable, which the checkers check. After aligning to `[:5]`, B's
  FPs went 51 -> **0** and D's ~55 phantom FPs disappeared. (Gold recall is
  unaffected -- the harness treats gold as all-positive.)
- **C9_old_accept (the big A-vs-B trap):** systematically builds negatives
  where the 5.0.1 (sara, mattra) class of the candidate matches a target's
  (so OLD thinks they rhyme) but 5.3.5's does not. 943 candidate words
  participate (กนก/กรก/ครก lumped as (ออ,กก) by old vs กรณ์/กรอก/ค็อก split
  by new; plus ตัว, กัณ/กุณ ณ-bug, ก็/ก๊ก tone marks, etc.).
- Realized negative mix (baseline 13%): `C6_random` 180, `C0_same_mattra`
  300, `C1_same_vowel` 300, `C3_short_long` 1855, `C4_old_disagree` 720,
  `C9_old_accept` 1500, `C5_lead_head` 360, `C2_trap` 600,
  `C8_oracle_blind` 185.
- **FP-by-operator on the 6,000 negatives**: A **1,136** (C9 961, C3 102,
  C8 48, C1 15), B **0**, D_w2p 315 (C9 154, C3 65, C8 63), D_ssg 174
  (C3 55, C8 63, C9 32). Augment-only precision: **A 81.1% vs B 100% vs
  D_ssg 97.1% vs D_w2p 94.8%**.
- **Merged-with-gold preview (A/B/D/Dssg, skip C)**: A P 96.9% / R 73.1% /
  F1 83.4%; B 100.0% / 87.5% / 93.3%; D_w2p 99.5% / 87.0% / 92.8%; D_ssg
  99.8% / 88.2% / 93.6%. The C9 traps made the precision gap visible even
  in the diluted merged metric.
- **B = 0 FPs is expected**: B *is* the 5.3.5 oracle, so on oracle-verified
  negatives it always agrees (the เพชร/เจ็ด C8 cases are True Negatives for
  B -- its blind spot is recall-side, documented in ORACLE_LIMITATIONS;
  A/D take the C8 precision hits for hearing the real rhyme).
- Positives: 914/1200 classical, 19 both-normalise, 217 where 5.0.1 rejects
  (A-vs-B recall differentiators).
- Review files: `candidates_review.tsv` (6,070 word-list rows with สระ/มาตรา
  spelled out), `review_negatives.tsv` (6,000), `review_positives.tsv`
  (1,200). ⏳ **author review gate** before use in the final report.

### v5 — oracle-blind flips to positives, volume 2,500/rule (2026-08-10)

**Design change (author request):** the B "oracle that is wrong" must *lose
points*. The old `C8_oracle_blind` negatives (gold=0, เพชร/เนตร/เกษตร vs
สระ เอะ + แม่กด) made A/D take precision hits while B — the 5.3.5 oracle —
kept a free 100% because it labelled them non-rhymes. Since the gold label is
the LINGUISTIC truth (เพชร~เจ็ด IS a rhyme, silent ร), those cases are now
emitted as **`HP_oracle_blind` POSITIVES (gold=1)** with tag `oracle_blind`:
- the oracle must NOT see the rhyme (`o[rid] is False`),
- every other rule's truth is unchanged (standalone),
- B therefore takes **false negatives** here for missing them, while checkers
  that hear the real rhyme get the credit.
- New `--ob-positives` arg (default 60/rule; limited by the curated
  silent-ร/เอะ+กด family and (เอะ,กด) target availability in the corpus).
- C8 removed from `_pool_for`/NEG_MIX; docstring updated.

**Regenerated profile (11,265 instances, 207s):**
- Negatives 10,000 (2,500/rule): `C6_random` 300, `C0_same_mattra` 500,
  `C1_same_vowel` 500, `C3_short_long` 3,100, `C4_old_disagree` 1,200,
  `C9_old_accept` 2,800, `C5_lead_head` 600, `C2_trap` 1,000.
- Tricky positives 1,200 (300/rule, unchanged): 920 classical, 18
  both-normalise, 209 where 5.0.1 rejects.
- **Oracle-blind positives 65** (r1×60, r3×5; r2/rX have no (เอะ,กด) targets
  in the corpus).
- **FP-by-operator on 10,000 negatives**: A **1,962** (C9 1,760, C3 167,
  C1 19, C4 8, C6 3, C0 2, C2 3), B **0**, D_w2p 461 (C9 264, C3 129,
  C1 23, C4 20, C6 12, C0 11, C2 2), D_ssg 217 (C3 118, C9 51, C4 15,
  C6 12, C0 9, C1 9, C2 3). Augment-only precision: **A 80.4% vs B 100% vs
  D_ssg 97.8% vs D_w2p 95.4%**.
- **FN-by-operator on 1,265 positives**: A **566** (507 tricky = 57.8%
  recall, 59 oracle-blind = 9.2%), B **65** (0 tricky, **65/65 oracle-blind
  = 0%** — the requested deduction), D_w2p 108 (107 tricky = 91.1%, 1
  oracle-blind), D_ssg 78 (77 tricky = 93.6%, 1 oracle-blind).
- **The paper's story, cleanly:** D (Klonpad + override dictionary) catches
  **64/65** oracle-blind rhymes (its `เพชร→เพ็ด` / `เนตร→เนด` overrides)
  where stock 5.3.5 (B) misses **all 65** — the overrides fix the base
  library's silent-ร blind spot. A, the other baseline, catches only 6/65.
- **Merged-with-gold preview (A/B/D/Dssg, skip C)**: A P 94.9% / R 73.0% /
  F1 82.5%; B 100.0% / 87.4% / 93.3%; D_w2p 99.2% / 87.0% / 92.7%; D_ssg
  99.7% / 88.2% / 93.6%. (B's 65 oracle-blind FNs are ~0.14% of 47,740 gold
  stanzas, so the merged recall drop is tiny; the deduction lives in the
  augment-only view.)
- **Checker C differentiator stays:** C3_short_long is now 3,100/10,000 —
  C (tltk collapses short/long vowels) is expected to fail most of these,
  driving C's augment precision toward ~79-80% while A/B/D sit far above.
- ⏳ **author review gate** before the full Checker C run (~40 min) and the
  final report notebook.

### v5.1 — oracle-blind volume 65 -> 423 (author: "yes add more") (2026-08-10)

**Probed & rejected (not oracle-blind):**
- บุตร/มิตร/บัตร/กอปร (the other silent-ร words in the 5.3.5 core's
  safe-strip list): the oracle already strips their ร and reads them
  correctly (`is_sumpus(บุตร,จุด)=True`) — not blind.
- **เขตร (author correction):** it is the ancient spelling of เขต (from Pali
  เขตฺต), read with LONG เอ; the oracle reads it correctly as (เอ,กด)
  (`is_sumpus(เขตร,เขต)=True`). My first draft wrongly put it in the เอะ+กด
  silent-ร family — those 5 gold=1 rows (targets เอะ+กด) were WRONG and are
  removed. Only เพชร/เนตร/เกษตร are silent-ร oracle-blind (true เอะ+กด).

**Added (verified blind on the emitted waks + partner-in-family, 0/423 rows
failed either check):**
- `ศัตรู` -> true (อู,กา) — **first_sara**: ssg keeps it ONE token, the
  oracle hears only sara[0] (ไอ+กา) and misses the true final ตรู
  (ศัตรู~ครู/ตรู/ปรู; pronounced [สัด-ตฺรู]).
- `กษัตรี`/`กษัตรีย์` -> true (อี,กา) — first_sara: final ตรี
  (กษัตรี~ตรี/ศรี; pronounced [กะ-สัด-ตฺรี]).
- `ORACLE_BLIND_REASON` records the mechanism per word (in the review note).

**Volume lever was the quota, not the pool:** (เอะ,กด) targets are abundant
at r1/r3 (569/566 occurrences) but the old cap was 60. `--ob-positives`
default 60 -> 250, and the pass now rotates through ALL candidate words per
stanza (was `cands[0]`). Result: **423 oracle-blind positives** (r1 250,
r2 87, r3 80, rX 6) — by candidate: ศัตรู 145, กษัตรีย์ 133, กษัตรี 120,
เพชร 13, เนตร 7, เกษตร 5 (0 เขตร). Total 11,623 instances.

**v5.1 eval (A/B/D/Dssg, skip C):**
- **FP-by-op on 10,000 negatives** unchanged from v5: A 1,962 (C9 1,760,
  C3 167), B 0, D_w2p 461, D_ssg 217.
- **FN-pos combined** (tricky + oracle-blind, reported as ONE number with
  breakdown): A **833** (507 tricky = 57.8% recall + 326 oracle-blind =
  22.9%), B **423** (0 tricky = 100% + **423/423 oracle-blind = 0%** — the
  full deduction), D_w2p 136 (107 tricky = 91.1% + 29 oracle-blind =
  **93.1%**), D_ssg 219 (77 tricky = 93.6% + 142 oracle-blind = 66.4%).
- **New D_w2p vs D_ssg differentiator:** w2p's pronunciation knowledge fixes
  BOTH blind spots (silent-ร via the override dictionary AND first_sara via
  w2p: ศัตรู->สัด-ตรู, กษัตรี->กะ-สัด-ตรี), so D_w2p catches 394/423 oracle-
  blind while D_ssg (plain ssg, no w2p hallucinations) catches only 281/423.
- **Merged-with-gold:** A P 94.9% / R 72.5% / F1 82.2%; B 100.0% / 86.5% /
  92.8%; D_w2p 99.2% / 86.8% / 92.6%; D_ssg 99.7% / 87.8% / 93.4%. B's 423
  oracle-blind FNs now visibly cost it recall (87.4% -> 86.5%) even in the
  merged metric — the "wrong oracle gets point deducted" effect the author
  asked for.
- **Quality audit:** 0 duplicate ids, 0 duplicate (S,C) pairs, 0 non-Thai
  source/candidate across all 11,623 instances; all 423 oracle-blind rows
  pass both the partner-in-family and oracle-blindness checks on the emitted
  waks; loanword negatives (เทอร์/สกีน/แฮงก์ ...) are clean Thai-script and
  oracle-verified (by design).
- **FN-pos reporting convention:** report combined FN-pos (tricky +
  oracle-blind) as the primary number, with the breakdown secondary — recall
  is naturally combined in the metrics since all positives are gold=1.

### v5.2–v5.6 — recheck-agent audit (author: "release the hound") (2026-08-10)

Four parallel recheck agents audited the review files (oracle-blind
positives, tricky positives, negatives, candidate pool) with independent IPA
+ spelled-out สระ/มาตรา (vowel length explicit). They caught a systemic
oracle limitation that the generator's oracle-gate could not self-detect:
**the 5.3.5 oracle misreads (a) การันต์ clusters it does not silence
(ไฟลท์->ไฟ ไอ/กา, นันทน์->นัน อะ/กน, มิตร์->มิด อิ/กด, เปิล->เปิน เออ/กน,
เชาวน์->เชา เอา/กา), (b) multi-syllable words ssg keeps as ONE token
(สังฆ->สัง-คะ, ศิลป->สิน-ละ-ปะ, สห->สะ-หะ, มโน->มะ-โน), (c) เ-อ (เออ) as เอ
(เทอม = /tʰɤːm/), and (d) โ+cluster+ง/ก as long โอ instead of short โอะ
(โครง/โปร่ง/โขลก).** Any such candidate poisons BOTH directions (the oracle
"confirms" a rhyme/non-rhyme against the wrong class).

**Fixes applied (all committed):**
- **v5.3** — dropped เนตร/เกษตร from oracle-blind (they are long-เอ เนด/
  กะ-เสด, NOT เอะ — same เขตร-class trap; confirmed by the author's own
  override dict เพชร->เพ็ด vs เนตร->เนด). 12 wrong rows gone; only เพชร
  remains silent_ร.
- **v5.4** — Agent 2: 13/67 broken tricky positives -> excluded 12
  candidates (ถรรพณ์ กรบ วล ปุร ฉล วน สถ ศิลป มม สังฆ แอ้ง กวัย); the other
  54 flagged were w2p false alarms (ซอฟต์ = ออ/กบ, มารร์ = อา/กน — oracle
  right, w2p hallucinating).
- **v5.5** — Agent 3: ~284/10,000 negatives had wrong gold=0 (real rhymes
  mislabeled non-rhyme) -> excluded ~50 การันต์/multi-syllable/junk
  candidates (ไฟลท์ ไจร ไวลด์ นันทน์ จันทน์ พันธน์ -ตร์/-ทร์/-ติ์ เปิล/เคิล/
  เกิล เลนส์ เหลน เชาวน์ เยาว กรุณ์ โสร่ง/โขมง/โขยง/โขยก พยัคฆ สห มห
  วรรคย์ ปรัห กนน ...). D_w2p's apparent FPs fell 526->285 — it was being
  penalized for correctly hearing the misread rhymes.
- **v5.6** — Agent 4 (candidate pool): 47 misassigned + 49 junk. Applied the
  45 orthographically-certain exclusions (multi-syllable Pali finals: มังส
  จัตุร จตุร วุฒิ มุติ เทว มโน สโม สโต ฉันท วัชร สมรรถ สิงห สมุห เสว; karan/
  glide: เชาว พอยน์ท สเปรย์ สแปร์ สแควร์ ไทร ไดรด์ ไดรฟ์; short-โอะ rule:
  โขลก โผลก โฉลก โครง โคร่ง โปร่ง โขลง; เออ-vs-เอ: เทอม เดอร์ม เดอร์น เทอด
  เปอร์ส เตอร์ส เตอร์ด เจอร์ค เบอร์ก เวอร์ค เออร์ค เธร์ เธ่ย์ เอร์; เหม่).
  The 49-word "junk" list was NOT blanket-applied — several are valid
  syllables of compounds (รวจ/นวณ/ฌงค์) the agents disagreed on; ⏳ author
  adjudication.
- **v5.6 eval (A/B/D/Dssg, skip C):** A P 95.1% / R 72.6% / F1 82.3% (1,949
  FPs: C9 1,761 + C3 157); B 100% / 86.5% / 92.8% (0 FPs, 0% oracle-blind);
  D_w2p 99.6% / 86.8% / 92.8% (285 FPs, 95.5% oracle-blind recall);
  D_ssg 99.7% / 87.8% / 93.4% (224 FPs, 66.2% oracle-blind recall). Combined
  FN-pos: A ~835, B 423, D_w2p ~125, D_ssg ~209.
- **Review files enriched for the gate:** `S_pron`/`C_pron` with `_src`
  (override = curated, authoritative; w2p = ML hint that CAN hallucinate —
  labeled, never trusted), plus a `partner` column (the rhyme-target
  syllables with their oracle (สระ/มาตรา)) so reviewers can verify in-file;
  `Paper/augment/output/README.md` documents the column semantics + w2p
  caution.
- **Residual risk (documented):** the misread detector is w2p-driven and
  ~80% noise; the full-set stratified sample (0/80) was clean, so remaining
  wrong-gold is estimated <1%; the ~49 contested junk entries and the
  เอ-อ/เอ + โ-cluster rules are flagged for the author's final sign-off
  before the full Checker C run.

## Session 9 — Final evaluation (incl. Checker C on the augmentation) + report notebook (2026-08-10)

### Runs
- `eval_harness.py --workers 10 --dw-workers 4 --augment ...` — **full run with Checker C**:
  C gold read from the Session-5 checkpoints; C scored on all 11,623 augment instances via
  the tltk worker pool (**41 min**). Output: `Paper/eval_checkers/full_metrics.json`.
- `paper_report_data.py` — augment-only + op-level tables for all five checkers (another
  ~40-min C pass), dumping **per-instance verdicts** to
  `Paper/report/augment_verdicts.json` so C never needs re-scoring; tables in
  `Paper/report/paper_tables.json`. Has `--from-verdicts` (recompute tables without
  re-running checkers) and applies the **Checker-A r3 N/A fix** at the stanza level.
- **Metric-design note:** each augment instance is standalone and tests exactly ONE rule,
  so the clean metric is **per-rule** (a stanza-level aggregate over the augmentation is
  only well-defined for B = the oracle; for A/C/D a swap that breaks their target rule can
  also disturb a different rule they read with other slicing/syllabification, contaminating
  stanza_ok). A has no r3 everywhere (N/A).

### Gold recall (stanza level, 36,475 stanzas; A has no r3)

| checker | stanza | r1 | r2 | r3 | rX |
|---|---|---|---|---|---|
| A · 5.0.1 | 73.4% | 86.3% | 88.8% | – | 88.7% |
| B · 5.3.5 | 87.5% | 94.7% | 96.5% | 95.5% | 96.7% |
| D_w2p | 87.4% | 95.4% | 96.3% | 94.9% | 96.5% |
| **D_ssg** | **88.5%** | 95.9% | 96.7% | 95.2% | 97.0% |
| C · Kongfha | 84.8% (cov 95.7%) | 93.2% | 96.5% | 94.1% | 96.6% |

### Augmentation-only OVERALL (pooled per-rule, n=11,623 = 10,000 neg + 1,623 pos)

| checker | precision | recall | F1 |
|---|---|---|---|
| A · 5.0.1 | 29.3% | 64.6% | 40.3% |
| B · 5.3.5 | **100.0%** | 73.9% | 85.0% |
| D_w2p | 84.4% | **92.3%** | **88.2%** |
| D_ssg | 87.1% | 86.4% | 86.7% |
| C · Kongfha | 30.6% | 88.3% | 45.4% |

### Error analysis (FP by operator on the 10,000 negatives; FN on positives)

| checker | total FP | C3 short↔long | C9 old-accept | FN-pos combined | =tricky | =oracle-blind |
|---|---|---|---|---|---|---|
| A | 1,928 | 159 | **1,757** | 824 | 492 | 332 |
| B | **0** | 0 | 0 | 423 | 0 | **423** |
| D_w2p | 276 | 125 | 104 | 125 | 107 | 18 |
| D_ssg | 208 | 110 | 51 | 221 | 81 | 140 |
| C | **3,129** | **2,714** | 286 | 244 | 154 | 90 |

### Findings (for the paper)
1. **B is the oracle**: 0 FP on oracle-verified negatives (100% precision by construction),
   but **0% oracle-blind recall** — it misses all 423 genuine rhymes (silent-ร เพชร,
   first-sara ศัตรู/กษัตรี/กษัตรีย์) its own is_sumpus cannot see. Gold there = linguistic
   truth, so B loses the points (the requested "wrong oracle gets deducted" effect).
2. **D recovers the blind spots**: D_w2p 95.7% oracle-blind (override dict + w2p read
   เพชร→เพ็ด, ศัตรู→สัด-ตรู, กษัตรี→กะ-สัด-ตรี) vs D_ssg 66.9% — the w2p-knowledge
   contribution, mechanistically isolated.
3. **C is the precision contrast**: strong recall (88.3% augment, 78.7% oracle-blind —
   tltk G2P hears the real rhymes) but **3,129 FPs, of which 2,714 (87.5% of the C3
   family) are short↔long สระ swaps** its `replace_long_short` collapses → augment-only
   precision 30.6%. C trades precision for recall exactly on the length distinction B/D
   enforce.
4. **A (5.0.1) trails everywhere**: gold recall 73.4%, augment P 29.3% (C9 drives 1,757
   FPs — words old reads with the same (สระ,มาตรา) the modern core splits), tricky recall
   ~59%.
5. **Best configuration: D_ssg** (merged F1 ≈ D_w2p, gold recall 88.5%, augment F1 86.7%,
   no w2p hallucinations). Paper narrative: B's improved rules + D's gold-standard G2P
   overrides lift recall from A's 73% to ~88% at ~100% precision on curated negatives.

### Report notebook (`Paper/Method_evaluation_script.ipynb`, 20 cells, executed ✅)
- Reads `full_metrics.json` + `report/paper_tables.json` at runtime (pure reader of the
  committed results); 6 tables (gold recall, augment-only per-rule P/R/F1, merged per-rule
  P/R/F1, gold by story, oracle-blind + combined FN-pos, FP/FN by operator) + 3 figures
  (augment P/R/F1, FP by operator, oracle-blind recall).
- Per-rule is the primary metric; the merged-precision gold-domination caveat and the
  stanza-level-augment caveat (B-only) are stated in the notebook.
- **New dependency:** `matplotlib` (for figures) — added to the venv.

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
