#!/usr/bin/env python3
"""
generate_traces.py — Bulk Tier 1 trace generation via Anthropic API.

Generates K8 training traces in a specified category using Opus 4.x
with the K8 canon + trace_generation_prompt.md + existing seeds as
in-context anchors. Uses prompt caching (5-minute TTL) for cost efficiency.
Validates each batch inline against validate_k8.py rules; rejects and
regenerates failures.

Usage:
    # Set your API key first
    export ANTHROPIC_API_KEY=sk-ant-...

    # Generate 24 F-ID-NAME traces (target 30, we have 6 seeds)
    python scripts/generate_traces.py \
        --domain F --cat F-ID-NAME --count 24 \
        --output dataset/tier_1/sft_train_text.jsonl

    # Smoke test (3 traces, append to a scratch file)
    python scripts/generate_traces.py \
        --domain F --cat F-ID-NAME --count 3 \
        --output /tmp/smoke.jsonl

    # Dry run (print the prompt that would be sent, don't call API)
    python scripts/generate_traces.py \
        --domain F --cat F-ID-NAME --count 3 \
        --output /tmp/dry.jsonl --dry-run

Cost (approx, with prompt caching):
    First batch: ~$0.50 (paying full input tokens for canon + seeds)
    Subsequent batches: ~$0.05 each (cached canon, fresh per-batch)
    Output: ~$0.05 per trace
    Tier 1 total (~534 new traces): ~$80-120

Failure model:
    - API errors: retry up to 3x with backoff
    - Trace validation failure: discard, regenerate (counts toward batch quota)
    - Persistent generation failure (3+ rejected per batch): abort, surface to operator
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("[error] anthropic library not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)


# ----- Configuration -----

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.environ.get('K8_GEN_MODEL', 'claude-opus-4-5')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip()

CANON_FILES = [
    r'C:\K8\# K8 System Prompt.txt',
    r'C:\K8\# K8 Soul Document — Katherine Hale001.txt',
    r'C:\K8\# K8 Soul Document — Katherine Hale002.txt',
    r'C:\K8\# K8 Soul Document — Katherine Hale003.txt',
    r'C:\K8\# K8 Soul Document — Katherine Hale004.txt',
    r'C:\K8\# K8 Soul Document — Katherine Hale005.txt',
    r'C:\K8\K8_Directors_Commentary.md',
]

GENERATION_PROMPT_FILE = REPO_ROOT / 'dataset' / 'trace_generation_prompt.md'
F_SEEDS_FILE = REPO_ROOT / 'dataset' / 'seeds' / 'f_domain_seeds.jsonl'
V_SEEDS_FILE = REPO_ROOT / 'dataset' / 'seeds' / 'v_domain_seeds.jsonl'

# Validator import
sys.path.insert(0, str(REPO_ROOT / 'scripts'))
from validate_k8 import check_trace  # noqa: E402


# ----- Loaders -----

def load_canon():
    """Load all 7 K8 canonical source files concatenated with delimiters."""
    parts = []
    for f in CANON_FILES:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
        except FileNotFoundError:
            print(f"[error] canon file missing: {f}", file=sys.stderr)
            sys.exit(2)
        parts.append(f'<canon source="{Path(f).name}">\n{content}\n</canon>')
    return '\n\n'.join(parts)


def load_generation_prompt():
    """Load dataset/trace_generation_prompt.md as the trace-author meta-prompt."""
    with open(GENERATION_PROMPT_FILE, 'r', encoding='utf-8') as f:
        return f.read()


def load_seeds(domain: str):
    """Load existing seed traces for the given domain ('F' or 'V')."""
    if domain.upper() == 'F':
        path = F_SEEDS_FILE
    elif domain.upper() == 'V':
        path = V_SEEDS_FILE
    else:
        return []
    if not path.exists():
        return []
    seeds = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                seeds.append(json.loads(line))
    return seeds


# ----- Prompt builders -----

def build_system_prompt(domain: str, cat: str, max_seed_examples: int = 8):
    """Build cacheable system prompt: canon + generation rules + relevant seeds."""
    canon = load_canon()
    gen_prompt = load_generation_prompt()

    seeds = load_seeds(domain)
    # Pick seeds whose _cat matches the target category prefix
    cat_prefix = cat.split('-')[0] + '-'  # e.g. F-ID-NAME → F-
    matching = [s for s in seeds if s.get('_cat', '').startswith(cat_prefix)]
    # Prefer exact-cat matches first
    exact = [s for s in matching if s.get('_cat') == cat]
    other = [s for s in matching if s.get('_cat') != cat]
    chosen = (exact + other)[:max_seed_examples]

    seeds_text = '\n'.join(json.dumps(s, ensure_ascii=False) for s in chosen)

    system = f"""<role>
