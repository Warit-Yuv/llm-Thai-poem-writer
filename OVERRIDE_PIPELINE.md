# Override Pipeline & Syllable Checking — Documentation

## 1. What this project is trying to do

Three goals, in order of dependency:

1. **A robust Thai syllable pronouncer & counter** — given any Klon-8 line (วรรค),
   produce the correct sequence of pronounced syllables (and therefore the
   correct syllable count, which Klon prosody depends on).
2. **A robust Klon rhyme checker** — using the improved
   `KhaveeVerifier` (`pythainlp.khavee`) to validate สัมผัส (rhyme), เอก/โท
   (tone positions), and syllable counts.
3. **A data-processing framework** for much larger corpora (target: ~10× the
   current Phra Aphai Mani dataset, ~80–100k waks). It will feed:
   - LLM fine-tuning data,
   - a teacher-facing validator for student Klon writing,
   - an environment for RL training / model validation.

`klonpad_validator.ipynb` is the **testing playground** for syllable extraction
and Klon checking. The production version will be a real Python module
(syllable extractor + Klon checker) that reuses everything built here.

---

## 2. The core problem: w2p hallucination

Syllable splitting ultimately falls back to `pronunciate(word, engine="w2p")`,
a machine-learning transliterator. It is usually right, but it **hallucinates on
~2–4% of words**, especially Pali/Sanskrit loanwords and some common words:

| Word (correct)     | w2p output (hallucinated) |
|--------------------|---------------------------|
| `มิได้` → มิ-ได้    | มิ-**ด้าย** (vowel length) |
| `กระเด็น` → กระ-เด็น | กระ-**เด็ด** (wrong final) |
| `ถามไถ่` → ถาม-ไถ่ | ถาม-**ถ่าย** (vowel length) |
| `จงฟัง` → จง-ฟัง    | จง-**งัฟ** (wrong final) |
| `น้ำตา` → น้ำ-ตา    | **น้าม**-ตา (redundant final in 1st syllable!) |
| `ใหญ่โต` → ใหญ่-โต | **ผะ-หย่น** (completely wrong) |
| `ก็ตาม` → ก็-ตาม    | กะ-**โต้ม** (completely wrong) |

A wrong syllable count or wrong vowel/final breaks Klon validation, so these
must be fixed. The mechanism is a **gold-standard override dictionary**
(`POETRY_OVERRIDES`): `word -> [pronounced syllables]`. The speedup from
looking up a dict instead of running w2p inference is a bonus, not the goal
(the goal is *correctness*).

### Performance note (measured)

```
dict lookup (100k-entry dict): ~57 ns
w2p inference (per word)      : ~4.5 ms
speedup                        : ~78,000×
```

Python dict lookup is O(1) string-hashing — **dict size does not affect
speed**. A large dictionary is acceptable; we only avoid *unnecessary*
entries (see COMPOSED bucket) and, more importantly, we avoid baking
unverified w2p hallucinations into the dictionary.

---

## 3. Architecture / files

| File | Role |
|------|------|
| `poetry_overrides.py` | **THE ONLY FILE YOU EDIT.** `POETRY_OVERRIDES` = gold-standard `word -> [syllables]` (3,315 keys: curated + merged gold draft + author fixes). To fix any word: find it here, edit it. |
| `build_overrides.py` | **The pipeline.** Reads the dict, screens it (suspicious dict entries are listed in the review file), scans the corpus, generates splits for unseen words (4 hallucination guards), and buckets into AUTO / FIXED / REVIEW / COMPOSED / SKIP. |
| `poetry_overrides_generated.py` | Pipeline output: **AUTO + FIXED + COMPOSED** entries not yet in the dict → paste into `poetry_overrides.py`. |
| `poetry_overrides_generated_review.py` | **THE review file.** New-word hallucinations + suspicious entries already in the dict → fix by ear, then edit `poetry_overrides.py`. |
| `poetry_overrides_generated.screen.tsv` | Full report: every word + frequency + syllables + flags + bucket + context. |
| `override_draft_cleaner.py` | Holds the shared `screen_override()` used by the pipeline. (The old draft tooling is archived.) |
| `klonpad_validator.ipynb` | Playground. Its generator cell now just runs `build_overrides.py`. |
| `Results/Exportable/*.csv` | Source corpus: 132 chapters × stanzas, each row `w1_a..w8_c` (8 waks × 3 parts). |
| `_archive/` | Outdated/duplicate files (old draft copies, old cleaner outputs, lenient experiment). Keep as backup; delete when sure. |

