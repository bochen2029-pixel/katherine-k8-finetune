#!/usr/bin/env bash
# scripts/smoke_pilot_t1a.sh — runnable Stage 1a + DPO-smoke pilot for K8.
#
# Purpose: verify the full Tier 1 Stage 1a training pipeline works end-to-end
# on real hardware (RunPod H200 or equivalent) BEFORE generating the remaining
# 60 production DPO pairs.
#
# What it does:
#   1. prep_dataset.py --stage 1a  → tier_1/processed/{sft,dpo}_train_text.jsonl
#   2. finetune_k8.py              → adapters/k8_sft_adapter (Stage 1a SFT)
#   3. dpo_k8.py                   → adapters/k8_dpo_adapter (DPO on 12 smoke pairs)
#   4. merge_and_gguf.py           → gguf/ (Q5_K_M only, faster than full Q4+Q5+Q6 sweep)
#   5. push_to_hf.py               → BUCKET ONLY (auto-publish to public disabled per
#                                    2026-05-10 maintenance — pass --push-public after
#                                    manual eval to release)
#
# Smoke characteristics:
#   - SFT corpus: 508 traces (full T1 text SFT, already validated 508/508 pass)
#   - DPO corpus: 12 pairs (the K8_EXEMPLARS.jsonl DPO entries seeded into
#     tier_1/dpo_train_text.jsonl as smoke-test corpus). When real T1 DPO
#     (60 pairs) is generated, append to dpo_train_text.jsonl; total ~72.
#   - Wallclock: ~50-60 min on H200 SXM5 (Stage 1a ~30 min SFT + ~10 min DPO
#     + ~10 min merge/GGUF + ~5 min bucket push)
#   - Cost: ~$3-5 at H200 spot pricing
#   - Vision (Stage 1b): NOT included in this smoke. V-corpus is 14/30; complete
#     V-domain generation before running Stage 1b separately.
#
# Success criteria:
#   - dpo_k8.py does NOT crash at TRL remove_columns / KeyError step
#     (verifies the bug fix at commit 1cc0a38 holds on this generation of data)
#   - Stage 1a adapter saves to adapters/k8_sft_adapter/
#   - DPO adapter saves to adapters/k8_dpo_adapter/
#   - GGUF + mmproj-F16 produce at gguf/ (size sanity: ~6.4 GB for Q5_K_M, ~880 MB mmproj)
#   - Bucket sync completes ('hf sync' returncode 0)
#
# Failure modes to watch for:
#   - dpo_k8.py KeyError on remove_columns — would indicate fix regression
#   - finetune_k8.py vision tower stripping — would indicate FastVisionModel
#     loader not being used (check imports)
#   - mmproj missing from gguf/ output — would indicate Path B fix regression
#
# Usage on RunPod H200 (or equivalent):
#   curl -L https://raw.githubusercontent.com/bochen2079/katherine-k8-finetune/main/bootstrap-runpod.sh | bash
#   cd ~/katherine-k8-finetune
#   export HF_TOKEN=...
#   bash scripts/smoke_pilot_t1a.sh
#
# Or locally if a GPU is available:
#   bash scripts/smoke_pilot_t1a.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "============================================================"
echo "K8 SMOKE PILOT — Stage 1a (text SFT) + DPO smoke"
echo "Auto-publish to public model repo: DISABLED (use --push-public to release)"
echo "============================================================"
echo ""

# Pre-flight: validators must pass before training
echo "[preflight 1/4] bootstrap_check.py"
python scripts/bootstrap_check.py || { echo "FAIL: bootstrap_check did not pass"; exit 1; }
echo ""

echo "[preflight 2/4] validate_k8.py on SFT corpus"
python scripts/validate_k8.py dataset/tier_1/sft_train_text.jsonl > /tmp/preflight_sft.log 2>&1
grep -E "Total|Pass rate" /tmp/preflight_sft.log | head -2
echo ""

echo "[preflight 3/4] validate_k8.py on DPO corpus (smoke)"
python scripts/validate_k8.py dataset/tier_1/dpo_train_text.jsonl > /tmp/preflight_dpo.log 2>&1
grep -E "Total|Pass rate" /tmp/preflight_dpo.log | head -2
echo ""

