# Implementation so far

Harbor + OpenHands evaluation PoC: run a **small coding benchmark** against **multiple Hugging Face models**. The run matrix is YAML-only; adding or removing a model does not require code changes.

Current demo matrix: **1 task × 1 agent × 5 models × 1 attempt = 5 trials**.

## What exists

### Model adapter
Stateless Hugging Face provider behind a `ModelProvider` interface. `HF_API_KEY` comes from `.env`. Calls return `model_name`, `output`, `token_usage`, `latency`, `error`. Wiring is constructor injection (`create_model_provider`). Inference uses `ModelSpec.hf_id` (falls back to `id`).

### Experiment matrix and compiler
`src/experiments/experiment.yaml` is the **matrix only**: `experiment_id`, `tasks`, `agents`, `models`, `attempts`.

IDs are resolved at load time:

- **Task** `health-api` → `datasets/internal-core/health-api/` (`task.toml`, instruction, starter, tests, Docker).
- **Model** `model1`…`model5` → Hugging Face ids and generation settings in `src/experiments/models.yaml`.

`ExperimentCompiler` expands **Task × Agent × Model × Attempt** into `TrialRequest` objects. The current YAML produces **5** trials.

### Benchmark task (`health-api`)
Independent of Harbor/OpenHands. Agent must add FastAPI `GET /health` returning `{"status":"ok"}`. Starter repo is incomplete; pytest checks start, HTTP 200, and exact body.

### Docker sandbox
Reproducible Python 3.12 image with FastAPI, uvicorn, pytest, **httpx**. One Compose project per `TRIAL_ID` for isolated runs. Health check prefers `/health`, falls back to OpenAPI.

`DockerSandboxFactory` copies the task starter into an isolated host workspace per `trial_id`. `SandboxSession.mount()` exposes that path to the agent; `destroy()` deletes it.

### Deterministic verifier
`Verifier` port + `DockerSandboxVerifier`. Independent of OpenHands: scores a workspace with Docker Compose only. Checks container start, image/app build, `GET /health` route, and pytest. Returns `ScoreResult` (`passed`, `build_passed`, `tests_passed`, `tests_failed`) and writes JSON artefacts under `artefacts/`.

### OpenHands agent adapter
Stateless `OpenHandsAdapter.execute(request, sandbox) -> TrialResult`. Reads `task_id`, `model_id` (`hf_id`), and `attempt_id` from `TrialRequest`, mounts the sandbox workspace, loads instructions from `task.toml` / `instruction.md`, starts OpenHands with the configured model, and captures messages, tool calls, commands, file changes, and a unified patch.

`TrialResult` contains `status`, `patch`, `trajectory`, `execution_logs`, `resource_usage`, `error_details`. The adapter does not score, store, or report. OpenHands is invoked through an injected runner (default: headless CLI). Tests use a fake runner.

### Experiment execution
`run_experiment()` loads YAML, compiles `TrialRequest`s, and runs each trial independently. `run_trial()` is the pipeline:

`TrialRequest` → sandbox → `OpenHandsAdapter` → `TrialResult` → `Verifier` → `FinalTrialResult`, then the sandbox is destroyed (including on failure). One failed trial does not stop the others.

The current matrix yields **5** independent executions. `FinalTrialResult` holds trial identity, `execution`, and `score`.

## Layout

```
src/adapters/models/     provider + HuggingFace adapter
src/adapters/verifiers/  Verifier port + Docker sandbox scorer
src/adapters/sandbox/    per-trial workspace copy + destroy
src/arms/adapters/agents/
  openhands_adapter.py   OpenHands execution → TrialResult
src/arms/application/
  run_trial.py           one trial pipeline
  run_experiment.py      compile + iterate independently
src/contracts/           TrialRequest, TrialResult, FinalTrialResult, SandboxSession, ScoreResult
src/experiments/
  experiment.yaml        matrix (IDs)
  models.yaml            alias → hf_id
  loader.py              resolve IDs
  compiler.py            expand TrialRequests
datasets/internal-core/health-api/
  task.toml, instruction.md, starter/, tests/, environment/
tests/
  test_compiler.py             load + expand (5 trials)
  test_verifier.py             verifier with a fake Docker runner
  test_openhands_adapter.py    adapter with fake OpenHands + sandbox
  test_run_experiment.py       5 independent trials; sandbox always destroyed
```

## How to check it works

From `harbor-demo/`:

```powershell
pip install -r requirements.txt
python -m pytest -q
```

Expected: compiler + verifier + OpenHands adapter + execution-layer tests pass (no Docker, no HF key, no OpenHands binary).

That covers:

| Piece | What the tests prove |
| --- | --- |
| Loader | `health-api` path + name from `task.toml`; aliases map to the five `hf_id`s |
| Compiler | exactly 5 `TrialRequest`s, one per model |
| Verifier | scoring + JSON artefact, Docker calls mocked |
| OpenHands adapter | mount, load task instructions, capture trajectory/patch/logs; error and timeout map to `TrialResult.status` |
| `run_trial` | sandbox → agent → verifier → `FinalTrialResult`; destroy on success and failure |
| `run_experiment` | 5 independent trials; one failure does not stop the rest |

Spot-check the matrix in a REPL (same directory):

```powershell
python -c "from src.experiments.compiler import ExperimentCompiler; t=ExperimentCompiler().compile(); print(len(t)); print([x.model.inference_id for x in t])"
```

Expected: `5` and the five Hugging Face model ids.

Optional, not automated yet:

- **Task tests** (`datasets/internal-core/health-api/tests/`): fail on the incomplete starter; pass after a correct `/health` implementation.
- **Hugging Face**: needs `HF_API_KEY` in `.env`. A live generate call is still manual.
- **Real Docker verifier**: `test_verifier.py` does not start containers. A live compose run needs Docker Desktop.
- **Live OpenHands**: `test_openhands_adapter.py` does not start the OpenHands CLI. A real run needs the binary, a mounted workspace, and `HF_API_KEY`.
- **Live experiment**: `run_experiment()` defaults would call real OpenHands and Docker; tests inject fakes.

## Not built yet
Harbor orchestration, reporting.
