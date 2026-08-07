# -*- coding: utf-8 -*-
"""จังหวะ (beat) marker for กลอนแปด วรรค.

Per วรรค:
  tokenize (newmm + custom_dict)  keep proper nouns whole (no shatter)
  pronunciate (w2p) -> split '-'  spoken-syllable count per word
  classify by total syllables     canonical 3-beat pattern, or flag
  place ' | ' on word boundaries  crossing word: cut at VERIFIED written
                                  syllables (จังหวะ is spoken and does cut
                                  words: ข้าชื่อวิ | เชียรโมรา), else flag

Why the guards: newmm shatters rare/proper words (อินทคาม -> อิน|ท|คาม). The
orphan letter is really a linking syllable with implicit อะ (ท = ทะ, 1
syllable), but pronunciate hallucinates on it (น -> นะ-โจน = 2). So orphans
are counted as exactly 1 without asking pronunciate. If that assumption is
ever wrong the วรรค total goes off-canon and flags downstream — the meter is
the checksum. OVERRIDES remains for shatters into WRONG multi-char pieces.
"""
import csv
import json
import os
import re
from functools import lru_cache
from pythainlp.tokenize import Tokenizer, subword_tokenize, syllable_tokenize
from pythainlp.corpus import thai_words
from pythainlp.transliterate import pronunciate

from Noto_tokenizer import POETRY_OVERRIDES

THAI = r"[ก-ฮ]"

# Proper nouns / rare compounds newmm splits wrong. Every entry is verified
# against the corpus: นครา shifts the TOTAL (นค|รา = 8 not 9) in 82 วรรค; the
# other three keep the total but move word boundaries (สานน -> สาน|นก|ล), which
# the meter checksum CANNOT see. That blindness is why entries are earned, not
# guessed: a dict entry applies to all ~97k วรรค
# and Thai runs words together, so a plausible string like ตัวอย่า (ตัว + อย่า)
# silently rewrites unrelated วรรค at the same syllable count. Add one only
# after a real วรรค breaks, then re-check the corpus for collateral splits.
OVERRIDES = {"อินทคาม", "มไหสวรรย์", "สานน", "นครา"}

# Words w2p miscounts go in Noto_tokenizer.POETRY_OVERRIDES (full syllable
# lists — the count is len(); the syllables themselves feed rhyme work later).

# Real one-character words in classical verse — NOT shatter fragments.
SINGLE_CHAR_OK = {"ณ", "ธ", "บ", "ก", "อ", "ฤ", "ฦ", "ฤๅ", "ฦๅ"}

_tok = Tokenizer(custom_dict=set(thai_words()) | OVERRIDES, engine="newmm")


@lru_cache(maxsize=None)
def _count_syls(word):
    """Spoken syllables: POETRY_OVERRIDES (curated syllable map, shared with
    the Noto validator) -> ssg bypass for <=2-char words (w2p hallucinates:
    ก -> กะ-โหฺมด) -> w2p, counting ITS OWN '-' boundaries. Noto's ssg
    re-segmentation of the joined phonetic string is deliberately skipped:
    it merges syllables (เสนา -> 1, so อัปยศอดสูเสนาใน fell to 6 = opener
    and left the review queue SILENTLY).

    Cached: w2p dominates runtime and words repeat ~2.5x per ตอน (2940 tokens,
    1160 unique in ep.1), so the cache halves a scan. --csv and --import each
    re-scan the same file, where it pays again."""
    if word in POETRY_OVERRIDES:
        return len(POETRY_OVERRIDES[word])
    if len(word) <= 2:
        return len(syllable_tokenize(word, engine="ssg")) or 1
    spoken = pronunciate(word, engine="w2p")
    if not spoken:
        return len(syllable_tokenize(word, engine="ssg")) or 1
    return len([s for s in spoken.split("-") if s.strip()]) or 1


