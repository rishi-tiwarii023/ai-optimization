import asyncio
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from main import (
    PROVIDERS,
    RESPONSES_DIR,
    TASK_ID_PATTERN,
    load_config,
    load_json,
    load_tasks,
    provider_spec,
    validate_config,
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
TASKS_PATH = ROOT / "tasks.json"
ENV_PATH = ROOT / ".env"
RESPONSES_PATH = ROOT / RESPONSES_DIR

load_dotenv(ENV_PATH)

app = FastAPI(title="PromptSprint")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

run_lock = asyncio.Lock()


class ConfigUpdate(BaseModel):
    provider: str
    model: str
    available_models: Optional[List[str]] = None
    temperature: float
    max_tokens: Optional[int] = None
    timeout_seconds: int
    continue_on_error: bool
    overwrite_existing: bool
    scoring: bool = False
    judge_model: Optional[str] = None
    extra_params: dict = Field(default_factory=dict)
    api_key: Optional[str] = None
    api_base: Optional[str] = None


class TaskItem(BaseModel):
    task_id: str
    prompt: str


class RunBody(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    task_id: Optional[str] = None
    overwrite: bool = False
    no_scoring: bool = False


class ScoreBody(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    task_id: Optional[str] = None
    overwrite: bool = False


def http_fail(message, status_code=400):
    raise HTTPException(status_code=status_code, detail=message)


def call_or_http(fn, *args, status_code=400, **kwargs):
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf):
            return fn(*args, **kwargs)
    except SystemExit:
        message = buf.getvalue().strip() or "Invalid request"
        raise HTTPException(status_code=status_code, detail=message)


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def upsert_env(key, value):
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    found = False
    updated = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            updated.append(line)
            continue
        name = line.split("=", 1)[0].strip()
        if name == key:
            updated.append(f"{key}={value}")
            found = True
        else:
            updated.append(line)
    if not found:
        if updated and updated[-1] != "":
            updated.append("")
        updated.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(updated) + "\n", encoding="utf-8")
    load_dotenv(ENV_PATH, override=True)


def config_to_file(body: ConfigUpdate):
    payload = body.model_dump(exclude={"api_key", "api_base"})
    if payload.get("extra_params") is None:
        payload["extra_params"] = {}
    return payload


def env_status(name):
    spec = provider_spec(name)
    api_key = os.getenv(spec["key_env"]) or ""
    item = {
        "name": name,
        "key_env": spec["key_env"],
        "prefix": spec["prefix"],
        "base_env": spec["base_env"],
        "base_optional": bool(spec.get("base_optional")),
        "custom": name not in PROVIDERS,
        "api_key_set": bool(api_key.strip()),
        "api_base": None,
    }
    if spec["base_env"]:
        item["api_base"] = os.getenv(spec["base_env"]) or ""
    return item


@app.get("/providers")
def get_providers():
    names = list(PROVIDERS)
    if CONFIG_PATH.exists():
        try:
            config = load_config(str(CONFIG_PATH))
            current = config.get("provider")
            if isinstance(current, str) and current.strip() and current.strip() not in names:
                names.append(current.strip())
        except Exception:
            pass
    return [env_status(name) for name in names]


@app.get("/config")
def get_config():
    if not CONFIG_PATH.exists():
        http_fail("Missing file: config.json", 404)
    return call_or_http(load_config, str(CONFIG_PATH), status_code=400)


@app.put("/config")
def put_config(body: ConfigUpdate):
    payload = config_to_file(body)
    validated = call_or_http(validate_config, payload, enforce_available_models=True)
    write_json(CONFIG_PATH, validated)
    spec = provider_spec(validated["provider"])
    if body.api_key and body.api_key.strip():
        upsert_env(spec["key_env"], body.api_key.strip())
    if spec["base_env"] is not None and body.api_base is not None:
        if body.api_base.strip() or not spec.get("base_optional"):
            upsert_env(spec["base_env"], body.api_base.strip())
    return {"ok": True, "config": validated, "provider": env_status(validated["provider"])}


@app.get("/tasks")
def get_tasks():
    if not TASKS_PATH.exists():
        http_fail("Missing file: tasks.json", 404)
    return call_or_http(load_tasks, str(TASKS_PATH), status_code=400)


@app.put("/tasks")
def put_tasks(tasks: List[TaskItem]):
    payload = [item.model_dump() for item in tasks]
    fd, tmp_path = tempfile.mkstemp(dir=str(ROOT), prefix=".tasks.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        validated = call_or_http(load_tasks, tmp_path, status_code=400)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    for item in validated:
        if not TASK_ID_PATTERN.fullmatch(item["task_id"]):
            http_fail(f'Invalid task_id {item["task_id"]!r}.')
    write_json(TASKS_PATH, validated)
    return validated


def list_result_files():
    if not RESPONSES_PATH.is_dir():
        return []
    results = []
    for name in sorted(os.listdir(RESPONSES_PATH)):
        if name == "summary.json" or not name.endswith(".json") or name.startswith("."):
            continue
        path = RESPONSES_PATH / name
        try:
            payload = load_json(str(path))
        except SystemExit:
            continue
        if isinstance(payload, dict):
            results.append(payload)
    return results


@app.get("/responses")
def get_responses():
    return list_result_files()


@app.get("/responses/summary")
def get_summary():
    path = RESPONSES_PATH / "summary.json"
    if not path.exists():
        http_fail("Missing file: summary.json", 404)
    payload = call_or_http(load_json, str(path), status_code=400)
    if not isinstance(payload, dict):
        http_fail("Invalid JSON in summary.json: expected a JSON object.")
    return payload


@app.get("/responses/{task_id}")
def get_response(task_id: str):
    if not TASK_ID_PATTERN.fullmatch(task_id):
        http_fail(f"Invalid task_id {task_id!r}.")
    path = RESPONSES_PATH / f"{task_id}.json"
    if not path.exists():
        http_fail(f"Missing file: {task_id}.json", 404)
    payload = call_or_http(load_json, str(path), status_code=400)
    if not isinstance(payload, dict):
        http_fail(f"Invalid JSON in {task_id}.json: expected a JSON object.")
    return payload


def build_script_command(script, body):
    command = [sys.executable, "-u", str(ROOT / script)]
    if getattr(body, "provider", None):
        command.extend(["--provider", body.provider])
    if getattr(body, "model", None):
        command.extend(["--model", body.model])
    if getattr(body, "task_id", None):
        command.extend(["--task-id", body.task_id])
    if getattr(body, "overwrite", False):
        command.append("--overwrite")
    if getattr(body, "no_scoring", False):
        command.append("--no-scoring")
    return command


async def stream_script(command):
    if run_lock.locked():
        yield f"data: {json.dumps({'error': 'A run is already in progress'})}\n\n"
        return
    async with run_lock:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=env,
            bufsize=1,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        loop = asyncio.get_running_loop()
        yield f"data: {json.dumps({'line': 'starting run'})}\n\n"
        try:
            while True:
                line = await loop.run_in_executor(None, process.stdout.readline)
                if line == "":
                    break
                yield f"data: {json.dumps({'line': line.rstrip()})}\n\n"
            code = await loop.run_in_executor(None, process.wait)
        except asyncio.CancelledError:
            process.kill()
            raise
        yield f"data: {json.dumps({'done': True, 'exit_code': code})}\n\n"


def sse_response(command):
    return StreamingResponse(
        stream_script(command),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/run")
async def post_run(body: Optional[RunBody] = None):
    payload = body or RunBody()
    return sse_response(build_script_command("main.py", payload))


@app.post("/score")
async def post_score(body: Optional[ScoreBody] = None):
    payload = body or ScoreBody()
    return sse_response(build_script_command("score.py", payload))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=[".venv", "frontend", ".git", "responses", "__pycache__"],
    )
