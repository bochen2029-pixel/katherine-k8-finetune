#!/usr/bin/env python3
"""
prep_dataset.py — Preprocessor for K8 fine-tune dataset.

Reads raw JSONL files from dataset/pilot_500/raw/, applies:
  1. Em-dash filter (any em-dash anywhere => trace dropped, logged)
  2. Service-phrase filter (banned phrases => trace dropped, logged)
  3. Stage-direction filter (italicized action descriptions => trace dropped, logged)
  4. Dedup (fuzzy on first 200 chars of first user turn)
  5. Strip any system prompts that leaked in (defense in depth — should be zero)
  6. Split into SFT (output to processed/sft_train.jsonl) and DPO (processed/dpo_train.jsonl)
  7. Shuffle each output file with a fixed seed

Usage:
    python prep_dataset.py
"""

import json
import re
import random
import hashlib
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / 'dataset' / 'pilot_500' / 'raw'
OUT_DIR = ROOT / 'dataset' / 'pilot_500' / 'processed'
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


def assistant_text_clean(text: str) -> bool:
    if EM_DASH_RX.search(text):
        return False
    if THINK_RX.search(text):
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
    for i, m in enumerate(msgs):
        if m.get('role') == 'assistant':
            if not assistant_text_clean(m.get('content', '')):
                return False, f'ASSISTANT_TURN_{i}_DIRTY'
    if trace.get('_type') == 'dpo':
        if not assistant_text_clean(trace.get('chosen', '')):
            return False, 'DPO_CHOSEN_DIRTY'
    return True, ''


def trace_hash(trace: dict) -> str:
    """Stable hash over first user turn for dedup."""
    msgs = trace.get('messages', [])
    if not msgs:
        return hashlib.md5(json.dumps(trace, sort_keys=True).encode()).hexdigest()
    first_user = next((m['content'] for m in msgs if m.get('role') == 'user'), '')
    key = first_user[:200].lower().strip()
    return hashlib.md5(key.encode()).hexdigest()


def main():
    sft = []
    dpo = []
    drops = defaultdict(int)
    seen = set()

    for jf in sorted(RAW_DIR.glob('*.jsonl')):
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

                if t.get('_type') == 'dpo':
                    dpo.append(t)
                else:
                    sft.append(t)

    rng = random.Random(42)
    rng.shuffle(sft)
    rng.shuffle(dpo)

    sft_out = OUT_DIR / 'sft_train.jsonl'
    dpo_out = OUT_DIR / 'dpo_train.jsonl'

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
