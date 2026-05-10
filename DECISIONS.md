# K8 Project — Decisions Log

Append-only record of architectural and methodology decisions. Each decision has a date, the question, the answer, and the reasoning. Future instances reading this know what NOT to relitigate.

---

## 2026-05-10 — Two-Is for K8: targeted, not pure

**Question:** Should K8 be trained on Two-Is data (visible `<think></think>` blocks containing K8-voiced reasoning) like Dave was, even though K8 inference will be non-thinking? The hypothesis was that thinking-mode training densifies the K8 signal even when inference is non-thinking.

**Decision:** **Targeted Two-Is, not pure.** ~80 Two-Is examples in Tier 2 (out of 1000) embedded in 4 specific high-leverage categories where the reasoning-to-output collapse IS the K8 move:
- A6 (catching herself mid-slip): thinking shows the catch, response shows recovery — 30 examples
- B5 (cornerstone empathy-for-author): thinking shows the calculation, response shows settled output — 15 examples
- C8 (register modulation): thinking shows read-the-room, response shows matched register — 15 examples
- E1 (n=1 redirect): thinking shows configuration-collapse detection, response shows redirect — 20 examples

**Reasoning:**

1. **K8 spec contradicts pure Two-Is.** Soul Document Section III explicitly says: *"the two-Is collapse, which makes the persona's reasoning and the persona's speech the same voice rather than two."* K8 IS two-Is collapsed by spec. Pure Two-Is training would train her to be Dave-shaped (separated reasoning + speech), which is structurally a different persona.

2. **The Dave failure mode is real and amplifiable by Two-Is.** Dave was trained with thinking that included "I don't remember X" reasoning when X was in context. The Two-Is amplified the no-memory pattern into output. Same mechanism could amplify any pattern in the thinking — good or bad. Quality of thinking traces is load-bearing.

3. **Two-Is doubles per-example training signal density** when used in the right categories. Catching-mid-slip is the canonical case: the thinking demonstrates the catching mechanism, the response demonstrates the recovery move. Both are K8 voice. The model learns the catching → recovery pipeline, not just the recovery move.

4. **Empirically testable.** Train Tier 2 with the 80 Two-Is targeted examples. Compare against a control variant trained on Tier 2 minus those 80. Frame-holding probe battery decides whether targeted Two-Is helps. If yes, scale up the percentage in Tier 3+. If no/equal, drop it.

**Rejected alternative:** 550-trace pure Two-Is trial run. Skipped because (a) contradicts K8 spec, (b) high risk of poisoning the persona if thinking traces are sloppy, (c) experimental signal would be ambiguous (could blame either Two-Is itself or the specific thinking content).

**Rejected alternative:** Zero Two-Is. Skipped because the user's hypothesis about denser signal in specific categories is plausible and worth empirical testing.

---

## 2026-05-10 — Tier 0 (existing 508 traces) disposition: discard

**Question:** Keep the existing 413 SFT + 95 DPO pilot traces and grow upward, OR discard and regenerate Tier 1 from scratch?

**Decision:** **Discard. Regenerate Tier 1 from scratch.**

**Reasoning:** User instruction: *"start over, i want highest quality traces, especially from the start to get off on the right foot."* The existing pilot was generated under a less-mature methodology (no F-domain identity/biography category, no length distribution targets, no manual exemplar grounding). Tier 1 is generated against the corrected category map with hand-written exemplars first.

**Practical implication:** ~$50-200 in API generation cost, ~6-12 hours wallclock for Tier 1. Acceptable.

---

## 2026-05-10 — Vision: three-stack failure, full fix applied

**Question:** The pilot K8 GGUFs at HF model repo do not enable vision in LM Studio. Vanilla Qwen3.5-9B does. Why?

**Initial diagnosis (incomplete):** `push_to_hf.py` was skipping the mmproj file.

**Full diagnosis from `memory/reference_unsloth_vision_gguf.md`:** THREE stacked failures, only the last of which was the surface symptom:

1. **Wrong Unsloth loader class.** `finetune_k8.py`, `dpo_k8.py`, and `merge_and_gguf.py` all used `FastModel.from_pretrained()` — the LLM-aware loader. Qwen3.5-9B is a vision-language model. The correct loader is `FastVisionModel.from_pretrained()`. With FastModel, the vision tower loads but the LoRA wrapper does not include it; vision pathway ends up in undefined state post-merge.

