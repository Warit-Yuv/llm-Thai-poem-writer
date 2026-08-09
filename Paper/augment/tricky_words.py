# -*- coding: utf-8 -*-
"""
Curated tricky-word data + builders for the Klon-8 augmentation.

Material
--------
* ``HARD_POSITIVE_PAIRS`` -- a small seed set (oracle-verified at build time)
  that guarantees the rare recall probes survive. It is a safety net only --
  diversity comes from ``build_positive_pairs`` over word lists + several
  dictionaries (classical ~50% / loan-words ~50%).

* ``ORACLE_LIMITATIONS`` -- pairs that DO rhyme linguistically but the 5.3.5
  oracle REJECTS. Used two ways:
  1. documented in the paper's limitations section;
  2. ``ORACLE_BLIND_POOL`` feeds the *oracle-blind* negative operator: the
     oracle labels these as non-rhymes (gold=0) even though they genuinely
     rhyme, so a checker that is linguistically better than the oracle on that
     case takes a precision hit. Reasons:
  - ``silent_r`` -- final ร silent from a Pali/Sanskrit root (NOT การันต์);
    เพชร = /phet/. The oracle keeps the long เอ (no ็ on the dead final).
    Rhymes with anything สระ เอะ + แม่กด: เพ็ด เห็ด เจ็ด เบ็ด เกร็ด.
  - ``first_sara`` -- check_sara keeps only the FIRST vowel in the input
    string (``return sara[0]``); on a whole multi-syllable word the final
    (rhyming) syllable's vowel is lost (วิศวกรรม -> อิ, loses กรรม).
  - ``rue_2syl`` -- ฤ read as a single รึ though it is two pronounced
    syllables (ฤทัย = รึ-ไท; the final ไท is never seen).

* ``build_positive_pairs`` -- dictionary-driven. Candidate syllables are
  grouped by their phonetic rhyme class (สระ + มาตรา exactly as ``is_sumpus``
  compares after its phonetic normalisation); oracle-verified pairs are drawn
  *within* a class. Members that need normalisation are combined first (they
  are the 5.0.1-vs-5.3.5 recall probes). Every pair records:
    - ``tag``            phenomenon tags (sara_norm / rue / karun / true_final)
    - ``both_normalize`` BOTH sides need the is_sumpus phonetic normalisation
    - ``old_fail``       the 5.0.1 checker rejects the pair (true A-vs-B diff)
    - ``classical``      both members come from corpus/overrides/traps

* ``dictionary_syllables`` -- syllables mined from several pythainlp word
  lists (thai_words, thai_orst_words, thai_icu_words, thai_syllables), cached
  to JSON. Loan words are welcome (they appear in modern Thai poetry too) as
  long as every pair is oracle-verified.

* Negative edge-case pools (consumed by ``corrupt.py``):
  - ``VOWEL_LENGTH_SWAP``  short<->long sara counterparts (เจ็ด/เชด, แข็ง/แขง)
  - ``liquid_final_pool``  ร/ล/ว finals where old pythainlp disagrees with the
    new core (ตัว -> old (อะ,เกอว) vs new (อัว,กา); ทร -> old กด vs new กน;
    หงส์ -> old returns an error string) -- "final consonant" confusion probes
  - ``LEAD_POOL``          ห/อ นำ (leading) words (หงส์ หน อยาก อย่า อยู่ ...)
  - ``ORACLE_BLIND_POOL``  words from ORACLE_LIMITATIONS + their rhyme families
  - ``EXTRA_SYLLABLES``    karun / ฤ / cluster / true-final trap words
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from typing import Optional

# ---------------------------------------------------------------------------
# 1. Curated seed pairs (safety net; re-verified at build time)
# ---------------------------------------------------------------------------
HARD_POSITIVE_PAIRS: list[tuple[str, str]] = [
    # สระ normalisation / reduced & transformed vowels
    ("ไทย", "ทัย"), ("ไทย", "ไท"), ("ทัย", "ไท"),
    ("กำ", "กรรม"), ("กำ", "กัม"), ("จำ", "กรรม"), ("จำ", "ธรรม"),
    ("บัน", "บรร"), ("สวรรค์", "สัน"), ("เลย", "เกย"),
    ("จวก", "พวก"), ("กัม", "กำ"),
    # ฤ (the oracle handles these)
    ("ฤทธิ์", "กิด"), ("ฤกษ์", "เกิก"), ("กฤษ", "กิด"),
    ("ตฤณ", "ติน"), ("ตฤณ", "บิน"), ("ตฤณ", "กิน"),
    # true-final -าย / -าว (ย/ว as vowel glides)
    ("กัย", "ไก"), ("ชัย", "ไช"), ("ใจ", "ไจ"), ("ใหญ่", "ไหย่"),
    # mattra families
    ("บ้าน", "พาล"), ("พาน", "พาล"), ("ธรรม", "สัม"),
    ("พร", "พอน"), ("ทำ", "จำ"),
    # karun the oracle DOES handle
    ("กษัตริย์", "สัด"),
    # both-need-normalisation probes (5.0.1 normalises only ONE side -> fails;
    # 5.3.5 normalises both -> passes). Common classical words only.
    ("ธรรม", "กรรม"), ("ธรรม", "สัม"), ("ธรรม", "กัม"),
    ("กรรม", "สัม"), ("กรรม", "กัม"),
]

# Pairs that rhyme linguistically but the 5.3.5 oracle REJECTS.
ORACLE_LIMITATIONS: list[dict] = [
    {
        "pair": ("เพชร", "เพ็ด"),
        "reason": "silent_r",
        "note": ("final ร silent from a Pali/Sanskrit root (NOT การันต์); "
                 "เพชร = /phet/. The oracle keeps the long เอ because the "
                 "dead final (แม่กด) has no ็. Rhymes with anything "
                 "สระ เอะ + แม่กด: เพ็ด เห็ด เจ็ด เบ็ด เกร็ด."),
    },
    {
        "pair": ("วิศวกรรม", "กำ"),
        "reason": "first_sara",
        "note": ("วิศวกรรม = วิด-สะ-วะ-กรรม; check_sara keeps only the first "
                 "vowel (อิ from วิ), so the final กรรม is lost. กรรม/กำ is a "
                 "rhyme the oracle accepts."),
    },
    {
        "pair": ("ฤทัย", "ไท"),
        "reason": "rue_2syl",
        "note": ("ฤทัย = รึ-ไท (two syllables); the oracle reads ฤ as a "
                 "single รึ (sara อึ) and never sees the final ไท."),
    },
]

_OLD_CORE_EXC = (IndexError, TypeError, ValueError, AttributeError, KeyError)
_DICT_EXC = (ImportError, AttributeError, OSError, ValueError, TypeError,
             KeyError)
_THAI_ONLY = re.compile(r"^[\u0E00-\u0E7F]+$")
_THAI_DIGITS = set("๐๑๒๓๔๕๖๗๘๙")

# Known junk syllables (corpus/ssg artifacts, not real words). The ฤ/ฦ ones
# are already excluded by the curated rule below; this list is for the rest.
BAD_SYLLABLES = {"ไหม้ร"}

# Curated ฤ/ฦ words with their TRUE (Royal-Society) pronunciations. ฤ words
# are only usable as candidates when their sound is known -- the oracle's
# default ฤ -> อึ reading is unreliable (พฤษภ is พรึก-สบ, not a single อึ+กบ
# syllable; ไข้ฤ/รอฤ/ลฤ are ssg artifacts, not words).
RUE_PRONUNCIATION = {
    # single-syllable sounds (usable as positive AND negative candidates)
    "ตฤณ": ["ติน"],       # อิ + กน
    "ฤทธิ์": ["ริด"],      # อิ + กด
    "ฤกษ์": ["เริก"],     # เออ + กก
    "กฤษ": ["กิด"],       # อิ + กด
    "ฤา": ["รือ"],         # อือ + กา
    "ฤๅ": ["รือ"],         # อือ + กา
    # multi-syllable sounds (usable as NEGATIVE candidates only; the oracle
    # gate still verifies non-rhyme, and they exercise the oracle's ฤ mis-read)
    "ฤดู": ["รึ", "ดู"],
    "ฤทัย": ["รึ", "ไท"],
    "พฤษภ": ["พรึก", "สบ"],
    "ฤๅษี": ["รือ", "สี"],
}


# Curated Thai syllable whitelist (thai_syllables) -- loaded once at import;
# every candidate syllable must be in it so corpus/dict ssg artifacts
# (แลลอด, กกง, ไหม้ร, ๑ ๒) never enter.
_THAI_WHITELIST: set = set()
try:
    import pythainlp.corpus as _pc
    _THAI_WHITELIST = set(_pc.thai_syllables())
except _DICT_EXC:
    _THAI_WHITELIST = set()


def is_clean_syllable(x, max_len=6) -> bool:
    """Positive-candidate check: pure Thai (no digits/punct), 2..max_len
    chars, not in BAD_SYLLABLES, in the curated thai_syllables whitelist (so
    corpus/dict ssg artifacts like แลลอด, กกง, ไหม้ร never enter), a single
    ssg syllable, and ฤ/ฦ words only when curated with a SINGLE-syllable
    pronunciation (ตฤณ->ติน)."""
    if not x or len(x) < 2 or len(x) > max_len:
        return False
    if x in BAD_SYLLABLES:
        return False
    if not _THAI_ONLY.match(x) or any(c in _THAI_DIGITS for c in x):
        return False
    if "ฤ" in x or "ฦ" in x:
        return x in RUE_PRONUNCIATION and len(RUE_PRONUNCIATION[x]) == 1
    if _THAI_WHITELIST and x not in _THAI_WHITELIST:
        return False
    from pythainlp.tokenize import syllable_tokenize
    try:
        return list(syllable_tokenize(x, engine="ssg")) == [x]
    except _DICT_EXC:
        return False


def is_clean_neg_syllable(x, max_len=6) -> bool:
    """Negative-candidate check: like ``is_clean_syllable``, but curated
    ฤ/ฦ words with multi-syllable pronunciations (ฤดู->รึ-ดู, พฤษภ->พรึก-สบ)
    are allowed too -- as negative candidates the oracle gate still verifies
    non-rhyme, and they probe the oracle's ฤ mis-reading."""
    if not x or len(x) < 2 or len(x) > max_len:
        return False
    if x in BAD_SYLLABLES:
        return False
    if not _THAI_ONLY.match(x) or any(c in _THAI_DIGITS for c in x):
        return False
    if "ฤ" in x or "ฦ" in x:
        return x in RUE_PRONUNCIATION
    if _THAI_WHITELIST and x not in _THAI_WHITELIST:
        return False
    from pythainlp.tokenize import syllable_tokenize
    try:
        return list(syllable_tokenize(x, engine="ssg")) == [x]
    except _DICT_EXC:
        return False


