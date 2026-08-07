# -*- coding: utf-8 -*-
"""Self-checks for CleanData.py — real วรรค from พระอภัยมณี, not synthetic input.

    pytest test_cleandata.py        or        python test_cleandata.py

Every case here is a bug that actually shipped once: the newmm shatter, the
w2p hallucination on orphan letters, the compound-tail miscount, and the
review CSV that used to confirm its own guesses.
"""
import csv
import os
import sys
import tempfile

import CleanData as C


def test_clean_waks():
    """The two canonical bodies: 8 -> [3,2,3], 9 -> [3,3,3], no flags."""
    a = C.analyze_wak("พระอย่าได้ถือความข้าสามคน")
    assert a["total_syllables"] == 8 and a["rhythm"] == [3, 2, 3], a

    b = C.analyze_wak("ทั้งสามคนคู่ชีวิตเป็นมิตรกัน")
    assert b["total_syllables"] == 9 and b["rhythm"] == [3, 3, 3], b


def test_ambiguous_seven_flags():
    """A genuine 7 is unresolvable — it must reach the human, not guess quietly."""
    c = C.analyze_wak("ดนตรีมีคุณที่ข้อไหน")
    assert c["total_syllables"] == 7 and c["needs_review"], c


def test_override_and_midword_beat():
    """custom_dict stops the สานน shatter (was 10 syl); the beat line then falls
    INSIDE วิเชียร and is cut at written syllables — จังหวะ is spoken."""
    d = C.analyze_wak("ข้าชื่อวิเชียรโมราเจ้าสานน")
    assert d["total_syllables"] == 9, d
    assert d["segmented"] == "ข้าชื่อวิ | เชียรโมรา | เจ้าสานน", d
    assert not d["needs_review"], d


def test_orphan_letter_counts_one():
    """newmm leaves ค alone; it's a linking syllable (คะ = 1), not w2p's 2.
    Before the guard this วรรค scanned as 10 = irregular."""
    e = C.analyze_wak("สนมนางแสนสุรางคนิกร")
    assert e["total_syllables"] == 9 and e["rhythm"] == [3, 3, 3], e
    assert e["segmented"] == "สนมนาง | แสนสุราง | คนิกร" and not e["needs_review"], e


def test_syllable_split_refuses_when_unsure():
    """วิเชียร is verifiable; มนุษย์ (1 piece) and เกสร must refuse — w2p reads
    เกสร alone as 2 (เกด-สอน) but as a compound tail it's 1 (เกด), and a bad
    split would shift the วรรค total silently."""
    assert C._syllable_split("วิเชียร", 2) == [("วิ", 1), ("เชียร", 1)]
    assert C._syllable_split("มนุษย์", 2) is None
    assert C._syllable_split("ปทุมเกสร", 3) is None


def test_manual_cuts_reject_edits():
    """Typed/pasted cuts may move beat lines, never change the text."""
    words = ["ข้า", "ชื่อ", "วิเชียร", "โมรา", "เจ้า", "สานน"]
    m = C._manual_cuts("ข้าชื่อวิ | เชียรโมรา | เจ้าสานน", words, 9)
    assert m == {"rhythm": [3, 3, 3], "segmented": "ข้าชื่อวิ | เชียรโมรา | เจ้าสานน"}, m
    assert C._manual_cuts("ข้าชื่อ | ผิดๆ | เจ้าสานน", words, 9) is None


def test_manual_cuts_require_three_beats():
    """A half-filled row must not become a 'resolved' วรรค: it would export with
    empty beat cells and vanish from the queue (--csv skips anything in
    review.json), going silently missing from both sides."""
    words = ["ข้า", "ชื่อ", "วิเชียร", "โมรา", "เจ้า", "สานน"]
    whole = "ข้าชื่อวิเชียรโมราเจ้าสานน"
    assert C._manual_cuts(whole, words, 9) is None                      # no cuts
    assert C._manual_cuts("ข้าชื่อวิ | เชียรโมราเจ้าสานน", words, 9) is None  # 2 beats
    assert C._manual_cuts("ข้าชื่อวิ |  | เชียรโมราเจ้าสานน", words, 9) is None  # empty beat


def test_section_checksum():
    """๏ sections must hold a multiple of 4 วรรค — the only check that catches a
    DROPPED วรรค. Glued ๏วรรค anchors too; no ๏ means no checksum."""
    _, _, secs = C.scan_ton("๏กากา กากา กากา กากา ๏ กากา กากา กากา")
    assert secs == [(0, 4, True), (4, 3, False)], secs
    _, _, secs = C.scan_ton("กากา กากา")
    assert secs == [], secs


