# Thai Poetry Rhyme Verification Using a Hybrid Rule-Based Approach for Education and GenAI

**Warit Yuvaniyama, Athit Phinyachok, Gunn Sanguankittipun, Leo Colombo, and Prachya Boonkwan**
*School of Information, Computer and Communication Technology*
*Sirindhorn International Institute of Technology, Thammasat University*

---

## Abstract

In Thai Klon-Paed (กลอนแปด) poetry (the eight-syllable verse form), each four-line stanza must satisfy an interlocking rhyming pattern where the rhyming syllables must share both a vowel sound (s`ar`a สระ) and a final-consonant class (mˆa:ttra: มาตราตัวสะกด). Because Thai is written without word boundaries and its orthography conceals vowels and silenced letters, automatic rhyme verification is non-trivial: neither classical rule-based checkers nor G2P-romanization checkers handle the resulting edge cases reliably.

We present a hybrid rule-based verification approach. First, we improve the KhaveeVerifier algorithm — vowel analysis, final-consonant class analysis, the rhyme test, karun silencing, and true-final detection — and merge it into PyThaiNLP main (Model B). Second, we introduce Klon8Checker (Model D), which augments these rules with a gold-standard G2P override dictionary of over 4,000 entries and a fallback segmenter, recovering phonetic blind spots of the base oracle.

We evaluate five checker configurations on a gold corpus of 36,475 classical stanzas (145,709 rhyme checks) and on a targeted augmentation of 11,623 instances: 10,000 adversarial negatives, 1,200 tricky positives, and 423 oracle-blind rhymes. The best configuration (D_ssg) reaches 88.5% gold recall and 86.9% F1 on the augmentation, Model B attains 100% precision on curated negatives, and D_w2p recovers 95.7% of the oracle-blind rhymes. The verifier is released as an explainable educational tool and provides a deterministic reward signal for RL-based Klon-Paed generation.

---

**Keywords:** Thai NLP, Thai poetry, Klon-Paed, rhyme verification, rule-based systems, grapheme-to-phoneme, reinforcement learning, educational technology
