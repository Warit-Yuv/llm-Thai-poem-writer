# -*- coding: utf-8 -*-
"""
build_overrides.py — reliable, smart override pipeline for Klon-8 poetry.

The override dict's REAL job is to fix w2p hallucinations (the speedup is a
bonus). The pipeline now has FOUR independent guards against hallucination:

  1. GOLD input            your hand-edited draft (`--gold`) is treated as
                           gold: values are used as-is and NEVER regenerated
                           from w2p. It is still screened, and anything that
                           looks wrong is surfaced to REVIEW instead of being
                           silently trusted. A small built-in KNOWN_GOLD_FIXES
                           layer (author-verified corrections) wins over both.
  2. PREFER-ORTHOGRAPHY    when ssg and w2p agree on syllable COUNT and every
                           syllable is sound-equivalent (is_sumpus), keep the
                           ssg ORTHOGRAPHIC split (ใช้ not ไช้, อยู่ not หยู่,
                           ผู้ not พู่, สาคร->สา-คร). Critical: keeps เอก/โท
                           tone marks identical to the source for aek/tow.
  3. COMPOSITION           before running w2p, try to decompose the word into
                           already-covered parts (main dict + gold + accepted).
                           If found, build the syllables from the parts — no
                           w2p call, no hallucination possible. This is the
                           "fix น้ำ once, น้ำตา/ปากน้ำ/น้ำท่า inherit" idea.
  4. SCREENING             per-syllable is_sumpus vs the word's own ssg split,
                           tone-lost / tone-changed flags, redundant-final
                           patterns, and structural checks (no-vowel fragment,
                           3+ consonant stack) that catch under-split Pali.

Buckets:
  AUTO     freq >= --min-freq  AND  passed screening  -> safe to merge now
  FIXED    flagged but deterministically fixable       -> safe to merge now
           (only the redundant-final pattern, e.g. น้ำ->น้าม, verified against
            the word's own last syllable via ssg — never a blanket replace)
  REVIEW   flagged, not safely fixable                 -> fix by ear, then merge
           (includes suspicious entries from your gold draft!)
  COMPOSED composed from covered parts (default)       -> safe to merge now
           = the "components fix compounds" bucket; no w2p involved
  SKIP     rare (freq < --min-freq) and clean          -> leave to w2p at runtime

Runtime w2p fall-through = REVIEW (until you fix) + SKIP. That is intentional
and small. Dict size never hurts performance (lookup is O(1), ~57 ns vs ~4.5 ms
for one w2p call), so we only avoid bloat and, more importantly, avoid baking
unverified w2p hallucinations into the dict.

Re-run whenever the corpus grows (e.g. 5x) — it regenerates everything from
scratch. It never modifies poetry_overrides.py or your hand-edited drafts.

Usage:
    python build_overrides.py                          # min-freq 3, compose on
    python build_overrides.py --min-freq 1             # max coverage
    python build_overrides.py --no-compose             # don't generate compounds
    python build_overrides.py --out poetry_overrides_generated.py

Outputs (same folder as --out):
    <out>.py              AUTO+FIXED+COMPOSED -> paste into poetry_overrides.py
    <out>_review.py       REVIEW -> fix by ear, then paste
    <out>.screen.tsv      every word + syllables + flags + context
"""
import argparse
import ast
import io
import os
import sys
from collections import defaultdict
from functools import lru_cache

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from pythainlp.khavee import KhaveeVerifier
from pythainlp.tokenize import syllable_tokenize, word_tokenize, word_dict_trie
from pythainlp.transliterate import pronunciate
from tqdm import tqdm

# reuse parsing + screening helpers (single source of truth)
from override_draft_cleaner import (
    build_corpus,
    load_main_dict,
    screen_override,
)

kv = KhaveeVerifier()

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CORPUS = os.path.join(ROOT, "Results", "Exportable")
DEFAULT_OUT = os.path.join(ROOT, "poetry_overrides_generated.py")


@lru_cache(maxsize=200000)
def process_w2p(word):
    """Same syllable-split logic as the notebook's process_w2p."""
    if len(word) <= 2:
        return tuple(syllable_tokenize(word, engine="ssg"))
    ph = pronunciate(word, engine="w2p")
    if not ph:
        return tuple(syllable_tokenize(word, engine="ssg"))
    clean = ph.replace("ฺ", "").replace("-", "")
    syls = syllable_tokenize(clean, engine="ssg")
    return tuple(s for s in syls if s != "ห" or word == "ห")


