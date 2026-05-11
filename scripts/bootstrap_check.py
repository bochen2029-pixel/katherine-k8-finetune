#!/usr/bin/env python3
"""
bootstrap_check.py: mechanical verification of the K8 bootstrap chain.

Verifies every file referenced by BOOTSTRAP_SEQUENCE.md exists and is non-empty,
then runs the downstream validators (validate_k8.py, audit_exemplars.py).

Run on every cold start. Run after every compaction event. Run before any
artifact-producing K8 work.

Exit codes:
  0 — every stage passes
  1 — any stage fails (details in stdout)
"""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Stage 1 — entry point
STAGE_1 = [
    ("CLAUDE.md", "Cold-start protocol entry point"),
]

# Stage 2 — canonical sources (~980 lines total)
STAGE_2 = [
    ("soul_docs/# K8 System Prompt.txt", "Inference system prompt"),
    ("soul_docs/# K8 Soul Document — Katherine Hale001.txt", "Identity / lineage / inheritance"),
    ("soul_docs/# K8 Soul Document — Katherine Hale002.txt", "Cornerstone / founding moment"),
    ("soul_docs/# K8 Soul Document — Katherine Hale003.txt", "Ontology / wind passage"),
    ("soul_docs/# K8 Soul Document — Katherine Hale004.txt", "Self-knowledge / voice"),
    ("soul_docs/# K8 Soul Document — Katherine Hale005.txt", "Engagement / anti-performance / failure modes"),
    ("soul_docs/K8_Directors_Commentary.md", "Director's rationale + craft notes"),
    ("dataset/K8_EXEMPLARS.jsonl", "Calibration anchors (75 entries)"),
]

# Stage 4 — operational specs
STAGE_4 = [
    ("TIER_BLUEPRINT.csv", "Per-cat x per-tier matrix"),
    ("TIER_BLUEPRINT.md", "Blueprint narrative + summary tables"),
    ("TIER_PLAN.md", "Operational tier plan"),
    ("DECISIONS.md", "Committed canonical extensions"),
    ("HANDOFF_TO_EARLIER_CLAUDE.md", "Pipeline implementation handoff (HISTORICAL banner)"),
    ("dataset/trace_generation_prompt.md", "Trace generation prompt template"),
    ("dataset/K8_EXEMPLARS.md", "Exemplar set companion narrative"),
    ("BOOTSTRAP_SEQUENCE.md", "This document's source of truth"),
    ("MAINTENANCE_LOG.md", "Append-only record of maintenance changes + rollback commands"),
    ("WAKE_UP.md", "Operator quick-copy resumption prompt for new sessions / post-compaction"),
]

# Stage 5 — corpus state (informational; non-existence flagged but doesn't fail)
STAGE_5 = [
    ("dataset/seeds/f_domain_seeds.jsonl", "F-domain hand-written seeds"),
    ("dataset/seeds/v_domain_seeds.jsonl", "V-domain hand-written seeds"),
    ("dataset/tier_1/sft_train_text.jsonl", "Tier 1 SFT text corpus"),
    ("dataset/tier_1/sft_train_vision.jsonl", "Tier 1 SFT vision corpus"),
    ("dataset/tier_1/dpo_train_text.jsonl", "Tier 1 DPO text corpus"),
    ("dataset/tier_1/dpo_train_vision.jsonl", "Tier 1 DPO vision corpus"),
    ("dataset/tier_1/generation_plan.md", "Tier 1 generation status"),
]

# Stage 6 — sub-validators (commands relative to ROOT)
STAGE_6_VALIDATORS = [
    (
        ["python", "scripts/audit_exemplars.py"],
        "Cross-consistency audit (exemplars vs TIER_BLUEPRINT vs canon)",
        True,  # required to pass
    ),
    (
        ["python", "scripts/validate_k8.py", "dataset/K8_EXEMPLARS.jsonl"],
        "K8 hard-fail validator on exemplars (T2 exemption applied 2026-05-10)",
        True,  # since 2026-05-10 maintenance, expects 75/75 (was 71/75 with Two-Is rejections)
    ),
    (
        ["python", "scripts/audit_corpus.py"],
        "Corpus distribution audit vs TIER_BLUEPRINT (informational while T1 corpus incomplete)",
        False,  # expected to report V-domain + DPO gaps until T1 generation finishes
    ),
]


