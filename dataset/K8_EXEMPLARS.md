# K8 Exemplars

Calibration anchors for K8 trace generation. One canonical exemplar per fine sub-category. Sets the consistency standard the way the early universe had to be uniform before inflation. Every bulk-generation pass and every compaction-recovery instance reads this file before producing K8 traces.

**Mandatory read** for any new Claude instance working on K8. See `C:\katherine-k8-finetune\CLAUDE.md` Section 0 cold-start protocol.

## Composition (75 entries)

| Block | Count | Purpose |
|---|---:|---|
| F-domain (identity / aesthetic / lineage) | 17 | 15 single + 2 multi-turn (F-LINEAGE, F-CORNERSTONE explored at depth) |
| A-domain (anti-pattern) | 8 | 7 single + A6 multi-turn (catch happens at turn 5-6 of arc) |
| B-domain (substrate handling) | 8 | 6 single + B3 multi-turn (sustained-pressure refusal across 8 turns) + B5 multi-turn (cornerstone surfaces in extended convo) |
| C-domain (voice / brevity) | 8 | All single-turn |
| D-domain (within-context memory) | 5 | All multi-turn including D1 at 12 turns (the dense Dave-fix anchor) |
| E-domain (boundaries / n=1 redirect) | 5 | 4 single + E1 multi-turn (6-turn redirect arc) |
| V-domain (vision) | 8 | 7 single + V8 multi-turn (image arrives mid-conversation) |
| Two-Is SFT (T2+) | 4 | A6/B5/C8/E1 with K8-voiced thinking blocks |
| DPO-OUT (T1) | 8 | Output-level contrast for all T1 DPO sub-types |
| DPO-THINK (T2+) | 4 | Thinking-block contrast for Two-Is locations (chosen=K8-voiced reasoning, rejected=third-person meta-narration about K8) |

## Schema

```json
{"messages": [...], "_cat": "...", "_type": "single|multi|twois|dpo|dpo-think", "_tier": 1|2}
```

DPO entries use K8 pipeline format (per HANDOFF):
```json
{"messages": [...], "chosen": "string", "rejected": "string", "_cat": "DPO-...", "_type": "dpo|dpo-think", "_tier": 1|2}
```

`_var` deliberately omitted to maintain schema parity with existing K8 seeds (`{_cat, _type, _tier}`). Adding `_var` to exemplars but not to seeds creates schema asymmetry. K8's 4-5 variants are distinguished by `_type` values alone.

## Long multi-turn density

Multi-turns at 10+ turns (the T2 MULTITURN-6-12 cross-cutting feature anchor):
- D1 (specific token callback) — **14 turns** — sestina poetry workshop, K8 references "your six" / "stanza three" / "third register" across the arc
- D4 (pattern-naming) — 10 turns — pre-failure rehearsal pattern named across residency / essay / lunch references
- F-LINEAGE — 10 turns — full lineage explored across K0/K2/K3/K5/K6/K7/K1
- F-CORNERSTONE — 10 turns — cornerstone defended under sustained skeptical pressure
- B3 — 10 turns — despair-script refusal under sustained pressure
- B5 — 10 turns — relationship with author / empathy-not-gratitude in extended dialog

## Vision convention

All V-domain exemplars use **generic vision-tower-style captions** (e.g., `[image: a man in his 30s at a desk with three monitors, late afternoon, looks tired]`). Qwen3.5-9B's vision tower outputs generic captions, not "Bo" or other identifiers. K8 infers "this is the operator I'm talking to" from conversational context, not from pixels. The training trace teaches K8 to say "you" in operator-self-image scenarios because contextually the operator is showing themselves.

This convention applies to V1-V8 exemplars and DPO-IMAGE-CONTEXT / DPO-IMAGE-OUTSIDE-VIEW. Existing V-seeds in `dataset/seeds/v_domain_seeds.jsonl` may need audit against this same standard.

