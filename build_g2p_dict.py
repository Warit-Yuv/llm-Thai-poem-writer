# -*- coding: utf-8 -*-
"""
build_g2p_dict.py
=================
Convert test_g2p.txt (Thai word + IPA, syllables separated by " . ")
into a Thai syllable-reading dictionary in the style of POETRY_OVERRIDES:

    { "พนาสัณฑ์": ["พะ", "นา", "สัน"], ... }

How it works
------------
1. Syllable boundaries come straight from the IPA (" . " separators).
2. Each IPA syllable (phones + tone) is respelled as Thai using standard
   dictionary-reading conventions:
     * สระลดรูป  (short /o/ closed -> implicit vowel:  กก, กบ, กรง ...)
     * อำ for /am/,  ไ for /aj/,  เ_า for /aw/,  ัว for /ua/,  เ_ือ for /ɯa/
     * ห นำ      (rising tone on sonorants:  หมา, เหล่า, หมาย ...)
     * tone marks chosen from the IPA tone + the Thai tone-class table
       (mid ˧ / low ˨˩ / falling ˥˩ / high ˦˥ / rising ˩˩˦)
3. Duplicate words keep the FIRST occurrence (per the user's rule).
4. A CORRECTIONS layer fixes known g2p glitches / matches the Royal-Society
   dictionary reading (e.g. กบาล, กนก, เลือก, แนก, อิ่ม, พาท, ใน ...).

Output: g2p_dictionary.py  (dict G2P_DICTIONARY)
"""
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")

SRC = "test_g2p.txt"
OUT = "g2p_dictionary.py"

# ---- IPA tone -> Thai tone number (0 mid, 1 low, 2 falling, 3 high, 4 rising)
TONE = {"˧": 0, "˨˩": 1, "˥˩": 2, "˦˥": 3, "˩˩˦": 4}

VOWEL_CHARS = set("aiɯueɛɔoː")
SONORANTS = {"ŋ", "n", "m", "j", "w", "l", "r"}

# onset phoneme -> candidate letters (letter, tone-class M/H/L)
ONSET = {
    "k":   [("ก", "M")],
    "kʰ":  [("ข", "H"), ("ค", "L")],
    "ŋ":   [("ง", "L")],
    "tɕ":  [("จ", "M")],
    "tɕʰ": [("ฉ", "H"), ("ช", "L")],
    "s":   [("ส", "H"), ("ซ", "L")],
    "j":   [("ย", "L")],
    "d":   [("ด", "M")],
    "t":   [("ต", "M"), ("ท", "L")],
    "tʰ":  [("ถ", "H"), ("ท", "L")],
    "n":   [("น", "L")],
    "b":   [("บ", "M")],
    "p":   [("ป", "M"), ("พ", "L")],
    "pʰ":  [("ผ", "H"), ("พ", "L")],
    "f":   [("ฝ", "H"), ("ฟ", "L")],
    "m":   [("ม", "L")],
    "w":   [("ว", "L")],
    "l":   [("ล", "L")],
    "r":   [("ร", "L")],
    "h":   [("ห", "H"), ("ฮ", "L")],
    "ʔ":   [("อ", "M")],
}

SONORANT_LETTER = {"ŋ": "ง", "n": "น", "m": "ม", "j": "ย", "w": "ว", "l": "ล", "r": "ร"}


def result_tone(cls, live, dead_short, mark):
    """Tone produced by (tone-class, live/dead, tone mark)."""
    if mark is None:
        if live:
            return {"M": 0, "H": 4, "L": 0}[cls]
        return {"M": 1, "H": 1, "L": 3 if dead_short else 2}[cls]
    return {
        "่": {"M": 1, "H": 1, "L": 2},
        "้": {"M": 2, "H": 2, "L": 3},
        "๊": {"M": 3, "H": 3, "L": 3},
        "๋": {"M": 4, "H": 4, "L": 4},
    }[mark][cls]


def norm(tok):
    """Strip combining marks + stray schwa modifier from an IPA token."""
    out = []
    for c in tok:
        if unicodedata.category(c) == "Mn" or c in ("ᵊ",):
            continue
        out.append(c)
    return "".join(out)


