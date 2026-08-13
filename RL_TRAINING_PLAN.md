# Plan: Deterministic Reward Environment + Gemma RL Fine-tuning for Klon-Paed

**Status:** Proposal — review before building.
**Purpose:** Make the paper's claim *"Two deployments. … a deterministic reward environment for RL-based Klon-Paed generation"* **true** (it is currently aspirational), and add a real, measurable contribution: an RL-tuned Thai Klon-Paed generator.
**Stack:** Unsloth + Gemma (latest) + TRL (GRPO), with our verifier as the reward.

---

## 0. Feasibility — can we do it?

**Yes.** The hard part — a *deterministic* reward function — is already built and evaluated:

- `core.py` — `KhaveeVerifier` (Model B, our 5.3.5-style oracle): `check_sara`, `check_marttra`, `is_sumpus`, `handle_karun_sound_silence`, `_is_true_final`.
- `poetry_overrides.py` — 4,292-entry gold pronunciation dictionary (Klonpad, Model D).
- `huggingface_space/checker.py` — production service that already tokenizes waks, counts syllables (SSG), and checks rhymes, returning plain dicts. **This is the natural backbone of the reward environment.**
- 36,475 gold stanzas (`Dataset/`) for SFT + RL prompts, and an adversarial/audited augmentation set for reward validation.

What is **missing** (this plan builds it):
1. A formal, tested, deterministic reward **environment** API.
2. A training environment (torch + unsloth + trl + peft + bitsandbytes) — not yet installed.
3. An SFT baseline + GRPO fine-tune of a Gemma model on classical Klon-Paed.
4. Evaluation (before/after RL) + optional deployment on the HF Space.

**Local hardware:** NVIDIA RTX 4060, 8 GB VRAM → QLoRA (4-bit) on a ~1B–4B-class Gemma; GRPO with micro-batch 1–2 + gradient accumulation. Workable for a small dataset and a few epochs; bigger models need a rented GPU.

---

## 1. Goal

Ship:
1. `reward_env/` — deterministic reward environment scoring a generated Klon-Paed stanza (syllable count + rules r1/r2/r3/rX), built on `checker.py`/`core.py`.
2. A fine-tuned **Gemma** model (Unsloth) — SFT on the classical corpus, then RL (GRPO) against the reward env.
3. An evaluation report (base Gemma vs SFT vs RL) with real generated stanzas.
4. Paper §2 (contribution bullet 5) and §6.2 updated to describe the shipped environment + tuned model (and optionally the HF model card).

---

## 2. Architecture

```
 prompt: "กลอนแปด [theme/keywords/1st wak]" (or continue-from-wak-1)
   │
   ▼
 Gemma (base | SFT | RL-tuned)  ── generates 4 waks
   │
   ▼
 Reward Environment (deterministic, no randomness)
   ├─ normalize waks (checker.py tokenization)
   ├─ per-wak syllable count (SSG)          → 7–9 syllable meter check
   ├─ tripartite prosody (SSG)              → 3 rhythmic groups per wak
   ├─ rhyme r1 (สดับ→รับ), r2 (รับ→รอง), r3 (รอง→ส่ง)   [intra-stanza]
   ├─ rhyme rX (inter-stanza)               [first-class; curriculum]
   ├─ identical-word rhyme penalty          → no cheap self-rhymes
   ├─ (optional) rhyme-to-keyword / forced-rhyme-word bonus
   ├─ KL penalty + repetition penalty       → anti reward-hacking
   └─ returns Reward(total, r1, r2, r3, rX, meter, tripartite, …) → GRPO
```

