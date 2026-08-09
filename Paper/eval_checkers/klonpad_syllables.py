# -*- coding: utf-8 -*-
"""
Klonpad syllable extraction (override dictionary + w2p fallback).

Faithful extraction of the syllable-segmentation routine from
``klonpad_validator.ipynb`` (``process_w2p`` and ``extract_poetic_syllables``)
promoted to a reusable module. Segmentation is resolved in priority order:

    1. a token (or a merged / stolen-character combination of tokens) that
       matches an entry in ``POETRY_OVERRIDES``;
    2. ssg sub-syllables of a token that contain an override entry;
    3. w2p (Word2Phrase) ``pronunciate`` output, ssg-split, as fallback.

``POETRY_OVERRIDES`` (``poetry_overrides.py``) is the gold-standard
``word -> [syllables]`` map; it is loaded once and used to build a combined
newmm trie (default dictionary + override keys).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pythainlp.tokenize import syllable_tokenize, word_tokenize, word_dict_trie
from pythainlp.transliterate import pronunciate

from poetry_overrides import POETRY_OVERRIDES

_trie = None


def _build_trie():
    """Combined newmm trie: default dictionary + all override keys."""
    global _trie
    if _trie is None:
        trie = word_dict_trie()  # default newmm dictionary
        for k in POETRY_OVERRIDES:
            if len(k) > 1 and k not in trie:
                trie.add(k)
        _trie = trie
    return _trie


@lru_cache(maxsize=200_000)
def process_w2p(word: str) -> tuple:
    """w2p ``pronunciate`` -> clean -> ssg split. LRU-cached (w2p is slow).

    ``maxsize`` is 200k to cover the full-corpus vocabulary: the evaluate set
    has ~145,900 waks / tens of thousands of distinct words, far more than a
    small cache would retain, which would thrash it and re-run the slow
    ``pronunciate`` model.
    """
    if len(word) <= 2:
        return tuple(syllable_tokenize(word, engine="ssg"))
    phonetic = pronunciate(word, engine="w2p")
    if not phonetic:
        return tuple(syllable_tokenize(word, engine="ssg"))
    clean = phonetic.replace("ฺ", "").replace("-", "")
    syls = syllable_tokenize(clean, engine="ssg")
    return tuple(s for s in syls if s != "ห" or word == "ห")


def _fallback_syllables(word: str, fallback: str = "w2p") -> tuple:
    """Syllabify a word not covered by an override.

    ``fallback="w2p"`` reproduces the original notebook behaviour (Word2Phrase
    ``pronunciate`` -> clean -> ssg split). ``fallback="ssg"`` uses plain ssg
    syllable tokenization directly on the Thai text with no romanisation step,
    so it cannot introduce w2p hallucinations (but also cannot benefit from
    w2p's pronunciation knowledge for rare/archaic words).
    """
    if fallback == "ssg":
        return tuple(syllable_tokenize(word, engine="ssg"))
    return process_w2p(word)


def extract_poetic_syllables(text: str, custom_trie=None,
                             fallback: str = "w2p",
                             stats: Optional[dict] = None) -> list:
    """Return the phonetic syllables of a wak using override-aware segmentation.

    ``fallback`` selects the segmenter used when no override matches
    (``"w2p"`` = original notebook behaviour, ``"ssg"`` = plain ssg).
    When ``stats`` is provided (a dict), it receives per-source syllable
    counts under the keys ``"override"``, ``"w2p"`` and ``"ssg"``.
    """
    words = word_tokenize(text, engine="newmm", custom_dict=custom_trie or _build_trie())
    final_syllables = []

    def _emit(syls, src):
        final_syllables.extend(syls)
        if stats is not None:
            stats[src] = stats.get(src, 0) + len(syls)

    i = 0
    while i < len(words):
        word = words[i]

        # --- MERGE CHECK: join consecutive tokens to match an override ---
        merged = False
        MAX_MERGE = 6
        end = min(i + MAX_MERGE, len(words))
        for j in range(end, i, -1):
            combined = "".join(words[i:j])
            if combined in POETRY_OVERRIDES:
                _emit(POETRY_OVERRIDES[combined], "override")
                i = j
                merged = True
                break
        if merged:
            continue

        # --- STOLEN-CHAR CHECK: recover a char newmm stole into the next token ---
        if i + 1 < len(words):
            next_word = words[i + 1]
            for k in range(1, min(4, len(next_word) + 1)):
                candidate = word + next_word[:k]
                if candidate in POETRY_OVERRIDES:
                    _emit(POETRY_OVERRIDES[candidate], "override")
                    remainder = next_word[k:]
                    if remainder:
                        words[i + 1] = remainder
                    else:
                        words.pop(i + 1)
                    i += 1
                    merged = True
                    break
            if merged:
                continue

        # --- Direct override ---
        if word in POETRY_OVERRIDES:
            _emit(POETRY_OVERRIDES[word], "override")
            i += 1
            continue

        # --- ssg sub-syllables containing an override ---
        sub_syllables = syllable_tokenize(word, engine="ssg")
        has_override = any(sub in POETRY_OVERRIDES for sub in sub_syllables)
        if len(sub_syllables) > 1 and has_override:
            for sub in sub_syllables:
                if sub in POETRY_OVERRIDES:
                    _emit(POETRY_OVERRIDES[sub], "override")
                else:
                    _emit(_fallback_syllables(sub, fallback),
                          "ssg" if fallback == "ssg" else "w2p")
            i += 1
            continue

        # --- Fallback ---
        _emit(_fallback_syllables(word, fallback),
              "ssg" if fallback == "ssg" else "w2p")
        i += 1

    return final_syllables