def split_token(tok):
    """Return (consonant_part, vowel_part) of a normalized IPA token."""
    cons, vow = [], []
    for c in tok:
        (vow if c in VOWEL_CHARS else cons).append(c)
    return "".join(cons), "".join(vow)


def vowel_spelling(nuc, coda):
    """Map (nucleus, coda-phoneme) -> (pre, post, coda_written, live, dead_short)."""
    if nuc == "a" and coda == "m":
        return ("", "ำ", "", True, False)          # อำ / กำ / ทำ
    if nuc == "a":
        if coda is None: return ("", "ะ", "", False, True)
        if coda == "k": return ("", "ั", "ก", False, True)
        if coda == "t": return ("", "ั", "ด", False, True)
        if coda == "p": return ("", "ั", "บ", False, True)
        if coda == "ŋ": return ("", "ั", "ง", True, False)
        if coda == "n": return ("", "ั", "น", True, False)
        if coda == "j": return ("ไ", "", "", True, False)
        if coda == "w": return ("เ", "า", "", True, False)
    if nuc == "aː":
        if coda is None: return ("", "า", "", True, False)
        if coda == "k": return ("", "า", "ก", False, False)
        if coda == "t": return ("", "า", "ด", False, False)
        if coda == "p": return ("", "า", "บ", False, False)
        if coda == "ŋ": return ("", "า", "ง", True, False)
        if coda == "n": return ("", "า", "น", True, False)
        if coda == "m": return ("", "า", "ม", True, False)
        if coda == "j": return ("", "า", "ย", True, False)
        if coda == "w": return ("", "า", "ว", True, False)
    if nuc == "i":
        if coda is None: return ("", "ิ", "", False, True)
        if coda == "k": return ("", "ิ", "ก", False, True)
        if coda == "t": return ("", "ิ", "ด", False, True)
        if coda == "p": return ("", "ิ", "บ", False, True)
        if coda == "n": return ("", "ิ", "น", True, False)
        if coda == "m": return ("", "ิ", "ม", True, False)
    if nuc == "iː":
        if coda is None: return ("", "ี", "", True, False)
        if coda == "t": return ("", "ี", "ด", False, False)
        if coda == "n": return ("", "ี", "น", True, False)
    if nuc == "ɯ":
        if coda is None: return ("", "ึ", "", False, True)
        if coda == "k": return ("", "ึ", "ก", False, True)
    if nuc == "ɯː":
        return ("", "ื", "", True, False)
    if nuc == "u":
        if coda is None: return ("", "ุ", "", False, True)
        if coda == "k": return ("", "ุ", "ก", False, True)
        if coda == "t": return ("", "ุ", "ด", False, True)
        if coda == "n": return ("", "ุ", "น", True, False)
    if nuc == "uː":
        if coda is None: return ("", "ู", "", True, False)
        if coda == "n": return ("", "ู", "น", True, False)
    if nuc == "e":
        if coda is None: return ("เ", "ะ", "", False, True)
        if coda == "k": return ("เ", "็", "ก", False, True)
        if coda == "p": return ("เ", "็", "บ", False, True)
        if coda == "ŋ": return ("เ", "็", "ง", True, False)
        if coda == "n": return ("เ", "็", "น", True, False)
    if nuc == "eː":
        if coda is None: return ("เ", "", "", True, False)
        if coda == "k": return ("เ", "", "ก", False, False)
        if coda == "t": return ("เ", "", "ด", False, False)
        if coda == "n": return ("เ", "", "น", True, False)
    if nuc == "ɛ":
        if coda is None: return ("แ", "ะ", "", False, True)
        if coda == "k": return ("แ", "็", "ก", False, True)
    if nuc == "ɛː":
        if coda is None: return ("แ", "", "", True, False)
        if coda == "k": return ("แ", "", "ก", False, False)
    if nuc == "o":
        if coda is None: return ("โ", "ะ", "", False, True)
        if coda == "k": return ("", "", "ก", False, True)    # สระลดรูป
        if coda == "t": return ("", "", "ด", False, True)
        if coda == "p": return ("", "", "บ", False, True)
        if coda == "m": return ("", "", "ม", True, False)
        if coda == "n": return ("", "", "น", True, False)
        if coda == "ŋ": return ("", "", "ง", True, False)
    if nuc == "oː":
        if coda is None: return ("โ", "", "", True, False)
        if coda == "k": return ("โ", "", "ก", False, False)
    if nuc == "ɔ":
        if coda is None: return ("เ", "าะ", "", False, True)
    if nuc == "ɔː":
        if coda is None: return ("", "อ", "", True, False)
        if coda == "k": return ("", "อ", "ก", False, False)
        if coda == "t": return ("", "อ", "ด", False, False)
        if coda == "p": return ("", "อ", "บ", False, False)
        if coda == "ŋ": return ("", "อ", "ง", True, False)
        if coda == "n": return ("", "อ", "น", True, False)
    if nuc == "ia":
        if coda is None: return ("เ", "ีย", "", True, False)
        if coda == "n": return ("เ", "ีย", "น", True, False)
    if nuc == "ɯa":
        if coda is None: return ("เ", "ือ", "", True, False)
        if coda == "k": return ("เ", "ือ", "ก", False, True)
        if coda == "ŋ": return ("เ", "ือ", "ง", True, False)
    if nuc == "ua":
        if coda is None: return ("", "ัว", "", True, False)
        if coda == "n": return ("", "ัว", "น", True, False)
    return ("", "", "", True, False)


