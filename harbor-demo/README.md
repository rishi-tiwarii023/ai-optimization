# Implementation so far

Harbor + OpenHands evaluation PoC: run a **small coding benchmark** against **multiple models via Laguna**. The run matrix is YAML-only; adding or removing a model does not require code changes.

Current demo matrix: **1 task × 1 agent × 5 models × 1 attempt = 5 trials**.

## What exists

### Model adapter
Stateless client for a **local LiteLLM/Laguna** proxy behind a `ModelProvider` interface. `LAGUNA_API_KEY`, `LAGUNA_API_ENDPOINT` (typically `http://127.0.0.1:4000`), and `LAGUNA_PROXY_URL` come from `.env`. Requests to Laguna are sent through that HTTP proxy (localhost is not bypassed) so corporate firewalls do not drop plaintext HTTP responses. Inference uses `ModelSpec.laguna_id`. OpenHands gets `LLM_MODEL=litellm_proxy/{laguna_id}` and `LLM_BASE_URL` pointing at local Laguna.

### Experiment matrix and compiler
`src/experiments/experiment.yaml` is the **matrix only**: `experiment_id`, `tasks`, `agents`, `models`, `attempts`.

IDs are resolved at load time:

- **Task** `health-api` → `datasets/internal-core/health-api/` (`task.toml`, instruction, starter, tests, Docker).
- **Model** `model1`…`model5` → model ids and generation settings in `src/experiments/models.yaml`.

`ExperimentCompiler` expands **Task × Agent × Model × Attempt** into `TrialRequest` objects. The current YAML produces **5** trials.

### Benchmark task (`health-api`)
Independent of Harbor/OpenHands. Agent must add FastAPI `GET /health` returning `{"status":"ok"}`. Starter repo is incomplete; pytest checks start, HTTP 200, and exact body.

### Docker sandbox
Reproducible Python 3.12 image with FastAPI, uvicorn, pytest, **httpx**. One Compose project per `TRIAL_ID` for isolated runs. Health check prefers `/health`, falls back to OpenAPI.

`DockerSandboxFactory` copies the task starter into an isolated host workspace per `trial_id`. `SandboxSession.mount()` exposes that path to the agent; `destroy()` deletes it.

### Deterministic verifier
`Verifier` port + `DockerSandboxVerifier`. Independent of OpenHands: scores a workspace with Docker Compose only. Checks container start, image/app build, `GET /health` route, and pytest. Returns `ScoreResult` (`passed`, `build_passed`, `tests_passed`, `tests_failed`) and writes JSON artefacts under `artefacts/`.

### OpenHands agent adapter
Stateless `OpenHandsAdapter.execute(request, sandbox) -> TrialResult`. Reads `task_id`, `model_id` (`laguna_id`), and `attempt_id` from `TrialRequest`, mounts the sandbox workspace, loads instructions from `task.toml` / `instruction.md`, starts OpenHands with the configured model, and captures messages, tool calls, commands, file changes, and a unified patch.

`TrialResult` contains `status`, `patch`, `trajectory`, `execution_logs`, `resource_usage`, `error_details`. The adapter does not score, store, or report. OpenHands is invoked through an injected runner (default: headless CLI). Tests use a fake runner.

### Experiment execution
`run_experiment()` loads YAML, compiles `TrialRequest`s, and runs each trial independently. `run_trial()` is the pipeline:

`TrialRequest` → sandbox → `OpenHandsAdapter` → `TrialResult` → `Verifier` → `FinalTrialResult`, then the sandbox is destroyed (including on failure). One failed trial does not stop the others.

The current matrix yields **5** independent executions. `FinalTrialResult` holds trial identity, `execution`, and `score`.

After all trials, `run_experiment()` writes `artifacts/metrics.json` and then generates the HTML dashboard (`reports/index.html` by default).

### Filesystem artifact storage
After each completed trial (including failures), `FilesystemArtifactStore` writes an immutable directory `artifacts/run_<trial_id>/` with `manifest.json`, `trajectory.json`, `stdout.log`, `stderr.log`, `patch.diff`, `agent-result.json`, `resource-usage.json`, and `verifier-result.json`. Existing directories are never overwritten.

### Metrics aggregation
`MetricsCollector.collect()` turns each `FinalTrialResult` (verifier result, resource usage, trial result) into one `ModelMetrics` row: `model_name`, `status`, `build_passed`, `tests_passed`, `test_count`, `execution_time`, `token_usage`, `estimated_cost`, `tool_calls`, `score`. `score` is `1.0` when the verifier passed, otherwise `tests_passed / test_count` (or `0` if there were no tests). `aggregate()` sums counts/time/tokens/cost/tool calls and averages `score` across all trials, plus a `by_model` rollup. `run_experiment()` writes `artifacts/metrics.json` (`trials`, `aggregate`, `by_model`).

### HTML reporting dashboard
`generate_dashboard()` (Pandas + Jinja2) loads **all** `metrics.json` files under the search root, aggregates trials per model, and writes a standalone HTML file.

Default output: `reports/index.html` (template: `templates/report.html`). The dashboard includes:

