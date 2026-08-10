# Candidate-pool adjudication — contested junk (Agent 4, 2026-08-10)

Context: the recheck agents audited the candidate pool (`Paper/augment/output/candidates_review.tsv`). The 45 orthographically-certain *misassignments* (multi-syllable finals, การันต์/glide, short-โอะ rule, เออ-vs-เอ) were already excluded in v5.6 via `ORACLE_MISREAD_EXCLUDE`. What remains is this **49-word junk list** plus ~15 borderline root fragments that the reviewers disagreed on — several are valid syllables of compounds (e.g. นวณ from คำนวณ, ฌงค์, รวจ from ตรวจ). The author decides DROP or KEEP per word. DROP = add to `ORACLE_MISREAD_EXCLUDE` (or a dedicated pool-exclude) and regenerate; KEEP = leave in the pool.

Columns: **cand** = times used as a *candidate* in the 11,623 instances; **src** = times it was the *source* syllable (original corpus text — not controllable, listed for info); **pool** = still in `candidates_review.tsv`.

## Author decisions (2026-08-10) — applied as v5.7

**DROP (11)** — added to `ORACLE_MISREAD_EXCLUDE` in `Paper/augment/tricky_words.py`:
`ควณ`, `หภัก`, `เสน่`, `งค`, `ษส`, `ชส`, `บส`, `ตศต`, `พเจ้า`, `ทบุ`, `สเป`
(no meaning, or broken syllable fragments; พเจ้า/ทบุ/สเป split the syllable).

**KEEP (all the rest)** — compound syllables (รวจ/นวณ/ชวร/กตัญ from สำรวจ/คำนวณ/ประชวร/กตัญญู),
`ปณต` (a name), and all borderline Pali roots. Rationale: the augmentation needs a valid
**rhyme unit**, not a standalone word — no-meaning syllables that don't break anything are fine.

## 49 contested junk — DECIDE DROP / KEEP

| word | cand | src | pool | Agent-4 reason | decision |
|---|---|---|---|---|---|
| `รวจ` | 1 | 0 | Y | fragment of ตรวจ | |
| `ควณ` | 2 | 0 | Y | not a word (ควน is; ควณ isn't) | |
| `นวณ` | 1 | 0 | Y | not a word (syllable of คำนวณ) | |
| `ชวร` | 1 | 0 | Y | not a word | |
| `หภัก` | 2 | 0 | Y | not a word | |
| `เสน่` | 1 | 0 | — | ssg split of เสน่ห์ | |
| `กตัญ` | 1 | 0 | Y | fragment of กตัญญู | |
| `งค` | 0 | 0 | Y | fragment (อังค) | |
| `ษส` | 1 | 0 | Y | not a word | |
| `ชส` | 2 | 0 | Y | not a word | |
| `บส` | 1 | 2 | Y | not a word | |
| `ตศต` | 0 | 0 | Y | not a word | |
| `ปณต` | 4 | 0 | Y | not a word | |
| `ขยด` | 1 | 0 | — | not a word | |
| `ชมด` | 3 | 0 | Y | not a word | |
| `ฉบบ` | 1 | 0 | Y | fragment (ฉบับ) | |
| `ฉมบ` | 2 | 0 | Y | not a word | |
| `บบ` | 1 | 0 | Y | not a word | |
| `ปบ` | 0 | 0 | Y | not a word | |
| `ยป` | 0 | 0 | Y | not a word | |
| `อพ` | 1 | 0 | Y | not a word | |
| `ชมน์` | 1 | 0 | Y | not a word | |
| `บล` | 0 | 4 | — | not a word (bull?) | |
| `ภน` | 0 | 0 | — | fragment (ภณ is the word) | |
| `รนต์` | 1 | 0 | Y | not a word | |
| `คณห์` | 6 | 0 | Y | not a word | |
| `ดงค์` | 2 | 0 | — | not a word | |
| `ฌงค์` | 1 | 0 | Y | not a word (syllable of ฌาน/สังฆ์?) | |
| `ชงค์` | 3 | 0 | Y | not a word | |
| `มงค์` | 13 | 0 | Y | not a word | |
| `ยงค์` | 2 | 5 | Y | not a word | |
| `สงค์` | 4 | 31 | Y | not a word | |
| `สงส์` | 6 | 0 | Y | not a word | |
| `ซุค` | 0 | 0 | Y | transliteration fragment | |
| `นุข` | 0 | 0 | Y | not a word | |
| `บุค` | 0 | 0 | Y | not a word | |
| `ยุก` | 0 | 0 | Y | not a word | |
| `กุซ` | 0 | 0 | — | not a word | |
| `คุช` | 0 | 0 | — | not a word | |
| `จุท` | 0 | 0 | Y | not a word | |
| `มุธ` | 0 | 0 | Y | not a word | |
| `อุซ` | 0 | 0 | — | not a word | |
| `อล่อง` | 0 | 0 | — | not a word | |
| `อลึ่ง` | 0 | 0 | Y | not a word | |
| `อล่วย` | 5 | 0 | Y | not a word (true_final tag on a non-word) | |
| `ชอ่ำ` | 1 | 0 | Y | not a word | |
| `กุตร` | 0 | 0 | — | not a word | |
| `ทบุ` | 1 | 0 | Y | not a word | |
| `พเจ้า` | 1 | 0 | Y | typo/fragment (พระเจ้า) | |

## Borderline root fragments — DECIDE DROP / KEEP

| word | cand | src | pool | note | decision |
|---|---|---|---|---|---|
| `กัจ` | 0 | 0 | — | Pali root kacca family, not standalone | |
| `กัซ` | 0 | 0 | — | Pali root kacca family, not standalone | |
| `กัธ` | 1 | 0 | Y | Pali root kacca family, not standalone | |
| `กัศ` | 0 | 0 | — | Pali root kacca family, not standalone | |
| `กศ` | 1 | 0 | Y | root fragment | |
| `วจ` | 0 | 0 | Y | Pali 'speech', real but root-like | |
| `ทร` | 11 | 17 | — | Pali root/prefix | |
| `ปร` | 0 | 0 | Y | Pali root/prefix | |
| `มร` | 0 | 0 | — | truly มะ-ระ | |
| `หร` | 0 | 0 | — | Pali root/prefix | |
| `กวอน` | 1 | 0 | — | transliteration | |
| `เพช` | 0 | 0 | Y | fragment of เพชร; vowel short เอะ not เอ | |
| `สรรช` | 0 | 0 | — | root fragment | |
| `สเป` | 0 | 0 | Y | transliteration fragment | |
| `ฉัคร` | 28 | 0 | Y | root fragment | |
| `คพ` | 0 | 0 | Y | valid Pali monosyllable -- KEEP | |
| `สพ` | 0 | 0 | Y | valid Pali monosyllable -- KEEP | |
| `รภ` | 1 | 0 | Y | valid Pali monosyllable -- KEEP | |
| `ลภ` | 0 | 0 | Y | valid Pali monosyllable -- KEEP | |
| `ยพ` | 0 | 0 | Y | valid Pali monosyllable -- KEEP | |

## How to apply

Tell the assistant which words to DROP; they will be added to `ORACLE_MISREAD_EXCLUDE` in `Paper/augment/tricky_words.py` and the augmentation regenerated (instances that used them get replaced). KEEP words stay untouched.
