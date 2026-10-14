# ToolTalk GPT-6 Luna evaluation (effort=none)

- Dataset: Microsoft ToolTalk, 100 sampled decision points (50 easy, 50 ToolTalk)
- Evaluation: one-step tool prediction with gold conversation history; not live app execution
- Model: `gpt-6-luna`
- Reasoning effort: `none`
- Successful model outputs scored: 90 / 100
- Unscored: 10 / 100 (malformed/non-JSON outputs or policy-blocked prompts)

| Split | Scored | Exact tool sequence | Gold argument subset exact |
|---|---:|---:|---:|
| All scored | 90 | 56.7% | 37.8% |
| Easy | 50 | 70.0% | 54.0% |
| ToolTalk | 40 | 40.0% | 17.5% |

## Caveats

- Exact sequence matching is strict; semantically valid alternatives may be marked incorrect.
- The denominator excludes 10 items without a usable prediction. This is not an all-100 success rate.
- This is an auxiliary teacher-forced prediction metric, not the official ToolTalk score and not an end-to-end execution benchmark.
- The raw prediction log can contain user/conversation text. Review and redact it before any public release.

Raw local output: `tooltalk_gpt-6-luna_none.jsonl` (not intended for public release without privacy review).
