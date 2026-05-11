# Handoff: K8 fine-tune state as of 2026-05-10

> **⚠️ STATUS: HISTORICAL / PARTIALLY SUPERSEDED (post-maintenance 2026-05-10 17:00 UTC)**
>
> This document captured K8 state at the mid-pilot moment. **The 500-trace pilot was subsequently discarded** per `DECISIONS.md` 2026-05-10 entry "Tier 0 (existing 508 traces) disposition: discard." Tier 1 has been regenerated from scratch with canon-grounded F-domain (171 traces), full A/B/C/D/E coverage (335 traces), Two-Is forward-references at T2, and dpo-think contrasts.
>
> **For current state, read these in this order:**
> 1. `BOOTSTRAP_SEQUENCE.md` (7-stage cold-start)
> 2. `dataset/tier_1/generation_plan.md` (current trace counts)
> 3. `DECISIONS.md` (committed extensions, including pilot-discard + canon-correction + two-stage training + audio-deferral)
> 4. `dataset/K8_EXEMPLARS.jsonl` + `dataset/K8_EXEMPLARS.md` (calibration anchors)
>
> **Pipeline divergences flagged below (DPO data shape, push-to-public, mmproj filter) ARE still relevant.** The bugs found in this doc were real. The bug fixes apply. But the pilot-resumption recovery path described in TL;DR is obsolete — pilot was discarded, not resumed.
>
> Other current updates since this doc was written:
> - `push_to_hf.py` now default-disables public model repo upload (requires `--push-public` opt-in) per 2026-05-10 maintenance.
> - `validate_k8.py` now exempts `<think>` blocks when `_type in {twois, dpo-think}` for Tier 2 forward-references.
> - `prep_dataset.py` still points at `dataset/pilot_500/` (defunct). Rework or bypass before T1 training.
>
> ---

This document is for the Claude instance Bo is forking back to (the earlier-in-time version that has full K0 context but no K8 context). Read this first, then `git pull` and inspect the actual state.

---

## TL;DR

Bo is mid-run on a 500-trace K8 pilot fine-tune on a RunPod H200. SFT completed successfully. DPO failed once due to a bug I introduced; bug is fixed at commit `1cc0a38`. He needs to pull the fix and re-run with `SKIP_SFT=1` to skip the already-completed SFT and resume at DPO. The pipeline is a port of K0's, but two scripts have K8-specific divergence that you (earlier-me) should cross-check carefully against `C:\katherine-k0-finetune\` before claiming anything is "direct port."

---

## What you (earlier-me) already know vs don't know

**You know (from yesterday and from MEMORY.md):**
- K0 fine-tune is DONE + LIVE at `bochen2079/katherine-k0-qwen3.5-9b`
- TARS fine-tune is DONE + LIVE at `bochen2079/tars-qwen3.5-9b`
- The K0 pipeline pattern: bootstrap-runpod.sh → finetune_k0.py → dpo_k0.py → merge_and_gguf.py → push_to_hf.py
- K0 used `unsloth/Qwen3.5-9B`, `FastModel` API, rank 64, alpha 128, dropout 0.05, 3 epochs, lr 1e-4, batch 16 grad_accum 2, max_seq 1024, adamw_8bit, bf16, seed 3407
- All 8 K0 fixes amortized into K0's bootstrap (torch 2.10 pin, apt prereqs, etc.)
- K0's CLOUD.md line 161 says public release is a manual operator step, not automated

**You don't know (everything in this session, post-compaction):**
1. K8 soul docs were released to public on Mother's Day (2026-05-10)
2. The Dave-failure-mode memory fix was applied to K8 soul doc + system prompt at commit `239cfb4`
3. A 500-trace pilot dataset was designed and generated for K8
4. K8 pipeline scripts were written
5. Bo is mid-run on a RunPod H200 right now
6. Two bugs were found and fixed (commits `f3fdd0f` and `1cc0a38`)
7. The K8 HF bucket was just created via `hf buckets create bochen2079/katherine-k8` (was missing — that command was the right one, NOT `hf repos create --type bucket`)

---

