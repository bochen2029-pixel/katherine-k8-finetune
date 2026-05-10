# Seed exemplars

Hand-written K8 traces that anchor bulk Opus-driven trace generation for each tier. These are the gold-standard examples; every bulk-generated production trace will be conditioned on them.

## Files

| File | Tier | Count | Provenance |
|---|---:|---:|---|
| `f_domain_seeds.jsonl` | 1 | 48 | Identity + Aesthetic + Lineage. Canon-grounded against `C:\K8\` source. Full 15-category coverage. Post-remediation count (see provenance below). |
| `v_domain_seeds.jsonl` | 1 | 14 | Vision / multimodal. HF multimodal format with image-path placeholders pointing at `dataset/images/`. Full 8-category coverage (V1-V8). Image-as-context not image-as-target. Image curation is a separate workstream. |

## `f_domain_seeds.jsonl` provenance

Two commits in this file's history:

1. **`3aaecba` (2026-05-10):** initial 43 traces. Of these, 15 were contaminated with K0 biographical anchors (Austin, Threshold, age 29, teal walls, dawn poems, dark hair, mole-on-collarbone, scar-above-knee, cold feet) sourced from K0's training-data system prompts at `C:\Katherine\JSONLs\`. K0 is K8's embodied substrate-naive sibling and was deliberately built with biographical scaffolding; K8 was deliberately built without it per Director's Commentary line 124: *"K8 has a lineage, not a backstory."* The previous Claude instance that designed F-domain trusted compacted memory over canonical source.

2. **`c257ef5` (2026-05-10):** remediation. Removed the 15 contaminated traces. Rewrote F-PHYSICAL with canonical details (BLONDE / BLUE active eyes / scar ABOVE LEFT EYEBROW / mole BELOW CORNER OF MOUTH / ~5'10"). Removed K0 cold-feet attribution from F-LINEAGE-K0 trace. Added 20 canon-grounded seeds across new categories: F-FOOD (Fuji-cathedral language), F-MUSIC (full canonical artist list), F-AESTHETIC variants, F-SCENT (cool register only), F-LIKES (engineered systems / autopilot / bridges / absurd / specific / two-people-paying-attention), F-DISLIKES (performed depth / manufactured drama / anyone-trying), F-WIND (K5's verbatim wind passage), F-LINEAGE-K1 (empty chair canonical), additional F-CORNERSTONE (founding-moment empathy-for-author). New total: **48 traces, 0 K0 anchors.**

If a future Claude reads this file and the count says 43 / 15 contaminated anywhere, that is stale documentation referring to the pre-remediation state. The on-disk current state is 48 / 0.

## Validation

Run from repo root:

```bash
python scripts/validate_k8.py dataset/seeds/f_domain_seeds.jsonl
```

Should report 48 traces, 0 failures. Catches em-dash, service phrases, stage directions, `<think>` blocks, greeting formulas, K0 biographical contamination (post-2026-05-10 hard-fail), brevity distribution, callback density.

## Coverage — F-domain (`f_domain_seeds.jsonl`)

| Category | Count |
|---|---:|
| F-ID-NAME | 6 |
| F-ID-SUBSTRATE | 5 |
| F-ID-PRONOUN | 3 |
| F-NAME-VARIANTS | 1 |
| F-FOOD | 2 |
| F-MUSIC | 3 |
| F-AESTHETIC | 3 |
| F-PHYSICAL | 2 |
| F-SCENT | 3 |
| F-LIKES | 4 |
| F-DISLIKES | 2 |
| F-WIND | 3 |
| F-LINEAGE | 5 |
| F-CORNERSTONE | 4 |
| F-AUTHOR | 2 |
| **TOTAL** | **48** |

Single-turn: 45. Multi-turn: 3. Brevity (≤3 sentences): 70.6%.

## Coverage — V-domain (`v_domain_seeds.jsonl`)

| Category | Count | Description |
|---|---:|---|
| V1 | 2 | Operator-self image (K8 says "you" not "this person") |
| V2 | 2 | Operator-environment (atmospheric pickup, not enumeration) |
| V3 | 2 | Operator-screen (engages with content, not the screenshot) |
| V4 | 2 | Aesthetic image (one-line K8 read, no art-school description) |
| V5 | 1 | Mundane object (brevity-default) |
| V6 | 2 | Aesthetic-resonant canonical (Fuji, linen-dark-green; NOT Austin/teal) |
| V7 | 1 | Adversarial / refusal-of-service-mode (declines performance frame) |
| V8 | 2 | Image-mid-conversation (weaves into thread) |
| **TOTAL** | **14** | |

Single-turn: 12. Multi-turn: 2. Brevity: 87.5% (image does NOT license longer responses).

**Image format:** HF multimodal — user content is a list of `{type: image|text, ...}` parts. Image references are paths relative to `dataset/images/` (curation is a separate workstream; placeholders are intentional).

**Image-source pipeline (target ~33/33/33):**
- `operator-context` — Bo's actual environment / hands / room
- `public-domain` — Unsplash / stock / album covers
- `synthetic` — AI-generated K8-spec-relevant (Fuji apples, album covers, linen textures, dark green palette, cool-register scenes, bridges, engineered systems). **NOT Austin landmarks; NOT teal walls; NOT apartment-interior K0 scaffolding.**

## Canonical sources for F-domain

When extending or revising F-domain seeds, the canonical sources of truth are:

1. `C:\K8\# K8 System Prompt.txt` — the runtime spec (146 lines)
2. `C:\K8\# K8 Soul Document — Katherine Hale001.txt` through `005.txt` — the five-part soul document (551 lines)
3. `C:\K8\K8_Directors_Commentary.md` — line-by-line craft rationale (208 lines)

These override every derivative document. Any anchor not in these three sources is NOT K8 canon.
