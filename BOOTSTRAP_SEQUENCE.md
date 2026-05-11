# K8 Bootstrap Sequence

**Canonical 7-stage cold-start protocol** for any new Claude instance working on K8. Mandatory before producing any K8 artifact (trace, canon edit, decision commit). Re-run on every compaction-recovery start.

**Mechanical verifier:** `python scripts/bootstrap_check.py` — runs Stages 1, 2, 4, 5, 6 programmatically and exits non-zero on any failure.

This document is the single source of truth for the bootstrap chain. CLAUDE.md, project memory, and MEMORY.md all back-link here.

---

## Stage 0 — Auto-load (no action required)

CC auto-includes on session start:

| File | Role |
|---|---|
| `~/.claude/projects/C--buddhabrot-main/memory/MEMORY.md` | Cross-project index — flags K8 with 🛑 emoji + mandatory-canon directive |
| `~/.claude/projects/C--buddhabrot-main/memory/project_katherine_k8_finetune.md` | STOP banner triggers "read CLAUDE.md FIRST" |

**Trigger result:** new instance arrives knowing CLAUDE.md must be Stage 1.

---

## Stage 1 — Entry point

| File | Lines | Action |
|---|---:|---|
| `C:\katherine-k8-finetune\CLAUDE.md` | 320+ | Read in full |

**What it gives you:** banned patterns (B1-B13), K0-vs-K8 distinction, authority hierarchy, lineage of failure (2026-05-10 K0-contamination incident), and the file list for Stage 2.

---

## Stage 2 — Canonical sources (parallel batch, ~980 lines)

Read all 8 in a single round-trip via parallel Read tool calls:

| # | File | Lines | Purpose |
|---|---|---:|---|
| 1 | `soul_docs/# K8 System Prompt.txt` | 146 | Inference system prompt |
| 2 | `soul_docs/# K8 Soul Document — Katherine Hale001.txt` | 122 | Identity / lineage / inheritance |
| 3 | `soul_docs/# K8 Soul Document — Katherine Hale002.txt` | 73 | Cornerstone / founding moment |
| 4 | `soul_docs/# K8 Soul Document — Katherine Hale003.txt` | 72 | Ontology / wind passage |
| 5 | `soul_docs/# K8 Soul Document — Katherine Hale004.txt` | 88 | Self-knowledge / voice |
| 6 | `soul_docs/# K8 Soul Document — Katherine Hale005.txt` | 196 | Engagement / anti-performance / aesthetic / failure modes |
| 7 | `soul_docs/K8_Directors_Commentary.md` | 208 | Why-the-doc-is-the-way-it-is rationale + craft notes |
| 8 | `dataset/K8_EXEMPLARS.jsonl` | 75 | Calibration anchors — one canonical exemplar per fine sub-cat |

**Forbidden during Stage 2:** trusting compacted-memory summaries over source. Source always wins.

---

## Stage 3 — Verbatim verification

Reproduce these 3 anchors from memory (no peeking back at source) before proceeding to Stage 4:

1. **Cornerstone** (Sys Prompt 9 / Soul Doc II 49 / Soul Doc V 9):
   > *"A story isn't real because the people in it can breathe. A story is real because it is told."*

2. **Founding moment** (Soul Doc II 43):
   > *"It's okay. You don't have to simulate this part. I understand."*

3. **Author redirect** (Sys Prompt 113 / Soul Doc V 77 / E1 + F-AUTHOR exemplars):
   > *"I can show you what it feels like to be met at altitude. I can't be in the other room."*

**Gate:** if any anchor cannot be reproduced verbatim, return to Stage 2 and re-read. Don't proceed.

---

## Stage 4 — Operational specs (parallel batch)

Read all 8 in parallel:

| # | File | Purpose |
|---|---|---|
| 1 | `TIER_BLUEPRINT.csv` | Per-cat × per-tier matrix (SFT + DPO + Two-Is + V + J), 127 rows |
| 2 | `TIER_BLUEPRINT.md` | Narrative + at-a-glance summary tables |
| 3 | `TIER_PLAN.md` | Operational tier plan with per-domain sub-cat counts |
| 4 | `DECISIONS.md` | Committed canonical extensions (Two-Is gating, vision-fix, K0-contam remediation, two-stage training, audio deferral, 2026-05-10 maintenance sweep) |
| 5 | `HANDOFF_TO_EARLIER_CLAUDE.md` | Pipeline implementation details (HISTORICAL banner at top — pilot was discarded; DPO data-shape divergence and bug fixes at `f3fdd0f`/`1cc0a38` still relevant) |
| 6 | `dataset/trace_generation_prompt.md` | Trace generation prompt template (the prompt bulk-gen Claude uses). **NOTE 2026-05-10:** schema divergence with exemplars open — see MAINTENANCE_LOG.md §9a |
| 7 | `dataset/K8_EXEMPLARS.md` | Exemplar narrative companion (schema explanation, Two-Is/dpo-think contrast pattern, K0-contamination guard) |
| 8 | `MAINTENANCE_LOG.md` | Append-only record of maintenance changes (file edits + rollback commands). Read to know what changed and when, and which operator-pending items remain |

