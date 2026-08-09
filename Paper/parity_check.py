# -*- coding: utf-8 -*-
"""
Parity validation for the instrumented Klon-8 checkers.

The vendored modules ``_orig_core`` (pythainlp 5.0.1) and ``_dev_core``
(pythainlp 5.3.5) still contain the original ``check_klon`` method verbatim.
This script calls those original methods on gold stanzas and asserts that the
instrumented per-rule checkers (Checker A / Checker B) reproduce the original
verdicts. It is a guard against transcription errors in the instrumentation.

Within-stanza rules are validated on single-stanza inputs (4 waks), where the
original output is unambiguous; the inter-stanza rule (rX) is validated on
two-stanza inputs (8 waks).

Notes:
  * Checker A implements only r1, r2 and rX (the 5.0.1 checker has no r3).
  * If the original ``check_klon`` bails out (returns a generic error string,
    e.g. when a wak is too short for its syllable indexing), the stanza is
    counted as "bailed" and excluded from strict comparison.
"""
from __future__ import annotations

import ast
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "Paper"))

from pythainlp.tokenize import subword_tokenize  # noqa: E402

from eval_checkers import _orig_core, _dev_core  # noqa: E402
from eval_checkers.original_khavee import OriginalKhaveeChecker  # noqa: E402
from eval_checkers.dev_khavee import RuleBasedKhaveeChecker  # noqa: E402
from data_loading import load_stanzas  # noqa: E402


def _syl_dict(wak: str):
    return subword_tokenize(wak, engine="dict")


def _syl_ssg(wak: str):
    return subword_tokenize(wak, engine="ssg")


# ---------------------------------------------------------------------------
# Original 5.0.1 parsing
# ---------------------------------------------------------------------------
def parse_a(waks) -> dict | None:
    """Run 5.0.1 check_klon on 4 or 8 waks; return per-rule booleans or None."""
    kv = _orig_core.KhaveeVerifier()
    res = kv.check_klon(" ".join(waks), k_type=8)
    n = len(waks)
    rules = {"r1_w1_w2": True, "r2_w2_w3": True}
    if n >= 8:
        rules["rX_inter"] = True
    if isinstance(res, str):
        return rules if res.startswith("The poem is correct") else None

    for e in res:
        if "Can't find rhyme between paragraphs" not in e:
            continue
        start = e.index("between paragraphs ") + len("between paragraphs ")
        end = e.index(" in paragraph ", start)
        pair_str = e[start:end]
        para = int(e[end + len(" in paragraph "):])
        try:
            a, b = ast.literal_eval(pair_str)
        except Exception:
            continue
        base = (para - 1) * 4
        if isinstance(b, list):
            rules["r1_w1_w2"] = False
            continue
        w2l = _syl_dict(waks[base + 1])[-1]
        w3l = _syl_dict(waks[base + 2])[-1]
        # r2 and rX can both produce the same message when w3_last == prev_w4_last
        # (e.g. จิต-ฤทธิ์ in khobut_11), so test each independently.
        if {a, b} == {w2l, w3l}:
            rules["r2_w2_w3"] = False
        if para > 1:
            prev_w4l = _syl_dict(waks[base - 1])[-1]
            if {a, b} == {w2l, prev_w4l}:
                rules["rX_inter"] = False
    return rules


# ---------------------------------------------------------------------------
# Original 5.3.5 parsing
# ---------------------------------------------------------------------------
def parse_b(waks) -> dict | None:
    """Run 5.3.5 check_klon on 4 or 8 waks; return per-rule booleans or None."""
    kv = _dev_core.KhaveeVerifier()
    res = kv.check_klon(" ".join(waks), k_type=8)
    n = len(waks)
    rules = {"r1_w1_w2": True, "r2_w2_w3": True, "r3_w3_w4": True}
    if n >= 8:
        rules["rX_inter"] = True
    if isinstance(res, str):
        return rules if res.startswith("The poem is correct") else None

    for e in res:
        m = None
        # "Rhyme error in Stanza (บทที่) N: '<x>' (Wak K) ..."
        if "Rhyme error" in e:
            import re
            m = re.search(r"\(Wak (\d)\)", e)
        if m:
            k = m.group(1)
            if k == "1":
                rules["r1_w1_w2"] = False
            elif k == "2":
                rules["r2_w2_w3"] = False
            elif k == "3":
                rules["r3_w3_w4"] = False
        elif "Inter-stanza rhyme error" in e:
            rules["rX_inter"] = False
    return rules


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------
def compare(checker, orig_fn, rules_to_compare, waks, instrumented_rules):
    """Compare instrumented rules vs parsed original for one stanza."""
    expected = orig_fn(waks)
    if expected is None:
        return "bail", {}
    mismatches = {}
    for r in rules_to_compare:
        if r in expected and r in instrumented_rules:
            if expected[r] != instrumented_rules[r]:
                mismatches[r] = (expected[r], instrumented_rules[r])
    return ("ok" if not mismatches else "mismatch", mismatches)