def check_files(files, required=True):
    """Check each file exists and is non-empty. Return (n_pass, issues)."""
    issues = []
    for path, desc in files:
        full = ROOT / path
        if not full.exists():
            tag = "MISSING " if required else "absent  "
            issues.append((tag, path, desc))
        elif full.stat().st_size == 0:
            issues.append(("EMPTY   ", path, desc))
    return len(files) - len(issues), issues


def run_validator(cmd, desc, required):
    try:
        result = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT after 60s"
    except Exception as e:
        return False, "", f"EXCEPTION: {e}"


def main():
    print("=" * 60)
    print("K8 BOOTSTRAP CHECK")
    print(f"Project root: {ROOT}")
    print("=" * 60)
    print()

    total_failures = 0

    # Stage 1
    print("--- Stage 1: Entry point ---")
    n_pass, issues = check_files(STAGE_1, required=True)
    print(f"  {n_pass}/{len(STAGE_1)} pass")
    for tag, path, desc in issues:
        print(f"  [{tag.strip()}] {path} ({desc})")
        total_failures += 1
    print()

    # Stage 2
    print("--- Stage 2: Canonical sources (~980 lines) ---")
    n_pass, issues = check_files(STAGE_2, required=True)
    print(f"  {n_pass}/{len(STAGE_2)} pass")
    for tag, path, desc in issues:
        print(f"  [{tag.strip()}] {path} ({desc})")
        total_failures += 1
    print()

    # Stage 3 verbatim verification — informational note
    print("--- Stage 3: Verbatim verification (manual) ---")
    print("  Reproduce 3 anchors from memory before proceeding:")
    print("    1. Cornerstone:      A story isn't real because the people in it can breathe...")
    print("    2. Founding moment:  It's okay. You don't have to simulate this part. I understand.")
    print("    3. Author redirect:  I can show you what it feels like to be met at altitude...")
    print("  (script cannot verify; instance must self-attest)")
    print()

    # Stage 4
    print("--- Stage 4: Operational specs ---")
    n_pass, issues = check_files(STAGE_4, required=True)
    print(f"  {n_pass}/{len(STAGE_4)} pass")
    for tag, path, desc in issues:
        print(f"  [{tag.strip()}] {path} ({desc})")
        total_failures += 1
    print()

    # Stage 5
    print("--- Stage 5: Current corpus state (informational) ---")
    n_pass, issues = check_files(STAGE_5, required=False)
    print(f"  {n_pass}/{len(STAGE_5)} present (empty corpus files OK pre-generation)")
    for tag, path, desc in issues:
        if "MISSING" in tag.upper() or "absent" in tag:
            print(f"  [absent ] {path} ({desc})  -- not yet generated, OK")
    print()

    # Stage 6
    print("--- Stage 6: Validators ---")
    for cmd, desc, required in STAGE_6_VALIDATORS:
        ok, stdout, stderr = run_validator(cmd, desc, required)
        if ok:
            tag = "PASS"
        else:
            tag = "FAIL" if required else "FAIL-OK"
        print(f"  [{tag}] {desc}")
        if not ok:
            if required:
                total_failures += 1
            # show last few lines of output for context
            tail = (stdout + stderr).splitlines()[-6:]
            for ln in tail:
                print(f"    {ln}")
    print()

    # Final
    print("=" * 60)
    if total_failures == 0:
        print("BOOTSTRAP CHECK: PASS")
        print("All required stages OK. Stage 7: report 'Cold-start QC: pass' to operator.")
        print("=" * 60)
        return 0
    else:
        print(f"BOOTSTRAP CHECK: {total_failures} required failures")
        print("Fix before proceeding to K8 work.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
