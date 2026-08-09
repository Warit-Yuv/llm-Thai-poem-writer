# -*- coding: utf-8 -*-
"""
Checker C — Kongfha ``word_check`` (KlonSuphap-LM, tltk-G2P based).

The Kongfha method romanises each wak into syllables with ``tltk.nlp.g2p``,
reduces each syllable to its vowel-mattra string, and compares vowel-mattra
strings after long-to-short normalisation (``replace_long_short``). It operates
on an 8-wak unit (two 4-wak bots) and emits nine binary scores:

    bot1: สดับ-รับ, รับ-รอง, รับ-ส่ง, รอง-ส่ง
    bot2: สดับ-รับ, รับ-รอง, รับ-ส่ง, รอง-ส่ง
    cross: ส่ง1-รับ2   (Wak4 of bot1 vs Wak2 of bot2)

Mapping to the canonical rule set: r1 <- สดับ-รับ, r2 <- รับ-รอง,
r3 <- รอง-ส่ง, rX <- cross. The additional รับ-ส่ง rule has no canonical
analogue and is recorded only in ``meta`` (it is redundant given รับ-รอง and
รอง-ส่ง). Structural failures (fewer than 8 waks, G2P failure, or a wak with
fewer than 5 / more than 10 romanised syllables) are reported as ``dropped``.

Runtime: ``tltk`` (and its dependency ``gensim``) cannot be installed in the
project venv (Python 3.14 has no prebuilt ``gensim`` wheel), so romanisation and
scoring run in a subprocess under a separate interpreter that has ``tltk`` (the
global Python 3.12). See ``kongfha_worker.py``. Override the interpreter path
with the ``KONGFHA_PYTHON`` environment variable.

Methodological note (reported for transparency): the method compares
vowel-mattra strings only, so it does not compare the final consonant (matra),
and long/short vowel pairs are treated as equivalent.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import List, Optional, Tuple

from .common import CheckerResult, RULES

# Path to a Python interpreter with tltk installed (global Python 3.12 here).
DEFAULT_KONGFHA_PYTHON = (
    r"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
)


def _resolve_python() -> Optional[str]:
    env = os.environ.get("KONGFHA_PYTHON")
    if env:
        return env
    if os.path.exists(DEFAULT_KONGFHA_PYTHON):
        return DEFAULT_KONGFHA_PYTHON
    return None


def _bot_rules(score) -> dict:
    """Map one bot's 4 scores to canonical rules (score layout per bot:
    [สดับ-รับ, รับ-รอง, รับ-ส่ง, รอง-ส่ง])."""
    return {
        "r1_w1_w2": bool(score[0]),
        "r2_w2_w3": bool(score[1]),
        "r3_w3_w4": bool(score[3]),
        "rA_w2_w4": bool(score[2]),  # extra รับ-ส่ง rule (redundant; meta only)
    }


def _mk_result(checker: str, rules: dict, extra: bool) -> CheckerResult:
    canon = {r: rules.get(r) for r in RULES}
    na = tuple(r for r in RULES if canon[r] is None)
    ok = any(canon[r] is not None for r in RULES) and all(
        canon[r] for r in RULES if canon[r] is not None
    )
    return CheckerResult(
        checker=checker, stanza_ok=ok, rules=canon, na=na,
        meta={"extra_รับส่ง": extra},
    )


class KongfhaChecker:
    """Subprocess client for the Kongfha (KlonSuphap-LM) rhyme scorer."""

    name = "C_kongfha_word_check"

    def __init__(self, python_path: Optional[str] = None) -> None:
        self._python = python_path or _resolve_python()
        here = os.path.dirname(os.path.abspath(__file__))
        self._worker = os.path.join(here, "kongfha_worker.py")

    def score_units(self, units: List[Tuple[str, List[str]]]) -> List[dict]:
        """Score 8-wak units in a single subprocess call.

        ``units`` is a list of ``(id, [w1..w8])``. Returns one dict per unit
        with keys ``id``, ``fail`` (str or None) and, when not failed,
        ``score``/``repli`` (lists of nine ints).
        """
        if self._python is None:
            raise RuntimeError(
                "Checker C needs a Python interpreter with tltk installed. "
                "Set the KONGFHA_PYTHON environment variable to its path."
            )
        payload = "\n".join(
            json.dumps({"id": i, "waks": w}, ensure_ascii=False) for i, w in units
        )
        proc = subprocess.run(
            [self._python, self._worker],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if proc.returncode != 0:
            raise RuntimeError("Kongfha worker failed:\n" + proc.stderr[-3000:])
        out = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def build_pair(self, res: dict):
        """Map one worker result (an 8-wak unit) to per-stanza results.

        Returns ``(bot1, bot2, inter_ok, dropped, drop_reason)`` where
        ``bot1``/``bot2`` are :class:`CheckerResult` for the first/second 4-wak
        stanza and ``inter_ok`` is the cross (ส่ง1-รับ2) rhyme outcome.
        """
        if res.get("fail"):
            return None, None, None, True, res["fail"]
        score = res["score"]
        bot1 = _mk_result(self.name, _bot_rules(score[0:4]), bool(score[2]))
        bot2 = _mk_result(self.name, _bot_rules(score[4:8]), bool(score[6]))
        return bot1, bot2, bool(score[8]), False, ""
