# -*- coding: utf-8 -*-
"""
Hard negative/positive generation for the Klon-8 evaluation.

Method
------
* **Oracle** = the 5.3.5 ``is_sumpus`` (the shared rhyme predicate), applied
  with the canonical rule semantics (r1: Wak1[-1] vs any of Wak2[1..5]; r2:
  Wak2[-1] vs Wak3[-1]; r3: Wak3[-1] vs any of Wak4[1..5]; rX: previous
  Wak4[-1] vs Wak2[-1]). Only oracle-confirmed verdicts label the data.

* **Negatives** (precision probes) are a MIX of operators so the test is not
  saturated by one easy family:
  - ``C6_random``       different สระ AND มาตรา (trivial baseline, ~8%)
  - ``C0_same_mattra``  same มาตรา, different สระ (~10%, saturating -> some)
  - ``C1_same_vowel``   same สระ, different มาตรา (~5%, saturating -> some)
  - ``C3_short_long``   same มาตรา, short<->long สระ swap (เจ็ด/เชด, แข็ง/แขง)
  - ``C4_liquid_final`` ร/ล/ว finals where old pythainlp disagrees (ตัว, ทร,
    หงส์...) -- "final consonant" confusion
  - ``C5_lead_head``    ห/อ นำ (leading) words
  - ``C2_trap``         karun / ฤ / cluster trap words
  - ``C8_oracle_blind`` known oracle misses (genuine rhymes the oracle labels
    as non-rhymes) -> precision probes, so precision is not 100% everywhere
  Simple baselines total ~20-25%; edge cases dominate.

* **Positives** (recall on tricky words): the source syllable of a genuine
  gold rhyme is swapped for a tricky rhyming candidate from the
  dictionary-driven pool (same สระ + มาตรา rhyme class, oracle-confirmed).
  Each positive is STANDALONE: every other rule's truth must be unchanged, so
  the instance tests exactly one rhyme in an otherwise-intact stanza. Each
  records its phenomenon tag, whether BOTH syllables needed phonetic
  normalisation, and whether the 5.0.1 checker rejects the pair (the genuine
  A-vs-B differentiator).

* **Review**: two human-readable TSVs are written so the author can check the
  data before it is used in metrics:
  - ``candidates_review.tsv`` -- the candidate WORD LIST per rhyme class,
    with every word's สระ / มาตรา spelled out (raw + post-normalisation + old
    pythainlp) so the author verifies the pool once, not each instance;
  - ``review_negatives.tsv`` / ``review_positives.tsv`` -- compact instances
    with the swap and its sara/mattra up front.

Usage:
    .venv\\Scripts\\python.exe Paper\\augment\\corrupt.py \\
        --per-rule 1500 --positives 300 --out-dir Paper\\augment\\output
"""
import argparse
import json
import os
import random
import sys
import time
from collections import Counter, OrderedDict, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                     # augment
sys.path.insert(0, os.path.dirname(_HERE))    # Paper
sys.path.insert(0, os.path.dirname(os.path.dirname(_HERE)))  # repo root

from pythainlp.tokenize import syllable_tokenize  # noqa: E402

from data_loading import load_stanzas  # noqa: E402
from eval_checkers import _dev_core, _orig_core  # noqa: E402
from poetry_overrides import POETRY_OVERRIDES  # noqa: E402
from augment.tricky_words import (  # noqa: E402
    EXTRA_SYLLABLES,
    HARD_POSITIVE_PAIRS,
    LEAD_POOL,
    ORACLE_BLIND_FAMILIES,
    ORACLE_LIMITATIONS,
    VOWEL_LENGTH_SWAP,
    build_positive_pairs,
    clean_neg_syllables,
    clean_syllables,
    dictionary_syllables,
    is_clean_syllable,
    liquid_final_pool,
    phenomenon_tags,
    rhyme_class,
    syllable_report,
)

RULES = ("r1_w1_w2", "r2_w2_w3", "r3_w3_w4", "rX_inter")
kv = _dev_core.KhaveeVerifier()
old_kv = _orig_core.KhaveeVerifier()

