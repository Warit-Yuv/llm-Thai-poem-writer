# -*- coding: utf-8 -*-
"""
override_draft_cleaner.py

Cleans & screens the (user-edited) Tier A override draft WITHOUT touching it.

Reads:
  - override_draft_tierA_safe copy.py   user-edited Tier A draft (your backup)
  - klonpad_validator.ipynb             main POETRY_OVERRIDES (for dedup)
  - Results/Evaluate/**/*_ok.csv       corpus (for example context)

Writes:
  - override_draft_tierA_clean.py       paste-ready dict (no "# xN" comments,
                                        deduped, keys already in main dict removed)
  - override_draft_tierA_screen.tsv     full peek table for every 2+ syllable word

Prints:
  - duplicate keys inside the draft
  - keys already present in main POETRY_OVERRIDES (would-be duplicates, removed)
  - heuristic flags on 2+ syllable words (final consonant / long-short vowel /
    tone-mark loss / redundant final) with example context for manual review

NOTE: syllable VALUES are taken from your draft as-is; this script never
rewrites pronunciation, it only flags suspicious ones for you to eyeball.
"""
import ast
import glob
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pandas as pd
from pythainlp.khavee import KhaveeVerifier
from pythainlp.tokenize import syllable_tokenize

kv = KhaveeVerifier()

ROOT = os.path.dirname(os.path.abspath(__file__))
DRAFT = os.path.join(ROOT, "override_draft_tierA_safe copy.py")
NOTEBOOK = os.path.join(ROOT, "klonpad_validator.ipynb")
OUT_PY = os.path.join(ROOT, "override_draft_tierA_clean.py")
OUT_TSV = os.path.join(ROOT, "override_draft_tierA_screen.tsv")
EXPORT_DIR = os.path.join(ROOT, "Results", "Evaluate")

TONE = "่้๊๋"
# (syllable screening now delegates to the improved KhaveeVerifier.is_sumpus)


# vowel characters (used to decide whether a syllable is comparable)
VOWEL_CHARS = "ะาิีึืุูเแโใไำัอ็"


def word_last_syllable(word):
    try:
        syls = syllable_tokenize(word, engine="ssg")
        return syls[-1] if syls else None
    except Exception:
        return None