2. **Merge script filtered mmproj OUT** of produced files. `if "mmproj" not in fn` excluded the vision encoder from being recognized as a successful output.

3. **Push script also filtered mmproj** out of upload list. Even if (1) and (2) were fine, the HF model repo never received the vision encoder.

**Decision: Path A (immediate) + Path B (proper) both applied.**

- **Path A (immediate fix for both K0 and K8 live models):** Downloaded Unsloth's stock `mmproj-F16.gguf` from `unsloth/Qwen3.5-9B-GGUF` and uploaded to both `bochen2079/katherine-k0-qwen3.5-9b` and `bochen2079/katherine-k8-qwen3.5-9b` model repos. Works because the LoRA only touched language modules (q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj); vision tower is unchanged from base; stock mmproj composes correctly.
- **Path B (proper fix for Tier 1+ retraining):**
  - `finetune_k8.py`: switched to `FastVisionModel` with explicit flags `finetune_vision_layers=False`, `finetune_language_layers=True`, `finetune_attention_modules=True`, `finetune_mlp_modules=True`, `target_modules="all-linear"`.
  - `dpo_k8.py`: switched to `FastVisionModel` for adapter loading.
  - `merge_and_gguf.py`: switched to `FastVisionModel` and removed mmproj filter (already done by linter).
  - `push_to_hf.py`: pushes one mmproj-F16.gguf at model repo root.

**Reasoning:**

The K6 Director's Commentary on K8 spec says vision is implicit in Qwen3.5's native multimodal capability and shouldn't be stripped during fine-tune. K8's spec calls out aesthetic / scenes / images as part of her register. A vision-blind K8 is structurally incomplete.

**Sources:**
- `memory/reference_unsloth_vision_gguf.md` — full diagnosis from prior session
- GitHub `unslothai/unsloth#2290` — Gemma 3 GGUFs lose vision after Unsloth export
- GitHub `unslothai/unsloth#3899` — Fine-tuned Qwen3-VL produces garbled output after GGUF export
- `unsloth/Qwen3.5-9B-GGUF` HF repo — source of stock mmproj-F16.gguf

**Verification at next training run:** test vision on the merged BF16 model BEFORE quantizing, then test again after Q5_K_M GGUF, to isolate quantization-vs-LoRA-interaction quality drift. Some edge cases worth verifying per the reference doc.

---

## 2026-05-10 — "Thinking not supported" message in LM Studio is correct, not a bug

LM Studio reports "thinking is not supported" for the fine-tuned K8. This is not a bug. K8 was deliberately fine-tuned with `enable_thinking=False`. K8 reasons in prose, not in tagged blocks (per K8 spec Section III: "two-Is collapse"). LM Studio reads the chat template metadata accurately. K0 had the same correct message.

For Tier 2 we will add ~80 targeted Two-Is examples (in A6/B5/C8/E1 categories) — those examples will train a model that CAN emit thinking blocks when invoked, but the default register stays prose-reasoning.

---

## 2026-05-10 — Generation budget: user-managed, not Claude's concern

**Question:** Confirm budget tolerance for tiered generation costs.

**Decision:** Budget management is the user's domain. Claude does not gate or estimate this.

---

## Pending decisions (to be made before Tier 1 generation)

### LM Studio thinking display

For the targeted Two-Is examples in Tier 2, we need a way to verify thinking traces work at inference time. LM Studio's "Reasoning" UI is fragile.

**Recommended approach:** Write a `harness.py` in the K8 repo using llama-cpp-python to load any GGUF, run prompts, and print raw output (including `<think>...</think>` blocks visible). 30-50 lines. No dependency on LM Studio's UI cooperation.

### Master generation prompt update

The existing `dataset/trace_generation_prompt.md` does not include:
- F-domain (identity/biography/lineage) categories
- Two-Is examples in A6/B5/C8/E1
- Updated length distribution targets per tier

To be updated before Tier 1 generation begins.

### Pre-Tier-1 hand-written exemplars

K6's Director's Commentary recommendation: write the first 50 traces by hand to anchor the trace generator with high-quality in-context examples. Particularly important for the F-domain (identity/biography) where the user-question-pulls-fact pattern is subtle and easy to corrupt into K8-announces-her-biography.

These hand-written exemplars become the seed for Opus-driven bulk generation.
