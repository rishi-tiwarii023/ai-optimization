# PromptSprint Frontend

I use this dashboard to configure models, edit tasks, and run PromptSprint from the browser. It is a settings and run console, not a chat UI.

The React app talks to my FastAPI process (`api.py`) through the Vite `/api` proxy. When I save in the UI, I write the same files I use from the CLI: `config.json`, `.env`, `tasks.json`, and `responses/`.

```
Browser :5173          FastAPI :8000              Files
Config  ─────────────► GET/PUT /config  ────────► config.json, .env
Tasks   ─────────────► GET/PUT /tasks   ────────► tasks.json
Results ─────────────► POST /run, /score ───────► main.py / score.py
        ─────────────► GET /responses*  ────────► responses/
```

I open [http://localhost:5173](http://localhost:5173). Routes I use:

| Path | Page |
|---|---|
| `/config` | Provider, model, API key, base URL, run flags |
| `/tasks` | Add, edit, delete prompts |
| `/results` | Run tasks, score, inspect outputs |

---

## How I run the frontend

The API has to be up. Vite proxies `/api` to `http://127.0.0.1:8000`.

### 1. API (project root)

I activate the venv, then:

```
pip install -r requirements.txt
uvicorn api:app --reload --port 8000 --reload-exclude ".venv" --reload-exclude "frontend" --reload-exclude "responses"
```

Or:

```
python api.py
```

### 2. Frontend (second terminal)

```
cd frontend
npm install
npm run dev
```

Then I open [http://localhost:5173](http://localhost:5173). Config is the default page.

Other scripts I use:

```
npm run build      # production bundle in dist/
npm run preview    # serve the production build
```

If the UI shows request errors, my API is not up or is not on port 8000.

---

## How I update configuration

I open **Config**. Values load from `config.json` and `.env`. I click **Save** to write them back. If the API rejects a field, I see the error above the form.

### Provider and model

1. I choose **Provider**: `openrouter`, `openai`, `anthropic`, `gemini`, or `laguna`.
2. I set **Model** to a LiteLLM id with that provider’s prefix (for example `openrouter/poolside/laguna-s-2.1:free`). Laguna uses the `openai/` prefix.
3. I keep the active model in **Available models**. I type a model id and press Enter to add a tag; I click `x` to remove one. Save fails if `model` is not in this list.

### API key and base URL

- **API key** is write-only. I never see a stored key. A placeholder means I already have a key set; I leave the field blank to keep it.
- **Base API URL** shows only for providers that need it (`openrouter`, `laguna`). It maps to `OPENROUTER_API_BASE` or `LAGUNA_API_BASE`.

Save writes the key and base URL into `.env` for the provider I selected. I do not commit `.env`.

### Generation and run flags

| Field | What I use it for |
|---|---|
| Temperature | `0.0`–`2.0` |
| Max tokens | A number, or I toggle **Use provider default** (`null`) |
| Timeout (s) | Per-call timeout |
| Score successful responses | When I turn this on, a **Judge model** field appears (same prefix as provider; optional, defaults to my run model) |
| Continue on error | Keep going after a failed task |
| Overwrite existing results | Replace files already in `responses/` |
| Extra params | JSON object passed through to `litellm.completion()` |

These persist in `config.json` for both this UI and `python main.py`.

---

## How I update tasks

I open **Tasks**. The table is `tasks.json`.

1. **Add task** — I get a new row with a `task_id` I can edit until the first save.
2. I edit **prompt** in the textarea. After I save, that `task_id` stays locked.
3. **Delete** on a row removes that task. I use checkboxes + **Delete selected** when I want several gone at once.
4. **Save all** writes the full list in one request. Nothing is stored until I save.

`task_id` may contain only letters, numbers, underscores, and hyphens. Duplicate ids and empty prompts are rejected.

---

## How I see results and run jobs

I open **Results**.

### Run

1. I can set **Provider override**, **Model override**, or **Task ID filter**. If I leave a field blank, I use `config.json` / all tasks. Overrides apply to that run only; they are not written back.
2. I toggle **Overwrite** when I want to replace existing result files. I toggle **No scoring** to skip the judge even if scoring is on in config.
3. I click **Run**. Stdout from `main.py` streams into the console. When the process exits, summary tiles and the results table refresh.

Existing result files are skipped unless I turn overwrite on.

### Score

I click **Score** to run `score.py` on already-saved responses (failed tasks are skipped). I use **Overwrite** if I want to rescore. `score_stats` is written into `responses/summary.json`.

### Summary

Tiles come from `responses/summary.json`: run id, provider, model, timestamps, counts (total / successful / failed / skipped), tokens, reported cost, elapsed time, average latency. I only see score stats (mean, median, mode, max, p95, std_dev) when scoring produced values.

### Task table

Columns: `task_id`, `status`, `score`, `total_tokens`, `latency_ms`, `cost`. I click a row for a drawer with prompt, response, error (if failed), and raw metrics. Files live in `responses/<task_id>.json`.

---

## Pages and files

```
frontend/
├── README.md
├── package.json
├── vite.config.js          # /api → :8000
└── src/
    ├── App.jsx
    ├── api.js
    ├── pages/
    │   ├── ConfigPage.jsx
    │   ├── TasksPage.jsx
    │   └── ResultsPage.jsx
    └── components/
        ├── Navbar.jsx
        ├── FieldRow.jsx
        └── Toggle.jsx
```

CLI for the same backend is in [../README.md](../README.md).