def main(sample_limit: int = 600) -> None:
    stanzas = load_stanzas()
    # Focused sample: all of phukaoTong, then heads of the other stories.
    sample = [s for s in stanzas if s.story == "phukaoTong"]
    for story in ("phraAphai", "khobut", "khunChangKhunPhaen", "SuphasaetSonYing"):
        sample += [s for s in stanzas if s.story == story][:sample_limit // 5]

    chkA = OriginalKhaveeChecker()
    chkB = RuleBasedKhaveeChecker()

    stats = {
        "A": {"ok": 0, "mismatch": 0, "bail": 0},
        "B": {"ok": 0, "mismatch": 0, "bail": 0},
        "A_rX": {"ok": 0, "mismatch": 0, "bail": 0},
        "B_rX": {"ok": 0, "mismatch": 0, "bail": 0},
    }
    a_mis = []
    b_mis = []

    # Group by (story, chapter) to form consecutive pairs for rX.
    from collections import defaultdict
    by_chapter = defaultdict(list)
    for s in sample:
        by_chapter[(s.story, s.chapter)].append(s)

    for st in sample:
        waks = [st.w1, st.w2, st.w3, st.w4]

        # Checker A (r1, r2)
        resA = chkA.check_stanza(st.w1, st.w2, st.w3, st.w4, st.prev_w4)
        status, mis = compare(chkA, parse_a, ("r1_w1_w2", "r2_w2_w3"), waks, resA.rules)
        stats["A"][status if status != "bail" else "bail"] += 1
        if status == "mismatch":
            a_mis.append((st.story, st.chapter, st.row, mis))

        # Checker B (r1, r2, r3)
        resB = chkB.check_stanza(st.w1, st.w2, st.w3, st.w4, st.prev_w4)
        status, mis = compare(chkB, parse_b, ("r1_w1_w2", "r2_w2_w3", "r3_w3_w4"), waks, resB.rules)
        stats["B"][status if status != "bail" else "bail"] += 1
        if status == "mismatch":
            b_mis.append((st.story, st.chapter, st.row, mis))

    # rX via consecutive pairs within each chapter
    for key, rows in by_chapter.items():
        for i in range(len(rows) - 1):
            s1, s2 = rows[i], rows[i + 1]
            waks = [s1.w1, s1.w2, s1.w3, s1.w4, s2.w1, s2.w2, s2.w3, s2.w4]
            resA = chkA.check_stanza(s2.w1, s2.w2, s2.w3, s2.w4, s1.w4)
            resB = chkB.check_stanza(s2.w1, s2.w2, s2.w3, s2.w4, s1.w4)
            stA, misA = compare(chkA, parse_a, ("rX_inter",), waks, resA.rules)
            stB, misB = compare(chkB, parse_b, ("rX_inter",), waks, resB.rules)
            stats["A_rX"][stA if stA != "bail" else "bail"] += 1
            stats["B_rX"][stB if stB != "bail" else "bail"] += 1
            if stA == "mismatch":
                a_mis.append((s2.story, s2.chapter, s2.row, {"rX": misA}))
            if stB == "mismatch":
                b_mis.append((s2.story, s2.chapter, s2.row, {"rX": misB}))

    print("=" * 78)
    print("PARITY VALIDATION — instrumented vs original check_klon")
    print("=" * 78)
    for label, d in stats.items():
        print(f"  {label:<6} ok={d['ok']:<6} mismatch={d['mismatch']:<5} bail={d['bail']}")
    print(f"\n  Checker A mismatches: {len(a_mis)}")
    for story, ch, row, mis in a_mis[:10]:
        print(f"    A  {story}/{ch} row {row}: {mis}")
    print(f"  Checker B mismatches: {len(b_mis)}")
    for story, ch, row, mis in b_mis[:10]:
        print(f"    B  {story}/{ch} row {row}: {mis}")
    print("\n  (bail = original check_klon returned a generic error string and was excluded)")


if __name__ == "__main__":
    main()
