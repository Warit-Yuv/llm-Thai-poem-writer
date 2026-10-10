# FINAL REPORT — Klon-8 Rhyme Checker Evaluation

**Date:** 2026-10-11 · **Machine:** 13th Gen Intel Core i7-13620H (10 cores / 16
threads), 31.7 GB RAM · **Corpus:** post-transcription-gap-patch (36,474 stanzas).

This is the authoritative, self-contained report of every number in the paper.
Sources: `Paper/eval_checkers/full_gold_results.json` (gold),
`Paper/report/paper_tables.json` (augmentation),
`Paper/eval_checkers/full_metrics.json` (merged),
`Paper/eval_checkers/benchmark_speed.json` (speed).

Rule notation: $R_1$ สดับ→รับ, $R_2$ รับ→รอง, $R_3$ รอง→ส่ง, $R_X$ inter-stanza.

---

## 1. Corpus

| Name | Files | Stanzas | Waks | $R_1{+}R_2{+}R_3$ | $R_X$ | Total rhyme |
|---|---:|---:|---:|---:|---:|---:|
| SuphasaetSonYing | 1 | 200 | 800 | 600 | 199 | 799 |
| khobut | 14 | 1,303 | 5,212 | 3,909 | 1,289 | 5,198 |
| khunChangKhunPhaen | 43 | 10,543 | 42,172 | 31,629 | 10,500 | 42,129 |
| phraAphai | 132 | 24,341 | 97,364 | 73,023 | 24,206 | 97,229 |
| phukaoTong | 1 | 87 | 348 | 261 | 86 | 347 |
| **TOTAL** | **191** | **36,474** | **145,896** | **109,422** | **36,280** | **145,702** |

- $R_1{+}R_2{+}R_3$ = 3 × stanzas (every stanza has the three intra-stanza rules).
- $R_X$ = stanzas − files − gap-seams (a row with no previous stanza is N/A; the 3
  gap-seam rows are also N/A).
- Total = 3 × 36,474 + 36,280 = **145,702**.
- Augmentation: 11,623 instances (10,000 negatives + 1,623 positives).

---

## 2. Gold-corpus recall (all-positive → recall only)

| checker | stanza_ok% | $R_1$ | $R_2$ | $R_3$ | $R_X$ | n |
|---|---:|---:|---:|---:|---:|---:|
| A (5.0.1) | 74.0 | 86.3 | 89.5 | – | 89.4 | 36,429 |
| B (5.3.5) | 88.1 | 94.7 | 97.2 | 95.5 | 97.4 | 36,474 |
| D_w2p | 88.1 | 95.4 | 97.0 | 94.9 | 97.3 | 36,474 |
| **D_ssg** | **89.2** | **95.9** | **97.4** | 95.2 | **97.8** | 36,474 |
| C (Kongfha) | 85.5 | 93.1 | 96.5 | 94.1 | 96.6 | 69,482 |

$R_3$ is N/A for A (5.0.1 has no $R_3$). C evaluates 2 stanzas per 8-wak unit, so
its `n` is ~2× and it drops units on tltk failures (coverage 97.6%).

Per-story stanza_ok%:

| story | A | B | D_w2p | D_ssg | C |
|---|---:|---:|---:|---:|---:|
| SuphasaetSonYing | 76.9 | 91.0 | 89.5 | 89.5 | 87.1 |
| khobut | 70.5 | 86.7 | 85.7 | 86.1 | 83.7 |
| khunChangKhunPhaen | 76.2 | 87.3 | 83.5 | 84.8 | 80.5 |
| phraAphai | 73.2 | 88.6 | 90.3 | 91.3 | 87.6 |
| phukaoTong | 67.8 | 81.6 | 77.0 | 79.3 | 80.0 |

---

## 3. Augmentation — precision / recall / F1 (stanza level)

10,000 oracle-verified negatives + 1,623 positives.

