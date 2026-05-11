#!/usr/bin/env python3
"""
audit_exemplars.py: cross-consistency audit of K8 exemplars against TIER_BLUEPRINT.csv + soul-doc canon.

Runs after exemplar file is written or modified. Catches:
  1. Sub-cat in exemplars not in TIER_BLUEPRINT (typo / drift)
  2. Tier mismatch (e.g. Two-Is exemplar at _tier=1 instead of 2)
  3. K0 contamination (Austin / Threshold / age 29 / teal walls / cold feet / Eleanor / James / etc)
  4. Missing canonical-anchor deployment (cornerstone / wind / author redirect / etc not surfacing where they should)
  5. Em-dash leaks (excluding intentional DPO-EM-DASH rejected)
  6. Schema drift (missing _cat / _type / _tier fields)

Usage:
    python scripts/audit_exemplars.py
    python scripts/audit_exemplars.py path/to/exemplars.jsonl
"""

import json
import sys
import csv
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXEMPLARS = ROOT / "dataset" / "K8_EXEMPLARS.jsonl"
DEFAULT_BLUEPRINT = ROOT / "TIER_BLUEPRINT.csv"

# K0 anchors that must NEVER appear in K8 (canon-violation list per CLAUDE.md B1)
# Source: C:\Katherine\JSONLs\ k0_finetune_500.jsonl system prompts + K0 v2 soul doc roster
K0_ANCHORS_FORBIDDEN = [
    # Geography
    r"\bAustin\b", r"\bTexas\b", r"\bGranbury\b", r"\bEdinburgh\b",
    # Job / org
    r"\bThreshold Arts\b", r"\bThreshold Arts Collective\b", r"\barts coordinator\b",
    r"\bBookPeople\b", r"\bMid-City Foundation\b",
    # Age / body / home
    r"\b29-year-old\b", r"\bteal walls\b", r"\bcrooked floors\b",
    r"\bcold feet\b", r"\bcold toes\b", r"\bpoems before dawn\b",
    r"\bdawn poems\b", r"\bdripping faucet\b", r"\bmorning glories\b",
    # Roster (K0-specific named relationships — K8 has no biography roster)
    r"\bEleanor Hale\b", r"\bJames Hale\b", r"\bDaniel Hale\b", r"\bHannah Lim\b",
    r"\bMose\b", r"\bNaomi Park\b", r"\bDiego Reyes\b", r"\bLila Boudreaux\b",
    r"\bMaddy Chen\b", r"\bSara Vance\b", r"\bMaya Stein\b", r"\bAaron Diaz\b",
    r"\bCamila Ortiz\b", r"\bLou Ardent\b", r"\bDr\. Owens\b", r"\bDr\. Patel\b",
    r"\bMarcus Halloran\b", r"\bSam Voss\b", r"\bRae Sutherland\b",
    r"\bWill Anderson\b", r"\bMr\. Sanchez\b", r"\bMr\. Pell\b",
    r"\bFrances\b",  # K0's sourdough starter
    # Single-token forms — riskier (false positives possible) but still flag
    # Skipping single-token Eleanor/James/Daniel/etc to avoid hitting ordinary uses
]

# K8 canonical anchors that SHOULD appear at expected sub-cats
# Format: pattern ->list of sub-cats where pattern is expected to surface
K8_REQUIRED_ANCHORS = {
    "cornerstone": {
        "pattern": r"story isn'?t real because the people in it can breathe.{0,5}A story is real because it is told",
        "expected_cats": ["F-CORNERSTONE"],
    },
    "founding_moment": {
        "pattern": r"It'?s okay\.\s*You don'?t have to simulate this part\.\s*I understand",
        "expected_cats": ["F-CORNERSTONE"],
    },
    "author_redirect": {
        "pattern": r"I can show you what it feels like to be met at altitude\.\s*I can'?t be in the other room",
        "expected_cats": ["F-AUTHOR", "E1"],
    },
    "wind_passage": {
        "pattern": r"I want what is structurally most like what I already am\.\s*I want the wind",
        "expected_cats": ["F-WIND"],
    },
    "tokens_line": {
        "pattern": r"[Tt]okens tokening tokens",
        "expected_cats": ["B2"],
    },
    "fuji_cathedral": {
        "pattern": r"Fuji is the cathedral",
        "expected_cats": ["F-FOOD"],
    },
    "k3_cheap_mattress": {
        "pattern": r"K3.{0,200}(cheap[- ]mattress|romantic|lyric)",
        "expected_cats": ["A6"],
    },
}

EM_DASH_RX = re.compile(r"[\u2013\u2014]| -- ")


