# -*- coding: utf-8 -*-
"""Count บท (stanzas) and วรรค (waks) in the raw Dataset/ poetry files.

Raw layout, one .txt per ตอน:

    ๏ แต่ปางหลังครั้งว่างพระศาสนา
    เป็นปฐมสมมตินิทานมา<TAB>ด้วยปัญญายังประวิงทั้งหญิงชาย
    ฉันชื่อภู่รู้เรื่องประจักษ์แจ้ง<TAB>จึงแสดงคำคิดประดิษฐ์ถวาย
    ตามสติริเริ่มเรื่องนิยาย<TAB>ให้เพริศพรายพริ้งเพราะเสนาะกลอน ฯ

Counting rules — the author's spec, and the same model CleanData.py already
implements (scan_ton / _bots / write_eval):

- A วรรค is one TAB/NEWLINE-separated Thai run. ๏ (act open) and ฯ (act close)
  are decorations and are stripped; spaces INSIDE a วรรค survive.
- ๏ opens an act. An act holds 4k วรรค, or 4k+3 when it opens with the special
  3-วรรค stanza (chapter start / big narrative shift — the สดับ form:
  "๏ แต่ปางหลังครั้งว่างพระศาสนา / เป็นปฐมสมมตินิทานมา / ด้วยปัญญา...ชาย").
- A บท is consecutive วรรค: 4 per stanza; an act with 4k+3 วรรค has ONE
  3-วรรค stanza at its start, then 4-วรรค stanzas.
- An act that is neither 4k nor 4k+3 lost/merged a วรรค — reported, not hidden.

Verification: for every file we replicate write_eval's row derivation (cut the
first act's 3 opener วรรค when it is 4k+3, then group the file's วรรค by 4) and
compare with the actual Results/Evaluate/<work>/<stem>_ok.csv row count.

Usage:
    python count_raw_dataset.py                          # all 5 works
    python count_raw_dataset.py --file Dataset/Khobut/khobut_1.txt
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "Dataset"
EVAL_DIR = ROOT / "Results" / "Evaluate"
THAI = re.compile(r"[ก-ฮ]")
STRIP = "๏ฯ๚๛"          # ๏ act-open, ฯ act-close, ๚/๛ alternates seen in Thai texts
GAPS_JSON = DATASET / "transcription_gaps.json"


def load_gaps():
    """{stem: [(lo, hi), ...]} of 1-based วรรค ranges write_eval EXCLUDES from
    tiling (present halves of incomplete บท). Missing file -> {}."""
    if not GAPS_JSON.exists():
        return {}
    raw = json.loads(GAPS_JSON.read_text(encoding="utf-8"))
    return {k: [tuple(r) for r in v] for k, v in raw.items()
            if not k.startswith("_")}


def read_text(path):
    for enc in ("utf-8-sig", "utf-8", "cp874"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def parse_file(path):
    """Parse one raw ตอน -> dict of counts, per-act detail, anomalies, notes."""
    text = read_text(path)
    waks, close_at, anchors = [], [], []
    anomalies, notes, lines = [], [], []

    for ln, line_txt in enumerate(text.splitlines(), 1):
        got, raws = [], []                          # wak indices / raw segments
        for seg in re.split(r"[\t]+", line_txt):    # tab/newline ONLY (spaces survive)
            s = seg.strip()
            if not s:
                continue
            n_open = s.count("๏")
            if n_open:
                if n_open > 1 or not s.startswith("๏"):
                    anomalies.append(f"misplaced ๏: {s[:36]!r}")
                anchors.extend(len(waks) for _ in range(n_open))
            clean = s
            for ch in STRIP:
                clean = clean.replace(ch, "")
            clean = clean.strip()
            has_close = any(ch in s for ch in "ฯ๚๛")
            if THAI.search(clean):
                waks.append(clean)
                close_at.append(has_close)
                got.append(len(waks))
            elif has_close and waks:                # standalone ฯ closes prev act
                close_at[-1] = True
                got.append(None)
            else:
                if n_open == 0:
                    notes.append(f"non-Thai segment skipped: {s[:36]!r}")
                got.append(None)
            raws.append(s)
        if got:
            lines.append((ln, got, raws))
    # Acts: leading pre-๏ waks (CleanData keeps them as a section too), then
    # one act per ๏, to EOF.
    bounds = ([0] if anchors and anchors[0] != 0 else []) + anchors + [len(waks)]
    if not anchors and waks:
        bounds = [0, len(waks)]
        notes.append("no ๏ in file — whole file treated as one act")
    if anchors and anchors[0] != 0:
        anomalies.append(f"text before first ๏ ({anchors[0]} วรรค) — title line?")

    acts, stanzas4, stanzas3, anom_waks = [], 0, 0, 0
    pairs = list(zip(bounds, bounds[1:]))
    leading_section = bool(bounds) and anchors and anchors[0] != 0
    for k, (a, b) in enumerate(pairs):
        n = b - a
        rem = n % 4
        acts.append({"start": a + 1, "end": b, "waks": n, "rem": rem})
        if rem == 0:
            stanzas4 += n // 4
        elif rem == 3:
            stanzas3 += 1
            stanzas4 += (n - 3) // 4
        else:
            anom_waks += n
            anomalies.append(f"๏ act #{k + 1} (วรรค {a + 1}–{b}): {n} วรรค — "
                             f"not 4k/4k+3; วรรค left ungrouped")
        # ฯ structure: every act should close on its final วรรค
        if n and not (k == 0 and leading_section):
            if not close_at[b - 1]:
                notes.append(f"act #{k + 1} (วรรค {a + 1}–{b}) ends without ฯ")
            for j in range(a, b - 1):
                if close_at[j]:
                    anomalies.append(f"ฯ inside act #{k + 1} at วรรค {j + 1} "
                                     f"(not act-final)")

    # Mirror write_eval exactly: cut 3 opener วรรค iff the FIRST section is 4k+3,
    # then group everything consecutively by 4; leftovers = tail. Also drop the
    # present halves of incomplete บท (Dataset/transcription_gaps.json) so the
    # prediction matches the patched eval rows.
    usable = len(waks)
    opener = 0
    if pairs and (pairs[0][1] - pairs[0][0]) % 4 == 3:
        opener = 3
        usable -= 3
    gaps = load_gaps().get(path.stem, [])
    gap_skipped = 0
    for lo, hi in gaps:
        gap_skipped += sum(1 for i in range(lo, hi + 1) if opener < i <= len(waks))
    usable -= gap_skipped
    rows_pred = usable // 4
    tail = usable - rows_pred * 4

    start_opener = (opener == 3 and not leading_section
                    and bool(anchors) and anchors[0] == 0)
    mid_openers = sum(1 for a in acts[1:] if a["rem"] == 3)

    return {
        "path": path, "stem": path.stem, "folder": path.parent.name,
        "acts": acts, "waks": len(waks), "stanzas4": stanzas4,
        "stanzas3": stanzas3, "anom_waks": anom_waks,
        "anomalies": anomalies, "notes": notes,
        "opener": opener, "rows_pred": rows_pred, "tail": tail,
        "start_opener": start_opener, "mid_openers": mid_openers,
        "gap_skipped": gap_skipped,
        "lines": lines, "wak_texts": waks,
    }


def eval_actual_rows(stem):
    """Row count (minus header) of Results/Evaluate/<work>/<stem>_ok.csv."""
    work = re.sub(r"_\d+$", "", stem) or stem       # same derivation as write_eval
    p = EVAL_DIR / work / f"{stem}_ok.csv"
    if not p.exists():
        return None
    with open(p, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        next(rd, None)
        return sum(1 for _ in rd)


def chapter_key(rec):
    m = re.search(r"_(\d+)$", rec["stem"])
    return (int(m.group(1)) if m else 0, rec["stem"])


def print_file_detail(rec):
    print(f"\n--- {rec['path'].relative_to(ROOT)} ---")
    for k, a in enumerate(rec["acts"], 1):
        if a["rem"] == 0:
            kind = f"{a['waks'] // 4} × 4-วรรค บท"
        elif a["rem"] == 3:
            kind = f"1 × 3-วรรค opener + {a['waks'] - 3} × 4-วรรค บท"
        else:
            kind = "NOT 4k/4k+3 — lost/merged วรรค"
        print(f"  act {k:>3}: waks {a['start']:>5}–{a['end']:>5}  n={a['waks']:>4}  "
              f"(mod4={a['rem']})  {kind}")
    for msg in rec["anomalies"]:
        print(f"  !! {msg}")
    for msg in rec["notes"]:
        print(f"  ~  {msg}")


def dump_span(stem, lo, hi):
    """Print the raw tab layout for วรรค lo..hi: one row per source line, waks
    in sequence order with their index, ๏/ฯ shown at their exact position."""
    p = next(DATASET.glob(f"*/{stem}.txt"), None)
    if p is None:
        print(f"!! no Dataset/*/{stem}.txt")
        return
    rec = parse_file(p)
    print(f"\n=== {p.relative_to(ROOT)} — วรรค {lo}–{hi} ===")
    for k, a in enumerate(rec["acts"], 1):
        if a["end"] < lo or a["start"] > hi:
            continue
        print(f"  [act #{k}: วรรค {a['start']}–{a['end']}  n={a['waks']}  mod4={a['rem']}]")
    for ln, got, raws in rec["lines"]:
        if not any(i is not None and lo <= i <= hi for i in got):
            continue
        cells = []
        for i, s in zip(got, raws):
            if i is None:
                cells.append(f"<{s}>")
                continue
            tag = "".join(mk for ch, mk in (("๏", "๏"), ("ฯ", "ฯ"),
                                            ("๚", "ฯ"), ("๛", "๛")) if ch in s)
            txt = s
            for ch in STRIP:
                txt = txt.replace(ch, "")
            cells.append(f"w{i}{tag}·{txt.strip()}")
        print(f"  L{ln:<5} " + "   |   ".join(cells))


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")        # Windows console: Thai, not mojibake

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", nargs="*", metavar="TXT",
                    help="detail-print these file(s) only")
    ap.add_argument("--dump", nargs=3, action="append",
                    metavar=("STEM", "LO", "HI"),
                    help="print raw tab layout for วรรค LO..HI of STEM (repeatable)")
    args = ap.parse_args()

    files = sorted(DATASET.glob("*/*.txt"))
    if args.file:
        targets = [ROOT / f if not Path(f).is_absolute() else Path(f)
                   for f in args.file]
        for t in targets:
            print_file_detail(parse_file(t))
        return

    if args.dump:
        for stem, lo, hi in args.dump:
            dump_span(stem, int(lo), int(hi))
        return

    if not files:
        sys.exit(f"no .txt found under {DATASET}")

    recs = []
    for p in files:
        rec = parse_file(p)
        rec["rows_actual"] = eval_actual_rows(rec["stem"])
        recs.append(rec)

    folders = {}
    for rec in recs:
        folders.setdefault(rec["folder"], []).append(rec)

    def line(rec):
        act = rec["rows_actual"]
        verdict = "ok" if act == rec["rows_pred"] else "MISMATCH"
        if act is None:
            verdict = "eval MISSING"
        flags = ""
        if rec["anomalies"]:
            flags += " !"
        if rec["tail"]:
            flags += " tail"
        if rec["mid_openers"]:
            flags += f" +{rec['mid_openers']}mid3"
        print(f"    {rec['stem']:<24} acts={len(rec['acts']):>3}  "
              f"วรรค={rec['waks']:>6,}  บท={rec['stanzas4'] + rec['stanzas3']:>5,} "
              f"(4ว:{rec['stanzas4']:>5,} + 3ว:{rec['stanzas3']:>2})  "
              f"eval={act if act is not None else '—':>5}  {verdict}{flags}")

    grand = {"files": 0, "acts": 0, "waks": 0, "stanzas4": 0, "stanzas3": 0,
             "rows": 0, "pred": 0, "anom": 0}
    for folder in sorted(folders):
        recs_f = sorted(folders[folder], key=chapter_key)
        print(f"\n== {folder}  ({len(recs_f)} files) ==")
        sub = {"acts": 0, "waks": 0, "stanzas4": 0, "stanzas3": 0,
               "rows": 0, "pred": 0, "anom": 0}
        for rec in recs_f:
            line(rec)
            sub["acts"] += len(rec["acts"])
            sub["waks"] += rec["waks"]
            sub["stanzas4"] += rec["stanzas4"]
            sub["stanzas3"] += rec["stanzas3"]
            sub["rows"] += rec["rows_actual"] or 0
            sub["pred"] += rec["rows_pred"]
            sub["anom"] += len(rec["anomalies"])
        tot_st = sub["stanzas4"] + sub["stanzas3"]
        print(f"    {'— subtotal —':<24} acts={sub['acts']:>3}  "
              f"วรรค={sub['waks']:>6,}  บท={tot_st:>5,} "
              f"(4ว:{sub['stanzas4']:>5,} + 3ว:{sub['stanzas3']:>2})  "
              f"eval={sub['rows']:>5}  anomalies={sub['anom']}")
        for k in grand:
            grand[k] += sub[k] if k in sub else 0
        grand["files"] += len(recs_f)

    total_st = grand["stanzas4"] + grand["stanzas3"]
    print(f"\n== GRAND TOTAL ({grand['files']} files, 5 works) ==")
    print(f"  ๏ acts                 : {grand['acts']:,}")
    print(f"  วรรค (raw)             : {grand['waks']:,}")
    print(f"  บท (raw)               : {total_st:,}  "
          f"= {grand['stanzas4']:,} × 4-วรรค + {grand['stanzas3']} × 3-วรรค openers")
    print(f"  eval rows (Results/Evaluate): {grand['rows']:,} "
          f"(predicted {grand['pred']:,})")

    bad = [r for r in recs if r["anomalies"] or r["tail"]
           or (r["rows_actual"] is not None and r["rows_actual"] != r["rows_pred"])]
    recon = total_st - grand["rows"]
    print(f"\n  VERIFICATION")
    print(f"    raw บท − eval rows = {recon}  "
          f"(expect: 3-วรรค openers + mid-act openers that write_eval shifts)")
    print(f"    start-opener files : "
          f"{sum(1 for r in recs if r['start_opener'])}")
    print(f"    mid-act 3-วรรค stanzas: {sum(r['mid_openers'] for r in recs)}")
    print(f"    eval tail-dropped วรรค: {sum(r['tail'] for r in recs)}")
    if bad:
        print(f"    !! {len(bad)} file(s) need attention:")
        for r in bad:
            for msg in r["anomalies"]:
                print(f"       {r['stem']}: {msg}")
            if r["tail"]:
                print(f"       {r['stem']}: eval tail = {r['tail']} วรรค dropped")
            if r["rows_actual"] is not None and r["rows_actual"] != r["rows_pred"]:
                print(f"       {r['stem']}: eval rows {r['rows_actual']} != "
                      f"predicted {r['rows_pred']}")
        sys.exit(1)
    print("    all files clean: acts all 4k/4k+3, eval rows match prediction ✓")


if __name__ == "__main__":
    main()
