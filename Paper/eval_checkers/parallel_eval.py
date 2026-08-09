# -*- coding: utf-8 -*-
"""
Parallel evaluation of the instrumented checkers over the gold corpus.

The A/B/D(+Dssg) eval loops are ~100% parallelizable pure CPU (ssg CRF, newmm,
w2p are all single-threaded), and the one-time per-process overhead is tiny
(measured ~0.44 s: imports + data load + ssg model + override trie + w2p). So a
``--workers N`` flag turns the ~95 s sequential A/B/D/Dssg run into ~10-15 s.

Each worker process instantiates its own checker (building its own cheap trie /
caches) and evaluates a contiguous slice of stanzas; workers return compact
plain-dict per-story aggregates (no heavy objects are pickled back).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # eval_checkers
sys.path.insert(0, os.path.dirname(_HERE))    # Paper
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

from eval_checkers.common import RULES  # noqa: E402

# The w2p engine (pythainlp.transliterate.pronunciate engine="w2p") is a
# pure-numpy GRU RNN: its np.matmul calls make numpy/OpenBLAS spawn a thread
# pool PER PROCESS. Running N checker processes then oversubscribes the cores
# (measured: D_w2p got *slower* at 10 workers: 35.6 -> 30.2 s). Capping BLAS
# threads to 1 per process restores clean process-level scaling. Applied only
# in the parallel path, before the pool is created (children inherit os.environ
# before their numpy import).
_BLAS_THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


def _eval_slice(task):
    """Evaluate one stanza slice with one checker; return plain per-story dicts.

    ``task`` = (name, checker_class, kwargs, stanza_slice). Top-level function so
    it can be pickled for Windows multiprocessing (spawn).
    """
    _name, cls, kwargs, slice_stanzas = task
    ck = cls(**(kwargs or {}))
    per = {}
    for s in slice_stanzas:
        r = ck.check_stanza(s.w1, s.w2, s.w3, s.w4, prev_w4=s.prev_w4)
        st = per.setdefault(s.story,
                            {"n": 0, "pass": 0, "drop": 0, "we": 0,
                             "r_ok": {}, "r_n": {}})
        if r.dropped:
            st["drop"] += 1
            continue
        st["n"] += 1
        st["pass"] += int(r.stanza_ok)
        for rid in RULES:
            v = r.rules.get(rid)
            if v is not None:
                st["r_n"][rid] = st["r_n"].get(rid, 0) + 1
                st["r_ok"][rid] = st["r_ok"].get(rid, 0) + int(v)
    return per


def _plan_tasks(checkers, workers, stanzas):
    """Return ``(counts, pool_size, tasks)`` for the checker runs.

    ``counts`` maps checker name -> its worker count; ``pool_size`` is the pool
    to create (max of the counts); ``tasks`` is the flat list of
    ``(name, cls, kwargs, stanza_slice)`` tasks to submit.
    """
    if isinstance(workers, dict):
        counts = workers
        pool_size = max(counts.values()) if counts else 1
    else:
        counts = {name: workers for name, _cls, _kw in checkers}
        pool_size = workers

    n = len(stanzas)
    tasks = []
    for name, cls, kwargs in checkers:
        w = min(max(counts.get(name, 1), 1), max(n, 1))
        base, rem = divmod(n, w)
        idx = 0
        for i in range(w):
            sz = base + (1 if i < rem else 0)
            tasks.append((name, cls, kwargs, stanzas[idx:idx + sz]))
            idx += sz
    return counts, pool_size, tasks


def _map_tasks(tasks, pool_size):
    """Evaluate tasks, sequentially or via a Pool (Windows spawn-safe)."""
    if pool_size <= 1:
        return [_eval_slice(t) for t in tasks]
    # limit BLAS/numpy threads in the worker processes (see _BLAS_THREAD_ENV)
    for key, val in _BLAS_THREAD_ENV.items():
        os.environ.setdefault(key, val)
    from multiprocessing import Pool

    with Pool(processes=pool_size) as pool:
        return pool.map(_eval_slice, tasks)  # order preserved


def run_checkers(stanzas, checkers, workers=1):
    """Run ``checkers`` over ``stanzas`` and return per-story aggregates.

    ``checkers`` is a list of ``(name, checker_class, kwargs)``, e.g.
    ``("B_pythainlp_5.3.5", RuleBasedKhaveeChecker, None)``. The checker classes
    must be importable by qualified name (they are pickled by reference).

    ``workers`` is either an int (applied to every checker) or a dict
    ``{checker_name: workers}`` for per-checker counts. Per-checker counts let
    you cap a checker that does not scale (D_w2p's numpy-GRU w2p is fastest at
    ~4 workers) while letting the others use more cores.

    Returns ``{name: {story: {"n","pass","drop","we","r_ok","r_n"}}}`` with
    plain dicts (safe to serialize / merge).
    """
    _counts, pool_size, tasks = _plan_tasks(checkers, workers, stanzas)
    raw = _map_tasks(tasks, pool_size)

    out = {name: {} for name, _cls, _kw in checkers}
    for (name, _cls, _kw, _sl), per in zip(tasks, raw):
        for story, st in per.items():
            tgt = out[name].setdefault(
                story, {"n": 0, "pass": 0, "drop": 0, "we": 0,
                        "r_ok": {}, "r_n": {}})
            tgt["n"] += st["n"]
            tgt["pass"] += st["pass"]
            tgt["drop"] += st["drop"]
            tgt["we"] += st["we"]
            for rid in st["r_n"]:
                tgt["r_n"][rid] = tgt["r_n"].get(rid, 0) + st["r_n"][rid]
                tgt["r_ok"][rid] = tgt["r_ok"].get(rid, 0) + st["r_ok"][rid]
    return out


def _collect_slice(task):
    """Per-instance variant of :func:`_eval_slice` (same task format)."""
    _name, cls, kwargs, slice_stanzas = task
    ck = cls(**(kwargs or {}))
    out = []
    for s in slice_stanzas:
        r = ck.check_stanza(s.w1, s.w2, s.w3, s.w4, prev_w4=s.prev_w4)
        out.append({
            "story": s.story, "chapter": s.chapter, "row": s.row,
            "stanza_ok": bool(r.stanza_ok), "drop": bool(r.dropped),
            "rules": {rid: (None if r.rules.get(rid) is None
                            else bool(r.rules[rid])) for rid in RULES},
        })
    return out


def collect_instances(stanzas, checkers, workers=1):
    """Like :func:`run_checkers` but returns per-instance verdicts.

    Returns ``{name: [ {story, chapter, row, stanza_ok, drop, rules} ... ]}``
    with one entry per stanza, in the same order as ``stanzas``. This keeps the
    raw data needed for confusion metrics and error analysis (the aggregate
    path only keeps counts).
    """
    _counts, pool_size, tasks = _plan_tasks(checkers, workers, stanzas)
    if pool_size <= 1:
        raw = [_collect_slice(t) for t in tasks]
    else:
        for key, val in _BLAS_THREAD_ENV.items():
            os.environ.setdefault(key, val)
        from multiprocessing import Pool

        with Pool(processes=pool_size) as pool:
            raw = pool.map(_collect_slice, tasks)
    out = {name: [] for name, _cls, _kw in checkers}
    for (name, _cls, _kw, _sl), lst in zip(tasks, raw):
        out[name].extend(lst)
    return out
