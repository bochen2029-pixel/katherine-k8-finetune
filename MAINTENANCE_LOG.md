# K8 Project Maintenance Log

Append-only record of maintenance changes. Each entry: timestamp, what changed, why, file paths, rollback command.

---

## 2026-05-10 17:00 UTC — Post-T1-text-generation maintenance sweep

**Trigger:** Operator request after rescan flagged several items needing fix/optimize/correct before Tier 2 generation and training.

**Scope:** 8 files edited, 2 files created, 0 files deleted. All edits reversible via backup files in `backups/maintenance-2026-05-10/`.

**Validators after all changes:**
- `bootstrap_check.py`: PASS
- `audit_exemplars.py`: PASS (61/61 sub-cats covered, all 7 canonical anchors deployed)
- `audit_corpus.py`: 16 issues — all expected V/DPO generation gaps per `generation_plan.md`
- `validate_k8.py` on `K8_EXEMPLARS.jsonl`: 75/75 PASS (was 71/75 — Two-Is exemption fixed it)
- `validate_k8.py` on `tier_1/sft_train_text.jsonl`: 508/508 PASS, 73.1% brevity, D-callback 49.2%

---

### Change 1: `scripts/validate_k8.py` — Tier 2 `<think>` exemption

**Why:** Validator hard-failed all 4 Two-Is exemplars + 4 dpo-think exemplars because they contain `<think>` blocks. Tier 1 forbids `<think>` (K8 is two-Is-collapsed by spec). Tier 2 introduces targeted Two-Is at A6/B5/C8/E1 per DECISIONS.md. Validator needed to know.

**Edit:**
- Added `allow_think: bool = False` param to `check_assistant_text()`. When True, skips THINK_BLOCK check.
- Caller (`validate_trace`) now sets `allow_think = trace.get('_type') in ('twois', 'dpo-think')` and passes through.
- Extended DPO branch from `if trace.get('_type') == 'dpo'` to `if trace.get('_type') in ('dpo', 'dpo-think')`.

**Verification:** `validate_k8.py dataset/K8_EXEMPLARS.jsonl` now 75/75 pass (was 71/75).

**Rollback:** `cp backups/maintenance-2026-05-10/validate_k8.py.bak scripts/validate_k8.py`

---

### Change 2: `scripts/push_to_hf.py` — disable auto-publish by default