# Target negative mix (fraction of --per-rule). C0 is minor (same-mattra
# saturates); edge cases dominate. If an edge family exhausts its pool, the
# leftover quota is redistributed to the OTHER edge families first, and C0
# only absorbs whatever is still missing (so C0 stays ~10-15%). C2_trap is
# kept modest (too many karun/loanword traps looked noisy); C8 (oracle-blind)
# only fires when the rhyme target is genuinely in the silent-ร/เอะ+กด family.
NEG_MIX = [
    ("C6_random", 0.05),
    ("C0_same_mattra", 0.08),
    ("C1_same_vowel", 0.08),
    ("C3_short_long", 0.26),
    ("C4_liquid_final", 0.18),
    ("C5_lead_head", 0.10),
    ("C2_trap", 0.12),
    ("C8_oracle_blind", 0.06),
]
FILL_OP = "C0_same_mattra"

OP_NOTES = {
    "C0_same_mattra": "same mattra",
    "C1_same_vowel": "same sara",
    "C6_random": "diff sara+mat (baseline)",
    "C3_short_long": "short<->long sara",
    "C4_liquid_final": "ร/ล/ว final (old disagrees)",
    "C5_lead_head": "ห/อ นำ",
    "C2_trap": "karun/ฤ/cluster",
    "C8_oracle_blind": "oracle-blind limitation",
    "HP_tricky": "tricky-rhyme positive",
}


def syl(w: str) -> list:
    return list(syllable_tokenize(w, engine="ssg"))


def oracle_rules(w1, w2, w3, w4, prev_w4):
    """Canonical rule truths via ssg segmentation + the 5.3.5 is_sumpus."""
    s1, s2, s3, s4 = syl(w1), syl(w2), syl(w3), syl(w4)
    return {
        "r1_w1_w2": any(kv.is_sumpus(s1[-1], t) for t in s2[1:6]),
        "r2_w2_w3": bool(s2 and s3 and kv.is_sumpus(s2[-1], s3[-1])),
        "r3_w3_w4": any(kv.is_sumpus(s3[-1], t) for t in s4[1:6]),
        "rX_inter": None if prev_w4 is None
        else bool(kv.is_sumpus(syl(prev_w4)[-1], s2[-1])),
    }


def build_inventory(stanzas):
    inv = set()
    for s in stanzas:
        for w in (s.w1, s.w2, s.w3, s.w4):
            inv.update(syl(w))
        if s.prev_w4:
            inv.update(syl(s.prev_w4))
    for vals in POETRY_OVERRIDES.values():
        inv.update(vals)
    inv.update(EXTRA_SYLLABLES)
    return sorted(x for x in inv if x)


def build_indexes(syls):
    mattra_idx = defaultdict(list)
    vowel_idx = defaultdict(list)
    sm_idx = defaultdict(list)      # (raw sara, raw mattra)
    for x in syls:
        s, m = kv.check_sara(x), kv.check_marttra(x)
        mattra_idx[m].append(x)
        vowel_idx[s].append(x)
        sm_idx[(s, m)].append(x)
    return mattra_idx, vowel_idx, sm_idx


def _nonrhymes_with(C, avoid):
    return all(kv.is_sumpus(C, t) is False for t in avoid)


def _pool_for(op, S, avoid, mi, vi, sm_idx, pools, inv):
    if op == "C0_same_mattra":
        return mi.get(kv.check_marttra(S), [])
    if op == "C1_same_vowel":
        return vi.get(kv.check_sara(S), [])
    if op == "C3_short_long":
        s = VOWEL_LENGTH_SWAP.get(kv.check_sara(S))
        return sm_idx.get((s, kv.check_marttra(S)), []) if s else []
    if op == "C4_liquid_final":
        return pools["liquid"]
    if op == "C5_lead_head":
        return pools["lead"]
    if op == "C2_trap":
        return pools["traps"]
    if op == "C8_oracle_blind":
        fams = {rhyme_class(t, kv) for t in avoid}
        return [c for c, fam in ORACLE_BLIND_FAMILIES.items() if fam in fams]
    if op == "C6_random":
        return inv
    return []


