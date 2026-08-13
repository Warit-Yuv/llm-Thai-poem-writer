"""Production-facing Klon-4/Klon-8 analysis service used by the demo UI.

The module deliberately returns plain dictionaries so the same backend can be
used by Streamlit, tests, notebooks, or a future API without coupling the
prosody logic to a particular interface.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import KhaveeVerifier  # noqa: E402
from pythainlp.tokenize import subword_tokenize, syllable_tokenize  # noqa: E402


THAI_RE = re.compile(r"[ก-ฮฤฦ]")
# วรรค separators accepted on input. Hyphens are deliberately absent: they carry
# meaning inside a word, so splitting on them would tear real วรรค apart.
# A space is weaker than the rest — it also occurs *inside* a วรรค — so it only
# joins the set when the strong separators alone fail to produce whole บท.
STRONG_SEPARATORS = re.compile(r"[,\r\n;:|/\\•]+")
ANY_SEPARATOR = re.compile(r"[\s,;:|/\\•]+")
TONE_MARKS = "่้๊๋"
WAK_NAMES = ("วรรคสดับ", "วรรครับ", "วรรครอง", "วรรคส่ง")
SUPPORTED_KLON_TYPES = {4, 8}
KLON_NAMES = {4: "กลอนสี่", 8: "กลอนแปด"}
REPORT_SCHEMA_VERSION = "1.2"


@lru_cache(maxsize=1)
def verifier() -> KhaveeVerifier:
    """Use the improved verifier that is versioned with this project."""
    return KhaveeVerifier()


def _clean_token(token: str) -> str:
    return "".join(ch for ch in token.strip() if THAI_RE.search(ch) or ch in TONE_MARKS or ch in "ะาิีึืุูเแโใไัำ็์ฺๅๆ")


def tokenize_written_words(text: str) -> list[str]:
    """Return SSG units while discarding spaces and punctuation."""
    cleaned = _clean_token(text)
    if not cleaned:
        return []
    return [unit.strip() for unit in syllable_tokenize(cleaned, engine="ssg") if unit.strip()]


def tokenize_editor_units(text: str) -> list[str]:
    """Return the exact units produced by PyThaiNLP SSG."""
    return tokenize_written_words(text)


def tokenize_editor_syllable_units(text: str) -> list[str]:
    """Return one visible unit per SSG result; no w2p or overrides are used."""
    return tokenize_written_words(text)


@lru_cache(maxsize=20_000)
def pronounce_word(word: str) -> tuple[tuple[str, ...], str]:
    """Return syllables from PyThaiNLP SSG without generative pronunciation."""
    result = tuple(
        syllable.replace("ฺ", "").strip()
        for syllable in syllable_tokenize(word, engine="ssg")
        if syllable.strip()
    )
    return result or (word,), "ssg"


def _validate_klon_type(k_type: int) -> None:
    if k_type not in SUPPORTED_KLON_TYPES:
        raise ValueError("k_type must be 4 or 8")


@lru_cache(maxsize=20_000)
def analyze_sound(syllable: str) -> dict[str, Any]:
    """Expose stable Khavee sound features for explainable UI details."""
    try:
        sara = verifier().check_sara(syllable)
    except Exception:
        sara = "ไม่ทราบ"
    try:
        marttra = verifier().check_marttra(syllable)
    except Exception:
        marttra = "ไม่ทราบ"
    try:
        weight_raw = verifier().check_karu_lahu(syllable)
        weight = {"karu": "ครุ", "lahu": "ลหุ"}.get(str(weight_raw), "ไม่ทราบ")
    except Exception:
        weight = "ไม่ทราบ"
    try:
        tone_raw = verifier().check_aek_too(syllable)
        tone = {"aek": "เอก", "too": "โท"}.get(str(tone_raw), "—")
    except Exception:
        tone = "ไม่ทราบ"
    return {
        "syllable": syllable,
        "vowel": sara,
        "final_class": marttra,
        "weight": weight,
        "tone_role": tone,
    }


def _rhythm_for(total: int, k_type: int = 8) -> tuple[list[int] | None, str]:
    _validate_klon_type(k_type)
    if k_type == 4:
        if total == 4:
            return [2, 2], "ผ่าน"
        if total == 5:
            return [2, 3], "ผ่าน"
        return None, "ไม่ผ่าน"
    if total == 8:
        return [3, 2, 3], "ผ่าน"
    if total == 9:
        return [3, 3, 3], "ผ่าน"
    if total == 7:
        return [3, 2, 2], "ผ่าน"
    return None, "ไม่ผ่าน"


def _group_syllables(syllables: list[str], rhythm: list[int] | None) -> list[str]:
    if not rhythm:
        return ["-".join(syllables)] if syllables else []
    groups: list[str] = []
    position = 0
    for length in rhythm:
        groups.append("-".join(syllables[position : position + length]))
        position += length
    if position < len(syllables):
        groups.append("-".join(syllables[position:]))
    return groups


def analyze_wak(text: str, index: int = 0, k_type: int = 8) -> dict[str, Any]:
    """Analyze one written wak using deterministic SSG syllabification."""
    _validate_klon_type(k_type)
    words: list[dict[str, Any]] = []
    spoken_syllables: list[str] = []

    for syllable in tokenize_written_words(text):
        syllables = (syllable,)
        source = "ssg"
        spoken_syllables.append(syllable)
        words.append(
            {
                "word": syllable,
                "pronunciation": syllable,
                "syllables": 1,
                "source": source,
                "sound_details": [analyze_sound(syllable) for syllable in syllables],
            }
        )

    max_words = 5 if k_type == 4 else 10
    try:
        core_tokens = [token for token in subword_tokenize(text, engine="ssg") if token.strip()]
        word_count_source = "ssg subword_tokenize (same rule as core.check_klon)"
    except Exception:
        core_tokens = [word["word"] for word in words]
        word_count_source = "newmm fallback"
    word_count = len(core_tokens)
    word_count_passed = 0 < word_count <= max_words

    rhythm, status = _rhythm_for(len(spoken_syllables), k_type)
    notes: list[str] = []
    if status == "ไม่ผ่าน":
        expected = "4–5" if k_type == 4 else "7–9"
        notes.append(
            f"พบ {len(spoken_syllables)} พยางค์ ซึ่งอยู่นอกช่วง {expected} พยางค์ที่ระบบรองรับสำหรับ{KLON_NAMES[k_type]}"
        )
    if word_count > max_words:
        notes.append(f"พบ {word_count} หน่วยคำ เกินขีดจำกัด {max_words} หน่วยคำของ{KLON_NAMES[k_type]}")
    elif word_count == 0:
        notes.append("ไม่พบหน่วยคำที่ระบบสามารถวิเคราะห์ได้")
    line_status = "ไม่ผ่าน" if status == "ไม่ผ่าน" or not word_count_passed else status

    return {
        "index": index,
        "klon_type": k_type,
        "wak_name": WAK_NAMES[index % 4],
        "text": text.strip(),
        "words": words,
        "core_tokens": core_tokens,
        "word_count": word_count,
        "max_words": max_words,
        "word_count_source": word_count_source,
        "word_count_passed": word_count_passed,
        "spoken_syllables": spoken_syllables,
        "syllable_count": len(spoken_syllables),
        "rhythm": rhythm,
        "rhythm_text": "–".join(map(str, rhythm)) if rhythm else "—",
        "beat_groups": _group_syllables(spoken_syllables, rhythm),
        "status": line_status,
        "meter_status": status,
        "meter_passed": status == "ผ่าน",
        "notes": notes,
    }


def _safe_rhyme(first: str, second: str) -> bool:
    if not first or not second:
        return False
    try:
        return bool(verifier().is_sumpus(first, second))
    except Exception:
        return False


def _sound_signature(syllable: str) -> dict[str, str]:
    try:
        return {
            "vowel": verifier().check_sara(syllable),
            "final_class": verifier().check_marttra(syllable),
        }
    except Exception:
        return {"vowel": "ไม่ทราบ", "final_class": "ไม่ทราบ"}


def compare_rhyme(first: str, second: str) -> dict[str, Any]:
    """Explain one Khavee rhyme decision together with teachable sound data."""
    first = _clean_token(first)
    second = _clean_token(second)
    first_syllables, first_source = pronounce_word(first) if first else ((), "—")
    second_syllables, second_source = pronounce_word(second) if second else ((), "—")
    first_rhyme = first_syllables[-1] if first_syllables else first
    second_rhyme = second_syllables[-1] if second_syllables else second
    first_details = [analyze_sound(syllable) for syllable in first_syllables]
    second_details = [analyze_sound(syllable) for syllable in second_syllables]
    return {
        "first": first,
        "second": second,
        "passed": _safe_rhyme(first_rhyme, second_rhyme),
        "first_sound": _sound_signature(first_rhyme),
        "second_sound": _sound_signature(second_rhyme),
        "first_analysis": {
            "pronunciation": "-".join(first_syllables) if first_syllables else "—",
            "syllables": list(first_syllables),
            "rhyme_syllable": first_rhyme or "—",
            "sound_details": first_details,
            "source": first_source,
        },
        "second_analysis": {
            "pronunciation": "-".join(second_syllables) if second_syllables else "—",
            "syllables": list(second_syllables),
            "rhyme_syllable": second_rhyme or "—",
            "sound_details": second_details,
            "source": second_source,
        },
        "engine": "project core.KhaveeVerifier",
    }


def _candidate_check(
    rule: str,
    source_line: int,
    target_line: int,
    source: str,
    candidates: list[tuple[int, str]],
    preferred_positions: set[int],
) -> dict[str, Any]:
    matches = [position for position, syllable in candidates if _safe_rhyme(source, syllable)]
    return {
        "rule": rule,
        "source_line": source_line + 1,
        "target_line": target_line + 1,
        "source": source,
        "candidates": [{"position": pos, "syllable": syl} for pos, syl in candidates],
        "matched_positions": matches,
        "passed": bool(matches),
        "preferred_position": any(position in preferred_positions for position in matches),
    }


def _direct_check(
    rule: str,
    source_line: int,
    target_line: int,
    source: str,
    target: str,
) -> dict[str, Any]:
    return {
        "rule": rule,
        "source_line": source_line + 1,
        "target_line": target_line + 1,
        "source": source,
        "target": target,
        "passed": _safe_rhyme(source, target),
        "preferred_position": True,
    }


def _rhyme_checks(lines: list[dict[str, Any]], k_type: int = 8) -> list[dict[str, Any]]:
    _validate_klon_type(k_type)
    checks: list[dict[str, Any]] = []
    complete_line_count = len(lines) - (len(lines) % 4)

    for start in range(0, complete_line_count, 4):
        stanza = lines[start : start + 4]
        if not all(line["spoken_syllables"] for line in stanza):
            continue

        w1, w2, w3, w4 = stanza
        if k_type == 4:
            w2_limit = 3 if len(w2["spoken_syllables"]) == 5 else 2
            w4_limit = 3 if len(w4["spoken_syllables"]) == 5 else 2
            preferred_w2 = set(range(1, w2_limit + 1))
            preferred_w4 = set(range(1, w4_limit + 1))
        else:
            w2_limit = w4_limit = 5
            preferred_w2 = preferred_w4 = {3, 5}

        w2_candidates = list(enumerate(w2["spoken_syllables"][:w2_limit], start=1))
        w4_candidates = list(enumerate(w4["spoken_syllables"][:w4_limit], start=1))
        checks.append(
            _candidate_check(
                "ท้ายวรรคสดับ → พยางค์ต้นของวรรครับ",
                start,
                start + 1,
                w1["spoken_syllables"][-1],
                w2_candidates,
                preferred_w2,
            )
        )
        checks.append(
            _direct_check(
                "ท้ายวรรครับ → ท้ายวรรครอง",
                start + 1,
                start + 2,
                w2["spoken_syllables"][-1],
                w3["spoken_syllables"][-1],
            )
        )
        checks.append(
            _candidate_check(
                "ท้ายวรรครอง → พยางค์ต้นของวรรคส่ง",
                start + 2,
                start + 3,
                w3["spoken_syllables"][-1],
                w4_candidates,
                preferred_w4,
            )
        )

        if start >= 4:
            previous_w4 = lines[start - 1]["spoken_syllables"]
            if previous_w4:
                checks.append(
                    _direct_check(
                        "ท้ายวรรคส่งบทก่อน → ท้ายวรรครับบทถัดไป",
                        start - 1,
                        start + 1,
                        previous_w4[-1],
                        w2["spoken_syllables"][-1],
                    )
                )
    return checks


def parse_waks(poem_text: str) -> list[str]:
    """Split a poem into วรรค on any separator: newline, space, comma, slash…

    Newline and comma carry equal weight, so four lines of four comma-separated
    วรรค parse as 16, not 4. A space only counts as a separator when the strong
    ones alone do not yield whole บท — otherwise a วรรค written with an internal
    space would be torn in two.

    app.py shares this function rather than splitting again, so the วรรค count
    shown to the user is always the one that gets analyzed.
    """
    waks = [wak.strip() for wak in STRONG_SEPARATORS.split(poem_text) if wak.strip()]
    if len(waks) >= 4 and len(waks) % 4 == 0:
        return waks
    spaced = [wak.strip() for wak in ANY_SEPARATOR.split(poem_text) if wak.strip()]
    return spaced or waks


def _humanize_core_message(message: str) -> str:
    if "Word count exceeds" in message:
        return "KhaveeVerifier พบวรรคที่มีจำนวนหน่วยคำเกินขีดจำกัด"
    if "Inter-stanza rhyme error" in message:
        return "KhaveeVerifier พบสัมผัสระหว่างบทที่ไม่ตรงตามกฎ"
    if "Rhyme error" in message:
        return "KhaveeVerifier พบตำแหน่งสัมผัสที่ไม่ตรงตามกฎ"
    if "complete stanzas" in message:
        return "KhaveeVerifier พบว่าจำนวนวรรคไม่ครบบท"
    return "KhaveeVerifier พบข้อสังเกตที่ควรตรวจสอบ"


def _run_core_validation(raw_waks: list[str], k_type: int) -> dict[str, Any]:
    """Run the repository's native check_klon as an auditable second opinion."""
    if not raw_waks:
        return {"status": "ตรวจไม่ได้", "passed": None, "messages": [], "raw_messages": []}
    try:
        result = verifier().check_klon(" ".join(raw_waks), k_type=k_type)
    except Exception as exc:
        return {
            "status": "ตรวจไม่ได้",
            "passed": None,
            "messages": ["ไม่สามารถเรียกใช้ core.check_klon ได้"],
            "raw_messages": [f"{type(exc).__name__}: {exc}"],
        }

    if result == "The poem is correct according to the principle.":
        return {"status": "ผ่าน", "passed": True, "messages": [], "raw_messages": []}

    raw_messages = result if isinstance(result, list) else [str(result)]
    return {
        "status": "พบข้อสังเกต",
        "passed": False,
        "messages": list(dict.fromkeys(_humanize_core_message(message) for message in raw_messages)),
        "raw_messages": raw_messages,
    }