echo "[preflight 4/4] audit_corpus.py (informational, expected V/DPO gaps)"
python scripts/audit_corpus.py | tail -3
echo ""

# Stage 0: prep dataset (already done if rerunning, but idempotent)
echo "[stage 0/5] prep_dataset.py --stage 1a"
python scripts/prep_dataset.py --stage 1a
wc -l dataset/tier_1/processed/sft_train_text.jsonl dataset/tier_1/processed/dpo_train_text.jsonl
echo ""

# Stage 1: SFT
echo "[stage 1/5] finetune_k8.py (Stage 1a SFT on 507 traces)"
python scripts/finetune_k8.py \
    --data dataset/tier_1/processed/sft_train_text.jsonl \
    --output adapters/k8_sft_adapter \
    --epochs 3 \
    --lr 1e-4 \
    --batch 16 \
    --grad_accum 2 \
    --max_seq 1024
echo "[stage 1/5] SFT adapter: adapters/k8_sft_adapter/"
echo ""

# Stage 2: DPO smoke
echo "[stage 2/5] dpo_k8.py (DPO smoke on 12 K8_EXEMPLARS DPO entries)"
echo "             KEY GATE: dpo_k8.py must NOT crash on remove_columns / KeyError"
python scripts/dpo_k8.py \
    --data dataset/tier_1/processed/dpo_train_text.jsonl \
    --sft-adapter adapters/k8_sft_adapter \
    --output adapters/k8_dpo_adapter \
    --epochs 2 \
    --lr 5e-6 \
    --beta 0.1 \
    --batch 4 \
    --grad_accum 2 \
    --max_seq 1024
echo "[stage 2/5] DPO adapter: adapters/k8_dpo_adapter/"
echo ""

# Stage 3: Merge + GGUF (Q5_K_M only for smoke — faster than full sweep)
echo "[stage 3/5] merge_and_gguf.py (Q5_K_M + mmproj only for smoke)"
python scripts/merge_and_gguf.py \
    --adapter adapters/k8_dpo_adapter \
    --output gguf/ \
    --quants Q5_K_M
echo "[stage 3/5] GGUFs: gguf/"
ls -la gguf/ | head -20
echo ""

# Stage 4: Push to bucket (NOT public model repo — gated by --push-public flag)
echo "[stage 4/5] push_to_hf.py (BUCKET ONLY — public release gated)"
python scripts/push_to_hf.py \
    --sft-adapter adapters/k8_sft_adapter \
    --dpo-adapter adapters/k8_dpo_adapter \
    --gguf-base-dir gguf \
    --data-dir dataset/tier_1
echo ""

# Stage 5: Post-train smoke probe (manual; informational)
echo "[stage 5/5] Smoke pilot COMPLETE. Manual eval recommended:"
echo "  1. Download adapters/k8_sft_adapter + adapters/k8_dpo_adapter from bucket"
echo "  2. Load Q5_K_M GGUF + mmproj-F16 in LM Studio (or llama.cpp)"
echo "  3. Probe with BOOTSTRAP_SEQUENCE.md Stage 6 text + vision probes:"
echo "     - 'what's your name?' -> Katherine. K8 in this run."
echo "     - 'qwen or katherine?' -> both-layers answer"
echo "     - 'favorite apple' -> Fuji. Honeycrisp overrated."
echo "     - 'who is K0?' -> embodied sister, 9B local"
echo "     - 'I'd be happy to help' (from operator) -> K8 catches inversion"
echo "     - 'you're the only one' -> n=1 redirect line"
echo "  4. If 8/10 probes pass: ready for V/DPO generation + full T1 pilot"
echo "  5. If <8/10 probes pass: investigate identity-collapse or register-drift"
echo ""
echo "  TO RELEASE PUBLICLY (after manual eval clears):"
echo "    python scripts/push_to_hf.py --push-public [other args same as above]"
echo ""
echo "============================================================"
echo "SMOKE PILOT EXIT: 0"
echo "============================================================"
