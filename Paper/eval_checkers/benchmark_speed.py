# -*- coding: utf-8 -*-
"""Speed benchmark for the four checkers (A/B/D/Dssg) and Checker C.

Measures wall-clock time for the gold-corpus evaluation at worker counts 1..10,
so the parallel speed-up (or slow-down) of each checker is reproducible.

  * A/B/D/Dssg: full gold corpus (36,283 stanzas) via parallel_eval.run_checkers
  * C (Kongfha): a fixed SAMPLE of units (default 1 chunk = 3000) via the
    persistent tltk worker pool, since the full corpus is ~50 min per pass

Usage:
    .venv\\Scripts\\python.exe Paper/eval_checkers/benchmark_speed.py
    .venv\\Scripts\\python.exe Paper/eval_checkers/benchmark_speed.py --c-sample 500
    .venv\\Scripts\\python.exe Paper/eval_checkers/benchmark_speed.py --only abd
    .venv\\Scripts\\python.exe Paper/eval_checkers/benchmark_speed.py --only c

Output: a table per checker (workers, seconds, speed-up vs 1 worker) and a JSON
file ``Paper/eval_checkers/benchmark_speed.json`` for the record.
"""
import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from data_loading import load_stanzas  # noqa: E402
from eval_checkers import (  # noqa: E402
    OriginalKhaveeChecker, RuleBasedKhaveeChecker, KlonpadChecker,
    KlonpadSsgChecker,
)
from eval_checkers.parallel_eval import run_checkers  # noqa: E402
from eval_checkers.run_c_full import build_units, score_units_parallel  # noqa: E402

OUT = os.path.join(_HERE, "benchmark_speed.json")

ABD = [
    ("A_pythainlp_5.0.1", OriginalKhaveeChecker, None),
    ("B_pythainlp_5.3.5", RuleBasedKhaveeChecker, None),
    ("D_klonpad_w2p", KlonpadChecker, None),
    ("D_klonpad_ssg_fallback", KlonpadSsgChecker, None),
]


def bench_abd(stanzas, worker_counts):
    """Time A/B/D/Dssg over the full corpus at each worker count."""
    results = {}
    for w in worker_counts:
        t = time.time()
        run_checkers(stanzas, ABD, workers=w)
        dt = time.time() - t
        results[w] = dt
        print(f"  A/B/D/Dssg  workers={w:>2}  {dt:7.2f}s", flush=True)
    return results


def bench_c(units, worker_counts, sample):
    """Time Checker C on a fixed sample of units at each worker count."""
    batch = [(str(i), w) for i, (_uid, w) in enumerate(units[:sample])]
    results = {}
    for w in worker_counts:
        t = time.time()
        score_units_parallel(batch, workers=w)
        dt = time.time() - t
        results[w] = dt
        print(f"  C (Kongfha) workers={w:>2}  {dt:7.2f}s  "
              f"({sample / dt:.1f} u/s)", flush=True)
    return results


def _table(name, results):
    base = results.get(1)
    print(f"\n== {name} ==")
    print(f"  {'workers':>7}  {'seconds':>9}  {'speed-up':>9}")
    for w in sorted(results):
        su = (base / results[w]) if base else float("nan")
        print(f"  {w:>7}  {results[w]:>9.2f}  {su:>8.2f}x")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["abd", "c", "all"], default="all")
    ap.add_argument("--workers", type=int, nargs="+",
                    default=list(range(1, 11)),
                    help="worker counts to test (default 1..10)")
    ap.add_argument("--c-sample", type=int, default=3000,
                    help="units for the C sample (default 3000 = 1 chunk)")
    args = ap.parse_args()

    out = {"workers": args.workers, "c_sample": args.c_sample}

    if args.only in ("abd", "all"):
        stanzas = load_stanzas()
        print(f"A/B/D/Dssg over {len(stanzas)} stanzas", flush=True)
        out["abd"] = bench_abd(stanzas, args.workers)
        _table("A/B/D/Dssg (full corpus)", out["abd"])

    if args.only in ("c", "all"):
        units, _meta = build_units()
        print(f"\nChecker C over {args.c_sample} units (sample)", flush=True)
        out["c"] = bench_c(units, args.workers, args.c_sample)
        _table(f"C (Kongfha, {args.c_sample}-unit sample)", out["c"])

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