def clean_syllables(xs, max_len=6) -> list:
    return [x for x in xs if is_clean_syllable(x, max_len)]


def clean_neg_syllables(xs, max_len=6) -> list:
    return [x for x in xs if is_clean_neg_syllable(x, max_len)]


# ---------------------------------------------------------------------------
# 2. Phonetic rhyme class -- what is_sumpus actually compares
# ---------------------------------------------------------------------------
_N1_SARA, _N1_MAT = "อะ", "เกย"        # -> ไอ / กา  (true-final -ัย / -ไ-ย)
_N2_SARAS = ("อะ", "อำ")               # + กม -> อำ / กา (อำ / อัม / กรรม)


def rhyme_class(word, kv):
    """(สระ, มาตรา) exactly as ``is_sumpus`` compares them, after its phonetic
    normalisation. Two syllables rhyme iff their rhyme classes are equal."""
    sara = kv.check_sara(word)
    marttra = kv.check_marttra(word)
    if sara == _N1_SARA and marttra == _N1_MAT:
        sara, marttra = "ไอ", "กา"
    if sara in _N2_SARAS and marttra == "กม":
        sara, marttra = "อำ", "กา"
    return (sara, marttra)


def normalisation_class(word, kv) -> Optional[str]:
    """Return 'N1' / 'N2' when the syllable needs the is_sumpus phonetic
    normalisation, else None."""
    sara = kv.check_sara(word)
    marttra = kv.check_marttra(word)
    if sara == _N1_SARA and marttra == _N1_MAT:
        return "N1"
    if sara in _N2_SARAS and marttra == "กม":
        return "N2"
    return None


