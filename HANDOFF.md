# HANDOFF — Eval gap patch + Checker C recovery + metric refresh

**Date:** 2026-10-09 (evening) · **From:** the gap-patch / metric-refresh session
**Workspace:** `e:\User\Noto\SIIT\SIIT_Year_4\LLM_WritePoem`
**venv:** `.venv` (Python 3.14.3, pythainlp 5.3.5) · **tltk venv:** `.venv312` (Python 3.12)

---

## 0) Author's standing rules — read first, follow always

1. **`Dataset/PhraAphai/phraAphai_22.txt` is FINAL.** Never edit / re-verify it. The
   incomplete บท is an accepted, documented gap. Do not fabricate the missing couplet.
2. **Ask the author before re-running any evaluation or metric job.** (Already granted for
   this workstream — see §3.)
3. Batch questions, be decisive, answer in English. Do not guess.
4. **Do NOT kill long-running jobs early.** The tltk workers look idle (low CPU) while
   loading models / between units; killing them wastes the whole run. Let them finish.

---

## 1) What this session did (all committed & pushed to `origin/main`)

| commit | what |
|---|---|
| `b1289e1` | Eval gap patch: `Dataset/transcription_gaps.json` + `CleanData.write_eval` + `count_raw_dataset.py` + test |
| `1af7668` | Seam fix: rows after a gap are fresh stanzas (rX N/A) via `Results/Evaluate/gap_seams.json` + `Paper/data_loading.py` |
| `5dbf02a` | Checker C: streaming `.partial` checkpoints + progress bar; `recover_c_chunks.py`; `benchmark_speed.py` |
| `0657887` | Trim Table 3 footnote; PROGRESS.md Session 11b |
| `30437dc` | `recover_c_chunks.py`: one-shot worker (persistent pool stalls) |

### The gap patch (Step 2 — DONE)
- `Dataset/transcription_gaps.json` = `{"phraAphai_22": [[517,518]], "phraAphai_31": [[177,178],[891,892]]}`
  (1-based วรรค ranges to EXCLUDE from tiling; `_`-prefixed keys are comments).
- `CleanData.write_eval` drops those วรรค before grouping, asserts the remainder tiles by 4,
  and records the **seam rows** (the eval rows that follow each gap) in
  `Results/Evaluate/gap_seams.json`.
- `Paper/data_loading.load_stanzas` reads the seam file and sets `prev_w4 = None` there, so
  **rX is N/A at the seams** (not a false miss). This was the author's explicit requirement.
- Regenerated: **_22 = 225 rows**, **_31 = 289 rows** (was 290). Grand total **36,474**.
- `count_raw_dataset.py` cross-check reports both files `ok`.

### rX verification (5.3.5 oracle)
- The 3 artificial seam misses (`เดียร~ยับ`, `ใจ~สอง`, `นอน~ไข้`) are **gone** (rX N/A).
- The patch also **eliminated the ~95-row rX cascade** the shifted tiling had caused.
- Remaining rX misses are pre-existing text quirks: _22 `ดิน~ศีล`, `บุตรี~ษี`, `ตรี~รัศมี`;
  _31 `ไฟ~พิสมัย` (×2), `การ~ณฑ์`.

### Corpus counts (paper-facing)
stanzas 36,475 → **36,474**; waks 145,900 → **145,896**; gold rhyme checks 145,709 →
**145,705**. Paper updated: abstract, contributions, dataset paragraph, Table 3 caption,
`abstract.md`, `StoryLayout.tex`.

---

## 2) Checker C — the environment problem (IMPORTANT)

**tltk has no Python 3.14 wheel**, so the project `.venv` (3.14.3) cannot run Checker C.
The global Python 3.12 (`KONGFHA_PYTHON` default) had a **broken numpy 2.5.2 / scipy 1.12.0**
pair (`numpy.dtype size changed`), so `import tltk` failed.

**Fix:** a dedicated **`.venv312`** (Python 3.12) with `tltk` + `pandas` + `requests` +
upgraded `scikit-learn`/`scipy` (numpy 2.5.3 / scipy 1.18.1 / sklearn 1.9.1). Point
`KONGFHA_PYTHON` at it:

```powershell
$env:KONGFHA_PYTHON = (Resolve-Path ".venv312\Scripts\python.exe").Path
```

**The persistent-pool stall:** `run_c_full.py`'s original `_PersistentWorker` (long-lived
subprocess + reader thread) **intermittently stalls idle** in this environment — workers
start but never process (CPU ~0, memory ~4 MB, i.e. tltk never loads). This wasted several
runs. `score_units_parallel` was rewritten to use **one-shot subprocesses with temp-file
I/O** (no pipes) in `sub_batch`-sized rounds. **If a run still stalls, do NOT kill it
immediately — wait; the machine may just be loading models.**

---

## 3) Checker C gold chunks — RECOVERED (DONE)

The gap patch changed only `_22`/`_31`; **35,771 of 36,283 units are byte-identical** to the
pre-patch run. `Paper/eval_checkers/recover_c_chunks.py` reuses the cached result for every
unchanged unit and re-scores only the **275** changed units (one-shot worker, ~2 min), then
rewrites all 13 chunks in the new order.