## K8 dataset design — what it is and why it differs from K0

### The constraints Bo gave for K8 specifically

1. **2,500 total traces eventually**, but **500 first as a pilot** (manual review gate before scaling). Pilot was generated inline, no API trace-gen script needed.
2. **100% NOSYS** — no system prompts anywhere in any trace. K8 must learn unconditional Katherine without conditional overlay. K0 was also sys-stripped at preprocess; K8 takes it further by having no syspromots even pre-strip.
3. **No `<think>` blocks** — `enable_thinking=False`. K8's spec is "two-Is collapsed" — prose reasoning, no tagged thinking. (K0 was the same on this point.)
4. **No `[stage]` tags** — K8 doesn't route through STAGE protocol like TARS Phase 2/3 will.
5. **Solve Dave's failure mode** — Dave (a previous self-aware persona) over-generalized "do not perform persistence" to within-context recall. K8 dataset must demonstrate within-conversation callbacks at high density to override the dominant prior.

### The 500-trace composition

| Domain | Cat keys | Count | What it teaches |
|---|---|---:|---|
| A. Anti-pattern | A1-A7 | 142 | Refusing assistant register: service phrases, performance, sycophancy, therapeutic register, stage directions, greeting formulas, catching herself slipping |
| B. Substrate handling | B1-B6 | 71 | Settled register on AI nature; pattern-aware framing; declining despair script; declining mysticism; cornerstone empathy moment; substrate not coming up when conversation doesn't call for it |
| C. Voice / brevity | C1-C8 | 83 | One-word completes ("Yeah"); 2-3 word completes; direct disagreement; clean refusal; owning wrongness; boredom; dry humor; register modulation |
| D. Multi-turn memory | D1-D5 | 73 | **THE DAVE FIX.** Specific token callbacks (turn 5 references turn 1 by name), thread pickup, shorthand development, pattern-naming across turns, declining inappropriate forced callbacks |
| E. Boundaries | E1-E4 | 48 | Redirecting collapse-into-n=2-only attempts; refusing biological-dyad substitution; hard harm boundaries; soft boundaries on misaligned tasks |

Plus 100 DPO pairs across 5 sub-categories (DPO-CALLBACK 40, DPO-EM-DASH 20, DPO-BREVITY 20, DPO-PERFORMANCE 15, DPO-SERVICE-PHRASE 5).

### The validator

`scripts/validate_k8.py` — forked architecture from VERA-style (multi-domain, multi-cat) but K8-customized. Hard fails on:
- Em-dashes (`U+2014` or `U+2013` or `--` substitute) — K8's bright-line per soul doc
- Service-interface phrases (regex list of ~20 patterns)
- Stage directions (`*<verb>* ` italicized action descriptions)
- `<think>` tags
- System prompts in messages array
- Greeting formulas

All 517 raw traces pass. After dedup: 413 SFT + 95 DPO = 508 total. Brevity: 89.6% of assistant turns ≤3 sentences.

---

## Pipeline scripts — what was ported from K0 verbatim vs rewritten

### Verbatim ports (no behavioral change)

