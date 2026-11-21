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
as `OBSERVED`. A cancelled execution (gate rejected or expired) and a blocked
one (`review-rework-exhausted`) are final states of the run, recorded as the
Runtime left them.

It does not evaluate outcomes either: the task oracle, the evidence checklist
and the analysis are separate and run on the recorded runs.

## Inputs

- **Run descriptor** (`examples/run.yaml`): task (repository, starting commit,
  request, acceptance criteria, AIEF intent for L3), condition, agent and
  model, repeat index, frozen treatment files and their expected SHA-256. The
  launcher refuses a treatment file whose hash differs from the frozen one.
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