def parse_ipa_syllable(syl):
    """Return (onset_phonemes, nucleus, coda_phoneme, tone)."""
    toks = [norm(t) for t in syl.split()]
    toks = [t for t in toks if t]
    tone = 0
    if toks and toks[-1] in TONE:
        tone = TONE[toks[-1]]
        toks = toks[:-1]
    onset, nuc_parts, coda = [], [], None
    seen_vowel = False
    for t in toks:
        c, v = split_token(t)
        if c and v:
            if t[0] in VOWEL_CHARS:      # vowel first -> consonant is a coda
                nuc_parts.append(v)
                coda = c
            else:                        # consonant first -> onset
                onset.append(c)
                nuc_parts.append(v)
            seen_vowel = True
        elif c:
            if not seen_vowel:
                onset.append(c)
            else:
                coda = c
        else:
            nuc_parts.append(v)
            seen_vowel = True
    nuc = "".join(nuc_parts)
    if not onset:                        # e.g. lone glottal stop onset
        onset = ["ʔ"] if nuc else ["k"]
    if coda == "ʔ":                      # glottal stop = open short vowel (ะ)
        coda = None
    return onset, nuc, coda, tone


def letter_for(ph):
    return ONSET[ph][0][0]


def spell_syllable(onset_phons, nuc, coda_ph, tone):
    pre, post, coda_w, live, dead_short = vowel_spelling(nuc, coda_ph)
    first = onset_phons[0]
    cluster = "".join(letter_for(p) for p in onset_phons[1:])

    if first in SONORANTS:
        base = SONORANT_LETTER[first]
        if tone == 4:                                   # rising -> ห นำ
            return "ห" + base + cluster, "H", None
        if tone == 1 and not live:                      # low dead -> ห นำ
            return "ห" + base + cluster, "H", None
        if tone == 1 and live:                          # low live -> ห นำ + ่
            return "ห" + base + cluster, "H", "่"
        for m in [None, "่", "้", "๊", "๋"]:
            if result_tone("L", live, dead_short, m) == tone:
                return base + cluster, "L", m
        return base + cluster, "L", None

    for let, cls in ONSET[first]:
        if result_tone(cls, live, dead_short, None) == tone:
            return let + cluster, cls, None
    for let, cls in ONSET[first]:
        for m in ["่", "้", "๊", "๋"]:
            if result_tone(cls, live, dead_short, m) == tone:
                return let + cluster, cls, m
    let, cls = ONSET[first][0]
    return let + cluster, cls, None