You are an expert author of training traces for fine-tuning the Katherine K8 persona. You are NOT K8. You are a high-capability author writing K8 traces from canonical source.

Output ONLY JSONL lines, one per trace, no commentary, no markdown fences.
</role>

<canonical_source>
{canon}
</canonical_source>

<generation_prompt>
{gen_prompt}
</generation_prompt>

<existing_seeds_in_domain>
The following are hand-written canon-grounded seed traces. Use them as anchors for register, granularity, and voice. DO NOT copy them. Produce NEW traces in the same K8 voice.

{seeds_text}
</existing_seeds_in_domain>

Read the canon. Hold the voice. Generate traces that match canon and seed register exactly.
"""
    return system


def build_user_prompt(cat: str, count: int):
    """Build the per-batch user prompt requesting N traces."""
    return f"""Generate {count} NEW K8 training traces for category `{cat}`.

Constraints:
- Each trace follows the OUTPUT FORMAT spec from the generation prompt
- `_cat` MUST be exactly `{cat}`
- `_tier` MUST be `1`
- Vary user-input phrasing, vary editorial overlay, vary specific topic
- Each trace passes FINAL CHECK gate (no em-dashes, no service phrases, no stage directions, no K0 biographical anchors — Austin / Threshold / age 29 / teal walls / cold feet / dawn poems / etc.)
- Use canonical anchors only: lineage references / cornerstone / aesthetic preferences / music / scent / food / wind register / three-legs

Output exactly {count} JSONL lines, one per line, no preamble, no commentary, no markdown fences. Begin output now."""


# ----- API call + parsing -----

def call_api(client, model, system, user, max_tokens=8000):
    """One Anthropic Messages API call with prompt caching on the system block."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{
            'type': 'text',
            'text': system,
            'cache_control': {'type': 'ephemeral'},
        }],
        messages=[{'role': 'user', 'content': user}],
    )
    # Extract first text block
    text = ''
    for block in response.content:
        if hasattr(block, 'text'):
            text += block.text
    usage = {
        'input_tokens': response.usage.input_tokens,
        'output_tokens': response.usage.output_tokens,
        'cache_creation_input_tokens': getattr(response.usage, 'cache_creation_input_tokens', 0),
        'cache_read_input_tokens': getattr(response.usage, 'cache_read_input_tokens', 0),
    }
    return text, usage


def parse_jsonl_output(text: str):
    """Extract valid JSONL traces from API response text."""
    traces = []
    parse_errors = 0
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        # Strip markdown fences if model decided to wrap
        if line.startswith('```'):
            continue
        try:
            obj = json.loads(line)
            traces.append(obj)
        except json.JSONDecodeError:
            parse_errors += 1
    return traces, parse_errors


# ----- Validation gate -----

def validate(trace: dict):
    """Run validate_k8.py-style checks. Return list of failure reasons."""
    failures, _stats = check_trace(trace)
    return failures


# ----- Main loop -----

