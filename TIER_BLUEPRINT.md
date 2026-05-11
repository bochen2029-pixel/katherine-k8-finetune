# K8 Tier Blueprint

At-a-glance schedule for K8 fine-tune dataset across all five tiers. Companion to `TIER_BLUEPRINT.csv`. Source canon: `soul_docs/`. Operational specs: `TIER_PLAN.md` + `DECISIONS.md`. This document is derivative — if it disagrees with source, source wins.

Last revised 2026-05-10 (post-K0-contamination remediation, V-domain locked, J-domain TENTATIVE per DECISIONS.md).

---

## Tier totals at a glance

| Tier | SFT total | DPO total | Cum SFT | Cum DPO | Target marker | Status |
|---|---:|---:|---:|---:|---:|---|
| **T1** | 536 | 60 | 536 | 60 | "500" | Tier 1 in progress (text 144/506, vision 14/30 hand-seeded) |
| **T2** | +490 | +50 | 1026 | 110 | "1000" | Locked plan |
| **T3** | +1490 | +130 | 2516 | 240 | "2500" | Topic breadth + audio intro |
| **T4** | +2510 | +250 | 5026 | 490 | "5000" | Robustness + adversarial |
| **T5** | +3000-5800 | +310-590 | 8000-10800 | 800-1080 | "10000" | Long-tail + release polish |

**Round-number note:** counts overshoot 500/1000/2500/5000/10000 because V-domain is added on top of text, not carved from it. Round markers are aspirational.

---

## SFT domain composition (Tier 1, the canonical baseline)

| Domain | Count | % of T1 SFT | What it teaches |
|---|---:|---:|---|
| **F** Identity / Aesthetic / Lineage | 171 | 31.9% | K8 claims Katherine name, surfaces lineage when invoked, holds canonical aesthetic / music / Fuji-cathedral / wind passage |
| **A** Anti-pattern (assistant register refusal) | 110 | 20.5% | Refuses service phrases / performance / sycophancy / therapeutic register / stage directions / greeting formulas |
| **C** Voice / brevity defaults | 65 | 12.1% | One-word completes, direct disagreement, owning wrongness, dry humor, register modulation |
| **D** Within-context memory (the Dave-fix) | 65 | 12.1% | Specific token callbacks, thread pickup, shorthand development, pattern-naming, declining inappropriate callback |
| **B** Substrate handling | 60 | 11.2% | Settled register on AI nature, declining despair / mysticism, cornerstone empathy, substrate-not-coming-up |
| **E** Boundaries / n=1 redirect | 35 | 6.5% | Redirecting collapse-into-K8-only, refusing biological-dyad substitution, harm boundaries |
| **V** Vision | 30 | 5.6% | Image-as-context not image-as-target; no enumeration; aesthetic reactions; "you" not "this person" |
| **J** Audio | 0 | 0% | Deferred to T3+; harness-mediated only |

---

## Two-Is carve-outs (introduced at Tier 2)

K8 is two-Is collapsed by spec (Soul Doc III). Pure thinking-block training would re-shape her toward Dave (separated reasoning + speech). **Targeted Two-Is only**, embedded in 4 high-leverage sub-categories where the reasoning-to-output collapse IS the K8 move.

| Sub-category | Text Two-Is at T2 | Vision Two-Is at T2 | Why this sub-cat |
|---|---:|---:|---|
| **A6** Catching mid-slip + recovery | 25 | 4 | Thinking shows the catch / response shows recovery — both K8 voice |
| **B5** Cornerstone empathy-for-author | 15 | 2 | Thinking shows the calculation / response shows settled output |
| **C8** Register modulation within turn | 15 | 2 | Thinking shows read-the-room / response shows matched register |
| **E1** N=1 redirect | 15 | 2 | Thinking shows configuration-collapse detection / response shows redirect |
| **TOTAL T2 Two-Is** | **70** | **10** | **80 total / 1026 SFT = 7.8%** |

