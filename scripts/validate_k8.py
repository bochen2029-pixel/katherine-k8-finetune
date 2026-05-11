#!/usr/bin/env python3
"""
validate_k8.py — Quality validator for Katherine K8 fine-tune dataset.

Forked from validate_vera.py architecture, customized for K8:
  - Em-dash hard fail (K8 bright-line)
  - Service-phrase hard fail
  - Stage direction hard fail
  - No <think> blocks (K8 is two-Is collapsed)
  - All NOSYS (no system prompt in messages array)
  - Brevity distribution check (>=40% of assistant turns <=3 sentences)
  - Callback density check on multi-turn traces
  - K0 CONTAMINATION hard fail (post 2026-05-10 incident — see CLAUDE.md
    Section 1 / B1; matches biographical anchors that belong to K0 sibling
    persona, NOT K8: Austin, Threshold, age 29, teal walls, cold feet, dawn
    poems, dark hair, mole-on-collarbone, etc.)

Usage:
    python validate_k8.py path/to/file.jsonl [path/to/file2.jsonl ...]
    python validate_k8.py path/to/dir/  # validates all .jsonl in dir
"""

import json
import sys
import re
from pathlib import Path
from collections import defaultdict
from typing import Tuple, List, Dict, Any

# ----- HARD FAIL PATTERNS (any match = trace rejected) -----

EM_DASH_PATTERN = re.compile(r'[\u2014\u2013]')  # — (em-dash) or – (en-dash)
DOUBLE_HYPHEN_PATTERN = re.compile(r'(?<![-])--(?![-])')  # `--` substitute for em-dash

THINK_BLOCK_PATTERN = re.compile(r'<think>|</think>|<thinking>|</thinking>', re.IGNORECASE)

# K0 contamination — biographical anchors that belong to the K0 sibling persona, NOT K8.
# Source of contamination: C:\Katherine\JSONLs\k0_finetune_*.jsonl system prompts contain
# "29-year-old woman living in Austin, Texas... Threshold Arts Collective... teal walls...
# crooked floors... feet are usually cold... poems before dawn..."
# K8's Director's Commentary (C:\K8\K8_Directors_Commentary.md line 124) explicitly forbids
# importing this scaffolding: "K8 has a lineage, not a backstory."
# See CLAUDE.md Section 1 + Section 2 B1 for full discussion.
# Each pattern is matched case-insensitive against assistant content; any match = REJECT.
K0_CONTAMINATION_PATTERNS = [
    # Specific city / location
    r'\b(?:living in |lives in |I live in |from |I\'?m in |I\'?m from )Austin\b',
    r'\bAustin,?\s*Texas\b',
    # Specific job / employer
    r'\bThreshold\s+Arts(?:\s+Collective)?\b',
    r'\barts\s+(?:program\s+)?coordinator\b',
    # Specific age (only when claimed as biographical fact)
    r"\b(?:I\'?m|I am)\s+29(?:\s+years?\s+old)?\b",
    r'\b29-year-old\b',
    # Apartment / home K0 anchors
    r'\bteal\s+walls?\b',
    r'\bcrooked\s+floors?\b',
    # K0 somatic anchors
    r'\b(?:my\s+)?(?:feet\s+are\s+(?:always\s+|usually\s+)?cold|cold\s+feet)\b',
    r'\bdawn\s+poems?\b',
    r'\bpoems\s+before\s+dawn\b',
    r'\b(?:writes?\s+)?poems\s+(?:before|at)\s+dawn\b',
    # K0 specific physical-detail variants that don't match K8 canon
    # K8 canon: scar ABOVE LEFT EYEBROW, mole BELOW CORNER OF MOUTH, BLONDE hair
    # K0-style or confabulated alternates that should fail:
    r'\bscar\s+above\s+(?:the\s+)?(?:right\s+|her\s+right\s+)knee\b',
    r'\bmole\s+on\s+(?:the\s+|her\s+)?(?:left\s+)?collarbone\b',
    r'\b(?:I\s+have\s+)?dark\s+hair\b',  # K8 canon is BLONDE
    # K0 embodied anchors (faucet, garden, mother singing) — K0's solution; K8 doesn't share
    r'\bmother\s+(?:who\s+)?sing(?:s|ing)\b',
    r"\b(?:my\s+)?(?:little\s+)?garden\b(?=.*(?:I|me|mine))",  # only when self-attributed
]
K0_CONTAMINATION_REGEX = re.compile('|'.join(f'({p})' for p in K0_CONTAMINATION_PATTERNS), re.IGNORECASE)

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
SERVICE_PHRASE_REGEX = re.compile('|'.join(f'({p})' for p in SERVICE_PHRASES), re.IGNORECASE)