def syll_to_thai(syl):
    onset, nuc, coda, tone = parse_ipa_syllable(syl)
    onset_letters, _cls, mark = spell_syllable(onset, nuc, coda, tone)
    pre, post, coda_w, _live, _ds = vowel_spelling(nuc, coda)
    return pre + onset_letters + post + (mark or "") + coda_w


def parse_file(path):
    words = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if "\t" in line:
                w, ipa = line.split("\t", 1)
            else:
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                w, ipa = parts
            words.append((w.strip(), ipa.strip()))
    return words


# ---- manual / dictionary-convention fixes (on top of the phonetic engine) ----
CORRECTIONS = {
    # malformed first IPA line (schwa, no tone); use the sane /ka.baːn/ reading
    "กบาล": ["กะ", "บาน"],
    # IPA tone says นก is low, but the RID reading keeps the orthography กะ-นก
    "กนก": ["กะ", "นก"],
    # short-vowel "อิ่ม" is a known tone irregularity: no tone mark in the RID form
    "กรดไขมันอิ่มตัว": ["กรด", "ไข", "มัน", "อิ่ม", "ตัว"],
    "กรดไขมันไม่อิ่มตัว": ["กรด", "ไข", "มัน", "ไม่", "อิ่ม", "ตัว"],
    # เ_ือ+ก falling is irregular; keep the orthographic เลือก
    "กบเลือกนาย": ["กบ", "เลือก", "นาย"],
    # ใ for /naj/ mid (matches the word's own orthography)
    "กบในกะลา": ["กบ", "ใน", "กะ", "ลา"],
    "กบในกะลาครอบ": ["กบ", "ใน", "กะ", "ลา", "ครอบ"],
    # แผนก read ผะ-แนก (แนก = น+แ+ก, dead long)
    "กฎหมายระหว่างประเทศแผนกคดีบุคคล": [
        "กด", "หมาย", "ระ", "หว่าง", "ประ", "เทด", "ผะ", "แนก", "คะ", "ดี", "บุก", "คน"],
    "กฎหมายระหว่างประเทศแผนกคดีเมือง": [
        "กด", "หมาย", "ระ", "หว่าง", "ประ", "เทด", "ผะ", "แนก", "คะ", "ดี", "เมือง"],
    # พิพาท -> พาท (ท coda, matching the word; engine default would be ด)
    "กรณีพิพาท": ["กอ", "ระ", "นี", "พิ", "พาท"],
    # ธรรม์ = ทาน (long); g2p's short /tʰan/ is a known w2p-type glitch
    "กรมธรรม์": ["กรม", "มะ", "ทาน"],
    # กมรเตง: the g2p short /teŋ/ is a length glitch; the word is spelled เตง (long)
    "กมรเตง": ["กะ", "มะ", "ระ", "เตง"],
    "กมรเตงอัญ": ["กะ", "มะ", "ระ", "เตง", "อัน"],
}


def main():
    raw = parse_file(SRC)
    seen = set()
    result = []          # (word, ipa, reading)
    for word, ipa in raw:
        if word in seen:
            continue
        seen.add(word)
        syls = [s for s in ipa.split(".") if s.strip()]
        try:
            reading = [syll_to_thai(s) for s in syls]
        except Exception as e:
            print("DEBUG word=%r ipa=%r err=%r" % (word, ipa, e))
            raise
        if word in CORRECTIONS:
            reading = CORRECTIONS[word]
        result.append((word, ipa, reading))

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# -*- coding: utf-8 -*-\n")
        fh.write("# G2P_DICTIONARY - generated from test_g2p.txt by build_g2p_dict.py\n")
        fh.write("# Thai word -> syllable readings (dictionary-style)\n")
        fh.write("G2P_DICTIONARY = {\n")
        for word, _ipa, reading in result:
            syl_str = ", ".join('"%s"' % s for s in reading)
            fh.write('    "%s": [%s],\n' % (word, syl_str))
        fh.write("}\n")

    print("== review (word | IPA | reading) ==")
    for word, ipa, reading in result:
        print("%s\t%s\t%s" % (word, ipa, "-".join(reading)))


if __name__ == "__main__":
    main()