def _is_orphan(tok):
    """Lone Thai consonant = newmm shattered a word. It's a linking syllable
    (consonant + implicit อะ: ค = คะ) — count 1, don't let pronunciate invent
    syllables from it. Whitelisted 1-char words excepted."""
    return len(tok) == 1 and re.fullmatch(THAI, tok) and tok not in SINGLE_CHAR_OK


def _pattern(total, counts):
    """Canonical 3-beat pattern by syllable total, or (None, reason)."""
    if total == 8:
        return [3, 2, 3], None
    if total == 9:
        # a LONE 4-syllable word at an edge bends [3,3,3] -> [4,2,3]/[3,2,4]
        longs = [i for i, c in enumerate(counts) if c >= 4]
        if len(longs) == 1 and longs[0] == 0:
            return [4, 2, 3], None
        if len(longs) == 1 and longs[0] == len(counts) - 1:
            return [3, 2, 4], None
        if longs:
            return None, "4-syllable word not at วรรค edge"
        return [3, 3, 3], None
    if total == 7:
        return [3, 2, 2], "7 syllables — ambiguous, [3,2,2] is only a guess"
    return None, None  # openers (<=6) / irregular (>=10) handled by caller


def _syllable_split(word, expect):
    """(piece, syls) list from written-syllable tokenization, or None when the
    split can't be trusted: <2 pieces, pieces don't rejoin to the word, or the
    pieces' spoken counts don't sum to the whole word's (w2p reads เกสร alone
    as 2 syl — เกด-สอน, really เก-สอน — but as a compound tail it's 1: เกด.
    A mismatch would silently shift the วรรค total)."""
    pieces = subword_tokenize(word, engine="dict")
    if len(pieces) < 2 or "".join(pieces) != word:
        return None
    counts = [_count_syls(p) for p in pieces]
    if sum(counts) != expect:
        return None
    return list(zip(pieces, counts))


def _place_beats(words, counts, pattern):
    """Join words into 3 beats at the pattern's syllable lines. จังหวะ is spoken,
    so a beat line may fall INSIDE a word (ข้าชื่อวิ | เชียรโมรา): a crossing
    word is cut at written-syllable boundaries when _syllable_split verifies the
    cut, else kept whole and flagged. Returns (segmented_text, straddled?)."""
    bounds = [pattern[0], pattern[0] + pattern[1]]   # cumulative syllable lines
    beats, straddle, pos, bi = [[], [], []], False, 0, 0
    units = [(w, c, True) for w, c in zip(words, counts)]  # (text, syls, may_split)
    i = 0
    while i < len(units):
        w, c, may_split = units[i]
        if bi < 2 and pos + c > bounds[bi] and may_split:
            pieces = _syllable_split(w, c)
            if pieces:
                # ponytail: one split level only — a multi-syllable PIECE that
                # still crosses a line flags rather than re-splitting into junk.
                # That also bounds the loop: _syllable_split guarantees >=2
                # pieces and the pieces carry may_split=False, so the retry at
                # the same i cannot split again — every `continue` makes progress.
                units[i:i + 1] = [(p, pc, False) for p, pc in pieces]
                continue                             # re-place this position as pieces
        beats[bi].append(w)
        pos += c
        if bi < 2 and pos >= bounds[bi]:
            if pos > bounds[bi]:                     # crossed the line uncut
                straddle = True
            bi += 1
        i += 1
    return " | ".join("".join(b) for b in beats), straddle


def analyze_wak(text):
    """Mark one วรรค. Unsure -> flag; never emit a wrong slice silently."""
    words, counts, flags = [], [], []
    for t in _tok.word_tokenize(text):
        if not re.search(THAI, t):                   # drop spaces, ๏, ฯ, punctuation
            continue
        words.append(t)
        counts.append(1 if _is_orphan(t) else _count_syls(t))
    total = sum(counts)

    if total <= 6:
        kind, pattern, note = "opener", None, "opener (<=6 syllables) — short วรรค, expected"
    elif total >= 10:
        kind, pattern, note = "irregular", None, f"{total} syllables — likely shatter/miscount"
    else:
        kind = "body"
        pattern, note = _pattern(total, counts)

    if pattern:
        segmented, straddle = _place_beats(words, counts, pattern)
        if straddle:
            flags.append("word straddles a beat boundary")
    else:
        segmented = "".join(words)

    if note:
        flags.append(note)

    return {
        "wak": text,
        "kind": kind,
        "total_syllables": total,
        "rhythm": pattern,
        "segmented": segmented,
        "needs_review": bool(flags) and kind != "opener",
        "flags": flags,
        "words": list(zip(words, counts)),
    }

