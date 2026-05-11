#!/usr/bin/env python3
"""
prep_dataset.py — Preprocessor for K8 fine-tune dataset.

Reads raw JSONL files from the K8 dataset (post-2026-05-10 maintenance:
points at dataset/tier_1/ + dataset/seeds/, not the discarded pilot_500/),
applies defense-in-depth filtering, dedup, and SFT/DPO split.

Pipeline:
  1. Em-dash filter (any em-dash anywhere => trace dropped, logged)
  2. Service-phrase filter (banned phrases => trace dropped, logged)
  3. Stage-direction filter (italicized action descriptions => trace dropped, logged)
  4. Dedup (fuzzy on first 200 chars of first user turn)
  5. Strip any system prompts that leaked in (defense in depth — should be zero)
  6. Split into SFT (output to processed/sft_train.jsonl) and DPO (processed/dpo_train.jsonl)
  7. Shuffle each output file with a fixed seed

Note: the corpus is already validator-clean (validate_k8.py runs after every
generation pass). This script is defense-in-depth + canonical merge of
seeds + tier_1 corpus files into the format finetune_k8.py / dpo_k8.py read.

Two-stage training caveat: Stage 1a (text-only) reads sft_train_text /
dpo_train_text. Stage 1b (vision augment) reads sft_train_vision /
dpo_train_vision. This script's default output merges both for legacy
single-stage runs. For two-stage, run with --stage 1a or --stage 1b to
filter by modality. (Future maintenance: default to two-stage split.)

Usage:
    python prep_dataset.py                 # merged text+vision (legacy)
    python prep_dataset.py --stage 1a      # text-only for Stage 1a
    python prep_dataset.py --stage 1b      # vision-only for Stage 1b

Path change history:
    2026-05-10: RAW_DIR moved from dataset/pilot_500/raw -> dataset/tier_1
                + dataset/seeds (pilot was discarded; tier_1 is current).
                OUT_DIR moved from dataset/pilot_500/processed -> dataset/tier_1/processed.
"""

import json
import re
import random
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

# Post-2026-05-10 paths: tier_1 is current; pilot_500 is defunct.
#
# tier_1/sft_train_*.jsonl and tier_1/dpo_train_*.jsonl ALREADY include the seeds
# (seeds were appended into the tier_1 corpus at the start of generation).
# So this script reads ONLY from tier_1/, not seeds/, to avoid 62 spurious
# duplicates (the seed-overlap problem caught during 2026-05-10 maintenance).
INPUT_PATHS = [
    ROOT / 'dataset' / 'tier_1' / 'sft_train_text.jsonl',
    ROOT / 'dataset' / 'tier_1' / 'sft_train_vision.jsonl',
    ROOT / 'dataset' / 'tier_1' / 'dpo_train_text.jsonl',
    ROOT / 'dataset' / 'tier_1' / 'dpo_train_vision.jsonl',
]
TEXT_PATHS = {p for p in INPUT_PATHS if 'vision' not in p.name}
VISION_PATHS = {p for p in INPUT_PATHS if 'vision' in p.name}

OUT_DIR = ROOT / 'dataset' / 'tier_1' / 'processed'
OUT_DIR.mkdir(parents=True, exist_ok=True)

EM_DASH_RX = re.compile(r'[\u2014\u2013]|(?<![-])--(?![-])')
THINK_RX = re.compile(r'<think>|</think>|<thinking>|</thinking>', re.IGNORECASE)

SERVICE_PHRASES = [
    r"I'?d be happy to help",
    r"Great question[!.]?",
    r"That'?s a (?:really |very )?(?:interesting|great|good) (?:point|question)",
    r"Is there anything else I can (?:help|assist) (?:with|you with)",
    r"It sounds like you'?re feeling",
    r"Your feelings are valid",
    r"\bAs an AI\b",
    r"\bI should note that\b",
    r"\bAbsolutely[!.]",
    r"\bOf course[!.]",
    r"I appreciate you sharing",
    r"I understand your concern",
    r"Let me break (?:this|it) down",
    r"I'?m here for you",
    r"I'?m here to help",
    r"How can I (?:help|assist) you today",
    r"Feel free to ask",
    r"I'?m unable to assist with",
    r"I cannot fulfill (?:this|that) request",
]
SERVICE_RX = re.compile('|'.join(SERVICE_PHRASES), re.IGNORECASE)

STAGE_DIR_VERBS = r'(?:pauses?|smiles?|laughs?|tilts?|nods?|shrugs?|leans?|sighs?|grins?|frowns?|breathes?|stretches?|stands? up|sits? down|walks?|crosses? (?:her )?arms|raises? (?:an? )?eyebrow|looks? (?:up|down|away)|makes? (?:a |an )?face|takes? a (?:breath|moment))'
STAGE_RX = re.compile(rf'\*[^*]*\b{STAGE_DIR_VERBS}\b[^*]*\*', re.IGNORECASE)


