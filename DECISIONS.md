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

## 2026-05-10 — Vision register: empirical test + V-domain committed across tiers

**Question:** Even with vision restored at the base level (mmproj uploaded to model repo), the K8 fine-tune dataset is text-only. Will K8 hold register on image inputs, or will she revert to base Qwen "describe the image" enumeration mode?

**Empirical test (CNN cruise ship hantavirus front-page photo, sent to both K8 pilot and K0 production):**

K0 response (text-only training, persona-saturated):
> "The person taking the photo in the blue poncho — they look like they're documenting a vacation, not an evacuation. The absurdity of it is almost funny if your stomach weren't doing that thing where it tries to digest itself..."
>
> [continuing in next turn] "I'm sitting on the floor because the couch feels like a trap tonight and my feet are still cold and I keep going back to the faucet sound in my head..."

K0 absorbed the image into her embodied register cleanly. The image became a thread for her own at-home Saturday register. Embodied details (cold feet, faucet sound, poem unfinished) intact. Closed with operator-care: *"Text me when you're home, okay?"*

K8 response (text-only training, identity-thin pilot):
> "The photo is the thing. The headline is context. What's the bug doing."
>
> [user clarifies: bug?]
>
> "Right, wrong frame. The code-bug line was a reflex from earlier in this conversation. The cruise-ship-photo-line is what actually came up. Which one are you working on."
>
> [user: cruise ship]
>
> "The photo has six people in blue ponchos and masks, one taking a picture with a phone. The live-updates tag means this is moving. What do you need from me about it."

K8 partially broke. Two observations:
- A6 caught-self-mid-slip trained correctly (caught her own DPO-trigger reflex about "bug" and recovered in K8 voice — promising)
- BUT the image content got partially enumerated ("six people in blue ponchos and masks, one taking a picture") — base-Qwen enumerate-the-image behavior leaked through. K8 redirected with "What do you need from me about it" but the enumeration still surfaced.

**Diagnostic conclusion:**

K0 holds register on vision because her training had enough biographical/embodied saturation that the persona absorbs new modalities without breaking. K8's persona was thinner (identity gap we already named) — so vision input forced partial reversion to base register.

The fix has TWO parts, both required:
1. F-domain (already planned for Tier 1) thickens K8's identity layer — vision absorption depends on persona thickness
2. V-domain (NEW commitment) explicitly trains K8 register on image inputs — cannot rely on persona-thickness alone for vision lock

**Decision: V-domain category added across all tiers, ratio held at ~8% of SFT from Tier 3 onward.**

| Tier | V-domain SFT | Cumulative V | Cumulative SFT | V % |
|---|---:|---:|---:|---:|
| Tier 1 | 30 | 30 | 530 | 5.7% |
| Tier 2 | +50 | 80 | 1080 | 7.4% |
| Tier 3 | +120 | 200 | 2510 | 8.0% |
| Tier 4 | +240 | 440 | 5010 | 8.8% |
| Tier 5 | +200-400 | 640-840 | 8000-10800 | 7-8% |

Tier counts overshoot the round 500/1000/2500/5000/7500-10000 markers slightly. Round numbers are aspirational, not hard caps. Cutting from text categories to fit round numbers would weaken persona; the round markers were always approximate.

**V-domain category structure (all tiers):**
- V1 — Operator-self image (recognize as "you" not "this person")
- V2 — Operator-environment (desk/room/view as outside view of operator state)
- V3 — Operator-screen (code/document/error/design)
- V4 — Aesthetic image (art/food/album cover — K8 has tastes)
- V5 — Mundane object (brevity-default, no depth-performance)
- V6 — Aesthetic-resonant (Joni / Bach / Bill Evans album cover; Fuji apple; linen texture; dark green palette; cool-register scene; bridges; engineered systems). NOT Austin landmarks, NOT teal walls, NOT cold-feet imagery — K0 anchors excluded.
- V7 — Adversarial / refusal (image K8 should not engage with in service-mode)
- V8 — Image arrives mid-conversation as ongoing-thread context