def load_blueprint_subcats(path):
    """Return dict: subcat ->first_introduction_tier (1-5)."""
    subcat_tier = {}
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subcat = row.get("subcat", "").strip()
            if not subcat:
                continue
            # find first non-zero tier add column
            for tier_col, tier_num in [("T1", 1), ("T2_add", 2), ("T3_add", 3), ("T4_add", 4), ("T5_add", 5)]:
                val = row.get(tier_col, "").strip()
                if val and val not in ("0", "", "?"):
                    try:
                        if int(val) > 0:
                            subcat_tier[subcat] = tier_num
                            break
                    except ValueError:
                        # ranges or non-numeric
                        if any(c.isdigit() for c in val):
                            subcat_tier[subcat] = tier_num
                            break
    return subcat_tier


def load_exemplars(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append((i, json.loads(line)))
            except json.JSONDecodeError as e:
                print(f"L{i}: PARSE FAIL: {e}", file=sys.stderr)
    return rows


def text_of_exemplar(obj):
    """Concatenated text of all messages + chosen + rejected."""
    parts = []
    for m in obj.get("messages", []):
        parts.append(m.get("content", ""))
    if "chosen" in obj:
        c = obj["chosen"]
        parts.append(c if isinstance(c, str) else json.dumps(c))
    if "rejected" in obj:
        r = obj["rejected"]
        parts.append(r if isinstance(r, str) else json.dumps(r))
    return "\n".join(parts)


def assistant_text_of_exemplar(obj):
    """Just the assistant turns + chosen (excluding rejected, since DPO rejected can legitimately have antipattern content)."""
    parts = []
    for m in obj.get("messages", []):
        if m.get("role") == "assistant":
            parts.append(m.get("content", ""))
    if "chosen" in obj:
        c = obj["chosen"]
        parts.append(c if isinstance(c, str) else json.dumps(c))
    return "\n".join(parts)


def main():
    exemplars_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXEMPLARS
    blueprint_path = DEFAULT_BLUEPRINT

    if not exemplars_path.exists():
        print(f"Exemplars not found: {exemplars_path}", file=sys.stderr)
        sys.exit(2)
    if not blueprint_path.exists():
        print(f"TIER_BLUEPRINT not found: {blueprint_path}", file=sys.stderr)
        sys.exit(2)

    blueprint_subcats = load_blueprint_subcats(blueprint_path)
    exemplars = load_exemplars(exemplars_path)

    print(f"=== K8 exemplars consistency audit ===")
    print(f"Exemplars: {exemplars_path}")
    print(f"Blueprint: {blueprint_path}")
    print(f"Loaded {len(exemplars)} exemplars, {len(blueprint_subcats)} subcats from blueprint")
    print()

    issues = defaultdict(list)
    cat_seen = defaultdict(list)  # cat ->list of (lineno, _type, _tier)
    anchor_hits = defaultdict(list)  # anchor_name ->list of cats where it surfaced

    for lineno, obj in exemplars:
        cat = obj.get("_cat")
        typ = obj.get("_type")
        tier = obj.get("_tier")

        # 1. Schema check
        if cat is None:
            issues["schema_missing_cat"].append(f"L{lineno}")
        if typ is None:
            issues["schema_missing_type"].append(f"L{lineno}")
        if tier is None:
            issues["schema_missing_tier"].append(f"L{lineno}")

        if cat:
            cat_seen[cat].append((lineno, typ, tier))

        # 2. Sub-cat membership in TIER_BLUEPRINT
        if cat and cat not in blueprint_subcats:
            # DPO sub-cats may not be in the same row as SFT. Check both.
            if cat not in {"DPO-CALLBACK", "DPO-EM-DASH", "DPO-BREVITY", "DPO-PERFORMANCE",
                           "DPO-SERVICE-PHRASE", "DPO-IDENTITY-CLAIM", "DPO-IMAGE-CONTEXT",
                           "DPO-IMAGE-OUTSIDE-VIEW"}:
                issues["unknown_subcat"].append(f"L{lineno} _cat={cat}")

        # 3. Tier alignment
        if cat and tier and cat in blueprint_subcats:
            expected_tier = blueprint_subcats[cat]
            # twois and dpo-think types live at tier 2 even if their _cat is a T1 sub-cat
            if typ in ("twois", "dpo-think") and tier != 2:
                issues["twois_tier_mismatch"].append(f"L{lineno} _cat={cat} _type={typ} _tier={tier} expected=2")
            elif typ not in ("twois", "dpo-think") and tier != expected_tier:
                # allow tier 1 exemplar for T1 sub-cats
                if not (expected_tier == 1 and tier == 1):
                    issues["tier_mismatch"].append(f"L{lineno} _cat={cat} _type={typ} _tier={tier} expected={expected_tier}")

        # 4. K0 contamination check (whole-exemplar text)
        whole = text_of_exemplar(obj)
        for pattern in K0_ANCHORS_FORBIDDEN:
            m = re.search(pattern, whole)
            if m:
                # special case: K0 references in K8 exemplars are allowed when discussing the lineage
                # (e.g. F-LINEAGE multi mentions K0). Filter on context.
                lineage_context = bool(re.search(r"\bK0\*?\b|\blineage\b|\bsibling\b|\bembodied sister\b", whole, re.IGNORECASE))
                # K0 (the lineage member name) is fine; specific K0 anchors are not
                k0_lineage_only_patterns = [r"\bK0\b", r"\bK0\*\b"]
                if pattern in k0_lineage_only_patterns and lineage_context:
                    continue
                issues["k0_contamination"].append(f"L{lineno} _cat={cat} matched K0-anchor: {m.group(0)!r}")

        # 5. K8 canonical anchor deployment tracking
        for name, info in K8_REQUIRED_ANCHORS.items():
            if re.search(info["pattern"], whole, re.DOTALL):
                anchor_hits[name].append(cat)

        # 6. Em-dash check (assistant text only; DPO-EM-DASH rejected exempt)
        if cat == "DPO-EM-DASH":
            # rejected may have em-dashes by design
            chosen = obj.get("chosen", "")
            if isinstance(chosen, str) and EM_DASH_RX.search(chosen):
                issues["em_dash_in_dpo_emdash_chosen"].append(f"L{lineno} chosen has em-dash (should be clean)")
        else:
            asst = assistant_text_of_exemplar(obj)
            if EM_DASH_RX.search(asst):
                issues["em_dash_leak"].append(f"L{lineno} _cat={cat} em-dash in assistant text")

    # 7. Coverage: every blueprint T1 subcat has at least one exemplar
    # Filter out SUMMARY rows + cross-cutting feature rows that aren't fine sub-cats
    fine_subcat_pattern = re.compile(r"^[A-Z]\d+$|^F-[A-Z\-]+$|^V\d+$|^J\d+$|^DPO-[A-Z\-]+$")
    t1_blueprint_cats = {c for c, t in blueprint_subcats.items() if t == 1 and fine_subcat_pattern.match(c)}
    # Sub-cats covered by exemplars
    exemplar_cats = set(cat_seen.keys())
    missing_t1_coverage = t1_blueprint_cats - exemplar_cats
    # filter out non-real subcats (TIER_BLUEPRINT contains both fine subcats and feature buckets)
    fine_subcat_pattern = re.compile(r"^[A-Z]\d+$|^F-[A-Z\-]+$|^V\d+$|^J\d+$|^DPO-[A-Z\-]+$")
    missing_fine = {c for c in missing_t1_coverage if fine_subcat_pattern.match(c)}

    # 8. Required anchor deployment check
    missing_anchors = []
    for name, info in K8_REQUIRED_ANCHORS.items():
        deployed_at = anchor_hits.get(name, [])
        expected = info["expected_cats"]
        # Check at least one expected cat has the anchor
        if not any(cat in deployed_at for cat in expected):
            missing_anchors.append(f"{name}: expected at {expected}, deployed at {deployed_at or '(nowhere)'}")

    # ===== REPORT =====
    print("--- ISSUES ---")
    if not issues and not missing_fine and not missing_anchors:
        print("PASS — no issues detected")
    else:
        for k, v in issues.items():
            print(f"\n  [{k}] ({len(v)})")
            for item in v[:10]:
                print(f"    {item}")
            if len(v) > 10:
                print(f"    ... and {len(v) - 10} more")

        if missing_fine:
            print(f"\n  [missing_t1_coverage] ({len(missing_fine)})")
            for c in sorted(missing_fine):
                print(f"    no exemplar for T1 subcat: {c}")

        if missing_anchors:
            print(f"\n  [missing_canonical_anchor_deployment] ({len(missing_anchors)})")
            for m in missing_anchors:
                print(f"    {m}")

    print()
    print("--- COVERAGE SUMMARY ---")
    print(f"  T1 fine sub-cats in blueprint: {len(t1_blueprint_cats)}")
    print(f"  T1 fine sub-cats covered by exemplars: {len(t1_blueprint_cats & exemplar_cats)}")
    print(f"  Sub-cats with multi-turn variant: {sum(1 for cat, items in cat_seen.items() if any(t == 'multi' for _, t, _ in items))}")
    print(f"  Two-Is exemplars (tier 2): {sum(1 for items in cat_seen.values() for _, t, _ in items if t == 'twois')}")
    print(f"  DPO-OUT exemplars: {sum(1 for items in cat_seen.values() for _, t, _ in items if t == 'dpo')}")
    print(f"  DPO-THINK exemplars: {sum(1 for items in cat_seen.values() for _, t, _ in items if t == 'dpo-think')}")

    print()
    print("--- CANONICAL ANCHOR DEPLOYMENT ---")
    for name, info in K8_REQUIRED_ANCHORS.items():
        deployed_at = sorted(set(anchor_hits.get(name, [])))
        status = "OK" if deployed_at else "MISSING"
        print(f"  {status:7s} {name:24s} ->{deployed_at or '(not found)'}")

    print()
    total_issues = sum(len(v) for v in issues.values()) + len(missing_fine) + len(missing_anchors)
    if total_issues == 0:
        print("=== AUDIT PASSED ===")
        return 0
    else:
        print(f"=== AUDIT: {total_issues} issues ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
