"""
Stage 1 — QLoRA SFT trainer for Katherine K8 on Qwen3.5-9B.

Direct port of finetune_k0.py — same hyperparameters validated working
on K0 (50 min wallclock H200 SXM5, $3, frame-holding verified at Q5_K_M).

Hyperparameters:
  rank       = 64        (alpha = 128, dropout = 0.05)
  epochs     = 3
  lr         = 1e-4 (cosine, warmup 5%)
  batch      = 16 per device, grad_accum = 2 (effective 32)
  max_seq    = 1024
  bf16       = on
  optim      = adamw_8bit
  thinking   = OFF       (K8 is two-Is collapsed, prose reasoning)
  sys-prompt = STRIPPED  (data is already NOSYS; defense in depth at format time)

Failsafe:
  - Adapter saved per epoch
  - --skip-train + existing --output to re-run downstream stages
"""
import argparse
import os
import sys

# Unsloth MUST import before transformers/peft/trl
from unsloth import FastModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
from transformers import DataCollatorForSeq2Seq


def do_train(args, model, tokenizer):
    """Attach LoRA, format dataset, train, save adapter."""
    model = FastModel.get_peft_model(
        model,
        r=args.rank,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=args.alpha,
        lora_dropout=args.dropout,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    print(f"[data] loading {args.data}")
    ds = load_dataset("json", data_files=args.data, split="train")
    print(f"[data] {len(ds)} examples loaded")

    def fmt(examples):
        out = []
        for msgs in examples["messages"]:
            # Defense in depth: drop any system message that snuck through prep
            msgs = [m for m in msgs if m.get("role") != "system"]
            text = tokenizer.apply_chat_template(
                msgs,
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=False,   # K8 is two-Is collapsed
            )
            out.append(text)
        return {"text": out}

    ds = ds.map(fmt, batched=True, remove_columns=ds.column_names)

    print()
    print("[sample] first formatted example (truncated):")
    print("-" * 60)
    print(ds[0]["text"][:1000])
    print("-" * 60)

    # Sanity: no <think> blocks should appear
    leaked_think = sum(1 for r in ds if "<think>" in r["text"])
    if leaked_think > 0:
        print(f"[warn] {leaked_think}/{len(ds)} formatted examples contain '<think>' tags")
        print(f"[warn] K8 should NOT have thinking blocks — investigate source data")

    # Sanity: no system prompts in formatted text
    sys_leaked = sum(1 for r in ds if "<|im_start|>system" in r["text"])
    if sys_leaked > 0:
        print(f"[warn] {sys_leaked} formatted examples contain system markers; check prep_dataset.py")

    sft_config = SFTConfig(
        output_dir=args.output,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        warmup_ratio=0.05,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        logging_steps=5,
        save_strategy="epoch",
        save_total_limit=10,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=3407,
        report_to="none",
        max_seq_length=args.max_seq,
        dataset_text_field="text",
        dataset_num_proc=1,
        packing=False,
        bf16=True,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds,
        args=sft_config,
        data_collator=DataCollatorForSeq2Seq(tokenizer=tokenizer),
    )

    print()
    print(f"[train] starting: {args.epochs} epochs × {len(ds)} samples / "
          f"effective_batch {args.batch * args.grad_accum} = "
          f"~{(args.epochs * len(ds)) // (args.batch * args.grad_accum)} steps")
    trainer.train()

    print()
    print(f"[save] writing adapter to {args.output}")
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    print(f"[save] adapter persisted")
    return model


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="dataset/pilot_500/processed/sft_train.jsonl")
    p.add_argument("--output", default="adapters/k8_sft_adapter")
    p.add_argument("--model", default="unsloth/Qwen3.5-9B")
    p.add_argument("--max_seq", type=int, default=1024)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--rank", type=int, default=64)
    p.add_argument("--alpha", type=int, default=128)
    p.add_argument("--dropout", type=float, default=0.05)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--grad_accum", type=int, default=2)
    p.add_argument("--skip-train", action="store_true",
                   help="Skip training; assume adapter already exists at --output")
    args = p.parse_args()

    if args.skip_train:
        if not os.path.isdir(args.output):
            print(f"[error] --skip-train set but adapter dir not found: {args.output}", file=sys.stderr)
            sys.exit(1)
        print(f"[skip-train] adapter at {args.output}")
        return

    print(f"[load] base model: {args.model}")
    model, tokenizer = FastModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq,
        load_in_4bit=True,
        full_finetuning=False,
    )

    do_train(args, model, tokenizer)
    print("[done] SFT stage complete")


if __name__ == "__main__":
    main()
