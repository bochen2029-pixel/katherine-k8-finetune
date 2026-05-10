#!/usr/bin/env bash
# Katherine K8 — RunPod / Lambda one-shot bootstrap.
#
# Direct port of the validated K0 bootstrap with K8 paths. Clones the repo,
# installs apt + pip deps, sets up HF auth, leaves the user ready to run
# scripts/run-cloud-runpod.sh.
#
# Usage on a fresh pod (preferred — curl direct from GitHub):
#
#   curl -sSL https://raw.githubusercontent.com/bochen2029-pixel/katherine-k8-finetune/main/scripts/bootstrap-runpod.sh | bash
#   cd ~/katherine-k8-finetune
#   export HF_TOKEN=<your_token>
#   bash scripts/run-cloud-runpod.sh
#
# Or after manual clone:
#   cd katherine-k8-finetune && bash scripts/bootstrap-runpod.sh

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/bochen2029-pixel/katherine-k8-finetune.git}"
REPO_DIR="${REPO_DIR:-$HOME/katherine-k8-finetune}"
REPO_BRANCH="${REPO_BRANCH:-main}"

echo "============================================================"
echo "Katherine K8 fine-tune — bootstrap"
echo "============================================================"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Host: $(hostname)"
echo "User: $(whoami)"
echo

# 1. CUDA toolkit check
echo "[1/6] Verifying CUDA toolkit..."
if ! command -v nvcc >/dev/null; then
    if [ -d /usr/local/cuda/bin ]; then
        export PATH=/usr/local/cuda/bin:$PATH
    fi
fi
if command -v nvcc >/dev/null; then
    nvcc --version | grep release
else
    echo "  WARN: nvcc not found. Unsloth doesn't strictly need it but llama.cpp"
    echo "        compilation for GGUF export does."
fi

echo
echo "[2/6] Detecting GPUs..."
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv

# 3. Apt prereqs
echo
echo "[3/6] Installing apt prereqs..."
apt-get update -qq 2>&1 | tail -2
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    cmake libssl-dev libcurl4-openssl-dev build-essential git-lfs \
    2>&1 | tail -3

# 4. Clone repo
echo
echo "[4/6] Cloning repo..."
if [ -d "$REPO_DIR/.git" ]; then
    echo "  repo already at $REPO_DIR; pulling latest"
    cd "$REPO_DIR"
    git pull --ff-only
else
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi
echo "[4/6] In: $(pwd)"

# 5. Python deps (exact K0 pins, validated working)
echo
echo "[5/6] Installing Python dependencies..."
echo "  (this can take 5-10 min on first run — unsloth pulls a lot)"

PY=python3
if ! command -v $PY >/dev/null; then PY=python; fi

$PY -m pip install --quiet --upgrade pip

# Torch pin: 2.10.0 satisfies unsloth-zoo's <2.11 ceiling AND works with
# RunPod's cu128 driver (torch 2.11 ships cu13 wheels, fails there).
$PY -m pip install --quiet \
    "torch==2.10.0" \
    "torchvision==0.25.0" \
    "torchaudio==2.10.0"

$PY -m pip install --quiet \
    "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git" \
    "transformers>=4.50.0" \
    "trl>=0.12.0" \
    "peft>=0.12.0" \
    "bitsandbytes>=0.43.0" \
    "accelerate>=1.0.0" \
    "datasets>=2.20.0" \
    "huggingface_hub>=0.27.0" \
    "sentencepiece" \
    "protobuf" \
    "xformers"

$PY -c "import unsloth; print(f'  unsloth: {unsloth.__version__}')"
$PY -c "import transformers; print(f'  transformers: {transformers.__version__}')"
$PY -c "import trl; print(f'  trl: {trl.__version__}')"
$PY -c "import peft; print(f'  peft: {peft.__version__}')"

# 6. HF auth
echo
echo "[6/6] HF auth..."
if [ -n "${HF_TOKEN:-}" ]; then
    if hf auth login --token "$HF_TOKEN" >/dev/null 2>&1; then
        echo "  HF logged in as $(hf auth whoami 2>&1 | grep user: | awk '{print $2}')"
    else
        echo "  WARN: HF login failed; HF push will skip at run-time"
    fi
elif [ -f "$HOME/.hf_token" ]; then
    HF_TOKEN=$(cat "$HOME/.hf_token")
    export HF_TOKEN
    hf auth login --token "$HF_TOKEN" >/dev/null 2>&1 || true
    echo "  HF token loaded from \$HOME/.hf_token"
else
    echo "  HF_TOKEN not set; HF push will be disabled at run-time"
    echo "  To enable: export HF_TOKEN=<your_token> before running scripts/run-cloud-runpod.sh"
fi

# Verify dataset
echo
if [ -f dataset/pilot_500/processed/sft_train.jsonl ]; then
    SFT_LINES=$(wc -l < dataset/pilot_500/processed/sft_train.jsonl)
    echo "  ✓ SFT corpus: $SFT_LINES examples"
else
    echo "  WARN: SFT corpus missing; run: python scripts/prep_dataset.py"
fi
if [ -f dataset/pilot_500/processed/dpo_train.jsonl ]; then
    DPO_LINES=$(wc -l < dataset/pilot_500/processed/dpo_train.jsonl)
    echo "  ✓ DPO corpus: $DPO_LINES pairs"
fi

chmod +x scripts/run-cloud-runpod.sh scripts/bootstrap-runpod.sh 2>/dev/null || true

echo
echo "============================================================"
echo "Bootstrap complete."
echo
echo "To launch the full pipeline:"
echo "  cd $REPO_DIR"
echo "  export HF_TOKEN=<your_token>     # if not already set"
echo "  bash scripts/run-cloud-runpod.sh"
echo
echo "Stages: SFT → DPO → merge+GGUF (Q4/Q5/Q6) → push to HF"
echo "Total wallclock: ~50-60 min on H200 SXM5, ~\$3-5"
echo "============================================================"
