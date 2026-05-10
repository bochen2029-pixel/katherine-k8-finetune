"""
Stage 3 — Merge LoRA into base + export GGUF in 3 quantization levels.

Direct port of K0's merge_and_gguf.py. Reads the final adapter (DPO if
present, else SFT), merges into Qwen3.5-9B base, writes:
  gguf_q4_k_m/  ~5.5 GB
  gguf_q5_k_m/  ~6.5 GB    sweet spot, your target
  gguf_q6_k/    ~7.7 GB

Failsafe: each quant is independent; if q5 fails, q4+q6 are still useful.
First run compiles llama.cpp internally (~5-10 min).
"""
import argparse
import os
import sys
from pathlib import Path

# FastVisionModel preserves Qwen3.5-9B vision tower for mmproj export
from unsloth import FastVisionModel


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True)
    p.add_argument("--max_seq", type=int, default=1024)
    p.add_argument("--gguf-base-dir", default="gguf")
    p.add_argument("--quants", nargs="+", default=["q4_k_m", "q5_k_m", "q6_k"])
    args = p.parse_args()

    if not os.path.isdir(args.adapter):
        print(f"[error] adapter not found: {args.adapter}", file=sys.stderr)
        sys.exit(1)

    print(f"[load] adapter (vision-aware loader): {args.adapter}")
    model, tokenizer = FastVisionModel.from_pretrained(
        model_name=args.adapter,
        max_seq_length=args.max_seq,
        load_in_4bit=True,
        full_finetuning=False,
    )

    Path(args.gguf_base_dir).mkdir(parents=True, exist_ok=True)

    successes = []
    failures = []
    for quant in args.quants:
        out_dir = os.path.join(args.gguf_base_dir, f"gguf_{quant}")
        print()
        print(f"[gguf] === exporting {quant} → {out_dir} ===")
        try:
            model.save_pretrained_gguf(
                out_dir,
                tokenizer,
                quantization_method=quant,
            )
            # Unsloth appends "_gguf" suffix to output dir; search both
            search_dirs = [out_dir, f"{out_dir}_gguf"]
            produced = []
            mmproj_found = []
            for sd in search_dirs:
                if not os.path.isdir(sd):
                    continue
                for root, _, files in os.walk(sd):
                    for fn in files:
                        if not fn.endswith(".gguf"):
                            continue
                        full = os.path.join(root, fn)
                        size_mb = os.path.getsize(full) / (1024 * 1024)
                        if "mmproj" in fn:
                            mmproj_found.append((full, size_mb))
                        else:
                            produced.append((full, size_mb))
            if produced:
                for f, sz in produced:
                    print(f"[gguf] OK: {f}  ({sz:.0f} MB)")
                for f, sz in mmproj_found:
                    print(f"[gguf] OK (vision): {f}  ({sz:.0f} MB)")
                successes.append((quant, produced + mmproj_found))
            else:
                print(f"[gguf] WARN: no .gguf file found in {out_dir} or {out_dir}_gguf")
                failures.append((quant, "no .gguf produced"))
        except Exception as e:
            print(f"[gguf] FAIL: {type(e).__name__}: {e}")
            failures.append((quant, str(e)))

    print()
    print("=" * 60)
    print(f"[summary] {len(successes)} successful, {len(failures)} failed")
    for quant, files in successes:
        for f, sz in files:
            print(f"  ✓ {quant}: {f}  ({sz:.0f} MB)")
    for quant, err in failures:
        print(f"  ✗ {quant}: {err}")

    if not successes:
        print("[fatal] no quants succeeded; adapter is preserved")
        sys.exit(2)
    print()
    print("[done] merge + GGUF stage complete")


if __name__ == "__main__":
    main()
