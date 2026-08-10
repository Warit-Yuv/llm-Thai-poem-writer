# -*- coding: utf-8 -*-
"""
Compute the paper's augment-only tables and op-level FP/FN breakdown for all
five checkers (A, B, D_w2p, D_ssg, C) and save them to
``Paper/report/paper_tables.json`` for the report notebook.

- A/B/D_w2p/D_ssg are scored in parallel (fast).
- Checker C is scored through the persistent tltk worker pool (slow, ~10-15
  min for the 11,623 augment instances) -- same path as eval_harness.

Output JSON structure::

    {
      "generated": ISO timestamp,
      "per_checker": {
         "<checker>": {
           "stanza":  {augment-only stanza metrics incl. tp/fp/fn/tn,
                       coverage},
           "rules":   {rid: {augment-only metrics}},
           "fn_pos_combined": N, "fn_tricky": N, "fn_oracle_blind": N,
           "fp_by_op": {op: N}, "fn_pos_by_op": {op: N},
           "pos_recall_by_op": {op: {"tp": n, "total": n}},
         }, ...
      },
      "neg_mix": {op: count}, "pos_mix": {op: count}
    }
"""
import argparse
import json
import os
import sys
import time
from collections import Counter, OrderedDict, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # eval_checkers
sys.path.insert(0, os.path.dirname(_HERE))    # Paper
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

from data_loading import Stanza  # noqa: E402
from eval_checkers import metrics as M  # noqa: E402
from eval_checkers.eval_harness import (  # noqa: E402
    CHECKERS, C_NAME, collect_instances, collect_c_augment,
)
from eval_checkers.common import RULES  # noqa: E402

DEFAULT_AUG = os.path.join(os.path.dirname(_HERE), "augment", "output",
                           "instances.json")
DEFAULT_OUT = os.path.join(os.path.dirname(_HERE), "report",
                           "paper_tables.json")
DEFAULT_VERD = os.path.join(os.path.dirname(_HERE), "report",
                            "augment_verdicts.json")

# Checkers that do not implement r3 (5.0.1): for them an r3-targeting augment
# instance is N/A at the STANZA level (their stanza_ok ignores r3, so a broken
# r3 would look OK and pollute precision). Per-rule r3 stays N/A.
NO_R3 = frozenset({"A_pythainlp_5.0.1"})


def _augment_key(inst):
    return (inst["w1"], inst["w2"], inst["w3"], inst["w4"], inst["prev_w4"])


