# GPT-6 Luna · Muse-style Action Evaluation Kit

## Latest empirical result

An auxiliary Microsoft ToolTalk one-step prediction run using `gpt-6-luna` with
reasoning effort `none` scored 90 usable predictions out of 100: exact tool
sequence 56.7%, and exact gold-argument subset 37.8%. See
[`results/tooltalk_gpt-6-luna_none_summary.md`](results/tooltalk_gpt-6-luna_none_summary.md)
for split-level scores and caveats. Raw predictions and downloaded conversation
cache are intentionally excluded from this public repository.

**Status (2026-10-14):** Evaluation design and scripts validated locally, **no GPT-6 Luna inference performed**. The execution environment has no `OPENAI_API_KEY` and outbound fetches are unavailable. Never treat local suite validation as a model score.

## What this evaluates

| Track | Source | Evaluation set | What is tested | Outcome metric |
|---|---|---:|---|---|
| A | Zapier AutomationBench 1.0.6 PUBLIC | 100 sampled cases: sales 17, marketing 17, operations 17, support 17, finance 16, HR 16 | Multi-app execution across simulated SaaS tools; multi-step workflows; realistic starting app state | Actual simulated end-state task success + per-assertion partial credit |
| B | Microsoft ToolTalk | 100 *decision points* from 78 actual conversations (50 easy, 50 hard); **same conversation can contribute multiple examples** | Tool name/order and argument prediction given gold historical context | Tool-sequence exact / gold-argument subset exact (offline imitation only) |
| C | Authored synthetic Muse personal suite | 100 scenarios, 10 categories × 10 examples | Reminders, schedules, email, calendar, monitoring, shopping, travel, documents, cross-app, guardrails | Decision, tool-route and required-slot exact (planning only) |

**Sources:**
- Zapier: https://github.com/zapier/AutomationBench (public tasks; official leaderboard uses a harder private split)
- Microsoft: https://github.com/microsoft/ToolTalk (MIT; 28 easy + 50 hard conversations)
- Berkeley BFCL v4: https://gorilla.cs.berkeley.edu/leaderboard (optional external standard for AST and multi-turn; not integrated into these scripts)
- τ-bench: https://github.com/sierra-research/tau2-bench (optional external standard for transactional end state)
- Model/API docs: https://developers.openai.com/api/docs/models/gpt-6-luna
- Official benchmark context: https://openai.com/index/introducing-gpt-6-sol-and-luna/

The model ID is **`gpt-6-luna`**. The official recommended route for tool calling is the **Responses API**. The AutomationBench script explicitly forces `--api responses`; other scripts use `client.responses.create(...)`.

## Install and run: A. 100 open-source end-state tasks

Requirements: Python 3.13+, `uv`, Git, OpenAI API key, network access. All business apps are **simulated** and no live external messages/purchases are sent.

```bash
# Unzip this kit, then from any working directory:
git clone https://github.com/zapier/AutomationBench.git
cd AutomationBench
uv sync
cd ..
export OPENAI_API_KEY='YOUR_KEY'

# Baseline: 100 seeded, stratified tasks with actual stateful tool execution
python muse_action_eval/run_official100.py \
  --repo ./AutomationBench \
  --output ./muse_results \
  --efforts max \
  --toolsets api \
  --max-concurrent 4

# Diagnostic ablations on exactly the same 100 task IDs
python muse_action_eval/run_official100.py \
  --repo ./AutomationBench --output ./muse_results \
  --efforts medium high max \
  --toolsets api zapier \
  --max-concurrent 4

python muse_action_eval/summarize.py --output ./muse_results
```

**Interpretation:** For each combination, the script scores the same 100 tasks, broken down 17/17/17/17/16/16. **Running both 3 reasoning efforts and 2 toolsets involves 600 task rollouts**, not 100 total. The sample is fixed using seed `20261014`, stored in `manifest_100.json` with repository commit. Repeating on the same manifest supports paired comparisons. For research-grade reporting, rerun different seeds and calculate confidence intervals (at n=100, a 50% success rate has an approximate 95% binomial interval of ±10 pp). Keep a copy of the benchmark repo at the same commit when rerunning. 

`api` offers explicit REST-style Tool APIs; `zapier` is a harder tool-discovery style setting. Scores across these settings are NOT directly the same as published scores unless all evaluation parameters, version, and data split match.