def check_klon(poem_text: str, k_type: int = 8) -> dict[str, Any]:
    """Return an explainable structural report for Klon-4 or Klon-8 stanzas."""
    _validate_klon_type(k_type)
    raw_waks = parse_waks(poem_text)
    lines = [analyze_wak(text, index, k_type) for index, text in enumerate(raw_waks)]
    complete = bool(lines) and len(lines) % 4 == 0
    rhyme_checks = _rhyme_checks(lines, k_type)
    core_validation = _run_core_validation(raw_waks, k_type)

    meter_passed = sum(1 for line in lines if line["meter_passed"])
    word_count_passed = sum(1 for line in lines if line["word_count_passed"])
    rhyme_passed = sum(1 for check in rhyme_checks if check["passed"])
    total_checks = (2 * len(lines)) + len(rhyme_checks) + 1
    passed_checks = meter_passed + word_count_passed + rhyme_passed + int(complete)
    score = round(100 * passed_checks / total_checks) if total_checks else 0

    warnings: list[str] = []
    if not complete:
        warnings.append("กลอนหนึ่งบทต้องมี 4 วรรค กรุณาใส่หนึ่งวรรคต่อหนึ่งบรรทัด")
    for check in rhyme_checks:
        if k_type == 8 and check["passed"] and not check["preferred_position"]:
            warnings.append(
                f"สัมผัสจากวรรค {check['source_line']} ไปวรรค {check['target_line']} "
                "อยู่ในตำแหน่งอนุโลม ไม่ใช่ตำแหน่งหลัก 3 หรือ 5"
            )
    if core_validation["passed"] is False:
        warnings.extend(core_validation["messages"])

    failed = (
        not complete
        or any(line["meter_status"] == "ไม่ผ่าน" for line in lines)
        or any(not line["word_count_passed"] for line in lines)
        or any(not check["passed"] for check in rhyme_checks)
        or core_validation["passed"] is False
    )
    needs_review = bool(warnings)
    verdict = "ไม่ผ่าน" if failed else ("ควรตรวจ" if needs_review else "ผ่าน")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "klon_type": k_type,
        "klon_name": KLON_NAMES[k_type],
        "engine": {
            "rhyme": f"core.KhaveeVerifier (project version, k_type={k_type})",
            "pronunciation": "PyThaiNLP syllable_tokenize (ssg only)",
        },
        "input": poem_text,
        "line_count": len(lines),
        "stanza_count": len(lines) // 4,
        "complete_stanzas": complete,
        "lines": lines,
        "rhyme_checks": rhyme_checks,
        "core_validation": core_validation,
        "summary": {
            "verdict": verdict,
            "structural_score": score,
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "meter_passed": meter_passed,
            "meter_total": len(lines),
            "word_count_passed": word_count_passed,
            "word_count_total": len(lines),
            "rhyme_passed": rhyme_passed,
            "rhyme_total": len(rhyme_checks),
        },
        "warnings": list(dict.fromkeys(warnings)),
        "limitations": [
            "คะแนนเป็นสัดส่วนกฎโครงสร้างที่ผ่าน ไม่ใช่คะแนนความไพเราะหรือความหมาย",
            "การแยกพยางค์ใช้ PyThaiNLP SSG เท่านั้น และคำที่ SSG แยกไม่แน่ชัดควรให้มนุษย์ยืนยัน",
            (
                "กลอนสี่ตรวจสัมผัสใน 2 พยางค์แรก หรือ 3 พยางค์แรกเมื่อวรรคนั้นมี 5 พยางค์"
                if k_type == 4
                else "กลอนแปดตรวจสัมผัสใน 5 พยางค์แรก โดยตำแหน่ง 3 และ 5 ถือเป็นตำแหน่งหลัก"
            ),
        ],
    }
