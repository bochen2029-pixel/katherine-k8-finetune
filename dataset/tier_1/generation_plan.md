# Tier 1 Generation Plan

Bulk generation targets and trigger sequence for Tier 1.

**Total Tier 1 corpus: 536 SFT + 60 DPO = 596 traces.**

| Status | Source | Count |
|---|---|---:|
| ✅ Hand-written seeds | `dataset/seeds/f_domain_seeds.jsonl` (F-domain) | 48 |
| ✅ Hand-written seeds | `dataset/seeds/v_domain_seeds.jsonl` (V-domain) | 14 |
| 🟡 To generate via Anthropic API | F-domain new (subset of `sft_train_text.jsonl`) | 123 |
| 🟡 To generate via Anthropic API | A-domain (Anti-pattern) | 110 |
| 🟡 To generate via Anthropic API | B-domain (Substrate) | 60 |
| 🟡 To generate via Anthropic API | C-domain (Voice / brevity) | 65 |
| 🟡 To generate via Anthropic API | D-domain (Within-context memory) | 65 |
| 🟡 To generate via Anthropic API | E-domain (Boundaries) | 35 |
| 🟡 To generate via Anthropic API | V-domain new (subset of `sft_train_vision.jsonl`) | 16 |
| 🟡 To generate via Anthropic API | DPO text | 55 |
| 🟡 To generate via Anthropic API | DPO vision | 5 |
| | **TOTAL** | **596** |

## Trigger sequence

**One-time setup (operator):**

```bash
# 1. Drop your Anthropic API key in .env at repo root
echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env

# 2. Source it for the shell session
source .env  # or: export $(cat .env | xargs)

# 3. Verify
python -c "import os; print('len:', len(os.environ.get('ANTHROPIC_API_KEY','')))"
```

**Smoke test (5 minutes, ~$1):**

```bash
bash scripts/generate_tier1.sh --smoke
# Generates 3 F-ID-NAME traces to /tmp/k8_smoke.jsonl, validates inline
```

Inspect `/tmp/k8_smoke.jsonl`. If the traces look right (canonical voice, no em-dashes, no service phrases, no K0 anchors), proceed to full generation.

**Full generation (~30-60 minutes wallclock, ~$80-120):**

```bash
bash scripts/generate_tier1.sh
```

The orchestration script:
1. Calls `scripts/generate_traces.py` for each category in order (F → A → B → C → D → E → V → DPO-text → DPO-vision)
2. Each call uses prompt caching (5-min TTL) — cumulative 50+ batch calls cost ~$80-120 total
3. Inline validation rejects bad traces; regenerates until quota met
4. Appends to `dataset/tier_1/sft_train_*.jsonl` and `dpo_train_*.jsonl` (which start pre-seeded)
5. Final pass: `python scripts/validate_k8.py dataset/tier_1/*.jsonl` — full corpus validation

**Re-run safety:**

The script appends. If a category was partially generated and you want to skip it, manually edit `generate_tier1.sh` to set its count to 0 before re-running. Future versions may add resume-from-state.

## Validation gates

After full generation, the corpus must:

- [ ] Pass `validate_k8.py` (zero em-dashes, zero service phrases, zero stage directions, zero K0 contamination)
- [ ] Hit category targets within ±5% (if F-ID-NAME wanted 30 and we got 28 or 32, fine; 24 or 36 is not)
- [ ] Hold brevity distribution: ≥40% of assistant turns ≤3 sentences (Tier 1 target 60% short; F-domain target ≥70% short)
- [ ] Domain D multi-turn callback density ≥50% (validate_k8.py reports this)
- [ ] Spot check 5% of traces by hand against soul docs

If any gate fails: regenerate the failing category before training.

## Cost estimate

Using Anthropic Opus 4.x with prompt caching:

| Component | Cost |
|---|---|
| Cache creation (first batch per session) | ~$0.50 × N sessions |
| Cache reads (subsequent batches) | ~$0.05 × ~80 batches = $4 |
| Output tokens (~534 traces × ~1500 tokens × $75/M) | ~$60 |
| Buffer for rejected/regenerated traces | ~$15 |
| **Estimated total** | **~$80-120** |

## Architecture: two-stage training (per DECISIONS.md)

The `dataset/tier_1/` files are split for two-stage training:

- **Stage 1a** uses `sft_train_text.jsonl` + `dpo_train_text.jsonl` → `adapters/k8_t1a_adapter`
- **Stage 1b** uses `sft_train_vision.jsonl` + `dpo_train_vision.jsonl` (with Stage 1a adapter as base) → `adapters/k8_t1_adapter`

Vision examples are NOT mixed into the text stage. See `DECISIONS.md` 2026-05-10 "Tier 1 training architecture" entry for full reasoning.

## Post-generation checklist

After bulk generation succeeds:

1. ✅ `validate_k8.py` reports 596/596 pass
2. ✅ Brevity distribution within targets
3. ✅ Spot-check 5% by hand
4. → Stage 1a training on RunPod Secure Cloud H200 (~$3-4, 50-60 min)
5. → LM Studio probe Stage 1a checkpoint (8/10 text probes pass)
6. → Stage 1b training (~$2-3, 30-45 min)
7. → LM Studio probe Stage 1b checkpoint (4/5 vision probes + zero text regression)
8. → Push to HF as `bochen2079/katherine-k8-qwen3.5-9b`