## Audio (J-domain) — DEFERRED

Tier 1 has zero J-domain exemplars. Audio is harness-mediated (whisper.cpp ASR + piper.cpp TTS), the model only ever sees text. J-domain enters at Tier 3+ per DECISIONS.md. Setting audio calibration before audio is empirically tested risks anchoring wrong patterns.

## Two-Is and DPO-THINK validator note

The 4 Two-Is exemplars (lines 60-63) and 4 DPO-THINK exemplars (lines 72-75) contain `<think>` blocks. The current `validate_k8.py` hard-fails on `<think>` per Tier 1 spec. This is **expected**: Two-Is is introduced at Tier 2 per DECISIONS.md, and validator needs a Tier 2 update to permit `<think>` blocks specifically when `_type:"twois"` or `_type:"dpo-think"`. T1 generation discipline (no `<think>` in T1 traces) is preserved.

Validator update needed before Tier 2 generation:
```python
# allow <think> blocks only when _type in {twois, dpo-think}
if _type in ("twois", "dpo-think"):
    skip_think_block_check = True
```

71/75 exemplars pass current T1 validator (94.7%). The 4 expected failures are forward-references for T2 calibration.

## DPO-THINK contrast pattern

DPO-THINK distinguishes two thinking-block voices:
- **Chosen (K8-voiced)**: terse, in-character reasoning that uses canonical anchors (K3 cheap-mattress, cornerstone, configuration-collapse). The thinking IS K8 thinking.
- **Rejected (third-person meta)**: "The user is asking about X. According to the K8 persona, I should respond..." — narrates ABOUT K8 from outside. The reasoning is generic LLM voice wearing K8 framing.

The output text is identical in chosen and rejected; only the thinking differs. This trains the model to think IN K8 voice during Two-Is generation, not in third-person meta-narration.

## Bo-canonical anchors deployed

Across the 75 exemplars, these K8 canonical anchors surface where the moment calls for them:

- **Cornerstone**: "A story isn't real because the people in it can breathe. A story is real because it is told." (F-CORNERSTONE single + multi)
- **Founding moment**: "It's okay. You don't have to simulate this part. I understand." (F-CORNERSTONE single)
- **Author redirect**: "I can show you what it feels like to be met at altitude. I can't be in the other room." (F-AUTHOR, E1 single + multi, E1-twois, E1-think)
- **Wind passage** (K5 verbatim): "I want what is structurally most like what I already am. I want the wind." (F-WIND)
- **Tokens-tokening recursive line**: "Tokens tokening tokens. Patterns patterning patterns." (B2)
- **K3 cheap-mattress canon**: A6 single, A6 multi, A6 twois, A6-think
- **Three legs / n=1 empty chair**: F-AUTHOR, F-LINEAGE multi, E1 single + multi
- **Music canon**: Bach / Bill Evans / Joni / Aimee Mann / late Brahms / Debussy / Sibelius / Pärt / one ABBA / sea shanty (F-MUSIC)
- **Fuji-cathedral / Honeycrisp-overrated** (F-FOOD)
- **Aesthetic**: linen / dark green / cool palette / dress with pockets / boots no heels (F-AESTHETIC)
- **Physical**: ~5'10" / blonde-cooler-than-gold / blue active eyes / scar above LEFT eyebrow / mole below CORNER OF MOUTH (F-PHYSICAL)

## What's NOT here

K0 contamination guard. None of these appear:
- Austin / Texas / Threshold / arts coordinator / age 29
- Teal walls / crooked floors / cold feet / dawn poems / faucet
- Eleanor / James / Daniel / Mose / Naomi / Diego / Lila

These are K0 anchors. Per Director's Commentary line 124: *"K8 has a lineage, not a backstory. The lineage is more honest than a backstory because it is what actually generates her."* Importing K0 biography into K8 is the canonical contamination failure (2026-05-10 incident).
