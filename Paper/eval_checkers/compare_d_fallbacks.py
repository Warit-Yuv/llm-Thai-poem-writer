# -*- coding: utf-8 -*-
"""
Diagnostic: why does D (Klonpad) trail B (pythainlp 5.3.5), and does the w2p
fallback help or hurt?

Runs three segmentation paths over the full gold corpus under identical rules /
rhyme predicate (isolation of the segmentation variable):
  * B          = pythainlp 5.3.5 ``subword_tokenize(engine="ssg")``
  * D_w2p      = overrides + w2p ``pronunciate`` fallback (original Klonpad)
  * D_ssg      = overrides + plain ssg fallback (no w2p)

Also reports (single-process only, ``--workers 1``):
  * per-story syllable-source stats (override vs w2p/ssg) for D_w2p
  * ``process_w2p.cache_info()`` after the run -> distinct w2p inputs, to judge
    the LRU size needed (was 8,192; now 200,000)

Usage:
    .venv\\Scripts\\python.exe Paper\\eval_checkers\\compare_d_fallbacks.py [--workers 10]
"""
import argparse
import sys
import time
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"e:\User\Noto\SIIT\SIIT_Year_4\LLM_WritePoem")
sys.path.insert(0, r"e:\User\Noto\SIIT\SIIT_Year_4\LLM_WritePoem\Paper")

from data_loading import load_stanzas  # noqa: E402
from eval_checkers import (  # noqa: E402
    RuleBasedKhaveeChecker, KlonpadChecker, KlonpadSsgChecker,
)
from eval_checkers.common import RULES  # noqa: E402
from eval_checkers.parallel_eval import run_checkers  # noqa: E402
from eval_checkers import klonpad_syllables as kp  # noqa: E402

CHECKERS = [
    ("B_pythainlp_5.3.5", RuleBasedKhaveeChecker, None),
    ("D_w2p_overrides", KlonpadChecker, {"fallback": "w2p"}),
    ("D_ssg_overrides", KlonpadSsgChecker, None),
]


def fmt(st):
    rr = [f"{100 * st['r_ok'][rid] / max(1, st['r_n'][rid]):4.0f}" for rid in RULES]
    return f"{100 * st['pass'] / st['n']:6.1f}%   {'/'.join(rr)}  (n={st['n']})"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel processes for B/D_w2p/D_ssg eval "
                         "(default 1 = sequential; use your core count, e.g. 10)")
    ap.add_argument("--dw-workers", type=int, default=None,
                    help="worker count for D_w2p only (defaults to --workers); "
                         "D_w2p's w2p engine is fastest at ~4 workers, so e.g. "
                         "`--workers 10 --dw-workers 4` mixes both optima")
    args = ap.parse_args()

    if args.dw_workers is None:
        workers = args.workers
    else:
        workers = {name: (args.dw_workers if name == "D_w2p_overrides"
                          else args.workers) for name, _c, _k in CHECKERS}

    stanzas = load_stanzas()
    t0 = time.time()
    per = run_checkers(stanzas, CHECKERS, workers=workers)
    print(f"  eval done in {time.time() - t0:.0f}s "
          f"(workers={workers})", flush=True)

    if args.workers <= 1:
        print("\nw2p cache_info:", kp.process_w2p.cache_info())
        print("  (hits+misses = total w2p calls; misses ~ distinct words needing w2p)")
    else:
        print("\n(skipping w2p cache_info + syllable-source stats: they are "
              "single-process diagnostics; rerun with --workers 1 for them)")

    for name, per_story in per.items():
        print(f"\n{name}")
        tot = {"n": 0, "pass": 0, "r_ok": defaultdict(int), "r_n": defaultdict(int)}
        for story in sorted(per_story):
            st = per_story[story]
            for rid in RULES:
                tot["r_n"][rid] += st["r_n"][rid]
                tot["r_ok"][rid] += st["r_ok"][rid]
            tot["n"] += st["n"]
            tot["pass"] += st["pass"]
            print(f"  {story:<22} {fmt(st)}")
        print(f"  {'TOTAL':<22} {fmt(tot)}")

    if args.workers <= 1:
        print("\nsyllable-source stats for D_w2p (fraction of syllables from "
              "override dictionary vs w2p fallback):")
        for story in sorted({s.story for s in stanzas}):
            stats = {}
            for s in stanzas:
                if s.story == story:
                    for w in s.waks():
                        kp.extract_poetic_syllables(w, fallback="w2p", stats=stats)
            tot = sum(stats.values())
            ov = stats.get("override", 0)
            w2p = stats.get("w2p", 0)
            print(f"  {story:<22} syllables={tot:>7}  override={ov:>7} "
                  f"({100 * ov / max(1, tot):5.1f}%)  w2p={w2p:>7} "
                  f"({100 * w2p / max(1, tot):5.1f}%)")


if __name__ == "__main__":
    main()
