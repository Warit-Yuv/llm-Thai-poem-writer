# -*- coding: utf-8 -*-
"""
Diagnostic: why does D (Klonpad) trail B (pythainlp 5.3.5), and does the w2p
fallback help or hurt?

Runs three segmentation paths over the full gold corpus under identical rules /
rhyme predicate (isolation of the segmentation variable):
  * B          = pythainlp 5.3.5 ``subword_tokenize(engine="ssg")``
  * D_w2p      = overrides + w2p ``pronunciate`` fallback (original Klonpad)
  * D_ssg      = overrides + plain ssg fallback (no w2p)

Also reports:
  * per-story syllable-source stats (override vs w2p/ssg) for D_w2p
  * ``process_w2p.cache_info()`` after the run -> distinct w2p inputs, to judge
    the LRU size needed (was 8,192; now 200,000)
"""
import sys
import time
from collections import OrderedDict, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"e:\User\Noto\SIIT\SIIT_Year_4\LLM_WritePoem")
sys.path.insert(0, r"e:\User\Noto\SIIT\SIIT_Year_4\LLM_WritePoem\Paper")

from data_loading import load_stanzas  # noqa: E402
from eval_checkers import (  # noqa: E402
    RuleBasedKhaveeChecker, KlonpadChecker, KlonpadSsgChecker,
)
from eval_checkers.common import RULES  # noqa: E402
from eval_checkers import klonpad_syllables as kp  # noqa: E402


def run(ck, stanzas):
    per = defaultdict(lambda: {"n": 0, "pass": 0, "drop": 0,
                               "r_ok": defaultdict(int), "r_n": defaultdict(int)})
    t0 = time.time()
    for s in stanzas:
        r = ck.check_stanza(s.w1, s.w2, s.w3, s.w4, prev_w4=s.prev_w4)
        st = per[s.story]
        if r.dropped:
            st["drop"] += 1
            continue
        st["n"] += 1
        st["pass"] += int(r.stanza_ok)
        for rid in RULES:
            v = r.rules.get(rid)
            if v is not None:
                st["r_n"][rid] += 1
                st["r_ok"][rid] += int(v)
    print(f"  ({ck.name} done in {time.time() - t0:.0f}s)")
    return per


def fmt(st):
    rr = [f"{100 * st['r_ok'][rid] / max(1, st['r_n'][rid]):4.0f}" for rid in RULES]
    return f"{100 * st['pass'] / st['n']:6.1f}%   {'/'.join(rr)}  (n={st['n']})"


def main():
    stanzas = load_stanzas()
    B = RuleBasedKhaveeChecker()
    Dw = KlonpadChecker(fallback="w2p")
    Ds = KlonpadSsgChecker()

    print("running B ...")
    pb = run(B, stanzas)
    print("running D_w2p ...")
    pd = run(Dw, stanzas)
    print("running D_ssg ...")
    pds = run(Ds, stanzas)

    print("\nw2p cache_info:", kp.process_w2p.cache_info())
    print("  (hits+misses = total w2p calls; misses ~ distinct words needing w2p)")

    for name, per in [("B_pythainlp_5.3.5", pb), ("D_w2p_overrides", pd),
                      ("D_ssg_overrides", pds)]:
        print(f"\n{name}")
        tot = {"n": 0, "pass": 0, "r_ok": defaultdict(int), "r_n": defaultdict(int)}
        for story in sorted(per):
            st = per[story]
            for rid in RULES:
                tot["r_n"][rid] += st["r_n"][rid]
                tot["r_ok"][rid] += st["r_ok"][rid]
            tot["n"] += st["n"]
            tot["pass"] += st["pass"]
            print(f"  {story:<22} {fmt(st)}")
        print(f"  {'TOTAL':<22} {fmt(tot)}")

    print("\nsyllable-source stats for D_w2p (fraction of syllables from override "
          "dictionary vs w2p fallback):")
    for story in sorted({s.story for s in stanzas}):
        stats = {}
        for s in stanzas:
            if s.story == story:
                for w in s.waks():
                    kp.extract_poetic_syllables(w, fallback="w2p", stats=stats)
        tot = sum(stats.values())
        ov = stats.get("override", 0)
        w2p = stats.get("w2p", 0)
        print(f"  {story:<22} syllables={tot:>7}  override={ov:>7} "
              f"({100 * ov / max(1, tot):5.1f}%)  w2p={w2p:>7} "
              f"({100 * w2p / max(1, tot):5.1f}%)")


if __name__ == "__main__":
    main()
