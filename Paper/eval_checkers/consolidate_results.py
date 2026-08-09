# -*- coding: utf-8 -*-
"""
Consolidate the full-corpus gold evaluation of all four checkers into a single
reproducible JSON artifact for the report notebook.

  * recomputes A (pythainlp 5.0.1), B (pythainlp 5.3.5), D (Klonpad w2p) and
    D_ssg (Klonpad ssg fallback) from the corpus; can be parallelised with
    ``--workers N``. Measured: all-four 95 s sequential -> ~33 s with
    ``--workers 10 --dw-workers 4`` (B/A/D_ssg scale up to ~10x, but D_w2p's
    numpy-GRU w2p engine does NOT scale and is fastest at 4 workers, so the
    mixed setting caps only D_w2p at 4)
  * reads Checker C results from the checkpoint files written by ``run_c_full``
    (or skips it with ``--skip-c``)
  * runs the cross-chapter boundary rX check (report-only; the primary metric
    stays file-by-file): last stanza's Wak4 of chapter N vs first stanza's Wak2
    of chapter N+1, judged by checker B
  * writes ``Paper/eval_checkers/full_gold_results.json`` (override with
    ``--out``)
"""
import argparse
import json
import os
import sys
import time
from collections import OrderedDict, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # eval_checkers
sys.path.insert(0, os.path.dirname(_HERE))    # Paper
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

from data_loading import load_stanzas  # noqa: E402
from eval_checkers import (  # noqa: E402
    OriginalKhaveeChecker, RuleBasedKhaveeChecker, KlonpadChecker,
    KlonpadSsgChecker, KongfhaChecker,
)
from eval_checkers.common import RULES  # noqa: E402
from eval_checkers.run_c_full import CHECK_DIR, build_units  # noqa: E402
from eval_checkers.parallel_eval import run_checkers  # noqa: E402

OUT = os.path.join(_HERE, "full_gold_results.json")

CHECKERS = [
    ("A_pythainlp_5.0.1", OriginalKhaveeChecker, None),
    ("B_pythainlp_5.3.5", RuleBasedKhaveeChecker, None),
    ("D_klonpad_w2p", KlonpadChecker, None),
    ("D_klonpad_ssg_fallback", KlonpadSsgChecker, None),
]


def _empty():
    return {"n": 0, "pass": 0, "drop": 0, "we": 0,
            "r_ok": defaultdict(int), "r_n": defaultdict(int)}


def _run_c(meta, nchunks):
    rows = []
    for k in range(nchunks):
        fp = os.path.join(CHECK_DIR, f"chunk_{k:03d}.jsonl")
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    client = KongfhaChecker()
    per = defaultdict(_empty)
    for (story, _i, _j), res in zip(meta, rows):
        fail = res.get("fail")
        if fail and fail.startswith("WorkerError"):
            per[story]["we"] += 1
            per[story]["drop"] += 1
            continue
        bot1, bot2, inter, drop, _reason = client.build_pair(res)
        for bot in (bot1, bot2):
            st = per[story]
            if drop:
                st["drop"] += 1
                continue
            st["n"] += 1
            st["pass"] += int(bot.stanza_ok)
            for rid in RULES:
                v = bot.rules.get(rid)
                if v is not None:
                    st["r_n"][rid] += 1
                    st["r_ok"][rid] += int(v)
        if not drop:
            per[story]["r_n"]["rX_inter"] += 1
            per[story]["r_ok"]["rX_inter"] += int(inter)
    return per


def _cross_chapter(by_ch):
    B = RuleBasedKhaveeChecker()
    cross = {}
    for story in sorted({k[0] for k in by_ch}):
        chs = [k[1] for k in by_ch if k[0] == story]
        ok = tot = 0
        ex = []
        for a in range(len(chs) - 1):
            last = by_ch[(story, chs[a])][-1]
            first = by_ch[(story, chs[a + 1])][0]
            tot += 1
            r = B.check_stanza(first.w1, first.w2, first.w3, first.w4,
                               prev_w4=last.w4)
            if not r.dropped and r.rules["rX_inter"]:
                ok += 1
            else:
                ex.append([chs[a], chs[a + 1],
                           last.w4, first.w2])
        cross[story] = {"boundaries": tot, "rhyme": ok,
                        "exceptions": ex[:10], "nexceptions": len(ex)}
    return cross


