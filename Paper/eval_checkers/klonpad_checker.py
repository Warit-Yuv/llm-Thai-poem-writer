# -*- coding: utf-8 -*-
"""
Checker D — Klonpad (override-enhanced segmentation + Klon-8 rules).

Working hypothesis. An override dictionary of verified syllable splits should
improve rhyme detection by correcting w2p/ssg segmentation errors *before* the
rhyme rules are applied. To isolate the segmentation variable, this checker
uses the same rule set and the same rhyme predicate (``is_sumpus`` from
pythainlp 5.3.5) as Checker B; the only difference is that syllables are
produced by :func:`klonpad_syllables.extract_poetic_syllables` (overrides +
w2p) rather than by raw ssg tokenization.
"""
from __future__ import annotations

from typing import Optional

from . import _dev_core
from . import klonpad_syllables as kp
from .common import CheckerResult, RULES


class KlonpadChecker:
    """Klonpad checker: override-aware segmentation + Klon-8 rhyme rules.

    ``fallback`` selects the segmenter used for words not covered by
    ``POETRY_OVERRIDES``: ``"w2p"`` (default, original notebook behaviour) or
    ``"ssg"`` (plain ssg, no w2p romanisation).
    """

    def __init__(self, fallback: str = "w2p", name: Optional[str] = None) -> None:
        self._kv = _dev_core.KhaveeVerifier()
        self._fallback = fallback
        self.name = name or f"D_klonpad_{fallback}"

    def _syl(self, wak: str):
        return kp.extract_poetic_syllables(wak, fallback=self._fallback)

    def check_stanza(self, w1, w2, w3, w4, prev_w4: Optional[str] = None) -> CheckerResult:
        try:
            s1, s2, s3, s4 = (self._syl(w) for w in (w1, w2, w3, w4))
            rules = {r: None for r in RULES}
            meta = {
                "tokenizer": f"overrides+{self._fallback}",
                "syllables": {"w1": s1, "w2": s2, "w3": s3, "w4": s4},
                "word_counts": [len(s1), len(s2), len(s3), len(s4)],
            }

            # Rule set mirrors Checker B (pythainlp 5.3.5) for isolation.
            rules["r1_w1_w2"] = bool(
                s1 and s2 and any(self._kv.is_sumpus(s1[-1], t) for t in s2[:5])
            )
            rules["r2_w2_w3"] = bool(s2 and s3 and self._kv.is_sumpus(s2[-1], s3[-1]))
            rules["r3_w3_w4"] = bool(
                s3 and s4 and any(self._kv.is_sumpus(s3[-1], t) for t in s4[:5])
            )
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
            return CheckerResult(
                checker=self.name, stanza_ok=False,
                rules={r: None for r in RULES}, na=RULES,
                dropped=True, drop_reason=f"is_sumpus error: {e}", meta={},
            )


class KlonpadSsgChecker(KlonpadChecker):
    """Klonpad variant whose fallback is plain ssg (no w2p romanisation).

    Used to isolate whether the w2p ``pronunciate`` fallback helps or hurts
    relative to a pure ssg fallback, e.g. on words not covered by the override
    dictionary (older/archaic texts such as Khun Chang Khun Phaen).
    """

    def __init__(self) -> None:
        super().__init__(fallback="ssg", name="D_klonpad_ssg_fallback")
