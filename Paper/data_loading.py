# -*- coding: utf-8 -*-
"""
Loader for the gold-standard evaluation set (``Results/Evaluate``).

Each CSV row is one stanza (บท) of four waks (``w1..w4``). Chapters are
processed independently (file-by-file): the inter-stanza rule is evaluated only
between consecutive rows *within* a chapter. Consequently the first row of each
chapter has ``prev_w4 = None`` (inter-stanza rule not applicable), and the last
row of each chapter has no successor (its Wak-4 has no outgoing link to check).

The loader returns a list of :class:`Stanza` records together with a
per-story/per-chapter index so downstream code can reproduce the exact
gold-positive instance counts.
"""
from __future__ import annotations

import csv
import glob
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVALUATE_DIR = os.path.join(ROOT, "Results", "Evaluate")

WAK_COLS = ("w1", "w2", "w3", "w4")


@dataclass
class Stanza:
    """One stanza (บท) with bookkeeping for the inter-stanza rule."""

    story: str
    chapter: str            # basename of the source file, e.g. "phraAphai_1"
    row: int                # 0-based index within the chapter
    w1: str
    w2: str
    w3: str
    w4: str
    prev_w4: Optional[str]  # Wak4 of the previous row, or None for row 0

    def waks(self) -> List[str]:
        return [self.w1, self.w2, self.w3, self.w4]


def _chapter_num(name: str) -> int:
    # Operate on the basename: the full path may contain digits in unrelated
    # directory names (e.g. "SIIT_Year_4"), which would silently break the
    # numeric chapter ordering (stable sort then keeps lexicographic order,
    # e.g. khobut_10..khobut_14, khobut_1..khobut_9).
    m = re.search(r"(\d+)", os.path.basename(name))
    return int(m.group(1)) if m else 0


def chapters_by_story(evaluate_dir: str = EVALUATE_DIR) -> Dict[str, List[str]]:
    """Map story name -> sorted list of chapter CSV paths (numeric order)."""
    stories: Dict[str, List[str]] = {}
    for fp in sorted(glob.glob(os.path.join(evaluate_dir, "*", "*_ok.csv"))):
        story = os.path.basename(os.path.dirname(fp))
        stories.setdefault(story, []).append(fp)
    for story in stories:
        stories[story].sort(key=_chapter_num)
    return stories


def load_stanzas(evaluate_dir: str = EVALUATE_DIR) -> List[Stanza]:
    """Load all stanzas from ``Results/Evaluate`` (file-by-file)."""
    stanzas: List[Stanza] = []
    for story, files in chapters_by_story(evaluate_dir).items():
        for fp in files:
            chapter = os.path.basename(fp).replace("_ok.csv", "")
            with open(fp, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            for i, row in enumerate(rows):
                w = [row[c].strip() for c in WAK_COLS]
                prev = None if i == 0 else rows[i - 1]["w4"].strip()
                stanzas.append(Stanza(story, chapter, i, *w, prev))
    return stanzas


def summary(stanzas: Optional[List[Stanza]] = None) -> Dict[str, Tuple[int, int]]:
    """Return ``{story: (n_stanzas, n_waks)}`` for reporting."""
    if stanzas is None:
        stanzas = load_stanzas()
    out: Dict[str, Tuple[int, int]] = {}
    for s in stanzas:
        n, w = out.get(s.story, (0, 0))
        out[s.story] = (n + 1, w + 4)
    return out