**Why:** Pre-fix behavior auto-published GGUFs to public model repo `bochen2079/katherine-k8-qwen3.5-9b` on every training run. Risk: a failed fine-tune (e.g., pilot's identity-collapse mode) ships publicly with no manual eval gate. Operator instruction: "yes don't push to hf models page only to the hf bucket automatically."

**Edit:**
- Added `--push-public` opt-in flag (default False) at argparse layer.
- Wrapped GGUF + mmproj upload section in `if args.push_public:` else print skip notice.
- Updated docstring to reflect new default + usage example.
- Updated `--data-dir` default from `dataset/pilot_500` (defunct) to `dataset/tier_1` (current).

**Default behavior post-fix:** adapters/data/logs → `bochen2079/katherine-k8` bucket (private). GGUFs do NOT upload. Operator must explicitly pass `--push-public` after eval gate clears.

**Verification:** `python scripts/push_to_hf.py --help` shows `--push-public` flag with description.

**Rollback:** `cp backups/maintenance-2026-05-10/push_to_hf.py.bak scripts/push_to_hf.py`

---

### Change 3: `HANDOFF_TO_EARLIER_CLAUDE.md` — stale-doc banner

**Why:** Doc TL;DR said "Bo is mid-run on a 500-trace K8 pilot fine-tune on a RunPod H200." Pilot was discarded per DECISIONS.md "Tier 0 (existing 508 traces) disposition: discard." Future instances reading this would think pilot is still in progress.

**Edit:** Added "STATUS: HISTORICAL / PARTIALLY SUPERSEDED" banner at top with:
- Statement that pilot was discarded
- Pointer to current state via BOOTSTRAP_SEQUENCE.md, generation_plan.md, DECISIONS.md
- Note that pipeline divergences (DPO data shape, push-public, mmproj filter) ARE still relevant — the bug fixes apply, but the pilot-resumption recovery path is obsolete
- Note about other current updates (push_to_hf default-disable, validator T2 exemption, prep_dataset paths)

Original content preserved below banner for historical reference.

**Rollback:** `cp backups/maintenance-2026-05-10/HANDOFF_TO_EARLIER_CLAUDE.md.bak HANDOFF_TO_EARLIER_CLAUDE.md`

---

### Change 4: `dataset/tier_1/generation_plan.md` — current state

**Why:** Plan showed everything as 🟡 TODO. Reality: 508/506 text SFT done in-conversation. Doc currency drift.

**Edit:** Replaced status table with target-vs-actual two-column version:
- 6 rows flipped from 🟡 TODO to ✅ DONE (F-new, A, B, C, D, E)
- 3 rows still 🟡 TODO (V-domain 16, DPO text 55, DPO vision 5)
- Header now reads "508 done / 596 target (85%)"
- Added note about Stage 1a (text-only) vs Stage 1b (vision augment) two-stage training architecture.

**Rollback:** `cp backups/maintenance-2026-05-10/generation_plan.md.bak dataset/tier_1/generation_plan.md`

---

### Change 5: `scripts/prep_dataset.py` — path rebase + Two-Is exemption + stage flag

**Why:** Script pointed at defunct `dataset/pilot_500/raw/` and `dataset/pilot_500/processed/`. Pilot was discarded — these dirs don't exist. Also: script's THINK_RX filter would have rejected the same Two-Is/dpo-think rows validate_k8.py was rejecting. Also: script crashed on V-seeds (HuggingFace multimodal list content). Also: no support for two-stage training output split.

**Edits:**
- `RAW_DIR` removed; replaced with `INPUT_PATHS` list pointing at `dataset/tier_1/sft_train_text.jsonl + sft_train_vision.jsonl + dpo_train_text.jsonl + dpo_train_vision.jsonl`. Seeds NOT included (corpus already contains them; including both would dedup against itself, costing 62 false duplicates).
- `OUT_DIR` moved from `dataset/pilot_500/processed/` to `dataset/tier_1/processed/`.
- Added `--stage {1a, 1b, all}` argparse flag. 1a = text-only (Stage 1a training input), 1b = vision-only (Stage 1b training input), all = merged (legacy single-stage). Output filename suffix matches stage.
- `assistant_text_clean()` gained `allow_think` param matching validate_k8.py behavior.
- `trace_clean()` sets `allow_think = ttype in ('twois', 'dpo-think')` and passes through.
- `trace_clean()` DPO branch extended to handle `dpo-think`.
- `trace_hash()` fixed to handle both string and HuggingFace multimodal list content (was crashing on V-seeds with AttributeError: 'list' object has no attribute 'lower').

**Verification:**
- `python scripts/prep_dataset.py` → SFT: 521 / DPO: 0 / Drops: 1 DUPLICATE (1 internal dup is normal, not a script bug)
- `python scripts/prep_dataset.py --stage 1a` → SFT: 507 / DPO: 0
- Output files written to `dataset/tier_1/processed/sft_train.jsonl` and `dpo_train.jsonl` (or `_text` / `_vision` suffix per stage).

**Rollback:** `cp backups/maintenance-2026-05-10/prep_dataset.py.bak scripts/prep_dataset.py`

---

### Change 6: `scripts/finetune_k8.py` + `scripts/dpo_k8.py` — default data paths

**Why:** Both scripts defaulted to `dataset/pilot_500/processed/sft_train.jsonl` and `dataset/pilot_500/processed/dpo_train.jsonl`. Defunct paths post-pilot-discard.

**Edit:** Both `--data` arg defaults updated to `dataset/tier_1/processed/{sft,dpo}_train.jsonl`. Help text added explaining the path rebase and pointing to `prep_dataset.py` as the populator.

**Rollback:**
- `cp backups/maintenance-2026-05-10/finetune_k8.py.bak scripts/finetune_k8.py`
- `cp backups/maintenance-2026-05-10/dpo_k8.py.bak scripts/dpo_k8.py`

---

### Change 7: `DECISIONS.md` — appended session log

**Why:** DECISIONS.md is the canonical place for committed extensions / corrections. The session's maintenance changes need to be recorded for the next instance to discover.

**Edit:** Appended new section "## 2026-05-10 — Maintenance sweep (post-T1 in-conversation generation)" documenting:
- 5 infrastructure additions (BOOTSTRAP_SEQUENCE.md, bootstrap_check.py, audit_exemplars.py, K8_EXEMPLARS.jsonl + .md, TIER_BLUEPRINT.csv + .md)
- 4 bug fixes (validate_k8 Two-Is exemption, push_to_hf default-disable, prep_dataset path rebase, finetune/dpo paths)
- 4 doc currency fixes (HANDOFF banner, generation_plan, CLAUDE.md, project memory + MEMORY.md)
- 3 operator-pending items (trace_generation_prompt schema decision, vision format reconciliation, DPO + V-domain generation)

**Rollback:** `cp backups/maintenance-2026-05-10/DECISIONS.md.bak DECISIONS.md`

---

### Change 8 (NEW FILE): `scripts/audit_corpus.py`

**Why:** Had `audit_exemplars.py` (exemplars vs blueprint) but no equivalent for the corpus. Corpus distribution drift would not be caught by `validate_k8.py` (which checks per-trace patterns, not aggregate distribution).

**Created:** `scripts/audit_corpus.py` (~210 lines). Mirrors audit_exemplars.py but reads `dataset/tier_1/*.jsonl` and checks:
1. Schema completeness (_cat, _type, _tier present)
2. Sub-cat membership in TIER_BLUEPRINT.csv
3. Tier alignment (twois/dpo-think must be _tier=2)
4. K0 contamination (50+ forbidden patterns: Austin, Threshold, Eleanor, James, cold feet, etc)
5. Distribution vs blueprint targets (per-cat target ±10% tolerance)
6. Brevity distribution per sub-cat (informational, no fail)

**Verification:** Run produces "AUDIT_CORPUS: 16 issues" — all expected V/DPO generation gaps. No K0 contamination, no schema drift, no tier mismatch. Distribution OK for completed sub-cats (F/A/B/C/D/E all within tolerance).

**Rollback:** `rm scripts/audit_corpus.py` (new file, no backup needed)

---

### Operator-pending items (LEFT for explicit operator decision)

These items were flagged but NOT changed unilaterally. Operator decision required before T2 generation.

#### 9a. `trace_generation_prompt.md` — Two-Is schema divergence

The trace generation prompt uses `_cat: A6-TWOIS / B5-TWOIS / C8-TWOIS / E1-TWOIS` with `_type: single`. Required by the FINAL CHECK gate: "If `<think>` block present, `_cat` MUST end in `-TWOIS` or `-TWOIS-V`."

The K8_EXEMPLARS.jsonl uses `_cat: A6 / B5 / C8 / E1` with `_type: twois` (separate field). Required by validate_k8.py post-Change-1 (which uses `_type` to decide `allow_think`).

These are two different schemas. Both work; both are valid. The exemplar schema (separate `_type: twois`) is more consistent with the existing K8 seed schema `{_cat, _type, _tier}` and avoids inventing new sub-cats. The trace generation prompt schema (-TWOIS suffix) is more visually distinct but breaks symmetry with non-Two-Is sub-cats.

**Operator decision needed before T2 generation.** Two paths:
- (A) Update trace_generation_prompt.md to use `_cat: A6, _type: twois` (recommendation — matches exemplars + validator + audit)
- (B) Update exemplars + validate_k8.py + audit_exemplars.py + audit_corpus.py to use `_cat: A6-TWOIS, _type: single` (matches trace_generation_prompt.md, but more changes)

#### 9b. Vision schema divergence

Existing `dataset/seeds/v_domain_seeds.jsonl` and `dataset/tier_1/sft_train_vision.jsonl` use HuggingFace multimodal list format: `"content": [{"type": "image", "image": "..."}, {"type": "text", "text": "..."}]`.

K8_EXEMPLARS.jsonl V-domain entries use Option-1 text-placeholder string format: `"content": "[image: <description>] thoughts"`. Per Bo's earlier conversation: this is more honest about what Qwen3.5-9B's vision tower actually emits (generic captions, not "Bo"); K8 infers operator from conversational context.

Both work for different stages: Option-1 for synthetic generation, HF-multimodal for T2500+ real-image substitution. The forward-compat path requires a substitution script that converts Option-1 placeholders to HF-multimodal at T2500.

**Operator decision needed.** Recommendation: keep both formats — exemplars use Option-1 (calibration anchors for the bulk generator's prompt design), corpus uses HF-multimodal (the actual training data shape). The trace_generation_prompt.md should describe BOTH conventions and clarify Tier-1-uses-Option-1 vs Tier-2500+-uses-HF-multimodal.

#### 9c. Outstanding T1 generation work

Not maintenance items — operational TODO from generation_plan.md:
- 16 V-domain text-placeholder traces (Option-1 format)
- 55 DPO-text pairs
- 5 DPO-vision pairs

These finish Tier 1. Run when operator is ready. The maintenance fixes in this log are prerequisites for clean training.

---

## Rollback all changes (panic button)

```bash
cd /c/katherine-k8-finetune
cp backups/maintenance-2026-05-10/validate_k8.py.bak           scripts/validate_k8.py
cp backups/maintenance-2026-05-10/push_to_hf.py.bak            scripts/push_to_hf.py
cp backups/maintenance-2026-05-10/prep_dataset.py.bak          scripts/prep_dataset.py
cp backups/maintenance-2026-05-10/finetune_k8.py.bak           scripts/finetune_k8.py
cp backups/maintenance-2026-05-10/dpo_k8.py.bak                scripts/dpo_k8.py
cp backups/maintenance-2026-05-10/HANDOFF_TO_EARLIER_CLAUDE.md.bak  HANDOFF_TO_EARLIER_CLAUDE.md
cp backups/maintenance-2026-05-10/generation_plan.md.bak       dataset/tier_1/generation_plan.md
cp backups/maintenance-2026-05-10/trace_generation_prompt.md.bak   dataset/trace_generation_prompt.md
cp backups/maintenance-2026-05-10/DECISIONS.md.bak             DECISIONS.md
rm scripts/audit_corpus.py
rm MAINTENANCE_LOG.md
```

Verify rollback: `python scripts/bootstrap_check.py && python scripts/validate_k8.py dataset/tier_1/sft_train_text.jsonl`

---

## Maintenance principles preserved

- Every touched file has a `.bak` in `backups/maintenance-2026-05-10/` (9 files backed up before edit)
- No file was deleted
- No corpus data was modified (only scripts + docs)
- All validators run clean post-changes
- Bootstrap chain intact (`bootstrap_check.py: PASS`)
- Operator-uncertain decisions left for explicit operator approval (Section 9a / 9b above)

Authored by Claude Opus 4.7 [1M context] during 2026-05-10 17:00 UTC maintenance sweep at operator's request.

---

## 2026-05-10 18:00 UTC — Counterpart audit corroboration (no file changes)

**Trigger:** Operator forwarded the K0-fork instance's read-only audit of K8 work for cross-validation.

**Counterpart verdict:** "STRUCTURALLY ON TRACK. NO BLOCKERS. NO DEFECTS." Two-pass methodology (Explore agent + concrete data audit, in parallel) converged on the same conclusion this maintenance sweep reached. Specifically:

- Bootstrap chain works (`bootstrap_check.py` exit 0, all 6 mechanical stages pass)
- 75/75 exemplars pass post-T2-exemption
- 508/508 T1 SFT pass
- 0 net K0 contamination (24 raw regex hits all resolved as false positives in EXAMPLE/Maren reference set or F-SCENT iris-perfume note)
- 0 em-dashes in K8 corpus (13 em-dash hits were all in EXAMPLE/M0_FINETUNE_EXEMPLARS.jsonl — other-persona by design)
- 0 JSON parse failures
- All 10 pipeline scripts current and dated 2026-05-10

**Two items I initially considered actioning, then verified-and-rejected:**

1. **"Tighten audit_corpus.py Iris regex with context disambiguation."**
   - Pre-action verification: `grep -c "Iris" scripts/audit_corpus.py scripts/audit_exemplars.py` returns 0 for both.
   - Neither audit script's K0_FORBIDDEN list contains `\bIris\b`. The counterpart's 4 Iris-related false positives came from their own broader manual scan, not from running my pre-built audits.
   - **Conclusion:** no change needed. Adding regex disambiguation for a pattern that doesn't exist would be introducing untested logic that could mask actual Iris-as-K0-teen contamination in future generations. Pre-built audits are correct as-is.

2. **"Clarify D-callback density target — counterpart cites 49.2% vs 50%."**
   - Pre-action verification: searched all `.md` and `.py` files for `callback density` / `50%` / `≥50` targets in K8 docs.
   - No "50%" target is documented anywhere in K8 specs. HANDOFF mentions callback function as a quality marker but sets no percentage threshold. `validate_k8.py` reports the raw 49.2% with no comparison.
   - The counterpart's "50% target" appears to be their own informal inference, not a doc claim.
   - **Conclusion:** no clarification needed. Adding "the target is X" would be inventing a target that doesn't currently exist. Better to leave the raw report uninterpreted.

**Cross-instance learning logged (informational, not actioned — K0 is sibling repo, project boundary respected):**

- K0 has `audit_consistency.py` (soul-doc contradiction detector) that K8 doesn't.
- K8 has `bootstrap_check.py` (mechanical chain verifier) and `audit_exemplars.py` (exemplars-vs-blueprint cross-checker) that K0 doesn't.
- Both projects independently converged on CHANGELOG/MAINTENANCE_LOG patterns, exemplar files, held-out evals (K0) / forward-reference exemplars (K8), mandatory-read protocols, byte-identical backups.
- Backporting K8's mechanical-verifier patterns to K0 was raised by the counterpart as a future opportunity. **Not actioned here — that requires operator authorization and crosses project boundaries.** Logged for operator decision.

**Audit-method note:** counterpart used parallel sub-agents (Explore + data audit). This maintenance sweep used sequential inline verification. Both converged on the same verdict — sub-agents are higher-thoroughness for fresh-context audits, sequential is faster for in-conversation work. Worth noting for future audit-method selection.

**Files touched in this entry:** `MAINTENANCE_LOG.md` only (this append). No code or canon files modified. No backups needed (doc append is reversible by deleting this section).

**Verifiable state after this entry:** unchanged from 17:00 UTC maintenance sweep. All validators still pass at the same numbers (75/75 exemplars, 508/508 corpus, bootstrap PASS, audit_exemplars PASS, audit_corpus 16 expected V/DPO gaps).

---

## 2026-05-10 18:30 UTC — WAKE_UP.md added for durable resumption

**Trigger:** Operator request to make the wake-up prompt persistent rather than ephemeral copy-paste. Goal: a future Claude instance (new session or post-compaction) can be brought back to this state via a single canonical prompt that triggers the existing bootstrap chain plus operator-pending guardrails.

**New file:** `C:\katherine-k8-finetune\WAKE_UP.md`. Contents:
- Copy-paste prompt block at top (the canonical resumption prompt)
- "What this prompt restores fully" and "What it deliberately does NOT restore" sections
- Dependencies table listing all files the prompt relies on + their verifiers
- "When to update this file" guidance for future operators/instances
- Cross-references to BOOTSTRAP_SEQUENCE.md, MAINTENANCE_LOG.md, CLAUDE.md, MEMORY.md, bootstrap_check.py

**Backlinks added (3 places, mechanically traceable):**

1. **`CLAUDE.md` Section 0** — added "Operator quick-copy: WAKE_UP.md" line directly below the canonical-entry-point + mechanical-verifier lines. New instances reading CLAUDE.md Section 0 see WAKE_UP.md as the third element of the cold-start triad (BOOTSTRAP_SEQUENCE → WAKE_UP → bootstrap_check.py).

2. **`MEMORY.md` K8 entry** (in `~/.claude/projects/C--buddhabrot-main/memory/`) — replaced the bare BOOTSTRAP_SEQUENCE.md reference with "Quick-copy wake-up prompt: `WAKE_UP.md` (paste prompt block into new session for full cold-start). Or read BOOTSTRAP_SEQUENCE.md directly." So both paths surface in the auto-loaded index entry.

3. **`scripts/bootstrap_check.py` STAGE_4** — added `WAKE_UP.md` to operational-specs file list (9 → 10 entries). If WAKE_UP.md goes missing in a future commit, bootstrap_check.py exits non-zero. Chain is mechanically enforced.

**Verification:** `python scripts/bootstrap_check.py` exits 0 post-changes. Stage 4 reports 10/10 pass (previously 9/9).

**Files touched (with backups):**

| File | Action | Backup |
|---|---|---|
| `WAKE_UP.md` | NEW — durable resumption prompt at project root | n/a (new file) |
| `CLAUDE.md` | Section 0 backlink to WAKE_UP.md (1-line addition) | `CLAUDE.md.bak-wake_up` |
| `MEMORY.md` (project memory index) | K8 entry now points at WAKE_UP.md first, BOOTSTRAP_SEQUENCE.md second | `MEMORY.md.bak-wake_up` |
| `scripts/bootstrap_check.py` | STAGE_4 list extended with WAKE_UP.md | `bootstrap_check.py.bak-wake_up` |

**Why this entry is in MAINTENANCE_LOG.md rather than DECISIONS.md:** this is a derivative artifact (WAKE_UP.md restates the prompt designed in conversation; it's not a canonical extension to K8 spec). DECISIONS.md is reserved for spec-level commitments; MAINTENANCE_LOG is the right home for infrastructure additions.

**Rollback (if needed):**
```bash
cp backups/maintenance-2026-05-10/CLAUDE.md.bak-wake_up               CLAUDE.md
cp backups/maintenance-2026-05-10/MEMORY.md.bak-wake_up               /c/Users/user/.claude/projects/C--buddhabrot-main/memory/MEMORY.md
cp backups/maintenance-2026-05-10/bootstrap_check.py.bak-wake_up      scripts/bootstrap_check.py
rm WAKE_UP.md
```

**Self-consistency note:** WAKE_UP.md's prompt block points to "BOTH 2026-05-10 entries: 17:00 UTC sweep + 18:00 UTC counterpart-audit corroboration + 18:30 UTC WAKE_UP.md addition." This entry (the 18:30 UTC one) is now the third entry referenced. The new-instance reading WAKE_UP.md sees a pointer back to this entry — loop closed.

---

## 2026-05-10 18:45 UTC — DPO data-shape verified + smoke pilot packaged

**Trigger:** Operator pushed back on the prior turn's hand-wave framing ("needs DPO shape verification before generating 60"). Right pushback — the trainer script exists in-repo; verification should be done, not flagged. Operator also requested: "package and pretty another pilot run and let me confirm if it trains."

**Static verification (CPU-only, completed in-conversation):**

| Check | Result |
|---|---|
| `dpo_k8.py` `fmt_dpo_example` expects keys | `messages` (list ending in user) + `chosen (str)` + `rejected (str)` |
| K8_EXEMPLARS.jsonl `_type:dpo` entry keys | `messages, chosen, rejected, _cat, _type, _tier` — matches ✓ |
| K8_EXEMPLARS.jsonl `_type:dpo` chosen/rejected type | `str` / `str` — matches ✓ |
| K8_EXEMPLARS.jsonl `_type:dpo-think` entry shape | Same keys, chosen+rejected still strings (with `<think>` blocks inside) — matches ✓ |
| `dpo_k8.py` has `remove_columns=ds.column_names` (commit `1cc0a38` defense) | Present, plus additional TRL 0.24 defensive note in code ✓ |
| `prep_dataset.py` handles `_type:'dpo-think'` | Maintenance sweep extended DPO branch to `('dpo', 'dpo-think')` + `allow_think` flag ✓ |

**Verdict on DPO data-shape verification:** PASS. The K8 DPO trainer + the K8_EXEMPLARS.jsonl DPO entries are shape-compatible. The `remove_columns` bug-fix at `1cc0a38` is in place. No code changes needed.

**Smoke pilot packaged — `scripts/smoke_pilot_t1a.sh`:**

Runnable end-to-end Stage 1a + DPO-smoke pilot for K8 on RunPod H200 (or equivalent). Purpose: verify the training pipeline works on real hardware BEFORE generating the remaining 60 production DPO pairs.

Stages:
1. **Preflight:** runs `bootstrap_check.py`, `validate_k8.py` on SFT + DPO corpora, `audit_corpus.py`. Exits non-zero if any fail.
2. **prep_dataset.py --stage 1a:** produces `tier_1/processed/sft_train_text.jsonl` (507 traces) + `dpo_train_text.jsonl` (12 smoke pairs).
3. **finetune_k8.py:** Stage 1a SFT on 507 traces → `adapters/k8_sft_adapter` (~30 min H200, ~$2).
4. **dpo_k8.py:** DPO smoke on 12 K8_EXEMPLARS DPO entries → `adapters/k8_dpo_adapter` (~10 min, ~$1). **KEY GATE: must NOT crash on `remove_columns` / KeyError** (verifies `1cc0a38` fix on real data).
5. **merge_and_gguf.py:** Q5_K_M only for smoke (faster than Q4+Q5+Q6 sweep) + mmproj-F16 → `gguf/`.
6. **push_to_hf.py:** BUCKET ONLY (adapters + data + logs). Public model repo upload is GATED behind `--push-public` flag (default OFF since 2026-05-10 17:00 UTC maintenance). Operator must explicitly opt-in after manual LM Studio probe gate clears.

**Smoke characteristics:**
- SFT corpus: 508 traces (full T1 text SFT)
- DPO corpus: 12 pairs (K8_EXEMPLARS DPO subset — calibration anchors doubling as smoke-test data; when real T1 DPO is generated, append to bring total to ~72)
- Wallclock: ~50-60 min on H200 SXM5
- Cost: ~$3-5 at H200 spot pricing
- Vision (Stage 1b): NOT included — V-corpus is 14/30; complete V-domain generation before Stage 1b

**DPO smoke corpus seeded:** `dataset/tier_1/dpo_train_text.jsonl` now contains 12 entries (extracted from K8_EXEMPLARS.jsonl via `grep -E '"_type":"dpo"|"_type":"dpo-think"' dataset/K8_EXEMPLARS.jsonl > dataset/tier_1/dpo_train_text.jsonl`). All 12 pass shape verification (messages-ends-in-user, chosen str, rejected str). The duplication between K8_EXEMPLARS.jsonl and tier_1/dpo_train_text.jsonl is intentional — exemplars are calibration anchors first, training data second; for the smoke pilot the dual-purpose is acceptable. When real T1 DPO (60 pairs) is generated, simply append to tier_1/dpo_train_text.jsonl; the 12 exemplar entries can stay (12+60=72, small overshoot vs 60 target) or be cleared and re-seeded post-real-generation.

**Files touched:**

| File | Action | Backup |
|---|---|---|
| `dataset/tier_1/dpo_train_text.jsonl` | Seeded with 12 K8_EXEMPLARS DPO entries (was 0 lines) | n/a (was empty; reverting = empty the file again) |
| `dataset/tier_1/processed/sft_train_text.jsonl` | Produced by prep_dataset.py --stage 1a (507 traces) | n/a (regenerable from prep_dataset.py) |
| `dataset/tier_1/processed/dpo_train_text.jsonl` | Produced by prep_dataset.py --stage 1a (12 entries) | n/a (regenerable) |
| `scripts/smoke_pilot_t1a.sh` | NEW — runnable pilot | n/a (new file) |

**Rollback (if smoke seeding needs reverting):**
```bash
> dataset/tier_1/dpo_train_text.jsonl  # truncate back to 0 lines
rm scripts/smoke_pilot_t1a.sh
rm -rf dataset/tier_1/processed/
```

**Verification:** `bootstrap_check.py` PASS post-additions (Stage 4 10/10, Stage 5 corpus-state updated to reflect dpo_train_text.jsonl populated).

**Operator action item:** run `bash scripts/smoke_pilot_t1a.sh` on RunPod H200. Expected outcomes documented in script header comments. If smoke completes without errors AND LM Studio probes show K8 voice intact (no identity collapse, no register drift), pipeline is verified for T1 — proceed to V-domain 16 + DPO 60 generation, then full T1 production run.

If smoke fails at the `dpo_k8.py` step on real hardware: that's the regression case — would indicate either (a) data-shape mismatch despite static verification, (b) TRL version drift since the `1cc0a38` fix, or (c) Unsloth/PEFT incompatibility. Debug from that signal.
