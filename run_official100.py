#!/usr/bin/env python3
"""Stratified, seeded 100-task AutomationBench evaluation with GPT-6 Luna.

Requires a separately cloned zapier/AutomationBench repo, uv sync and OPENAI_API_KEY.
No real business accounts are touched: AutomationBench simulates app environments.
"""
import argparse
import json
import os
import random
import subprocess
import sys
from pathlib import Path

QUOTAS = {"sales": 17, "marketing": 17, "operations": 17,
          "support": 17, "finance": 16, "hr": 16}
SEED = 20261014


def task_name(row):
    info = row.get("info") or {}
    if isinstance(info, str):
        info = json.loads(info)
    return info.get("task_name") or row.get("task")


def sample_manifest(repo: Path, target: Path):
    sys.path.insert(0, str(repo))
    from automationbench.domains import get_combined_dataset
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    rng = random.Random(SEED)
    choices = {}
    for domain, count in QUOTAS.items():
        ds = get_combined_dataset([domain])
        names = [task_name(row) for row in ds]
        if len(names) < count or any(not n for n in names):
            raise ValueError(f"Cannot sample {count} valid tasks from {domain} (found {len(names)})")
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate task names in {domain}")
        choices[domain] = sorted(rng.sample(names, count))
    manifest = {
        "benchmark": "zapier/AutomationBench", "repo_commit": commit,
        "sample_seed": SEED, "model": "gpt-6-luna", "n": sum(QUOTAS.values()),
        "selection": choices,
        "note": "A fixed 100-task subset of the PUBLIC benchmark; not the private leaderboard."
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True, help="Local cloned AutomationBench root")
    p.add_argument("--output", type=Path, default=Path("results"))
    p.add_argument("--toolsets", nargs="+", choices=["api", "zapier", "limited_zapier"], default=["api"])
    p.add_argument("--efforts", nargs="+", choices=["none", "low", "medium", "high", "xhigh", "max"], default=["max"])
    p.add_argument("--max-concurrent", type=int, default=4)
    p.add_argument("--max-steps", type=int, default=50)
    p.add_argument("--dry-run", action="store_true", help="Print commands and manifest without API calls")
    args = p.parse_args()
    repo = args.repo.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not (repo / "automationbench" / "scripts" / "eval.py").is_file():
        p.error(f"Invalid AutomationBench repository: {repo}")
    if not args.dry_run and not os.getenv("OPENAI_API_KEY"):
        p.error("OPENAI_API_KEY is unset. Use --dry-run to create a manifest without inference.")
    manifest_path = output / "manifest_100.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("n") != 100 or set(manifest.get("selection", {})) != set(QUOTAS):
            raise ValueError("Existing manifest incompatible; use a different output directory")
    else:
        manifest = sample_manifest(repo, manifest_path)
    for toolset in args.toolsets:
      for effort in args.efforts:
        for domain, names in manifest["selection"].items():
            dest = output / toolset / effort / f"{domain}.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            cmd = ["uv", "run", "auto-bench", "--model", "gpt-6-luna",
                   "--api", "responses", "--toolset", toolset,
                   "--domains", domain, "--tasks", ",".join(names),
                   "--reasoning-effort", effort,
                   "--max-concurrent", str(args.max_concurrent),
                   "--max-steps", str(args.max_steps),
                   "--export-json", str(dest)]
            print(f"[{toolset}/{effort}/{domain}] {len(names)} cases")
            if args.dry_run:
                print("  ", " ".join(cmd[:14]), "...", "[task names omitted]")
            else:
                if dest.exists():
                    print("  SKIP existing result:", dest)
                    continue
                subprocess.run(cmd, cwd=repo, check=True)
    print("Manifest:", manifest_path)
    print("Scoring: python summarize.py --output", output)

if __name__ == "__main__":
    main()