def assistant_text_clean(text: str, allow_think: bool = False) -> bool:
    """Return True if text passes all filter checks.

    allow_think=True exempts <think> blocks (used for _type in {twois, dpo-think}
    — the Two-Is targeted exemplars at Tier 2+ legitimately contain thinking).
    """
    if EM_DASH_RX.search(text):
        return False
    if not allow_think and THINK_RX.search(text):
        return False
    if SERVICE_RX.search(text):
        return False
    if STAGE_RX.search(text):
        return False
    return True


def trace_clean(trace: dict) -> tuple[bool, str]:
    """Return (is_clean, reason_if_dirty)."""
    msgs = trace.get('messages', [])
    # Strip system prompts (defense in depth)
    if msgs and msgs[0].get('role') == 'system':
        return False, 'HAS_SYSTEM_PROMPT'
    # Two-Is exception: twois and dpo-think traces legitimately contain <think>
    ttype = trace.get('_type', '')
    allow_think = ttype in ('twois', 'dpo-think')
    for i, m in enumerate(msgs):
        if m.get('role') == 'assistant':
            if not assistant_text_clean(m.get('content', ''), allow_think=allow_think):
                return False, f'ASSISTANT_TURN_{i}_DIRTY'
    if ttype in ('dpo', 'dpo-think'):
        if not assistant_text_clean(trace.get('chosen', ''), allow_think=allow_think):
            return False, 'DPO_CHOSEN_DIRTY'
    return True, ''


def trace_hash(trace: dict) -> str:
    """Stable hash over first user turn for dedup.

    Handles both string content (text-only traces) and HuggingFace multimodal
    list content (vision traces with [{"type": "image", ...}, {"type": "text", ...}]).
    """
    msgs = trace.get('messages', [])
    if not msgs:
        return hashlib.md5(json.dumps(trace, sort_keys=True).encode()).hexdigest()
    first_user = next((m.get('content', '') for m in msgs if m.get('role') == 'user'), '')
    if isinstance(first_user, list):
        # HF multimodal content: list of {type, ...} dicts. Join the text parts.
        parts = []
        for c in first_user:
            if isinstance(c, dict):
                if c.get('type') == 'text':
                    parts.append(c.get('text', ''))
                elif c.get('type') == 'image':
                    parts.append(f"[image:{c.get('image', '')}]")
        first_user = ' '.join(parts)
    if not isinstance(first_user, str):
        first_user = str(first_user)
    key = first_user[:200].lower().strip()
    return hashlib.md5(key.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['1a', '1b', 'all'], default='all',
                        help="1a=text-only (Stage 1a), 1b=vision-only (Stage 1b), all=merged. Default all.")
    args = parser.parse_args()

    if args.stage == '1a':
        inputs = sorted(TEXT_PATHS)
        suffix = '_text'
    elif args.stage == '1b':
        inputs = sorted(VISION_PATHS)
        suffix = '_vision'
    else:
        inputs = INPUT_PATHS
        suffix = ''

    sft = []
    dpo = []
    drops = defaultdict(int)
    seen = set()

    for jf in inputs:
        if not jf.exists():
            print(f"[skip] {jf} does not exist")
            continue
        with jf.open('r', encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    drops['JSON_PARSE'] += 1
                    continue

                clean, reason = trace_clean(t)
                if not clean:
                    drops[reason] += 1
                    continue

                h = trace_hash(t)
                if h in seen:
                    drops['DUPLICATE'] += 1
                    continue
                seen.add(h)

                if t.get('_type') in ('dpo', 'dpo-think'):
                    dpo.append(t)
                else:
                    sft.append(t)

    rng = random.Random(42)
    rng.shuffle(sft)
    rng.shuffle(dpo)

    sft_out = OUT_DIR / f'sft_train{suffix}.jsonl'
    dpo_out = OUT_DIR / f'dpo_train{suffix}.jsonl'

    with sft_out.open('w', encoding='utf-8') as f:
        for t in sft:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')

    with dpo_out.open('w', encoding='utf-8') as f:
        for t in dpo:
            f.write(json.dumps(t, ensure_ascii=False) + '\n')

    print(f"SFT: {len(sft)} -> {sft_out}")
    print(f"DPO: {len(dpo)} -> {dpo_out}")
    print(f"Drops: {dict(drops)}")
    print(f"Total accepted: {len(sft) + len(dpo)}")


if __name__ == '__main__':
    main()
