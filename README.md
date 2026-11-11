# No-CoT comparison: Fable 5.2 vs Astra

Using released problems from **Neel Nanda’s [no-CoT evaluation](https://www.lesswrong.com/posts/eRmzz8J8Qkzqvzrgg/astra-can-do-a-concerning-amount-with-no-chain-of-thought)** and his [nocot-bench](https://github.com/neelnanda-io/nocot-bench) data and grader.

## Matched original problems

60 problems: 15 per task, with five low-, five medium-, and five higher-difficulty items. Fable was tested twice; Astra’s scores come from one published response per identical problem.

| Task | Fable draw 1 | Fable draw 2 | Astra |
|---|---:|---:|---:|
| Arithmetic | 10/15 | 10/15 | 11/15 |
| Repeated lookup | 10/15 | 9/15 | 10/15 |
| State machine | 8/15 | 7/15 | 11/15 |
| Configuration patches | 9/15 | 9/15 | 12/15 |
| **Total** | **37/60 (61.7%)** | **35/60 (58.3%)** | **44/60 (73.3%)** |

Eight of Fable’s 120 replies used thinking tokens and count as wrong. Two hard source-bank cells exceeded the invalid-response threshold. On the remaining 50 items, Fable scored **70% / 68%**, versus Astra’s **86%**. No evaluation responses were missing or truncated.

**Cost: approximately $3.53**, including prompt search and controls, below the $4 cap. No new Astra calls. This is an exploratory matched-item comparison with model-specific prompts, not an overall ranking or a reproduction of the normalized 7.2-step result.

[Results](results/matched_summary.json) · [Paired comparison and validity gates](results/matched_comparison.json) · [Methods and reproduction](METHODS.md)

## Earlier small runs

The initial easier 50-problem subset scored 94% for Fable versus 98% for Astra. A separate custom arithmetic diagnostic suggested a highly uncertain ~6-step threshold; its units are not directly comparable to Neel’s 7.2. [Earlier results](results/summary.json) · [Depth diagnostic](results/continuation_depth_fit.json)