def safe_fix(word, syls):
    """Deterministic, VERIFIED fix for redundant-final hallucinations.

    Works at ANY syllable position, not just the last (e.g. น้ำตา -> น้าม-ตา).
    For each position where the word's own ssg syllable is a prefix of the w2p
    syllable and the extra char is orthographically redundant, restore the ssg
    spelling:
        น้ำ (ssg, ำ) + explicit ม -> น้าม   -> fix to น้ำ
        ไส (ssg, ไ) + ย -> ไสย          -> fix to ไส
        เรา (ssg, เ-า) + ว -> เราว      -> fix to เรา
    Note: w2p spells the ำ-sound as explicit "าม", so we normalize ำ -> าม
    before comparing. Never a blanket replace: requires the exact redundant
    pattern, matching syllable counts, and valid ssg syllables without การันย์.
    """
    if len(syls) < 2:
        return list(syls), False
    try:
        ssg_syls = syllable_tokenize(word, engine="ssg")
    except Exception:
        ssg_syls = []
    if not ssg_syls or len(ssg_syls) != len(syls):
        return list(syls), False
    fixed = list(syls)
    changed = False
    for i, (ws, o) in enumerate(zip(ssg_syls, syls)):
        if len(ws) < 2 or "์" in ws:
            continue
        if ws.endswith("ำ") and o == ws.replace("ำ", "าม"):
            fixed[i], changed = ws, True
        elif (ws.endswith("ไ") or ws.endswith("ใ")) and o == ws + "ย":
            fixed[i], changed = ws, True
        elif ws.endswith("า") and "เ" in ws and o == ws + "ว":
            fixed[i], changed = ws, True
    return fixed, changed


# ---------------------------------------------------------------------------
# GOLD layers — author-verified corrections. Highest priority source.
# (The user explicitly identified these during review; they override even the
#  hand-edited draft, which still contains some w2p-era errors, e.g. บาทบงกช.)
# ---------------------------------------------------------------------------
KNOWN_GOLD_FIXES = {
    "พหล": ["พะ", "หน"],              # w2p/ssg both hallucinate -> พะ-หลัน
    "บาทบงกช": ["บาด", "ทะ", "บง", "กด"],  # draft still has w2p's 3-syllable error
    "เฉยเมย": ["เฉย", "เมย"],          # both ssg+w2p split the ย out
    "ระหกระเหิน": ["ระ", "หก", "ระ", "เหิน"],  # both merge หก+ระ -> หกระ
    "ตรอมตรม": ["ตรอม", "ตรม"],        # both break ตรอม-ตรม into 4 fragments
}


def load_gold(path):
    """Parse a POETRY_OVERRIDES-style dict out of a .py file (hand-edited
    draft). Accepts either `POETRY_OVERRIDES = {...}` or
    `POETRY_OVERRIDES_ADD = {...}`. Returns {word: [syllables]}."""
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ("POETRY_OVERRIDES", "POETRY_OVERRIDES_ADD")
            for t in node.targets
        ):
            if isinstance(node.value, ast.Dict):
                out = {}
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and isinstance(v, (ast.List, ast.Tuple)):
                        out[k.value] = [e.value for e in v.elts if isinstance(e, ast.Constant)]
                return out
    return {}


def prefer_ssg_split(word, w2p_syls):
    """Orthography-preserving split: if ssg and w2p agree on syllable count
    and EVERY ssg syllable is sound-equivalent to the w2p one, prefer the ssg
    spelling. This keeps original orthography and tone marks (ใช้ not ไช้,
    ผู้ not พู่, สาคร -> สา-คร, ประชากร -> ประ-ชา-กร) — critical for เอก/โท.

    Rejects splits containing 1-char fragments or การันย์ syllables (Pali
    silent letters), and splits where any position is NOT sound-equivalent
    (e.g. พหล: ssg พ-หล vs w2p พะ-หลัน — หล vs หลัน is a real mismatch).

    Returns the ssg split as a list, or None to keep the w2p split.
    """
    try:
        ssg_syls = syllable_tokenize(word, engine="ssg")
    except Exception:
        return None
    if not ssg_syls or len(ssg_syls) != len(w2p_syls):
        return None
    for ws in ssg_syls:
        if len(ws) < 2 or "์" in ws:
            return None
    for ws, o in zip(ssg_syls, w2p_syls):
        try:
            if not kv.is_sumpus(ws, o):
                return None
        except Exception:
            return None
    return list(ssg_syls)


