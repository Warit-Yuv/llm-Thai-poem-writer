# -*- coding: utf-8 -*-
"""Instrumented Klon-8 rhyme-detection checkers.

This package evaluates four Thai Klon-8 rhyme-detection systems under a single
instrumented interface so that every checked rhyme pair is recorded. The four
systems under evaluation are:

    A  Original PyThaiNLP   (pythainlp 5.0.1 ``KhaveeVerifier.check_klon``)
    B  Rule-based PyThaiNLP (pythainlp 5.3.5, incl. the improved KhaveeVerifier)
    C  Kongfha word_check   (KlonSuphap-LM, tltk-G2P based)
    D  Klonpad              (override-enhanced syllable extraction + Klon-8 rules)

Checkers A and B are faithful, instrumented reproductions of the respective
``check_klon`` implementations; the vendored source classes live in
``_orig_core.py`` (5.0.1) and ``_dev_core.py`` (5.3.5).
"""
from .original_khavee import OriginalKhaveeChecker
from .dev_khavee import RuleBasedKhaveeChecker
from .klonpad_checker import KlonpadChecker, KlonpadSsgChecker
from .kongfha_checker import KongfhaChecker

__all__ = [
    "OriginalKhaveeChecker",
    "RuleBasedKhaveeChecker",
    "KlonpadChecker",
    "KlonpadSsgChecker",
    "KongfhaChecker",
]