def _to_plain(per):
    out = {}
    for story, st in sorted(per.items()):
        out[story] = {
            "n": st["n"], "pass": st["pass"], "drop": st["drop"], "we": st["we"],
            "stanza_ok_pct": round(100 * st["pass"] / max(1, st["n"]), 2),
            "rules": {rid: {"n": st["r_n"].get(rid, 0), "ok": st["r_ok"].get(rid, 0),
                            "accept_pct": round(100 * st["r_ok"].get(rid, 0) /
                                                max(1, st["r_n"].get(rid, 0)), 2)}
                      for rid in RULES},
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel processes for the A/B/D/Dssg eval loop "
                         "(default 1 = sequential; recommended 10, with "
                         "--dw-workers 4 for D_w2p, which does not scale)")
    ap.add_argument("--dw-workers", type=int, default=None,
                    help="worker count for D_w2p only (defaults to --workers). "
                         "D_w2p's numpy-GRU w2p engine is fastest at ~4 workers, "
                         "while B/A/D_ssg scale up to ~10, so e.g. "
                         "`--workers 10 --dw-workers 4` mixes both optima")
    ap.add_argument("--skip-c", action="store_true",
                    help="skip reading Checker C checkpoint files "
                         "(use when run_c_full has not been run yet)")
    ap.add_argument("--out", default=OUT,
                    help=f"output JSON path (default: {OUT})")
    args = ap.parse_args()

    t0 = time.time()
    stanzas = load_stanzas()
    by_ch = OrderedDict()
    for s in stanzas:
        by_ch.setdefault((s.story, s.chapter), []).append(s)
    units, meta = build_units()
    nchunks = (len(units) + 3000 - 1) // 3000

    if args.dw_workers is None:
        workers = args.workers
    else:
        workers = {name: (args.dw_workers if name == "D_klonpad_w2p"
                          else args.workers) for name, _c, _k in CHECKERS}
    print(f"running A/B/D/Dssg with workers={workers}...", flush=True)
    abc = run_checkers(stanzas, CHECKERS, workers=workers)
    print(f"  A/B/D/Dssg done in {time.time() - t0:.0f}s", flush=True)

    data = {
        "date": "2026-08-09",
        "gold": {
            "files": len({(s.story, s.chapter) for s in stanzas}),
            "stanzas": len(stanzas),
            "waks": len(stanzas) * 4,
            "inter_links": len(units),
        },
        "checkers": {},
        "cross_chapter_rX": None,
    }
    for name, per in abc.items():
        data["checkers"][name] = _to_plain(per)

    if args.skip_c:
        print("skipping Checker C (--skip-c)", flush=True)
    else:
        print("reading C from checkpoints...", flush=True)
        per_c = _run_c(meta, nchunks)
        data["checkers"]["C_kongfha_word_check"] = _to_plain(per_c)

    print("cross-chapter rX check (checker B)...", flush=True)
    cross = _cross_chapter(by_ch)
    data["cross_chapter_rX"] = cross

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"wrote {args.out}  ({time.time() - t0:.0f}s total)", flush=True)

    # quick console summary
    for name, per in data["checkers"].items():
        tot = {"n": 0, "pass": 0}
        for st in per.values():
            tot["n"] += st["n"]
            tot["pass"] += st["pass"]
        print(f"{name:<24} stanza_ok={100 * tot['pass'] / max(1, tot['n']):.1f}%  "
              f"n={tot['n']}")
    print("\ncross-chapter boundaries rhyming:")
    for story, c in cross.items():
        print(f"  {story:<22} {c['rhyme']}/{c['boundaries']}  "
              f"({c['nexceptions']} non-rhyming)")


if __name__ == "__main__":
    main()