def scan_ton(text):
    """Scan a whole ตอน. วรรค = whitespace-separated Thai runs (๏/ฯ drop out
    because they carry no ก-ฮ). Returns (results, flag_rate, sections).

    ๏ (ฟองมัน) is a section anchor (~every 6 บท), not a per-บท marker. Each
    ๏-to-๏ section must hold a multiple of 4 วรรค: a merge already self-flags
    as irregular (>=10 syl), but a DROPPED วรรค is invisible per-วรรค — only
    this checksum catches it, before it shifts every later บท grouping.
    sections = [(start_wak_index, n_waks, ok)], empty if the text has no ๏.
    ponytail: two วรรค with no space between merge into one token -> flagged as
    irregular, so a bad split self-announces rather than passing silently."""
    waks, anchors = [], []
    for t in re.split(r"\s+", text):
        if "๏" in t:                      # standalone ๏ or glued ๏วรรค
            anchors.append(len(waks))
        if re.search(THAI, t):
            waks.append(t)
    results = [analyze_wak(w) for w in waks]
    rate = sum(r["needs_review"] for r in results) / len(results) if results else 0.0
    # วรรค before the first ๏ (e.g. a title line) form a section too — check them.
    bounds = ([0] if anchors and anchors[0] != 0 else []) + anchors + [len(waks)]
    sections = [(a, b - a, (b - a) % 4 == 0) for a, b in zip(bounds, bounds[1:])]
    return results, rate, sections

def _manual_cuts(seg, words, total):
    """Typed cuts ('beat1 | beat2 | beat3') -> checkpoint entry, or None if the
    cuts don't yield exactly 3 จังหวะ, or the typed text doesn't rejoin to the
    วรรค (cuts only, no edits). rhythm becomes None when the per-beat counts
    don't sum to the วรรค total (fragment pronunciation is unreliable) — the
    cuts still stand.

    The 3-beat rule is what stops a half-filled row becoming a 'resolved' วรรค:
    an entry with fewer beats exports with empty cells AND drops out of the
    review queue (--csv skips anything already in review.json), so it would go
    silently missing from both sides."""
    pieces = ["".join(p.split()) for p in seg.split("|")]
    if len(pieces) != 3 or not all(pieces):
        return None
    if "".join(pieces) != "".join(words):
        return None
    rhythm = [_count_syls(p) for p in pieces]
    if sum(rhythm) != total:
        rhythm = None
    return {"rhythm": rhythm, "segmented": " | ".join(pieces)}


