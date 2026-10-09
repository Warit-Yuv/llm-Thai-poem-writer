# HANDOFF — Dataset gap decision → optional eval patch → metric refresh

**Date:** 2026-10-09 · **From:** the raw-dataset audit session · **For:** the next agent session
**Workspace:** `e:\User\Noto\SIIT\SIIT_Year_4\LLM_WritePoem` · venv `.venv` (Python 3.14.3, pythainlp 5.3.5)

---

## 0) Author's standing rules — read first, follow always

1. **`Dataset/PhraAphai/phraAphai_22.txt` is FINAL.** The author verified it against the
   printed source on the web (2026-10-09). Do **not** edit it, do **not** re-verify it, and
   do **not** insert the "missing" couplet
   `บ้างเขียวขาววาวแววแก้ววิเชียร / ตะโล่งเลี่ยนเลื่องเหลืองเรืองระยับ`:
   restoring it would fabricate text that is not in the data and misrepresent the source
   (author's words). The incomplete บท in that file is an accepted, documented gap.
2. **Ask the author before re-running any evaluation or metric job.** ("It's okay to rerun
   the experiment but before doing that ask me again first.") The full sequence + runtimes
   are in Step 3 so the ask can be ONE message.
3. Batch questions, be decisive, answer in English. If has questions, ask the author; if has answers, answer the author. Do not guess.
4. Note: a script `verify_phra22_fix.py` ran during the author's check (exit 0) and was
   deleted afterwards; no data file changed as a result (git-clean). If you ever need to
   know what it verified — ask the author, don't guess.

---

## 1) Context in 30 seconds

The repo evaluates four Klon-8 rhyme checkers (A = pythainlp 5.0.1, B = 5.3.5
KhaveeVerifier, C = Kongfha/tltk, D = Klonpad overrides) over a gold corpus built from
`Dataset/<work>/<stem>.txt` by `CleanData.py --eval` into
`Results/Evaluate/<work>/<stem>_ok.csv` (one 4-วรรค บท per row, columns w1..w4).
Paper numbers (iSAI, v5.7) come from `Paper/eval_checkers/full_metrics.json` +
`Paper/report/paper_tables.json`, rendered by `Paper/Method_evaluation_script.ipynb`.

This workstream audited the RAW `Dataset/` files — counted บท/วรรค with the project's own
rules and cross-checked every file against its eval CSV. Results are logged in
`PROGRESS.md` → **Session 11** (read it; it is the factual record).

---

## 2) Verified facts

### Raw counts (`python count_raw_dataset.py`)

| | files | วรรค | บท (act rule) | eval rows |
|---|---:|---:|---:|---:|
| Khobut | 14 | 5,215 | 1,304 | 1,303 |
| KhunChangKhunPhaen | 43 | 42,172 | 10,543 | 10,543 |
| PhraAphai | 132 | 97,373 | 24,321¹ | 24,342 |
| PhukaoTong | 1 | 351 | 88 | 87 |
| SuphasaetSonYing | 1 | 803 | 201 | 200 |
| **total** | **191** | **145,914** | **36,457** | **36,475** |

¹ excludes the 90 วรรค of the 5 checksum-failing acts (32 of those belong to 8 complete บท
in phraAphai_80). True complete บท = **36,478** (incl. the 4 three-wak openers) + **3
incomplete บท** (6 of their 12 วรรค present). No mid-chapter 3-วรรค stanza exists anywhere
(7,234 ๏ acts checksummed); the only 3-วรรค openers are the 4 works' first files — KCKP has
none, matching the author's note.

### The five checksum failures

| file | act (วรรค) | n | diagnosis | status |
|---|---|---|---|---|
| phraAphai_22 | 27 (501–530) | 30 | repeated couplet present once; region rhymes only if twice | **KEEP AS-IS (author, final)** |
| phraAphai_31 | 8 (173–182) | 10 | บท [X,Y,177,178] missing its first half | propose same as _22 |
| phraAphai_31 | 43 (875–892) | 18 | บท [X2,Y2,891,892] missing its first half | propose same as _22 |
| phraAphai_80 | 25–26 (365–396) | 10+22 | **nothing missing** — ฯ@374 + ๏@375 sit mid-บท [373–376] | none (cosmetic) |

Checker evidence (`python check_boundaries.py`, 5.3.5 oracle): the author-grouped stanzas
score *"The poem is correct according to the principle"*; the eval's sequential rows inside
the gap windows fail r2/rX (e.g. _22 [521–524]: `พร้อม~กุฏิ์` r2 ✗, and the author-confirmed
`ยับ~พร้อม` rX ✗).

### Author-approved grouping (the reference for any eval patch)

- **_22:** `[501-504][505-508][509-512][513-516] | [517,518 + 2 missing] (incomplete) |
  [519-522][523-526][527-530] | [531-534]…` (act 28 onward re-aligns).
- **_31:** `[173-176] | [177,178 + 2 missing] | [179-182]…[887-890] |
  [891,892 + 2 missing] | [893-896]…[1157-1160]`.
- **_80:** eval's sequential rows are already correct; only the ฯ/ฯ decoration placement is
  off. Optional cosmetic fix (author approval): move the ฯ from w374 to w376 → acts 25/26
  become 12+20 and pass the checksum. Text unchanged either way.

Corroboration: `README.md` says PhraAphai = **97,379** วรรค; the files hold 97,373 = 6
fewer (the 3 lost couplets) — the README number predates the loss.

---

## 3) The decision already made (do not relitigate)

phraAphai_22 keeps its text as-is. Both candidate groupings leave something broken
(`[517-520]` is a valid บท but forces `[521-524]` to break; the author grouping
`[519-530]` gives three perfect บท but orphans [517,518]) — because 2 วรรค are genuinely
absent from the source. Inserting the repeated couplet was **rejected by the author**
(fabrication). The only open question is how the **eval** should represent the affected
windows.

---

## 4) Remaining work — ordered plan

### Step 1 — ONE batched author ask (do this before anything else)

Copy-paste (adjust after re-reading):

> Two confirmations before I touch anything:
> 1. **phraAphai_31** has the same two gaps as phraAphai_22 (between
>    `…ไม่กลับกลายแกล้งลวงแม่ดวงใจ` [w176] and `จะสัญญาว่าขานประการใด` [w177]
> >>> Author here: "yes, I see there is a gap of 2 waks -> ๏ พระฟังนางช่างฉลาดประภาษพ้อ	ทั้งลวงล่อสิ้นลมคมใจหาย
จึงว่าพี่นี้ซื่อเป็นชื่อชาย	ไม่กลับกลายแกล้งลวงแม่ดวงใจ
*จะสัญญาว่าขานประการใด	พี่จะให้ความสัตย์ไม่ขัดน้อง*, and the text is correct as-is"
> 
> ; and between
>    `…ต่อพระองค์โปรดแปลจึงแน่นอน` [w890] and `จึงถามว่าอาจารย์ท่านเข้านอน` [w891]).
>    Same treatment as _22 — keep the text as-is, do not fabricate the couplets?
>    (If your web check says the source HAS them and you want them inserted, say so and
>    I will follow your text instead.)
> >>> Author here: "yes, the text is correct as-is, do not fabricate the couplets"
> *จึงถามว่าอาจารย์ท่านเข้านอน	หรือว่าจะจรจากกุฎีไปที่ใด ฯ* is actually missing the first half of the couplet, so the gap is real.
> >>> Author Comment: "Make sure the matrix is correctly evaluated and the precision/recall when the gaps are present is correctly reported. It might be a mistake in the library archive or the source text, but the gaps are real and should be reported as such. You may split the file/drop the rows in the evaluation to reflect the gaps, but do not fabricate the missing couplets. Ensure the rhyme rules are correctly applied to the remaining rows. So, keep the original text as-is, and patch the evaluation row/split file/or drop but make sure number is correctly reported."
> 2. May I patch the **eval rows** around the 3 gap sites — exclude the 6 present-half
>    วรรค ([517,518] / [177,178] / [891,892]), re-tile the rest (eval 36,475 → 36,474
>    rows) — and then re-run the metric sequence? Runtimes: A/B/D ≈ 35 s; Checker C
>    targeted re-score ≈ 3 min (or full C ≈ 49 min); harness + tables + notebook ≈ 10 min.

If the author says "no patch" → skip Steps 2–3, do Step 4 only.
> >>> Author here: "Yes, you may patch the eval rows around the 3 gap sites. If you want to exclude the 6 present-half waks ([517,518] / [177,178] / [891,892]), make sure neigbor rows are not affected. Also makesure rX is correct and not shift, so the gold is preserved.  and then re-run the metric sequence. Make sure to document this change in the PROGRESS.md and update any relevant metrics or tables accordingly."

### Step 2 — implement the eval gap patch (only if approved)

1. Create `Dataset/transcription_gaps.json`:
   ```json
   {"phraAphai_22": [[517, 518]], "phraAphai_31": [[177, 178], [891, 892]]}
   ```
   (1-based วรรค ranges to EXCLUDE from stanza tiling — the present halves of the
   incomplete บท.)
2. `CleanData.write_eval`: read that JSON (keyed by stem), skip excluded waks while
   tiling, assert the remainder tiles exactly by 4, and report `gap_skipped` in the
   returned stats. Run `python test_cleandata.py` after editing (project self-checks).
3. `count_raw_dataset.py`: consume the same JSON in its eval-row prediction, otherwise it
   will report the patched files as MISMATCH.
4. Regenerate: `python CleanData.py Dataset/PhraAphai/phraAphai_22.txt --eval` and
   `python CleanData.py Dataset/PhraAphai/phraAphai_31.txt --eval`.
5. **Expected:** _22 = 225 rows with rows-from-130 re-tiled to
   `[519-522][523-526][527-530][531-534]…[899-902]` (no tail drop); _31 = 289 rows
   (`[179-182]…[887-890]`, `[893-896]…[1157-1160]`); grand total 36,474.
6. Do **not** hand-edit the CSVs without the mechanism — a bare `--eval` rerun would
   silently revert a hand patch.

### Step 3 — metric refresh (only if Step 2 happened; author-approved in Step 1)

Stale after a patch: `Paper/eval_checkers/full_gold_results.json` (A/B/D gold),
`Paper/eval_checkers/_c_chunks/chunk_*.jsonl` (C gold), `full_metrics.json`,
`Paper/report/paper_tables.json`. **Still valid:** `Paper/report/augment_verdicts.json`
(C's augment verdicts — the augmentation is standalone and independent of these eval rows;
do NOT regenerate `Paper/augment/`), `poetry_overrides*.py`, the G2P dictionary.

1. `python Paper/eval_checkers/consolidate_results.py --workers 10 --dw-workers 4 --skip-c --out Paper/eval_checkers/full_gold_results.json` (~35 s).
2. Checker C gold: ~275 changed rows. Preferred: targeted re-score of just those eval rows
   through `Paper/eval_checkers/kongfha_worker.py` (GLOBAL Python 3.12, `KONGFHA_PYTHON`;
   8-wak units = 2 consecutive eval rows joined with `\n`; ~3 min), writing the same JSONL
   format into the chunk files (back up `Paper/eval_checkers/_c_chunks/` first).
   Fallback: full `python Paper/eval_checkers/run_c_full.py --workers 10` (~49 min).
3. `python Paper/eval_checkers/eval_harness.py --workers 10 --dw-workers 4 --augment Paper/augment/output/instances.json --out Paper/eval_checkers/full_metrics.json`
   (C augment verdicts are reused from the cached verdicts — do not re-score them).
4. `python Paper/eval_checkers/paper_report_data.py --from-verdicts` then
   `python Paper/eval_checkers/refresh_metrics.py` (rebuild tables/merged totals).
5. Re-run `Paper/Method_evaluation_script.ipynb` (reads the JSONs; all tables/figures refresh).
6. Re-run the cross-chapter boundary rX check (report-only; _22's last row changed).
7. Update paper numbers if they shift (`Paper/Latex_Paper/iSAI-Klon-Checker.tex`; the
   workspace copy is what compiles — beware the second copy in `E:\Download`, see
   `/memories/repo/build.md`). Expected shape of the change: **augment-only tables
   unchanged**; gold-side numbers tick up slightly (~+0.2–0.5 pp recall — ~275
   systematically-broken gold rows become valid); **3 new gold rX misses appear at the gap
   seams** (`เดียร~ยับ`, `ใจ~สอง`, `นอน~ไข้` — 3 of 36,284 rX links; mention them in the
   paper's dataset paragraph as gap properties, don't hide them).

### Step 4 — documentation (always, even with no patch)

- `PROGRESS.md`: Session 11 is already written — extend it with the outcomes of Steps 1–3.
- Paper dataset section: one sentence documenting the 3 source-verified incomplete บท
  (and, if unpatched, that ~275 eval rows sit on shifted boundaries by construction).
- Optional (author call): README's "97,379 วรรค" → 97,373 with a footnote.

---

## 5) What NOT to do

- Do not edit / re-verify / "fix" `Dataset/PhraAphai/phraAphai_22.txt`.
- Do not regenerate the augmentation (`Paper/augment/`) or the override dictionaries —
  unaffected by this workstream.
- Do not "fix" phraAphai_80's text — nothing is missing there.
- Do not delete `count_raw_dataset.py` / `check_boundaries.py` — they are the audit tools
  the author may want again.
- Do not run any evaluation/metric job without the author's go-ahead (Rule 0.2).

---

## 6) Environment & gotchas

- Python: `.venv\Scripts\python.exe` (terminal is usually pre-activated). Checker C / tltk
  run under the GLOBAL Python 3.12 (`KONGFHA_PYTHON` env var).
- Printing Thai on Windows: `sys.stdout.reconfigure(encoding="utf-8")` first; piping output
  through `Select-Object` mangles UTF-8 — write to a file and read it instead.
- `KhaveeVerifier.is_sumpus(wak1, wak2)` on WHOLE วรรค is invalid (`check_sara` reads only
  the first syllable). Compare LAST syllables (ssg) or use `check_klon`, which takes
  whitespace-separated waks and groups them 4-per-บท.
- LaTeX: two copies of `iSAI-Klon-Checker.tex` exist (workspace + `E:\Download`); the
  workspace one is what `latexmk` compiles.
- Tools: `count_raw_dataset.py` (`--file`, `--dump STEM LO HI`), `check_boundaries.py`.

---

## 7) Key Thai anchors (for the author ask and any future source check)

- **_22 gap:** after `ดูเรืองรุ่งราวกับลายระบายเขียน` (w518) / before `กุฏิ์น้อยน้อยร้อยเศษสังเกตนับ` (w521) —
  the incomplete บท = [517,518 + 2]; the repeated couplet would be
  `บ้างเขียวขาววาวแววแก้ววิเชียร / ตะโล่งเลี่ยนเลื่องเหลืองเรืองระยับ`
  (its exact slot in the printed source — before w519 or after w520 — is the author's
  knowledge; irrelevant while the decision is keep-as-is).
- **_31 gap 1:** after `ไม่กลับกลายแกล้งลวงแม่ดวงใจ` (w176) / before `จะสัญญาว่าขานประการใด` (w177).
- **_31 gap 2:** after `ต่อพระองค์โปรดแปลจึงแน่นอน` (w890) / before `จึงถามว่าอาจารย์ท่านเข้านอน` (w891).