def find_negatives(S, avoid, rng, op, mi, vi, sm_idx, pools, inv,
                   used_pairs, maxk=3):
    """Candidates for an operator that stay non-rhyming with ``avoid``."""
    pool = list(_pool_for(op, S, avoid, mi, vi, sm_idx, pools, inv))
    rng.shuffle(pool)
    out = []
    for C in pool:
        if C == S or (S, C) in used_pairs:
            continue
        if not _nonrhymes_with(C, avoid):
            continue
        used_pairs.add((S, C))
        out.append((C, op))
        if len(out) >= maxk:
            return out
    return out


def _neg_note(op, S, C) -> str:
    base = OP_NOTES.get(op) or op
    if op == "C8_oracle_blind":
        for entry in ORACLE_LIMITATIONS:
            if S in entry["pair"] or C in entry["pair"]:
                return f"{base}:{entry['reason']}"
    return base


def _ordered_candidates(plist, rng):
    """Order candidates for one source syllable so picks stay diverse:
    both-normalise first (old_fail interleaved ~3:1 with old-pass), then
    phenomenon-tagged, then mattra-family, each alternating classical/dict."""
    def _tier(p):
        if p["both_normalize"]:
            return 0
        return 1 if p["tag"] != "mattra_family" else 2

    tiers = {0: [], 1: [], 2: []}
    for p in plist:
        tiers[_tier(p)].append(p)
    ordered = []
    b = tiers[0]
    fails = [p for p in b if p["old_fail"]]
    passes = [p for p in b if not p["old_fail"]]
    rng.shuffle(fails)
    rng.shuffle(passes)
    i = j = 0
    while i < len(fails) or j < len(passes):
        for _ in range(3):
            if i < len(fails):
                ordered.append(fails[i])
                i += 1
        if j < len(passes):
            ordered.append(passes[j])
            j += 1
    for t in (1, 2):
        cl = [p for p in tiers[t] if p["classical"]]
        dc = [p for p in tiers[t] if not p["classical"]]
        rng.shuffle(cl)
        rng.shuffle(dc)
        i = j = 0
        while i < len(cl) or j < len(dc):
            for _ in range(3):
                if i < len(cl):
                    ordered.append(cl[i])
                    i += 1
            if j < len(dc):
                ordered.append(dc[j])
                j += 1
    return ordered


def find_positives(S, used_pairs, index, maxk=2):
    """Dict-driven candidates that the oracle confirms DO rhyme with S.

    Returns (candidate, tag, both_normalize, old_fail) tuples.
    """
    out = []
    for p in index.get(S, ()):
        C = p["b"] if p["a"] == S else p["a"]
        if C == S or (S, C) in used_pairs:
            continue
        if kv.is_sumpus(S, C) is not True:
            continue
        used_pairs.add((S, C))
        out.append((C, p["tag"], p["both_normalize"], p["old_fail"]))
        if len(out) >= maxk:
            return out
    return out


def _replace_last(wak, S, C):
    if not wak.endswith(S):
        return None
    return wak[: len(wak) - len(S)] + C


def _rule_site(rid, s):
    """Return (wak_index_1based, original_syllable, avoid_list) for a rule."""
    if rid == "r1_w1_w2":
        return 1, syl(s.w1)[-1], syl(s.w2)[1:6]
    if rid == "r2_w2_w3":
        return 3, syl(s.w3)[-1], [syl(s.w2)[-1]]
    if rid == "r3_w3_w4":
        return 3, syl(s.w3)[-1], syl(s.w4)[1:6]
    # rX
    return 2, syl(s.w2)[-1], [syl(s.prev_w4)[-1]]


