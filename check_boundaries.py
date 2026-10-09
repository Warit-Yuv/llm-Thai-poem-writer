# -*- coding: utf-8 -*-
"""Settle the 5 orphan-pair sites in phraAphai_22/31/80 with Checker B's rules.

At each site an ๏ act ends with a 2-วรรค fragment (its last วรรค carries ฯ)
right before the next act's ๏. Three fates are possible:

  E  (what write_eval does today): the pair is วรรค 1+2 of a stanza that spans
     the act boundary -> บท = [o1, o2, n1, n2]
  A  (act-faithful): the next act opens its own บท -> [n1, n2, n3, n4]; the
     pair is then a 2-วรรค fragment with no home (acts stay stanza-aligned)
  F  (missing source text): the pair is วรรค 3+4 of a closing บท whose first
     half is lost from the source — testable only via the rX link o2 <-> n2

Every candidate is judged by the 5.3.5 KhaveeVerifier (the project oracle,
Checker B) on a 3-บท window so the inter-stanza rhyme is included too.
"""
import sys
from pathlib import Path

from pythainlp.tokenize import syllable_tokenize

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from count_raw_dataset import parse_file, DATASET
from Paper.eval_checkers._dev_core import KhaveeVerifier

kv = KhaveeVerifier()


def last_syl(wak):
    """Final syllable of a วรรค (ssg) — where รับ-รอง and the rX rhyme live."""
    return syllable_tokenize(wak, engine="ssg")[-1]

# (stem, 1-based index of the orphan pair's first วรรค)
SITES = [
    ("phraAphai_22", 529),
    ("phraAphai_31", 181),
    ("phraAphai_31", 891),
    ("phraAphai_80", 373),
    ("phraAphai_80", 395),
]


def show(name, ws, start):
    v = kv.check_klon(" ".join(ws[start:start + 12]))
    if isinstance(v, str):
        print(f"      {name}: {v}")
    else:
        print(f"      {name}: " + "  ||  ".join(v))


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    for stem, o1 in SITES:
        rec = parse_file(next(DATASET.glob(f"*/{stem}.txt")))
        ws = rec["wak_texts"]                       # 0-based
        i = o1 - 1
        o1t, o2t = ws[i], ws[i + 1]
        n = ws[i + 2:i + 6]                         # next act's first บท
        print(f"\n=== {stem} — orphan pair วรรค {o1}–{o1 + 1} ===")
        print(f"    pair   : {o1t}   /   {o2t}")
        print(f"    next   : {n[0]}   /   {n[1]}   /   {n[2]}   /   {n[3]}")
        # E: [P | o1,o2,n1,n2 | n3..n6]  — window starts at P (o1-4)
        show("E eval ", ws, i - 4)
        # A: [P | n1..n4 | n5..n8] with the orphan pair removed
        wa = ws[:i] + ws[i + 2:]
        show("A act  ", wa, i - 4)
        # F: o2 as วรรคส่ง must rhyme with the next act's วรรค 2 (last syllables)
        a, b = last_syl(o2t), last_syl(n[1])
        print(f"      F rX  : last-syl {a!r} vs {b!r} -> {kv.is_sumpus(a, b)}")


if __name__ == "__main__":
    main()
    # phraAphai_80 site #2 deep dive: candidate tilings around วรรค 385–404
    rec = parse_file(next(DATASET.glob("*/phraAphai_80.txt")))
    ws = rec["wak_texts"]
    print("\n=== phraAphai_80 — tiling candidates around วรรค 385–404 ===")
    show("T1 [385-388|389-392|393-396]", ws, 384)
    show("T2 [389-392|393-396|397-400]", ws, 388)
    show("T3 [393-396|397-400|401-404]", ws, 392)

    # phraAphai_22: is the pair [529,530] w3+w4 of บท [527-530]? and where does
    # the tiling break earlier?
    rec = parse_file(next(DATASET.glob("*/phraAphai_22.txt")))
    ws = rec["wak_texts"]
    print("\n=== phraAphai_22 — tiling probes ===")
    show("A [501-504|505-508|509-512]", ws, 500)
    show("B [513-516|517-520|521-524]", ws, 512)
    show("C eval [525-528|529-532|533-536]", ws, 524)
    show("D shift [527-530|531-534|535-538]", ws, 526)

    # phraAphai_31 site #1: is บท [179-182] (orphan pair as w3+w4) real?
    rec = parse_file(next(DATASET.glob("*/phraAphai_31.txt")))
    ws = rec["wak_texts"]
    print("\n=== phraAphai_31 — tiling probes ===")
    show("E eval [177-180|181-184|185-188]", ws, 176)
    show("F shift [179-182|183-186|187-190]", ws, 178)
