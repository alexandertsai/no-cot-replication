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

## Harder arithmetic follow-up: stopped on no-CoT failure

The approved extension targeted depths 7, 9 and 11, initially 30 responses with a 50-call cap. These are new, separately labelled diagnostic items, not part of the sealed benchmark. The upstream arithmetic generator produced a frozen initial set and reserves at depths 4–11 using seed 20261111. Each item rejects locally redundant operations and has a longest structural path where independently perturbing every operation output by either +1 or -1 changes the final answer. This finite sensitivity audit does not eliminate all algebraic shortcuts or reproduce Neel's cross-task calibration. Public files contain IDs/hashes, not questions or answers.

Native token counting estimated 54,166 input tokens for the planned 30 calls. Only **two inference calls actually ran**, both on the same depth-7 item:

- Original recipe: **124 thinking tokens**, invalid.
- One stronger answer-or-guess system prompt: **114 thinking tokens**, invalid; validation stopped immediately.

Total additional usage: **3,680 input tokens and 264 output tokens**. No further hard items or repeats were purchased. The existing positive control had already demonstrated a responsive counter. We did not fit a sigmoid or estimate a 50% threshold from these failed protocol probes. A failed no-CoT check does not establish inability to solve the arithmetic task without thinking under another elicitation method.

`python hard_arithmetic.py prepare` regenerates the private diagnostic items. `python hard_arithmetic.py summary` reproduces the report. Both inference runners stop on the first invalid response and refuse to resume after a recorded invalid response. `replicate.request` accepts an optional system text for the separately recorded repair; the original recipe remains the default. [Manifest](results/hard_manifest.json), [original attempt](results/hard_rows.jsonl), [repair recipe](results/hard_recipe.json), [repair attempt](results/hard_recipe_validation.jsonl), [summary](results/hard_summary.json).

## Budgeted continuation: a usable recipe, limited depth evidence

