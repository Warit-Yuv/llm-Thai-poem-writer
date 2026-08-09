# -*- coding: utf-8 -*-
"""
Checker B — Rule-based PyThaiNLP ``check_klon`` (pythainlp 5.3.5).

This module reproduces the rule-based ``check_klon`` that shipped in pythainlp
5.3.5 (the release that merged the improved KhaveeVerifier). The vendored
class :class:`_dev_core.KhaveeVerifier` is a verbatim copy of
``pythainlp/khavee/core.py`` from the project venv (5.3.5), including its
improved ``is_sumpus`` (สระเกิน normalisation). Syllable segmentation uses
``subword_tokenize(engine="ssg")``.

Rule set (as implemented in 5.3.5 ``check_klon``, ``k_type=8``):

    r1_w1_w2 : Wak1[-1] rhymes with any of Wak2[:5]
    r2_w2_w3 : Wak2[-1] rhymes with Wak3[-1]
    r3_w3_w4 : Wak3[-1] rhymes with any of Wak4[:5]
    rX_inter : Wak4[-1] (previous stanza) rhymes with Wak2[-1] (current)
"""
from __future__ import annotations

from typing import Optional

from pythainlp.tokenize import subword_tokenize

from . import _dev_core
from .common import CheckerResult, RULES


class RuleBasedKhaveeChecker:
    """Instrumented reproduction of the pythainlp 5.3.5 rule-based checker."""

    name = "B_pythainlp_5.3.5"

    def __init__(self) -> None:
        self._kv = _dev_core.KhaveeVerifier()

    def _syl(self, wak: str):
        try:
            return subword_tokenize(wak, engine="ssg")
        except Exception:
            return []

    def check_stanza(self, w1, w2, w3, w4, prev_w4: Optional[str] = None) -> CheckerResult:
        try:
            s1, s2, s3, s4 = (self._syl(w) for w in (w1, w2, w3, w4))
            rules = {r: None for r in RULES}
            meta = {
                "tokenizer": "ssg",
                "syllables": {"w1": s1, "w2": s2, "w3": s3, "w4": s4},
                "word_counts": [len(s1), len(s2), len(s3), len(s4)],
            }

            # r1: วรรคสดับ -> วรรครับ (Wak1 last vs any of Wak2[:5])
            rules["r1_w1_w2"] = bool(
                s1 and s2 and any(self._kv.is_sumpus(s1[-1], t) for t in s2[:5])
            )
            # r2: วรรครับ -> วรรครอง
            rules["r2_w2_w3"] = bool(s2 and s3 and self._kv.is_sumpus(s2[-1], s3[-1]))
            # r3: วรรครอง -> วรรคส่ง (Wak3 last vs any of Wak4[:5])
            rules["r3_w3_w4"] = bool(
                s3 and s4 and any(self._kv.is_sumpus(s3[-1], t) for t in s4[:5])
            )
            # rX: inter-stanza (previous Wak4 last vs current Wak2 last)
            if prev_w4 is not None:
                sp = self._syl(prev_w4)
                rules["rX_inter"] = bool(s2 and sp and self._kv.is_sumpus(sp[-1], s2[-1]))
            else:
                rules["rX_inter"] = None

            na = tuple(r for r in RULES if rules[r] is None)
            ok = any(rules[r] is not None for r in RULES) and all(
                rules[r] for r in RULES if rules[r] is not None
            )
            return CheckerResult(checker=self.name, stanza_ok=ok, rules=rules, na=na, meta=meta)
        except Exception as e:
            # The 5.3.5 check_klon bails (returns a generic error) on any crash.
            return CheckerResult(
                checker=self.name, stanza_ok=False,
                rules={r: None for r in RULES}, na=RULES,
                dropped=True, drop_reason=f"is_sumpus error: {e}", meta={},
            )
