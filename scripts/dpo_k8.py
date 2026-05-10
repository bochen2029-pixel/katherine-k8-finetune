"""
Stage 2 — DPO trainer for Katherine K8, on top of the SFT adapter.

Direct port of dpo_k0.py. Difference: K8 DPO data has chosen/rejected as
plain strings (the K0 path expected list-of-message-dicts). Format function
adapted for the simpler schema.

Hyperparameters (matching K0 validated config):
  epochs       = 2
  lr           = 5e-6
  beta         = 0.1
  batch        = 4 per device, grad_accum = 2 (effective 8)
  max_seq      = 1024
  optim        = adamw_8bit
"""
import argparse
import os
import sys

from unsloth import FastModel
from datasets import load_dataset
from trl import DPOTrainer, DPOConfig


def fmt_dpo_example(ex, tokenizer):
    """Convert {messages: [...], chosen: str, rejected: str} → DPO trio.

    The K8 dataset stores messages array (ending in user) + chosen/rejected
    as plain strings. DPOTrainer needs prompt str + chosen str + rejected str.
    """
    msgs = ex["messages"]
    msgs = [m for m in msgs if m.get("role") != "system"]
    prompt_str = tokenizer.apply_chat_template(
        msgs,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    return {
        "prompt": prompt_str,
        "chosen": ex["chosen"],
        "rejected": ex["rejected"],
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="dataset/pilot_500/processed/dpo_train.jsonl")
    p.add_argument("--sft-adapter", default="adapters/k8_sft_adapter")
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
            print(f"[error] --skip-train set but DPO adapter dir not found: {args.output}", file=sys.stderr)
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

    # IMPORTANT: remove all original columns. The K8 dataset stores
    # {messages, chosen, rejected, _cat, _type}. After fmt we want
    # {prompt, chosen, rejected} only. If we don't drop the originals,
    # TRL's DPOTrainer sees both 'messages' AND 'prompt' keys and
    # rejects with: "Invalid keys in the example: {messages, ...}"
    ds = ds.map(
        lambda ex: fmt_dpo_example(ex, tokenizer),
        remove_columns=ds.column_names,
    )

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
        ref_model=None,
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
