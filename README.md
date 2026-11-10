# No-CoT replication: Fable 5.2 vs Astra

Fable 5.2 scored **94%**, versus Astra’s **98%**, on the same 50 problems without chain of thought.

| Task | Fable 5.2 | Astra |
|---|---:|---:|
| Arithmetic | 23/25 (92%) | 24/25 (96%) |
| Repeated lookup | 9/10 (90%) | 10/10 (100%) |
| Shortest paths | 15/15 (100%) | 15/15 (100%) |
| **Total** | **47/50 (94%)** | **49/50 (98%)** |

Both models repeated the same outcomes on their second draws. All compared responses passed their respective no-CoT checks. Astra’s responses come from the published benchmark; we ran only Fable 5.2.

**Usage:** 105 inference calls, 155,789 input tokens and 1,523 output tokens, including controls.

This small subset uses different serving/prompt formats and does not establish an overall model ranking.

Inspired by **Neel Nanda’s [article](https://www.lesswrong.com/posts/eRmzz8J8Qkzqvzrgg/astra-can-do-a-concerning-amount-with-no-chain-of-thought)**, using his [nocot-bench](https://github.com/neelnanda-io/nocot-bench) data and grader.

[Results](results/summary.json) · [Astra comparison](results/astra_comparison.json) · [Methods and reproduction](METHODS.md)
