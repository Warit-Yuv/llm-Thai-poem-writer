# -*- coding: utf-8 -*-
"""
Checker A — Original PyThaiNLP ``check_klon`` (pythainlp 5.0.1).

This module reproduces the original implementation's underlying logic while
instrumenting each rhyme rule so that every checked syllable pair is recorded.
The vendored class :class:`_orig_core.KhaveeVerifier` is a verbatim copy of
``pythainlp/khavee/core.py`` from the 5.0.1 release (including its own
``is_sumpus``), so the tokenizer (``subword_tokenize(engine="dict")``) and the
rhyme judgement are exactly those of the original checker.

Rule set (as implemented in 5.0.1 ``check_klon``, ``k_type=8``):

    r1_w1_w2 : Wak1[-1] rhymes with any of Wak2[1..4]   (0-indexed positions 1-4)
    r2_w2_w3 : Wak2[-1] rhymes with Wak3[-1]
    rX_inter : Wak2[-1] (current stanza) rhymes with Wak4[-1] (previous stanza)

Note: the original 5.0.1 checker does not check the Wak3-Wak4 rule
(``r3_w3_w4``); that rule is therefore reported as not applicable (``None``).
"""
from __future__ import annotations

from typing import Optional

from pythainlp.tokenize import subword_tokenize

from . import _orig_core
from .common import CheckerResult, RULES


class OriginalKhaveeChecker:
    """Instrumented reproduction of the pythainlp 5.0.1 Klon-8 checker."""

    name = "A_pythainlp_5.0.1"

    def __init__(self) -> None:
        self._kv = _orig_core.KhaveeVerifier()

    def _syl(self, wak: str):
        try:
            return subword_tokenize(wak, engine="dict")
        except Exception:
            return []

    def check_stanza(self, w1, w2, w3, w4, prev_w4: Optional[str] = None) -> CheckerResult:
        try:
            s1, s2, s3, s4 = (self._syl(w) for w in (w1, w2, w3, w4))
            rules = {r: None for r in RULES}
            meta = {
                "tokenizer": "dict",
                "syllables": {"w1": s1, "w2": s2, "w3": s3, "w4": s4},
                "word_counts": [len(s1), len(s2), len(s3), len(s4)],
            }

            # r1: วรรคสดับ -> วรรครับ  (Wak1 last vs any of Wak2[1..4])
            rules["r1_w1_w2"] = bool(
                s1 and s2 and any(self._kv.is_sumpus(s1[-1], t) for t in s2[1:5])
            )
            # r2: วรรครับ -> วรรครอง  (Wak2 last vs Wak3 last)
            rules["r2_w2_w3"] = bool(s2 and s3 and self._kv.is_sumpus(s2[-1], s3[-1]))
            # r3: not present in the 5.0.1 implementation -> N/A
            rules["r3_w3_w4"] = None
            # rX: inter-stanza (current Wak2 last vs previous Wak4 last)
            if prev_w4 is not None:
                sp = self._syl(prev_w4)
                rules["rX_inter"] = bool(s2 and sp and self._kv.is_sumpus(s2[-1], sp[-1]))
            else:
                rules["rX_inter"] = None

            na = tuple(r for r in RULES if rules[r] is None)
            applicable = [r for r in RULES if rules[r] is not None]
            ok = bool(applicable) and all(rules[r] for r in applicable)
            return CheckerResult(checker=self.name, stanza_ok=ok, rules=rules, na=na, meta=meta)
        except Exception as e:
            # The original 5.0.1 check_klon bails (returns a generic error) on any
            # is_sumpus crash (e.g. single-char tokens break check_marttra).
            return CheckerResult(
                checker=self.name, stanza_ok=False,
                rules={r: None for r in RULES}, na=RULES,
                dropped=True, drop_reason=f"is_sumpus error: {e}", meta={},
            )
