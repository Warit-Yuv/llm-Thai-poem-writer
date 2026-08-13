# PyThaiNLP PR #1453 — KhaveeVerifier logic fixes

**PR title:** *Fix the logic of `check_sara`, `check_marttra`, `is_sumpus`, `handle_karun_sound_silence`*
**Repository:** [PyThaiNLP/pythainlp](https://github.com/PyThaiNLP/pythainlp)
**PR link:** https://github.com/PyThaiNLP/pythainlp/pull/1453
**Author:** [@Warit-Yuv](https://github.com/Warit-Yuv) (contributor)
**Reviewer / merger:** [@wannaphong](https://github.com/wannaphong) (approved and merged)
**Status:** ✅ Merged — merge commit `0cde97c` into `PyThaiNLP:main`
**Milestone:** 6.0 · **Label:** `bug` · **Commits:** 45 · **Files changed:** 4

---

## 1. Overview

This PR fixes several defects in the Thai poetry/rhyme submodule
`pythainlp/khavee/core.py` (`KhaveeVerifier`). It improves:

- vowel (`สระ`) detection — `check_sara`
- syllable spelling-section (`มาตราตัวสะกด`) classification — `check_marttra`
- rhyme (`สัมผัส`) matching logic — `is_sumpus`
- silent-suffix (ตัวการันต์, `-์`) stripping — `handle_karun_sound_silence`

to ensure stricter compliance with standard Thai grammar and the Royal Society of
Thailand (ราชบัณฑิตยสภา) orthographic conventions.

A new internal helper `_is_true_final()` was introduced to distinguish *true*
final consonants from letters that are really part of an initial cluster
(คำควบกล้ำ / อักษรนำ) or a vowel digraph. `check_klon` was also rewritten
(stanza-based, uses the `ssg` syllable segmenter, adds inter-stanza rhyme
checking), and `check_karu_lahu` was refactored.

### Files changed (4)

| File | Change |
|---|---|
| `pythainlp/khavee/core.py` | Main logic fixes; new `_is_true_final`; class-level constants; rewritten `check_klon` / `check_karu_lahu` |
| `tests/core/test_khavee.py` | Massively expanded `check_sara` / `check_marttra` / `is_sumpus` / `handle_karun_sound_silence` / `_is_true_final` / `check_karu_lahu` / `check_aek_too` coverage |
| `tests/extra/test_khavee_extended.py` | **New file** — `check_klon` tests moved here (requires the extra `ssg` dependency) |
| `tests/extra/__init__.py` | Registers the new `test_khavee_extended.py` module |

---

## 2. Change-by-change documentation (code + reason)

### 2.1 Complex silent suffix handling — `handle_karun_sound_silence`

**Reason (from PR description):**
> The previous hardcoded string truncation logic (`word[:-2]`) assumes that all
> silent markers cover exactly *one consonant + one Karun* (`-์`). It fails entirely
> on multi-letter silent suffixes or clusters containing quiet vowels (e.g. ธุ์, ธิ์,
> ตริย์), leaving leftover unpronounced letters that disrupt vowel and syllable checks.

**What changed:**

```python
# BEFORE — naive: drop Karun + exactly 1 preceding char
sound_silenced = word.endswith("์")
if not sound_silenced:
    return word
word = word[:-2]          # WRONG for ธิ์, ตริย์, ษมณ์, ...
return word

# AFTER — pattern-aware stripping, only when Karun is the FINAL char
if not word.endswith("์"):
    return word           # (โอห์ม = Karun mid-word → not processed)

# multi-letter Karun silent suffixes
if word.endswith("กษมณ์"):      # พระลักษมณ์ → พระลัก
    return word[:-4]
if word.endswith("กษณ์"):       # ลักษณ์, ทรลักษณ์ (avoid breaking สัมภาษณ์)
    return word[:-3]
if word.endswith("ตริย์"):      # กษัตริย์ → กษัต
    return word[:-4]
if word.endswith("ญจน์"):      # กาญจน์ (avoid breaking โรจน์)
    return word[:-3]

# 2-consonant Karun suffixes
# ตร์: ศาสตร์, ภาพยนตร์, กาสาวพัสตร์, เวทมนตร์
# ทร์: จันทร์, บดินทร์, ภูมินทร์, นราธิเบนทร์
# ดร์: นิรันดร์   ฎร์: ราษฎร์, สุราษฎร์
if word.endswith(("ตร์", "ทร์", "ดร์", "ฎร์")):
    return word[:-3]

# standard 1-consonant (+optional vowel) + Karun: สัตว์(ว์), แพทย์(ย์), พันธุ์(ธิ์)
if len(word) >= 3 and word[-2] in {"ิ", "ี", "ึ", "ื", "ุ", "ู", "ั"}:
    return word[:-3]      # vowel sits right before the Karun
else:
    return word[:-2]
```

**Reason (author, in review discussion):** the `-์`-silenced final vowel must be
stripped because it is orthographically present but phonetically silent; stripping
it is harmless in `check_sara` (leading vowel is detected first) and *necessary* in
`check_marttra` to expose the true final consonant for spelling-section
classification.

**Tests added** (`KhaveeHandleKarunTestCase`):

```python
kv.handle_karun_sound_silence("จันทร์")        # -> "จัน"
kv.handle_karun_sound_silence("สิทธิ์")         # -> "สิท"
kv.handle_karun_sound_silence("กษัตริย์")       # -> "กษัต"
kv.handle_karun_sound_silence("พระลักษมณ์")    # -> "พระลัก"
kv.handle_karun_sound_silence("อินทรีย์")       # -> "อินทรี"
kv.handle_karun_sound_silence("ภาพยนตร์")      # -> "ภาพยน"
kv.handle_karun_sound_silence("กาสาวพัสตร์")    # -> "กาสาวพัส"
kv.handle_karun_sound_silence("ไปรษณีย์")       # -> "ไปรษณี"
kv.handle_karun_sound_silence("วิศวกรรมศาสตร์") # -> "วิศวกรรมศาส"
```
Internal Karun (การ์ตูน, โอห์ม, กอล์ฟ, ฟิล์ม) is left untouched.

---

### 2.2 Initial cluster & semi-vowel separation — new `_is_true_final`

**Reason (from PR description):**
> The deprecated internal method `_has_true_final_yl` did not check for tone marks
> (วรรณยุกต์), failing on target words like `ใกล้` because the string ends with a
> diacritic instead of a consonant. It also misclassified instances where a letter
> functioned as a vowel component rather than a true final consonant (ตัวสะกด),
> e.g. `เสีย`, `ไทย`.

**What changed:**

```python
# _has_true_final_yl is kept as a backward-compatible alias:
def _has_true_final_yl(self, word: str) -> bool:
    return self._is_true_final(word)

def _is_true_final(self, word: str) -> bool:
    # 1. strip Karun, keep original for tone-dependent structures
    word = self.handle_karun_sound_silence(word)
    original_word = word
    word = remove_tonemark(word)          # ใกล้ -> กล → ends in ล
    if len(word) < 2:
        return False
    last_char = word[-1]
    consonants = [c for c in word if c in self.VALID_CONSONANTS]  # ฤ/ฦ included
    if len(consonants) < 2:
        return False

    # ย inside เ-ีย (เสีย, เมีย) or after ไ/ใ (ไทย, ไชย) is a vowel, not final
    if last_char == "ย" and (("ไ" in word or "ใ" in word)
                             or ("เ" in word and "ี" in word)):
        return False

    # guard: only ล/ร/ว with exactly 2 consonants + pre-posed vowels need checking
    if last_char not in "ลรว" or len(consonants) != 2:
        return True
    if not ("เ" in word or "แ" in word or "โ" in word or "ไ" in word or "ใ" in word):
        return True

    if last_char == "ล" and cluster in self._LAM_CLUSTERS:  # กล ขล คล ปล ผล พล หล ถล ฉล สล ศล ตล
        return word == "เพล"            # only เพล stays แม่กน
    if last_char == "ร" and cluster in self._RUA_CLUSTERS:  # กร ขร คร ตร ปร พร ฟร บร ศร สร หร
        return False
    if last_char == "ว":
        if ("ไ" in word or "ใ" in word) and cluster in self._WA_CLUSTERS:
            return False                # ไกว, ไขว้: ว is ALWAYS a cluster
        elif ("เ" in word or "แ" in word or "โ" in word):
            if original_word in self._WA_WHITELIST:   # เขว เหว่ แคว แหว โคว โหว โหว่
                return False
            # otherwise ว is a true final: เลว, เหว, แก้ว, แห้ว
    return True                         # จัย, สมัย, ชล, ผล, เหนื่อย
```

**Reason (documented in code/PR):** native Thai clusters (คำควบกล้ำ) and leading
consonants (อักษรนำ) paired with pre-posed vowels (`เ-`, `แ-`, `โ-`, `ไ-`, `ใ-`)
must not have their semi-vowels/liquids (`ล`, `ร`, `ว`) falsely flagged as final
consonants.

**Verification shown in PR:**

```
# Previous:                          # After:
เสีย  true final: True  Marttra: เกย   เสีย  true final: False  Marttra: กา
ไกล  true final: True  Marttra: เกย   ไกล  true final: False  Marttra: กา
ไทย  true final: True  Marttra: เกย   ไทย  true final: False  Marttra: กา
ใกล้  true final: False Marttra: เกย   ใกล้  true final: False Marttra: กา
ไกว  true final: False Marttra: กา    ไกว  true final: False Marttra: กา
ใคร  true final: False Marttra: กา    ใคร  true final: False Marttra: กา
แปร  true final: False Marttra: กน    แปร  true final: False Marttra: กา
```

**Tests added** (`KhaveeIsTrueFinalTestCase`):
- true finals: `จัย`, `สมัย`, `เลื่อย`, `เปื่อย`, `เฉื่อย`, `เหนื่อย`
- fake finals: `ไทย`, `ใคร`, `ไกล`, `ใกล้`, `เสีย`, `ไกว`, `โปร`, `แปร`, `เปล`, `ไฟล์`

---

### 2.3 Syllable spelling-section corrections — `check_marttra`

**Reason (from PR description):**
> Words disguised by initial consonant clusters (คำควบกล้ำ) wrapped in pre-posed
> vowels (e.g. `เขว`, `แปร`, `ไถล`) were previously misclassified into incorrect
> closed-syllable sections มาตราตัวสะกด (e.g. แม่เกอว, แม่กน) instead of แม่ ก กา.
> Standalone words representing individual letters (e.g. `ธ`, `ณ`) were also
> assigned to closed categories.

**What changed (highlights):**

```python
# BEFORE:                                            AFTER:
kv.check_marttra("พาล") -> "เกย"  (misclassified)    kv.check_marttra("พาล") -> "กน"
kv.check_marttra("ธ")   -> "กด"   (wrong assignment) kv.check_marttra("ธ")   -> "กา"

# new flow:
word = self.handle_karun_sound_silence(word)   # resolve Karun FIRST
original_word = word
word = remove_tonemark(word)

# 1) strip silent terminal vowels of Pali/Sanskrit loans
if word.endswith(self._MASKING_TERMINAL_VOWELS):   # เกียรติ ชาติ ญาติ ... ภูมิ พฤติ ... เกตุ เมรุ เหตุ ธาตุ วุฒิ สมมุติ วิมุติ
    word = word[:-1]

# 2) smarter cluster ending in ร:
if len(word) >= 3 and word[-1] == "ร":
    if prev_char in {"ต", "ช", "ป"}:            # บุตร เนตร มิตร เกษตร บัตร เพชร กอปร -> always strip
        word = word[:-1]
    elif prev_char in {"ก", "ข", "ค", "ฆ", "ท"}:  # จักร vs มังกร / สมุทร vs สุนทร
        if word[-3] in {"ั", "ิ", "ี", "ุ", "ู"}:   # short vowel before cluster -> strip
            word = word[:-1]                     # จั-ก-ร, สมุ-ท-ร

# 3) standalone letters -> open syllable
if word in self._SINGLE_CHAR_WORDS:  # {"บ", "ณ", "ธ", "พณ", "ฤ", "ฦ"}
    return "กา"

# 4) สระเกิน (อำ, ไอ, ใอ, เอา) -> orthographic แม่ ก กา (per Royal Society)
if word[-1] == "ำ" or word.endswith("ํา"):
    return "กา"
if word.endswith("ํ"):
    return "กง"

# 5) cluster check via _is_true_final
if word[-1] in "ยลรว" and ("เ" in word or "แ" in word or "โ" in word):
    if not self._is_true_final(original_word):
        return "กา"                       # เขว แปร ไกล ไกว เปล โปร ...

# 6) open-syllable vowel endings (incl. รากยาว "ๅ", เอีย/เอือ/อัว catches)
if (last_char in self._OPEN_SYLLABLE_VOWELS
        or ("ี" in word and last_char == "ย")   # เสีย เมีย
        or ("ื" in word and last_char == "อ")   # เรือ เสือ
        or ("ั" in word and last_char == "ว")): # ตัว ชั่ว กลัว
    return "กา"

# 7) final-consonant dispatch now uses frozensets: _KOK_CHARS _KOD_CHARS _KON_CHARS _KOB_CHARS
#    unknown -> "กา"  (was "Can't find Marttra in this word")
```

**Reason (documented note):**
> English loanwords ending in an "L" sound (`ล`) (e.g. แอปเปิล, โมเดล, เลเวล,
> ฟุตบอล) will continue to default to แม่กน under this orthographic checker.
> Improvement could be made later to handle poetic variations that treat these as
> แม่เกอว for rhyming purposes.

`check_marttra` now **strictly follows orthography (รูป)**, not phonetics: สระเกิน
(อำ, ไอ, ใอ, เอา) and ฤ/ฤๅ/ฦ/ฦๅ are grammatically แม่ ก กา; phonetic rhyming for
these is handled dynamically in `is_sumpus`.

**Tests added:** ~100 new assertions, e.g. `ไทย/ไกล/ใกล้/เสีย/เปล/ไกว/โปร/แปร/ไฟล์ → กา`,
`พาล → กน`, `ธ/ณ/พณ/บ → กา`, `ขำ/จำ → กา` (was `กม`), `กอปร → กบ`, `ชาต/เกียรติ/สมมุติ → กด`, `ธรรม → กม`.

---

### 2.4 Vowel invariant & transformation rules — `check_sara`

**Reason (from PR description):**
> Sequential loop conditions shadowed each other (causing bugs like the `"อัว"`
> parsing defect), and unsafe list operations were applied when merging raw `"เ"`
> characters into `"แ"`. The processing loop was standardized to cleanly handle
> compound vowels, the shadowing logic was fixed, and fast substring constraints
> were added for the variant realizations of `"ฤ"` / `"ฦ"` (เออ, อิ, อึ).
> Transformed and reduced vowels (สระเปลี่ยนรูป / สระลดรูป) were integrated using
> the Mai Tai Khu diacritic (`-็`).

**What changed (highlights):**

```python
original_word = word                     # keep for exceptions (ฤทธิ์) AFTER karun strip
word = self.handle_karun_sound_silence(word)
word_req = remove_tonemark(word)
if not word_req:  return ""              # "", "อ์", "้", ...

# silent terminal vowel of Pali/Sanskrit loans
if word_req.endswith(self._MASKING_TERMINAL_VOWELS):
    word, word_req = word[:-1], word_req[:-1]

# per-char loop (fixes shadowing):
#   "ั" + endswith("ว")  -> อัว   (was: `elif i == "ั" and "ว" in word` — buggy)
#   "็" now appends "็" (marker) instead of "ออ"; resolved later via ไม้ไต่คู้
#   "รร" removed from the loop (was evaluated per character → handled once below)

# ไม้ไต่คู้ (สระเปลี่ยนรูป/ลดรูป) resolution
if "็" in sara:
    sara.remove("็")
    if "เอ" in sara:    sara = ... "เอะ"    # เจ็ด เป็น เด็ก
    elif "แอ" in sara:  sara = ... "แอะ"    # แข็ง แท็กซี่ แย็บ
    else:               sara = ... "เอาะ"   # ก็ ล็อก ผล็อย

# merging rules now guarded / commented
if "เอ" in sara and "อิ" in sara: -> เออ     # เกิด เมิน
elif "อ" == word[-1] and "เอ" in sara and "ออ" in sara: -> เออ   # เหม่อ
elif "โอ" in sara and "อะ" in sara: -> โอะ   # โตะ
elif "เอ" in sara and "อี" in sara: -> เอีย   # เรียน
if "อือ" in sara and "เออ" in sara: -> เอือ   # มะเขือ เสือ เงือก

# รร handled exactly once, outside the loop
if "รร" in word:
    sara.append("อำ" if self.check_marttra(word) == "กม" else "อะ")

# เ-ย (ลดรูป เ-อ): เลย เคย เอย -> เออ (guarded so เตียง stays เอีย)
if "เอ" in sara and word_req.endswith("ย") and self._is_true_final(original_word):
    if not [v for v in sara if v not in {"เอ", "ออ"}]:
        sara = ["เออ"]

# ฤ/ฦ variants — evaluated on ORIGINAL word (before karun strip)
if any(ex in original_word for ex in ("ฤา", "ฤๅ", "ฦา", "ฦๅ")):   sara = ["อือ"]
elif "ฤ" in original_word or "ฦ" in original_word:
    if word == "ฤก" or original_word.startswith("ฤกษ"):            sara.append("เออ")  # ฤกษ์ -> เริก
    elif any(ex in original_word for ex in ("กฤช","กฤต","กฤษ","ตฤต","ตฤณ","ทฤษ","ปฤษ","ศฤง","สฤต","ฤทธ")):
        sara.append("อิ")                                          # ฤทธิ์ อังกฤษ กฤษณ์
    else:                                                          sara.append("อึ")    # ฤดู ฤทัย พฤษภาคม

# reduced vowels fallback
if not sara and len(word) >= 2:
    sara.append("ออ" if word[-1] == "ร" else "โอะ")   # พร นคร / นม กรด

# นิกหิต: "ํา" -> อำ (typo fix), standalone "ํ" -> อะ (อัง)
# isolated symbols: บ -> ออ ; ณ ธ อ พณ -> อะ
# explicit sara words via frozenset _EXPLICIT_SARA_WORDS = {เออะ เออ เอ เอะ เอา เอาะ}
# final fallback: return "อะ"  (was "" )
```

**Copilot review finding + fix:** `check_sara()` stripped Karun suffixes *before*
the ฤ/ฦ heuristics, so `ฤทธิ์` became `ฤท` and the `ฤทธ` substring no longer
matched (falling through to default `อึ`). Fixed by commit
`b75e409` *"Fix check_sara ฤ evaluation in the word with silent Karun"* — exception
matching now uses `original_word`.

**Copilot review finding + fix:** `elif "รร" in word:` ran inside the per-character
loop, calling `check_marttra` repeatedly and appending the รร-vowel multiple times.
Fixed by commit `f780e36` *"fix the รร loop logic in check_sara"* — now evaluated
once, outside the loop.

**Verification shown in PR:**

```
# Previous:                      # After:
เลย  Sara: เอ  Marttra: เกย       เลย  Sara: เออ  Marttra: เกย
พวก  Sara: อัว  Marttra: กก       พวก  Sara: อัว  Marttra: กก
เจ็ด  Sara: เอ  Marttra: กด       เจ็ด  Sara: เอะ  Marttra: กด
แข็ง  Sara: แอ  Marttra: กง       แข็ง  Sara: แอะ  Marttra: กง
ก็    Sara: ออ  Marttra: กา       ก็    Sara: เอาะ Marttra: กา
```

---

### 2.5 Control-flow refactoring for rhyme matching — `is_sumpus`

**Reason (from PR description):**
> The sequential `elif` structure allowed arguments to short-circuit early, which
> caused asymmetric matching failures if `word1` normalized but `word2` did not.

**What changed:**

```python
# BEFORE:  if/elif — only ONE side got normalized          # AFTER: isolated ifs — BOTH sides normalize
if sara1 == "อะ" and marttra1 == "เกย":   -> "ไอ"/"กา"     if sara1 == "อะ" and marttra1 == "เกย":   -> ...
elif sara2 == "อะ" and marttra2 == "เกย": -> "ไอ"/"กา"     if sara2 == "อะ" and marttra2 == "เกย":   -> ...
if sara1 == "อำ" and marttra1 == "กม":    -> "อำ"/"กา"     if (sara1 == "อะ" or sara1 == "อำ") and marttra1 == "กม": -> ...
elif sara2 == "อำ" and marttra2 == "กม":  -> "อำ"/"กา"     if (sara2 == "อะ" or sara2 == "อำ") and marttra2 == "กม": -> ...
return bool(marttra1 == marttra2 and sara1 == sara2)

# also: empty input guard added
if not word1 or not word2:
    return False
```

**Reason (documented in code):** normalization of สระเกิน (อำ, ไอ, ใอ) — while
`check_marttra` classifies `วัย` as อะ+เกย and `ใจ` as ไอ+กา, poetry cares about the
*sound* (เสียง), so the phonetic CVC structures are normalized into their สระเกิน
counterparts (`เอา` needs no normalizer since native spelling forces `/aw/` via `เ-า`).

**What it fixes (from PR):**
- aligns `"อะ"` + `"แม่เกย"` into `"ไอ"` + `"แม่กา"` (กัย ~ ไก ~ ไกล)
- bridges the poetic concordance of `อรรม` / `อัม` / `อำ` → e.g. `ธรรม - สัม - จำ` all rhyme.

**Verification shown in PR:**

```python
kv.is_sumpus("บ้าน", "พาล")   # True
kv.is_sumpus("ธรรม", "สัม")   # True
kv.is_sumpus("ธรรม", "จำ")    # True
kv.is_sumpus("กัย", "ไก")     # True
kv.is_sumpus("ใจ", "ไทย")     # True
```

---

## 3. Other changes in the same PR

### 3.1 `check_klon` — full rewrite (stanza-based + `ssg`)

- Raises `ImportError` if the `ssg` library is missing:
  `"The 'ssg' library is required for comprehensive poem analysis (check_klon). Please install it using: pip install ssg"`.
- Rejects any `k_type` other than 4 or 8.
- Splits the poem into waks (`text.split()`), requires complete stanzas:
  `"The poem does not have complete stanzas (บท). A stanza must contain exactly 4 sentences (วรรค)."`
- Tokenizes each wak with `subword_tokenize(wak, engine="ssg")` — **direct CRF
  syllable segmentation, no word pre-segmentation** (this is the Model-B path
  described in the iSAI paper).
- Evaluates per stanza:
  - word-count limit: 10 for Klon 8, 5 for Klon 4
  - Rule 1 (สดับ→รับ), Rule 2 (รับ→รอง), Rule 3 (รอง→ส่ง),
    Rule 4 inter-stanza rhyme (ผิดสัมผัสระหว่างบท) against previous stanza's Wak 4.
  - Klon 8 targets = first 5 syllables of Wak 2/4 (อนุโลม 1,2,4 / บังคับ 3,5);
    Klon 4 targets = first 2 (or 3 if wak has 5 words).
- New structured error messages, e.g.
  `"Rhyme error in Stanza (บทที่) 1: 'มาก' (Wak 1) does not rhyme with ['คน', 'อื่น', 'สัก', 'หมื่น', 'แสน'] (Wak 2)"`.
- Failure now returns `f"Something went wrong during evaluation: {e}"` instead of a
  generic message.
- Extensive ASCII-art docstring diagrams of Klon 4 / Klon 8 rhyme structure
  (สดับ/รับ/รอง/ส่ง).

### 3.2 `check_karu_lahu` — refactor

- Return type `Union[str, bool]`; empty string → `False`.
- `_LAHU_SYLLABLE_OVERRIDES = {"บ", "บ่", "ณ", "ธ", "ก็", "ฤ", "ฦ"}` always light.
- karu = `marttra != "กา"` **or** long vowel (`_LONG_VOWELS`) **or** special vowel
  (`_SPECIAL_VOWELS = {อำ, ไอ, เอา}`), evaluated with pre-computed frozensets.
- Tests consolidated into data-driven `test_karu_words` / `test_lahu_words` /
  `test_invalid_karu_lahu_words`.

### 3.3 `check_aek_too` — simplification

- Replaced `word_characters = [*text]` list scanning with direct substring checks
  (`"่" in text`, `"้" in text`).

### 3.4 Class-level constants (performance)

- `VALID_CONSONANTS = frozenset(thai_consonants + "ฤฦ")`
- `_MASKING_TERMINAL_VOWELS`, `_LAHU_SYLLABLE_OVERRIDES`, `_SINGLE_CHAR_WORDS`
- `_LAM_CLUSTERS`, `_RUA_CLUSTERS`, `_WA_CLUSTERS`, `_WA_WHITELIST`
- `_OPEN_SYLLABLE_VOWELS`, `_KOK_CHARS`, `_KOD_CHARS`, `_KON_CHARS`, `_KOB_CHARS`
- `_LONG_VOWELS`, `_SPECIAL_VOWELS`, `_EXPLICIT_SARA_WORDS`

### 3.5 Documentation

- Full class docstring for `KhaveeVerifier` (capabilities, examples, `ssg` note).
- Doctest fixes and expansions (e.g. `is_sumpus("จำ","กรรม")`, `check_klon` examples).
- `# pylint: disable=protected-access` in tests for `_is_true_final` / `_has_true_final_yl`.

---

## 4. Review discussion & documented rationale (select highlights)

| Topic | Reason given |
|---|---|
| **Silent vowel exceptions are suffix-only** | Author: words like `เกียรติ` / `ชาติ` / `ธรรมชาติ` are silent *as suffixes* (`พระเกียรติ` → พระ-เกียด, `ธรรมชาติ` → ทัม-มะ-ชาด). Tokenizer cannot be guaranteed to split these, so list-inclusion is wrong; `endswith` is justified. `ชาติพันธุ์` (ชาด-ติ-พัน) shows it is *not* silent as an infix/prefix. |
| **`check_sara` strips Karun before ฤ/ฦ** | Copilot (Medium): `ฤทธิ์` → `ฤท` broke `ฤทธ` matching → fixed by evaluating exceptions on `original_word` (commit `b75e409`). |
| **`รร` inside per-char loop** | Copilot (Medium): duplicated vowels / repeated `check_marttra` → fixed, evaluated once (commit `f780e36`). |
| **`_is_true_final` cognitive complexity** | Author: cannot go below ~15 complexity without splitting into subfunctions, which the author judged worse; later refactored anyway (commit `738eef7` "Refactor _is_true_final to reduce complexity"). |
| **English loanwords ending in -ล** | Documented limitation: แอปเปิล/โมเดล/เลเวล/ฟุตบอล default to แม่กน (orthographic); poetic แม่เกอว treatment deferred. |

**Reviewers:** Copilot code review (4 comments, all resolved) + human approval by
`@wannaphong`. SonarQube Cloud quality gate passed. `@bact` added the `bug` label.

---

## 5. Notable commits (selection)

| Commit | Message |
|---|---|
| `c88e5e3` | Refactor `_has_true_final_yl` method for clarity |
| `6cb76a5` | Refactor final consonant checks in KhaveeVerifier |
| `139b0de` | Add สระประสม transformed vowels classifier to `check_sara`, fix คำโดด |
| `b75e409` | Fix `check_sara` ฤ evaluation in the word with silent Karun |
| `f780e36` | Fix the รร loop logic in `check_sara` |
| `03d123b` | Add many more test cases; fix category of ไทย ไกล ใกล้ |
| `9085b57` | Fix นิกหิต `-ํ` and รากยาว `ๅ` / ฤ ฤๅ logic |
| `738eef7` | Refactor `_is_true_final` to reduce complexity |
| `e85c13e` | Rewrite `check_klon`, `test_khavee.py` |
| `54ed2b7` | Move `check_klon` tests to new `test_khavee_extended.py` |
| `3a46dde` | perf(khavee): optimize character lookups, simplify klon output |
| `b5962d8` | refactor(khavee): harden edge cases, improve marttra cluster logic |
| `b3e9378` | perf(khavee): move repeated sets to class constants |
| `7d2769c` | fix(khavee): remove redundant marttra check, fix assertEqual arg order |
| `0cde97c` | **Merge commit** into `PyThaiNLP:main` |

---

## 6. Impact on the iSAI paper (Model B = PyThaiNLP 5.3.5 `KhaveeVerifier`)

- `check_sara` / `check_marttra` / `is_sumpus` behavior changed materially — any
  numbers reported for Model B were computed against the **pre-fix** logic; results
  will shift if re-run against this PR's merged code (scheduled for PyThaiNLP 6.0).
- `check_klon` now hard-requires the `ssg` package (which our `_dev_core.py`
  already uses via `subword_tokenize(engine="ssg")`) and checks **inter-stanza
  rhyme** (สัมผัสระหว่างบท), which the previous implementation did not verify.
- Rhyme now normalizes `อรรม/อัม/อำ` and `อัย/ไอ` phonetically, matching the strict
  Thai poetic constraints our paper assumes (e.g. `จิต`~`มิตร`, `มิตร`~`ผิด`).