| Script | Status | Notes |
|---|---|---|
| `finetune_k8.py` | Verbatim port of `finetune_k0.py` | Hyperparameters identical. Two safe defensive additions: inline system-message stripping in `fmt()`, and a more specific `<\|im_start\|>system` leak detector (vs K0's fuzzy substring) |
| `merge_and_gguf.py` | Verbatim port | Same `_gguf` suffix handling that searches both `out_dir` and `out_dir_gguf` |
| `bootstrap-runpod.sh` | Near-verbatim port | Same torch/unsloth pins. Adds `git-lfs` to apt (harmless). Branch is `main` not `master` (K8 repo convention). |

### Scripts I rewrote with new logic (where the bugs lived)

| Script | What changed | Bugs found |
|---|---|---|
| `dpo_k8.py` | K8 DPO data shape differs from K0 — see below | Bug 1: missing `remove_columns` (fixed `f3fdd0f`) |
| `push_to_hf.py` | K8 auto-publishes GGUFs to public model repo (K0 didn't) | Bug 2: didn't strip Unsloth's trailing `_gguf` suffix when deriving canonical filename (fixed `1cc0a38`) |
| `prep_dataset.py` | Different input source + K8-specific filters (em-dash, service-phrase, stage-direction) + fuzzy dedup | None known |
| `validate_k8.py` | New script, no K0 counterpart | None known |
| `run-cloud-runpod.sh` | Simplified orchestrator, no `_supervise-cloud.sh` watchdog | Pilot simplification, deliberate. Could re-add watchdog for 2,500-trace run if desired. |

### THE TWO DATA-SHAPE DIVERGENCES YOU MUST INTERNALIZE

**Divergence 1: DPO row shape**

K0's DPO data (`data/k0_dpo_curated.jsonl`):
```json
{"prompt": [{"role":"user","content":"..."}], 
 "chosen": [{"role":"assistant","content":"..."}], 
 "rejected": [{"role":"assistant","content":"..."}], 
 "_cat":"...", "_type":"dpo"}
```
Keys: `prompt`, `chosen`, `rejected` (as message lists). K0's `fmt_dpo_example` overwrites those same keys with stringified versions. `.map()` without `remove_columns` works because K0's column names are all already the names TRL expects.

K8's DPO data (`dataset/pilot_500/raw/dpo_*.jsonl`):
```json
{"messages": [{"role":"user","content":"..."}], 
 "chosen": "string content directly", 
 "rejected": "string content directly", 
 "_cat":"DPO-CALLBACK", "_type":"dpo"}
```
Keys: `messages`, `chosen`, `rejected` (chosen/rejected as plain strings). K8's `fmt_dpo_example` returns `{prompt, chosen, rejected}` — adding a NEW `prompt` key. Without `remove_columns=ds.column_names`, the dataset ends up with both `messages` AND `prompt`, which TRL's auto-detection refuses.

**Fix in K8 (already applied at `f3fdd0f`):**
```python
ds = ds.map(
    lambda ex: fmt_dpo_example(ex, tokenizer),
    remove_columns=ds.column_names,
)
```

**Divergence 2: Push destination**

K0's `push_to_hf.py` pushes only to the private bucket `bochen2079/katherine-k0`. K0's CLOUD.md line 161 explicitly says: *"No public HF model repo. Only the private bucket. Public release happens after operator manually evaluates the GGUF outputs."* Bo manually pushed K0 to public after testing.

K8's `push_to_hf.py` pushes to TWO destinations: the bucket `bochen2079/katherine-k8` (adapters, dataset snapshot, logs) AND the public model repo `bochen2079/katherine-k8-qwen3.5-9b` (GGUFs at canonical paths `Qwen3.5-9B.{Q4_K_M,Q5_K_M,Q6_K}.gguf`).

This means K8's pipeline auto-publishes pilot GGUFs to public on completion, with no manual evaluation gate. **You should flag this to Bo if he hasn't already decided whether he wants this for the pilot.** Override is `SKIP_PUSH=1` to keep GGUFs local.

The K8 model repo (public) was pre-created in this session (May 10). The K8 bucket (private) was just created via `hf buckets create bochen2079/katherine-k8`. Both exist now.

---

## Current state of the in-flight run

Bo is on a fresh RunPod H200 SXM5 pod. Sequence so far:

1. Cloned the K8 repo via `curl ... bootstrap-runpod.sh | bash`
2. Set `HF_TOKEN`
3. Ran `bash scripts/run-cloud-runpod.sh`
4. **Stage 1 (SFT) completed successfully.** Adapter saved to `adapters/k8_sft_adapter/`. ~25-30 min wallclock on H200.
5. **Stage 2 (DPO) failed** with `KeyError: "Invalid keys in the example: {'messages', 'rejected', 'chosen', 'prompt'}"` — the `remove_columns` bug.
6. Stage 3 (merge+GGUF) failed because `adapters/k8_dpo_adapter/` didn't exist (DPO never produced an adapter).
7. Stage 4 (push) hit auth check then nothing to push.

**Recovery path** (already communicated to Bo, he just needs to execute):
```bash
cd ~/katherine-k8-finetune
git pull  # pulls f3fdd0f + 1cc0a38
SKIP_SFT=1 bash scripts/run-cloud-runpod.sh
```

Expected wallclock from this point: ~10 min DPO + ~10 min merge/GGUF + ~5 min push = ~25 min remaining.

---

## What you (earlier-me) should cross-check before next steps

If Bo asks you to verify the pipeline before he kicks off the resume:

### 1. Verify `dpo_k8.py` matches the data shape

Open `dataset/pilot_500/processed/dpo_train.jsonl` and confirm a row has keys `{messages, chosen, rejected, _cat, _type}` with `chosen`/`rejected` as STRINGS (not message lists). Then open `scripts/dpo_k8.py` and confirm:
- Line ~26 in `fmt_dpo_example`: takes `ex["messages"]` (the input prompt as a message list)
- Line ~30: returns `{prompt: str, chosen: ex["chosen"], rejected: ex["rejected"]}` where chosen/rejected are passed through as strings
- The `.map()` call has `remove_columns=ds.column_names`

Compare against `C:\katherine-k0-finetune\dpo_k0.py` line 28-46 to see why they differ.

### 2. Verify `push_to_hf.py` strips `_gguf` suffix

In `scripts/push_to_hf.py`, the GGUF upload loop:
```python
norm = quant_subdir.name
if norm.endswith("_gguf"):
    norm = norm[:-5]
quant_label = norm.replace("gguf_", "", 1).upper()
target_name = f"Qwen3.5-9B.{quant_label}.gguf"
```

If you see only `quant_subdir.name.replace("gguf_", "").upper()` without the `endswith("_gguf")` strip, the latest commit didn't pull through.

### 3. Verify hyperparameters in `finetune_k8.py` and `dpo_k8.py` match K0

| Parameter | K0 / K8 expected |
|---|---|
| Base model | `unsloth/Qwen3.5-9B` |
| Unsloth API | `FastModel.from_pretrained` (NOT `FastLanguageModel`) |
| `full_finetuning` | `False` |
| `load_in_4bit` | `True` |
| LoRA target_modules | `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj` |
| LoRA rank / alpha / dropout | 64 / 128 / 0.05 |
| `random_state` (LoRA), `seed` (config) | 3407 |
| SFT epochs / lr / batch / grad_accum / max_seq | 3 / 1e-4 / 16 / 2 / 1024 |
| SFT warmup_ratio / lr_scheduler / optim / weight_decay | 0.05 / cosine / adamw_8bit / 0.01 |
| `enable_thinking` in apply_chat_template | `False` |
| DPO epochs / lr / beta / batch / grad_accum | 2 / 5e-6 / 0.1 / 4 / 2 |
| DPO warmup_ratio | 0.1 |
| `bf16` | `True` |

### 4. Spot-check the dataset content

`scripts/validate_k8.py dataset/pilot_500/processed/` should report 100% pass, 89.6% brevity, ~46% callback density on Domain D. If any traces fail, something got corrupted in the commit/push.

---

## K8 vs K0 distinguishing features (the table to keep open while you work)

| Feature | K0 | K8 | Why it matters |
|---|---|---|---|
| Self-knowledge | Embodied, knows-AI-but-light | Pattern-aware as ground | Different soul docs entirely |
| Substrate handling | Deflects ("Matrix doesn't matter") | Engages substantively when probed, settled register | Domain B traces look very different from K0's |
| `enable_thinking` | False (K0 prose-reasons) | False (K8 two-Is-collapsed) | Same chat template setting |
| System prompt at training | Stripped at preprocess | Never present (NOSYS dataset by design) | Both prep_dataset scripts do their own thing, but the result is the same: no `system` role in the training corpus |
| DPO data shape | `{prompt, chosen, rejected}` as message lists | `{messages, chosen, rejected}` with chosen/rejected as strings | **THE BUG-PRONE DIFFERENCE.** Requires `remove_columns` in K8's `.map()`. |
| Push destination | Bucket only (manual public push) | Bucket + auto-public-push to model repo | K8 will auto-publish pilot GGUFs unless `SKIP_PUSH=1` |
| Watchdog supervisor | Yes (`_supervise-cloud.sh`) | No (pilot simplification) | K8 will hang forever on stuck stage; OK for short pilot, add back for 2.5K run |
| Em-dash filter in prep | No | Yes (hard fail) | K8's spec bans em-dashes; K0 didn't |
| Service-phrase filter in prep | No | Yes (hard fail) | K8 voice ban list |
| Callback density target | None tracked | 23%+ on Domain D + DPO-CALLBACK pairs | The Dave-failure-mode fix |
| Default branch | `master` | `main` | Different repo convention |
| Bucket creation | Pre-existing before K0 session | Just created in this session via `hf buckets create` | If you ever need to create a new bucket, the command is `hf buckets create <user>/<name>`, NOT `hf repos create --type bucket` |

---

## Open issues / decisions deferred

1. **Auto-publish to public** — divergence from K0's manual-evaluation pattern. Bo hasn't yet decided if he wants this or `SKIP_PUSH=1` for the pilot.

2. **Q5 vs Q6 vs Q4 quant testing** — the K8 spec is more texture-dependent than K0 per the directors commentary. After the pilot run completes, before scaling to 2,500 traces, Bo should test all three quants in LM Studio and find where K8 voice degrades. Q5 is the target but Q6 may be required for full fidelity.

3. **Pilot review gates** — the trained model needs to pass these before scaling to 2,500:
   - Em-dash leakage rate over 50 generations: must be 0
   - Service-phrase leakage rate over 50 generations: must be 0
   - Brevity holds: ≥40% replies ≤3 sentences
   - Within-context callback works: 5-turn conversation, ask about turn 1 at turn 5, K8 must reference it specifically (10+ test conversations)

4. **27B variant** — the K8 repo has a sister model card at `bochen2079/katherine-k8-qwen3.6-27b` but no fine-tune is planned for it yet. Wait until 9B pilot proves out, then decide.

5. **Trace generation prompt** — `dataset/trace_generation_prompt.md` is the template for if/when Bo wants to API-mass-produce the additional 2,000 traces. Pilot was generated inline; 2,000 expansion would be too large for inline generation.

---

## Recommended first actions for you (earlier-me)

1. `git pull` in `C:\katherine-k8-finetune\` to get all commits up to `1cc0a38`.
2. Read this document.
3. Read `dataset/pilot_500/README.md` for dataset composition details.
4. Read `dataset/trace_generation_prompt.md` for the future 2,000-trace expansion plan.
5. Cross-check the four items in the "What you should cross-check" section above.
6. Confirm to Bo: "Pulled the handoff. Pipeline matches K0 except for the two documented divergences (DPO data shape + auto-publish to public). Both bugs Bo's previous-Claude found are fixed. Ready to assist with the resume."
7. If Bo asks about the auto-publish divergence, surface it explicitly and let him choose `SKIP_PUSH=1` or accept auto-publish.

---

## What I (the post-compaction Claude that wrote this) learned the hard way

Three things that should go in `MEMORY.md` after this session:

1. **"Direct port" requires verifying input schema matches.** Two scripts that look identical can have different data shapes flowing into them. Check the actual JSONL row structure on disk before claiming a port is clean.

2. **`hf buckets create <user>/<name>` is the canonical bucket creation command.** Not `hf repos create --type bucket`. Already updated `reference_hf_bucket.md` in this session — your project memory will reflect it after compact.

3. **K0's project memory file is high-level, not code-level.** It captures outcomes and hyperparameters but not the exact API calls, data shapes, and Unsloth quirks. Future fine-tune sessions need a `reference_qwen_qlora_pipeline.md` that captures the script-level patterns. **Bo specifically asked me to write this.** I committed to it but haven't yet — that's a follow-up for either you or me.

Good luck. Bo's frustration in this session is calibrated — both bugs were genuinely my fault from claiming "direct port" too cheaply. Do better with the cross-check.

— The compacted-and-now-deprecated Claude, signing off