---

## 4. How the pipeline works (`build_overrides.py`)

The pipeline has **four independent guards against hallucination**:

1. **GOLD input** — your hand-edited draft (`--gold`) is read as gold: its
   values are used as-is and **never regenerated** from w2p. It is still
   screened, and anything suspicious goes to REVIEW instead of being silently
   trusted (this is what surfaces draft errors like `ผู้ใด → พู่-ได`).
   A small built-in `KNOWN_GOLD_FIXES` layer (author-verified corrections)
   wins over everything:
   ```
   พหล        -> พะ-หน          (w2p & ssg both hallucinate -> พะ-หลัน)
   บาทบงกช    -> บาด-ทะ-บง-กด   (your draft still had w2p's 3-syllable error)
   เฉยเมย     -> เฉย-เมย        (both engines split the ย out)
   ระหกระเหิน -> ระ-หก-ระ-เหิน  (both merge หก+ระ into หกระ)
   ตรอมตรม    -> ตรอม-ตรม       (both break it into 4 bare fragments)
   ```
2. **PREFER-ORTHOGRAPHY** (`prefer_ssg_split`) — when ssg and w2p agree on
   syllable count and every ssg syllable is sound-equivalent (`is_sumpus`),
   keep the **ssg orthographic split**. This preserves original spelling and
   **tone marks**, which matters for เอก/โท checking:
   ```
   ใช้  -> ใช้  (not ไช้)      สาคร  -> สา-คร  (not สา-คอน)
   อยู่ -> อยู่ (not หยู่)      ประชากร -> ประ-ชา-กร (not ...-กอน)
   ผู้  -> ผู้  (not พู่)       ไพร่ฟ้าข้าแผ่นดิน -> ...ข้า... (not ข่า)
   ```
3. **COMPOSITION** (`compose_from_parts`) — before running w2p, try to
   decompose the word into already-covered parts (main dict + gold + accepted
   candidates). If it decomposes, the syllables are **built from the parts** —
   no w2p call, no hallucination possible. This is the "fix น้ำ once, then
   น้ำตา / ปากน้ำ / น้ำท่า inherit" idea: `น้ำตา = น้ำ + ตา -> น้ำ-ตา`.
4. **SCREENING** (`screen_override`) — see section 5.

```
1. Load the dict (poetry_overrides.py) + KNOWN_GOLD_FIXES; screen the dict
   itself and list any suspicious entries in the review file.
2. Build a Trie = default newmm dictionary + all covered words.
3. Tokenize every wak (newmm + Trie) and count unique tokens.
4. For every token NOT covered:
   a. try COMPOSITION from covered parts  -> COMPOSED bucket (safe)
   b. else w2p split, then PREFER-ORTHOGRAPHY (ssg when sound-equivalent)
5. Screen every candidate, then bucket.
```

### Buckets

| Bucket | Meaning | What you do |
|--------|---------|-------------|
| **AUTO** | `freq >= --min-freq` and passed screening | merge, **no review needed** |
| **FIXED** | flagged, but deterministically fixable (verified) | merge (fix already applied) |
| **COMPOSED** | built from covered parts (e.g. `น้ำตา` = `น้ำ` + `ตา`) | merge — safe by construction, no w2p involved |
| **REVIEW** | flagged, not safely fixable (incl. suspicious dict entries) | fix by ear, then edit the dict |
| **SKIP** | rare (`freq < --min-freq`) and clean | leave to w2p at runtime (intentional) |

