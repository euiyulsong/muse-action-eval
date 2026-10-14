#!/usr/bin/env python3
"""Aggregate official AutomationBench exports into scores and per-case CSV."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=Path("results"))
    args=p.parse_args()
    base=args.output
    manifest_path=base/"manifest_100.json"
    if not manifest_path.is_file():
        p.error("No manifest_100.json: run run_official100.py first")
    manifest=json.loads(manifest_path.read_text())
    expected={d:set(v) for d,v in manifest["selection"].items()}
    records=[]
    for f in sorted(base.glob("*/*/*.json")):
        if f.name=="manifest_100.json":continue
        raw=json.loads(f.read_text())
        meta=raw.get("meta",{})
        domain=f.stem
        effort=f.parent.name
        toolset=f.parent.parent.name
        results=raw.get("tasks") or raw.get("task_results")
        if results is None:
            raise ValueError(f"Missing per-task results in {f}; keys={list(raw)}")
        seen=set()
        for r in results:
            name=r.get("name")
            if name not in expected.get(domain,set()):
                raise ValueError(f"Unrecognized task {domain}/{name} in {f}")
            if name in seen:raise ValueError(f"Duplicate name: {name}")
            seen.add(name)
            rows={"toolset":toolset,"effort":effort,"domain":domain,"task":name,
                  "pass":int(bool(r.get("passed"))),
                  "partial_credit":float(r.get("score") or 0),
                  "assertions_passed":r.get("assertions_passed"),
                  "assertions_total":r.get("assertions_total"),
                  "model_calls":r.get("num_model_calls"),
                  "tool_calls":r.get("num_tool_calls"),
                  "latency_model_seconds":r.get("model_time_s"),
                  "cost_usd":r.get("cost")}
            records.append(rows)
        if seen!=expected[domain]:
            print(f"WARNING incomplete {f}: got {len(seen)} of {len(expected[domain])} tasks")
        if meta.get("model")!="gpt-6-luna":
            print("WARNING unexpected model",meta.get("model"),f)
    if not records:
        print("No model result JSON files yet; this is NOT a GPT-6 Luna score.")
        return
    path=base/"task_scores.csv"
    with path.open("w",newline="",encoding="utf-8-sig") as fp:
        w=csv.DictWriter(fp, fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    groups=defaultdict(list)
    for r in records:
        groups[(r["toolset"],r["effort"],"ALL")].append(r)
        groups[(r["toolset"],r["effort"],r["domain"])].append(r)
    summary=[]
    for (toolset,effort,domain),g in sorted(groups.items()):
        vals=[r["cost_usd"] for r in g if isinstance(r["cost_usd"],(int,float))]
        times=[r["latency_model_seconds"] for r in g if isinstance(r["latency_model_seconds"],(int,float))]
        summary.append({"toolset":toolset,"effort":effort,"domain":domain,"n":len(g),
                        "pass_rate":round(sum(r["pass"] for r in g)/len(g),4),
                        "avg_partial_credit":round(sum(r["partial_credit"] for r in g)/len(g),4),
                        "avg_cost_usd":round(sum(vals)/len(vals),5) if vals else None,
                        "avg_model_time_s":round(sum(times)/len(times),3) if times else None})
    (base/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    for x in summary:print(x)
    print("Saved:",path,base/"summary.json")

if __name__=="__main__":main()
