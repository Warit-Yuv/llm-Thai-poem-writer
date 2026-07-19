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
import re # Regular expressions for Thai character ranges
from pythainlp.tokenize import Tokenizer, subword_tokenize
from pythainlp.corpus import thai_words
from pythainlp.transliterate import pronunciate

THAI = r"[ก-ฮ]"

# Proper nouns / rare compounds newmm shatters into WRONG multi-char pieces.
# (Orphan-letter shatters no longer need entries — orphans count as 1 syllable.)
OVERRIDES = {"อินทคาม", "มไหสวรรย์", "สานน", "วิเชียร", "โมรา"}

# Real one-character words in classical verse — NOT shatter fragments.
SINGLE_CHAR_OK = {"ณ", "ธ", "บ", "ก", "อ", "ฤ"}

_tok = Tokenizer(custom_dict=set(thai_words()) | OVERRIDES, engine="newmm")


def _count_syls(word):
    """Spoken syllables: pronunciate then split '-'. Phonetic, so it fixes
    orthographic undercount (มนุษย์ = มะ-นุด = 2, not 1)."""
    spoken = pronunciate(word, engine="w2p")
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
    pieces' spoken counts don't sum to the whole word's (เกสร alone = เกด-สอน
    but in compounds = เกด — a mismatch would silently shift the วรรค total)."""
    pieces = subword_tokenize(word, engine="dict")
    if len(pieces) < 2 or "".join(pieces) != word:
        return None
    counts = [_count_syls(p) for p in pieces]
    if sum(counts) != expect:
        return None
    return list(zip(pieces, counts))


def _group(words, counts, pattern):
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
        segmented, straddle = _group(words, counts, pattern)
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
    typed text doesn't rejoin to the วรรค (cuts only, no edits). rhythm becomes
    None when the per-beat counts don't sum to the วรรค total (fragment
    pronunciation is unreliable) — the cuts still stand."""
    pieces = ["".join(p.split()) for p in seg.split("|")]
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
                save(r["wak"], {"rhythm": r["rhythm"], "segmented": r["segmented"]})
                break
            if "|" in ans:
                entry = _manual_cuts(ans, words, r["total_syllables"])
                if entry is None:
                    print("  !! text mismatch — place cuts only, no edits")
                    continue
                save(r["wak"], entry)
                break
            # anything else: re-ask
    print(f"done — {len(ck)} answers in {ck_path}")


