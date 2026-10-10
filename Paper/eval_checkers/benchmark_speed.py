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


def bench_abd(stanzas, worker_counts, repeats=1):
    """Time EACH of A/B/D_w2p/D_ssg separately over the full corpus, at each
    worker count, averaged over ``repeats`` runs.
    Returns {checker_name: {workers: mean_seconds}}."""
    results = {name: {} for name, _c, _k in ABD}
    for name, cls, kw in ABD:
        for w in worker_counts:
            times = []
            for _ in range(repeats):
                t = time.time()
                run_checkers(stanzas, [(name, cls, kw)], workers=w)
                times.append(time.time() - t)
            dt = sum(times) / len(times)
            results[name][w] = dt
            extra = (f"  (runs {['%.1f' % x for x in times]})"
                     if repeats > 1 else "")
            print(f"  {name:<24} workers={w:>2}  {dt:7.2f}s{extra}", flush=True)
    return results


def bench_c(units, worker_counts, sample, repeats=1):
    """Time Checker C on a fixed sample of units at each worker count,
    averaged over ``repeats`` runs."""
    batch = [(str(i), w) for i, (_uid, w) in enumerate(units[:sample])]
    results = {}
    for w in worker_counts:
        times = []
        for _ in range(repeats):
            t = time.time()
            score_units_parallel(batch, workers=w)
            times.append(time.time() - t)
        dt = sum(times) / len(times)
        results[w] = dt
        extra = (f"  (runs {['%.1f' % x for x in times]})"
                 if repeats > 1 else "")
        print(f"  C (Kongfha) workers={w:>2}  {dt:7.2f}s  "
              f"({sample / dt:.1f} u/s){extra}", flush=True)
    return results


def _table(name, results):
    """results: {workers: seconds} for a single checker."""
    base = results.get(1)
    print(f"\n== {name} ==")
    print(f"  {'workers':>7}  {'seconds':>9}  {'speed-up':>9}")
    for w in sorted(results):
        su = (base / results[w]) if base else float("nan")
        print(f"  {w:>7}  {results[w]:>9.2f}  {su:>8.2f}x")


def _table_multi(title, per_checker):
    """per_checker: {checker_name: {workers: seconds}} — one column per checker."""
    names = list(per_checker)
    workers = sorted({w for r in per_checker.values() for w in r})
    print(f"\n== {title} ==")
    header = f"  {'workers':>7}  " + "  ".join(f"{n[:18]:>18}" for n in names)
    print(header)
    for w in workers:
        cells = []
        for n in names:
            base = per_checker[n].get(1)
            dt = per_checker[n].get(w)
            if dt is None:
                cells.append(f"{'—':>18}")
            else:
                su = (base / dt) if base else float("nan")
                cells.append(f"{dt:>10.2f}s {su:>5.2f}x")
        print(f"  {w:>7}  " + "  ".join(cells))


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
    ap.add_argument("--repeats", type=int, default=1,
                    help="repeat each measurement N times and average "
                         "(reduces noise from background load)")
    args = ap.parse_args()

    out = {"workers": args.workers, "c_sample": args.c_sample,
           "repeats": args.repeats}

    if args.only in ("abd", "all"):
        stanzas = load_stanzas()
        print(f"A/B/D_w2p/D_ssg over {len(stanzas)} stanzas (each timed separately, "
              f"{args.repeats} repeat(s))", flush=True)
        out["abd"] = bench_abd(stanzas, args.workers, repeats=args.repeats)
        _table_multi("A/B/D_w2p/D_ssg (full corpus, per checker)", out["abd"])

    if args.only in ("c", "all"):
        units, _meta = build_units()
        print(f"\nChecker C over {args.c_sample} units (sample, "
              f"{args.repeats} repeat(s))", flush=True)
        out["c"] = bench_c(units, args.workers, args.c_sample,
                           repeats=args.repeats)
        _table(f"C (Kongfha, {args.c_sample}-unit sample)", out["c"])

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
