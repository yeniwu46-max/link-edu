# OpenMAIC fit assessment for LINK

Accessed: 2026-09-09 (Asia/Shanghai)

Repository: https://github.com/THU-MAIC/OpenMAIC

## Snapshot

- Approximate GitHub popularity: 33.7k stars, 5.4k forks, 523 commits as displayed by GitHub on the access date.
- Current README announces v1.0.0 on 2026-08-27.
- Root license: MIT. Bundled `packages/mathml2omml` keeps LGPL-3.0-or-later terms.
- Runtime prerequisites: Node.js >=22.19 and pnpm >=10.
- Main architecture: Next.js/React/TypeScript monorepo; LangGraph-based multi-agent orchestration; course-generation pipeline; playback and action engines; browser/HTTP/PostgreSQL/S3 storage abstractions.

## Sources inspected

- README and architecture: https://github.com/THU-MAIC/OpenMAIC
- Package and eval scripts: https://github.com/THU-MAIC/OpenMAIC/blob/main/package.json
- Evaluation directory: https://github.com/THU-MAIC/OpenMAIC/tree/main/eval
- Orchestration evaluations: https://github.com/THU-MAIC/OpenMAIC/tree/main/eval/orchestration
- Deterministic director verdict: https://github.com/THU-MAIC/OpenMAIC/blob/main/eval/orchestration/judge.ts
- Semantic answer-content judge: https://github.com/THU-MAIC/OpenMAIC/blob/main/eval/orchestration/answer-content-judge.ts
- Answer-content runner and A/B design: https://github.com/THU-MAIC/OpenMAIC/blob/main/eval/orchestration/answer-content-runner.ts
- Synthetic scenario dataset: https://github.com/THU-MAIC/OpenMAIC/blob/main/eval/orchestration/scenarios/answer-content.json
- Runtime orchestration: https://github.com/THU-MAIC/OpenMAIC/tree/main/lib/orchestration
- Playback engine: https://github.com/THU-MAIC/OpenMAIC/tree/main/lib/playback

## Relevant patterns worth adapting

1. Split deterministic and semantic judging. OpenMAIC explicitly uses deterministic parsing for binary routing/END decisions and an LLM judge only when answer quality is not mechanically decidable.
2. Turn vague quality into narrow, observable labels. Its answer-content judge separately checks `leads_with_answer` and `answered_anywhere`, exposing the specific "drift first, answer later" failure mode.
3. Strict judge-output validation. Only real booleans or exact boolean strings are accepted; malformed outputs become evaluator errors rather than silent passes or ordinary failures.
4. Run the real production prompt/parser path in evaluation instead of testing a simplified imitation.
5. Compare prompt variants with explicit baseline and with-rule treatments, using synthetic/anonymized scenarios derived from failure taxonomy.
6. Store scenario definitions separately from runners and reporters, which maps naturally to LINK's existing `fractions_acceptance.json`.

## Fit and non-fit

Strong conceptual overlap:

- multi-agent classroom roles and turn orchestration;
- live interruption/playback state;
- model/provider abstraction;
- scenario-based evaluation and LLM-as-Judge;
- synthetic/anonymized classroom failure taxonomies.

Important product and stack mismatch:

- OpenMAIC primarily has AI teachers/peers teaching a learner; LINK has a human teacher teaching virtual students and receiving evidence-based coaching.
- OpenMAIC is Next.js/React/TypeScript/LangGraph; LINK is Vue + Flask/Python with a deliberately small single-process runtime.
- Importing the whole application would replace rather than incrementally improve the current architecture.
- OpenMAIC's evaluation code is repository-specific infrastructure, not a general replacement for DeepEval, Promptfoo, or an observability platform.
- Its README warns that the reference `PERSISTENCE_DEV_TOKEN` is visible in browser code and provides no user isolation; it is only suitable for localhost/trusted-network single-user use.

## Recommendation

Do not merge or vendor the full OpenMAIC repository into LINK. Adapt its evaluation patterns into a Python-native LINK harness, and selectively inspect published `@openmaic/*` packages only if LINK later adds generated slides, quizzes, PPTX import/export, or a course authoring workbench. Keep LINK's existing evidence validation authoritative; add narrow semantic judges and A/B scenario runs inspired by OpenMAIC, optionally implemented through DeepEval.