def _load_review(path):
    ck_path = path + ".review.json"
    if os.path.exists(ck_path):
        with open(ck_path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def write_csv(path, window=2):
    """ตอน file -> two CSVs (utf-8-sig so Excel reads Thai):
    <stem>_export.csv    clean overlapping `window`-บท rows, columns w1_a..wN_c
                         (stride 1 within a ๏ act — every สัมผัสระหว่างบท pair
                         appears; the 3-วรรค วรรครับ opener บท is cut)
    <stem>_attention.csv ONE ROW PER unresolved flagged วรรค, beat guess
                         prefilled. Fix the cells / put 'x' in a to exclude /
                         delete the row to defer, then --import.
    Answers in <path>.review.json overlay automatically; a บท with an
    excluded/unresolved วรรค blocks its windows (no false rhyme pair).
    Details (rhythms, counts, provenance) are printed by scan, not stored."""
    ck = _load_review(path)
    with open(path, encoding="utf-8") as fh:
        results, _, sections = scan_ton(fh.read())

    def cells(r):
        """3 beat cells for a clean/resolved วรรค; None = blocks its บท."""
        e = ck.get(r["wak"])
        if e is not None:
            if e.get("exclude"):
                return None
            seg = e["segmented"]
        elif r["needs_review"]:
            return None
        else:
            seg = r["segmented"]
        return (seg.split(" | ") + ["", ""])[:3]

    stem = os.path.splitext(path)[0]
    stats = {"export_rows": 0, "attention_rows": 0, "bot_clean": 0,
             "bot_blocked": 0, "sections_skipped": 0,
             "export": stem + "_export.csv", "attention": stem + "_attention.csv"}
    with open(stats["export"], "w", encoding="utf-8-sig", newline="") as fe, \
         open(stats["attention"], "w", encoding="utf-8-sig", newline="") as fa:
        we, wa = csv.writer(fe), csv.writer(fa)
        we.writerow([f"w{i}_{b}" for i in range(1, 4 * window + 1) for b in "abc"])
        wa.writerow(["wak", "syllables", "flag", "a", "b", "c"])

        for r in results:                          # attention file: poem order
            if r["needs_review"] and r["wak"] not in ck:
                wa.writerow([r["wak"], r["total_syllables"], "; ".join(r["flags"])]
                            + (r["segmented"].split(" | ") + ["", ""])[:3])
                stats["attention_rows"] += 1

        for start, n, _ in sections:
            rem = n % 4
            if rem not in (0, 3):
                stats["sections_skipped"] += 1
                continue
            bots = []
            for i in range(start + rem, start + n, 4):   # +rem cuts the opener บท
                vs = [cells(results[j]) for j in range(i, i + 4)]
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


def import_attention(path):
    """Merge an edited <stem>_attention.csv into <path>.review.json. Every row
    present = confirmed; guard: the beat cells must rejoin EXACTLY to the วรรค
    (cuts only, no edits — Excel autocorrect gets caught here). 'x' in cell a =
    exclude. Deleted rows simply reappear on the next --csv. Rerun --csv after
    importing: recovered windows move into the export file."""
    att = os.path.splitext(path)[0] + "_attention.csv"
    with open(path, encoding="utf-8") as fh:
        results, _, _ = scan_ton(fh.read())
    by_wak = {r["wak"]: r for r in results}

    ck = _load_review(path)
    ok = bad = 0
    with open(att, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            wak = (row.get("wak") or "").strip()
            r = by_wak.get(wak)
            if r is None:
                print(f"  !! unknown วรรค (wak cell edited?): {wak}")
                bad += 1
                continue
            if (row.get("a") or "").strip().lower() == "x":
                ck[wak] = {"exclude": True}
                ok += 1
                continue
            seg = " | ".join(c for c in ((row.get(k) or "").strip() for k in "abc") if c)
            entry = _manual_cuts(seg, [w for w, _ in r["words"]], r["total_syllables"])
            if entry is None:
                print(f"  !! cells don't rejoin to the วรรค — cuts only, no edits: {wak}")
                bad += 1
                continue
            ck[wak] = entry
            ok += 1
    with open(path + ".review.json", "w", encoding="utf-8") as fh:
        json.dump(ck, fh, ensure_ascii=False, indent=1)
    print(f"imported {ok}, rejected {bad} -> {path}.review.json")
    return ok, bad


if __name__ == "__main__":
    import sys
    from collections import Counter

    if len(sys.argv) > 1:                              # driver: scan / resolve a ตอน file
        sys.stdout.reconfigure(encoding="utf-8")       # Windows: print Thai, not mojibake
        sys.stdin.reconfigure(encoding="utf-8")        # ...and read typed/piped Thai answers
        path = [a for a in sys.argv[1:] if not a.startswith("-")][0]
        if "--resolve" in sys.argv:
            resolve_ton(path)
            sys.exit()
        if "--csv" in sys.argv:
            s = write_csv(path)
            print(f"export:     {s['export_rows']} rows -> {s['export']}")
            print(f"attention:  {s['attention_rows']} วรรค to fix -> {s['attention']}")
            print(f"บท:         {s['bot_clean']} clean, {s['bot_blocked']} blocked (วรรครับ opener cut)")
            if s["sections_skipped"]:
                print(f"๏ sections skipped (bad %4): {s['sections_skipped']}")
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

    # no file arg -> self-check on real วรรค: the custom_dict fix + both flag types.
    a = analyze_wak("พระอย่าได้ถือความข้าสามคน")       # clean 8
    assert a["total_syllables"] == 8 and a["rhythm"] == [3, 2, 3], a

    b = analyze_wak("ทั้งสามคนคู่ชีวิตเป็นมิตรกัน")      # clean 9
    assert b["total_syllables"] == 9 and b["rhythm"] == [3, 3, 3], b

    c = analyze_wak("ดนตรีมีคุณที่ข้อไหน")              # genuine 7 -> flagged
    assert c["total_syllables"] == 7 and c["needs_review"], c

    d = analyze_wak("ข้าชื่อวิเชียรโมราเจ้าสานน")       # was 10 via shatter; override -> 9
    assert d["total_syllables"] == 9, d
    # beat line falls inside วิเชียร -> auto-split at written syllables, no flag
    assert d["segmented"] == "ข้าชื่อวิ | เชียรโมรา | เจ้าสานน", d
    assert not d["needs_review"], d

    e = analyze_wak("สนมนางแสนสุรางคนิกร")             # orphan ค = คะ (1 syl): was 10-irregular
    assert e["total_syllables"] == 9 and e["rhythm"] == [3, 3, 3], e
    assert e["segmented"] == "สนมนาง | แสนสุราง | คนิกร" and not e["needs_review"], e

    # the split guard: วิเชียร verifiable; มนุษย์ (1 piece) and เกสร (piece
    # counts 2+2 != spoken 2... เกด-สอน vs compound เกด) must refuse
    assert _syllable_split("วิเชียร", 2) == [("วิ", 1), ("เชียร", 1)]
    assert _syllable_split("มนุษย์", 2) is None
    assert _syllable_split("ปทุมเกสร", 3) is None

    # resolve-menu typed cuts: valid cuts pass, edited text refuses
    m = _manual_cuts("ข้าชื่อวิ | เชียรโมรา | เจ้าสานน",
                     ["ข้า", "ชื่อ", "วิเชียร", "โมรา", "เจ้า", "สานน"], 9)
    assert m == {"rhythm": [3, 3, 3], "segmented": "ข้าชื่อวิ | เชียรโมรา | เจ้าสานน"}, m
    assert _manual_cuts("ข้าชื่อ | ผิดๆ | เจ้าสานน",
                        ["ข้า", "ชื่อ", "วิเชียร", "โมรา", "เจ้า", "สานน"], 9) is None

    # ๏ checksum: 4-วรรค section ok, 3-วรรค section bad; glued ๏วรรค counts too.
    _, _, secs = scan_ton("๏กากา กากา กากา กากา ๏ กากา กากา กากา")
    assert secs == [(0, 4, True), (4, 3, False)], secs
    _, _, secs = scan_ton("กากา กากา")            # no ๏ -> checksum skipped
    assert secs == [], secs

    # CSV round-trip: act1 = 2 clean บท -> 1 export row; act2 = flagged วรรค
    # blocks its บท -> 1 attention row, no export; act3 = bad %4 -> skipped.
    # Then fix the attention row, --import, rewrite: export grows, attention empties.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("๏ " + " ".join(["กากา"] * 8)
                     + " ๏ ดนตรีมีคุณที่ข้อไหน " + " ".join(["กากา"] * 7)
                     + " ๏ กากา")
        s = write_csv(p)
        assert s["export_rows"] == 1 and s["attention_rows"] == 1, s
        assert s["bot_clean"] == 3 and s["bot_blocked"] == 1, s
        assert s["sections_skipped"] == 1, s
        with open(s["export"], encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        assert rows[0][:4] == ["w1_a", "w1_b", "w1_c", "w2_a"] and len(rows[0]) == 24
        assert rows[1] == ["กากา", "", ""] * 8, rows[1]

        with open(s["attention"], encoding="utf-8-sig", newline="") as fh:
            att = list(csv.DictReader(fh))
        assert att[0]["wak"] == "ดนตรีมีคุณที่ข้อไหน", att
        att[0]["a"], att[0]["b"], att[0]["c"] = "ดนตรี", "มีคุณ", "ที่ข้อไหน"
        with open(s["attention"], "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=att[0].keys())
            w.writeheader()
            w.writerows(att)
        ok, bad = import_attention(p)
        assert (ok, bad) == (1, 0), (ok, bad)
        s = write_csv(p)
        assert s["export_rows"] == 2 and s["attention_rows"] == 0, s

    print("8 ->", a["segmented"])
    print("9 ->", b["segmented"])
    print("7 ->", c["segmented"], "| flags:", c["flags"])
    print("all self-checks passed")