**Reward design (graded, deterministic):**
- **Meter — 7–9 syllables per wak** (Klon-Paed is valid at 7, 8, or 9; not exactly 8). Score scaled over [7,9], penalized outside.
- **Tripartite prosody (the intended reading):** each wak is read in **three rhythmic groups**. Reward a wak whose syllable sequence admits a partition into exactly 3 contiguous groups of 2–4 syllables; canonical patterns 3-3-3 (9), 3-2-3 (8), 3-3-2 or 2-3-3 (7) are preferred, but any valid 3-group split also counts.
- **Rhyme rules:** `+1` each for r1, r2, r3; **rX (inter-stanza) is first-class** — older models struggle with it, so it carries explicit weight and is introduced via curriculum (intra-stanza rules first, then rX).
- **No identical-word rhymes:** if a "rhyming" pair is the *same surface word* (cheap self-rhyme), that rule's credit is zeroed/penalized.
- Optional: `+0.5` if the stanza rhymes with a *target* word (rhyme-to-word tasks / curriculum).
- Subtract `β · KL(model ‖ reference)` and a repetition penalty to prevent collapse/reward hacking.
- Total normalized to `[0, 1]`.

**Determinism contract:** same input ⇒ identical score (pure Python over the verifier; no sampling, no randomness). Covered by unit tests.

---

## 3. Model & training stack