The user authorized up to $4 in additional token spending. Published Fable 5.2 standard rates were verified at $8/M input and $40/M output tokens ([source](https://platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2)). No fast mode, prompt caching, external compute, or browser was used. Seven recipes were screened in fixed order on three reserved items at depths 7/9/11. Recipe selection used only no-CoT validity, never answer accuracy. The eighth planned recipe was not needed.

The selected recipe, `strong_plain_hard10`, uses upstream v2 plus its strong no-deliberation paragraph, ten harder gold-answer demonstration turns, plain output, low effort, and a 100-token cap. Demonstration IDs are disjoint from screening/validation and measured items. All ten validation responses (five reserved items, two draws each) were clean. A fresh max-effort control returned 170 thinking tokens, validating the counter. Screen and validation calls are distinct requests even where their item IDs coincide.

The main sample contains five held-out problems at each of depths 7/9/11, two draws each. The predefined downward expansion measured depths 5/6. After seeing noisy 5/6/7 scores, one additional group at depth 4 was declared before its ten calls to anchor the lower end. This was an adaptive diagnostic, not a preregistered confirmatory test.

There were **92 continuation inference calls**: 21 screens, 10 validations, 1 control, and 60 main responses over 30 distinct problems. Returned usage: **182,983 input tokens and 3,937 output tokens**. Estimated standard token cost: **$1.621344**. Estimated total across the entire Fable experiment, including the original subset and first two hard probes: **$2.968576**. These are token-price calculations, not account invoices.

Before every paid request, the script calls native token counting and reserves at twice published standard rates, allowing 25% + 256 prompt tokens above the count and the full output limit. The initial guard accumulated all maximum reservations and paused at 76 calls despite an estimated actual cost of $1.33. It was revised to release unused reservations only after usage arrives: completed requests retain twice their calculated cost; unsettled requests keep their full maximum. No retry is automatic. This allowed completion without changing the $4 cap. The spending ledger stays local in ignored `private/`; the revision note is preserved. Final conservative accounted bound: **$3.242688**, below $4. Summing historical per-call maxima is not the simultaneous budget commitment or actual spend.

### Scoring and failures

Nontruncated reasoned replies count as wrong in the primary score. Truncated and blind responses are missing and excluded from its denominator. The summary also separately reports success per all attempted calls; it must not be confused with the primary score. No counters were blind in this continuation.

| Depth | Primary correct/scorable | Valid responses | Truncated/missing | Other no-CoT-invalid |
|---|---:|---:|---:|---:|
| 4 | 10/10 | 10/10 | 0 | 0 |
| 5 | 6/10 | 10/10 | 0 | 0 |
| 6 | 3/10 | 9/10 | 0 | 1 |
| 7 | 4/9 | 9/10 | 1 | 0 |
| 9 | 0/5 | 5/10 | 5 | 0 |
| 11 | 0/4 | 3/10 | 6 | 1 |

Depth 9 has 50% missing responses. Depth 11 has 60% missing and 25% invalid among the four scorable responses. Neither enters the fit. High-depth protocol failure is not evidence that the model cannot compute at those depths under other elicitation methods.

### Descriptive threshold fit

`python fit_continuation.py` fits a decreasing logistic curve separately to each draw at depths 4/5/6/7. It never treats the second draw as new independent items. The zero-chance-floor model gives 50% crossings of approximately **6.04** and **5.82** structural steps. Nominal profile-likelihood 95% intervals are **4.78–12.80** and **4.32–16.36**, conditional on this small selected sample. They do not include task-design, adaptive selection, or full serving uncertainty. These are weak descriptive estimates, not precise model limits. They cannot be compared directly with Neel's cross-task normalized 7.2-step estimate.

The stronger instructions and harder demonstrations changed the setup from the original 94% subset. The custom items are also sensitivity-filtered. Do not merge the original and continuation accuracy curves.

Reproduce metadata summaries with `python budget_continuation.py summary` and `python fit_continuation.py`. Running `python budget_continuation.py` resumes existing calls; from an empty output directory it performs paid inference under its budget guard. Keep the local private ledger and result rows when resuming, and do not delete records to retry. All manifests, recipe settings, costs, validity flags, and fits are under `results/continuation_*`. Raw replies, thinking content, questions, and gold answers remain in ignored `private/`.

## Matched original serial-task comparison

### Frozen selection and baseline

The user authorized a separate $4 run, intended to compare Fable 5.2 against existing Astra results on identical released problems. Seed `20261112` selected **60 previously untested Fable main items**, 15 per family, with five low, five middle, and five hard items. Within a stratum, nominal difficulty levels were sampled round-robin with seeded shuffled item order. Selection used item availability, difficulty labels, and previous-exposure exclusions, never Astra correctness. Five separate validation items per family and three potential hard demonstrations per family were reserved before inference. All three sets are disjoint. The public manifest contains IDs and hashes; task text and golds stay private.

Families and banks: `arithmetic` / `arithmetic_hi`; `brew` / `brew_v2s` at h7; `chain` / `chain_hi`; and `cfgpatch` / `cfgpatch_hi`. The rejected `brew_hi` extension is explicitly breadth/scan-confounded in Neel's manifest, so it was not used. The harder banks include supplemental rungs not scored in NCRI. Difficulty labels vary by task and are not a common serial-step unit. No index or normalized depth is fitted.

The baseline is the first published Astra response on each of the same 60 items. The shipped second Astra draw does not cover all harder banks. Both Fable repeats are compared against this one fixed Astra realization; it is not counted twice as independent Astra evidence. Both models are normalized consistently for JSON answer wrappers and regraded using the same upstream answer grader. All 60 Astra regrades agree with the published correctness verdicts, and all have explicit zero hidden-token discrepancy.

### Recipe search and post-declared completion

The six initial configurations varied the upstream immediate-recall/strong system instruction, plain versus JSON output, canonical versus three hard demonstrations, and one versus all available canonical examples. Search used only no-CoT validity, not answer correctness. For one-shot banks, the canonical and one-shot strong plain configurations have identical wires; their calls are serving repeats, not independent prompt designs. The initial configurations validated arithmetic and state-machine tasks on five reserved items twice. Fresh maximum-effort controls showed nonzero thinking counters.

Lookup and patches did not meet the strict zero-invalid validation rule. Two zero-demonstration configurations were declared and tested next. Strong JSON without demonstrations gave 9/10 valid lookup probes and 8/10 valid patch probes. Before buying their held-out evaluations, a further completion plan explicitly relaxed the exploratory criterion to at least 8/10 valid probes while retaining every reasoning failure and source-bank validity flags. This was post-declared and must not be described as clean confirmatory validation. The hard validation subsets had higher invalid fractions than those pooled task figures. Controls for these two tasks also returned nonzero thinking counters.

Selected settings: arithmetic `strong_schema` (canonical demonstrations); state machine `strong_schema_hard3`; lookup and patches `strong_schema_zero` under the exploratory completion. All use native Anthropic Messages, adaptive thinking, low effort, a 300-output-token JSON cap, and the upstream v2 plus strong no-deliberation text. Control calls use maximum effort, no no-deliberation system, and a 512-token cap. There were no fresh Astra calls, browser actions, or remote-compute calls.

### Results and exclusions

All **120 Fable main responses** arrived without blind usage or truncation. Eight used thinking tokens and are wrong in the primary score. The table below keeps them in the denominator.

| Family | Fable draw1 | Fable draw2 | Published Astra |
|---|---:|---:|---:|
| arithmetic | 10/15 | 10/15 | 11/15 |
| brew | 10/15 | 9/15 | 10/15 |
| chain | 8/15 | 7/15 | 11/15 |
| cfgpatch | 9/15 | 9/15 | 12/15 |

Overall: Fable **37/60** and **35/60**, Astra **44/60**. The first Fable draw is the primary paired comparison; the second is a serving repeat on the same items. The exploratory exact McNemar p-values are 0.0923 and 0.0117, respectively; do not select the more favorable repeat or treat them as independent replications over new items.

We also apply a common source-bank inclusion set: exclude a cell if either model has >20% invalid among scorable replies or >20% missing. Fable cell quality is evaluated across both draws, so the inclusion set does not change between repeats. The missingness cutoff is an additional conservative guard, not a claim of an identical Neel rule. Arithmetic-hi and brew-v2s each had 3/10 invalid Fable responses, excluding ten distinct items. The remaining **50** matched items give Fable **35/50 (70%)** and **34/50 (68%)**, Astra **43/50 (86%)**. This is a different 50-item set from the original easier subset. Exclusion depends on protocol validity, not answer correctness, but this qualified-subset analysis is still exploratory.

### Budget and audit

This matched run used **231 inference calls**: 107 probes, 4 controls, and 120 evaluations. Returned usage was **408,542 input tokens and 6,599 output tokens**. Estimated standard cost at the verified $8/M input and $40/M output rates is **$3.532296**, below the separate $4 cap. Prices are token-based calculations, not a retrieved account invoice.

Every paid request was token-counted and reserved before transmission, with a 25% + 256 input-token allowance, full output cap, and a 20% rate margin. Settled usage was initially carried at 1.2x estimated standard cost; before exploratory completion this was changed to 1.1x so unused reserves could fund the remaining fixed tests while retaining a price margin. Unknown or failed requests retain their full reserve and are not automatically retried. The final conservative committed amount is **$3.885526**, still under $4. [Completion and budget revision](results/matched_completion_plan.json). The spending ledger stays only in ignored `private/matched_ledger.jsonl`, in accordance with the request to remove public ledgers.

`python matched_serial.py prepare` reconstructs the frozen selection from the pinned local upstream data. `preflight` token-counts initial prompts without model inference. `run` is the strict initial recipe search and can perform paid calls from a fresh directory. `python complete_matched.py` is the separately declared exploratory completion, also budget-guarded. Existing rows are reused on resume; retain the private ledger for unsettled-request protection. Reproduce saved analyses for free with `python matched_serial.py summary` and `python analyze_matched.py`. Raw answers/thinking and the original questions/golds remain private.

Public artifacts: [manifest](results/matched_manifest.json), [initial plan](results/matched_plan.json), [zero-shot extension](results/matched_search_extension.json), [completion plan](results/matched_completion_plan.json), [selected recipes](results/matched_recipes.json), [Fable metadata](results/matched_rows.jsonl), [Astra metadata](results/matched_astra.json), [summary](results/matched_summary.json), and [paired analysis](results/matched_comparison.json).