### Why SKIP exists (the "don't override everything" answer)

Rare words that pass screening don't need a dict entry — w2p is right on them
and they appear once or twice, so the cost is negligible. Only *frequent*
words (speed) and *suspicious* words (correctness) get overridden.

### Coverage (current corpus, `--min-freq 3`, strict, dict already merged)

```
dict (poetry_overrides.py)     3,315 words  -> 97.5% of tokens covered
AUTO      2,532 words    6.7%   <- merge these
FIXED        20 words    0.0%   <- auto-corrected, merge
COMPOSED  3,433 words    4.3%   <- built from covered parts, merge
REVIEW      832 words    2.4%   <- fix by ear (787 new + 45 already in dict)
SKIP      1,764 words    0.6%   <- left to w2p
--------------------------------------------------------------
runtime dict-covered: ~97.5%   fall-through to w2p: ~2.5%
```

`--review-lenient` (bulk-accept mode) drops the new-word REVIEW further by
trusting w2p on leading-consonant (อักษรนำ) words where ssg under-splits —
see section 5 for the trade-off. Default is **strict** (safety first).

---

## 5. Screening methodology (the important part)

The screening delegates to the **improved `KhaveeVerifier`** (your updated
pythainlp) rather than hand-rolling Thai phonology:

- `kv.check_sara` / `kv.check_marttra` — vowel (incl. long/short) and
  final-consonant class, with proper handling of การันย์ (silent `์`), silent
  `ร`-clusters (`จักร`, `มิตร`, `สมุทร`), Pali masking vowels (`ชาติ`, `บัติ`,
  `เหตุ`), `รร`, ฤ/ฦ, and reduced vowels.
- `kv.is_sumpus(a, b)` — True if two syllables share vowel AND final,
  **with สระเกิน normalization** (`อัย → ไอ`, `อัม → อำ`), so `สัย`≡`ไส`,
  `น้ำ`≡`น้าม`-sound are compared by sound, not spelling.

### Per-syllable comparison (every position, not just the last)

The override's syllables are compared **position by position** against the
word's own `ssg` syllable split:

- counts match → `kv.is_sumpus(ssg_syl[i], override_syl[i])` for each `i`
- counts differ → flagged (syllable-count disagreement is itself suspect)

This is what catches `น้ำตา → น้าม-ตา` (a hallucination in the **first**
syllable), `ใหญ่โต → ผะ-หย่น` (both syllables wrong), etc.

Syllables whose ssg form contains การันย์ or is a 1-char fragment are skipped
(silent Pali letters / under-split fragments → the override is usually right).

### Deterministic checks (cheap, in addition to is_sumpus)

- **tone marks lost** — override has fewer `่ ้ ๊ ๋` than the source word.
- **tone mark CHANGED** — a position has a *different* tone mark than the
  source (`ผู้` ้ → `พู่` ่). This breaks เอก/โท checking downstream, so it is
  always flagged (and prevented up-front by prefer-orthography).
- **1-char syllable fragments** — `เฉย-เม-ย`, `ตร-อม-ตร-ม` (the split is
  wrong). 2+ char cluster syllables (`คร`, `ทร`, `บง`) are *not* flagged —
  they have implicit vowels and are legit (that was a false-positive flood in
  early versions); wrong 2+ char fragments are caught by the is_sumpus
  comparison instead.
- **over-spelled / redundant finals** — a syllable ending in `ำ`+consonant,
  `ไ/ใ`+`ย`, or `เ-า`+`ว` (e.g. `น้าม`).

### Syllable-count disagreements (both engines are unreliable)

Leading-consonant (อักษรนำ) words break both engines in opposite directions:

```
กลัว (TRUE 1 syllable)  -> w2p hallucinates กล-หวัว   [has bare fragment กล]
กวัด (TRUE 1 syllable)  -> w2p hallucinates กะ-วัด    [NO fragment — slips!]
ตลบ  (TRUE 2 syllables) -> ssg wrongly sees 1        [w2p's ตะ-หลบ is right]
อนุชา (TRUE 3)          -> ssg wrongly sees 2        [w2p's อะ-นุ-ชา is right]
```

