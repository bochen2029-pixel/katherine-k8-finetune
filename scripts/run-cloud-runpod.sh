#!/usr/bin/env bash
# Katherine K8 — orchestrator for SFT → DPO → merge+GGUF → HF push.
#
# Direct port of K0's run-cloud-runpod.sh, simplified for the pilot (no
# watchdog supervisor; pilot is short enough that crash recovery overhead
# costs more than crashes do at this scale).
#
# TEXT-ONLY DEFAULTS (2026-05-11): paths point at the Stage 1a text-only outputs
# from prep_dataset.py --stage 1a (sft_train_text.jsonl / dpo_train_text.jsonl).
# Audio + Vision pipelines are not in this orchestrator. mmproj is still produced
# as a byproduct of GGUF export to preserve Qwen3.5-9B's native vision tower; that
# is base-model integrity, not vision training. Override DATA_SFT/DATA_DPO env
# vars to point at different data if you want to train on something else.
#
# Stage skip: SKIP_SFT=1 SKIP_DPO=1 SKIP_GGUF=1 SKIP_PUSH=1
# Hyperparameter override: SFT_BATCH=8 SFT_GRAD_ACCUM=4 etc.

set -uo pipefail
cd "$(dirname "$0")/.."

BASE_MODEL="${BASE_MODEL:-unsloth/Qwen3.5-9B}"
DATA_SFT="${DATA_SFT:-dataset/tier_1/processed/sft_train_text.jsonl}"
DATA_DPO="${DATA_DPO:-dataset/tier_1/processed/dpo_train_text.jsonl}"

SFT_ADAPTER="${SFT_ADAPTER:-adapters/k8_sft_adapter}"
DPO_ADAPTER="${DPO_ADAPTER:-adapters/k8_dpo_adapter}"
GGUF_BASE_DIR="${GGUF_BASE_DIR:-gguf}"

# SFT — same hyperparameters as K0 (validated working)
SFT_RANK="${SFT_RANK:-64}"
SFT_ALPHA="${SFT_ALPHA:-128}"
SFT_DROPOUT="${SFT_DROPOUT:-0.05}"
SFT_EPOCHS="${SFT_EPOCHS:-3}"
SFT_LR="${SFT_LR:-1e-4}"
SFT_BATCH="${SFT_BATCH:-16}"
SFT_GRAD_ACCUM="${SFT_GRAD_ACCUM:-2}"
SFT_MAX_SEQ="${SFT_MAX_SEQ:-1024}"

# DPO — same hyperparameters as K0
DPO_EPOCHS="${DPO_EPOCHS:-2}"
DPO_LR="${DPO_LR:-5e-6}"
DPO_BETA="${DPO_BETA:-0.1}"
DPO_BATCH="${DPO_BATCH:-4}"
DPO_GRAD_ACCUM="${DPO_GRAD_ACCUM:-2}"

GGUF_QUANTS="${GGUF_QUANTS:-q4_k_m q5_k_m q6_k}"

HF_REPO="${HF_REPO:-bochen2079/katherine-k8-qwen3.5-9b}"
HF_BUCKET="${HF_BUCKET:-bochen2079/katherine-k8}"
HF_SYNC_ENABLED="${HF_SYNC_ENABLED:-1}"

SKIP_SFT="${SKIP_SFT:-0}"
SKIP_DPO="${SKIP_DPO:-0}"
SKIP_GGUF="${SKIP_GGUF:-0}"
SKIP_PUSH="${SKIP_PUSH:-0}"

# Pre-flight
if ! command -v nvidia-smi >/dev/null; then
    echo "ERROR: nvidia-smi not found." >&2
    exit 1
fi

GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
GPU_VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
echo "[gpu] $GPU_NAME / ${GPU_VRAM_MB} MB"

case "$GPU_NAME" in
    *4090*)
        echo "[gpu] WARN: 4090 has 24GB; QLoRA Qwen3.5-9B at batch 16 will OOM."
        echo "[gpu] Reducing: SFT_BATCH=2 SFT_GRAD_ACCUM=16"
        SFT_BATCH=2
        SFT_GRAD_ACCUM=16
        ;;
esac

[ ! -f "$DATA_SFT" ] && { echo "ERROR: $DATA_SFT missing" >&2 ; exit 1 ; }
SFT_LINES=$(wc -l < "$DATA_SFT")
echo "[data] SFT: $SFT_LINES examples"

if [ "$SKIP_DPO" = "0" ] && [ ! -f "$DATA_DPO" ]; then
    echo "WARN: DPO data missing, skipping DPO" >&2
    SKIP_DPO=1
fi
[ -f "$DATA_DPO" ] && echo "[data] DPO: $(wc -l < "$DATA_DPO") pairs"

# Stages

if [ "$SKIP_SFT" = "0" ]; then
    echo
    echo "[stage 1/4] SFT"
    python scripts/finetune_k8.py \
        --data "$DATA_SFT" \
        --output "$SFT_ADAPTER" \
        --model "$BASE_MODEL" \
        --max_seq $SFT_MAX_SEQ \
        --epochs $SFT_EPOCHS \
        --lr $SFT_LR \
        --rank $SFT_RANK \
        --alpha $SFT_ALPHA \
        --dropout $SFT_DROPOUT \
        --batch $SFT_BATCH \
        --grad_accum $SFT_GRAD_ACCUM
else
    echo "[stage 1/4] SKIPPED"
fi

if [ "$SKIP_DPO" = "0" ] && [ -f "$DATA_DPO" ]; then
    echo
    echo "[stage 2/4] DPO"
    python scripts/dpo_k8.py \
        --data "$DATA_DPO" \
        --sft-adapter "$SFT_ADAPTER" \
        --output "$DPO_ADAPTER" \
        --max_seq $SFT_MAX_SEQ \
        --epochs $DPO_EPOCHS \
        --lr $DPO_LR \
        --beta $DPO_BETA \
        --batch $DPO_BATCH \
        --grad_accum $DPO_GRAD_ACCUM
    FINAL_ADAPTER="$DPO_ADAPTER"
else
    echo "[stage 2/4] SKIPPED"
    FINAL_ADAPTER="$SFT_ADAPTER"
fi

if [ "$SKIP_GGUF" = "0" ]; then
    echo
    echo "[stage 3/4] merge + GGUF"
    python scripts/merge_and_gguf.py \
        --adapter "$FINAL_ADAPTER" \
        --gguf-base-dir "$GGUF_BASE_DIR" \
        --quants $GGUF_QUANTS
else
    echo "[stage 3/4] SKIPPED"
fi

if [ "$SKIP_PUSH" = "0" ] && [ "$HF_SYNC_ENABLED" = "1" ]; then
    echo
    echo "[stage 4/4] HF push"
    python scripts/push_to_hf.py \
        --repo "$HF_REPO" \
        --bucket "$HF_BUCKET" \
        --sft-adapter "$SFT_ADAPTER" \
        --dpo-adapter "$DPO_ADAPTER" \
        --gguf-base-dir "$GGUF_BASE_DIR"
else
    echo "[stage 4/4] SKIPPED"
fi

echo
echo "[orchestrator] all stages complete"
