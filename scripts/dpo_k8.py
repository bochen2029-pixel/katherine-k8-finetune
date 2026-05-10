"""
Stage 2 — DPO trainer for Katherine K8, on top of the SFT adapter.

Derived from dpo_k0.py with these K8-specific changes:

  1. Default data path  : dataset/pilot_500/processed/dpo_train.jsonl
  2. Default sft-adapter / output paths : adapters/k8_*
  3. Source data shape  : K8 stores chosen/rejected as PLAIN STRINGS
     (not list-of-message-dicts as K0 did). The fmt function reads
     ex["chosen"] and ex["rejected"] directly without [0]["content"].
  4. CRITICAL FIX — regex strip of empty <think></think> markers in the
     formatted prompt string. Same root cause as the SFT script: Qwen3.5's
     chat template inserts these regardless of enable_thinking=False.
  5. CRITICAL FIX — explicit `.select_columns(["prompt", "chosen",
     "rejected"])` AFTER the format map. The previous K8 run failed with
     `KeyError: "Invalid keys in the example: {'messages', 'rejected',
     'chosen', 'prompt'}"` because TRL 0.24's _prepare_dataset re-adds
     'messages' from the prompt string when the prompt looks
     conversational, then refuses with both 'messages' and 'prompt'
     present. remove_columns alone is no longer sufficient defense.

Hyperparameters (unchanged from K0):
  epochs       = 2
  lr           = 5e-6     (DPO needs gentle steps)
  beta         = 0.1      (KL strength to reference; standard)
  batch        = 4 per device, grad_accum = 2 (effective 8)
  max_seq      = 1024
  optim        = adamw_8bit

DPOTrainer uses adapter-disabled forward as the reference model (PEFT trick;
saves a model copy in VRAM). The SFT adapter loaded as the policy is also
the reference snapshot.
"""
import argparse
import os
import re
import sys

from unsloth import FastModel
from datasets import load_dataset
from trl import DPOTrainer, DPOConfig


THINK_BLOCK_RE = re.compile(r'<think>\s*</think>\s*\n*', flags=re.IGNORECASE)


def fmt_dpo_example(ex, tokenizer):
    """K8 raw {messages, chosen (str), rejected (str)} → TRL standard
    {prompt (str), chosen (str), rejected (str)}.

    K8 source schema: messages ends with role:user; chosen and rejected
    are candidate assistant final-turn replies as plain strings.
    """
    msgs = ex["messages"]
    msgs = [m for m in msgs if m.get("role") != "system"]
    prompt_str = tokenizer.apply_chat_template(
        msgs,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    # Strip empty <think></think> markers Qwen3.5's chat template inserts.
    prompt_str = THINK_BLOCK_RE.sub('', prompt_str)
    return {
        "prompt": prompt_str,
        "chosen": ex["chosen"],     # already a plain string in K8 schema
        "rejected": ex["rejected"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="dataset/pilot_500/processed/dpo_train.jsonl")
    p.add_argument("--sft-adapter", default="adapters/k8_sft_adapter",
                   help="SFT adapter to load as policy starting point")
    p.add_argument("--output", default="adapters/k8_dpo_adapter")
    p.add_argument("--max_seq", type=int, default=1024)
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--lr", type=float, default=5e-6)
    p.add_argument("--beta", type=float, default=0.1)
    p.add_argument("--batch", type=int, default=4)
    p.add_argument("--grad_accum", type=int, default=2)
    p.add_argument("--skip-train", action="store_true")
    args = p.parse_args()

    if args.skip_train:
        if not os.path.isdir(args.output):
            print(f"[error] --skip-train set but DPO adapter dir not found: {args.output}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"[skip-train] DPO adapter at {args.output}")
        return

    if not os.path.isdir(args.sft_adapter):
        print(f"[error] SFT adapter not found at {args.sft_adapter}", file=sys.stderr)
        print(f"        Run finetune_k8.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"[load] base + SFT adapter: {args.sft_adapter}")
    model, tokenizer = FastModel.from_pretrained(
        model_name=args.sft_adapter,
        max_seq_length=args.max_seq,
        load_in_4bit=True,
        full_finetuning=False,
    )

    print(f"[data] loading {args.data}")
    ds = load_dataset("json", data_files=args.data, split="train")
    print(f"[data] {len(ds)} preference pairs loaded")

    # Format raw rows into the TRL-expected {prompt, chosen, rejected} string trio.
    ds = ds.map(
        lambda ex: fmt_dpo_example(ex, tokenizer),
        remove_columns=ds.column_names,
    )

    # CRITICAL DEFENSIVE: TRL 0.24's _prepare_dataset re-adds 'messages' if the
    # prompt looks conversational, then rejects with `KeyError: Invalid keys...`
    # if 'messages' AND 'prompt' coexist. select_columns explicitly lists what
    # we keep; reliable across datasets/TRL versions.
    ds = ds.select_columns(["prompt", "chosen", "rejected"])

    # Sanity: no <think> blocks should survive
    leaked = sum(1 for ex in ds if "<think>" in ex["prompt"])
    if leaked > 0:
        print(f"[FATAL] {leaked}/{len(ds)} DPO prompts contain '<think>' blocks after stripping",
              file=sys.stderr)
        sys.exit(1)
    print(f"[ok] 0/{len(ds)} DPO prompts contain <think> blocks")

    print("[sample] first DPO example:")
    print("-" * 60)
    print("prompt:  ", ds[0]["prompt"][:500])
    print("chosen:  ", ds[0]["chosen"][:300])
    print("rejected:", ds[0]["rejected"][:300])
    print("-" * 60)

    dpo_config = DPOConfig(
        output_dir=args.output,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        warmup_ratio=0.1,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=4,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        report_to="none",
        max_length=args.max_seq,
        max_prompt_length=args.max_seq // 2,
        beta=args.beta,
        bf16=True,
    )

    trainer = DPOTrainer(
        model=model,
        ref_model=None,                     # adapter-disabled forward = reference
        args=dpo_config,
        train_dataset=ds,
        tokenizer=tokenizer,
    )

    print()
    print(f"[train] DPO: {args.epochs} epochs × {len(ds)} pairs / "
          f"effective_batch {args.batch * args.grad_accum}")
    trainer.train()

    print()
    print(f"[save] writing DPO adapter to {args.output}")
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"[done] DPO stage complete")


if __name__ == "__main__":
    main()
