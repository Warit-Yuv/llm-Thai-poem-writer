# -*- coding: utf-8 -*-
"""Comprehensive end-to-end evaluation + speed benchmark, with repeats.

Runs the FULL pipeline on an otherwise-idle machine and averages the speed
numbers over N repeats:

  1. Gold eval   — A/B/D_w2p/D_ssg (parallel) + C (from checkpoints)
  2. Augment eval — A/B/D_w2p/D_ssg + C (the slow part, ~24 min at 4 workers)
  3. Speed bench  — each checker separately at 1..10 workers, R repeats each
  4. Consolidate  — full_gold_results.json
  5. Tables       — paper_tables.json (from the fresh augment verdicts)
  6. Metrics      — full_metrics.json

Usage (from repo root, with KONGFHA_PYTHON set):
    $env:KONGFHA_PYTHON = (Resolve-Path ".venv312\\Scripts\\python.exe").Path
    .venv\\Scripts\\python.exe Paper/eval_checkers/run_full_eval.py --repeats 3

Outputs a summary to stdout and writes ``Paper/eval_checkers/full_eval_summary.json``.
"""
import argparse
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
PY = sys.executable
SUMMARY = os.path.join(_HERE, "full_eval_summary.json")


def run(cmd, label):
    print(f"\n{'='*70}\n{label}\n{'='*70}", flush=True)
    t = time.time()
    p = subprocess.run(cmd, cwd=ROOT)
    dt = time.time() - t
    print(f"[{label}] exit={p.returncode} in {dt:.0f}s", flush=True)
    if p.returncode != 0:
        raise SystemExit(f"{label} failed (exit {p.returncode})")
    return dt


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=3,
                    help="repeats per worker count in the speed benchmark")
    ap.add_argument("--workers", type=int, default=10,
                    help="A/B/D workers for the eval passes")
    ap.add_argument("--dw-workers", type=int, default=4)
    ap.add_argument("--c-workers", type=int, default=4,
                    help="Checker C workers (4 is the sweet spot)")
    ap.add_argument("--skip-speed", action="store_true")
    ap.add_argument("--skip-eval", action="store_true")
    args = ap.parse_args()

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    if not os.environ.get("KONGFHA_PYTHON"):
        print("WARNING: KONGFHA_PYTHON not set — Checker C will fail.",
              flush=True)

    summary = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
               "repeats": args.repeats, "timings": {}}

    # 1+2. Full eval (gold + augment) → full_metrics.json
    if not args.skip_eval:
        summary["timings"]["eval_harness"] = run([
            PY, "Paper/eval_checkers/eval_harness.py",
            "--workers", str(args.workers),
            "--dw-workers", str(args.dw_workers),
            "--c-workers", str(args.c_workers),
            "--augment", "Paper/augment/output/instances.json",
            "--out", "Paper/eval_checkers/full_metrics.json",
        ], "eval_harness (gold + augment)")

        # 4. Consolidate gold (A/B/D + C from chunks)
        summary["timings"]["consolidate"] = run([
            PY, "Paper/eval_checkers/consolidate_results.py",
            "--workers", str(args.workers),
            "--dw-workers", str(args.dw_workers),
            "--out", "Paper/eval_checkers/full_gold_results.json",
        ], "consolidate_results (gold)")

        # 5. Paper tables (from the fresh augment verdicts)
        summary["timings"]["paper_tables"] = run([
            PY, "Paper/eval_checkers/paper_report_data.py",
            "--from-verdicts", "Paper/report/augment_verdicts.json",
            "--out", "Paper/report/paper_tables.json",
        ], "paper_report_data (augment tables)")

    # 3. Speed benchmark (per checker, 1..10 workers, R repeats)
    if not args.skip_speed:
        summary["timings"]["speed_abd"] = run([
            PY, "Paper/eval_checkers/benchmark_speed.py", "--only", "abd",
            "--repeats", str(args.repeats),
            "--workers", *[str(w) for w in range(1, 11)],
        ], "speed benchmark A/B/D_w2p/D_ssg (1..10 workers)")
        summary["timings"]["speed_c"] = run([
            PY, "Paper/eval_checkers/benchmark_speed.py", "--only", "c",
            "--c-sample", "200", "--repeats", str(args.repeats),
            "--workers", *[str(w) for w in range(1, 11)],
        ], "speed benchmark C (200-unit sample, 1..10 workers)")

    summary["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"\nwrote {SUMMARY}", flush=True)


if __name__ == "__main__":
    main()