def needs_normalisation(word, kv) -> bool:
    return normalisation_class(word, kv) is not None


def phenomenon_tags(word, kv) -> set:
    """Tags for the phenomena a syllable exercises."""
    tags = set()
    if needs_normalisation(word, kv):
        tags.add("sara_norm")        # สระลดรูป/เปลี่ยนรูป handled in is_sumpus
    if any(c in word for c in "ฤฦ"):
        tags.add("rue")
    if "์" in word:
        tags.add("karun")            # การันต์ the oracle handles
    if word.endswith(("ย", "ว")) and \
            rhyme_class(word, kv)[0] in ("ไอ", "เอา", "อัว"):
        tags.add("true_final")       # ย/ว as vowel glides
    return tags


def syllable_report(word, kv, old_kv) -> dict:
    """Spell out a syllable's สระ / มาตรา for the review word lists."""
    sara, mart = kv.check_sara(word), kv.check_marttra(word)
    norm = normalisation_class(word, kv)
    nsara, nmart = rhyme_class(word, kv)
    try:
        osara, omart = old_kv.check_sara(word), old_kv.check_marttra(word)
    except _OLD_CORE_EXC:
        osara, omart = "?", "?"
    return {
        "word": word,
        "sara": sara, "mart": mart,
        "norm_class": norm or "-",
        "norm_sara": nsara, "norm_mart": nmart,
        "old_sara": osara, "old_mart": omart,
        "old_differs": (osara, omart) != (sara, mart),
    }


