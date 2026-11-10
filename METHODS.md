# Methods and replication details

Small no-chain-of-thought replication on Fable 5.2.

A low-budget, three-task replication inspired by **Neel Nanda's [Astra can do a concerning amount with no chain of thought](https://www.lesswrong.com/posts/eRmzz8J8Qkzqvzrgg/astra-can-do-a-concerning-amount-with-no-chain-of-thought)**. The benchmark data, prompt construction, and answer grader come from Neel's [nocot-bench](https://github.com/neelnanda-io/nocot-bench). This repository contributes the native-Anthropic runner, fixed subset, and results; it is not the original benchmark or an endorsement by its author.

## Experiment

- Model: `claude-fable-5-2`, native Anthropic Messages API, run November 10, 2026.
- Fixed seed: `20261110`; five items per difficulty rung, chosen before any inference.
- Tasks: arithmetic (25 items / five rungs), repeated lookup `brew` (10 / two rungs), shortest path (15 / three rungs).
- Two fresh, uncached draws of each item: 100 main observations over 50 unique items.
- Pilot: five arithmetic items spanning the five rungs, twice; reuse those ten exact responses in the main measurement.
- Positive control: the same five items, high effort, without the no-deliberation system or JSON schema; maximum 512 output tokens.
- Main recipe: adaptive thinking, low effort, immediate-recall system prompt, structured final-answer schema, no prefill or temperature setting, maximum 300 output tokens. Available canonical demonstration turns are preserved: arithmetic 10, brew 1, shortest path 3.
- Upstream pinned to `beb2ffcf73b657a445e8a7b797d7c9b0e249b570`. The native route and selected subset are adaptations of the article's setup.

## Results

| Task | Draw 1 | Draw 2 | Combined |
|---|---:|---:|---:|
| arithmetic | 23/25 | 23/25 | 92% |
| brew | 9/10 | 9/10 | 90% |
| shortpath | 15/15 | 15/15 | 100% |

All 100 main responses reported zero thinking tokens, with no visible reasoning, blind usage, or truncation. The positive control showed nonzero thinking on 4/5 calls. All item outcomes agreed between draws. Primary and conditional-valid scores coincide.

**Total inference spend:** 105 API calls; 155,789 input tokens and 1,523 output tokens (including controls). No dollar estimate is asserted.

Detailed rung scores and first-draw uncertainty intervals are in [results/summary.json](results/summary.json); audit metadata is in [results/rows.jsonl](results/rows.jsonl).

## Interpretation

A valid no-CoT response requires an explicitly present `usage.output_tokens_details.thinking_tokens == 0`, nonzero output usage, no thinking/redacted-thinking content blocks, no visible deliberation according to the upstream screen, a nonempty answer, and no output truncation. Missing counts are blind, not zero. A reasoning response counts as wrong in the primary score. The main run is gated on a clean two-draw pilot and a positive control that actually increases the thinking counter.

Native Messages usage does not provide the independent total-minus-input-minus-output witness used on some other routes. These are provider-reported token observations and content checks, not proof of a single internal forward pass. Full responses remain local for auditing; the public metadata excludes prompts, answers, gold labels, and raw thinking. Benchmark banks are not redistributed.

Only three selected domains are measured. There is no overall NCRI score, ranking, architectural inference, or direct replication of the article's cross-model odds ratio. Five items per rung have low precision. First-draw Wilson intervals in the summary avoid treating two repeats of an item as independent new problems; they are approximate selected-item intervals and omit stratification and serving uncertainty. Both draws are also reported separately. No more items are purchased based on whether the result looks interesting.

## Reproduce

Requires Python 3.9+, Git, unzip, and an Anthropic credential with model access. No Python packages are required. Obtain the benchmark locally using its upstream instructions; `setup.sh` clones the pinned upstream and verifies/unpacks its distributed archive. It will not overwrite a checkout at a different commit.

```bash
bash setup.sh
# Set ANTHROPIC_API_KEY securely in your environment; never commit it.
# Use a new directory for a fresh experiment; an existing results/ resumes it.
python replicate.py pilot
python replicate.py control
python replicate.py main
python analyze.py
```

`NOCOT_BENCH` can select a different path to the pinned benchmark checkout. Calls execute sequentially, append metadata immediately, and resume by stage/item/draw. HTTP errors stop the run without automatic retries. Main-stage pilot reuse is explicitly marked, so token totals do not double-count it. Do not delete output files unless intentionally starting another paid run.

`items.json` stores only upstream item IDs. `plan.json` records the frozen subset and recipe. Private raw responses and credentials are excluded by `.gitignore`.

## Free depth analysis

`python depth_analysis.py` analyzes the saved arithmetic responses without network calls. [Output and proposed budget](results/depth_analysis.json).

| Structural dependency depth | Correct per draw | Unique problems |
|---|---:|---:|
| 1 | 1/1 | 1 |
| 2 | 4/4 | 4 |
| 3 | 5/5 | 5 |
| 4 | 7/7 | 7 |
| 5 | 4/5 | 5 |
| 6 | 2/3 | 3 |

Both draws agree. Structural depth counts the longest binary-operation dependency path, ignoring numeric signs. It is not shortcut-aware effective depth, and does not reproduce Neel's perturbation-based, cross-task calibrated 7.2-step estimate. The maximum sampled depth has only three unique items; no reliable 50% threshold can be fitted.

A proposed extension starts with 30 responses, with a cap of 50 total: roughly 55k–95k input tokens and 360–600 expected output tokens if no-CoT holds. The hard output cap is 15,000 tokens. These are planning estimates; exact requests should be token-counted before spending. No extension has run.
