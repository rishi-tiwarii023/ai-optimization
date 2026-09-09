# Implementation so far

Harbor + OpenHands evaluation PoC: run a **small coding benchmark** against **multiple Hugging Face models**, with the experiment matrix defined in YAML (no code changes to add/remove models).

Current demo matrix: **1 task × 1 agent × 5 models × 1 attempt → 5 trials**.

## What exists

### Model adapter
Stateless Hugging Face provider behind a `ModelProvider` interface. `HF_API_KEY` comes from `.env`. Calls return a common schema: `model_name`, `output`, `token_usage`, `latency`, `error`. Wiring is constructor injection (`create_model_provider`).

### Experiment compiler
`experiment.yaml` → `TrialRequest` list. Expansion is **Task × Agent × Model × Attempt**. Models, tasks, agents, and attempt count are YAML-only.

### Benchmark task (`health-api`)
Independent of Harbor/OpenHands. Agent must add FastAPI `GET /health` → `{"status":"ok"}`. Starter repo is incomplete; pytest checks start, HTTP 200, and exact body.

### Docker sandbox
Reproducible Python 3.12 image with FastAPI, uvicorn, pytest, **httpx2**. One Compose project per `TRIAL_ID` for isolated runs. Health check prefers `/health`, falls back to OpenAPI.

## Layout

```
src/adapters/models/     provider + HuggingFace adapter
src/contracts/           Pydantic config, response, TrialRequest
src/experiments/         YAML + loader + compiler
datasets/internal-core/health-api/
  task.toml, instruction.md, starter/, tests/, environment/
```

## Not built yet
OpenHands agent adapter, trial runner, Harbor orchestration, scoring/reporting.