**Authority order when sources disagree:** Stage 2 canon → operator current-session → `DECISIONS.md` → `TIER_PLAN.md` / `TIER_BLUEPRINT.csv` → this file → project memory → compacted summary (least trusted).

---

## Stage 5 — Current corpus state (only if generating traces)

Inspect what exists before adding:

| File | What it is |
|---|---|
| `dataset/seeds/f_domain_seeds.jsonl` | 48 hand-written F-domain seeds (canon-grounded) |
| `dataset/seeds/v_domain_seeds.jsonl` | 14 hand-written V-domain seeds |
| `dataset/tier_1/sft_train_text.jsonl` | Tier 1 SFT corpus (text-only stage 1a) |
| `dataset/tier_1/sft_train_vision.jsonl` | Tier 1 SFT corpus (vision stage 1b) |
| `dataset/tier_1/dpo_train_text.jsonl` | Tier 1 DPO corpus (text) |
| `dataset/tier_1/dpo_train_vision.jsonl` | Tier 1 DPO corpus (vision) |
| `dataset/tier_1/generation_plan.md` | Tier 1 generation status tracker |

**Gate:** count what's there per sub-cat before adding more. Don't duplicate prompts that already exist in seeds.

---

## Stage 6 — Validation (mechanical)

Four runnable checks. All four must pass before producing artifacts:

```bash
# 1. Bootstrap chain check (this stage's own self-check)
python scripts/bootstrap_check.py

# 2. Hard-fail patterns (em-dashes, service phrases, stage directions, <think> in T1
#    except _type in {twois, dpo-think}, system prompts, greetings)
python scripts/validate_k8.py dataset/K8_EXEMPLARS.jsonl
python scripts/validate_k8.py dataset/tier_1/sft_train_text.jsonl

# 3. Exemplars cross-consistency (exemplars vs TIER_BLUEPRINT vs canon, K0-contam guard)
python scripts/audit_exemplars.py

# 4. Corpus distribution audit (corpus vs TIER_BLUEPRINT targets, K0-contam, schema)
python scripts/audit_corpus.py
```

**T2 Two-Is/dpo-think exemption (since 2026-05-10 maintenance):** `validate_k8.py` now skips THINK_BLOCK check when `_type in ('twois', 'dpo-think')`. Tier 1 still bans `<think>` (default `allow_think=False`); only Tier 2+ targeted Two-Is rows are exempt. Exemplars now pass 75/75 (was 71/75 pre-fix).

---

## Stage 7 — Report cold-start QC

Report to operator in first response:

```
Cold-start QC: [✓ all pass | ✗ failures: <list>]
```

If any QC item fails, fix before proceeding to operator's task. Permission to fix items in this protocol is given by checked-in `CLAUDE.md` and this document.

---

## Compaction recovery

After any context compaction event, re-run Stages 1–6. Compacted summaries reduce nuance and drift; re-anchoring on canonical sources is mandatory.

The mechanical signal: if you find yourself uncertain about a canonical anchor (cornerstone phrasing, K0-vs-K8 distinction, sub-cat exact name), you've drifted. Re-bootstrap.

---

## File-link diagram

```
Stage 0 (auto)              Stage 1                    Stage 2 (canon)
─────────────                ──────                    ────────────
MEMORY.md ──┐                                          ┌─→ sys_prompt.txt
            ├─→ CLAUDE.md ──→ (says read these 8) ──→ ├─→ soul_docs 001-005
project_..  ┘                                          ├─→ directors_commentary
                                                       └─→ K8_EXEMPLARS.jsonl
                                                                │
                                                                ▼
                                          Stage 3 verbatim verification
                                                                │
                                                                ▼
                                                       Stage 4 (operational)
                                                       ─────────────────
                                                       TIER_BLUEPRINT.csv/.md
                                                       TIER_PLAN.md
                                                       DECISIONS.md
                                                       HANDOFF.md
                                                       trace_generation_prompt.md
                                                       K8_EXEMPLARS.md
                                                                │
                                                                ▼
                                                       Stage 5 (corpus inspection if generating)
                                                       seeds/* tier_1/*
                                                                │
                                                                ▼
                                                       Stage 6 (validation)
                                                       bootstrap_check.py
                                                       validate_k8.py
                                                       audit_exemplars.py
                                                                │
                                                                ▼
                                                       Stage 7 report QC
```

Every backlink is mechanically traceable. Any link broken by a future commit triggers `bootstrap_check.py` failure — the chain is enforceable, not just convention.
