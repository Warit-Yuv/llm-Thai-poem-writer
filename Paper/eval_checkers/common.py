# -*- coding: utf-8 -*-
"""
Shared data contract for the Klon-8 rhyme-detection evaluation.

A stanza (บท) consists of four waks (วรรค): w1 (สดับ), w2 (รับ), w3 (รอง),
w4 (ส่ง). The canonical rule set follows the Klon-8 prosodic model used by the
reference implementation (pythainlp KhaveeVerifier):

    r1_w1_w2 : final syllable of Wak 1 rhymes with a target inside Wak 2
    r2_w2_w3 : final syllable of Wak 2 rhymes with the final syllable of Wak 3
    r3_w3_w4 : final syllable of Wak 3 rhymes with a target inside Wak 4
    rX_inter : final syllable of Wak 4 (previous stanza) rhymes with the final
               syllable of Wak 2 (current stanza)

The inter-stanza rule is applicable only when a previous stanza exists
(i.e. it is ``None``/not-applicable for the first stanza of a chapter, since
chapters are evaluated independently).

Each checker implements :meth:`check_stanza`, which returns a
:class:`CheckerResult` recording the outcome of every applicable rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Canonical rule identifiers, shared by all checkers.
RULES: Tuple[str, ...] = ("r1_w1_w2", "r2_w2_w3", "r3_w3_w4", "rX_inter")


@dataclass
class CheckerResult:
    """Outcome of evaluating one stanza (บท) with one checker.

    ``rules`` always contains a key for every rule in :data:`RULES`; a value of
    ``None`` means the rule was not applicable (N/A, currently only possible
    for ``rX_inter`` when no previous stanza exists). ``stanza_ok`` is True iff
    every applicable rule passed. ``dropped`` indicates the checker could not
    produce a rhyme verdict for this stanza (e.g. G2P failure), in which case
    the rule outcomes should not be interpreted.
    """

    checker: str
    stanza_ok: bool
    rules: Dict[str, Optional[bool]]
    na: Tuple[str, ...] = ()
    dropped: bool = False
    drop_reason: str = ""
    meta: Dict = field(default_factory=dict)

    @property
    def applicable(self) -> List[str]:
        return [r for r in RULES if self.rules.get(r) is not None]


def stanza_ok_from_rules(rules: Dict[str, Optional[bool]]) -> bool:
    """True iff every applicable rule in ``rules`` passed."""
    vals = [v for v in rules.values() if v is not None]
    return bool(vals) and all(vals)
