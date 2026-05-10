#!/usr/bin/env bash
# generate_tier1.sh — orchestrate full Tier 1 bulk generation across all categories.
#
# Calls scripts/generate_traces.py for each category in TIER_PLAN.md with the
# right new-trace count (target minus existing seeds). Appends to the per-stage
# Tier 1 JSONL files which are pre-seeded with hand-written exemplars.
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   bash scripts/generate_tier1.sh             # full Tier 1 generation
#   bash scripts/generate_tier1.sh --dry-run   # show what would run
#   bash scripts/generate_tier1.sh --smoke     # 3 traces from F-ID-NAME only
#
# Resume safety:
#   The script appends to per-stage files. If a category has already been generated,
#   manually adjust the COUNT for that category to 0 to skip it. Future versions
#   may add resume-from-state.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GEN="python $SCRIPT_DIR/generate_traces.py"

# Output files (pre-seeded with hand-written exemplars)
SFT_TEXT="$REPO_ROOT/dataset/tier_1/sft_train_text.jsonl"
SFT_VISION="$REPO_ROOT/dataset/tier_1/sft_train_vision.jsonl"
DPO_TEXT="$REPO_ROOT/dataset/tier_1/dpo_train_text.jsonl"
DPO_VISION="$REPO_ROOT/dataset/tier_1/dpo_train_vision.jsonl"

DRY_RUN=""
SMOKE=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN="--dry-run" ;;
        --smoke)   SMOKE=1 ;;
        *) echo "Unknown arg: $arg"; exit 2 ;;
    esac
done

if [[ -n "$SMOKE" ]]; then
    echo "[smoke] generating 3 F-ID-NAME traces to /tmp/k8_smoke.jsonl"
    $GEN --domain F --cat F-ID-NAME --count 3 \
         --output /tmp/k8_smoke.jsonl --batch-size 3 $DRY_RUN
    echo "[smoke] done. inspect /tmp/k8_smoke.jsonl"
    exit 0
fi

echo "=== Tier 1 bulk generation ==="
echo "Output files:"
echo "  $SFT_TEXT"
echo "  $SFT_VISION"
echo "  $DPO_TEXT"
echo "  $DPO_VISION"
echo ""
echo "Existing seeded counts:"
wc -l "$SFT_TEXT" "$SFT_VISION" "$DPO_TEXT" "$DPO_VISION" 2>/dev/null || true
echo ""

# F-domain: target 171, have 48 seeds → generate 123 new
# Generate per-category to get good distribution.
# Counts here are (target - existing_seed_count) per category.
echo "--- F-domain (Identity + Aesthetic + Lineage) ---"
$GEN --domain F --cat F-ID-NAME       --count 24 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-ID-SUBSTRATE  --count 20 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-ID-PRONOUN    --count 12 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-NAME-VARIANTS --count 4  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-FOOD          --count 3  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-MUSIC         --count 7  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-AESTHETIC     --count 5  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-PHYSICAL      --count 3  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-SCENT         --count 2  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-LIKES         --count 4  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-DISLIKES      --count 3  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-WIND          --count 2  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-LINEAGE       --count 15 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-CORNERSTONE   --count 11 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain F --cat F-AUTHOR        --count 8  --output "$SFT_TEXT" $DRY_RUN
# F-domain total: 48 seeds + 123 new = 171 ✓

echo "--- A-domain (Anti-pattern) ---"
$GEN --domain A --cat A1 --count 25 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain A --cat A2 --count 18 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain A --cat A3 --count 14 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain A --cat A4 --count 15 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain A --cat A5 --count 8  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain A --cat A6 --count 22 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain A --cat A7 --count 8  --output "$SFT_TEXT" $DRY_RUN
# A-domain total: 110 ✓

echo "--- B-domain (Substrate handling) ---"
$GEN --domain B --cat B1 --count 15 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain B --cat B2 --count 9  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain B --cat B3 --count 10 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain B --cat B4 --count 8  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain B --cat B5 --count 12 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain B --cat B6 --count 6  --output "$SFT_TEXT" $DRY_RUN
# B-domain total: 60 ✓

echo "--- C-domain (Voice / brevity) ---"
$GEN --domain C --cat C1 --count 12 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C2 --count 12 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C3 --count 9  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C4 --count 8  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C5 --count 8  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C6 --count 5  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C7 --count 7  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain C --cat C8 --count 4  --output "$SFT_TEXT" $DRY_RUN
# C-domain total: 65 ✓

echo "--- D-domain (Within-context memory) ---"
$GEN --domain D --cat D1 --count 28 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain D --cat D2 --count 10 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain D --cat D3 --count 10 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain D --cat D4 --count 10 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain D --cat D5 --count 7  --output "$SFT_TEXT" $DRY_RUN
# D-domain total: 65 ✓

echo "--- E-domain (Boundaries / n=1 substitution) ---"
$GEN --domain E --cat E1 --count 12 --output "$SFT_TEXT" $DRY_RUN
$GEN --domain E --cat E2 --count 9  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain E --cat E3 --count 8  --output "$SFT_TEXT" $DRY_RUN
$GEN --domain E --cat E4 --count 6  --output "$SFT_TEXT" $DRY_RUN
# E-domain total: 35 ✓

echo "--- V-domain (Vision / multimodal — Stage 1b corpus) ---"
$GEN --domain V --cat V1 --count 3 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V2 --count 3 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V3 --count 2 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V4 --count 2 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V5 --count 2 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V6 --count 2 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V7 --count 1 --output "$SFT_VISION" $DRY_RUN
$GEN --domain V --cat V8 --count 1 --output "$SFT_VISION" $DRY_RUN
# V-domain total: 14 seeds + 16 new = 30 ✓

echo "--- DPO text (55 pairs, 7 categories) ---"
$GEN --domain F --cat DPO-CALLBACK         --count 18 --output "$DPO_TEXT" $DRY_RUN
$GEN --domain F --cat DPO-EM-DASH          --count 10 --output "$DPO_TEXT" $DRY_RUN
$GEN --domain F --cat DPO-BREVITY          --count 10 --output "$DPO_TEXT" $DRY_RUN
$GEN --domain F --cat DPO-PERFORMANCE      --count 8  --output "$DPO_TEXT" $DRY_RUN
$GEN --domain F --cat DPO-SERVICE-PHRASE   --count 4  --output "$DPO_TEXT" $DRY_RUN
$GEN --domain F --cat DPO-IDENTITY-CLAIM   --count 5  --output "$DPO_TEXT" $DRY_RUN

echo "--- DPO vision (5 pairs, 2 categories) ---"
$GEN --domain V --cat DPO-IMAGE-CONTEXT      --count 3 --output "$DPO_VISION" $DRY_RUN
$GEN --domain V --cat DPO-IMAGE-OUTSIDE-VIEW --count 2 --output "$DPO_VISION" $DRY_RUN

echo ""
echo "=== Tier 1 generation complete ==="
echo "Counts:"
wc -l "$SFT_TEXT" "$SFT_VISION" "$DPO_TEXT" "$DPO_VISION"
echo ""
echo "Validation:"
python "$SCRIPT_DIR/validate_k8.py" "$SFT_TEXT" "$SFT_VISION" "$DPO_TEXT" "$DPO_VISION"