def build_positive_pairs(kv, rng, sources, seed_pairs=(),
                         max_pairs_per_class=60, max_both_per_class=400,
                         max_total=None, old_checker=None,
                         classical_set=None):
    """Dictionary-driven hard-positive generation.

    Groups ``sources`` (single-syllable candidates) by phonetic rhyme class
    (same สระ + มาตรา) and draws oracle-verified pairs within each class.
    Members needing normalisation (N2 then N1) are combined FIRST so the
    both-normalise probes are plentiful, not drowned out by plain
    mattra-family pairs. Each pair is a dict:

        {"a", "b", "class": (sara, marttra), "tag", "both_normalize",
         "old_fail", "classical"}

    ``both_normalize`` = both sides need the is_sumpus phonetic normalisation.
    ``old_fail`` = the 5.0.1 checker rejects the pair (the genuine
    A-vs-B differentiator). ``classical_set`` marks pairs whose members all
    come from the classical inventory rather than the general dictionary.
    """
    classes = defaultdict(list)
    for s in sources:
        if not s:
            continue
        k = rhyme_class(s, kv)
        if k[0] and k[1]:
            classes[k].append(s)
    pairs = []
    seen = set()

    def _try(a, b):
        if a == b or kv.is_sumpus(a, b) is not True:
            return None
        key = (a, b) if a <= b else (b, a)
        if key in seen:
            return None
        seen.add(key)
        k = rhyme_class(a, kv)
        tags = phenomenon_tags(a, kv) | phenomenon_tags(b, kv)
        both = needs_normalisation(a, kv) and needs_normalisation(b, kv)
        old_fail = False
        if old_checker is not None:
            try:
                old_fail = old_checker.is_sumpus(a, b) is False
            except _OLD_CORE_EXC:
                old_fail = True
        classical = bool(classical_set and a in classical_set
                         and b in classical_set)
        return {
            "a": a, "b": b, "class": list(k),
            "tag": "|".join(sorted(tags)) if tags else "mattra_family",
            "both_normalize": both,
            "old_fail": old_fail,
            "classical": classical,
        }

    # curated seeds first (they survive even in sparse classes)
    for a, b in seed_pairs:
        p = _try(a, b)
        if p:
            pairs.append(p)

    for k, members in sorted(classes.items()):
        members = sorted(set(members))
        n2 = [m for m in members if normalisation_class(m, kv) == "N2"]
        n1 = [m for m in members if normalisation_class(m, kv) == "N1"]
        rest = [m for m in members
                if normalisation_class(m, kv) not in ("N1", "N2")]

        # N2 x N2 combinations: the both-normalise probe family (many pairs)
        rng.shuffle(n2)
        nn = 0
        for i in range(len(n2)):
            if nn >= max_both_per_class:
                break
            a = n2[i]
            for b in n2[i + 1:]:
                p = _try(a, b)
                if p:
                    pairs.append(p)
                    nn += 1
                    if max_total and len(pairs) >= max_total:
                        return pairs
                    break

        # N1 x N1, then the rest, sampled
        rng.shuffle(n1)
        rng.shuffle(rest)
        ordered = n1 + rest
        n = 0
        for i in range(len(ordered)):
            if max_pairs_per_class and n >= max_pairs_per_class:
                break
            a = ordered[i]
            for b in ordered[i + 1:]:
                p = _try(a, b)
                if p:
                    pairs.append(p)
                    n += 1
                    if max_total and len(pairs) >= max_total:
                        return pairs
                    break
    return pairs


