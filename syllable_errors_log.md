# Syllable Pronunciation Error Log (Re-checked after re-run)

## ✅ Confirmed Fixed (Stanzas 31–57)

After re-running the notebook with updated overrides, all 8 errors below are now fixed:

| # | Stanza | Wak | Word | Was | Now (Fixed) |
|---|--------|-----|------|-----|-------------|
| 1 | 35 | 8 | `ด้นดั้น` | ด้น-**ด้าน** | ด้น-**ดั้น** ✅ |
| 2 | 37 | 5 | `เสนา` | เสนา (1 unit) | **เส-นา** (2) ✅ |
| 3 | 38 | 3 | `กระนั้น` | **กอ-ระ**-นั้น | **กระ**-นั้น ✅ |
| 4 | 39 | 5 | `กระหวัด` | กระ-**หะ-วัด** | กระ-**หวัด** ✅ |
| 5 | 45 | 7 | `เภตรา` | เพตรา (1 unit) | **เพ-ตรา** (2) ✅ |
| 6 | 55 | 5 | `เทวราช` | เท-วะ-**ดา** | เท-วะ-**ราด** ✅ |
| 7 | 55 | 8 | `โทโส` | โท-**โท** | โท-**โส** ✅ |
| 8 | 57 | 2 | `การเวก` | กาน-**เกด** | **กา-ระ-เวก** ✅ |

---

## ⚠️ Known Issue: Tokenization-dependent overrides not triggering

Some overrides only work when `newmm` tokenizer produces the word as a single token.
When the tokenizer splits the word into smaller pieces, the override is never checked.

### Issue A — `วิญญาณ์` (Stanza 11 Wak 7, Stanza 56 Wak 7)

- **Original S11W7**: `ผู้ใดฟังวังเวงในวิญญาณ์`
- **Original S56W7**: `ซึ่งสงสัยไม่สิ้นในวิญญาณ์`
- **Current output**: `['วิ', 'ยา']`
- **Expected**: `['วิน', 'ยา']`
- **Root cause**: `newmm` splits `วิญญาณ์` as `วิ` + `ญญาณ์`. The override `"วิญญาณ์": ["วิน", "ยา"]` never triggers because `วิญญาณ์` is never seen as a single token.
- **Partial fix applied**: `"ญญาณ์": ["ยา"]` — handles the second part (ญญาณ์ → ยา instead of ยะ-ยา), but `วิ` stays as `['วิ']` instead of `['วิน']`.
- **Why wrong**: `วิ` without the ญ final is a different word (prefix). In `วิญญาณ์`, the ญ is the final consonant of the first syllable making it `วิน`.

### Issue B — `ศอก` (Stanza 15 Wak 8, Stanza 16 Wak 4)

- **Original wak**: `กระบองสี่ศอกวางไว้ข้างกาย`
- **Current output**: `['สี่', 'ศอ', 'กวาง']`
- **Expected**: `['สี่', 'สอก', 'วาง']`
- **Root cause**: `newmm` splits `ศอกวาง` as `ศอ` + `กวาง` (merging the ก from ศอก into กวาง). The override `"ศอก": ["สอก"]` never triggers.
- **Note**: User already identified this — same class of issue.

### Suggested fix

Modify `extract_poetic_syllables()` to check if consecutive tokens combine to match a known override before processing them individually. E.g. if `words[i] + words[i+1]` is in `POETRY_OVERRIDES`, use it.

---

## All overrides added (final)

```python
# === Stanza 31-57 corrections (all confirmed working except Issue A/B) ===
"ด้นดั้น": ["ด้น", "ดั้น"],           # S35W8: wrong vowel length
"เสนา": ["เส", "นา"],                # S37W5: missing syllable split
"กระนั้น": ["กระ", "นั้น"],           # S38W3: wrong cluster split (treated กร as Pali)
"กระหวัด": ["กระ", "หวัด"],           # S39W5: extra implicit vowel
"เภตรา": ["เพ", "ตรา"],              # S45W7: missing syllable split
"เทวราช": ["เท", "วะ", "ราด"],       # S55W5: misread ราช as ดา
"โทโส": ["โท", "โส"],               # S55W8: misread โส as โท
"ญญาณ์": ["ยา"],                     # S56W7: partial fix for วิญญาณ์ split
"การเวก": ["กา", "ระ", "เวก"],       # S57W2: was กาน-เกด, correct is กา-ระ-เวก
```