def parse_assignment(source, var_names):
    """Return (keys, values) of the first dict assigned to one of var_names."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in var_names and isinstance(node.value, ast.Dict):
                    d = node.value
                    keys = [ast.literal_eval(k) for k in d.keys]
                    vals = [ast.literal_eval(v) for v in d.values]
                    return keys, vals
    raise ValueError(f"no dict assignment to {var_names} found")


def load_notebook_main_dict(path):
    with io.open(path, encoding="utf-8") as f:
        nb = json.load(f)
    for cell in nb["cells"]:
        src = "".join(cell.get("source", []))
        if "POETRY_OVERRIDES" in src and "=" in src and "{" in src:
            try:
                keys, _ = parse_assignment(src, {"POETRY_OVERRIDES"})
                return keys
            except Exception:
                continue
    raise ValueError("POETRY_OVERRIDES not found in notebook")


def load_main_dict():
    """Main override dict: prefer poetry_overrides.py module, fall back to the notebook."""
    mod = os.path.join(ROOT, "poetry_overrides.py")
    if os.path.exists(mod):
        import importlib.util

        spec = importlib.util.spec_from_file_location("poetry_overrides", mod)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        d = dict(m.POETRY_OVERRIDES)
        print(f"   loaded main dict from poetry_overrides.py: {len(d)} keys")
        return d
    keys = load_notebook_main_dict(NOTEBOOK)
    return {k: None for k in keys}


def load_draft(path):
    with io.open(path, encoding="utf-8") as f:
        src = f.read()
    keys, vals = parse_assignment(src, {"POETRY_OVERRIDES_ADD", "POETRY_OVERRIDES"})
    return keys, vals


def build_corpus(export_dir):
    """Load every `*_ok.csv` under `export_dir` into one corpus string.

    Recursive scan so it ingests ALL poems, not just phraAphai — the new
    `Results/Evaluate/<poem>/*_ok.csv` layout (khobut/, khunChangKhunPhaen/,
    phraAphai/, phukaoTong/, SuphasaetSonYing/) as well as the old flat
    `Results/Export/ok/*_ok.csv` layout.

    Handles both CSV layouts:
      - old 24-col:  w1_a..w8_c   (8 waks x 3 parts)
      - new  4-col:  w1..w4       (4 full waks per row)
    Falls back to every column if neither layout matches.
    """
    texts = []
    old_cols = [f"w{n}_{p}" for n in range(1, 9) for p in ("a", "b", "c")]
    new_cols = [f"w{n}" for n in range(1, 5)]
    fps = sorted(glob.glob(os.path.join(export_dir, "**", "*_ok.csv"), recursive=True))
    for fp in fps:
        df = pd.read_csv(fp, dtype=str)
        if old_cols[0] in df.columns:
            cols = old_cols
        elif new_cols[0] in df.columns:
            cols = new_cols
        else:
            cols = list(df.columns)
        for _, row in df.iterrows():
            texts.append("".join(row[c] for c in cols if isinstance(row[c], str)))
    return "\n".join(texts)


def find_context(big, word):
    i = big.find(word)
    if i < 0:
        return ""
    return big[max(0, i - 8): i + len(word) + 10].replace("\n", "¦")


def screen_override(word, syls, flag_ssg1_countdiff=True):
    """Review flags for 2+ syllable entries (verify by ear, never auto-fix).

    Compares EVERY syllable of the override against the word's own ssg split
    (not just the last) using the improved KhaveeVerifier.is_sumpus — so a
    hallucination at ANY position is caught (e.g. น้ำตา -> น้าม-ตา). Plus:
      - tone marks lost (override has fewer than the source word)
      - tone mark CHANGED (้->่, matters for เอก/โท checks downstream)
      - over-spelled / redundant finals (น้ำ -> น้าม, ไส -> ไสย)
      - no-vowel syllable fragments (เฉย-เม-ย, ตร-อม-ตร-ม -> split is wrong)
    Syllables whose ssg form has การันย์ or is a 1-char fragment are skipped
    (silent Pali letters -> override is usually right).

    flag_ssg1_countdiff=False: bulk-accept mode (--review-lenient). Skips
    count-disagreements where ssg sees FEWER syllables than the override AND
    the override has no bare fragment (cluster words where w2p is ~97% right,
    e.g. ตลบ -> ตะ-หลบ). High-signal flags (fragments, tone changes, ssg>w2p)
    are still kept. WARNING: ~3% of the skipped ones are real hallucinations
    (e.g. กวัด -> กะ-วัด), so only use this if you accept a small miss rate.
    """
    flags = []
    if len(syls) < 2:
        return flags

    # 1) tone marks lost (override has FEWER than the source word)
    nw = sum(1 for c in word if c in TONE)
    ns = sum(1 for c in "".join(syls) if c in TONE)
    if ns < nw:
        flags.append(f"tone lost {nw}→{ns}")

    # 2) structural problems anywhere in the override
    #    (only 1-char fragments are flagged — Pali cluster syllables like คร/ทร
    #     have implicit vowels and are legit; wrong 2+ char fragments are
    #     caught by the per-syllable is_sumpus comparison below instead)
    for i, o in enumerate(syls, 1):
        if len(o) < 2:
            flags.append(f"1-char syllable @{i} ({o})")
        if re.search(r"ำ[ก-ฮ]$", o):
            flags.append(f"redundant ำ+cons @{i}")
        if re.search(r"[ก-ฮ][ใไ]ย$", o):
            flags.append(f"redundant ไ/ใ+ย @{i}")
        if re.search(r"เ[ก-ฮ]าว$", o):
            flags.append(f"redundant เ-า+ว @{i}")

    # 3) syllable-by-syllable sound check against the word's own ssg split
    try:
        ssg_syls = syllable_tokenize(word, engine="ssg")
    except Exception:
        ssg_syls = []
    if not ssg_syls:
        return flags
    if len(ssg_syls) != len(syls):
        # ssg and w2p disagree on syllable COUNT. Both engines are unreliable
        # on leading-consonant (อักษรนำ) words, so this genuinely needs an ear:
        #   กลัว (1 syl)  -> w2p hallucinates กล-หวัว   [has bare fragment]
        #   ตลบ  (2 syls) -> ssg wrongly sees 1         [w2p correct, no frag]
        # Strict mode flags ALL of these. --review-lenient only keeps the
        # high-signal ones: ssg>w2p (w2p merged) and any w2p split that has a
        # bare fragment (the w2p-hallucination signature). ~97% of the dropped
        # entries are genuinely correct w2p splits of cluster words.
        if len(ssg_syls) > len(syls):
            flags.append(f"ssg splits more than override ({len(ssg_syls)} vs {len(syls)})")
        elif not flag_ssg1_countdiff and not any(
            len(o) < 2 or not any(c in VOWEL_CHARS for c in o) for o in syls
        ):
            pass  # lenient: ssg under-split a cluster word; w2p likely right
        else:
            flags.append(f"syllable count differs (ssg {len(ssg_syls)} vs w2p {len(syls)})")
        return flags
    for i, (ws, o) in enumerate(zip(ssg_syls, syls), 1):
        tw = [c for c in ws if c in TONE]
        to = [c for c in o if c in TONE]
        if tw and to and tw != to:
            flags.append(f"tone changed @{i} ({ws} vs {o})")
        if len(ws) < 2 or "์" in ws:
            continue
        try:
            if not kv.is_sumpus(ws, o):
                flags.append(f"sound mismatch @{i} ({ws} vs {o})")
        except Exception:
            flags.append(f"sound ? @{i}")
    return flags


def main():
    print("=" * 100)
    print("1) LOAD DRAFT  (from your backup: override_draft_tierA_safe copy.py)")
    keys, vals = load_draft(DRAFT)
    n = len(keys)
    print(f"   draft entries: {n}")

    # --- duplicates inside the draft ---
    seen, dups = {}, []
    for i, k in enumerate(keys):
        if k in seen:
            dups.append((k, seen[k], i))
        else:
            seen[k] = i
    print(f"   duplicate keys INSIDE draft: {len(dups)}")
    for k, i1, i2 in dups[:20]:
        print(f"       dup '{k}'  line {i1 + 2} vs {i2 + 2}   {vals[i1]} vs {vals[i2]}")

    # dedupe, keep first occurrence
    first = {}
    entries = []
    for i, k in enumerate(keys):
        if k not in first:
            first[k] = True
            entries.append((k, vals[i]))

    print()
    print("2) DIFF vs MAIN POETRY_OVERRIDES  (would-be duplicate keys)")
    main_dict = load_main_dict()
    main_keys = list(main_dict)
    main_set = set(main_keys)
    print(f"   main POETRY_OVERRIDES keys: {len(main_set)}  "
          f"(dups inside main: {len(main_keys) - len(main_set)})")
    already = [(w, s) for w, s in entries if w in main_set]
    remaining = [(w, s) for w, s in entries if w not in main_set]
    print(f"   draft keys already in main dict -> REMOVED: {len(already)}")
    for w, _ in already[:40]:
        print(f"       - {w}")
    if len(already) > 40:
        print(f"       ... and {len(already) - 40} more")

    print()
    print("3) SCREEN 2+ SYLLABLE WORDS  (wrong final / long-short vowel / tone / redundant final)")
    big = build_corpus(EXPORT_DIR)
    multi = [(w, s) for w, s in remaining if len(s) >= 2]
    rows, flagged = [], []
    for w, s in multi:
        fl = screen_override(w, s)
        ctx = find_context(big, w)
        rows.append((w, "-".join(s), ";".join(fl), ctx))
        if fl:
            flagged.append((w, "-".join(s), fl, ctx))
    print(f"   2+ syllable entries: {len(multi)}   flagged: {len(flagged)}")

    print()
    print("   FLAGGED ENTRIES (verify by ear before merging):")
    print(f"   {'word':<18}{'syllables':<28}{'flags':<36}context")
    print("   " + "-" * 96)
    for w, syl, fl, ctx in flagged[:120]:
        print(f"   {w:<18}{syl:<28}{';'.join(fl):<36}{ctx}")
    if len(flagged) > 120:
        print(f"   ... ({len(flagged) - 120} more in the TSV)")

    with io.open(OUT_TSV, "w", encoding="utf-8") as f:
        f.write("word\tsyllables\tflags\tcontext\n")
        for w, syl, fl, ctx in rows:
            f.write(f"{w}\t{syl}\t{fl}\t{ctx}\n")
    print(f"   wrote {os.path.basename(OUT_TSV)}  ({len(rows)} rows)")

    print()
    print("4) WRITE CLEAN FILE  (paste-ready: no comments, deduped, minus main-dict keys)")
    with io.open(OUT_PY, "w", encoding="utf-8") as f:
        f.write("# override_draft_tierA_clean.py\n")
        f.write("# Tier A overrides, cleaned: no '# xN' comments, deduped, keys already in\n")
        f.write("# POETRY_OVERRIDES removed. VERIFY flagged 2+ syllable entries in\n")
        f.write("# override_draft_tierA_screen.tsv before merging.\n")
        f.write("POETRY_OVERRIDES_ADD = {\n")
        for w, s in remaining:
            lst = ", ".join('"%s"' % x for x in s)
            f.write('    "%s": [%s],\n' % (w, lst))
        f.write("}\n")
    print(f"   wrote {os.path.basename(OUT_PY)}  ({len(remaining)} entries)")

    print()
    print("=" * 100)
    print(f"SUMMARY: draft={n} -> deduped={len(entries)} -> minus-main={len(remaining)}  "
          f"(multi-syllable {len(multi)}, flagged {len(flagged)})")


if __name__ == "__main__":
    main()
