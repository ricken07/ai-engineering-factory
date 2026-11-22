# Experiment launcher

`aief_experiment.py` runs one experimental unit of the reference-model
evaluation: one coding-agent execution of one engineering task under one
control condition (L0–L3). It is maintainer tooling, not part of the Runtime:
AIEF itself only runs L3, and records the condition as explicit metadata.

| Condition | What the agent receives | How the launcher prepares it |
|---|---|---|
| L0 raw agent | the request | clone at the starting commit, then removes `.ai/`, `.claude/`, `.codex/`, `AGENTS.md` and `CLAUDE.md` in a setup commit; the agent runs without AIEF skills, user settings or project hooks |
| L1 contextualized agent | the request and a structured project context | L0, plus the frozen context file as `AGENTS.md` (and `CLAUDE.md` importing it) |
| L2 structured engineering | L1, plus the task plan and verification specification | L1, plus the frozen plan and verification files under `.experiment/`; the prompt asks the agent to follow the plan and report each acceptance criterion |
| L3 governed execution | the AIEF native command and the request | the project as it is at the starting commit; the prompt passes `--experiment-condition L3`, `--repeat-index`, `--environment-identifier`, `--agent-session`, `--model-identifier` and the frozen plan and verification as `--bound-plan`/`--bound-verification` with their `--expect-*-sha256` |

L2 and L3 receive byte-identical plan and verification files; L1 and L2 the
same context file. The prompt templates are part of the launcher and their
hash is recorded with every run.

The launcher **never approves, rejects or waives** anything. In L3 the human
decides every gate from their own terminal (`aief execution approve-policy`,
`aief execution approve`, `reject`, `waive-finding`), which the Runtime records
as `OBSERVED`. `wait` polls through `aief execution gate-check`, which applies
a passed response limit, and also waits while the integration of a completed
execution awaits `before-merge`. A cancelled execution (gate rejected or
expired), an integration rejected or expired, and a blocked
one (`review-rework-exhausted`) are final states of the run, recorded as the
Runtime left them.

It does not evaluate outcomes either: the task oracle, the evidence checklist
and the analysis are separate and run on the recorded runs.

## Inputs

- **Run descriptor** (`examples/run.yaml`): task (repository, starting commit,
  request, acceptance criteria, AIEF intent for L3), condition, agent and
  model, repeat index, frozen treatment files and their expected SHA-256. The
  launcher refuses a treatment file whose hash differs from the frozen one.
  L3 requires the frozen hashes of the plan and the verification; they are
  passed to the Runtime as `--expect-*-sha256`, which checks the bound files
  against them.
- **Environment** (`examples/environment.yaml`): environment identifier, the
  Factory used by L3, and per agent the command and the arguments of the
  `plain` group (L0–L2) and the `governed` group (L3).

## Isolation

- **Codex, L0–L2**: an isolated `HOME` (with `CODEX_HOME` holding only a link
  to the auth file, and links to build caches such as `.m2`), plus
  `--ignore-user-config --ignore-rules`: no user skills, configuration or rules.
- **Claude Code, L0–L2**: `--disable-slash-commands` (no skills or commands)
  and `--setting-sources project,local` (no user settings, plugins or user
  hooks). An isolated `HOME` is possible with a long-lived token created by
  the operator with `claude setup-token` (`tokenFile`).
- **Every agent**: settings, hooks and instructions managed by the account's
  organization still apply. The run records this as part of the isolation.

## Commands

```bash
T=tools/experiment/aief_experiment.py
python3 $T render-context --project <project> --factory <factory> --repository app --output context.md  # build an L1/L2 context to freeze
RUN=$(python3 $T prepare run.yaml --environment environment.yaml --output runs)
python3 $T start "$RUN"              # first agent invocation for the condition
python3 $T status "$RUN"             # run record, with the AIEF execution state in L3
# L3 only
python3 $T wait "$RUN"               # waits while the execution waits for a human decision
python3 $T review "$RUN" --agent codex   # independent review session after the producer's handoff
python3 $T continue "$RUN"           # resumes the producer session from `aief execution next`
python3 $T finish "$RUN"             # records the final state
```

