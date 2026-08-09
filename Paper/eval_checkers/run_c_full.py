# -*- coding: utf-8 -*-
"""
Full-corpus runner for Checker C (Kongfha word_check via tltk G2P).

Improvements over the ad-hoc inline runs:
  * per-chunk progress output (units/s, elapsed, worker errors)
  * checkpointing to ``_c_chunks/chunk_<k>.jsonl`` so an interrupted run can be
    resumed by simply re-running (finished chunks are skipped)
  * **persistent worker pool** -- each tltk subprocess is long-lived, so tltk/
    gensim load once per worker and the per-wak G2P cache stays warm across the
    worker's whole share of the corpus (no per-chunk re-import)
  * parallel workers (--workers N; default 10) to compensate for tltk's slow
    single-threaded G2P

Usage:
    .venv\\Scripts\\python.exe Paper\\eval_checkers\\run_c_full.py [--workers 10]

Results are read back from the chunk files and aggregated into a per-story
gold-acceptance table (stanza_ok% + r1/r2/r3/rX) mirroring the A/B/D output.
"""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections import OrderedDict, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # eval_checkers
sys.path.insert(0, os.path.dirname(_HERE))    # Paper
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

from data_loading import load_stanzas  # noqa: E402
from eval_checkers import KongfhaChecker  # noqa: E402
from eval_checkers.common import RULES  # noqa: E402

CHECK_DIR = os.path.join(_HERE, "_c_chunks")
CH = 3000  # units per chunk


def build_units():
    """Return (units, meta): units as (id, [w1..w8]) row-pairs, meta aligned."""
    stanzas = load_stanzas()
    by_ch = OrderedDict()
    for s in stanzas:
        by_ch.setdefault((s.story, s.chapter), []).append(s)
    units, meta = [], []
    uid = 0
    for (story, _ch), rows in by_ch.items():
        for i in range(len(rows) - 1):
            r1, r2 = rows[i], rows[i + 1]
            units.append((str(uid), [r1.w1, r1.w2, r1.w3, r1.w4,
                                     r2.w1, r2.w2, r2.w3, r2.w4]))
            meta.append((story, i, i + 1))
            uid += 1
    return units, meta


