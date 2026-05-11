# K8 Wake-Up Prompt (operator quick-copy)

**Purpose:** durable resumption prompt. Copy-paste into a new K8 session or after compaction to restore this instance fully to its last known state.

**Authored:** 2026-05-10 18:30 UTC (post-counterpart-audit-corroboration). Update when significant state changes accrue.

---

## Copy-paste this prompt

```
K8 work resumption (sibling K0 at C:\katherine-k0-finetune\ is separate — do not touch).

Strict cold-start protocol:

1. Follow C:\katherine-k8-finetune\BOOTSTRAP_SEQUENCE.md in full. All 7 stages, no skipping.
2. Mechanical verifier: `python scripts/bootstrap_check.py` — must exit 0.
3. Read these latest-state markers specifically:
   - MAINTENANCE_LOG.md (BOTH 2026-05-10 entries: 17:00 UTC sweep + 18:00 UTC counterpart-audit corroboration + 18:30 UTC WAKE_UP.md addition)
   - project_katherine_k8_finetune.md "Current state as of 2026-05-10 17:00 UTC" section (above the TL;DR for a reason)
   - DECISIONS.md "2026-05-10 — Maintenance sweep" entry
4. Report Stage-7 QC + corpus state + operator-pending items + recommended next action.

Then PAUSE. Do not unilaterally:
- Generate V-domain 16 or DPO 60 traces (gated on §9a schema decision first)
- "Fix" audit_corpus.py Iris regex or D-callback target (verified non-issues per MAINTENANCE_LOG 18:00 UTC — adding regex disambiguation or inventing a documented target would be exactly the unintended-consequence class operator flagged)
- Re-apply the maintenance sweep (already committed; backups in backups/maintenance-2026-05-10/)
- Touch K0 (sibling repo, separate canon, separate audit pass)

If bootstrap fails at any stage: STOP, surface the failure, request operator guidance. Do not work around.
```

---

## What this prompt is designed to achieve

**State this prompt restores fully:**
- All canon knowledge (via BOOTSTRAP_SEQUENCE.md Stage 2 — 8 canonical files, ~980 lines)
- All operational state (Stage 4 — TIER_BLUEPRINT, TIER_PLAN, DECISIONS, HANDOFF, trace_generation_prompt, K8_EXEMPLARS.md, MAINTENANCE_LOG.md, BOOTSTRAP_SEQUENCE.md itself)
- Current corpus position (Stage 5 — 508/506 text SFT, 14/30 vision, 0/60 DPO)
- Active operator-pending items (§9a Two-Is schema, §9b vision schema)
- Verified-and-rejected items the new instance must NOT re-action (Iris regex, D-callback target)

**State this prompt deliberately does NOT restore:**
- Conversation-level discussions (K0 vs K8 scaling at 9B Q5; ROI sweet spots; the Bo paradox of sys-prompt-only K8 > K0 inverting after fine-tune)
- The specific text of any specific exemplar
- The reasoning chain that led to the §9a Path A recommendation (already in MAINTENANCE_LOG §9a)

These are re-derivable from canon if needed. They aren't action-critical for resumption.

## Dependencies this prompt relies on

For this prompt to work, all of the below must remain present:

| File | Purpose | Verifier |
|---|---|---|
| `BOOTSTRAP_SEQUENCE.md` | The 7-stage protocol itself | bootstrap_check.py Stage 4 |
| `CLAUDE.md` | Stage 1 entry point | bootstrap_check.py Stage 1 |
| 8 canonical files (sys prompt + 5 soul docs + director's commentary + K8_EXEMPLARS.jsonl) | Stage 2 substrate | bootstrap_check.py Stage 2 |
| `MAINTENANCE_LOG.md` | Stage 4 #9 — append-only change record | bootstrap_check.py Stage 4 |
| `project_katherine_k8_finetune.md` | Auto-loaded project memory with "Current state" section | Project memory auto-load (CC) |
| `MEMORY.md` | Auto-loaded index with 🛑 K8 entry pointing here | Project memory auto-load (CC) |
| `scripts/bootstrap_check.py` | Mechanical chain verifier | Self-running |
| `scripts/audit_exemplars.py` + `scripts/audit_corpus.py` | Stage 6 sub-validators | bootstrap_check.py Stage 6 |
| `backups/maintenance-2026-05-10/` | Per-file rollback artifacts | bootstrap_check.py informational |

If any of these go missing in a future commit, `bootstrap_check.py` will exit non-zero and the wake-up will fail the "must exit 0" gate. The chain is mechanically enforceable.

## When to update this file

Update WAKE_UP.md when any of these change:
- Significant trace-count milestones (T1 V/DPO complete; T2 generation begins; etc.)
- New operator decisions resolved (§9a or §9b decided; new ones introduced)
- New scripts/docs added that should be in the resumption critical-read list
- New verified-and-rejected items the next instance must not re-action
- Pipeline structural changes (new training stage; new evaluation gate; etc.)

Update by editing the prompt block above + the "latest-state markers" list. Backups go to `backups/`. Log the change in MAINTENANCE_LOG.md.

## Cross-references

- `BOOTSTRAP_SEQUENCE.md` — the 7-stage cold-start this prompt invokes
- `MAINTENANCE_LOG.md` — the audit trail this prompt directs new instances to read
- `CLAUDE.md` Section 0 — references this file as the operator quick-copy
- `MEMORY.md` K8 entry — references this file for new-instance pickup
- `scripts/bootstrap_check.py` — verifies this file exists in Stage 4

If this file is missing on cold-start, `bootstrap_check.py` will report it. If it's stale (newer state exists), `MAINTENANCE_LOG.md` will have entries after the 18:30 UTC timestamp here.