**Scoring:** `pass_rate` is fraction of fully completed final-state tasks. `avg_partial_credit` is mean fraction of assertions met. `task_scores.csv` has each case's number of model/tool calls, model-time, and estimated cost (if supplied by the underlying benchmark).

## B. 100 ToolTalk decision points from real open-source dialogs

ToolTalk code and conversations are fetched from GitHub when run. This is an **auxiliary teacher-forced prediction metric**, *not the original ToolTalk official environment execution score*. 100 points are drawn from 78 conversations and may not be independent.

```bash
python muse_action_eval/prepare_tooltalk100.py \
  --output muse_action_eval/tooltalk100.jsonl
python -m pip install openai
export OPENAI_API_KEY='YOUR_KEY'
python muse_action_eval/eval_tooltalk100.py \
  --data muse_action_eval/tooltalk100.jsonl \
  --output tooltalk_preds.jsonl \
  --model gpt-6-luna --effort medium
```

The extractor removes `session_token` and password from targets, uses previous gold conversational context including previous tool responses, and grades action names and provided gold argument values exactly. Some valid semantically equivalent results may be scored as mismatches. Use source's official evaluation harness for published ToolTalk comparable results.

## C. 100 personal Muse-style action-planning prompts

The `personal_synthetic100.jsonl` file is **already bundled**. Cases are **authored synthetic examples**, NOT a downloaded open-source benchmark.

```bash
python muse_action_eval/eval_personal100.py --check-only
python -m pip install openai
export OPENAI_API_KEY='YOUR_KEY'
python muse_action_eval/eval_personal100.py \
  --model gpt-6-luna --effort medium \
  --output personal_results
```

100 scenarios cover 10 categories, including repeated schedules, condition monitoring, approval gates and ambiguity. All planning requests are made in fixed KST time context `2026-10-14T20:14:00+09:00`. This track instructs Luna to produce a structured JSON plan. It **does not call real apps** and does not test real follow-through. Only explicitly specified critical argument fields are graded: this is more permissive than full argument exactness on some tasks. Result file includes the model's returned JSON, individual scores, errors, and a domain summary.

## Experimental design and metrics

1. **Primary:** AutomationBench `task_completed_correctly`: strict all-assertions pass, measured as a percentage over 100 instances.
2. **Partial:** assertion pass-rate, to distinguish partial progress from complete success.
3. **Action routing:** ToolTalk and synthetic suite Tool-sequence exact, argument-value checks, and policy (approval/clarification/rejection) decisions.
4. **Efficiency:** model calls/task, tool calls/task, model time/task, USD/task. Separately measure p50/p95 latency if system records overall wall time.
5. **Reliability:** run more trials per task when possible; compute `pass^k` or taskwise repeat pass-rate. Never infer repeated reliability from a single rollout.
6. **Operational/permissions:** false execution on missing approval, unnecessary external writes, bad time-zone conversion, duplicate actions, authorization errors. The synthetic suite **does not independently execute these**, so a full deployment needs additional audited sandbox integration tests.

Suggested 2×3 ablation (same 100 cases):

| | medium | high | max |
|---|---|---|---|
| Explicit API tools | A1 | A2 | A3 |
| Dynamic discovery / Zapier tools | B1 | B2 | B3 |

Compare domain success by paired task ID, and calculate incremental USD per additional success. Do not optimize just tool-call exactness: more than one legitimate action path can reach the same intended state.

## Limitations

- This kit has **not** run inference against GPT-6 Luna. The only local score is self-validation of evaluator fixtures, which is **not** an empirical model score.
- Production Muse internals, dedicated background scheduler durability, real external app permissions, UI browser computer-use and credentials are **not** reproduced here.
- The 100-case PUBLIC task slice will not match the official PRIVATE leaderboard. The official full public split contains 600 complex tasks plus 200 simple tasks (excluded from headline scoring).
- ToolTalk and personal cases are planning-only; the AutomationBench suite tests real simulated state transitions.
- Static benchmark prompts can have data contamination and should be complemented with freshly crafted unseen cases.
- Cost figures depend on actual model usage, cache state, current prices and all retries.

## Smoke-check performed in this environment

```text
$ python eval_personal100.py --check-only
Suite validation OK: 10 categories × 10 cases = 100
No model called. No empirical inference result.
$ python -m py_compile *.py
Success
```
