# -*- coding: utf-8 -*-
"""
End-to-end evaluation harness for the Klon-8 checkers.

Collects per-instance verdicts for every checker over the gold corpus —
A/B/D_w2p/D_ssg directly (parallel), C from the ``run_c_full`` checkpoints —
then computes per-rule and per-stanza metrics (coverage, recall with 95%
Wilson confidence intervals, conservative drop-as-fail) and writes a metrics
JSON consumed by the report notebook.

The gold corpus is all-positive (every stanza rhymes after the
data-completeness fix), so this pass measures **recall**. Precision/F1 need the
augmented negatives (deferred); ``--negatives-json`` is the merge hook and the
metrics module already handles mixed 0/1 gold.

Consistency note: a stanza is OK iff EVERY applicable rule holds (r1/r2/r3,
plus rX when there is a previous stanza). For Checker C this is recomputed from
its per-rule scores, so C's stanza-level figure here includes rX (the earlier
consolidate table reported the bot-level 85.4% without rX).

Usage:
    .venv\\Scripts\\python.exe Paper\\eval_checkers\\eval_harness.py \\
        --workers 10 --dw-workers 4
"""
import argparse
import json
import os
import sys
import time
from collections import OrderedDict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # eval_checkers
sys.path.insert(0, os.path.dirname(_HERE))    # Paper
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

from data_loading import load_stanzas, Stanza  # noqa: E402
from eval_checkers import (  # noqa: E402
    OriginalKhaveeChecker, RuleBasedKhaveeChecker, KlonpadChecker,
    KlonpadSsgChecker, KongfhaChecker,
)
from eval_checkers.common import RULES  # noqa: E402
from eval_checkers.parallel_eval import collect_instances  # noqa: E402
from eval_checkers.run_c_full import (  # noqa: E402
    CHECK_DIR, build_units, score_units_parallel,
)
from eval_checkers import metrics as M  # noqa: E402

OUT = os.path.join(_HERE, "full_metrics.json")

CHECKERS = [
    ("A_pythainlp_5.0.1", OriginalKhaveeChecker, None),
    ("B_pythainlp_5.3.5", RuleBasedKhaveeChecker, None),
    ("D_klonpad_w2p", KlonpadChecker, {"fallback": "w2p"}),
    ("D_klonpad_ssg_fallback", KlonpadSsgChecker, None),
]

C_NAME = "C_kongfha_word_check"


def read_c_chunks(nchunks):
    rows = []
    for k in range(nchunks):
        fp = os.path.join(CHECK_DIR, f"chunk_{k:03d}.jsonl")
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def collect_c(stanzas):
    """Per-stanza C verdicts from the checkpoint files (aligned with stanzas)."""
    by_ch = OrderedDict()
    for s in stanzas:
        by_ch.setdefault((s.story, s.chapter), []).append(s)
    units, _meta = build_units()
    nchunks = (len(units) + 3000 - 1) // 3000
    rows = read_c_chunks(nchunks)
    client = KongfhaChecker()

    rec_map = {}
    idx = 0
    for (story, chapter), ch_rows in by_ch.items():
        prev_inter = None
        for i in range(len(ch_rows) - 1):
            res = rows[idx]
            idx += 1
            k1 = (story, chapter, i)
            k2 = (story, chapter, i + 1)
            if res.get("fail"):
                rec_map[k1] = {"drop": True}
                rec_map[k2] = {"drop": True}
                prev_inter = None
                continue
            bot1, bot2, inter, _drop, _reason = client.build_pair(res)
            rec_map[k1] = {"drop": False, "bot": bot1,
                           "rX": None if i == 0 else prev_inter}
            rec_map[k2] = {"drop": False, "bot": bot2, "rX": inter}
            prev_inter = inter

    out = []
    for s in stanzas:
        rec = rec_map[(s.story, s.chapter, s.row)]
        if rec["drop"]:
            out.append({"story": s.story, "chapter": s.chapter, "row": s.row,
                        "stanza_ok": None, "drop": True,
                        "rules": {rid: None for rid in RULES}})
            continue
        bot = rec["bot"]
        rules = {rid: bot.rules[rid] for rid in RULES}
        rules["rX_inter"] = rec["rX"]
        applicable = [rid for rid in RULES if rules[rid] is not None]
        ok = bool(applicable) and all(rules[rid] for rid in applicable)
        out.append({"story": s.story, "chapter": s.chapter, "row": s.row,
                    "stanza_ok": ok, "drop": False, "rules": rules})
    return out


def _metric_dict(golds, preds):
    return M.metrics(golds, preds)