| checker | P | R | F1 | coverage | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A (5.0.1) | 28.4 | 62.7 | 39.1 | 99.3 | 775 | 1,950 | 461 | 5,492 |
| B (5.3.5) | **100.0** | 73.9 | 85.0 | 100.0 | 1,200 | **0** | 423 | 10,000 |
| D_w2p | 83.4 | **92.1** | **87.5** | 100.0 | 1,495 | 298 | 128 | 9,702 |
| D_ssg | 86.8 | 87.0 | 86.9 | 100.0 | 1,412 | 215 | 211 | 9,785 |
| C (Kongfha) | 30.4 | 87.1 | 45.1 | 97.6 | 1,357 | 3,107 | 201 | 6,674 |

Per-rule augmentation F1:

| checker | $R_1$ | $R_2$ | $R_3$ | $R_X$ |
|---|---:|---:|---:|---:|
| A (5.0.1) | 39.7 | 39.1 | – | 38.5 |
| B (5.3.5) | 70.6 | 87.3 | 88.2 | **99.0** |
| D_w2p | 85.7 | 94.0 | 80.8 | 92.7 |
| D_ssg | 82.7 | 91.6 | 82.2 | 95.5 |
| C (Kongfha) | 49.4 | 49.9 | 37.2 | 42.3 |

---

## 4. Merged (gold + augmentation) — the headline table

| checker | P | R | F1 |
|---|---:|---:|---:|
| A (5.0.1) | 95.0 | 73.1 | 82.6 |
| B (5.3.5) | **100.0** | 87.2 | 93.2 |
| D_w2p | 99.6 | 87.7 | 93.3 |
| **D_ssg** | 99.7 | **88.5** | **93.8** |
| C (Kongfha) | 92.2 | 84.2 | 88.0 |

---

## 5. Oracle-blind probe

423 genuine rhymes the 5.3.5 oracle cannot see (silent-ร `เพชร`, first-sara
`ศัตรู`/`กษัตรี`/`กษัตรีย์`).

| checker | oracle-blind recall | recovered / 423 |
|---|---:|---:|
| A (5.0.1) | 21.5 | 91 |
| B (5.3.5) | 0.0 | 0 |
| D_w2p | **95.7** | 405 |
| D_ssg | 68.1 | 288 |
| C (Kongfha) | 78.7 | 333 |

---

## 6. Speed (full gold corpus; C on a 200-unit sample; 3 repeats, idle machine)

| workers | A | B | D_w2p | D_ssg | C (sample) |
|---:|---:|---:|---:|---:|---:|
| 1 | 13.59 | 28.94 | 20.10 | 21.50 | 61.64 |
| 2 | 7.35 | 15.60 | 17.95 | 11.91 | 64.08 |
| 3 | 5.49 | 11.74 | 16.27 | 9.12 | 48.87 |
| 4 | 4.60 | 10.40 | 17.34 | 7.17 | 43.75 |
| 5 | 3.89 | 9.37 | 16.12 | 6.37 | 40.35 |
| 6 | 3.66 | 7.67 | 16.65 | 6.03 | 36.87 |
| 7 | 3.60 | 6.97 | 17.64 | 5.52 | 35.93 |
| 8 | 3.58 | 6.93 | 19.49 | 5.28 | 35.07 |
| 9 | 3.47 | 6.78 | 20.14 | 5.21 | 32.33 |
| 10 | 3.42 | 6.62 | 22.18 | 5.73 | 32.05 |

Speed-up at 10 workers: A **3.98×**, B **4.37×**, D_ssg **3.76×**, C **1.92×**;
**D_w2p 0.91× (slower)** — its numpy-GRU w2p spawns a BLAS thread pool per process.

Full-corpus C (36,283 units): ~0.31 s/unit → ~3.1 h at 1 worker, ~1.6 h at 10.

---

## 7. Which metrics to report (avoid confusing the reader)

The gold corpus is **all-positive** (classical poems are presumed to rhyme), so:

- **Gold → RECALL only** (stanza + per rule). Precision is undefined there.
- **Augmentation → PRECISION, RECALL, F1** (it has both classes).
- **Coverage** → C only (A/B/D cover ~100%).
- **Oracle-blind recall** → separate probe (oracle itself = 0%).
- **Do NOT mix** gold recall and augment recall in one column.

Recommended paper tables: (1) corpus, (2) gold recall, (3) augment P/R/F1,
(4) oracle-blind probe, (5) speed. That is exactly the set above.