**Status: DONE.** `Paper/eval_checkers/_c_chunks/` holds 13 chunks, 36,283 lines total.
Backups of the pre-patch CSVs, gold JSON, and C chunks are in `backups/eval_pre_gap_patch/`.

---

## 4) Remaining work — the metric refresh (Step 3)

**A/B/D gold: DONE** (`consolidate_results.py --skip-c`): B 88.1%, D_w2p 88.1%, D_ssg 89.2%,
A 74.0%. Cross-chapter rX: phraAphai 130/131.

**In progress / to run (in order):**

1. **`eval_harness.py`** (RUNNING as of this handoff — let it finish):
   ```powershell
   $env:KONGFHA_PYTHON = (Resolve-Path ".venv312\Scripts\python.exe").Path
   .venv\Scripts\python.exe Paper/eval_checkers/eval_harness.py --workers 10 --dw-workers 4 `
       --augment Paper/augment/output/instances.json --out Paper/eval_checkers/full_metrics.json
   ```
   This re-scores C on the **11,623 augmentation instances** (the slow part, ~10–15 min).
   Output → `tmp_harness.txt`. **Do not kill it.**
2. `python Paper/eval_checkers/paper_report_data.py --from-verdicts`
3. `python Paper/eval_checkers/refresh_metrics.py`
4. Re-run `Paper/Method_evaluation_script.ipynb` (reads the JSONs; tables/figures refresh).
5. Update paper numbers if they shift (`Paper/Latex_Paper/iSAI-Klon-Checker.tex`).
   Expected: augment-only tables unchanged; gold-side recall ticks up slightly; the gold rX
   denominator drops by 3 (the 3 seam links are now N/A).
6. Re-run the cross-chapter boundary rX check (report-only).

**Still valid (do NOT regenerate):** `Paper/report/augment_verdicts.json` (C's augment
verdicts are standalone), `Paper/augment/`, `poetry_overrides*.py`, the G2P dictionary.

---

## 5) Speed benchmark (author request — NOT yet run)

`Paper/eval_checkers/benchmark_speed.py` measures A/B/D/Dssg over the full corpus at
workers 1..10, and Checker C on a fixed sample, writing `benchmark_speed.json`.

```powershell
$env:KONGFHA_PYTHON = (Resolve-Path ".venv312\Scripts\python.exe").Path
.venv\Scripts\python.exe Paper/eval_checkers/benchmark_speed.py            # all
.venv\Scripts\python.exe Paper/eval_checkers/benchmark_speed.py --only abd # A/B/D only
.venv\Scripts\python.exe Paper/eval_checkers/benchmark_speed.py --only c --c-sample 500
```
Run this **after** the harness (to avoid resource contention). The author wants a
consistent, reproducible speed-up/slow-down table per model.

---

## 6) Checker C tooling improvements (DONE)

- `run_c_full.py`: results stream to `chunk_<k>.jsonl.partial` as they arrive (flushed per
  unit) and are atomically renamed to `chunk_<k>.jsonl` only when the chunk completes — a
  crash mid-chunk keeps every unit already scored. A live progress bar shows units/s,
  elapsed, and ETA.
- `score_units_parallel`: one-shot subprocesses + temp-file I/O (see §2).

---

## 7) Environment & gotchas

- Python: `.venv\Scripts\python.exe` (3.14.3). Checker C: `.venv312\Scripts\python.exe`
  (3.12) via `KONGFHA_PYTHON`.
- Printing Thai on Windows: `sys.stdout.reconfigure(encoding="utf-8")` first; piping through
  `Select-Object` mangles UTF-8 — write to a file and read it.
- LaTeX: `latexmk -xelatex iSAI-Klon-Checker.tex` from `Paper/Latex_Paper/`. The exit code
  is sometimes 1 even when the PDF is written (a locked-PDF / xdvipdfmx quirk) — check the
  PDF timestamp, not the exit code. Two copies of the `.tex` exist (workspace + `E:\Download`);
  the workspace one is what compiles.
- `KhaveeVerifier.is_sumpus(wak1, wak2)` on WHOLE วรรค is invalid (`check_sara` reads only
  the first syllable). Compare LAST syllables (ssg) or use `check_klon`.
- Tools: `count_raw_dataset.py` (`--file`, `--dump STEM LO HI`), `check_boundaries.py`.

---

## 8) Key Thai anchors

- **_22 gap:** after `ดูเรืองรุ่งราวกับลายระบายเขียน` (w518) / before `กุฏิ์น้อยน้อยร้อยเศษสังเกตนับ` (w521).
- **_31 gap 1:** after `ไม่กลับกลายแกล้งลวงแม่ดวงใจ` (w176) / before `จะสัญญาว่าขานประการใด` (w177).
- **_31 gap 2:** after `ต่อพระองค์โปรดแปลจึงแน่นอน` (w890) / before `จึงถามว่าอาจารย์ท่านเข้านอน` (w891).