def per_checker_gold(records, app_rx):
    """Compute per-story + total gold metrics for one checker's records.

    ``app_rx`` maps (story, chapter, row) -> whether rX applies.
    """
    stories = sorted({r["story"] for r in records})
    out = {"stanza": {}, "rules": {rid: {} for rid in RULES}}

    # --- stanza level (gold all 1) ---
    for story in stories:
        recs = [r for r in records if r["story"] == story]
        out["stanza"][story] = M.metrics(
            [1] * len(recs),
            [None if r["drop"] else bool(r["stanza_ok"]) for r in recs])
    out["stanza"]["TOTAL"] = M.metrics(
        [1] * len(records),
        [None if r["drop"] else bool(r["stanza_ok"]) for r in records])

    # --- per rule ---
    for rid in RULES:
        for story in stories:
            recs = [r for r in records if r["story"] == story]
            golds, preds = [], []
            for r in recs:
                if rid == "rX_inter" and not app_rx[(r["story"], r["chapter"], r["row"])]:
                    continue
                golds.append(1)
                preds.append(None if r["drop"] else r["rules"].get(rid))
            out["rules"][rid][story] = M.metrics(golds, preds)
        golds, preds = [], []
        for r in records:
            if rid == "rX_inter" and not app_rx[(r["story"], r["chapter"], r["row"])]:
                continue
            golds.append(1)
            preds.append(None if r["drop"] else r["rules"].get(rid))
        out["rules"][rid]["TOTAL"] = M.metrics(golds, preds)

    return out


def combine_with_gold(gold_md, extra_golds, extra_preds):
    """Append extra (gold, pred) instances to a gold TOTAL metric dict."""
    golds = [1] * gold_md["total"] + list(extra_golds)
    preds = ([None] * gold_md["dropped"] + [True] * gold_md["tp"]
             + [False] * (gold_md["fn"] + gold_md["fp"] + gold_md["tn"])
             + list(extra_preds))
    return M.metrics(golds, preds)


def _augment_key(inst):
    return (inst["w1"], inst["w2"], inst["w3"], inst["w4"], inst["prev_w4"])


def collect_augment(aug, workers, skip_c, filler):
    """Run all checkers on the augment stanzas.

    Returns ``{checker_name: [{"rule", "gold", "pred", "stanza_pred"}]}``
    aligned with ``aug`` (one entry per instance). Checker C is scored through
    the persistent tltk worker pool; a real gold stanza is used as the filler
    for the second half of each 8-wak unit.
    """
    key_inst = {_augment_key(i): i for i in aug}
    keys = list(key_inst)
    aug_stanzas = [
        Stanza(key_inst[k]["story"], key_inst[k]["chapter"],
               int(key_inst[k].get("row", 0)), *k[:4], k[4])
        for k in keys
    ]
    collected = collect_instances(aug_stanzas, CHECKERS, workers=workers)
    out = {name: [] for name, _c, _k in CHECKERS}
    for inst in aug:
        idx = keys.index(_augment_key(inst))
        for name, verdicts in collected.items():
            v = verdicts[idx]
            out[name].append({
                "rule": inst["rule"], "gold": inst["gold"],
                "pred": None if v["drop"] else v["rules"].get(inst["rule"]),
                "stanza_pred": None if v["drop"] else bool(v["stanza_ok"]),
            })
    if not skip_c:
        out[C_NAME] = collect_c_augment(aug, filler)
    return out


def collect_c_augment(aug, filler):
    """Checker C verdicts on augment instances (via the tltk worker)."""
    client = KongfhaChecker()
    units = []
    meta = []
    for i, inst in enumerate(aug):
        key = _augment_key(inst)
        waks = list(key[:4])
        if inst["rule"] == "rX_inter":
            # bot1.w4 = prev_w4 so C's cross link is exactly the rX pair
            bot1 = [filler.w1, filler.w2, filler.w3, inst["prev_w4"] or filler.w4]
            units.append((str(i), bot1 + waks))
        else:
            units.append((str(i), waks
                          + [filler.w1, filler.w2, filler.w3, filler.w4]))
        meta.append((i, inst["rule"]))
    results = score_units_parallel(units)
    out = []
    for (i, rule), res in zip(meta, results):
        inst = aug[i]
        if res.get("fail"):
            out.append({"rule": rule, "gold": inst["gold"], "pred": None,
                        "stanza_pred": None})
            continue
        bot1, bot2, inter, _d, _r = client.build_pair(res)
        if rule == "rX_inter":
            pred = inter
            stanza_pred = bool(bot2.stanza_ok) and bool(inter)
        else:
            pred = bot1.rules.get(rule) if bot1 else None
            stanza_pred = bool(bot1.stanza_ok) if bot1 else None
        out.append({"rule": rule, "gold": inst["gold"], "pred": pred,
                    "stanza_pred": stanza_pred})
    return out


