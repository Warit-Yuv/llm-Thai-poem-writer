# -*- coding: utf-8 -*-
"""Refresh the merged (gold + augment) TOTAL sections of full_metrics.json
from the CURRENT augment verdicts, without re-running any checker.

The gold per-story sections are already current (the corpus did not change);
only the merged TOTAL keys need rebuilding from the v5.7 verdicts.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from eval_checkers import metrics as M  # noqa: E402
from eval_checkers.common import RULES  # noqa: E402

METRICS = os.path.join(_HERE, "full_metrics.json")
VERD = os.path.join(os.path.dirname(_HERE), "report", "augment_verdicts.json")


def _safe(a, b):
    return round(a / b, 6) if b else None


def combine(gold_md, golds, preds):
    """Same semantics as eval_harness.combine_with_gold."""
    golds_all = [1] * gold_md["total"] + list(golds)
    preds_all = ([None] * gold_md["dropped"] + [True] * gold_md["tp"]
                 + [False] * (gold_md["fn"] + gold_md["fp"] + gold_md["tn"])
                 + list(preds))
    return M.metrics(golds_all, preds_all)


def main() -> None:
    metrics = json.load(open(METRICS, encoding="utf-8"))
    verdicts = json.load(open(VERD, encoding="utf-8"))

    for cname, ck in metrics["checkers"].items():
        entries = verdicts[cname]
        # gold-only TOTAL from per-story sections (current)
        stories = [s for s, v in ck["stanza"].items()
                   if isinstance(v, dict) and s != "TOTAL"]
        g_tot = {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "dropped": 0}
        for s in stories:
            for k in g_tot:
                g_tot[k] += ck["stanza"][s].get(k, 0)
        g_tot["total"] = (g_tot["tp"] + g_tot["fp"] + g_tot["fn"]
                           + g_tot["tn"] + g_tot["dropped"])
        # rebuild merged stanza TOTAL
        ck["stanza"]["TOTAL"] = combine(
            g_tot, [e["gold"] for e in entries],
            [e["stanza_pred"] for e in entries])
        ck["stanza"]["augment_n"] = len(entries)
        # per-rule merged TOTAL
        for rid in RULES:
            r = ck["rules"][rid]
            g = {"tp": 0, "fp": 0, "fn": 0, "tn": 0, "dropped": 0}
            for s in stories:
                if isinstance(r.get(s), dict):
                    for k in g:
                        g[k] += r[s].get(k, 0)
            g["total"] = (g["tp"] + g["fp"] + g["fn"]
                           + g["tn"] + g["dropped"])
            sub = [e for e in entries if e["rule"] == rid]
            r["TOTAL"] = combine(
                g, [e["gold"] for e in sub],
                [e["pred"] for e in sub]) if sub else {"total": 0}
            r["augment_n"] = len(sub)

    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1)
    print("refreshed", METRICS)

    # quick summary
    for cname, ck in metrics["checkers"].items():
        s = ck["stanza"]["TOTAL"]
        print(f"  {cname:28s} merged P={s['precision']} R={s['recall']} "
              f"F1={s['f1']} n={s['total']}")


if __name__ == "__main__":
    main()
