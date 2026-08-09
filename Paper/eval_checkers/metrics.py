# -*- coding: utf-8 -*-
"""
Confusion-matrix metrics for the Klon-8 rhyme-detection evaluation.

Definitions
-----------
* A checker emits a verdict (``True``/``False``) per instance — either a rhyme
  rule (r1/r2/r3/rX) or a whole stanza — or it *drops* the instance (no
  verdict: e.g. Checker C's WordFail/LengthFail, or Checker A's crash guard).
* The gold corpus is entirely positive (every stanza rhymes after the
  data-completeness fix), so the gold pass measures **recall**. Precision
  comes from the augmented negatives (deferred; the plumbing is in place).
* ``coverage`` = share of instances with a verdict; metrics are computed on the
  evaluated subset. A **conservative** variant counts drops as false
  predictions (false negative for recall, false positive for precision).

Confidence intervals use the Wilson score interval (95% by default).
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence

Gold = Sequence[bool]
Pred = Sequence[Optional[bool]]  # None = dropped (no verdict)


def wilson_ci(k: int, n: int, z: float = 1.96) -> Optional[tuple]:
    """Wilson score interval for a proportion ``k/n``; ``None`` if ``n <= 0``."""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (round(centre - half, 6), round(centre + half, 6))


def confusion(golds: Gold, preds: Pred):
    """Return ``(tp, fp, fn, tn, evaluated, dropped)``.

    ``None`` predictions are dropped (excluded from the confusion).
    """
    tp = fp = fn = tn = evaluated = dropped = 0
    for g, p in zip(golds, preds):
        if p is None:
            dropped += 1
            continue
        evaluated += 1
        if g:
            tp += int(bool(p))
            fn += int(not p)
        else:
            fp += int(bool(p))
            tn += int(not p)
    return tp, fp, fn, tn, evaluated, dropped


def _safe(a: int, b: int) -> Optional[float]:
    return round(a / b, 6) if b else None


def metrics(golds: Gold, preds: Pred) -> dict:
    """Full metric set for one (gold, predictions) pair.

    Returns: ``tp/fp/fn/tn``, ``evaluated/dropped/total``, ``coverage``,
    ``accuracy/precision/recall/f1`` (evaluated subset), ``recall_ci`` /
    ``precision_ci`` (Wilson 95%), and a ``conservative`` dict where drops
    count as false (recall/precision/f1).
    """
    tp, fp, fn, tn, evaluated, dropped = confusion(golds, preds)
    total = evaluated + dropped

    precision = _safe(tp, tp + fp)
    recall = _safe(tp, tp + fn)
    accuracy = _safe(tp + tn, evaluated)
    f1 = (round(2 * precision * recall / (precision + recall), 6)
          if precision and recall else None)

    # conservative: drops -> false positives (precision) / false negatives (recall)
    prec_c = _safe(tp, tp + fp + dropped)
    rec_c = _safe(tp, tp + fn + dropped)
    f1_c = (round(2 * prec_c * rec_c / (prec_c + rec_c), 6)
            if prec_c and rec_c else None)

    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "evaluated": evaluated, "dropped": dropped, "total": total,
        "coverage": _safe(evaluated, total),
        "accuracy": accuracy,
        "precision": precision, "precision_ci": wilson_ci(tp, tp + fp),
        "recall": recall, "recall_ci": wilson_ci(tp, tp + fn),
        "f1": f1,
        "conservative": {"precision": prec_c, "recall": rec_c, "f1": f1_c},
    }


def summarise(instances: List[dict], key: str) -> dict:
    """Collapse per-instance records into one :func:`metrics` result.

    ``instances`` are dicts with ``gold`` (bool) and ``pred`` (bool or None).
    ``key`` is a label for the returned dict (e.g. the checker name).
    """
    golds = [i["gold"] for i in instances]
    preds = [i["pred"] for i in instances]
    m = metrics(golds, preds)
    m["key"] = key
    m["n_instances"] = len(instances)
    return m