REVIEW_HEADER = [
    "id", "kind", "rule", "op", "wak#", "swap(S->C)",
    "orig_wak", "new_wak",
    "S_sara", "S_mat", "C_sara", "C_mat",
    "tag", "both_norm", "oldA_fail", "broken",
    "loc", "note",
]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-rule", type=int, default=1500,
                    help="target negatives per rule (default 1500)")
    ap.add_argument("--positives", type=int, default=300,
                    help="target positives per rule (default 300)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=os.path.join(_HERE, "output"))
    args = ap.parse_args()
    rng = random.Random(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()

    stanzas = load_stanzas()
    print(f"building inventory from {len(stanzas)} stanzas...", flush=True)
    inv = build_inventory(stanzas)
    print(f"  inventory: {len(inv)} classical syllables", flush=True)
    inv_clean = clean_syllables(inv)

    dict_syls = clean_syllables(dictionary_syllables(
        cache_path=os.path.join(args.out_dir, "dict_syllables_v3.json")))
    print(f"  dictionary syllables: {len(dict_syls)}", flush=True)
    all_syls = sorted(set(inv_clean) | set(dict_syls))
    mi, vi, sm_idx = build_indexes(all_syls)
    classical_set = set(inv_clean)

    pools = {
        "liquid": clean_syllables(liquid_final_pool(all_syls, kv, old_kv)),
        "lead": clean_syllables(LEAD_POOL),
        # trap pool allows curated multi-sound ฤ words (ฤดู/พฤษภ) as
        # negative candidates -- the oracle gate still verifies non-rhyme
        "traps": clean_neg_syllables(EXTRA_SYLLABLES),
    }

    by_story = OrderedDict()
    for s in stanzas:
        by_story.setdefault(s.story, []).append(s)
    stories = sorted(by_story)
    used_neg_pairs = set()
    used_pos_pairs = set()
    instances = []
    neg_rows = []
    pos_rows = []
    neg_counts = defaultdict(int)
    pos_counts = defaultdict(int)
    neg_op_counts = defaultdict(int)

    def _emit(kind, s, rid, waks, prev_w4, S, C, op, broken, wak_idx,
              tag="", both_normalize=False, old_fail=False, note=""):
        inst = {
            "id": f"{'pos' if kind == 'positive' else 'neg'}_"
                  f"{len(instances):06d}",
            "kind": kind, "rule": rid,
            "gold": 0 if kind == "negative" else 1,
            "story": s.story, "chapter": s.chapter, "row": s.row,
            "w1": waks[0], "w2": waks[1], "w3": waks[2], "w4": waks[3],
            "prev_w4": prev_w4, "op": op,
            "source_syl": S, "candidate": C, "broken": broken,
            "tag": tag, "both_normalize": both_normalize,
            "old_fail": old_fail, "note": note,
        }
        instances.append(inst)
        orig_waks = s.waks()
        row = [
            inst["id"], kind, rid, op, f"w{wak_idx}", f"{S}->{C}",
            orig_waks[wak_idx - 1], waks[wak_idx - 1],
            kv.check_sara(S), kv.check_marttra(S),
            kv.check_sara(C), kv.check_marttra(C),
            tag or "-", "Y" if both_normalize else "N",
            "Y" if old_fail else "N", ",".join(broken) or "-",
            f"{s.story}#{s.chapter}:{s.row}", note or "-",
        ]
        (neg_rows if kind == "negative" else pos_rows).append(row)

    # ---- negatives (mixed operators; per-op quota passes). Edge families fill
    # first; leftover quota is redistributed to other edge families; C0 is the
    # very last resort so it stays ~10-15% ----
    neg_targets = {op: int(round(args.per_rule * f)) for op, f in NEG_MIX}
    # redistribution only feeds the true edge families -- the simple baselines
    # (C6, C1, C0) stay capped so precision is not saturated by easy cases.
    baseline_ops = {FILL_OP, "C6_random", "C1_same_vowel"}
    edge_ops = [op for op, _ in NEG_MIX if op not in baseline_ops]
    op_order = [op for op, _ in NEG_MIX] + [FILL_OP]

    def _fill_neg_op(rid, op, target, op_actuals):
        """Fill one operator for one rule up to ``target`` (or exhaustion)."""
        for story in stories:
            if (neg_counts[rid] >= args.per_rule
                    or op_actuals[op] >= target):
                break
            for s in by_story[story]:
                if (neg_counts[rid] >= args.per_rule
                        or op_actuals[op] >= target):
                    break
                if rid == "rX_inter" and s.prev_w4 is None:
                    continue
                o_orig = oracle_rules(s.w1, s.w2, s.w3, s.w4, s.prev_w4)
                if o_orig[rid] is not True:
                    continue  # only corrupt genuine gold rhymes
                wak_idx, S, avoid = _rule_site(rid, s)
                cands = find_negatives(S, avoid, rng, op, mi, vi, sm_idx,
                                       pools, all_syls, used_neg_pairs)
                if not cands:
                    continue
                C, _op = cands[0]
                new_wak = _replace_last(s.waks()[wak_idx - 1], S, C)
                if new_wak is None:
                    continue
                waks = list(s.waks())
                waks[wak_idx - 1] = new_wak
                o = oracle_rules(waks[0], waks[1], waks[2], waks[3],
                                 s.prev_w4)
                if o[rid] is not False:
                    continue  # not actually broken
                broken = [r for r in RULES
                          if o[r] is False and o_orig[r] is True]
                _emit("negative", s, rid, waks, s.prev_w4, S, C, op,
                      broken, wak_idx, note=_neg_note(op, S, C))
                neg_counts[rid] += 1
                op_actuals[op] += 1
                neg_op_counts[op] += 1

    for rid in RULES:
        op_actuals = defaultdict(int)
        # primary passes: each edge op to its target, then C0 to its target
        for op in op_order:
            if neg_counts[rid] >= args.per_rule:
                break
            _fill_neg_op(rid, op, neg_targets[op], op_actuals)
        # redistribute leftover to edge families (round-robin) before C0
        if neg_counts[rid] < args.per_rule:
            exhausted = set()
            while (neg_counts[rid] < args.per_rule
                    and len(exhausted) < len(edge_ops)):
                progressed = False
                for op in edge_ops:
                    if op in exhausted or neg_counts[rid] >= args.per_rule:
                        continue
                    before = op_actuals[op]
                    _fill_neg_op(rid, op, args.per_rule, op_actuals)
                    if op_actuals[op] > before:
                        progressed = True
                    else:
                        exhausted.add(op)
                if not progressed:
                    break
        # last resort: C0 absorbs whatever is still missing
        _fill_neg_op(rid, FILL_OP, args.per_rule, op_actuals)
    print(f"negatives: {dict(neg_counts)}", flush=True)
    print(f"  by op: {dict(neg_op_counts)}", flush=True)

    # ---- dictionary-driven positive pool ----
    print("building dictionary-driven positive pool...", flush=True)
    seed_pairs = [p for p in HARD_POSITIVE_PAIRS
                  if is_clean_syllable(p[0]) and is_clean_syllable(p[1])]
    pos_pairs = build_positive_pairs(
        kv, rng, all_syls, seed_pairs=seed_pairs,
        max_pairs_per_class=60, max_both_per_class=400,
        old_checker=old_kv, classical_set=classical_set)
    by_src = defaultdict(list)
    for p in pos_pairs:
        by_src[p["a"]].append(p)
        by_src[p["b"]].append(p)
    pos_index = {S: _ordered_candidates(plist, rng)
                 for S, plist in by_src.items()}
    pool_tags = Counter(p["tag"] for p in pos_pairs)
    pool_both = sum(1 for p in pos_pairs if p["both_normalize"])
    pool_ofail = sum(1 for p in pos_pairs
                     if p["both_normalize"] and p["old_fail"])
    print(f"  pool: {len(pos_pairs)} oracle-verified pairs, "
          f"{len(pos_index)} source syllables, "
          f"{pool_both} both-normalise ({pool_ofail} old-fail)", flush=True)
    for tag, n in pool_tags.most_common():
        print(f"    {tag:<30} {n}", flush=True)

    # ---- hard positives (standalone: other rules unchanged) ----
    pos_tags = Counter()
    pos_both = 0
    pos_ofail = 0
    pos_classical = 0
    for rid in RULES:
        for story in stories:
            if pos_counts[rid] >= args.positives:
                break
            for s in by_story[story]:
                if pos_counts[rid] >= args.positives:
                    break
                if rid == "rX_inter" and s.prev_w4 is None:
                    continue
                o_orig = oracle_rules(s.w1, s.w2, s.w3, s.w4, s.prev_w4)
                if o_orig[rid] is not True:
                    continue
                wak_idx, S, _avoid = _rule_site(rid, s)
                cands = find_positives(S, used_pos_pairs, pos_index)
                if not cands:
                    continue
                C, tag, both, ofail = cands[0]
                new_wak = _replace_last(s.waks()[wak_idx - 1], S, C)
                if new_wak is None:
                    continue
                waks = list(s.waks())
                waks[wak_idx - 1] = new_wak
                o = oracle_rules(waks[0], waks[1], waks[2], waks[3],
                                 s.prev_w4)
                if o[rid] is not True:
                    continue  # oracle must confirm the rhyme still holds
                if any(o[r] != o_orig[r] for r in RULES if r != rid):
                    continue  # standalone: don't disturb other rhymes
                broken = [r for r in RULES
                          if o[r] is False and o_orig[r] is True]
                _emit("positive", s, rid, waks, s.prev_w4, S, C, "HP_tricky",
                      broken, wak_idx, tag, both, ofail,
                      "tricky-rhyme positive")
                pos_tags[tag] += 1
                pos_both += int(both)
                pos_ofail += int(ofail)
                pos_classical += int(C in classical_set)
                pos_counts[rid] += 1
    print(f"positives: {dict(pos_counts)}", flush=True)
    print(f"  by tag: {dict(pos_tags.most_common())}", flush=True)
    print(f"  both-normalise probes: {pos_both}", flush=True)
    print(f"  positives where 5.0.1 rejects (old_fail): {pos_ofail}",
          flush=True)
    pos_total = sum(pos_counts.values())
    print(f"  classical candidates: {pos_classical} / {pos_total}",
          flush=True)

    # ---- review word lists (per rhyme class) ----
    word_info = {}
    for p in pos_pairs:
        for w in (p["a"], p["b"]):
            word_info.setdefault(w, w in classical_set)
    cand_rows = []
    for w in sorted(word_info):
        rep = syllable_report(w, kv, old_kv)
        tags = "|".join(sorted(phenomenon_tags(w, kv))) or "-"
        cand_rows.append([
            f"{rep['norm_sara']}|{rep['norm_mart']}",
            w, rep["sara"], rep["mart"], rep["norm_class"],
            rep["old_sara"], rep["old_mart"],
            "Y" if rep["old_differs"] else "N",
            tags, "classical" if word_info[w] else "dict",
        ])
    cand_rows.sort(key=lambda r: (r[0], r[1]))

    # ---- write outputs ----
    with open(os.path.join(args.out_dir, "instances.json"),
              "w", encoding="utf-8") as f:
        json.dump(instances, f, ensure_ascii=False, indent=1)

    def _write_tsv(name, header, rows):
        path = os.path.join(args.out_dir, name)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("\t".join(header) + "\n")
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
        return path

    p_neg = _write_tsv("review_negatives.tsv", REVIEW_HEADER, neg_rows)
    p_pos = _write_tsv("review_positives.tsv", REVIEW_HEADER, pos_rows)
    p_cand = _write_tsv(
        "candidates_review.tsv",
        ["rhyme_class(sara|mat)", "word", "raw_sara", "raw_mat",
         "norm_class", "old_sara", "old_mat", "old_differs",
         "tags", "source"],
        cand_rows)

    with open(os.path.join(args.out_dir, "stats.json"),
              "w", encoding="utf-8") as f:
        json.dump({
            "negatives_per_rule": dict(neg_counts),
            "negatives_by_op": dict(neg_op_counts),
            "negatives_by_op_pct": {
                op: round(100.0 * n / max(1, sum(neg_op_counts.values())), 1)
                for op, n in sorted(neg_op_counts.items())},
            "positives_per_rule": dict(pos_counts),
            "positive_instances_by_tag": dict(pos_tags),
            "positive_instances_both_normalize": pos_both,
            "positive_instances_old_fail": pos_ofail,
            "positive_instances_classical": pos_classical,
            "positive_instances_dict": pos_total - pos_classical,
            "positive_pool_pairs": len(pos_pairs),
            "positive_pool_both_normalize": pool_both,
            "positive_pool_old_fail": pool_ofail,
            "candidate_words": len(word_info),
            "inventory_size": len(inv),
            "dictionary_syllables": len(dict_syls),
            "total_instances": len(instances),
            "seed": args.seed,
        }, f, ensure_ascii=False, indent=2)

    print(f"wrote instances.json ({len(instances)})", flush=True)
    print(f"wrote {p_neg} ({len(neg_rows)} rows)", flush=True)
    print(f"wrote {p_pos} ({len(pos_rows)} rows)", flush=True)
    print(f"wrote {p_cand} ({len(cand_rows)} rows)", flush=True)
    print(f"wrote stats.json ({time.time() - t0:.0f}s total)", flush=True)


if __name__ == "__main__":
    main()