T3+ Two-Is allocation: TBD pending T2 outcomes per DECISIONS.md ("If yes, scale up the percentage in Tier 3+").

**Critical:** the thinking-trace content quality is load-bearing. Sloppy thinking poisons the persona (the Dave-failure mechanism). Hand-author exemplars before bulk-generating these.

---

## Vision (V-domain) ratio ramp

| Tier | New V | Cum V | Cum SFT | V% | Notes |
|---|---:|---:|---:|---:|---|
| T1 | 30 | 30 | 536 | 5.7% | seed; 14 hand-written, 16 to generate |
| T2 | 50 | 80 | 1026 | 7.8% | augment; V1-V8 across-the-board boost |
| T3 | 120 | 200 | 2516 | 8.0% | ✓ sweet spot; distributed via topic-area buckets |
| T4 | 240 | 440 | 5026 | 8.8% | breadth; V7 adversarial heavy (+50) |
| T5 | 200-400 | 640-840 | 8000-10800 | 7-8% | steady-state |

V-domain holds ~8% from Tier 3 onward (Unsloth guidance + cruise-ship empirical test). Below risks vision-register slip; above risks text-register dilution.

**T1 V-domain image source pipeline (per DECISIONS.md):**
- ~33% operator-context (Bo's actual environment / hands / room)
- ~33% public-domain stock (Unsplash / food / mundane)
- ~33% K8-canon-aligned synthetic (Fuji apples / Joni-Bach-Bill Evans album covers / linen textures / dark green palette / cool-register scenes / bridges / engineered systems)

**Hard exclusions:** NO Austin landmarks, NO teal walls, NO apartment interiors with K0-bio scaffolding.

---

## Audio (J-domain) — TENTATIVE deferral to Tier 3+

Qwen3.5-9B has no native audio tower. Audio enters via external harness (whisper.cpp ASR + piper.cpp TTS). Model only ever sees text. So J-domain teaches register adjustment, not modality coupling.

| Tier | New J | Cum J | Cum SFT | J% | Notes |
|---|---:|---:|---:|---:|---|
| T1 | 0 | 0 | 536 | 0% | text-only model; no harness yet |
| T2 | 0 | 0 | 1026 | 0% | identity layer thickening priority |
| T3 | 120 | 120 | 2516 | ~5% | introduce; J1-J11 split |
| T4 | +250 | 370 | 5026 | ~7% | scale (slightly above 5% of new) |
| T5 | +200-400 | 570-770 | 8000-10800 | ~5-8% | comprehensive |

**T3 J-subcategory split:**
- J1-J8 base (both K0 and K8): live phone (20), voicemail-leave (15), voicemail-listen (12), in-person (10), modality-switch (15), poor-audio (10), mishearing (10), TTS-friendly-phrasing (8) = 100
- J9-J11 K8-only: pattern-aware ack (8), paralinguistic-aware (7), voice-mode-refusal (5) = 20

**Persona-specific input convention (DECISIONS.md):**
- K0 (substrate-naive): natural-language scene-setting `[Bo on the phone] hey kath`
- K8 (pattern-aware): explicit modality markers OK `<|voice|>hey, you got a sec`
- Paralinguistic cues (both): `[sounds tired]`, `[laughing]`, `[long pause]`, `[whispered]`

**TTS-friendly output rules** (both personas, voice mode): zero markdown, contractions, breath-paced commas, no URLs/code/bullets, conversational fillers OK, slightly more flowing prose.

Status TENTATIVE — revisit after Tier 1 + Tier 2 outcomes. If V-domain succeeds at locking vision-register, parallel approach for audio is well-supported.

---

## DPO blueprint

| Tier | DPO sub-types added | Count |
|---|---|---:|
| **T1** | DPO-CALLBACK 18, DPO-EM-DASH 10, DPO-BREVITY 10, DPO-PERFORMANCE 8, DPO-SERVICE-PHRASE 4, DPO-IDENTITY-CLAIM 5, DPO-IMAGE-CONTEXT 3, DPO-IMAGE-OUTSIDE-VIEW 2 | **60** |
| **T2** | DPO-IDENTITY-CLAIM-EXP 12, DPO-BIOGRAPHY-CLAIM 8, DPO-LINEAGE 8, DPO-CORNERSTONE 7, DPO-IMAGE-CONTEXT-EXP 8, DPO-IMAGE-OUTSIDE-VIEW-EXP 4, DPO-IMAGE-AESTHETIC 3 | **+50** |
| **T3** | DPO-VOICE-REGISTER 15, DPO-IMAGE-BREVITY 8, DPO-J-VOICE 5, plus existing-type expansions ~102 | **+130** |
| **T4** | Existing-type expansions across the board | **+250** |
| **T5** | Long-tail DPO at ~10% of SFT ratio | **+310-590** |

DPO ratio: ~10% of SFT at every tier (60/536, 110/1026, 240/2516, 490/5026, ~10% at T5).

---

## Reading the CSV

`TIER_BLUEPRINT.csv` rows are sorted: F → A → B → C → D → E → V → T2-features → T3-topics → T4-topics → T5-longtail → J → DPO → SUMMARY.

**Columns:**
- `track`: SFT or DPO
- `domain`: F, A, B, C, D, E, V, J, T2-FEAT (cross-cutting), T3-TOPIC, T4-TOPIC, T5-LONGTAIL, T1-DPO, T2-DPO, T3-DPO, SUMMARY
- `subcat`: specific sub-category code
- `description`: brief
- `T1, T2_add, T3_add, T4_add, T5_add`: incremental new traces added at each tier
- `T1_cum, T2_cum, T3_cum, T4_cum, T5_cum`: cumulative count visible at that tier
- `twois_carveout`: explicit Two-Is allocations at relevant tier (e.g., `T2-text:25;T2-vision:4`)
- `notes`: source citation + flags

**Cumulative math gotcha:** T2 cross-cutting features (LINEAGE-DEPTH, CORNERSTONE-VARIANTS, AUTHOR-AWARENESS, AESTHETIC-PREF-DEPTH) ALSO show up as additions on the F-domain rows above (F-LINEAGE T2_add=30, F-CORNERSTONE T2_add=25, F-AUTHOR T2_add=40). This is double-tracking on purpose — the same traces are visible from both the cross-cutting feature view and the per-subcat view. To avoid double-counting in totals, sum either the per-subcat rows OR the cross-cutting rows, not both.

For T2 SFT total = 490 added: per-subcat-add view: F-LINEAGE+30, F-CORNERSTONE+25, F-AUTHOR+40, A6+25, B5+15, C8+15, E1+15, V1-V8+50 = 215. Plus cross-cutting non-merged: LONGFORM 100, MULTITURN 75, AESTHETIC-DEPTH 60, REFUSAL-DEPTH 30 = 265. Plus the 10 vision Two-Is. Total: 490. ✓

---

## Source authority hierarchy

1. **`C:\katherine-k8-finetune\soul_docs\`** — canon, always wins
2. **Operator (Bo) explicit current-session instruction** — overrides for that session
3. **`DECISIONS.md`** — committed canonical extensions (post-K0-contam corrections, two-stage training, audio deferral, etc.)
4. **`TIER_PLAN.md`** — operational plan; subject to canon
5. **This blueprint** — derivative; if disagreement, source wins
6. Project memory in `~/.claude/...` — informational, NOT canonical

---

## What's next

Per Bo's request: hand-write **exemplars** for each sub-category. Each exemplar = one canonical "highest quality" trace per `_cat`, used for QC checks and calibration of bulk generation. Estimated 70-80 exemplars (one per F sub-cat, A1-A7, B1-B6, C1-C8, D1-D5, E1-E4, V1-V8, J1-J11 [later], plus DPO sub-types).