1. **Experiment Summary** — total trials, passed (score `1.0`), failed
2. **Model Comparison Table** — Model, Status, Build, Tests, Execution Time, Tokens, Cost, Score
3. **Charts** — execution time, token usage, cost, and score by model
4. **Ranking** — highest score, lowest cost, fastest model

`run_experiment()` calls this automatically after writing metrics (`write_report=True` by default). Runs that write metrics outside the repo (for example tests) place the report next to those metrics under `reports/index.html`.

## Layout

```
src/adapters/models/     provider + Laguna adapter
src/adapters/verifiers/  Verifier port + Docker sandbox scorer
src/adapters/sandbox/    per-trial workspace copy + destroy
src/arms/adapters/agents/
  openhands_adapter.py   OpenHands execution → TrialResult
src/arms/adapters/storage/
  filesystem_store.py    immutable per-trial artifact directory
src/arms/reporting/
  metrics.py             ModelMetrics + MetricsCollector → metrics.json
  dashboard.py           metrics.json → reports/index.html
src/arms/cli/
  run_experiment.py      python -m arms.cli.run_experiment
src/arms/application/
  run_trial.py           one trial pipeline
  run_experiment.py      compile + iterate independently + report
arms/cli/                module shim so `python -m arms.cli.run_experiment` works from this directory
src/contracts/           TrialRequest, TrialResult, FinalTrialResult, SandboxSession, ScoreResult
src/experiments/
  experiment.yaml        matrix (IDs)
  models.yaml            alias → laguna_id
  loader.py              resolve IDs
  compiler.py            expand TrialRequests
templates/report.html    Jinja2 HTML dashboard
datasets/internal-core/health-api/
  task.toml, instruction.md, starter/, tests/, environment/
tests/
  test_compiler.py             load + expand (5 trials)
  test_verifier.py             verifier with a fake Docker runner
  test_openhands_adapter.py    adapter with fake OpenHands + sandbox
  test_run_experiment.py       5 independent trials; sandbox always destroyed
  test_filesystem_store.py       save/load artifacts; refuse overwrite
  test_metrics.py                per-trial ModelMetrics + aggregate + metrics.json
  test_dashboard.py              HTML report from metrics.json; generated after run
  test_cli_run_experiment.py     CLI summary: 5 requests, results, bundles, 1 dashboard
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
| Loader | `health-api` path + name from `task.toml`; aliases map to the five `laguna_id`s |
| Compiler | exactly 5 `TrialRequest`s, one per model |
| Verifier | scoring + JSON artefact, Docker calls mocked |
| OpenHands adapter | mount, load task instructions, capture trajectory/patch/logs; error and timeout map to `TrialResult.status` |
| `run_trial` | sandbox → agent → verifier → `FinalTrialResult`; destroy on success and failure |
| `run_experiment` | 5 independent trials; one failure does not stop the rest; writes `metrics.json` and HTML report |
| Artifact store | per-trial files written once; second save is rejected |
| Metrics | one `ModelMetrics` per trial; aggregate + `metrics.json` |
| Dashboard | loads every `metrics.json`; writes HTML with summary, comparison table, charts, ranking |
| CLI | `python -m arms.cli.run_experiment` compiles 5 requests, runs the pipeline, prints the summary |

Run the experiment from `harbor-demo/` (live Docker + OpenHands unless you inject fakes in tests):

```powershell
python -m arms.cli.run_experiment
```

Flow: read `experiment.yaml` → TrialRequests → per trial (sandbox, OpenHands, verifier, artifacts) → aggregate `metrics.json` → `reports/index.html` → print summary.

Expected summary for the current matrix:

```
TrialRequests:     5
TrialResults:      5
Artifact bundles:  5
HTML dashboard:    1
```

Spot-check the matrix in a REPL (same directory):

```powershell
python -c "from src.experiments.compiler import ExperimentCompiler; t=ExperimentCompiler().compile(); print(len(t)); print([x.model.inference_id for x in t])"
```

Expected: `5` and the five model ids.

Optional, not automated yet:

- **Task tests** (`datasets/internal-core/health-api/tests/`): fail on the incomplete starter; pass after a correct `/health` implementation.
- **Laguna**: local LiteLLM at `LAGUNA_API_ENDPOINT` (e.g. `http://127.0.0.1:4000`). Set `LAGUNA_PROXY_URL` so HTTP goes through the corporate proxy.
- **Real Docker verifier**: `test_verifier.py` does not start containers. A live compose run needs Docker Desktop.
- **Live OpenHands**: `test_openhands_adapter.py` does not start the OpenHands CLI. A real run needs the **headless CLI** on `PATH` (or `OPENHANDS_BIN`), a mounted workspace, and Laguna env vars. The `openhands-ai` pip package in the venv is the HTTP agent-server, not that CLI — without the binary every trial errors immediately.
- **Live experiment**: `run_experiment()` defaults would call real OpenHands and Docker; tests inject fakes. After a live run, open `reports/index.html`.

## Not built yet
Harbor orchestration.
