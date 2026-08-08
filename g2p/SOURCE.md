# g2p/ — pronunciation lookup source

`wiktionary-23-7-2022-clean.tsv` — 16,027 lines, 14,839 unique Thai words with
IPA transcriptions, syllables separated by `" . "`.

- **Source:** https://github.com/PyThaiNLP/thai-g2p-wiktionary-corpus
- **Upstream origin:** Thai Wiktionary, scraped with
  [WikiPron](https://pypi.org/project/wikipron/)
- **License:** CC-BY-SA 3.0 — https://creativecommons.org/licenses/by-sa/3.0/

## Attribution / share-alike

CC-BY-SA 3.0 requires attribution and applies share-alike to derivative works.
Any dictionary generated from this file (`g2p_dictionary.py`, or a merged
override dict) is a derivative and inherits that obligation. Decide the repo's
LICENSE before publishing, and cite this corpus in the paper.

## Why the TSV is loaded directly, not respelled first

Syllable **counts** come from the IPA separators — `len(ipa.split(" . "))` —
which is exact and needs no phonetic conversion. Respelling IPA back into Thai
(`build_g2p_dict.py`) is only required for the rhyme work, where the actual
spelling matters, and it currently fails on 3.9% of entries (the `ɤ` / เออ
vowel family is missing from its table). Keeping counting on the raw IPA means
that gap never blocks the syllable pipeline.

## Multiple readings are kept, not collapsed

384 words (2.6%) carry more than one syllable count — the Sanskrit/Pali linking
class, where `ราช` is ราด (1) alone but ราด-ชะ (2) inside a compound, and
likewise `พล`, `จิต`, `สมุทร`. Collapsing these to one reading would silently
fix 23,474 corpus tokens to a guess. They are loaded as candidate sets so the
meter can choose — see `_meter_resolve` in `CleanData.py`.