_DICT_CACHES: dict = {}


def dictionary_syllables(limit_words=400000, cache_path=None):
    """Syllables mined from several pythainlp word lists.

    Sources (merged, deduped): ``thai_words`` (thaithai), ``thai_orst_words``
    (Royal Society), ``thai_icu_words`` (ICU dictionary) and
    ``thai_syllables``. This is the "known library / dictionary" source for
    same-สระ/มาตรา positive pairs and extra negative candidates. Loaded lazily
    and persisted to ``cache_path`` (JSON) so regeneration is fast.
    """
    key = cache_path or "__default__"
    if key in _DICT_CACHES:
        return _DICT_CACHES[key]
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            _DICT_CACHES[key] = json.load(f)
        return _DICT_CACHES[key]
    from pythainlp.tokenize import syllable_tokenize
    out = set()
    seen_words = set()

    def _feed(words):
        n = 0
        for w in words:
            if not isinstance(w, str) or not w:
                continue
            if w in seen_words:
                continue
            seen_words.add(w)
            try:
                out.update(syllable_tokenize(w, engine="ssg"))
            except _DICT_EXC:
                pass
            n += 1
            if n >= limit_words:
                break

    try:
        from pythainlp.corpus.common import thai_words
        _feed(thai_words())
    except _DICT_EXC as e:
        print(f"  [dict] thai_words unavailable: {e}", flush=True)
    for mod_name in ("thai_orst_words", "thai_syllables"):
        try:
            import pythainlp.corpus as _pc
            fn = getattr(_pc, mod_name)
            _feed(fn() if callable(fn) else fn)
        except _DICT_EXC as e:
            print(f"  [dict] {mod_name} unavailable: {e}", flush=True)
    _DICT_CACHES[key] = _finish_dict(out)
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(_DICT_CACHES[key], f, ensure_ascii=False)
    return _DICT_CACHES[key]


def _finish_dict(out):
    """Filter mined syllables: pure-Thai single whitelisted syllables -- this
    drops ssg over-merges (แลลอด), fragments (ทธิ์, หัตถ์น), corpus junk and
    most transliterated loanwords (ไดรว์, เบราว์) from dict-sourced
    candidates. (The whitelist is now enforced inside is_clean_syllable.)"""
    return clean_syllables(sorted(x for x in out if x))


# ---------------------------------------------------------------------------
# 3. Negative edge-case pools
# ---------------------------------------------------------------------------
# short <-> long สระ counterparts (same มาตรา, opposite vowel length).
# เจ็ด (เอะ) vs เชด (เอ), แข็ง (แอะ) vs แขง (แอ): NOT rhymes.
VOWEL_LENGTH_SWAP: dict = {
    "อะ": "อา", "อา": "อะ",
    "อิ": "อี", "อี": "อิ",
    "อุ": "อู", "อู": "อุ",
    "เอะ": "เอ", "เอ": "เอะ",
    "แอะ": "แอ", "แอ": "แอะ",
    "โอะ": "โอ", "โอ": "โอะ",
    "เออะ": "เออ", "เออ": "เออะ",
    "เอาะ": "ออ", "ออ": "เอาะ",
}

# ร/ล/ว finals where old pythainlp disagrees with the 5.3.5 core
# (e.g. ตัว: old (อะ,เกอว) vs new (อัว,กา); ทร: old กด vs new กน;
#  หงส์: old returns an error string). Computed from the inventory in
#  ``liquid_final_pool`` and augmented with these curated seeds.
LIQUID_FINAL_SEEDS = [
    "ตัว", "กลัว", "ชั่ว", "ทร", "วร", "บวร", "หงส์", "หน", "สาว", "ขาว",
    "จร", "พร", "พล", "ผล", "กล", "พาล", "สาร", "ธาร", "สาล", "บาล",
]