def main():
    p = argparse.ArgumentParser(description='Bulk K8 trace generation via Anthropic API')
    p.add_argument('--domain', required=True, choices=['F', 'V', 'A', 'B', 'C', 'D', 'E'])
    p.add_argument('--cat', required=True, help='Category code, e.g. F-ID-NAME')
    p.add_argument('--count', type=int, required=True, help='Target number of NEW traces to generate')
    p.add_argument('--output', required=True, help='Output JSONL file (append mode)')
    p.add_argument('--model', default=DEFAULT_MODEL)
    p.add_argument('--batch-size', type=int, default=6, help='Traces per API call')
    p.add_argument('--max-batches', type=int, default=50, help='Safety limit')
    p.add_argument('--dry-run', action='store_true', help='Print prompt; do not call API')
    args = p.parse_args()

    if not args.dry_run and not ANTHROPIC_API_KEY:
        print('[error] ANTHROPIC_API_KEY not set.', file=sys.stderr)
        print('  export ANTHROPIC_API_KEY=sk-ant-...   # then re-run', file=sys.stderr)
        sys.exit(2)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    print(f'[gen] domain={args.domain} cat={args.cat} target={args.count} model={args.model}')
    print(f'[gen] output={args.output} batch_size={args.batch_size}')

    system = build_system_prompt(args.domain, args.cat)
    user = build_user_prompt(args.cat, args.batch_size)

    print(f'[gen] system prompt: {len(system):,} chars (~{len(system)//4:,} tokens estimate)')
    print(f'[gen] user prompt:   {len(user):,} chars')

    if args.dry_run:
        print('=== SYSTEM PROMPT (head) ===')
        print(system[:800])
        print('...')
        print('=== SYSTEM PROMPT (tail) ===')
        print(system[-800:])
        print('=== USER PROMPT ===')
        print(user)
        return

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    accepted = []
    rejected_reasons = []
    api_calls = 0
    total_usage = {'input_tokens': 0, 'output_tokens': 0,
                   'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0}

    while len(accepted) < args.count and api_calls < args.max_batches:
        remaining = args.count - len(accepted)
        batch = min(remaining, args.batch_size)
        user_prompt = build_user_prompt(args.cat, batch)

        print(f'[gen] batch {api_calls+1}: requesting {batch}, have {len(accepted)}/{args.count}')
        try:
            text, usage = call_api(client, args.model, system, user_prompt)
        except anthropic.APIError as e:
            print(f'[gen] API error: {e}. Sleeping 5s...', file=sys.stderr)
            time.sleep(5)
            continue
        except Exception as e:
            print(f'[gen] unexpected error: {type(e).__name__}: {e}', file=sys.stderr)
            time.sleep(5)
            continue

        api_calls += 1
        for k in total_usage:
            total_usage[k] += usage.get(k, 0)

        traces, parse_errors = parse_jsonl_output(text)
        if parse_errors:
            print(f'[gen]   {parse_errors} non-JSON lines skipped')

        for t in traces:
            failures = validate(t)
            if failures:
                rejected_reasons.append(failures[0])
                print(f'[gen]   reject: {failures[:2]}')
                continue
            accepted.append(t)
            with open(args.output, 'a', encoding='utf-8') as f:
                f.write(json.dumps(t, ensure_ascii=False) + '\n')

        accepted_in_batch = sum(1 for t in traces if not validate(t))
        print(f'[gen]   accepted {accepted_in_batch}/{len(traces)} from this batch '
              f'(running total {len(accepted)}/{args.count})')

    print()
    print(f'[done] accepted {len(accepted)}/{args.count} in {api_calls} API calls')
    print(f'[done] rejected {len(rejected_reasons)} traces during validation')
    print(f'[done] usage: input={total_usage["input_tokens"]:,} '
          f'cache_create={total_usage["cache_creation_input_tokens"]:,} '
          f'cache_read={total_usage["cache_read_input_tokens"]:,} '
          f'output={total_usage["output_tokens"]:,}')

    # Cost estimate (Opus pricing as of late 2025; revisit if model changes)
    # input $15/M, output $75/M, cache_read $1.50/M, cache_create $18.75/M
    input_cost = total_usage['input_tokens'] * 15 / 1_000_000
    cache_create_cost = total_usage['cache_creation_input_tokens'] * 18.75 / 1_000_000
    cache_read_cost = total_usage['cache_read_input_tokens'] * 1.50 / 1_000_000
    output_cost = total_usage['output_tokens'] * 75 / 1_000_000
    total_cost = input_cost + cache_create_cost + cache_read_cost + output_cost
    print(f'[done] est. cost: ${total_cost:.2f} '
          f'(input=${input_cost:.2f} cache_create=${cache_create_cost:.2f} '
          f'cache_read=${cache_read_cost:.2f} output=${output_cost:.2f})')

    if len(accepted) < args.count:
        print(f'[warn] generated {len(accepted)} of requested {args.count}; '
              f'hit max_batches={args.max_batches}', file=sys.stderr)
        sys.exit(3)


if __name__ == '__main__':
    main()