def resolve_ton(path):
    """Interactive pass over a ตอน's flagged วรรค. Every answer is written to
    <path>.review.json IMMEDIATELY (keyed by วรรค text), so review survives
    quitting mid-episode; re-running skips answered วรรค. The JSONL writer
    will overlay these answers on the auto-guesses."""
    ck_path = path + ".review.json"
    ck = {}
    if os.path.exists(ck_path):
        with open(ck_path, encoding="utf-8") as fh:
            ck = json.load(fh)

    def save(wak, entry):
        ck[wak] = entry
        with open(ck_path, "w", encoding="utf-8") as fh:
            json.dump(ck, fh, ensure_ascii=False, indent=1)

    with open(path, encoding="utf-8") as fh:
        results, _, _ = scan_ton(fh.read())
    queue = [r for r in results if r["needs_review"] and r["wak"] not in ck]
    print(f"{len(queue)} วรรค to resolve ({len(ck)} already answered in {os.path.basename(ck_path)})")

    for n, r in enumerate(queue, 1):
        words = [w for w, _ in r["words"]]
        print(f"\n[{n}/{len(queue)}] {r['wak']}  ({r['total_syllables']} syl, {r['kind']})")
        print("  words: " + "  ".join(f"{w}({c})" for w, c in r["words"]))
        print(f"  auto:  {r['segmented']}   rhythm={r['rhythm']}")
        for f in r["flags"]:
            print(f"  flag:  {f}")
        while True:
            try:
                ans = input("  type cuts 'beat1 | beat2 | beat3'  (0=keep auto, x=exclude, s=later, q=quit) > ").strip()
            except EOFError:                          # piped answers ran out / Ctrl+Z
                ans = "q"
            if ans == "q":
                print(f"saved {len(ck)} answers -> {ck_path}")
                return
            if ans == "s":                            # unanswered: reappears next run
                break
            if ans == "x":
                save(r["wak"], {"exclude": True})
                break
            if ans == "0":
                if r["rhythm"] is None:      # irregular วรรค: there are no beats
                    print("  !! no auto guess to keep (rhythm=None) — type cuts, "
                          "or x to exclude, or s to defer")
                    continue
                save(r["wak"], {"rhythm": r["rhythm"], "segmented": r["segmented"]})
                break
            if "|" in ans:
                entry = _manual_cuts(ans, words, r["total_syllables"])
                if entry is None:
                    print("  !! need exactly 3 จังหวะ, and cuts only — no edits")
                    continue
                save(r["wak"], entry)
                break
            # anything else: re-ask
    print(f"done — {len(ck)} answers in {ck_path}")


# Output layout: sources live in PhraAphai/, results split by state under
# Results/. The .review.json checkpoint stays beside its source .txt.
_ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT_DIR = os.path.join(_ROOT, "Results", "Export", "ok")
ATTENTION_DIR = os.path.join(_ROOT, "Results", "Export", "not_ok")
# Evaluate is a sibling FORMAT, not a held-out split: every ตอน can appear in
# both folders. This repo only prepares data — the train/eval split is the
# training code's job, and it must not draw eval ตอน from Export/ok.
EVAL_DIR = os.path.join(_ROOT, "Results", "Evaluate")


def _out_paths(path):
    """(export_csv, attention_csv) for a source ตอน, routed to the Results/
    folders by basename. Dirs are created if missing so a fresh clone works."""
    base = os.path.splitext(os.path.basename(path))[0]
    os.makedirs(EXPORT_DIR, exist_ok=True)
    os.makedirs(ATTENTION_DIR, exist_ok=True)
    return (os.path.join(EXPORT_DIR, base + "_ok.csv"),
            os.path.join(ATTENTION_DIR, base + "_not_ok.csv"))