# ห/อ นำ (leading) words -- can be confused for something else by weak
# segmentation / mattra logic.
LEAD_POOL = [
    "หงส์", "หน", "หนา", "หนี", "หนึ่ง", "หมอก", "หมาก", "หมู", "เหงา",
    "ใหญ่", "อยาก", "อย่า", "อยู่", "อย่าง", "เห็น", "หมั้น", "หมื่น",
    "หม้อ", "หยุด", "หยิบ", "หยิ่ง", "หนาว", "หน่าย", "เหม็น", "หงาย",
]

# final ร silent from Pali/Sanskrit roots (NOT การันต์) -- เพชร = /phet/.
# These rhyme with the สระ เอะ + แม่กด family the oracle cannot see.
SILENT_R_TRAPS = [
    "เพชร", "เพ็ด", "เห็ด", "เจ็ด", "เบ็ด", "เกร็ด",
    "เนตร", "มิตร", "บัตร", "บุตร", "เกษตร", "กอปร",
]
KARUN_TRAPS = [
    "กษัตริย์", "สัด", "สรรเพชญ", "ปฏิสนธิ์", "วิศวกรรม",
    "อินทรีย์", "สัปดาห์", "จันทร์", "ภาพยนตร์", "กาสาวพัสตร์", "ลิขสิทธิ์",
    "ธำมรงค์", "โอห์ม", "รามเกียรติ์", "ฤทธิ์", "ฤกษ์",
]
RO_TRAPS = [
    "ฤทธิ์", "ฤกษ์", "พฤษภ", "ทฤษฎี", "กฤษ", "กฤษณะ", "ฤดู", "ฤา",
    "ฤๅ", "ฤๅษี",
]
CLUSTER_TRAPS = [
    "สวรรค์", "ทรลักษณ์", "เพชร", "สรรเพชญ", "กลั่น", "ครอบ", "ครวญ", "ไทร",
    "ปรโลก", "จรลี", "ทรยศ", "นรสิงห์", "หรดี", "อรทัย",
]
TRUE_FINAL_TRAPS = [
    "ใจ", "ไจ", "ใหญ่", "ไหย่", "ไทย", "ทัย", "ชัย", "ไช", "กลัว", "ตัว",
    "เสีย", "เสียว", "เปล", "แปร", "โปร", "ไกล", "ใกล้", "ไกว",
]

# Words the 5.3.5 oracle MISREADS: final ร silent from Pali/Sanskrit roots
# (NOT การันต์) makes them true สระ เอะ + แม่กด, but the oracle keeps the long
# เอ (no ็ on the dead final). Author-confirmed: anything with สระ เอะ + แม่กด
# rhymes with เพชร (เพ็ด เห็ด เจ็ด เบ็ด เกร็ด ...). These are the ONLY
# documented, author-confirmed oracle-blind single syllables, so the C8 probe
# is restricted to them.
ORACLE_BLIND_POOL: list[str] = ["เพชร", "เนตร", "เกษตร"]

# Linguistic rhyme family (rhyme class of the partner side) each oracle-blind
# word belongs to. The C8 probe only fires when the rhyme TARGET is in this
# family, so it genuinely tests oracle blindness.
ORACLE_BLIND_FAMILIES: dict = {
    "เพชร": ("เอะ", "กด"),
    "เนตร": ("เอะ", "กด"),
    "เกษตร": ("เอะ", "กด"),
}


def liquid_final_pool(inv, kv, old_kv) -> list:
    """ร/ล/ว final words where old pythainlp disagrees with the 5.3.5 core
    (computed from the inventory) plus curated seeds."""
    out = set(LIQUID_FINAL_SEEDS)
    for w in inv:
        if w and w[-1] in "รลว":
            try:
                if old_kv.check_marttra(w) != kv.check_marttra(w):
                    out.add(w)
            except _OLD_CORE_EXC:
                out.add(w)
    return sorted(out)


EXTRA_SYLLABLES: list[str] = sorted(set(
    SILENT_R_TRAPS + KARUN_TRAPS + RO_TRAPS + CLUSTER_TRAPS + TRUE_FINAL_TRAPS
    + LEAD_POOL + LIQUID_FINAL_SEEDS
    + [b for _a, b in HARD_POSITIVE_PAIRS]
    + [a for a, _b in HARD_POSITIVE_PAIRS]
))