class _PersistentWorker:
    """One long-lived tltk subprocess with a stdout reader thread.

    ``score(units)`` streams a batch to the worker's stdin and collects the
    results from the reader thread's queue. The process is reused for many
    batches, so its per-wak G2P cache (set up in ``kongfha_worker.py``) stays
    warm for the whole share of the corpus it is handed.
    """

    def __init__(self, python, worker_script, label):
        self._label = label
        self._err = []
        self._q = queue.Queue()
        self._proc = subprocess.Popen(
            [python, worker_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._rthread = threading.Thread(target=self._reader, daemon=True)
        self._rthread.start()
        self._ethread = threading.Thread(target=self._stderr_reader, daemon=True)
        self._ethread.start()

    def _reader(self):
        try:
            for line in self._proc.stdout:
                line = line.strip()
                if line:
                    self._q.put(json.loads(line))
        except Exception:
            pass

    def _stderr_reader(self):
        try:
            for line in self._proc.stderr:
                self._err.append(line)
        except Exception:
            pass

    def score(self, units):
        """Send ``units`` (list of (id, [w1..w8])) and return results in order."""
        payload = "\n".join(
            json.dumps({"id": i, "waks": w}, ensure_ascii=False) for i, w in units
        )
        self._proc.stdin.write(payload + "\n")
        self._proc.stdin.flush()
        results = []
        while len(results) < len(units):
            try:
                results.append(self._q.get(timeout=60))
            except queue.Empty:
                if self._proc.poll() is not None:
                    raise RuntimeError(
                        f"Kongfha worker [{self._label}] died:\n"
                        + "".join(self._err[-3000:])
                    )
        return results

    def close(self):
        try:
            self._proc.stdin.close()  # EOF -> worker exits cleanly
        except Exception:
            pass
        try:
            self._proc.wait(timeout=30)
        except Exception:
            self._proc.kill()


def process_chunk(pw, units, k, chunk_size=CH):
    """Score one chunk with a persistent worker, checkpoint it."""
    batch = units[k * chunk_size:(k + 1) * chunk_size]
    t = time.time()
    res = pw.score(batch)
    dt = time.time() - t
    fp = os.path.join(CHECK_DIR, f"chunk_{k:03d}.jsonl")
    with open(fp, "w", encoding="utf-8") as f:
        for r in res:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    we = sum(1 for r in res if (r.get("fail") or "").startswith("WorkerError"))
    return k, len(res), dt, we


def score_units_parallel(units, workers=10):
    """Score a list of 8-wak units with a pool of persistent tltk workers.

    ``units`` is a list of ``(id, [w1..w8])``. Results are returned in input
    order (ids are remapped internally to preserve order). Used for Checker C
    on the augmented instances (the gold corpus path reads checkpoints).
    """
    C = KongfhaChecker()
    n = len(units)
    k = max(1, min(workers, n))
    pws = [_PersistentWorker(C._python, C._worker, label=f"w{i}") for i in range(k)]
    batches = [[] for _ in range(k)]
    for idx, (_uid, waks) in enumerate(units):
        batches[idx % k].append((str(idx), waks))
    results_by_id = {}
    try:
        for i, pw in enumerate(pws):
            for r in pw.score(batches[i]):
                results_by_id[int(r["id"])] = r
    finally:
        for pw in pws:
            pw.close()
    return [results_by_id[i] for i in range(n)]


def aggregate(meta, nchunks):
    """Recompute per-story stats from the checkpoint files."""
    rows = []
    for k in range(nchunks):
        fp = os.path.join(CHECK_DIR, f"chunk_{k:03d}.jsonl")
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    Cst = defaultdict(lambda: {"n": 0, "pass": 0, "drop": 0,
                               "we": 0, "r_ok": defaultdict(int),
                               "r_n": defaultdict(int)})
    client = KongfhaChecker()
    for (story, _i, _j), res in zip(meta, rows):
        fail = res.get("fail")
        if fail and fail.startswith("WorkerError"):
            Cst[story]["we"] += 1
            Cst[story]["drop"] += 1
            continue
        bot1, bot2, inter, drop, _reason = client.build_pair(res)
        for bot in (bot1, bot2):
            st = Cst[story]
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
            Cst[story]["r_n"]["rX_inter"] += 1
            Cst[story]["r_ok"]["rX_inter"] += int(inter)
    return Cst


def fmt(st):
    rr = [f"{100 * st['r_ok'][rid] / max(1, st['r_n'][rid]):4.0f}"
          for rid in RULES]
    return (f"{100 * st['pass'] / st['n']:6.1f}%   "
            f"{'/'.join(rr)}  (n={st['n']}, drop={st['drop']}, we={st['we']})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10,
                    help="number of parallel tltk subprocesses "
                         "(each ~400 MB RAM; pick <= logical cores)")
    ap.add_argument("--chunk", type=int, default=CH)
    args = ap.parse_args()
    os.makedirs(CHECK_DIR, exist_ok=True)

    C = KongfhaChecker()
    units, meta = build_units()
    nchunks = (len(units) + args.chunk - 1) // args.chunk
    pending = [k for k in range(nchunks)
               if not os.path.exists(os.path.join(CHECK_DIR, f"chunk_{k:03d}.jsonl"))]
    done = nchunks - len(pending)
    t0 = time.time()
    print("Checker C (Kongfha) is the slow checker: tltk G2P is single-threaded "
          "pure-Python; expect minutes per chunk.", flush=True)
    print(f"total units={len(units)}  chunks={nchunks}  already-done={done}  "
          f"pending={len(pending)}  workers={args.workers}  "
          f"(RAM ~{args.workers * 0.42:.1f} GB)", flush=True)

    work = queue.Queue()
    for k in pending:
        work.put(k)

    _completed = [0]
    lock = threading.Lock()

    def worker_loop(wid):
        pw = _PersistentWorker(C._python, C._worker, label=f"w{wid}")
        while True:
            try:
                k = work.get_nowait()
            except queue.Empty:
                break
            try:
                kk, n, dt, we = process_chunk(pw, units, k)
            except Exception as e:
                pw.close()
                raise RuntimeError(f"worker {wid} failed on chunk {k}: {e}")
            with lock:
                _completed[0] += 1
                seq = _completed[0]
            print(f"[{done + seq}/{nchunks}] chunk {kk:03d} (w{wid}): {n} units "
                  f"in {dt:.1f}s ({n / dt:.0f} u/s) WE={we}  "
                  f"elapsed={time.time() - t0:.0f}s", flush=True)
        pw.close()

    nworkers = max(1, min(args.workers, len(pending))) if pending else 0
    threads = []
    for wid in range(nworkers):
        t = threading.Thread(target=worker_loop, args=(wid,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    if not pending:
        print("no pending chunks; all already completed.", flush=True)

    Cst = aggregate(meta, nchunks)
    print(f"\n{C.name}  (full corpus)")
    tot = {"n": 0, "pass": 0, "drop": 0, "we": 0,
           "r_ok": defaultdict(int), "r_n": defaultdict(int)}
    for story in sorted(Cst):
        st = Cst[story]
        for rid in RULES:
            tot["r_n"][rid] += st["r_n"][rid]
            tot["r_ok"][rid] += st["r_ok"][rid]
        tot["n"] += st["n"]
        tot["pass"] += st["pass"]
        tot["drop"] += st["drop"]
        tot["we"] += st["we"]
        print(f"  {story:<22} {fmt(st)}")
    print(f"  {'TOTAL':<22} {fmt(tot)}")


if __name__ == "__main__":
    main()
