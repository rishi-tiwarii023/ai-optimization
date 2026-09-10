from __future__ import annotations

from pathlib import Path

from src.arms.adapters.agents.openhands_adapter import OpenHandsAdapter, OpenHandsOutcome
from src.contracts.config import AgentSpec, AppSettings, ModelSpec, ProviderConfig, TaskSpec
from src.contracts.trials import TrialRequest


class FakeSandbox:
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        self.mount_calls = 0

    def mount(self) -> Path:
        self.mount_calls += 1
        return self._workspace


class FakeRunner:
    def __init__(self, outcome: OpenHandsOutcome, mutate=None) -> None:
        self.outcome = outcome
        self.mutate = mutate
        self.calls: list[dict] = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.mutate is not None:
            self.mutate(kwargs["workspace"])
        return self.outcome


def _request(task_path: str) -> TrialRequest:
    return TrialRequest(
        trial_id="exp::health-api::openhands::model1::1",
        experiment_id="exp",
        task=TaskSpec(id="health-api", name="Health API", path=task_path),
        agent=AgentSpec(id="openhands"),
        model=ModelSpec(id="model1", laguna_id="google/gemma-3-12b-it"),
        attempt=1,
        provider=ProviderConfig(type="laguna", prefix="litellm_proxy"),
    )


def test_execute_captures_trajectory_patch_and_logs(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text(
        'task_id = "health-api"\nname = "Health API"\ndescription = "Add GET /health"\n',
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text("Return {\"status\":\"ok\"}.", encoding="utf-8")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "app.py").write_text("print('start')\n", encoding="utf-8")

    def mutate(root: Path) -> None:
        (root / "app.py").write_text("print('health')\n", encoding="utf-8")

    runner = FakeRunner(
        OpenHandsOutcome(
            events=[
                {"kind": "message", "content": "I will add a health route."},
                {"kind": "tool_call", "name": "str_replace"},
                {"kind": "command", "cmd": "ls"},
            ],
            logs="openhands running",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
        mutate=mutate,
    )
    sandbox = FakeSandbox(workspace)
    adapter = OpenHandsAdapter(runner=runner, repo_root=tmp_path)
    result = adapter.execute(_request(str(task_dir)), sandbox)

    assert result.status == "success"
    assert result.error_details is None
    assert result.patch is not None and "print('health')" in result.patch
    assert sandbox.mount_calls == 1
    assert runner.calls[0]["model"].inference_id == "google/gemma-3-12b-it"
    assert "Add GET /health" in runner.calls[0]["instruction"]
    assert 'Return {"status":"ok"}.' in runner.calls[0]["instruction"]
    kinds = [event.kind for event in result.trajectory]
    assert "message" in kinds
    assert "tool_call" in kinds
    assert "command" in kinds
    assert "file_change" in kinds
    assert "task_id=health-api" in result.execution_logs
    assert "model_id=google/gemma-3-12b-it" in result.execution_logs
    assert "attempt_id=1" in result.execution_logs
    assert runner.calls[0]["timeout_seconds"] == 120.0
    assert result.resource_usage is not None
    assert result.resource_usage.total_tokens == 30


def test_execute_returns_error_without_raising(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text(
        'task_id = "health-api"\ndescription = "do the task"\n',
        encoding="utf-8",
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    runner = FakeRunner(OpenHandsOutcome(error="model unavailable", logs="boom"))
    adapter = OpenHandsAdapter(runner=runner, repo_root=tmp_path)
    result = adapter.execute(_request(str(task_dir)), FakeSandbox(workspace))
    assert result.status == "error"
    assert result.error_details == "model unavailable"


def test_execute_timeout_status(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text(
        'task_id = "health-api"\ndescription = "do the task"\n',
        encoding="utf-8",
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    runner = FakeRunner(
        OpenHandsOutcome(timed_out=True, error="OpenHands timed out after 120.0s", logs="")
    )
    adapter = OpenHandsAdapter(runner=runner, repo_root=tmp_path)
    result = adapter.execute(_request(str(task_dir)), FakeSandbox(workspace))
    assert result.status == "timeout"
    assert result.error_details is not None


def test_litellm_model_prefixes_repo_ids() -> None:
    from src.arms.adapters.agents.openhands_adapter import _litellm_model

    assert _litellm_model("google/gemma-3-12b-it") == "litellm_proxy/google/gemma-3-12b-it"
    assert (
        _litellm_model("litellm_proxy/google/gemma-3-12b-it")
        == "litellm_proxy/google/gemma-3-12b-it"
    )


def test_execute_passes_laguna_runtime_env(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text(
        'task_id = "health-api"\ndescription = "do the task"\n',
        encoding="utf-8",
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    runner = FakeRunner(OpenHandsOutcome())
    settings = AppSettings.model_validate(
        {
            "LAGUNA_API_KEY": "laguna-secret",
            "LAGUNA_API_ENDPOINT": "http://127.0.0.1:4000",
            "LAGUNA_PROXY_URL": "http://127.0.0.1:3128",
        }
    )
    adapter = OpenHandsAdapter(runner=runner, settings=settings, repo_root=tmp_path)
    adapter.execute(_request(str(task_dir)), FakeSandbox(workspace))
    call = runner.calls[0]
    assert call["api_key"] == "laguna-secret"
    assert call["model_prefix"] == "litellm_proxy"
    assert call["extra_env"]["LLM_BASE_URL"] == "http://127.0.0.1:4000"
    assert call["extra_env"]["HTTPS_PROXY"] == "http://127.0.0.1:3128"
    assert call["extra_env"]["NO_PROXY"] == ""


def test_runner_reports_missing_headless_cli(monkeypatch, tmp_path: Path) -> None:
    from src.arms.adapters.agents.openhands_adapter import SubprocessOpenHandsRunner

    monkeypatch.delenv("OPENHANDS_BIN", raising=False)
    monkeypatch.setattr("src.arms.adapters.agents.openhands_adapter.shutil.which", lambda name: None)
    runner = SubprocessOpenHandsRunner(binary="openhands-missing-for-test")
    outcome = runner.run(
        model=ModelSpec(id="model1", laguna_id="google/gemma-3-12b-it"),
        workspace=tmp_path,
        instruction="do the task",
        timeout_seconds=5.0,
        api_key="x",
    )
    assert outcome.error is not None
    assert "headless CLI not found" in outcome.error