def _load_review(path):
    ck_path = path + ".review.json"
    if os.path.exists(ck_path):
        with open(ck_path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _bots(sections):
    """([[ (i,j,k,l), ... ] per ๏ act], acts_skipped) — วรรค indices per บท.

    An act whose วรรค count is neither 4k nor 4k+3 is dropped: a วรรค was lost or
    merged there, so every บท boundary after it is guesswork. The +3 form cuts
    the 3-วรรค วรรครับ opener บท. Kept as one helper so the training export and
    the eval writer can never disagree about where a บท starts."""
    out, skipped = [], 0
    for start, n, _ in sections:
        rem = n % 4
        if rem not in (0, 3):
            skipped += 1
            continue
        out.append([tuple(range(i, i + 4))
                    for i in range(start + rem, start + n, 4)])
    return out, skipped


def write_csv(path, window=2):
    """ตอน file -> two CSVs (utf-8-sig so Excel reads Thai):
    <stem>_ok.csv        clean overlapping `window`-บท rows, columns w1_a..wN_c
                         (stride 1 within a ๏ act — every สัมผัสระหว่างบท pair
                         appears; the 3-วรรค วรรครับ opener บท is cut)
    <stem>_not_ok.csv    ONE ROW PER unresolved flagged วรรค. The auto-guess
                         sits in a read-only `guess` column and a/b/c ship
                         EMPTY: an unedited file imports NOTHING, so a review
                         is always typed, never defaulted (copy `guess` across
                         when you agree). 'x' in a excludes, blank defers.
    Answers in <path>.review.json overlay automatically; a บท with an
    excluded/unresolved วรรค blocks its windows (no false rhyme pair).
    Details (rhythms, counts, provenance) are printed by scan, not stored."""
    stats = {"export_rows": 0, "attention_rows": 0, "bot_clean": 0,
             "bot_blocked": 0, "sections_skipped": 0, "empty": False,
             "export": None, "attention": None}
    ck = _load_review(path)
    with open(path, encoding="utf-8") as fh:
        results, _, sections = scan_ton(fh.read())
    if not results:                          # empty/blank source: write nothing
        stats["empty"] = True
        return stats
    stats["export"], stats["attention"] = _out_paths(path)

    def cells(r):
        """3 beat cells for a clean/resolved วรรค; None = blocks its บท."""
        e = ck.get(r["wak"])
        if e is not None:
            if e.get("exclude") or not e.get("segmented"):   # excluded or malformed
                return None                                  # -> block, never guess
            seg = e["segmented"]
        elif r["needs_review"]:
            return None
        else:
            seg = r["segmented"]
        return (seg.split(" | ") + ["", ""])[:3]

    with open(stats["export"], "w", encoding="utf-8-sig", newline="") as fe, \
         open(stats["attention"], "w", encoding="utf-8-sig", newline="") as fa:
        we, wa = csv.writer(fe), csv.writer(fa)
        we.writerow([f"w{i}_{b}" for i in range(1, 4 * window + 1) for b in "abc"])
        wa.writerow(["wak", "syllables", "flag", "guess", "a", "b", "c"])

        seen = set()
        for r in results:                          # attention file: poem order
            if r["needs_review"] and r["wak"] not in ck and r["wak"] not in seen:
                seen.add(r["wak"])   # review.json is keyed by text: 1 row per unique
                wa.writerow([r["wak"], r["total_syllables"], "; ".join(r["flags"]),
                             r["segmented"], "", "", ""])
                stats["attention_rows"] += 1

        acts, stats["sections_skipped"] = _bots(sections)
        for act in acts:
            bots = []
            for idx in act:
                vs = [cells(results[j]) for j in idx]
                bots.append(vs if all(v is not None for v in vs) else None)
            run = []
            for bv in bots + [None]:               # sentinel flushes last run
                if bv is not None:
                    run.append(bv)
                    continue
                for k in range(len(run) - window + 1):
                    we.writerow([c for bot in run[k:k + window] for v in bot for c in v])
                    stats["export_rows"] += 1
                run = []
            stats["bot_clean"] += sum(1 for b in bots if b is not None)
            stats["bot_blocked"] += sum(1 for b in bots if b is None)
    return stats


def write_eval(path):
    """ตอน -> Results/Evaluate/<stem>_ok.csv, ONE บท PER ROW, columns w1..w4
    (utf-8-sig so Excel reads Thai, same as the export CSVs).

    Deliberately NOT the training export: no beat cuts (evaluation reads whole
    วรรค, so [3,3,3]/[3,2,3] is training-side machinery) and no sliding windows
    (an interleaved window scores the same บท two or three times, which quietly
    weights whatever it overlaps).

    A บท is kept when all 4 วรรค are `body` — that is the TEXT check: `irregular`
    means >=10 syllables (a merge or shatter) and `opener` means <=6, both signs
    the line itself is wrong. Beat flags do NOT block: 'straddles a beat
    boundary' and '7 syllables — ambiguous' say the จังหวะ is uncertain, not the
    text, and eval never looks at จังหวะ. A human 'exclude' still blocks — that
    is a judgement about the line, not the beats.

    Uses no review.json answers beyond excludes, so eval data needs no review
    pass to be usable."""
    ck = _load_review(path)
    with open(path, encoding="utf-8") as fh:
        results, _, sections = scan_ton(fh.read())
    os.makedirs(EVAL_DIR, exist_ok=True)
    out = os.path.join(EVAL_DIR, os.path.splitext(os.path.basename(path))[0] + "_ok.csv")

    def ok(r):
        return r["kind"] == "body" and not (ck.get(r["wak"]) or {}).get("exclude")

    acts, skipped = _bots(sections)
    kept = blocked = 0
    with open(out, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["w1", "w2", "w3", "w4"])
        for act in acts:
            for idx in act:
                bot = [results[j] for j in idx]
                if all(ok(r) for r in bot):
                    w.writerow([r["wak"] for r in bot])
                    kept += 1
                else:
                    blocked += 1
    return {"eval": out, "bot_kept": kept, "bot_blocked": blocked,
            "sections_skipped": skipped}


def import_attention(path):
    """Merge an edited <stem>_not_ok.csv into <path>.review.json. Only rows
    with TYPED a/b/c cells count as reviewed — a/b/c ship empty and the machine
    guess sits in the read-only `guess` column, so importing an untouched file
    is a no-op instead of laundering 35 guesses into ground truth. Guard: the
    beat cells must rejoin EXACTLY to the วรรค (cuts only, no edits — Excel
    autocorrect gets caught here). 'x' in cell a = exclude; blank row = defer,
    it reappears on the next --csv. Rerun --csv after importing: recovered
    windows move into the export file."""
    _, att = _out_paths(path)
    if not os.path.exists(att):
        print(f"  !! no {att} — run --csv first")
        return 0, 0
    with open(path, encoding="utf-8") as fh:
        results, _, _ = scan_ton(fh.read())
    by_wak = {r["wak"]: r for r in results}

    ck = _load_review(path)
    ok = bad = blank = 0
    with open(att, encoding="utf-8-sig", newline="") as fh:
        rows = csv.DictReader(fh)
        # pre-`guess` files hold the machine guess in a/b/c; importing one would
        # confirm every guess as reviewed. Refuse it — --csv rewrites the file.
        if "guess" not in (rows.fieldnames or []):
            print(f"  !! {os.path.basename(att)} is the old prefilled format — "
                  f"rerun --csv to regenerate it, then edit")
            return 0, 0
        for row in rows:
            wak = (row.get("wak") or "").strip()
            r = by_wak.get(wak)
            if r is None:
                print(f"  !! unknown วรรค (wak cell edited?): {wak}")
                bad += 1
                continue
            abc = [(row.get(k) or "").strip() for k in "abc"]
            if not any(abc):                          # untouched row: deferred
                blank += 1
                continue
            if abc[0].lower() == "x":
                ck[wak] = {"exclude": True}
                ok += 1
                continue
            entry = _manual_cuts(" | ".join(c for c in abc if c),
                                 [w for w, _ in r["words"]], r["total_syllables"])
            if entry is None:
                print(f"  !! cells don't rejoin to the วรรค — cuts only, no edits: {wak}")
                bad += 1
                continue
            ck[wak] = entry
            ok += 1
    summary = f"imported {ok}, rejected {bad}, blank/deferred {blank}"
    if ok:                                            # nothing accepted -> no file
        with open(path + ".review.json", "w", encoding="utf-8") as fh:
            json.dump(ck, fh, ensure_ascii=False, indent=1)
        summary += f" -> {path}.review.json"
    print(summary)
    return ok, bad


if __name__ == "__main__":
    import sys
    from collections import Counter

    for stream in (sys.stdout, sys.stderr, sys.stdin):  # Windows: Thai, not mojibake —
        stream.reconfigure(encoding="utf-8")            # stderr too, sys.exit(msg) uses it

    USAGE = ("usage: python CleanData.py <ตอน.txt> [--csv | --import | --resolve | --eval]\n"
             "       python CleanData.py --wak <วรรค|word> ...   (probe, no file)\n"
             "       python test_cleandata.py                    (self-checks)")

    if len(sys.argv) > 1:                              # driver: scan / resolve a ตอน file
        args = [a for a in sys.argv[1:] if not a.startswith("-")]
        if "--wak" in sys.argv:                        # probe any วรรค/word, no file needed
            for t in args:
                r = analyze_wak(t)
                print(f"\n{t}  ({r['total_syllables']} syl, {r['kind']})")
                for w, c in r["words"]:
                    print(f"  {w:<12} {pronunciate(w, engine='w2p')}  ({c})")
                if r["rhythm"]:
                    print(f"  beats: {r['segmented']}   {r['rhythm']}")
                for f in r["flags"]:
                    print(f"  flag:  {f}")
            sys.exit()
        if not args:
            sys.exit(USAGE)
        path = args[0]
        if "--resolve" in sys.argv:
            resolve_ton(path)
            sys.exit()
        if "--csv" in sys.argv:
            s = write_csv(path)
            if s.get("empty"):
                print(f"skipped:    {path} has no วรรค (empty file?) — nothing written")
                sys.exit()
            print(f"export:     {s['export_rows']} rows -> {s['export']}")
            print(f"attention:  {s['attention_rows']} วรรค to fix -> {s['attention']}")
            print(f"บท:         {s['bot_clean']} clean, {s['bot_blocked']} blocked (วรรครับ opener cut)")
            if s["sections_skipped"]:
                print(f"๏ sections skipped (bad %4): {s['sections_skipped']}")
            sys.exit()
        if "--eval" in sys.argv:
            s = write_eval(path)
            print(f"eval:       {s['bot_kept']} บท (1 per row, columns w1..w4) -> {s['eval']}")
            print(f"blocked:    {s['bot_blocked']} บท with a non-body วรรค (>=10 or <=6 syllables)")
            if s["sections_skipped"]:
                print(f"๏ acts skipped (bad %4): {s['sections_skipped']}")
            print("NOTE: this is a FORMAT, not a split — the same ตอน is also in Export/ok.")
            print("      whoever trains must hold the eval ตอน out, or it scores memorisation.")
            sys.exit()
        if "--import" in sys.argv:
            import_attention(path)
            sys.exit()
        with open(path, encoding="utf-8") as fh:
            results, rate, sections = scan_ton(fh.read())
        kinds = Counter(r["kind"] for r in results)
        orphans = sum(1 for r in results for w, _ in r["words"] if _is_orphan(w))
        print(f"วรรค scanned: {len(results)}")
        print(f"flag rate:    {rate:.1%}  ({sum(r['needs_review'] for r in results)} flagged)")
        print("by kind:      " + ", ".join(f"{k}={v}" for k, v in kinds.items()))
        print(f"orphan letters assumed คะ-style (1 syl): {orphans}")
        bad = [s for s in sections if not s[2]]
        if sections:
            print(f"๏ sections:   {len(sections)}, bad: {len(bad)}")
            for start, n, _ in bad:
                print(f"      - วรรค[{start}..{start + n - 1}]: {n} วรรค, not x4 — a วรรค was lost or merged here")
        else:
            print("๏ sections:   no ๏ found — checksum skipped")
        print("verdict:      " + (">20% — chase an upstream bug" if rate > 0.20 else "foundation holds — grow OVERRIDES from flags"))
        print("-" * 60)
        for i, r in enumerate(results):
            if r["needs_review"]:
                print(f"[{i}] {r['wak']}  ({r['total_syllables']} syl, {r['kind']})")
                for f in r["flags"]:
                    print(f"      - {f}")
        sys.exit()

    sys.exit(USAGE)   # self-checks live in test_cleandata.py (pytest or python)
