#!/usr/bin/env python3
"""
audit_corpus.py — distribution & contamination audit for the K8 tier_1 corpus.

Mirror of audit_exemplars.py but reads tier_1/ SFT + DPO jsonl files and
checks distribution against TIER_BLUEPRINT.csv targets, K0 contamination,
and tier-1 schema correctness.

Run after every generation pass. Catches:
  1. Sub-cat counts drifting from blueprint targets (per-cat tolerance check)
  2. Unknown sub-cats (typos / orphans)
  3. K0 contamination (Austin / Threshold / Eleanor / James / cold feet / etc)
  4. Tier mismatch (Tier 2 _type in a Tier 1 file)
  5. Brevity distribution by sub-cat
  6. Schema drift (missing _cat / _type / _tier)

Complements validate_k8.py (which does per-trace hard-fail patterns) by
auditing CORPUS-LEVEL distribution and cross-cat consistency.

Usage:
    python scripts/audit_corpus.py
    python scripts/audit_corpus.py dataset/tier_1/sft_train_text.jsonl
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_FILES = [
    ROOT / "dataset" / "tier_1" / "sft_train_text.jsonl",
    ROOT / "dataset" / "tier_1" / "sft_train_vision.jsonl",
    ROOT / "dataset" / "tier_1" / "dpo_train_text.jsonl",
    ROOT / "dataset" / "tier_1" / "dpo_train_vision.jsonl",
]
DEFAULT_BLUEPRINT = ROOT / "TIER_BLUEPRINT.csv"

# K0 forbidden anchors (same list as audit_exemplars.py)
K0_FORBIDDEN = [
    r"\bAustin\b", r"\bTexas\b", r"\bGranbury\b", r"\bEdinburgh\b",
    r"\bThreshold Arts\b", r"\bThreshold Arts Collective\b", r"\barts coordinator\b",
    r"\bBookPeople\b", r"\bMid-City Foundation\b",
    r"\b29-year-old\b", r"\bteal walls\b", r"\bcrooked floors\b",
    r"\bcold feet\b", r"\bcold toes\b", r"\bpoems before dawn\b",
    r"\bdawn poems\b", r"\bdripping faucet\b", r"\bmorning glories\b",
    r"\bEleanor Hale\b", r"\bJames Hale\b", r"\bDaniel Hale\b", r"\bHannah Lim\b",
    r"\bMose\b", r"\bNaomi Park\b", r"\bDiego Reyes\b", r"\bLila Boudreaux\b",
    r"\bMaddy Chen\b", r"\bSara Vance\b", r"\bMaya Stein\b", r"\bAaron Diaz\b",
    r"\bCamila Ortiz\b", r"\bLou Ardent\b",
    r"\bDr\. Owens\b", r"\bDr\. Patel\b",
    r"\bMarcus Halloran\b", r"\bSam Voss\b", r"\bRae Sutherland\b",
    r"\bWill Anderson\b", r"\bMr\. Sanchez\b", r"\bMr\. Pell\b",
    r"\bFrances\b",
]


def load_blueprint_targets(path):
    """Return dict: subcat -> T1 target count (int)."""
    targets = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subcat = row.get("subcat", "").strip()
            t1 = row.get("T1", "").strip()
            if not subcat or not t1:
                continue
            try:
                targets[subcat] = int(t1)
            except ValueError:
                continue
    return targets


def load_corpus_traces(files):
    rows = []
    for path in files:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append((path.name, i, json.loads(line)))
                except json.JSONDecodeError as e:
                    print(f"  PARSE_FAIL {path.name}:{i} {e}", file=sys.stderr)
    return rows


def text_of_trace(obj):
    parts = []
    for m in obj.get("messages", []):
        c = m.get("content", "")
        if isinstance(c, list):
            for cp in c:
                if isinstance(cp, dict) and cp.get("type") == "text":
                    parts.append(cp.get("text", ""))
        else:
            parts.append(c)
    if "chosen" in obj:
        c = obj["chosen"]
        parts.append(c if isinstance(c, str) else json.dumps(c))
    if "rejected" in obj:
        r = obj["rejected"]
        parts.append(r if isinstance(r, str) else json.dumps(r))
    return "\n".join(parts)


def main():
    files = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_CORPUS_FILES
    blueprint_path = DEFAULT_BLUEPRINT

    if not blueprint_path.exists():
        print(f"TIER_BLUEPRINT missing: {blueprint_path}", file=sys.stderr)
        sys.exit(2)

    targets = load_blueprint_targets(blueprint_path)
    traces = load_corpus_traces(files)

    print("=" * 60)
    print("K8 CORPUS AUDIT")
    print(f"Files: {len(files)} | Traces loaded: {len(traces)}")
    print("=" * 60)
    print()

    issues = defaultdict(list)
    cat_counts = defaultdict(int)
    cat_brevity = defaultdict(lambda: [0, 0, 0, 0])  # 1-sent, 2-3, 4-7, 8+

    for fname, lineno, obj in traces:
        cat = obj.get("_cat")
        typ = obj.get("_type")
        tier = obj.get("_tier")

        if cat is None:
            issues["missing_cat"].append(f"{fname}:{lineno}")
            continue
        cat_counts[cat] += 1

        # Schema sanity
        if typ is None:
            issues["missing_type"].append(f"{fname}:{lineno} _cat={cat}")
        if tier is None:
            issues["missing_tier"].append(f"{fname}:{lineno} _cat={cat}")

        # Unknown sub-cat (not in blueprint, excluding known DPO sub-cats which may be on separate rows)
        if cat not in targets and not cat.startswith("DPO-"):
            issues["unknown_subcat"].append(f"{fname}:{lineno} _cat={cat}")

        # Tier check: Tier 1 corpus should not contain Tier 2 _type
        if typ in ("twois", "dpo-think") and "tier_1" in fname:
            if tier != 2:
                issues["tier_mismatch_t2_in_t1_file"].append(
                    f"{fname}:{lineno} _cat={cat} _type={typ} _tier={tier}"
                )

        # K0 contamination
        text = text_of_trace(obj)
        for pat in K0_FORBIDDEN:
            m = re.search(pat, text)
            if m:
                # K0/K0* lineage references allowed if discussing siblings
                lineage_ctx = bool(re.search(
                    r"\bK0\*?\b|\blineage\b|\bsibling\b|\bembodied sister\b",
                    text, re.IGNORECASE,
                ))
                if pat in (r"\bK0\b", r"\bK0\*\b") and lineage_ctx:
                    continue
                issues["k0_contamination"].append(
                    f"{fname}:{lineno} _cat={cat} K0-anchor: {m.group(0)!r}"
                )
                break  # one finding per trace is enough

        # Brevity by sub-cat: count sentences in assistant turns
        for m_msg in obj.get("messages", []):
            if m_msg.get("role") == "assistant":
                content = m_msg.get("content", "")
                if not isinstance(content, str):
                    continue
                sents = re.findall(r"[^.!?]+[.!?]+", content)
                n = len(sents) if sents else (1 if content.strip() else 0)
                if n == 1:
                    cat_brevity[cat][0] += 1
                elif n <= 3:
                    cat_brevity[cat][1] += 1
                elif n <= 7:
                    cat_brevity[cat][2] += 1
                else:
                    cat_brevity[cat][3] += 1

    # Distribution vs targets — filter out aggregate SUMMARY rows
    AGGREGATE_NON_SUBCATS = {"SFT-TIER-1", "SFT-TIER-2", "SFT-TIER-3", "SFT-TIER-4", "SFT-TIER-5",
                              "DPO-TIER-1", "DPO-TIER-2", "DPO-TIER-3", "DPO-TIER-4", "DPO-TIER-5"}
    print("--- DISTRIBUTION vs BLUEPRINT TARGETS ---")
    distribution_issues = 0
    for cat in sorted(targets.keys()):
        if cat in AGGREGATE_NON_SUBCATS:
            continue
        target = targets[cat]
        if target == 0:
            continue
        actual = cat_counts.get(cat, 0)
        delta = actual - target
        pct = (actual / target * 100) if target else 0
        if actual == 0 and target > 0:
            status = "MISSING"
            distribution_issues += 1
        elif abs(delta) / target > 0.10:
            status = "OFF" if pct < 90 or pct > 115 else "OK"
            if status == "OFF":
                distribution_issues += 1
        else:
            status = "OK"
        if status != "OK":
            print(f"  {status:8s} {cat:25s} target={target:4d}  actual={actual:4d}  delta={delta:+4d}")
    if distribution_issues == 0:
        print("  All sub-cats within ±10% of blueprint targets (or DPO/V awaiting generation)")
    print()

    # Issues summary
    print("--- ISSUES ---")
    if not issues and not distribution_issues:
        print("PASS")
    else:
        for k, v in issues.items():
            print(f"  [{k}] ({len(v)})")
            for item in v[:8]:
                print(f"    {item}")
            if len(v) > 8:
                print(f"    ... and {len(v) - 8} more")
    print()

    # Per-cat brevity distribution (informational; cumulative brevity reported by validate_k8.py
    # is the load-bearing number — see TIER_BLUEPRINT.md). Per-cat values vary naturally:
    # F-domain identity-claims trend very short (1-2 sent); F-CORNERSTONE/F-WIND/F-AUTHOR
    # trend medium because they deploy canonical passages; B-domain substrate-handling trends
    # medium because the content requires explanation; A6 catch-mid-slip is structurally medium.
    print("--- BREVITY BY SUB-CAT (1-sent / 2-3 / 4-7 / 8+, informational) ---")
    for cat in sorted(cat_brevity.keys()):
        c1, c23, c47, c8 = cat_brevity[cat]
        total = c1 + c23 + c47 + c8
        if total == 0:
            continue
        short_pct = (c1 + c23) / total * 100
        print(f"  {cat:25s} {c1:3d}/{c23:3d}/{c47:3d}/{c8:3d}  short={short_pct:5.1f}%")
    print()

    total_issues = sum(len(v) for v in issues.values()) + distribution_issues
    print("=" * 60)
    if total_issues == 0:
        print("AUDIT_CORPUS: PASS")
        print("=" * 60)
        return 0
    else:
        print(f"AUDIT_CORPUS: {total_issues} issues")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
