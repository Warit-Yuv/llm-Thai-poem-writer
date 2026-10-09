# -*- coding: utf-8 -*-
"""Partial recovery of Checker C chunks after the transcription-gap patch.

The gap patch changed only phraAphai_22 / phraAphai_31 (512 of 36,283 units).
Every other unit's 8 waks are byte-identical to the pre-patch run, so its
cached result is still valid. This script:

  1. reads the PRE-PATCH chunks (backup) and maps unit content -> result
  2. builds the NEW unit list
  3. reuses the cached result for every unchanged unit
  4. re-scores ONLY the changed units (via the tltk worker pool)
  5. writes the 13 new chunk files in the new order

Run with KONGFHA_PYTHON pointing at the tltk interpreter (.venv312).
"""
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))

from eval_checkers import KongfhaChecker  # noqa: E402
from eval_checkers.run_c_full import build_units, CHECK_DIR, CH  # noqa: E402

BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(_HERE)), "backups", "eval_pre_gap_patch",
    "_c_chunks")


def _key(waks):
    return "\x1f".join(waks)


def score_oneshot(units):
    """Score ``units`` (list of (id, [w1..w8])) with ONE worker subprocess.

    The persistent-pool path (``score_units_parallel``) intermittently stalls
    idle in this environment; a single one-shot subprocess fed the whole batch
    on stdin is reliable and fast enough for the ~275-unit re-score. Results
    are returned keyed by id.
    """
    C = KongfhaChecker()
    payload = "\n".join(
        json.dumps({"id": i, "waks": w}, ensure_ascii=False) for i, w in units
    ) + "\n"
    p = subprocess.run([C._python, C._worker], input=payload,
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=1800)
    if p.returncode != 0:
        raise RuntimeError(f"worker failed ({p.returncode}):\n{p.stderr[-2000:]}")
    out = {}
    for line in p.stdout.splitlines():
        line = line.strip()
        if line:
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


def load_backup_map():
    """{unit content key: result dict} from the pre-patch chunks."""
    out = {}
    for fn in sorted(os.listdir(BACKUP_DIR)):
        if not fn.endswith(".jsonl"):
            continue
        with open(os.path.join(BACKUP_DIR, fn), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                out[rec["id"]] = rec  # id is the unit index in the OLD list
    return out


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    # Old units (pre-patch) — rebuild from the backup CSVs so ids align.
    import shutil
    import tempfile
    from data_loading import load_stanzas
    from collections import OrderedDict

    def units_from(evaluate_dir):
        stanzas = load_stanzas(evaluate_dir)
        by_ch = OrderedDict()
        for s in stanzas:
            by_ch.setdefault((s.story, s.chapter), []).append(s)
        out = []
        for (story, chapter), rows in by_ch.items():
            for i in range(len(rows) - 1):
                r1, r2 = rows[i], rows[i + 1]
                out.append([r1.w1, r1.w2, r1.w3, r1.w4,
                            r2.w1, r2.w2, r2.w3, r2.w4])
        return out

    with tempfile.TemporaryDirectory() as td:
        shutil.copytree("Results/Evaluate", td, dirs_exist_ok=True)
        for stem in ("phraAphai_22", "phraAphai_31"):
            shutil.copy(f"backups/eval_pre_gap_patch/{stem}_ok.csv",
                        os.path.join(td, "phraAphai", f"{stem}_ok.csv"))
        old_units = units_from(td)

    backup = load_backup_map()
    assert len(backup) == len(old_units), (len(backup), len(old_units))
    cache = {_key(old_units[int(i)]): backup[i] for i in backup}

    new_units, _meta = build_units()
    new_waks = [w for _uid, w in new_units]
    print(f"old units={len(old_units)}  new units={len(new_waks)}  "
          f"cached={len(cache)}", flush=True)

    missing = [i for i, w in enumerate(new_waks) if _key(w) not in cache]
    print(f"units needing re-score: {len(missing)}", flush=True)

    fresh = {}
    if missing:
        t = time.time()
        batch = [(str(i), new_waks[i]) for i in missing]
        print(f"scoring {len(batch)} units (one-shot worker)...", flush=True)
        scored = score_oneshot(batch)
        for i in missing:
            fresh[i] = scored[str(i)]
        print(f"re-scored {len(missing)} units in {time.time() - t:.1f}s",
              flush=True)
        assert len(fresh) == len(missing), (len(fresh), len(missing))

    # Write the new chunks in order.
    os.makedirs(CHECK_DIR, exist_ok=True)
    nchunks = (len(new_waks) + CH - 1) // CH
    for k in range(nchunks):
        fp = os.path.join(CHECK_DIR, f"chunk_{k:03d}.jsonl")
        with open(fp, "w", encoding="utf-8") as fh:
            for i in range(k * CH, min((k + 1) * CH, len(new_waks))):
                if i in fresh:
                    rec = fresh[i]
                else:
                    rec = dict(cache[_key(new_waks[i])])
                rec = dict(rec)
                rec["id"] = str(i)          # re-id to the NEW position
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"wrote {nchunks} chunks to {CHECK_DIR}", flush=True)


if __name__ == "__main__":
    main()
