# Checker speed benchmark (2026-10-09)

Machine: 13th Gen Intel Core i7-13620H (10 cores / 16 logical), 31.7 GB RAM.
Measured with `Paper/eval_checkers/benchmark_speed.py`; raw data in
`Paper/eval_checkers/benchmark_speed.json`.

## A/B/D/Dssg — full gold corpus (36,474 stanzas)

All four checkers run together (A, B, D_w2p, D_ssg) over the whole corpus.

| workers | seconds | speed-up |
|---:|---:|---:|
| 1 | 240.91 | 1.00x |
| 2 | 134.53 | 1.79x |
| 3 | 117.40 | 2.05x |
| 4 | 108.16 | 2.23x |
| 5 | 110.17 | 2.19x |
| 6 | 93.49 | 2.58x |
| 7 | 40.49 | 5.95x |
| 8 | 52.94 | 4.55x |
| 9 | 61.96 | 3.89x |
| 10 | 43.89 | 5.49x |

**Reading:** scaling is real but noisy — the machine had background load (OneDrive,
browser, VS Code) during the run, so workers 7–10 are not monotonic. The clean
signal is ~2.2x at 4 workers and ~5.5x at 10. D_w2p is capped at 4 workers (its
numpy-GRU w2p engine does not scale; see `parallel_eval.py`).

## Checker C (Kongfha / tltk) — 200-unit sample

| workers | seconds | u/s | speed-up |
|---:|---:|---:|---:|
| 1 | 155.81 | 1.3 | 1.00x |
| 2 | 157.08 | 1.3 | 0.99x |
| 4 | 51.64 | 3.9 | 3.02x |
| 10 | 53.30 | 3.8 | 2.92x |

**Reading:** C is ~0.37 s/unit single-threaded (tltk G2P is pure-Python,
single-threaded). It scales to ~3x at 4 workers but **not beyond** — 10 workers is
no faster than 4 (memory/CPU contention: each tltk process loads ~400 MB of
gensim models). **Use 4 workers for C.**

## Full-corpus C runtime (extrapolated)

- Gold corpus: 36,283 units → ~3.7 h at 1 worker, ~1.2 h at 4 workers.
- Augmentation: 11,623 units → ~1.2 h at 1 worker, ~24 min at 4 workers.
- The gold chunks were produced by `recover_c_chunks.py` (only 275 units re-scored,
  ~2 min) because the gap patch changed so few units.

## Notes / gotchas

- The tltk worker is **slow, not hung**: it streams results steadily at ~0.37 s/unit.
  A large batch looks idle for minutes before the first result; do not kill it.
- `score_units_parallel` uses one-shot subprocesses with temp-file I/O in
  `sub_batch`-sized rounds (the persistent-pool design stalled).
- Run the benchmark on an otherwise-idle machine for clean numbers.
