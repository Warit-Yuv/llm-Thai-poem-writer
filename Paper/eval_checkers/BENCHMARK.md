# Checker speed benchmark (2026-10-09)

Machine: 13th Gen Intel Core i7-13620H (10 cores / 16 logical), 31.7 GB RAM.
Measured with `Paper/eval_checkers/benchmark_speed.py`; raw data in
`Paper/eval_checkers/benchmark_speed.json`.

Each checker is timed **separately** over the full gold corpus (36,474 stanzas),
at worker counts 1..10. Checker C is timed on a 100-unit sample (its full-corpus
pass is ~1 h; the sample isolates the scaling shape).

## A — PyThaiNLP 5.0.1 (full corpus)

| workers | seconds | speed-up |
|---:|---:|---:|
| 1 | 22.82 | 1.00x |
| 2 | 10.25 | 2.23x |
| 3 | 7.24 | 3.15x |
| 4 | 5.82 | 3.92x |
| 5 | 5.23 | 4.36x |
| 6 | 4.56 | 5.01x |
| 7 | 4.72 | 4.84x |
| 8 | 4.51 | 5.06x |
| 9 | 4.31 | 5.29x |
| 10 | 4.15 | 5.49x |

## B — PyThaiNLP 5.3.5 (full corpus)

| workers | seconds | speed-up |
|---:|---:|---:|
| 1 | 37.77 | 1.00x |
| 2 | 36.05 | 1.05x |
| 3 | 22.92 | 1.65x |
| 4 | 19.59 | 1.93x |
| 5 | 18.67 | 2.02x |
| 6 | 18.36 | 2.06x |
| 7 | 16.86 | 2.24x |
| 8 | 17.32 | 2.18x |
| 9 | 13.92 | 2.71x |
| 10 | 7.82 | 4.83x |

## D_w2p — Klonpad, Word2Phrase fallback (full corpus)

| workers | seconds | speed-up |
|---:|---:|---:|
| 1 | 32.26 | 1.00x |
| 2 | 43.15 | 0.75x |
| 3 | 42.85 | 0.75x |
| 4 | 44.45 | 0.73x |
| 5 | 49.53 | 0.65x |
| 6 | 58.19 | 0.55x |
| 7 | 59.29 | 0.54x |
| 8 | 58.58 | 0.55x |
| 9 | 63.57 | 0.51x |
| 10 | 63.81 | 0.51x |

**D_w2p gets SLOWER with more workers** — its w2p engine is a pure-numpy GRU
whose `np.matmul` spawns a BLAS thread pool *per process*, so N processes
oversubscribe the cores. **Use 1 worker for D_w2p** (or cap it at 4 with
`--dw-workers 4` and BLAS threads pinned to 1, as `parallel_eval.py` does).

## D_ssg — Klonpad, ssg fallback (full corpus)

| workers | seconds | speed-up |
|---:|---:|---:|
| 1 | 47.30 | 1.00x |
| 2 | 23.85 | 1.98x |
| 3 | 17.84 | 2.65x |
| 4 | 13.59 | 3.48x |
| 5 | 15.06 | 3.14x |
| 6 | 15.18 | 3.12x |
| 7 | 13.68 | 3.46x |
| 8 | 14.98 | 3.16x |
| 9 | 13.95 | 3.39x |
| 10 | 12.86 | 3.68x |

## C — Kongfha / tltk (100-unit sample)

| workers | seconds | u/s | speed-up |
|---:|---:|---:|---:|
| 1 | 55.61 | 1.8 | 1.00x |
| 2 | 78.12 | 1.3 | 0.71x |
| 3 | 64.88 | 1.5 | 0.86x |
| 4 | 56.55 | 1.8 | 0.98x |
| 5 | 50.65 | 2.0 | 1.10x |
| 6 | 64.22 | 1.6 | 0.87x |
| 7 | 66.64 | 1.5 | 0.83x |
| 8 | 33.28 | 3.0 | 1.67x |
| 9 | 22.96 | 4.4 | 2.42x |
| 10 | 21.99 | 4.5 | 2.53x |

**Reading:** C is ~0.37 s/unit single-threaded (tltk G2P is pure-Python,
single-threaded). On a 100-unit sample the per-process tltk model load (~10 s)
dominates, so the small-sample curve is noisy and only turns up at 8–10 workers.
On a **larger** sample (200 units, earlier run) C reached ~3x at 4 workers and
did **not** improve beyond 4 (memory contention: each tltk process loads ~400 MB
of gensim models). **Use 4 workers for C on real workloads.**

## Full-corpus C runtime (extrapolated from 0.37 s/unit)

- Gold corpus: 36,283 units → ~3.7 h at 1 worker, ~1.2 h at 4 workers.
- Augmentation: 11,623 units → ~1.2 h at 1 worker, ~24 min at 4 workers.
- The gold chunks were produced by `recover_c_chunks.py` (only 275 units re-scored,
  ~2 min) because the gap patch changed so few units.

## Notes / gotchas

- The tltk worker is **slow, not hung**: it streams results steadily at ~0.37 s/unit.
  A large batch looks idle for minutes before the first result; do not kill it.
- `score_units_parallel` uses one-shot subprocesses with temp-file I/O in
  `sub_batch`-sized rounds (the persistent-pool design stalled).
- Run the benchmark on an otherwise-idle machine for clean numbers; the machine
  had background load (OneDrive, browser, VS Code) during these runs, so the
  mid-range worker counts are noisier than the endpoints.