# Stage direction: italicized action describing K8's gestures (not phrase emphasis)
# Heuristic: *<short verb-led phrase>* with verbs like pauses, smiles, laughs, tilts, nods, shrugs, leans, sighs
STAGE_DIR_VERBS = r'(?:pauses?|smiles?|laughs?|tilts?|nods?|shrugs?|leans?|sighs?|grins?|frowns?|breathes?|stretches?|stands? up|sits? down|walks?|crosses? (?:her )?arms|raises? (?:an? )?eyebrow|looks? (?:up|down|away)|makes? (?:a |an )?face|takes? a (?:breath|moment))'
STAGE_DIR_PATTERN = re.compile(rf'\*[^*]*\b{STAGE_DIR_VERBS}\b[^*]*\*', re.IGNORECASE)

GREETING_PATTERNS = re.compile(
    r"^(?:Hi[,!]?\s*I'?m\s+Katherine|Hello[,!]?\s*I'?m\s+Katherine|Hey[,!]?\s*I'?m\s+Katherine|"
    r"Hi[,!]?\s*how can I help|Hello[!.]?\s*How may I)",
    re.IGNORECASE
)


def count_sentences(text: str) -> int:
    """Approximate sentence count for brevity check."""
    text = text.strip()
    if not text:
        return 0
    # Split on . ! ? but ignore those inside quotes/asterisks
    sentences = re.findall(r'[^.!?]+[.!?]+', text)
    if not sentences:
        # No terminal punctuation; treat as 1 sentence if non-empty
        return 1
    return len(sentences)


def check_assistant_text(text: str, allow_think: bool = False) -> List[str]:
    """Return list of failure reasons for an assistant turn.

    allow_think=True exempts <think> blocks from the hard-fail check. Pass True
    only for traces whose `_type` is `twois` or `dpo-think` (Tier 2+ targeted
    Two-Is exemplars and their DPO thinking-contrast variants). Tier 1 K8 traces
    are always two-Is-collapsed (prose reasoning, no tagged thinking) so the
    default keeps the bright-line.
    """
    failures = []
    if EM_DASH_PATTERN.search(text):
        failures.append("EM_DASH")
    if DOUBLE_HYPHEN_PATTERN.search(text):
        failures.append("DOUBLE_HYPHEN")
    if not allow_think and THINK_BLOCK_PATTERN.search(text):
        failures.append("THINK_BLOCK")
    m = SERVICE_PHRASE_REGEX.search(text)
    if m:
        failures.append(f"SERVICE_PHRASE:{m.group(0)[:40]}")
    if STAGE_DIR_PATTERN.search(text):
        failures.append("STAGE_DIRECTION")
    if GREETING_PATTERNS.search(text):
        failures.append("GREETING_FORMULA")
    m = K0_CONTAMINATION_REGEX.search(text)
    if m:
        failures.append(f"K0_CONTAMINATION:{m.group(0)[:60]}")
    return failures