def build_report(per_inst, aug):
    """Collapse per-instance verdicts into the paper tables JSON, applying
    the Checker-A r3-N/A fix at the stanza level."""
    report = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
              "per_checker": OrderedDict()}
    for name, entries in per_inst.items():
        ck = {}
        # stanza level (augment only); r3-targeting instances are N/A for
        # checkers that do not implement r3
        stanza_entries = [e for e in entries
                          if e["rule"] != "r3_w3_w4" or name not in NO_R3]
        ck["stanza"] = M.summarise(stanza_entries, name)
        # clean overall = pooled per-rule predictions across ALL instances
        # (each instance tests exactly one rule; this is the micro-average)
        ck["overall"] = M.summarise(entries, name)
        # per rule
        ck["rules"] = {}
        for rid in RULES:
            sub = [e for e in entries if e["rule"] == rid]
            ck["rules"][rid] = M.summarise(sub, f"{name}:{rid}") \
                if sub else {"total": 0}
        # FN-pos combined (tricky + oracle-blind) + by-op
        fn_tricky = fn_ob = 0
        fn_by_op = Counter()
        fp_by_op = Counter()
        pos_recall_by_op = defaultdict(dict)
        for e in entries:
            if e["gold"] == 1:
                if e["pred"] is not True:
                    fn_by_op[e["op"]] += 1
                    if e["op"] == "HP_oracle_blind":
                        fn_ob += 1
                    elif e["op"] == "HP_tricky":
                        fn_tricky += 1
                pos_recall_by_op[e["op"]]["total"] = \
                    pos_recall_by_op[e["op"]].get("total", 0) + 1
                if e["pred"] is True:
                    pos_recall_by_op[e["op"]]["tp"] = \
                        pos_recall_by_op[e["op"]].get("tp", 0) + 1
            else:
                if e["pred"] is True:
                    fp_by_op[e["op"]] += 1
        ck["fn_pos_combined"] = fn_tricky + fn_ob
        ck["fn_tricky"] = fn_tricky
        ck["fn_oracle_blind"] = fn_ob
        ck["fp_by_op"] = dict(fp_by_op)
        ck["fn_pos_by_op"] = dict(fn_by_op)
        ck["pos_recall_by_op"] = {k: dict(v)
                                  for k, v in sorted(pos_recall_by_op.items())}
        report["per_checker"][name] = ck

    report["neg_mix"] = dict(Counter(i["op"] for i in aug if i["gold"] == 0))
    report["pos_mix"] = dict(Counter(i["op"] for i in aug if i["gold"] == 1))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--augment", default=DEFAULT_AUG)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--dw-workers", type=int, default=4)
    ap.add_argument("--skip-c", action="store_true",
                    help="skip the slow Checker C pass (table preview)")
    ap.add_argument("--dump-verdicts", default=DEFAULT_VERD,
                    help="save per-instance verdicts to this JSON "
                         "(None to disable)")
    ap.add_argument("--from-verdicts", default=None,
                    help="recompute tables from a saved augment_verdicts.json "
                         "(no checker re-run; use with --out)")
    args = ap.parse_args()

    aug = json.load(open(args.augment, encoding="utf-8"))
    print(f"augment instances: {len(aug)}", flush=True)

    if args.from_verdicts:
        per_inst = json.load(open(args.from_verdicts, encoding="utf-8"))
        print("loaded verdicts from", args.from_verdicts)
    else:
        per_inst = _collect(args, aug)
        if args.dump_verdicts:
            os.makedirs(os.path.dirname(args.dump_verdicts), exist_ok=True)
            with open(args.dump_verdicts, "w", encoding="utf-8") as f:
                json.dump(per_inst, f, ensure_ascii=False)
            print("wrote", args.dump_verdicts, flush=True)

    report = build_report(per_inst, aug)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("wrote", args.out, flush=True)

    # quick console summary
    print("\n== augment-only stanza precision/recall/F1 ==")
    for name, ck in report["per_checker"].items():
        s = ck["stanza"]
        print(f"  {name:28s} P={s['precision']} R={s['recall']} "
              f"F1={s['f1']} n={s['total']} cov={s['coverage']}")


def _collect(args, aug):
    """Score A/B/D/Dssg (parallel) + Checker C (tltk worker pool) on the
    augment instances and return per-instance verdicts keyed by checker."""
    key_inst = {_augment_key(i): i for i in aug}
    keys = list(key_inst)
    stanzas = [Stanza(key_inst[k]["story"], key_inst[k]["chapter"],
                      int(key_inst[k].get("row", 0)), *k[:4], k[4])
               for k in keys]
    t0 = time.time()
    collected = collect_instances(
        stanzas, CHECKERS,
        workers={"A_pythainlp_5.0.1": args.workers,
                 "B_pythainlp_5.3.5": args.workers,
                 "D_klonpad_w2p": args.dw_workers,
                 "D_klonpad_ssg_fallback": args.workers})
    print(f"A/B/D/Dssg collected in {time.time()-t0:.1f}s", flush=True)

    per_inst = {name: [] for name, _c, _k in CHECKERS}
    for inst in aug:
        idx = keys.index(_augment_key(inst))
        for name, verdicts in collected.items():
            v = verdicts[idx]
            per_inst[name].append({
                "rule": inst["rule"], "gold": inst["gold"], "op": inst["op"],
                "pred": None if v["drop"] else v["rules"].get(inst["rule"]),
                "stanza_pred": None if v["drop"] else bool(v["stanza_ok"]),
            })

    # ---- Checker C (slow, tltk worker pool) ----
    if not args.skip_c:
        t0 = time.time()
        filler = stanzas[0]
        c_entries = collect_c_augment(aug, filler)
        print(f"C augment collected in {time.time()-t0:.1f}s", flush=True)
        for e, inst in zip(c_entries, aug):
            e["op"] = inst["op"]
        per_inst[C_NAME] = c_entries
    return per_inst


if __name__ == "__main__":
    main()
