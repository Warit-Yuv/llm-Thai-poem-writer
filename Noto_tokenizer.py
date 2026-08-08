from pythainlp.tokenize import word_tokenize, syllable_tokenize
from pythainlp.transliterate import pronunciate

# 1. THE GOLD STANDARD DICTIONARY
POETRY_OVERRIDES = {
    "ก็": ["ก็"],
    "บ่": ["บ่"],
    "ได้": ["ได้"],
    "ธ": ["ทะ"],
    "ณ": ["นะ"],
    "ฤ": ["รึ"],
    "ฤๅ": ["รือ"],
    "ฤๅษี": ["รือ", "สี"],
    "มนุษย์": ["มะ", "นุด"],
    "พฤติกรรม": ["พฺรึด", "ติ", "กำ"],
    "สระ": ["สะ", "หระ"],
    "ความรู้สึก": ["ความ", "รู้", "สึก"],
    "เข้าใจ": ["เข้า", "ใจ"],
    "อยู่": ["อยู่"], # Fixes the "รู้อยู่" -> 'หยู่' hallucination
    "ผู้": ["ผู้"],   # Fixes the "ผู้ใด" -> 'พู่' hallucination
    "ใหม่": ["ใหม่"],
    "อย่า": ["อย่า"],
    "อย่าง": ["อย่าง"],
    "อยาก": ["อยาก"],
    # w2p swallows linking syllables in Sanskrit compounds — found via --wak probes
    "กิตติมศักดิ์": ["กิด", "ติ", "มะ", "สัก"],
    "ไสยศาสตร์": ["ไส", "ยะ", "สาด"],
    "อัปยศอดสู": ["อับ", "ปะ", "ยด", "อด", "สู"],
}

def process_w2p(word: str) -> list:
    """Helper function to cleanly process a string through the w2p model."""
    # pronunciate hallucination on very short words. Use syllable_tokenize instead.
    if len(word) <= 2:
        return syllable_tokenize(word, engine="ssg")
        
    phonetic_word = pronunciate(word, engine="w2p")
    
    if not phonetic_word:
        return syllable_tokenize(word, engine="ssg")
    
    # Clean up unwanted characters like Phinthu (-ฺ) and hyphens (-)
    clean_phonetic = phonetic_word.replace("ฺ", "").replace("-", "")
    
    # Using ssg (CRF segmenter) as it handles phonetic text better than dict
    phonetic_syllables = syllable_tokenize(clean_phonetic, engine="ssg")
    
    # Clean up stray 'ห' artifacts
    return [s for s in phonetic_syllables if s != "ห" or word == "ห"]

def extract_poetic_syllables(text: str) -> list:
    """Extracts phonetic syllables for Klon 8 verification."""
    # Tokenize text into words using the newmm (greedy) engine, allowing w2p to handle compound words
    words = word_tokenize(text, engine="newmm")
    final_syllables = []
    
    for word in words:
        # Direct Override if the tokenized word is in the POETRY_OVERRIDES list (O(1) Fast Lookup)
        if word in POETRY_OVERRIDES:
            final_syllables.extend(POETRY_OVERRIDES[word])
            continue

        # Use 'ssg' to check if newmm greedy engine merged words like "ได้ใจ" or "รู้อยู่"
        sub_syllables = syllable_tokenize(word, engine="ssg")

        # SINGLE-LETTER OVERRIDES ARE STANDALONE-ONLY.
        # A 1-char key ("จ" -> "จะ") must fire ONLY when the whole token IS that
        # letter (handled above). It must NEVER fire as a sub-syllable inside a
        # longer word: ssg sometimes splits a syllable into (single consonant +
        # rest), e.g. จวน -> ['จ','วน'], so applying "จ" here would turn the
        # 1-syllable word จวน into a wrong 2-syllable "จะ-วน".
        # Check if ANY of the segmented syllables are in the POETRY_OVERRIDES list
        has_override = any(
            len(sub) > 1 and sub in POETRY_OVERRIDES for sub in sub_syllables
        )

        if len(sub_syllables) > 1 and has_override:
            # Found a hidden override word in the segmented syllables. Process each sub-syllable independently.
            for sub in sub_syllables:
                if len(sub) > 1 and sub in POETRY_OVERRIDES:
                    final_syllables.extend(POETRY_OVERRIDES[sub])
                else:
                    final_syllables.extend(process_w2p(sub))
            continue
        
        # If no overrides were found inside, treat it as a true compound word (e.g. พัฒนาการ)
        # Proceed to parse the word into w2p pronunciate engine.
        final_syllables.extend(process_w2p(word))
        
    return final_syllables

# Test sentences (run `python Noto_tokenizer.py`; guarded so importing is silent)
if __name__ == "__main__":
    sentence = [
        "แม่รักลูกลูกก็รู้อยู่ว่ารัก",
        "สรรเพชญโพธิญาณประมาณหมาย",
        "บ่มีผู้ใดจะเข้าใจความรู้สึกของข้าได้",
        "ไหนใครใคร่ใช้ได้ใจชัยไทย",
        "โอ้มนุษย์ผู้มีจิตใจและมีความสามารถในการสร้างสรรค์สิ่งใหม่",
        "ความแปลกแยกและพัฒนาการ",
        "อย่าอยู่อย่างอยากหมากหมิ่นหมายหมอง",
        "อันประกอบด้วยสระและพยัญชนะหลายตัว",
    ]

    for sent in sentence:
        syllables = extract_poetic_syllables(sent)
        print(f"Sentence: {sent}")
        print(f"Final Syllable: {syllables}\n")