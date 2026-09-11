# PromptSprint

JSON tasks -> LiteLLM execution -> one result file per task -> usage summary.

LiteLLM is the only execution layer. The provider is data in `PROVIDERS` (`main.py`), not a factory or adapter. Every call is `litellm.completion()`.

## Setup

```
python -m venv .venv
```

Windows PowerShell activation:

```
.venv\Scripts\Activate.ps1
```

Install dependencies:

```
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set the key for the provider you will use. Do not commit `.env`.

```
OPENROUTER_API_KEY=your_actual_key
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
```

Only the active provider's variables are required. Unused keys may be absent.

## Configuration

Runtime settings live in `config.json`:

- `provider` — one of `openrouter`, `openai`, `anthropic`, `gemini`, `laguna`
- `model` — LiteLLM id, including the provider prefix
- `temperature`, `max_tokens`, `timeout_seconds`
- `continue_on_error`, `overwrite_existing`
- `extra_params` — optional object passed through to `litellm.completion()`
- `available_models` — optional list of OpenRouter ids; the active `model` must be one of them unless you override with `--model` / `--provider`

Prompts live in `tasks.json`. Add, remove, or replace tasks there only.

## Commands

```
python main.py
python main.py --tasks tasks.json
python main.py --config config.json
python main.py --output responses
python main.py --task-id task_003
python main.py --overwrite
python main.py --provider gemini --model gemini/gemini-2.5-flash
```

`--provider` and `--model` override `config.json` for that run only. They are not written back.

Ping the configured model:

```
python test/connection.py
```

## Inputs

| File | Role |
|---|---|
| `config.json` | Provider, model, generation and run flags |
| `tasks.json` | List of `{task_id, prompt}` |
| `.env` | API keys and optional `api_base` values |

## Outputs

```
responses/
├── task_001.json
├── …
├── task_010.json
└── summary.json
```

Each task file has the same schema: `status`, `response`, tokens, latency, and `cost` when LiteLLM reports it (`null` otherwise). `summary.json` aggregates the run (`run_id`, provider, model, counts, tokens, cost availability, elapsed time). Secrets are never printed or saved.

Existing task files are skipped unless `overwrite_existing` is true or you pass `--overwrite`.

## Switching provider

Nothing in `main.py` needs to change for these five providers.

**OpenAI directly**

1. Add `OPENAI_API_KEY` to `.env`.
2. Set `"provider": "openai"` and `"model": "openai/<model-id>"` in `config.json`.

**Anthropic directly**

1. Add `ANTHROPIC_API_KEY` to `.env`.
2. Set `"provider": "anthropic"` and `"model": "anthropic/<model-id>"` in `config.json`.

**Gemini directly**

1. Add `GEMINI_API_KEY` to `.env`.
2. Set `"provider": "gemini"` and `"model": "gemini/<model-id>"` in `config.json`.

**Laguna directly**

1. Add `LAGUNA_API_KEY` and `LAGUNA_API_BASE` to `.env` (base URL ending in `/v1`).
2. Set `"provider": "laguna"` and `"model": "openai/<model-id>"` in `config.json`.

**OpenRouter**

1. Keep `OPENROUTER_API_KEY` and `OPENROUTER_API_BASE` in `.env`.
2. Set `"provider": "openrouter"` and `"model": "openrouter/<vendor>/<model>"` in `config.json`.

Current OpenRouter defaults include:

- `openrouter/poolside/laguna-s-2.1:free`
- `openrouter/inclusionai/ling-3.0-flash-fin:free`
- `openrouter/google/gemma-4-26b-a4b-it:free`
- `openrouter/nvidia/nemotron-3.5-lightning:free`

One-off comparison without editing files:

```
python main.py --provider anthropic --model anthropic/<model-id> --overwrite
```

**Any other OpenAI-compatible vendor**

1. Add one row to `PROVIDERS` (`key_env`, `"openai/"` prefix, `base_env`).
2. Add those variables to `.env.example`.
3. Set provider and model in `config.json`.
