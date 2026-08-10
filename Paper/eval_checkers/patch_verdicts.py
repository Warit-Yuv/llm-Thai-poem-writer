# -*- coding: utf-8 -*-
"""Incrementally patch the cached augment verdicts after a small regeneration.

Compares the OLD instances (backup) with the NEW ones, re-scores only the
changed instances (A/B/D/Dssg directly, Checker C through the tltk worker
pool on just the changed subset), and writes an updated augment_verdicts.json
aligned with the NEW instance order.

Usage:
    .venv\\Scripts\\python.exe Paper\\eval_checkers\\patch_verdicts.py \\
        --old-instances OLD.json --new-instances NEW.json \\
        --old-verdicts OLD_VERD.json --out NEW_VERD.json
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

from data_loading import Stanza  # noqa: E402
from eval_checkers.eval_harness import (  # noqa: E402
    CHECKERS, C_NAME, collect_instances, collect_c_augment,
)

DEFAULT_AUG = os.path.join(os.path.dirname(_HERE), "augment", "output",
                           "instances.json")
DEFAULT_VERD = os.path.join(os.path.dirname(_HERE), "report",
                            "augment_verdicts.json")


def _key(i):
    return (i["w1"], i["w2"], i["w3"], i["w4"], i["prev_w4"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--old-instances",
        default=r"C:\Users\User\AppData\Local\Temp\instances_v56.json")
    ap.add_argument("--new-instances", default=DEFAULT_AUG)
    ap.add_argument(
        "--old-verdicts",
        default=r"C:\Users\User\AppData\Local\Temp\verdicts_v56.json")
    ap.add_argument("--out", default=DEFAULT_VERD)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--dw-workers", type=int, default=4)
    args = ap.parse_args()

    old_inst = json.load(open(args.old_instances, encoding="utf-8"))
    new_inst = json.load(open(args.new_instances, encoding="utf-8"))
    old_verd = json.load(open(args.old_verdicts, encoding="utf-8"))
    print(f"old={len(old_inst)} new={len(new_inst)}")

    # ---- find changed indices (by content, index-aligned) ----
    changed = [i for i in range(len(new_inst))
               if i >= len(old_inst) or _key(old_inst[i]) != _key(new_inst[i])
               or old_inst[i]["rule"] != new_inst[i]["rule"]]
    print(f"changed instances: {len(changed)}")
    for i in changed[:30]:
        o = old_inst[i] if i < len(old_inst) else None
        n = new_inst[i]
        print(f"  [{i}] old={o and o['candidate']}->{o and o['id']}  "
              f"new={n['candidate']}->{n['id']}")
    if not changed:
        print("no changes; keeping verdicts as-is")
        json.dump(old_verd, open(args.out, "w", encoding="utf-8"),
                  ensure_ascii=False)
        return

    # ---- re-score the changed subset ----
    sub = [new_inst[i] for i in changed]
    stanzas = [Stanza(s["story"], s["chapter"], int(s.get("row", 0)),
                      s["w1"], s["w2"], s["w3"], s["w4"], s["prev_w4"])
               for s in sub]
    t0 = time.time()
    collected = collect_instances(
        stanzas, CHECKERS,
        workers={"A_pythainlp_5.0.1": args.workers,
                 "B_pythainlp_5.3.5": args.workers,
                 "D_klonpad_w2p": args.dw_workers,
                 "D_klonpad_ssg_fallback": args.workers})
    print(f"A/B/D/Dssg re-scored {len(sub)} in "
          f"{time.time()-t0:.1f}s", flush=True)

    c_entries = collect_c_augment(sub, stanzas[0])
    print(f"C re-scored {len(sub)} in {time.time()-t0:.1f}s", flush=True)

    # ---- patch verdicts ----
    new_verd = json.loads(json.dumps(old_verd))  # deep copy
    for cname in new_verd:
        if len(new_verd[cname]) != len(new_inst):
            print(f"WARN: {cname} verdicts length {len(new_verd[cname])} "
                  f"!= instances {len(new_inst)}")
    for cname, verdicts in collected.items():
        for idx, e in zip(changed, verdicts):
            new_verd[cname][idx] = {
                "rule": new_inst[idx]["rule"],
                "gold": new_inst[idx]["gold"],
                "op": new_inst[idx]["op"],
                "pred": None if e["drop"] else e["rules"].get(
                    new_inst[idx]["rule"]),
                "stanza_pred": None if e["drop"] else bool(e["stanza_ok"]),
            }
    for idx, e in zip(changed, c_entries):
        new_verd[C_NAME][idx] = e
        new_verd[C_NAME][idx]["op"] = new_inst[idx]["op"]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(new_verd, f, ensure_ascii=False)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