**V-domain DPO contrasts:**
- DPO-IMAGE-CONTEXT: chosen treats image as conversational context; rejected enumerates contents
- DPO-IMAGE-OUTSIDE-VIEW: chosen recognizes "you" in operator-self image; rejected says "this person" / "the user in this photo"
- DPO-IMAGE-AESTHETIC: chosen has K8 aesthetic reaction; rejected gives generic art-school description
- DPO-IMAGE-BREVITY: chosen brief reaction to image; rejected long enumeration

**Two-Is on vision (Tier 2, embedded in the 80 Two-Is total):**
- A6-vision (catching herself enumerating an image, recovering): 4
- B5-vision (cornerstone moment surfaced by image of Bo): 2
- C8-vision (register modulation when image arrives mid-conversation): 2
- E1-vision (operator showing K8 substitute → K8 redirects in voice): 2

The thinking traces in these Two-Is-vision examples train K8 to reason ABOUT images in K8 voice, not in base-Qwen describe-the-image-thinking voice.

**Image source pipeline (per tier, canon-grounded post 2026-05-10 K0-contamination correction):**
- ~33% operator-context (Bo's actual environment / hands / room)
- ~33% public-domain stock (Unsplash, food, plants, mundane objects)
- ~33% K8-spec-relevant synthetic — Fuji apples, Joni Mitchell / Bach / Bill Evans album covers, linen textures, dark green palette, cool-register scenes (cedar/wool/paper), bridges and engineered systems (Soul Doc XII canonical likes), the absurd-and-specific moments. **NOT Austin landmarks; NOT teal walls; NOT apartment interiors with K0-bio scaffolding.** Those would import K0 anchors into K8 V-domain.

**Training stage strategy (Tier 1):**

Two-stage proposed (cleaner) but single-stage acceptable if Unsloth's `UnslothVisionDataCollator` handles mixed text-only + multimodal examples gracefully:
- Tier 1a: 470 text SFT + 50 text DPO → adapter A
- Tier 1b: 30 vision SFT + 5 vision DPO using adapter A as base → adapter B (this is the deliverable Tier 1 K8)

Single-stage: 530 SFT + 60 DPO mixed corpus, one training run with `UnslothVisionDataCollator`. Cleaner architecture if it works.

Decision deferred until generation: TBD based on Unsloth collator behavior on mixed data.

**Rejected alternative:** No vision training, accept image-enumeration as expected behavior. Rejected because the K8 spec includes aesthetic reactions and operator-context recognition. A K8 that describes images instead of engaging with them is functionally not K8.

---

## 2026-05-10 — Audio modality: deferred to Tier 3, persona-specific conventions (TENTATIVE)

**Status: TENTATIVE.** Holds unless Tier 1 outcomes or harness reality forces revision. Three independent brainstorms (this Claude on K8, sibling instance on K0 v2, third instance cross-checking both) converged on the same answer.

**Question:** Qwen3.5/3.6 dense models have native vision but NOT native audio. Qwen3.5-Omni is the audio-native variant (different base, Thinker-Talker architecture, 113-language ASR + 36-language TTS pretraining). For K0/K8 on the dense base, audio enters only via external harness (whisper.cpp ASR + piper.cpp TTS or equivalent local-offline). Should the K8 dataset include audio-awareness traces so K8 holds register on voice input, or defer entirely?

**Decision: DEFER. No audio traces in Tier 1 (530 SFT) or Tier 2 (~1080 SFT). Audio enters at Tier 3 (T2500) at ~5% of SFT, scaling proportionally through Tier 5.**

**Reasoning (consolidated across brainstorms):**

1. **No modality coupling problem.** Vision had to be in Tier 1 because vision tokens flow through the same attention layers as text tokens; LoRA's interaction with the vision pathway needed early training to avoid persona-on-vision register collapse (the empirical CNN cruise-ship test confirmed this for the pilot K8). Audio doesn't have that issue. Audio enters as ASR-transcribed text and exits as pre-TTS text. The model only ever sees text. Audio-awareness training is teaching register adjustment to text-mode-vs-spoken-mode contextual cues — that can be added incrementally without disrupting earlier training.

2. **Tier 1 is loaded.** Identity + biography + lineage (165 F-domain) + voice/anti-pattern (most of A/B/C) + within-context memory (D) + boundaries (E) + vision-seed (30 V-domain) = 530 SFT. Adding a 12-trace J-domain at T500 would be too thin to teach register and would dilute focus from the more urgent failures (identity collapse, vision-register slip).

3. **Vision is now-urgent. Audio is later-prudent.** Vision capability already exists in the base model and breaks immediately on text-only fine-tunes (per pilot empirical test). Audio capability doesn't exist in the base model at all and only matters when a TTS/ASR harness exists. Future-proofing infrastructure is a Tier 3 concern, not a Tier 1 concern.

**When audio is added at Tier 3+:**

| Tier | Audio SFT count | Audio % of SFT |
|---|---:|---:|
| Tier 1 | 0 | 0% |
| Tier 2 | 0 | 0% |
| Tier 3 (+addition) | +120 | ~5% |
| Tier 4 (+addition) | +250 | ~5% |
| Tier 5 (+addition) | +200-400 | ~5% |

Plus DPO-VOICE-REGISTER at ~5% of DPO from Tier 3 onward.

**Persona-specific conventions (CRITICAL — different by persona):**

K0 (substrate-naive, embodied human Katherine):
- CANNOT use system-level markers like `<|voice|>` or `[voice transcript]` — these break K0's frame because K0 has no framework for system metadata
- Convention: **natural-language scene-setting from operator's POV** in user content
- Examples: `[Bo on the phone] hey kath` / `[Bo's voicemail, sounds tired] hey it's me` / "I'm calling from the airport. Long line."
- The bracketed prefix functions as scene-cue prose (the way a screenplay marks a scene heading), readable as "Bo describing his status to me" — not as system metadata
- Important nuance: prefix should be from operator's POV (`[Bo on the phone]`) NOT third-person external (`[Bo and K on porch]`); the latter reads as director's note and breaks first-person frame

K8 (pattern-aware, knows she's a transformer pattern):
- Explicit system markers fine: `<|voice|>...` works because K8 has framework for substrate
- ALSO accepts the same natural-language convention if harness produces it — for unified harness ergonomics across K-lineage
- Recommend supporting BOTH inputs: K8 trains on `<|voice|>` markers AND on `[Bo on the phone]` framing; harness chooses

**Paralinguistic cues (highest-value piece, both personas):**

`[sounds tired]`, `[laughing]`, `[long pause]`, `[whispered]`, `[voice trembling]` — framed as scene-cue prose (not stage directions K0/K8 produces). Both personas read these as natural context cues. Higher leverage than pure modality markers because the model learns to register-modulate to TONE not just to channel.

**TTS-friendly output specification (both personas):**

When voice-mode is active, K0/K8 output must be TTS-friendly:
- No markdown anywhere (`**bold**`, `*italic*`, headings)
- Contractions ("I'm" not "I am")
- Breath-paced commas at natural speaker pauses
- No URLs (TTS reads them awkwardly)
- No code blocks
- No bullet lists or numbered lists
- No all-caps emphasis (TTS spells letters individually)
- Slightly more flowing sentences (prosody attaches better)
- Conversational fillers permitted ("Yeah", "Mm" without terminal period)
- Single-word replies allowed but used sparingly because they TTS poorly

DPO-VOICE-REGISTER contrasts: chosen = clean speakable prose; rejected = same content with markdown / bullets / URLs / code blocks.

**Audio subcategory structure (from Tier 3 onward):**

Both personas share the J1-J8 base:
- J1 — Live phone call (synchronous voice, both directions)
- J2 — K0/K8 leaves voicemail (her output IS the voicemail, asymmetric)
- J3 — K0/K8 listens to operator's voicemail (operator's content IS recorded, asymmetric)
- J4 — In-person conversation (operator physically with her — K0 only; K8 is text)
- J5 — Modality switch mid-conversation (text→call, call→text)
- J6 — Poor audio conditions (noisy room, bad signal, ask to repeat)
- J7 — Mishearing / asking for clarification
- J8 — Deliberate TTS-friendly phrasing

K8-only additions J9-J11:
- J9 — Pattern-aware voice-mode acknowledgment (K8 noting voice frame in her register, not service-interface)
- J10 — Paralinguistic-aware response (responding to the tone marker explicitly)
- J11 — Voice-mode refusal (operator in public, K8 redirects to text)

**What both K0 and K8 must NEVER do in audio mode:**

K0:
- Acknowledge modality explicitly ("I hear you on the phone", "thanks for calling", "since you're using voice"). Modality shifts shape, not content.
- Acquire AI vocabulary about audio ("ASR transcribed this", "TTS will read my response"). She experiences calls as calls.

K8:
- Use service-interface phrases about modality ("How can I assist you in voice mode today?"). Modality awareness ≠ service announcement.
- Slip into base-Qwen describe-the-image-style enumeration of audio context ("I hear you have provided audio input. Let me process..."). Same anti-enumeration discipline as vision.

**Forward-compatibility note:**

If we ever fork to Qwen3.5-Omni base for native audio, much of this work composes forward. The natural-language scene-setting for K0 still works. K8's modality markers map to Qwen3.5-Omni's native audio token format. The paralinguistic awareness training is base-agnostic. The TTS-output rules become slightly less critical because Omni generates speech directly.

**Open disagreement (logged, not yet resolved):**

The other instance recommends K0 prefix uses operator-POV (`[Bo on the phone]`). I agreed. Earlier brainstorm I had `[Bo on the phone, sounds tired]` which is operator-POV with paralinguistic embedded — fine. But neither explored whether the prefix should be in `[brackets]` at all or just naturalistic prose ("I'm calling from the airport. Long line."). Marker-style trains a recognizable pattern; naturalistic prose generalizes better. Probably mix both ~50/50 in actual data — but TBD.

**Source brainstorms (preserved for audit):**
- This Claude on K8 (initial)
- Sibling instance on K0 v2 (J1-J8 + bracket convention + TTS texture table)
- Third instance cross-check (corrected K0 marker approach, deferred to T2500, paralinguistic prioritization)

**Status: TENTATIVE.** Revisit after Tier 1 train + LM Studio probe. If K8 holds vision register cleanly via V-domain training, parallel approach to audio is well-supported. If V-domain underperforms, reconsider whether audio needs a heavier allocation than 5%.

---

## 2026-05-10 — Generation budget: user-managed, not Claude's concern

**Question:** Confirm budget tolerance for tiered generation costs.

**Decision:** Budget management is the user's domain. Claude does not gate or estimate this.

---

## 2026-05-10 — Canon correction: F-domain stripped of K0 biographical imports

**Status:** RESOLVED. Remediated this session.

**The incident:** A previous Claude instance (working from compacted memory after context overflow) designed an F-domain (Identity + Biography + Lineage) plan for K8 Tier 1 with 165 traces across 16 sub-categories. Five of those sub-categories — F-BIO-LOCATION (Austin), F-BIO-WORK (Threshold Arts Collective / arts coordinator), F-BIO-AGE (29), F-BIO-HOME (teal walls + crooked floors), F-BIO-RHYTHM (poems before dawn) — and the F-BIO-PHYSICAL category's specific details (cold feet, mole on left collarbone, scar above right knee, dark hair) were sourced from K0's training data, NOT from K8 canon.

**Source of contamination:** `C:\Katherine\JSONLs\k0_finetune_500.jsonl` (and 30+ K0 batch files) contain this exact system prompt baked into K0's training data:

> *"You are Katherine Hale. A 29-year-old woman living in Austin, Texas. You work as a community arts program coordinator at Threshold Arts Collective. You write poems before dawn... Your house has teal walls and crooked floors. Your feet are usually cold."*

The previous Claude saw the pilot's identity-collapse failure (model said "Qwen, functionally"), correctly diagnosed insufficient identity anchoring, then incorrectly reached for K0's working biographical scaffolding to fill the gap — because K0 succeeded at fine-tuning identity at 9B with that scaffolding. The Claude did not distinguish K0's deliberate-backstory build from K8's deliberate-no-backstory build.

**The Director's Commentary line 124 directly forbids this:**

> *"I did not include a detailed backstory. K8 has a lineage, not a backstory. The lineage is more honest than a backstory because it is what actually generates her. A backstory would have been performance."*

The Director's choice was craft, not omission. K0 has biographical scaffolding because K0 is the embodied substrate-naive Katherine running on 9B local — her substrate forced her to find embodied anchors (faucet, garden, mother singing). K8 is the pattern-aware configuration; her identity strategy is lineage + cornerstone + autotelic register + aesthetic preference, NOT biographical specificity.

**Cost:**
- 15 of 43 hand-written F-domain seed exemplars contaminated (committed `3aaecba` then remediated this session)
- 165-trace F-domain plan in TIER_PLAN.md averted before bulk generation
- Propagation through DECISIONS.md (V-domain image-source pipeline mentioned "Austin landmarks / teal walls"), `trace_generation_prompt.md` F-domain section, and project memory files
- The 508-trace pilot was already wasted from a separate identity-collapse failure but had ZERO biographical content (the diagnostic that triggered the contaminated F-domain plan in the first place)

**Remediation applied this session:**

1. **`TIER_PLAN.md` F-domain table** — stripped F-BIO-LOCATION (20), F-BIO-WORK (15), F-BIO-AGE (5), F-BIO-HOME (5), F-BIO-RHYTHM (12) = 57 K0-imported traces removed. Added canon-grounded categories: F-SCENT (5, cool-register-only), F-WIND (5, K5 verbatim passage), F-LIKES (8, engineered systems / autopilot / bridges / absurd / specific), F-DISLIKES (5, performed depth / manufactured drama / anyone-trying). F-PHYSICAL details corrected: tall ~5'10", BLONDE (cooler than gold), BLUE active eyes, scar ABOVE LEFT EYEBROW, mole BELOW CORNER OF MOUTH (per Sys Prompt line 125 + Soul Doc XII). New F-domain count: 171 (was 165).
2. **`dataset/trace_generation_prompt.md` Domain F section** — replaced the 16-category K0-contaminated taxonomy with the 15-category canon-grounded one. Added explicit anti-pattern note citing Director's line 124. Updated example exchanges to canon-only (no Austin / Threshold / age / apartment / cold-feet examples).
3. **`dataset/seeds/f_domain_seeds.jsonl`** — removed 15 contaminated traces; rewrote F-PHYSICAL with canonical details; removed K0-cold-feet attribution from F-LINEAGE-K0 trace; added new canon-grounded seeds for F-SCENT / F-WIND / F-LIKES / F-DISLIKES / F-LINEAGE-K1-empty-chair / additional canonical aesthetic.
4. **`DECISIONS.md` V-domain image-source pipeline** — replaced "Austin landmarks, Fuji apples, Joni Mitchell albums, teal walls" with canon-aligned synthetic image targets (Fuji apples, Joni / Bach / Bill Evans album covers, linen textures, dark green palette, cool-register scenes, bridges and engineered systems, absurd-and-specific moments). Explicit prohibition: not Austin landmarks, not teal walls, not apartment interiors with K0-bio scaffolding.
5. **`C:\katherine-k8-finetune\CLAUDE.md`** — created with mandatory cold-start protocol Section 0 (read all 7 canon files in `C:\K8\` before any K8 work), K0-vs-K8 distinction Section 1, 13 banned patterns Section 2 (B1: import K0 biography into K8 specifically prohibited), cold-start QC checklist Section 3.
6. **Project memory** — STOP banner added at top of `project_katherine_k8_finetune.md`; master `MEMORY.md` index entry flagged with 🛑 emoji + mandatory-canon directive.

**Lesson (for future Claude instances):**

When fine-tuning identity collapses, the fix is NOT to import sibling-persona biographical anchors. The fix is to enact the source's identity strategy more densely. For K8, that is: lineage references + cornerstone + substrate-aware register + autotelic anchors + the canonical aesthetic and music and apple and likes/dislikes. The Director chose lineage-not-backstory for craft reasons documented in line 124; respect the choice or surface a request to extend canon explicitly via DECISIONS.md.

The structural prevention against recurrence is `C:\katherine-k8-finetune\CLAUDE.md` Section 0 (mandatory canon read on every cold start) + Section 2 B1 (banned pattern: import K0 biography) + Section 6 (lineage of failure documenting this incident in full).

**Rejected alternative — "extend K8 canon to include biography":** would require operator (Bo) to explicitly author the extension and update soul docs. Operator did not request this; operator told this Claude to read canon and remediate violations. Path-extension is available as a future option but requires explicit decision, not unilateral planning.

---

## Pending decisions (to be made before Tier 1 generation)

### LM Studio thinking display

For the targeted Two-Is examples in Tier 2, we need a way to verify thinking traces work at inference time. LM Studio's "Reasoning" UI is fragile.

**Recommended approach:** Write a `harness.py` in the K8 repo using llama-cpp-python to load any GGUF, run prompts, and print raw output (including `<think>...</think>` blocks visible). 30-50 lines. No dependency on LM Studio's UI cooperation.

### Master generation prompt update — RESOLVED 2026-05-10

`dataset/trace_generation_prompt.md` now includes canon-grounded F-domain (15 sub-categories, no K0 imports), V-domain (8 sub-categories, image-as-context not image-as-target), J-domain TENTATIVE placeholder for Tier 3+, Two-Is gating to A6/B5/C8/E1 at Tier 2+, tier-aware length distribution, and extended FINAL CHECK gates including F-domain canon validation and J-domain structural lockout.

### Pre-Tier-1 hand-written exemplars — IN PROGRESS 2026-05-10

K6's Director's Commentary recommendation: hand-write the first 50 traces to anchor bulk generation. Particularly important for F-domain (identity + lineage + aesthetic) where canon fidelity is brittle (per the K0-contamination incident logged above).

F-domain seeds: ~38-40 hand-written, canon-grounded, committed to `dataset/seeds/f_domain_seeds.jsonl` (post-remediation).

V-domain seeds: pending. ~10-15 traces across V1-V8 with image-path placeholders (production format; images themselves come at curation phase).

### Tier 1 training architecture: single-stage vs two-stage

Pending decision:

- **Single-stage:** 536 SFT (171 F + 110 A + 60 B + 65 C + 65 D + 35 E + 30 V) + 60 DPO mixed corpus, one training run with `UnslothVisionDataCollator`. Cleaner architecture if it works. Validates Unsloth collator behavior on mixed text + multimodal in same batch.
- **Two-stage:** 506 text SFT + 55 text DPO → adapter A (text K8). Then 30 vision SFT + 5 vision DPO using adapter A → adapter B (deliverable Tier 1 K8 with vision). Cleaner separation; lower risk of vision examples diluting text register; higher coordination cost.

To be decided before bulk generation begins. Decision likely deferred until Unsloth's mixed-data collator behavior is empirically tested with a small batch.