def merge_augment(report, aug_preds):
    """Merge augment instances into every checker's gold metric totals."""
    for name, entries in aug_preds.items():
        if name not in report["checkers"]:
            continue
        ck = report["checkers"][name]
        for rid in RULES:
            sub = [e for e in entries if e["rule"] == rid]
            if sub:
                ck["rules"][rid]["TOTAL"] = combine_with_gold(
                    ck["rules"][rid]["TOTAL"],
                    [e["gold"] for e in sub], [e["pred"] for e in sub])
                ck["rules"][rid]["augment_n"] = len(sub)
        ck["stanza"]["TOTAL"] = combine_with_gold(
            ck["stanza"]["TOTAL"],
            [e["gold"] for e in entries],
            [e["stanza_pred"] for e in entries])
        ck["stanza"]["augment_n"] = len(entries)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel processes for A/B/D/Dssg (recommended 10)")
    ap.add_argument("--dw-workers", type=int, default=None,
                    help="worker count for D_w2p only (recommended 4)")
    ap.add_argument("--skip-c", action="store_true",
                    help="skip Checker C (no checkpoint files yet)")
    ap.add_argument("--out", default=OUT,
                    help=f"output metrics JSON path (default: {OUT})")
    ap.add_argument("--augment", default=None,
                    help="path to augment instances.json (from augment/corrupt.py) "
                         "to merge for precision/F1")
    args = ap.parse_args()

    t0 = time.time()
    stanzas = load_stanzas()
    app_rx = {(s.story, s.chapter, s.row): s.prev_w4 is not None for s in stanzas}

    if args.dw_workers is None:
        workers = args.workers
    else:
        workers = {name: (args.dw_workers if name == "D_klonpad_w2p"
                          else args.workers) for name, _c, _k in CHECKERS}

    print(f"collecting A/B/D/Dssg (workers={workers})...", flush=True)
    inst = collect_instances(stanzas, CHECKERS, workers=workers)
    if args.skip_c:
        print("skipping Checker C (--skip-c)", flush=True)
    else:
        print("reading Checker C from checkpoints...", flush=True)
        inst[C_NAME] = collect_c(stanzas)
    print(f"  collected in {time.time() - t0:.0f}s", flush=True)

    report = {
        "date": "2026-08-09",
        "gold": {
            "stanzas": len(stanzas),
            "waks": len(stanzas) * 4,
            "rule_instances": {
                "r1_w1_w2": len(stanzas),
                "r2_w2_w3": len(stanzas),
                "r3_w3_w4": len(stanzas),
                "rX_inter": sum(1 for s in stanzas if s.prev_w4 is not None),
            },
        },
        "checkers": {},
        "has_augment": args.augment is not None,
    }

    for name, records in inst.items():
        report["checkers"][name] = per_checker_gold(records, app_rx)

    if args.augment:
        with open(args.augment, encoding="utf-8") as f:
            aug = json.load(f)
        print(f"collecting augment verdicts ({len(aug)} instances)...", flush=True)
        filler = stanzas[0]
        aug_preds = collect_augment(aug, workers, args.skip_c, filler)
        print(f"  augment collected in {time.time() - t0:.0f}s", flush=True)
        merge_augment(report, aug_preds)
        print("merged augment (per-rule and stanza precision/F1)", flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"wrote {args.out}  ({time.time() - t0:.0f}s total)", flush=True)

    # console summary
    print("\n== stanza-level gold recall (95% CI) ==")
    print(f"{'checker':<28} {'recall':>8} {'CI':>22} {'cov':>6} {'n':>7}")
    for name, ck in report["checkers"].items():
        st = ck["stanza"]["TOTAL"]
        ci = st["recall_ci"]
        ci_s = f"[{ci[0]:.3f},{ci[1]:.3f}]" if ci else "–"
        print(f"{name:<28} {st['recall']:>7.1%} {ci_s:>22} "
              f"{st['coverage']:>5.1%} {st['total']:>7}")
    print("\n== per-rule gold recall ==")
    print(f"{'checker':<28} " + " ".join(f"{rid:>8}" for rid in RULES))
    for name, ck in report["checkers"].items():
        vals = " ".join(f"{ck['rules'][rid]['TOTAL']['recall'] or 0:>7.1%}"
                        for rid in RULES)
        print(f"{name:<28} {vals}")

    if report.get("has_augment"):
        print("\n== stanza-level precision / recall / F1 (gold + augment) ==")
        print(f"{'checker':<28} {'P':>7} {'R':>7} {'F1':>7} {'neg_n':>6}")
        for name, ck in report["checkers"].items():
            st = ck["stanza"]["TOTAL"]
            p = st["precision"] or 0
            r = st["recall"] or 0
            f1 = st["f1"] or 0
            print(f"{name:<28} {p:>6.1%} {r:>6.1%} {f1:>6.1%} "
                  f"{ck['stanza'].get('augment_n', 0):>6}")
        print("\n== per-rule precision / recall / F1 (gold + augment) ==")
        print(f"{'checker':<28} " + " ".join(f"{rid[:8]:>22}" for rid in RULES))
        for name, ck in report["checkers"].items():
            cells = []
            for rid in RULES:
                m = ck["rules"][rid]["TOTAL"]
                cells.append(f"{m['precision'] or 0:.1%}/{m['recall'] or 0:.1%}"
                             f"/{m['f1'] or 0:.1%}")
            print(f"{name:<28} " + " ".join(f"{c:>22}" for c in cells))


if __name__ == "__main__":
    main()