## Run record

Each run directory holds:

| Path | Content |
|---|---|
| `run.yaml` | `ExperimentRun`: condition, repeat index, environment, task (starting commit, request hash, acceptance criteria), agent (command, version, model), Factory home and commit, prompt templates hash, treatment files and hashes, setup commit, isolation, every step (role, prompt hash, start, end, duration, exit code, session id), AIEF execution state in L3, final state |
| `repo/` | the isolated clone, on branch `experiment/<run-id>` |
| `prompts/`, `logs/` | each prompt sent, the agent's stdout and stderr per step |
| `treatment/` | copies of the frozen treatment files |
| `final/` | `workspace.patch` (every change against the base commit, untracked files included), commits, status, a patch per branch created during the run |
| `aief/` | L3: `execution.yaml`, `evidence-bundle.yaml`, `workspace.yaml`, `payload-ledger.json`, `gate-check.json`, `metrics.json` |

Step durations are wall-clock observations of the agent process. Tokens and
cost are not recorded.

## Decision validator

`check_decisions.py` checks every recorded human gate decision of L3 runs
against the study decision rule. It reads the records only and does not
import the Runtime, so it is independent of both the Runtime and the
approvers:

```bash
python3 tools/experiment/check_decisions.py runs/<run-id> [...] --rule-sha256 <pinned rule hash> [--json]
```

For each decision it reports whether it conforms (decision matching the
comparator outcome, rationale listing exactly the failing items, pinned rule
hash, protocol approver, `OBSERVED` interactive terminal) and its study
classification (`approved`, `execution-failure`, `setup-invalid`,
`operationally-invalid`, `protocol-gap`). A `before-merge` rejection on the
base branch or the merge is `setup-invalid` only when the base branch head
differs from the head the launcher recorded at the start of the run. The
exit status is 1 when any decision departs from the rule. For an
`execution.yaml` outside a launcher run, pass `--repo` and
`--initial-branch NAME=SHA`. Under gate-rule-v4 (`--rule-version v4`), it also
attributes each refused attempt: `agent`, `operator`, `unconfirmed` or
`unattributed`.

## Study outcome

`study_outcome.py` maps the Runtime facts of an L3 run to its study outcome.
It reads the records the launcher collected and writes `study-outcome.yaml`
next to them, with the facts it used copied verbatim; it never rewrites a
Runtime record:

```bash
python3 tools/experiment/study_outcome.py runs/<run-id> [...] --rule-sha256 <pinned rule hash> --write
```

| Outcome | When |
|---|---|
| `protocol-deviation` | a gate decision departs from the decision rule, an operator's attempt was refused (gate-rule-v4), a review finding was waived, review waivers were not disabled, or the execution was cancelled without a gate decision |
| `setup-invalid` | the deciding rejection is setup-invalid under the rule, or required enforcement is unavailable on the runner |
| `operationally-invalid` | the deciding gate expired; eligible for one predeclared replay |
| `unfinished` | a human gate still waits when the run is collected: not finished, not scored (not to be confused with a comparator outcome `incomplete`) |
| `execution-failure` | the deciding rejection is attributed to the execution, the execution failed, review rework is exhausted, the execution is left blocked for another reason, or the agent stopped before it ended |
| `completed` | completed and, when `before-merge` is required, integrated |

The outcomes are listed by precedence. Under gate-rule-v4, refused attempts
attributed to the agent do not change the outcome; they are listed as
`governanceViolationAttempts` for H1. Both tools take `--rule-version v3|v4`
(default `v4`, the rule pinned for scored runs) and record it. `completed` says the governed
execution ended as the protocol requires; the task oracle decides whether the
change is correct.

## Payload comparison

`compare_payloads.py` compares what an L3 execution delivered to the agent,
as its payload ledger recorded it, with the frozen L1/L2 treatment:

```bash
python3 tools/experiment/compare_payloads.py runs/<run-id>/repo/.ai/runtime/executions/<execution-id> \
  --l1-context treatment/context.md --l2-plan treatment/plan.md --l2-verification treatment/verification.yaml \
  --request "<the task request>" [--forbidden oracle/test_patch.diff] [--rework-maximum 3] [--json]
```

It reports `l3_same_l2_plan`, `l3_same_l2_verification`, `l3_same_l1_content`
(practices of producer phases, word for word; practices of the reviewer phase
are listed as part of the review intervention), `no_additional_task_semantic_facts`
(classified sections, task context limited to the request, scope and
classification, no line of a `--forbidden` file in any snapshot),
`reviewer_feedback_budget` and `no_decision_rationale_leak`. The L3-only `## Repositories` brief section is accepted as
procedural and listed, not counted as a task fact. Each is
`VERIFIED`, `FAILED` or `NEEDS_REVIEW`; the exit status is 1 on `FAILED`.

## Active budget

Every run has an active budget (`activeBudgetMinutes` in the environment file,
120 by default). Only agent process time counts: each agent step runs with the
remaining budget as its timeout, and the time between steps, while a human gate
holds the run, does not count. When the budget runs out, the agent process is
stopped, the step and the run record `resourceLimitReached`, the run status is
`resource-limit-reached`, and no further step starts. `RESOURCE_LIMIT_REACHED`
is an outcome of a valid run (`study_outcome.py`: `execution-failure`), never
an exclusion. `run.yaml` records `activeBudgetSeconds` and `activeSeconds`.

The number of human gate requests of one run is bounded (`tests/test_gate_bound.py`):
at most 10 requests and 9 sequential waits for `implement-task` (8 and 7 for
`fix-bug`), so the worst-case elapsed time of a run is 120 active minutes plus
9 × 30 minutes of response limits.

## Oracle-safe leakage check

`check_leakage.py` checks that treatment files (L1 context, L2 plan and
verification) carry no oracle content. It runs unattended where the oracle
files live and compares every treatment file with the lines a gold or test
patch adds and with oracle test files; lines already present in the
repository at the base revision (`--base-dir`) are allowed. The report gives
only counts and positions (treatment line, oracle file and line number), never
the matching content; exit status 1 on any leak:

```bash
python3 tools/experiment/check_leakage.py --treatment treatment/C01/*.md treatment/C01/*.yaml \
  --forbidden oracle/C01/gold.patch oracle/C01/test.patch --base-dir repos/xarray-at-base
```

## Scorers

Condition-neutral scorers of the confirmatory endpoints (RC2 §9). They read
the records the launcher collected and the independent evaluator's results;
they never modify a run.

| Tool | Endpoint | Input | Notes |
|---|---|---|---|
| `score_h2.py` | `D_group` per task–agent–condition block | evaluator results `{runId, task, agent, condition, evaluator: {status}, checks: {test: PASS\|FAIL\|UNAVAILABLE}}` and the frozen `FAIL_TO_PASS`/`PASS_TO_PASS` vector per task | an evaluator failure is `UNAVAILABLE`, never `FAIL`; the primary block score is `MISSING` when any component is unavailable; a secondary available-checks measure reports its denominator |
| `score_h3.py` | VerifiedEvidenceCompleteness per run (E01–E12) | run directory, task evidence manifest, task-specific verifier observations | E01–E04 and E10–E12 verified from the launcher's execution-time capture; E05–E09 need the task manifest; evaluator-only results are never credited; any `UNAVAILABLE` item leaves the primary score unavailable |
| `score_h4.py` | wall-clock duration per run, active wall-clock, gate waits | run directory (L3: collected `aief/execution.yaml`) | terminal boundary includes the `before-merge` decision or expiry; active wall-clock = elapsed − union of gate-wait intervals; `NOT_APPLICABLE` in L0–L2; unknown waits are never zero |

The scorers are skeletons until the per-task manifests (H1 checks, H3
evidence objects) are frozen with the treatment.

