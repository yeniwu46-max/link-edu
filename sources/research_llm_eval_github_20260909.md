# LLM / Agent evaluation GitHub research

Accessed: 2026-09-09 (Asia/Shanghai)

Purpose: shortlist actively maintained, high-star repositories relevant to adding LLM-as-a-Judge, agent feedback, regression evaluation, and observability to LINK's Flask + Vue classroom application.

## Repository snapshot

Star counts are approximate values displayed by GitHub on the access date and will change.

| Repository | Approx. stars | License note | Relevant capabilities | Source |
|---|---:|---|---|---|
| promptfoo/promptfoo | 24.9k | MIT | Declarative prompt/agent/RAG tests, `llm-rubric`, G-Eval, trajectory goal success, custom Python/JS assertions, CI, red teaming | https://github.com/promptfoo/promptfoo |
| confident-ai/deepeval | 18.2k | Apache-2.0 | Pytest-style LLM tests, custom metrics, G-Eval, DAG metrics, conversational and agent metrics | https://github.com/confident-ai/deepeval |
| comet-ml/opik | 21.9k | Apache-2.0 | Self-hosted tracing, datasets, experiments, LLM-as-a-Judge, annotations, online evaluation and dashboards | https://github.com/comet-ml/opik |
| langfuse/langfuse | 34.4k | MIT except `ee` directories / verify deployment edition | Tracing, prompt management, datasets, experiments, human/LLM/code scores, annotation queues | https://github.com/langfuse/langfuse |
| Arize-ai/phoenix | 11.4k | Elastic License 2.0; review product-use restrictions | OpenTelemetry/OpenInference tracing, datasets, experiments, evaluators, prompt replay; easy local Python start | https://github.com/Arize-ai/phoenix |
| vibrantlabsai/ragas | 15.7k | Apache-2.0 | RAG-focused metrics, synthetic test generation, custom aspect metrics; agent templates still listed as coming soon in current README | https://github.com/vibrantlabsai/ragas |
| UKGovernmentBEIS/inspect_ai | 2.7k | MIT | Rigorous model/agent eval tasks, tool-use and multi-turn evaluation, model-graded scoring; stronger fit for model research than this app's first integration | https://github.com/UKGovernmentBEIS/inspect_ai |

## Primary documentation checked

- Promptfoo LLM rubric: https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/
- Promptfoo assertion/metric catalog: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- DeepEval G-Eval: https://deepeval.com/docs/metrics-llm-evals
- DeepEval custom metrics: https://deepeval.com/docs/metrics-custom
- Langfuse LLM-as-a-Judge: https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge
- Langfuse scores and annotation methods: https://langfuse.com/docs/evaluation/scores/overview
- Opik repository capabilities: https://github.com/comet-ml/opik
- Phoenix repository capabilities and license: https://github.com/Arize-ai/phoenix
- Ragas repository and current roadmap: https://github.com/vibrantlabsai/ragas
- Inspect AI repository: https://github.com/UKGovernmentBEIS/inspect_ai

## Project-specific interpretation

1. LINK already performs deterministic structural and provenance checks in `backend/services/classroom_reports.py`; these should remain authoritative and run before any probabilistic judge.
2. The current report model produces the six scores and reasons, while `validate_report` checks that cited event IDs exist and are eligible. It does not verify that the natural-language claim is semantically supported by the cited event. A second, independent judge or calibrated evaluator is therefore useful.
3. `backend/data/fractions_acceptance.json` already contains 36 synthetic acceptance scenarios and natural-language expected behavior. It is the natural seed for a versioned golden evaluation dataset, after adding expected labels, severity, deterministic invariants, and human-reviewed judge labels.
4. Recommended first adoption: DeepEval inside the existing Python test workflow, plus Promptfoo as a separate black-box/model-comparison and red-team harness. Adopt only one observability platform later; Opik is the cleanest fully Apache-2.0 all-in-one option, while Langfuse is the most popular and Phoenix is the lightest local Python trial but now has an ELv2 license.