def compose_from_parts(word, covered):
    """If `word` fully decomposes into covered sub-words, return the
    concatenated syllable list built from the parts (safe by construction —
    no w2p inference, no hallucination). Prefers fewer/longer parts. Returns
    None if no full decomposition exists."""
    n = len(word)
    if n < 2:
        return None

    @lru_cache(maxsize=None)
    def rec(pos):
        if pos == n:
            return []
        best = None
        for end in range(pos + 1, n + 1):
            sub = word[pos:end]
            sub_syls = covered.get(sub)
            if sub_syls is None:
                continue
            r = rec(end)
            if r is not None:
                cand = list(sub_syls) + r
                if best is None or len(cand) < len(best):
                    best = cand
        return best

    return rec(0)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--corpus", default=DEFAULT_CORPUS,
                    help="folder of phraAphai_*_export.csv files")
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help="output .py path for the AUTO overrides")
    ap.add_argument("--gold", default=None,
                    help="(optional) extra gold dict file — values are never "
                         "regenerated and still screened. The old draft was "
                         "merged into poetry_overrides.py, so this is normally "
                         "unused.")
    ap.add_argument("--min-freq", type=int, default=3,
                    help="only AUTO words appearing at least this many times "
                         "(rare clean words are left to w2p at runtime)")
    ap.add_argument("--no-compose", dest="compose", action="store_false", default=True,
                    help="do NOT generate overrides for words that decompose into "
                         "covered parts (e.g. น้ำตา = น้ำ + ตา); they stay runtime-split")
    ap.add_argument("--review-lenient", action="store_true",
                    help="do NOT flag Pali words where ssg sees 1 syllable but w2p "
                         "split into 2+ (usually w2p-correct; cuts review noise)")
    args = ap.parse_args()

    print("=" * 92)
    print("STEP 1/6 — load GOLD layers (main dict + known fixes + optional draft) & corpus")
    main_dict = load_main_dict()
    covered = dict(main_dict)
    covered.update(KNOWN_GOLD_FIXES)
    print(f"   main overrides: {len(main_dict):,} keys")
    print(f"   known gold fixes: {len(KNOWN_GOLD_FIXES):,}")
    gold_dict = load_gold(args.gold) if args.gold and os.path.exists(args.gold) else {}
    if gold_dict:
        print(f"   extra gold file ({os.path.basename(args.gold)}): {len(gold_dict):,} keys")
    # screen the extra gold file: verified entries become gold, suspicious -> REVIEW
    draft_flagged = {}
    for w, syls in gold_dict.items():
        if w in covered:
            continue
        fl = screen_override(w, syls, flag_ssg1_countdiff=not args.review_lenient)
        if fl:
            draft_flagged[w] = (syls, fl)
        else:
            covered[w] = syls
    if gold_dict:
        print(f"   extra-gold flagged for review: {len(draft_flagged):,}")
    # screen the main dict itself: anything suspicious is ALWAYS surfaced to
    # REVIEW so you can see it without hunting through the dict. Uses the
    # high-signal (lenient) screening: dict entries are already trusted, so we
    # only surface tone changes / sound mismatches / bare fragments — not the
    # (mostly-correct) ssg-vs-w2p count disagreements of cluster words.
    dict_flagged = {}
    for w, syls in main_dict.items():
        if len(syls) < 2:
            continue
        fl = screen_override(w, syls, flag_ssg1_countdiff=False)
        if fl:
            dict_flagged[w] = (syls, fl)
    print(f"   main dict entries flagged for review: {len(dict_flagged):,} "
          f"(kept in dict, but listed in the review file)")
    big = build_corpus(args.corpus)
    print(f"   corpus: {len(big.splitlines()):,} waks")

    print("STEP 2/6 — build poetry trie (default dict + overrides)")
    trie = word_dict_trie()
    for k in covered:
        if len(k) > 1:
            trie.add(k)
    try:
        print(f"   trie ready ({trie._word_count} words)")
    except Exception:
        print("   trie ready")

    print("STEP 3/6 — tokenize corpus & count unique words")
    counts = defaultdict(int)
    first_ctx = {}
    for line in tqdm(big.splitlines(), desc="tokenizing waks"):
        for tok in word_tokenize(line, engine="newmm", custom_dict=trie):
            counts[tok] += 1
            if tok not in first_ctx:
                i = big.find(tok)
                first_ctx[tok] = (big[max(0, i - 8): i + len(tok) + 10]
                                  .replace("\n", "¦")) if i >= 0 else ""
    print(f"   unique tokens: {len(counts):,}")

    print("STEP 4/6 — compose from parts first, then w2p + prefer-orthography")
    candidates = [w for w in counts if w not in covered and w not in draft_flagged]
    entries = {}       # word -> [syllables] (w2p/ssg path, needs screening)
    composed = {}      # word -> [syllables] (built from covered parts, safe)
    for w in tqdm(sorted(candidates, key=lambda x: -counts[x]), desc="syllables"):
        if args.compose:
            comp = compose_from_parts(w, covered)
            if comp is not None:
                composed[w] = comp
                covered[w] = comp
                continue
        syls = list(process_w2p(w))
        better = prefer_ssg_split(w, syls)
        if better is not None:
            syls = better
        entries[w] = syls
    print(f"   composed from covered parts: {len(composed):,}  "
          f"| w2p-processed: {len(entries):,}")

    print("STEP 5/6 — screen & bucket")
    flagged = {}
    for w, syls in entries.items():
        if len(syls) < 2:
            continue
        fl = screen_override(w, syls, flag_ssg1_countdiff=not args.review_lenient)
        if fl:
            flagged[w] = (syls, fl)

    buckets = {"AUTO": [], "FIXED": [], "REVIEW": [], "SKIP": [], "COMPOSED": []}
    for w, syls in sorted(entries.items(), key=lambda kv: -counts[kv[0]]):
        if w in flagged:
            fixed, ok = safe_fix(w, syls)
            if ok:
                buckets["FIXED"].append((w, fixed))
                covered[w] = fixed
            else:
                buckets["REVIEW"].append((w, syls))
            continue
        if counts[w] < args.min_freq:
            buckets["SKIP"].append((w, syls))
            continue
        buckets["AUTO"].append((w, syls))
        covered[w] = syls
    for w, (syls, _fl) in draft_flagged.items():
        buckets["REVIEW"].append((w, syls))
    for w, (syls, _fl) in dict_flagged.items():
        buckets["REVIEW"].append((w, syls))
    for w, syls in composed.items():
        buckets["COMPOSED"].append((w, syls))

    def _write_dict(path, header, pairs):
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write("POETRY_OVERRIDES_ADD = {\n")
            for w, s in pairs:
                lst = ", ".join('"%s"' % x for x in s)
                f.write('    "%s": [%s],\n' % (w, lst))
            f.write("}\n")

    merge = sorted(
        buckets["AUTO"] + buckets["FIXED"] + buckets["COMPOSED"],
        key=lambda kv: (-counts[kv[0]], kv[0]),
    )
    _write_dict(
        args.out,
        f"# {os.path.basename(args.out)} — AUTO+FIXED+COMPOSED (safe to merge), "
        f"generated by build_overrides.py\n"
        f"# AUTO {len(buckets['AUTO']):,} + FIXED {len(buckets['FIXED']):,} + "
        f"COMPOSED {len(buckets['COMPOSED']):,} entries.\n"
        "# Paste into poetry_overrides.py. Deduped; main-dict/gold keys excluded.\n",
        merge,
    )
    review_out = args.out.replace(".py", "_review.py")
    review = sorted(buckets["REVIEW"], key=lambda kv: (-counts[kv[0]], kv[0]))
    _write_dict(
        review_out,
        f"# {os.path.basename(review_out)} — REVIEW REQUIRED, generated by build_overrides.py\n"
        "# THE review file: entries w2p likely hallucinated, PLUS suspicious\n"
        "# entries already in poetry_overrides.py (they stay in the dict but are\n"
        "# listed here so you can see them). Fix each syllable split by ear,\n"
        "# then edit poetry_overrides.py. See <out>.screen.tsv for reasons.\n",
        review,
    )

    out_tsv = args.out.replace(".py", ".screen.tsv")
    bucket_of = {}
    for name in buckets:
        for w, _ in buckets[name]:
            bucket_of[w] = name
    # TSV rows: entries (w2p path) + composed + draft_flagged + dict_flagged
    tsv_rows = dict(entries)
    tsv_rows.update(composed)
    tsv_rows.update({w: s for w, (s, _) in draft_flagged.items()})
    tsv_rows.update({w: s for w, (s, _) in dict_flagged.items()})
    with io.open(out_tsv, "w", encoding="utf-8") as f:
        f.write("word\tfreq\tsyllables\tflags\tbucket\tcontext\n")
        for w, syls in sorted(tsv_rows.items(), key=lambda kv: -counts[kv[0]]):
            fl = ";".join(flagged[w][1]) if w in flagged else ""
            if w in draft_flagged:
                fl = ";".join(draft_flagged[w][1])
            if w in dict_flagged:
                fl = ";".join(dict_flagged[w][1])
            f.write(f"{w}\t{counts[w]}\t{'-'.join(syls)}\t{fl}\t"
                    f"{bucket_of.get(w, '?')}\t{first_ctx.get(w, '')}\n")

    # ---- threshold analysis: how many words / coverage at each min-freq ----
    tot = sum(counts.values())
    main_occ = sum(v for w, v in counts.items() if w in main_dict)
    print()
    print("   THRESHOLD ANALYSIS (unique words / % of tokens covered if merged):")
    for th in (1, 2, 3, 5, 10):
        occ = sum(v for w, v in counts.items()
                  if w not in covered and w not in draft_flagged
                  and counts[w] >= th)
        n = sum(1 for w in counts if w not in covered and w not in draft_flagged
                and counts[w] >= th)
        print(f"     freq>={th:<3} {n:>6,} words  ->  +{occ / tot * 100:5.1f}% of tokens")

    def _occ(bucket_words):
        return sum(counts[w] for w, _ in bucket_words)

    print()
    print("   BUCKETS (word count / token occurrences):")
    for name in ("AUTO", "FIXED", "COMPOSED", "REVIEW", "SKIP"):
        b = buckets[name]
        print(f"     {name:<9} {len(b):>6,} words  {_occ(b) / tot * 100:6.2f}%  "
              f"({_occ(b):,} occ)")
    merged_occ = sum(_occ(buckets[n]) for n in ("AUTO", "FIXED", "COMPOSED"))
    runtime_covered = main_occ + merged_occ
    fall = tot - runtime_covered
    print()
    print("   AT RUNTIME (after you merge AUTO+FIXED+COMPOSED):")
    print(f"     dict-covered tokens        : {runtime_covered:,} ({runtime_covered / tot * 100:.1f}%)")
    print(f"     fall through to w2p        : {fall:,} ({fall / tot * 100:.1f}%) "
          f"= REVIEW({len(buckets['REVIEW']):,}) + SKIP({len(buckets['SKIP']):,})")
    print()
    print(f"   wrote {os.path.basename(args.out)}           "
          f"(AUTO {len(buckets['AUTO']):,} + FIXED {len(buckets['FIXED']):,} "
          f"+ COMPOSED {len(buckets['COMPOSED']):,})")
    print(f"   wrote {os.path.basename(review_out)} ({len(review):,} entries)")
    print(f"   wrote {os.path.basename(out_tsv)}      ({len(tsv_rows):,} rows)")
    print(f"\n   REVIEW LIST ({len(review):,} — the hallucination fixes; verify by ear):")
    for w, syls in review[:80]:
        if w in flagged:
            fl = "; ".join(flagged[w][1])
        elif w in draft_flagged:
            fl = "; ".join(draft_flagged[w][1])
        elif w in dict_flagged:
            fl = "; ".join(dict_flagged[w][1])
        else:
            fl = ""
        print(f"     {w:<16} {'-'.join(syls):<26} {fl:<44} {first_ctx.get(w, '')}")
    if len(review) > 80:
        print(f"     ... ({len(review) - 80:,} more in {os.path.basename(out_tsv)})")


if __name__ == "__main__":
    main()
