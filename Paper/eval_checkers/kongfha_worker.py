# -*- coding: utf-8 -*-
"""
Standalone worker for the Kongfha (KlonSuphap-LM) rhyme scorer.

This script must be executed under a Python interpreter that has ``tltk``
installed. In this project's setup the project venv runs Python 3.14, where the
``tltk`` dependency ``gensim`` has no prebuilt wheel, so the worker is launched
from the global Python 3.12 (see ``kongfha_checker.py``).

Protocol: one JSON object per line on stdin, one per line on stdout.

    in : {"id": <str>, "waks": [w1, ..., w8]}    # 8 waks = two 4-wak stanzas
    out: {"id": <str>, "fail": null|<fail> ,
          "score": [9 ints] | null, "repli": [9 ints] | null}

The scoring mirrors ``KlonSuphap-LM/sumpass_eval.py`` exactly. Possible
``fail`` values: "WakNumberFail", "WordFail", "LengthFail".
"""
import json
import os
import sys

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_THIRD = os.path.join(_ROOT, "third_party", "KlonSuphap-LM")
if _THIRD not in sys.path:
    sys.path.insert(0, _THIRD)

from utils import word_check  # noqa: E402  (after sys.path setup)
from utils.word_check import (  # noqa: E402
    replace_long_short,
    format_str_waks,
    format_waks_syl,
)

# --- tltk G2P cache ---------------------------------------------------------
# tltk's ``nlp.g2p`` is a slow, single-threaded pure-Python model, and it is the
# dominant cost of Checker C. Thai Klon poetry reuses waks heavily (same words,
# same half-line endings), so we cache the per-wak romanisation. The reference
# calls ``Get_Vow_and_Syl(wak)`` from ``format_waks_syl`` by module-global name,
# so re-pointing the module attribute transparently activates the cache. The
# worker stays alive across many units (see run_c_full.py), so the cache stays
# warm for its whole shard.
try:
    from functools import lru_cache
    word_check.Get_Vow_and_Syl = lru_cache(maxsize=200_000)(word_check.Get_Vow_and_Syl)
except Exception:
    pass  # cache is an optimisation only; never break the worker
# ---------------------------------------------------------------------------


def sumpass_score(bot_VowMat, bot_th):
    """Eval-version of the Kongfha per-bot rhyme scorer (from sumpass_eval.py)."""
    score = [0, 0, 0, 0]
    repli = [0, 0, 0, 0]

    s1 = replace_long_short(bot_VowMat[0][-1])
    s1_th = bot_th[0][-1]
    for i in [1, 2, 3, 4]:
        cur = replace_long_short(bot_VowMat[1][i])
        cur_th = bot_th[1][i]
        if s1 == cur:
            score[0] += 1
            if s1_th == cur_th:
                repli[0] += 1
            break

    s2 = replace_long_short(bot_VowMat[1][-1])
    s2_th = bot_th[1][-1]
    if s2 == replace_long_short(bot_VowMat[2][-1]):
        score[1] += 1
        if s2_th == bot_th[2][-1]:
            repli[1] += 1

    for i in [1, 2, 3, 4]:
        cur = replace_long_short(bot_VowMat[3][i])
        cur_th = bot_th[3][i]
        if s2 == cur:
            score[2] += 1
            if s2_th == cur_th:
                repli[2] += 1
            break

    s2_2 = replace_long_short(bot_VowMat[2][-1])
    s2_2_th = bot_th[2][-1]
    for i in [1, 2, 3, 4]:
        cur = replace_long_short(bot_VowMat[3][i])
        cur_th = bot_th[3][i]
        if s2_2 == cur:
            score[3] += 1
            if s2_2_th == cur_th:
                repli[3] += 1
            break

    return score, repli


def get_score(txt):
    """Reference ``get_score`` from sumpass_eval.py (8-wak unit)."""
    txt_waks = format_str_waks(txt)
    if len(txt_waks) < 8:
        return "WakNumberFail"
    klon_VowMat, klon_th, fail = format_waks_syl(txt_waks)
    if fail:
        return "WordFail"
    for wak in klon_th:
        if len(wak) < 5 or len(wak) > 10:
            return "LengthFail"
    bots_VowMat = [klon_VowMat[0:4], klon_VowMat[4:8]]
    bots_th = [klon_th[0:4], klon_th[4:8]]
    score = []
    repli = []
    for i in range(len(bots_VowMat)):
        cur_score, cur_repli = sumpass_score(bots_VowMat[i], bots_th[i])
        score += cur_score
        repli += cur_repli
    s3 = replace_long_short(bots_VowMat[0][3][-1])
    s3_th = bots_th[0][3][-1]
    es3 = replace_long_short(bots_VowMat[1][1][-1])
    es3_th = bots_th[1][1][-1]
    score.append(0)
    repli.append(0)
    if s3 == es3:
        score[8] += 1
        if s3_th == es3_th:
            repli[8] += 1
    return [score, repli]


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        unit_id = obj.get("id")
        waks = obj.get("waks", [])
        out = {"id": unit_id}
        # The reference splits waks on newline/tab, so join with "\n".
        try:
            res = get_score("\n".join(waks))
        except Exception as e:  # one bad unit must not kill the worker
            out["fail"] = "WorkerError:" + type(e).__name__ + ":" + str(e)
            out["score"] = None
            out["repli"] = None
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        if isinstance(res, str):
            out["fail"] = res
            out["score"] = None
            out["repli"] = None
        else:
            out["fail"] = None
            out["score"] = res[0]
            out["repli"] = res[1]
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