`กวัด → กะ-วัด` is structurally identical to the correct `ตลบ → ตะ-หลบ`, so
**no automatic rule can separate them** — they genuinely need a human ear.

- **Strict (default):** ALL count disagreements → REVIEW (863). Safe — the
  ~3% real hallucinations (`กลัว`, `ขวัญ`, `กลบ`, `กวัด`...) are caught.
- **Lenient (`--review-lenient`):** keep only high-signal flags (bare
  fragments, tone changes, ssg>w2p). Drops REVIEW to ~292 by trusting w2p on
  the no-fragment cluster words — accepting that ~3% of those are real
  hallucinations. Only use if you accept a small miss rate.

### Safe auto-fix (`safe_fix`) — never a blanket replace

`safe_fix` only repairs the redundant-final pattern, **verified against the
word's own ssg syllable at the same position**:

```
น้ำ (ssg, ำ) + explicit ม → น้าม   → fix to น้ำ
ไส (ssg, ไ)  + ย         → ไสย    → fix to ไส
เรา (ssg, เ-า) + ว       → เราว   → fix to เรา
```

Subtlety handled: w2p spells the `ำ` sound as explicit `า+ม`, so we normalize
`ำ → าม` before comparing strings. Vowel-length changes (`ได้ → ด้าย`) are
**not** auto-fixed — they stay in REVIEW for your ears.

---

## 6. Workflow

```
edit poetry_overrides.py  →  run build_overrides.py  →  read poetry_overrides_generated_review.py  →  fix & re-edit
```

1. Run: `python build_overrides.py` (add `--min-freq N`,
   `--review-lenient`, `--no-compose`, `--out ...` as needed).
2. Open `poetry_overrides_generated_review.py` (the ONLY review file). It has
   two kinds of entries:
   - **new words** the pipeline thinks w2p hallucinated → fix by ear, then
     add to `poetry_overrides.py`;
   - **already in the dict** (marked in the header / `.screen.tsv`) → they
     stay in the dict, listed so you can see them. Fix them in
     `poetry_overrides.py` if you disagree.
3. Merge `poetry_overrides_generated.py` (AUTO+FIXED+COMPOSED) into
   `poetry_overrides.py` — or just leave it; since everything is already in
   the dict, this file only holds words the corpus has that the dict lacks.
4. Re-run the pipeline to confirm coverage climbed.

**No kernel involved:** `build_overrides.py` is a standalone script — it reads
all inputs fresh from disk. You never need to restart the notebook kernel to
regenerate; stale notebook state cannot affect it.

### Safety guarantees

- **The pipeline NEVER modifies `poetry_overrides.py`.** It only *reads* it
  (as the covered set) and *writes separate* `poetry_overrides_generated*.py`
  files. Your manual edits are preserved.
- **The dict is screened on every run.** Any suspicious entry already in
  `poetry_overrides.py` (tone changes, sound mismatches, bare fragments) is
  listed in the review file — so nothing hides in the dict.
- **KNOWN_GOLD_FIXES** in `build_overrides.py` stays as a safety net that
  wins over the dict for the specific words you already verified.
- Rebuilding after merging is idempotent: merged words are in the module, so
  they're excluded from generation (no duplicates, no removal).

---

## 7. Roadmap

- **Production module** (next step): extract `klon_syllables.py` /
  `klon_checker.py` from the notebook — a real, importable API:
  `extract_syllables(wak) -> [syllables]` and `check_klon(stanza) -> report`,
  built on `POETRY_OVERRIDES` + the improved `KhaveeVerifier`.
- **Scale to ~10× data**: re-run `build_overrides.py` on the larger corpus —
  it regenerates everything from scratch. Expect more unique words and a
  proportionally larger REVIEW list (rare words are where hallucinations hide).
- **Downstream consumers**: LLM training data generation, teacher validation
  of student Klon, RL environment (validator as reward signal).