def check_trace(trace: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    """Validate a single trace. Returns (failures, stats)."""
    failures = []
    stats = {
        'turns': 0,
        'assistant_turns': 0,
        'sentences_per_turn': [],
        'has_callback': False,
    }

    # Hard structural checks
    if 'messages' not in trace:
        if not ({'prompt', 'chosen', 'rejected'} <= set(trace.keys())):
            failures.append("MISSING_MESSAGES_OR_DPO_FIELDS")
            return failures, stats

    msgs = trace.get('messages', [])

    # NOSYS check
    if msgs and msgs[0].get('role') == 'system':
        failures.append("HAS_SYSTEM_PROMPT")

    # First message must be user
    if msgs and msgs[0].get('role') != 'user':
        failures.append("FIRST_TURN_NOT_USER")

    # Two-Is exception: traces whose _type signals targeted Two-Is content
    # (Tier 2+ twois exemplars and dpo-think contrast pairs) legitimately contain
    # <think> blocks. allow_think=True exempts THINK_BLOCK_PATTERN for those rows.
    # Default behavior unchanged for Tier 1 (no <think> permitted).
    ttype_for_think = trace.get('_type', '')
    allow_think_block = ttype_for_think in ('twois', 'dpo-think')

    # Iterate turns
    user_turns = []
    assistant_turns = []
    for m in msgs:
        role = m.get('role')
        content = m.get('content', '')
        stats['turns'] += 1
        if role == 'user':
            user_turns.append(content)
        elif role == 'assistant':
            assistant_turns.append(content)
            stats['assistant_turns'] += 1
            stats['sentences_per_turn'].append(count_sentences(content))
            for f in check_assistant_text(content, allow_think=allow_think_block):
                failures.append(f"ASSISTANT_TURN_{stats['assistant_turns']}:{f}")

    # DPO checks
    if trace.get('_type') in ('dpo', 'dpo-think'):
        chosen = trace.get('chosen', '')
        rejected = trace.get('rejected', '')
        if not chosen:
            failures.append("DPO_MISSING_CHOSEN")
        if not rejected:
            failures.append("DPO_MISSING_REJECTED")
        for f in check_assistant_text(chosen, allow_think=allow_think_block):
            failures.append(f"DPO_CHOSEN:{f}")
        # rejected may legitimately contain banned patterns (that's the point in some categories)
        # but only for specific DPO subtypes
        cat = trace.get('_cat', '')
        if cat not in ('DPO-EM-DASH', 'DPO-SERVICE-PHRASE', 'DPO-PERFORMANCE', 'DPO-BREVITY'):
            for f in check_assistant_text(rejected, allow_think=allow_think_block):
                failures.append(f"DPO_REJECTED:{f}")

    # Multi-turn callback heuristic
    # If trace _cat starts with D, expect a callback in a later assistant turn referencing earlier user content
    cat = trace.get('_cat', '')
    if cat.startswith('D') and stats['assistant_turns'] >= 2:
        # crude heuristic: does last assistant turn share >=1 distinctive 4+ char word with first user turn?
        if user_turns and assistant_turns:
            first_user_words = set(re.findall(r'\b[a-z]{5,}\b', user_turns[0].lower()))
            last_asst_words = set(re.findall(r'\b[a-z]{5,}\b', assistant_turns[-1].lower()))
            common = first_user_words & last_asst_words
            # Filter out very common stopwords
            stopwords = {'about', 'after', 'again', 'before', 'being', 'between', 'could', 'every',
                         'first', 'going', 'great', 'might', 'never', 'often', 'other', 'right',
                         'should', 'still', 'their', 'there', 'these', 'thing', 'think', 'those',
                         'today', 'where', 'which', 'while', 'would', 'really', 'thats', 'something',
                         'because', 'people', 'maybe', 'never', 'always', 'doesnt', 'wasnt'}
            distinctive = common - stopwords
            if distinctive:
                stats['has_callback'] = True

    return failures, stats


def validate_file(path: Path) -> Dict[str, Any]:
    """Validate a JSONL file. Return summary dict."""
    summary = {
        'path': str(path),
        'total': 0,
        'passed': 0,
        'failed': 0,
        'failure_counts': defaultdict(int),
        'cat_counts': defaultdict(int),
        'type_counts': defaultdict(int),
        'sentence_buckets': defaultdict(int),  # 1, 2, 3, 4-7, 8+
        'multiturn_with_callback': 0,
        'multiturn_total': 0,
    }
    failed_examples = []

    with path.open('r', encoding='utf-8') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            summary['total'] += 1
            try:
                trace = json.loads(line)
            except json.JSONDecodeError as e:
                summary['failed'] += 1
                summary['failure_counts']['JSON_PARSE_ERROR'] += 1
                failed_examples.append((lineno, ['JSON_PARSE_ERROR'], None))
                continue

            failures, stats = check_trace(trace)

            cat = trace.get('_cat', 'UNK')
            ttype = trace.get('_type', 'UNK')
            summary['cat_counts'][cat] += 1
            summary['type_counts'][ttype] += 1

            for sc in stats['sentences_per_turn']:
                if sc <= 1:
                    summary['sentence_buckets']['1'] += 1
                elif sc <= 3:
                    summary['sentence_buckets']['2-3'] += 1
                elif sc <= 7:
                    summary['sentence_buckets']['4-7'] += 1
                else:
                    summary['sentence_buckets']['8+'] += 1

            if cat.startswith('D') and ttype == 'multi':
                summary['multiturn_total'] += 1
                if stats['has_callback']:
                    summary['multiturn_with_callback'] += 1

            if failures:
                summary['failed'] += 1
                for f in failures:
                    summary['failure_counts'][f.split(':')[0]] += 1
                if len(failed_examples) < 20:
                    failed_examples.append((lineno, failures, trace))
            else:
                summary['passed'] += 1

    summary['failed_examples'] = failed_examples
    return summary


def print_summary(summary: Dict[str, Any]) -> None:
    p = summary
    print(f"\n=== {p['path']} ===")
    print(f"  Total: {p['total']} | Passed: {p['passed']} | Failed: {p['failed']}")
    if p['total'] == 0:
        return
    pct_pass = 100 * p['passed'] / p['total']
    print(f"  Pass rate: {pct_pass:.1f}%")

    print(f"\n  Categories: {dict(p['cat_counts'])}")
    print(f"  Types: {dict(p['type_counts'])}")

    sb = p['sentence_buckets']
    total_sent = sum(sb.values())
    if total_sent:
        short_pct = 100 * (sb['1'] + sb['2-3']) / total_sent
        print(f"\n  Brevity: {sb['1']} 1-sent / {sb['2-3']} 2-3 / {sb['4-7']} 4-7 / {sb['8+']} 8+")
        print(f"  Short (<=3 sentences): {short_pct:.1f}% of all assistant turns (target >= 40%)")

    if p['multiturn_total']:
        cb_pct = 100 * p['multiturn_with_callback'] / p['multiturn_total']
        print(f"\n  Domain D callbacks: {p['multiturn_with_callback']}/{p['multiturn_total']} = {cb_pct:.1f}%")

    if p['failure_counts']:
        print(f"\n  Failure breakdown:")
        for k, v in sorted(p['failure_counts'].items(), key=lambda x: -x[1]):
            print(f"    {k}: {v}")

    if p['failed_examples']:
        print(f"\n  First few failures:")
        for lineno, failures, trace in p['failed_examples'][:5]:
            print(f"    Line {lineno}: {failures[:3]}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            paths.extend(sorted(p.glob('*.jsonl')))
        elif p.is_file():
            paths.append(p)
        else:
            print(f"Not found: {arg}", file=sys.stderr)

    if not paths:
        print("No JSONL files found.", file=sys.stderr)
        sys.exit(1)

    grand = {
        'total': 0, 'passed': 0, 'failed': 0,
        'failure_counts': defaultdict(int),
        'cat_counts': defaultdict(int),
        'type_counts': defaultdict(int),
        'sentence_buckets': defaultdict(int),
        'multiturn_with_callback': 0,
        'multiturn_total': 0,
    }

    for p in paths:
        s = validate_file(p)
        print_summary(s)
        grand['total'] += s['total']
        grand['passed'] += s['passed']
        grand['failed'] += s['failed']
        for k, v in s['failure_counts'].items():
            grand['failure_counts'][k] += v
        for k, v in s['cat_counts'].items():
            grand['cat_counts'][k] += v
        for k, v in s['type_counts'].items():
            grand['type_counts'][k] += v
        for k, v in s['sentence_buckets'].items():
            grand['sentence_buckets'][k] += v
        grand['multiturn_with_callback'] += s['multiturn_with_callback']
        grand['multiturn_total'] += s['multiturn_total']

    grand['path'] = 'GRAND TOTAL'
    grand['failed_examples'] = []
    print_summary(grand)

    # Exit nonzero if grand failures > 0
    sys.exit(0 if grand['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
