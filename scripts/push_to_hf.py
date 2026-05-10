"""
Stage 4 — push K8 trained adapters + GGUFs to HF.

Direct port of K0's push_to_hf.py. Two destinations:
  Bucket (private):     bochen2079/katherine-k8 — adapters, training data, logs
  Model repo (public):  bochen2079/katherine-k8-qwen3.5-9b — GGUFs + (optional) merged bf16

Uses `hf sync DIR URL` (verified bucket-upload syntax). Does NOT use
`hf upload --repo-type bucket` (rejects 'bucket' as repo-type, broken in
current CLI).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def hf_sync(local_dir: str, remote_url: str, includes: list = None) -> bool:
    if not os.path.isdir(local_dir):
        print(f"[hf-sync] skip: {local_dir} does not exist")
        return False
    cmd = ["hf", "sync", local_dir, remote_url]
    if includes:
        for inc in includes:
            cmd += ["--include", inc]
    print(f"[hf-sync] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        out = (result.stdout or "") + (result.stderr or "")
        for line in out.splitlines()[-20:]:
            print(f"  {line}")
        if result.returncode != 0:
            print(f"[hf-sync] FAIL (returncode={result.returncode})")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"[hf-sync] TIMEOUT after 1 hour")
        return False
    except Exception as e:
        print(f"[hf-sync] EXC: {type(e).__name__}: {e}")
        return False


def hf_upload_to_repo(local_path: str, remote_subpath: str, repo_id: str) -> bool:
    """Upload to a public model repo (not a bucket). Uses `hf upload` form."""
    if not os.path.exists(local_path):
        print(f"[hf-upload] skip: {local_path} does not exist")
        return False
    cmd = ["hf", "upload", repo_id, local_path, remote_subpath, "--repo-type", "model"]
    print(f"[hf-upload] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        out = (result.stdout or "") + (result.stderr or "")
        for line in out.splitlines()[-15:]:
            print(f"  {line}")
        return result.returncode == 0
    except Exception as e:
        print(f"[hf-upload] EXC: {type(e).__name__}: {e}")
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default="bochen2079/katherine-k8-qwen3.5-9b",
                   help="Public model repo for GGUFs")
    p.add_argument("--bucket", default="bochen2079/katherine-k8",
                   help="Private bucket for adapters / data / logs")
    p.add_argument("--sft-adapter", default="adapters/k8_sft_adapter")
    p.add_argument("--dpo-adapter", default="adapters/k8_dpo_adapter")
    p.add_argument("--gguf-base-dir", default="gguf")
    p.add_argument("--data-dir", default="dataset/pilot_500")
    args = p.parse_args()

    print("[auth] verifying HF login...")
    r = subprocess.run(["hf", "auth", "whoami"], capture_output=True, text=True)
    if r.returncode != 0 or "Logged in" not in (r.stdout + r.stderr):
        print("[auth] not logged in. Run: hf auth login --token $HF_TOKEN", file=sys.stderr)
        sys.exit(1)
    print("[auth]", (r.stdout or r.stderr).strip().split("\n")[0])

    bucket_url_base = f"hf://buckets/{args.bucket}"
    results = {}

    # 1. Adapters → bucket (private)
    if os.path.isdir(args.sft_adapter):
        results["sft_adapter"] = hf_sync(args.sft_adapter, f"{bucket_url_base}/k8_sft_adapter/")
    if os.path.isdir(args.dpo_adapter):
        results["dpo_adapter"] = hf_sync(args.dpo_adapter, f"{bucket_url_base}/k8_dpo_adapter/")

    # 2. Dataset snapshot → bucket
    if os.path.isdir(args.data_dir):
        results["data"] = hf_sync(args.data_dir, f"{bucket_url_base}/data/",
                                  includes=["*.jsonl", "README.md"])

    # 3. Logs → bucket
    if os.path.isdir("."):
        results["logs"] = hf_sync(".", f"{bucket_url_base}/logs/",
                                  includes=["*.stderr.log", "*.log"])

    # 4. GGUFs → public model repo (Qwen3.5-9B.{Q4_K_M,Q5_K_M,Q6_K}.gguf at root)
    # Unsloth's save_pretrained_gguf may write to either gguf_q5_k_m/ OR
    # gguf_q5_k_m_gguf/ depending on internal logic. Strip the trailing
    # "_gguf" suffix before extracting the quant label, matching K0's logic.
    if os.path.isdir(args.gguf_base_dir):
        for quant_subdir in sorted(Path(args.gguf_base_dir).iterdir()):
            if not (quant_subdir.is_dir() and quant_subdir.name.startswith("gguf_")):
                continue
            for ggfile in quant_subdir.rglob("*.gguf"):
                if "mmproj" in ggfile.name:
                    continue
                # Normalize: gguf_q5_k_m_gguf → gguf_q5_k_m → Q5_K_M
                norm = quant_subdir.name
                if norm.endswith("_gguf"):
                    norm = norm[:-5]
                quant_label = norm.replace("gguf_", "", 1).upper()
                target_name = f"Qwen3.5-9B.{quant_label}.gguf"
                results[f"gguf:{target_name}"] = hf_upload_to_repo(
                    str(ggfile), target_name, args.repo
                )

    print()
    print("=" * 60)
    print("[summary]")
    for key, ok in results.items():
        print(f"  {'✓' if ok else '✗'} {key}")
    print()
    if all(results.values()):
        print("[done] all artifacts pushed")
        sys.exit(0)
    else:
        print("[partial] some pushes failed; see logs above")
        sys.exit(2)


if __name__ == "__main__":
    main()
