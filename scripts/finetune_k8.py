"""
Stage 1 — QLoRA SFT trainer for Katherine K8 on Qwen3.5-9B.

Derived from finetune_k0.py (validated working at 1× H200, ~50 min, $3 cost,
frame-holding verified at Q5_K_M). K8-specific changes vs the K0 baseline:

  1. Default data path  : dataset/pilot_500/processed/sft_train.jsonl
  2. Default output dir : adapters/k8_sft_adapter
  3. CRITICAL FIX — regex strip of empty <think></think> blocks. Qwen3.5's
     chat template (in transformers >=5.5 / Unsloth >=2026.5) inserts empty
     <think>\\n\\n</think>\\n\\n markers around every assistant turn even
     when enable_thinking=False is passed. K8 spec forbids think blocks
     anywhere; the previous K8 run trained on data poisoned with these
     blocks because the leak detector only warned, didn't abort.
  4. Leak detector promoted to FATAL (sys.exit on any survival).

Hyperparameters (unchanged from K0; persona-fine-tune envelope):
  rank       = 64        (alpha = 128, dropout = 0.05)
  epochs     = 3
  lr         = 1e-4 (cosine, warmup 5%)
  batch      = 16 per device, grad_accum = 2 (effective 32)
  max_seq    = 1024      (K8 data p99 ≈ 60 tokens; 16× margin is fine)
  bf16       = on
  optim      = adamw_8bit
  thinking   = OFF       (K8 is two-Is collapsed)
  sys-prompt = ABSENT    (K8 dataset is NOSYS by construction)
"""
import argparse
import os
import re
import sys

# Unsloth MUST import before transformers/peft/trl.
# CRITICAL: use FastVisionModel for Qwen3.5-9B (vision-language model).
# FastModel is the LLM-aware loader and will silently strip the vision tower
# during get_peft_model — the resulting GGUF loses image input capability.
# FastVisionModel + finetune_vision_layers=False preserves the native vision
# tower while LoRA-tuning only the language layers. See
# memory/reference_unsloth_vision_gguf.md for full diagnosis.
from unsloth import FastVisionModel
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig
from transformers import DataCollatorForSeq2Seq


# Strips empty think markers in any of these forms:
#   <think></think>
#   <think>\n</think>
#   <think>\n\n</think>
# plus any trailing newlines that follow.
THINK_BLOCK_RE = re.compile(r'<think>\s*</think>\s*\n*', flags=re.IGNORECASE)


def do_train(args, model, tokenizer):
    """Attach LoRA via FastVisionModel (preserves Qwen3.5-9B native vision tower)."""
    model = FastVisionModel.get_peft_model(
        model,
        # Vision tower is preserved by NOT fine-tuning it. The K8 LoRA only
        # touches the language path; vision encoder stays at base weights and
        # remains usable post-merge for the GGUF mmproj export.
        finetune_vision_layers=False,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=args.rank,
        lora_alpha=args.alpha,
        lora_dropout=args.dropout,
        bias="none",
        target_modules="all-linear",
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
            # CRITICAL: strip empty <think></think> blocks that Qwen3.5's
            # chat template inserts at every assistant turn regardless of
            # enable_thinking=False. K8 forbids think blocks anywhere.
            text = THINK_BLOCK_RE.sub('', text)
            out.append(text)
        return {"text": out}

    ds = ds.map(fmt, batched=True, remove_columns=ds.column_names)

    # Sanity check first formatted example
    print()
    print("[sample] first formatted example (truncated):")
    print("-" * 60)
    print(ds[0]["text"][:1000])
    print("-" * 60)

    # FATAL: any <think> survival means the data is poisoned. The
    # previous K8 run silently trained on poisoned data because the
    # detector was a warn, not a fatal. Promoted here.
    leaked = sum(1 for r in ds if "<think>" in r["text"])
    if leaked > 0:
        print(f"[FATAL] {leaked}/{len(ds)} formatted examples STILL contain '<think>' tags after stripping",
              file=sys.stderr)
        print(f"[FATAL] K8 must NOT train on poisoned data. Inspect tokenizer.apply_chat_template behavior.",
              file=sys.stderr)
        sys.exit(1)
    print(f"[ok] 0/{len(ds)} examples contain <think> blocks after stripping")

    # System prompt leak check (K8 is NOSYS by construction)
    sys_leaked = sum(1 for r in ds if "<|im_start|>system" in r["text"])
    if sys_leaked > 0:
        print(f"[FATAL] {sys_leaked} examples contain system markers (K8 is NOSYS)",
              file=sys.stderr)
        sys.exit(1)
    print(f"[ok] 0/{len(ds)} examples contain system markers")

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
    p.add_argument("--data", default="dataset/tier_1/processed/sft_train.jsonl",
                   help="SFT corpus path. Default points at tier_1/processed/ "
                        "(post-2026-05-10 maintenance, was pilot_500/processed/). "
                        "Run scripts/prep_dataset.py first to populate.")
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
            print(f"[error] --skip-train set but adapter dir not found: {args.output}",
                  file=sys.stderr)
            sys.exit(1)
        print(f"[skip-train] adapter at {args.output}")
        return

    print(f"[load] base model (vision-aware loader): {args.model}")
    model, tokenizer = FastVisionModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq,
        load_in_4bit=True,
        full_finetuning=False,
    )

    do_train(args, model, tokenizer)
    print("[done] SFT stage complete")


if __name__ == "__main__":
    main()