def _fixture(td):
    """3 ๏ acts: 2 clean บท / 1 flagged วรรค blocking its บท / a bad-%4 stub."""
    C.EXPORT_DIR = C.ATTENTION_DIR = td          # isolate: don't litter real Results/
    p = os.path.join(td, "t.txt")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("๏ " + " ".join(["กากา"] * 8)
                 + " ๏ ดนตรีมีคุณที่ข้อไหน " + " ".join(["กากา"] * 7)
                 + " ๏ กากา")
    return p


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_csv_round_trip():
    """--csv -> edit -> --import -> --csv: the fixed วรรค unblocks its บท and
    the recovered window moves from the attention file into the export."""
    with tempfile.TemporaryDirectory() as td:
        p = _fixture(td)
        s = C.write_csv(p)
        assert s["export_rows"] == 1 and s["attention_rows"] == 1, s
        assert s["bot_clean"] == 3 and s["bot_blocked"] == 1, s
        assert s["sections_skipped"] == 1, s

        with open(s["export"], encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        assert rows[0][:4] == ["w1_a", "w1_b", "w1_c", "w2_a"] and len(rows[0]) == 24
        assert rows[1] == ["กากา", "", ""] * 8, rows[1]

        att = _read(s["attention"])
        assert att[0]["wak"] == "ดนตรีมีคุณที่ข้อไหน", att
        att[0]["a"], att[0]["b"], att[0]["c"] = "ดนตรี", "มีคุณ", "ที่ข้อไหน"
        _write_attention(s["attention"], att)

        assert C.import_attention(p) == (1, 0)
        s = C.write_csv(p)
        assert s["export_rows"] == 2 and s["attention_rows"] == 0, s


def test_unedited_import_confirms_nothing():
    """THE regression guard. a/b/c ship empty and the machine guess sits in a
    separate column, so --import before editing is a no-op. When a/b/c were
    prefilled, one stray --import promoted 35 guesses to reviewed ground truth
    — including 10-syllable irregulars, which exported as a single-beat row."""
    with tempfile.TemporaryDirectory() as td:
        p = _fixture(td)
        s = C.write_csv(p)
        att = _read(s["attention"])
        assert att[0]["guess"], att[0]                      # guess is offered...
        assert (att[0]["a"], att[0]["b"], att[0]["c"]) == ("", "", ""), att[0]  # ...not applied

        assert C.import_attention(p) == (0, 0)              # untouched -> nothing
        assert not os.path.exists(p + ".review.json")       # and no file created
        assert C.write_csv(p)["attention_rows"] == 1        # วรรค still queued


def test_old_format_attention_is_refused():
    """132 attention CSVs predate the `guess` column and hold guesses in a/b/c.
    Importing one would confirm them all, so it is refused, not migrated."""
    with tempfile.TemporaryDirectory() as td:
        p = _fixture(td)
        s = C.write_csv(p)
        att = _read(s["attention"])
        att[0]["a"], att[0]["b"], att[0]["c"] = "ดนตรี", "มีคุณ", "ที่ข้อไหน"
        for row in att:                                     # drop the guess column
            del row["guess"]
        _write_attention(s["attention"], att)

        assert C.import_attention(p) == (0, 0)
        assert not os.path.exists(p + ".review.json")


def test_duplicate_wak_gets_one_row():
    """review.json is keyed by วรรค text, so a วรรค repeated in the ตอน needs
    exactly one row — 29 such cases exist in the corpus, one repeated 4x."""
    with tempfile.TemporaryDirectory() as td:
        C.EXPORT_DIR = C.ATTENTION_DIR = td
        p = os.path.join(td, "dup.txt")
        dup = "ดนตรีมีคุณที่ข้อไหน"
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("๏ " + " ".join([dup] + ["กากา"] * 2 + [dup] * 2 + ["กากา"] * 3))
        s = C.write_csv(p)
        assert s["attention_rows"] == 1, s
        assert [r["wak"] for r in _read(s["attention"])] == [dup]


def test_resolve_refuses_keep_auto_on_irregular():
    """'0 = keep auto' on an irregular วรรค has no beats to keep. Accepting it
    wrote {'rhythm': None, segmented: <whole วรรค>} — resolved, unqueued, and
    exported as one filled cell plus two empty ones."""
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "r.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("๏ " + " ".join(["กากา"] * 3)
                     + " พระชนนีรักใคร่ดังนัยนา " + " ".join(["กากา"] * 4))
        r = subprocess.run([sys.executable, "CleanData.py", p, "--resolve"],
                           input="0\nq\n", capture_output=True, text=True,
                           encoding="utf-8", cwd=os.path.dirname(os.path.abspath(__file__)))
        assert "no auto guess to keep" in r.stdout, r.stdout
        assert not os.path.exists(p + ".review.json"), "wrote a beatless entry"


def test_empty_source_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        C.EXPORT_DIR = C.ATTENTION_DIR = td
        p = os.path.join(td, "blank.txt")
        open(p, "w", encoding="utf-8").close()
        s = C.write_csv(p)
        assert s["empty"] and s["export"] is None and s["attention_rows"] == 0, s
        assert os.listdir(td) == ["blank.txt"], os.listdir(td)


def _write_attention(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")     # Windows: print Thai, not mojibake
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("all self-checks passed")