| Item | Choice | Note |
|---|---|---|
| Library | **Unsloth** (`pip install unsloth`) | 2–5× faster LoRA/QLoRA, low VRAM, `UnslothGRPOTrainer` |
| Model | **Gemma — latest release** (Gemma 3.x; **Gemma 4 if available** — verify on HF at start) | Pin exact checkpoint; start with the smallest instruct variant that fits 8 GB (1B–4B class) |
| RL | **TRL `GRPOTrainer`** (or Unsloth's GRPO) with a custom reward function calling `reward_env` | GRPO > PPO here: no critic needed, sample-efficient on small GPUs |
| Quantization | 4-bit QLoRA (bitsandbytes) | fits 8 GB VRAM |
| Dtype | bfloat16 | RTX 4060 supports it |
| Tokenizer | Gemma SentencePiece | handles Thai OK; normalize Thai text; test on real stanzas early |

**Open decision:** Gemma size (1B vs 4B-class) depends on (a) whether a Gemma 4 exists, (b) VRAM budget vs. quality. Start small, scale if metrics are weak.

---

## 4. Data

- **SFT:** format the 36,475 gold stanzas as `prompt → response`:
  - `prompt`: theme/keywords or the first wak (task: *continue the stanza*);
  - `response`: remaining waks.
- **RL:** prompts from the gold corpus with a **held-out split** (e.g., hold out whole works — `Phukao Tong` / `Khobut` — to avoid leakage and to allow "is this a real stanza" checks).
- **Reward validation:** reuse the audited augmentation set (10,000 negatives, 1,623 positives, 423 oracle-blind) as a *guard*: the reward env must score curated positives high and negatives low **before** we train on it.
- Optional RLHF-style preference data: pairs of (better/worse) completions derived from the gold vs. corrupted stanzas.

---

## 5. Phases & tasks

### Phase 0 — Training environment setup (~0.5–1 day)
- Create a **separate** venv (e.g., `.venv-rl`) — do **not** pollute the current `.venv` used by the paper/Space tooling.
- Install: CUDA `torch` + `unsloth` + `trl` + `peft` + `bitsandbytes` + `accelerate` + `datasets` + `transformers`.
- Smoke test: `torch.cuda.is_available()` on the RTX 4060; load a tiny Gemma in 4-bit.

### Phase 1 — Reward environment (`reward_env/`) (~1–2 days)
- Implement `KlonReward` on top of `checker.py`:
  - `score_waks(waks: list[str]) -> Reward`
  - `score_text(text: str) -> Reward` (parses/normalizes input)
  - `Reward` dataclass: `total, meter_ok, tripartite, r1, r2, r3, rX, breakdown`
  - helpers: tripartite check (3 groups of 2–4 syllables per wak, canonical patterns preferred) and identical-word rhyme detection.
- Unit tests: deterministic same-input/same-output; positives ≥ threshold; negatives < threshold (from the audit set).
- Export a `reward_fn(samples) -> list[float]` compatible with TRL `GRPOTrainer`.

### Phase 2 — SFT baseline (~1–2 days)
- Build SFT dataset (prompt/response) from the gold corpus.
- Unsloth QLoRA SFT on Gemma, 1–3 epochs; watch loss; sample stanzas.
- Evaluate base vs SFT with the reward env on held-out gold: % stanzas with all rules + 8 syllables.

### Phase 3 — RL with GRPO (~2–4 days)
- `GRPOTrainer` with `reward_fn` (the reward env) + KL penalty.
- Hyper-params for 8 GB: micro-batch 1–2, gradient accumulation, `num_generations` 4–8, gradient checkpointing.
- Iterate reward shaping (weights, length/KL coefficients).
- **Anti-hacking guard:** sample 50 outputs every run; check they are readable Thai and aren't gaming the checker (e.g., repeating a rhyming syllable).

### Phase 4 — Evaluation & paper update (~1–2 days)
- Table: **base Gemma vs SFT vs RL** on held-out stanzas: rhyme-rule accuracy (r1/r2/r3 **and rX**), 7–9-syllable + tripartite compliance, and sanity metrics (unique syllables, repetition, perplexity).
- If strong: update the paper —
  - Contribution bullet 5 → describe the shipped reward environment + Gemma checkpoint;
  - §6.2 → replace "future work" framing with the actual environment + training recipe;
  - add a model card / HF link.
- (Optional) add a "generate" tab to the HF Space using the tuned model.

---

## 6. Constraints & open decisions

1. **"Gemma 4"?** — I could not confirm a Gemma 4 release; the plan targets the **latest Gemma** (Gemma 3 family as of now; use Gemma 4 if it ships). Pin the exact checkpoint + Unsloth version at execution.
2. **8 GB VRAM** — fine for small Gemma + QLoRA + GRPO, but slow. If quality is insufficient, move training to a rented GPU (Colab/runpod) with the same code.
3. **HF token** — needed to download Gemma (gated) and to push the fine-tuned adapter.
4. **Paper scope** — do we ship *both* deployments in this paper, or report the reward environment + a proof-of-concept tuned model (1B)? A proof-of-concept with honest numbers is usually safer for a 6-page paper than overclaiming.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Reward hacking** (model exploits checker loopholes) | KL penalty, keep SFT init, manual sampling review, adversarial/oracle-blind eval as a guard |
| **Self-rhyme / identical-word gaming** | identical-word rule zeroes the credit + repetition penalty in the reward |
| **Tripartite prosody mis-splits** | restrict groups to 2–4 syllables; prefer canonical 3-3-3 / 3-2-3 / 3-3-2 / 2-3-3; validate on gold readings |
| Gemma tokenizer weak on Thai | Normalize Thai text; early sanity tests; (optionally) extend vocabulary |
| RL over-fits rhyme, loses poetry quality | Track diversity/repetition metrics + human spot checks |
| OOM on 8 GB | QLoRA 4-bit, micro-batch 1, gradient checkpointing, CPU offload |
| Time/compute | Small model + small epochs locally; scale to rented GPU only if needed |

---

## 8. Deliverables / acceptance criteria

- [ ] `reward_env/` package with unit tests; deterministic (same input → same score).
- [ ] Training venv + reproducible `requirements` / install script.
- [ ] SFT and RL checkpoints (LoRA adapters) — local and/or pushed to HF.
- [ ] Evaluation report: base vs SFT vs RL (rhyme rules, syllable count, samples).
- [ ] Paper §2 bullet 5 + §6.2 updated to describe the shipped environment + model (only with honest, measured numbers).
- [ ] (Optional) HF Space generation tab.

---

## 9. Rough timeline (single person, local GPU, small model)

| Phase | Effort |
|---|---|
| 0. Env setup | 0.5–1 d |
| 1. Reward env + tests | 1–2 d |
| 2. SFT baseline | 1–2 d |
| 3. GRPO RL | 2–4 d |
| 4. Eval + paper update | 1–2 d |
| **Total** | **~1.5–2 weeks** |

---

*Until Phase 1–4 are done, the paper's "deterministic reward environment" claim is a plan, not a fact — so we either build it (this plan) or soften the wording (e.g., "an educational web tool and a deterministic reward signal for RL generation" + future-work framing).*
