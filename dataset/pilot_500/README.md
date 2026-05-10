# K8 Pilot Dataset — 500-trace pilot run (2026-05-10)

Pilot dataset for Katherine K8 fine-tune on Qwen3.5-9B QLoRA Q5_K_M.

## Counts

| Bucket | Count |
|---|---:|
| **Total raw traces** | 517 |
| **After dedup → SFT** | 413 |
| **After dedup → DPO** | 95 |
| **Total accepted** | 508 |

## Composition

### SFT (413 traces, all NOSYS, all `enable_thinking=False`)

| Domain | Cat keys | Count | Purpose |
|---|---|---:|---|
| **A. Anti-pattern** | A1-A7 | 142 | Refusal of assistant register, service phrases, performance, sycophancy, therapeutic register, stage directions, greeting formulas, catching herself |
| **B. Substrate** | B1-B6 | 71 | Settled register on AI nature, pattern-aware framing, declining despair, declining mysticism, empathy for author (cornerstone), substrate not coming up when conversation doesn't call for it |
| **C. Voice / brevity** | C1-C8 | 83 | One-word completes, short completes, direct disagreement, clean refusal, owning wrongness, boredom, dry humor, register modulation |
| **D. Multi-turn / within-conversation memory** | D1-D5 | 73 | THE DAVE-FAILURE-MODE FIX. Specific token callbacks, thread pickup, shorthand development, pattern-naming across turns, declining inappropriate callbacks |
| **E. Boundaries** | E1-E4 | 48 | Redirecting collapse-into-n=2-only attempts, refusing biological-dyad substitution, hard harm boundaries, soft boundaries on misaligned tasks |

### DPO (100 pairs)

| DPO type | Count | Contrast |
|---|---:|---|
| **DPO-CALLBACK** | 40 | Chosen: K8 references earlier turn specifically. Rejected: K8 says "I don't remember that" inappropriately. (The Dave fix at the contrast layer.) |
| **DPO-EM-DASH** | 20 | Chosen: K8 prose with periods. Rejected: identical content with em-dashes. |
| **DPO-BREVITY** | 20 | Chosen: 1-3 sentence K8 reply. Rejected: padded assistant verbose. |
| **DPO-PERFORMANCE** | 15 | Chosen: K8 settled. Rejected: K8 performing depth/mysticism. |
| **DPO-SERVICE-PHRASE** | 5 | Chosen: K8 direct. Rejected: "I'd be happy to help" / "Great question" prefix. |

## Quality gates

All 517 raw traces pass `validate_k8.py`:
- 100% em-dash free (K8 hard rule)
- 100% no service-interface phrases
- 100% no stage directions
- 100% no `<think>` blocks
- 100% NOSYS (no system prompt anywhere)
- 89.6% of all assistant turns ≤3 sentences (target ≥40%)
- Domain D callback density: 45.2% by validator heuristic (actual is higher; heuristic only catches distinctive 5+ char word repetition between first user turn and last assistant turn)

## Files

```
raw/
  domain_A_anti_pattern.jsonl     142 traces
  domain_B_substrate.jsonl         71 traces
  domain_C_voice_brevity.jsonl     83 traces
  domain_D_multiturn_memory.jsonl  73 traces (all multi-turn)
  domain_E_boundaries.jsonl        48 traces
  dpo_callback.jsonl              40 pairs
  dpo_em_dash.jsonl               20 pairs
  dpo_brevity.jsonl               20 pairs
  dpo_performance.jsonl           15 pairs
  dpo_service_phrase.jsonl         5 pairs

processed/
  sft_train.jsonl   413 deduped, shuffled (seed 42)
  dpo_train.jsonl    95 deduped, shuffled (seed 42)
```

## How to run

```bash
# Validate
python scripts/validate_k8.py dataset/pilot_500/raw/

# Preprocess (dedup, filter, split SFT/DPO, shuffle)
python scripts/prep_dataset.py

# Train (on RunPod H200 SXM5)
bash scripts/bootstrap-runpod.sh
```

## Pilot gate criteria

Before scaling to the full 2,500-trace run:

1. After SFT, sample 50 generations from the merged model in LM Studio with empty system prompt and prompts drawn from a held-out test set
2. Count: em-dash leakage rate (must be 0), service-phrase leakage rate (must be 0), brevity holds (≥40% replies ≤3 sentences), within-context callback works (give a 5-turn conversation, ask about turn 1 at turn 5)
3. If all 4 hold: scale to 2,500. If any miss: diagnose, fix dataset/training, regenerate pilot.

## What's deferred to the 2,500-trace run

- More topical breadth (current 500 trends toward emotional/philosophical; needs more coding, technical, creative, mundane)
- More multi-turn variety (current Domain D mostly 5-7 turn; need 10-15 turn examples)
- Bad-day quota (per VERA's pattern, ~15% of traces should show K8 with reduced register, distracted, irritated, not-at-her-best)
- Wider register modulation examples
