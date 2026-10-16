import { useEffect, useRef, useState } from "react";
import { api, streamPost } from "../api.js";
import ProviderInput from "../components/ProviderInput.jsx";
import Toggle from "../components/Toggle.jsx";

function formatMs(value) {
  if (value == null) return "—";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

function scoreColor(score) {
  if (score == null) return "";
  if (score >= 8) return "text-green-700";
  if (score >= 5) return "text-zinc-700";
  return "text-amber-700";
}

function scoreBgColor(score) {
  if (score == null) return "bg-zinc-200";
  if (score >= 8) return "bg-green-500";
  if (score >= 5) return "bg-zinc-400";
  return "bg-amber-500";
}

function Tile({ label, value }) {
  return (
    <div className="border border-zinc-200 bg-zinc-50 px-3 py-2">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 break-all font-mono text-sm text-zinc-900">{value ?? "—"}</div>
    </div>
  );
}

function formatCapturedIst(run) {
  if (!run) return "—";
  if (run.captured_at_ist) return run.captured_at_ist;
  const raw = run.captured_at || run.started_at;
  if (!raw) return "—";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  const parts = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const pick = (type) => parts.find((p) => p.type === type)?.value ?? "";
  return `${pick("year")}-${pick("month")}-${pick("day")} ${pick("hour")}:${pick("minute")}:${pick("second")} IST`;
}

function formatStat(value) {
  if (value == null) return "—";
  return String(value);
}

function scoreBucketColor(index) {
  if (index >= 3) return "bg-green-500";
  if (index === 2) return "bg-zinc-400";
  return "bg-amber-500";
}

const SCORE_BUCKETS = [
  { label: "0–2", min: 0, max: 2 },
  { label: "2–4", min: 2, max: 4 },
  { label: "4–6", min: 4, max: 6 },
  { label: "6–8", min: 6, max: 8 },
  { label: "8–10", min: 8, max: 10.001 },
];

function ScoreDistributionChart({ results }) {
  const scored = results.filter((r) => r.score != null);
  if (scored.length === 0) return null;

  const counts = SCORE_BUCKETS.map((bucket) =>
    scored.filter((r) => r.score >= bucket.min && r.score < bucket.max).length,
  );
  const maxCount = Math.max(...counts, 1);
  const chartHeight = 96;

  return (
    <div className="mt-4 border border-zinc-200 bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          Score distribution
        </div>
        <div className="text-xs text-zinc-500">{scored.length} scored task(s)</div>
      </div>
      <div className="grid grid-cols-5 gap-2 sm:gap-4">
        {SCORE_BUCKETS.map((bucket, index) => {
          const count = counts[index];
          const barHeight =
            count === 0 ? 0 : Math.max(4, Math.round((count / maxCount) * chartHeight));
          return (
            <div key={bucket.label} className="flex min-w-0 flex-col items-center">
              <span className="mb-2 text-sm font-medium tabular-nums text-zinc-800">
                {count}
              </span>
              <div
                className="flex w-full items-end justify-center border-b border-zinc-200 bg-zinc-50 px-1"
                style={{ height: chartHeight }}
              >
                <div
                  className={`w-full max-w-10 rounded-t-sm ${scoreBucketColor(index)}`}
                  style={{ height: barHeight }}
                  title={`${count} task(s) in ${bucket.label}`}
                />
              </div>
              <span className="mt-2 text-center text-[11px] leading-tight text-zinc-500">
                {bucket.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RunScoreStatsTable({ runs, emptyMessage }) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
          <th className="px-3 py-2">time (IST)</th>
          <th className="px-3 py-2">model</th>
          <th className="px-3 py-2">count</th>
          <th className="px-3 py-2">mean</th>
          <th className="px-3 py-2">median</th>
          <th className="px-3 py-2">mode</th>
          <th className="px-3 py-2">max</th>
          <th className="px-3 py-2">median_range</th>
          <th className="px-3 py-2">p95</th>
          <th className="px-3 py-2">std_dev</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => {
          const stats = run.score_stats;
          return (
            <tr key={run.run_id} className="border-b border-zinc-200">
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">
                {formatCapturedIst(run)}
              </td>
              <td className="max-w-[14rem] px-3 py-2 break-all font-mono text-xs">
                {run.model ?? "—"}
              </td>
              <td className="px-3 py-2">{formatStat(stats?.count)}</td>
              <td className="px-3 py-2">{formatStat(stats?.mean)}</td>
              <td className="px-3 py-2">{formatStat(stats?.median)}</td>
              <td className="px-3 py-2">{formatStat(stats?.mode)}</td>
              <td className="px-3 py-2">{formatStat(stats?.max)}</td>
              <td className="px-3 py-2">{formatStat(stats?.median_range)}</td>
              <td className="px-3 py-2">{formatStat(stats?.p95)}</td>
              <td className="px-3 py-2">{formatStat(stats?.std_dev)}</td>
            </tr>
          );
        })}
        {runs.length === 0 ? (
          <tr>
            <td colSpan={10} className="px-3 py-8 text-center text-zinc-500">
              {emptyMessage}
            </td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}

function isRateLimitFailure(item) {
  if (!item || item.status !== "failed" || !item.error) return false;
  const type = String(item.error.type || "");
  const message = String(item.error.message || "");
  return /ratelimit/i.test(type) || /rate.?limit|\b429\b/i.test(message);
}

export default function ResultsPage() {
  const [providers, setProviders] = useState([]);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [taskId, setTaskId] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [noScoring, setNoScoring] = useState(false);
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const logRef = useRef(null);

  async function loadRuns() {
    const data = await api("/runs");
    setRuns(data.runs || []);
  }

  async function loadResults() {
    try {
      const [items, summaryPayload] = await Promise.all([
        api("/responses"),
        api("/responses/summary").catch(() => null),
      ]);
      setResults(items);
      setSummary(summaryPayload);
      setSelected((current) => {
        if (!current) return null;
        return items.find((entry) => entry.task_id === current.task_id) || current;
      });
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshData() {
    try {
      await loadResults();
      await loadRuns();
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    api("/providers")
      .then(setProviders)
      .catch((err) => setError(err.message));
    refreshData();
  }, []);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  function runBody(includeScoringFlag, extra = {}) {
    const body = { overwrite, ...extra };
    if (includeScoringFlag) body.no_scoring = noScoring;
    if (provider) body.provider = provider;
    if (model.trim()) body.model = model.trim();
    if (extra.task_id) {
      body.task_id = extra.task_id;
    } else if (taskId.trim()) {
      body.task_id = taskId.trim();
    }
    return body;
  }

  function rerunRateLimited(task) {
    startStream(
      "/run",
      runBody(true, { overwrite: true, task_id: task.task_id }),
    );
  }

  async function startStream(path, body) {
    setRunning(true);
    setError("");
    setLogs([]);
    try {
      const code = await streamPost(path, body, (line) => {
        setLogs((prev) => [...prev, line]);
      });
      setLogs((prev) => [...prev, `exit_code=${code}`]);
      await refreshData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  function formatScoreStatsLog(stats) {
    if (!stats) return null;
    return (
      "Score stats: " +
      `count=${stats.count} mean=${stats.mean} median=${stats.median} ` +
      `mode=${stats.mode} max=${stats.max} median_range=${stats.median_range} ` +
      `p95=${stats.p95} std_dev=${stats.std_dev}`
    );
  }

  async function captureStats() {
    setRunning(true);
    setError("");
    setLogs(["Refreshing score stats from saved task results…"]);
    try {
      const result = await api("/stats", { method: "POST" });
      const lines = [result.message];
      const statsLine = formatScoreStatsLog(result.score_stats);
      if (statsLine) lines.push(statsLine);
      setLogs(lines);
      await refreshData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  const scoreStats = summary?.score_stats;

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-zinc-900">Results</h1>
        <p className="text-sm text-zinc-500">
          Run tasks, score saved responses, and inspect output files.
        </p>
      </div>

      {error ? (
        <div className="mb-4 border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <section className="panel mb-4 p-4">
        <div className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Run controls
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-zinc-500">Provider override</span>
            <ProviderInput
              id="run-provider-options"
              className="input"
              value={provider}
              onChange={setProvider}
              providers={providers}
              placeholder="Use config"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-zinc-500">Model override</span>
            <input
              className="input"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              placeholder="Use config"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-zinc-500">Task ID filter</span>
            <input
              className="input"
              value={taskId}
              onChange={(event) => setTaskId(event.target.value)}
              placeholder="All tasks"
            />
          </label>
          <div className="flex flex-col justify-end gap-2">
            <Toggle checked={overwrite} onChange={setOverwrite} label="Overwrite" />
            <Toggle checked={noScoring} onChange={setNoScoring} label="No scoring" />
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            className="btn-primary"
            disabled={running}
            onClick={() => startStream("/run", runBody(true))}
          >
            {running ? "Running..." : "Run"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={running}
            onClick={() => startStream("/score", runBody(false))}
          >
            Score
          </button>
          <button
            type="button"
            className="btn"
            disabled={running}
            onClick={() => captureStats()}
          >
            Stats
          </button>
        </div>
        <div
          ref={logRef}
          className="mt-4 h-56 overflow-auto bg-zinc-900 p-3 font-mono text-xs leading-5 text-zinc-100"
        >
          {logs.length === 0 ? (
            <span className="text-zinc-500">No output yet.</span>
          ) : (
            logs.map((line, index) => <div key={`${index}-${line}`}>{line}</div>)
          )}
        </div>
      </section>

      {summary ? (
        <section className="mb-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            Summary
          </div>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Tile label="run_id" value={summary.run_id} />
            <Tile label="provider" value={summary.provider} />
            <Tile label="model" value={summary.model} />
            <Tile label="started_at" value={summary.started_at} />
            <Tile label="finished_at" value={summary.finished_at} />
            <Tile label="total" value={summary.total_tasks} />
            <Tile label="successful" value={summary.successful} />
            <Tile label="failed" value={summary.failed} />
            <Tile label="skipped" value={summary.skipped} />
            <Tile label="prompt tokens" value={summary.prompt_tokens} />
            <Tile label="completion tokens" value={summary.completion_tokens} />
            <Tile label="total tokens" value={summary.total_tokens} />
            <Tile
              label="reported cost"
              value={
                summary.reported_cost == null ? "unavailable" : summary.reported_cost
              }
            />
            <Tile label="elapsed" value={formatMs(summary.total_elapsed_ms)} />
            <Tile label="avg latency" value={formatMs(summary.average_latency_ms)} />
          </div>
          {scoreStats ? (
            <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
              <Tile label="scored tasks" value={scoreStats.count} />
              <Tile label="score mean" value={scoreStats.mean} />
              <Tile label="score median" value={scoreStats.median} />
              <Tile label="score mode" value={scoreStats.mode} />
              <Tile label="score max" value={scoreStats.max} />
              <Tile label="score p95" value={scoreStats.p95} />
              <Tile label="score std_dev" value={scoreStats.std_dev} />
              <Tile label="median range (IQR)" value={scoreStats.median_range} />
            </div>
          ) : null}
          <ScoreDistributionChart results={results} />
        </section>
      ) : (
        <p className="mb-4 text-sm text-zinc-500">No summary.json yet.</p>
      )}

      <section className="panel overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
              <th className="px-3 py-2">task_id</th>
              <th className="px-3 py-2">status</th>
              <th className="px-3 py-2">score</th>
              <th className="px-3 py-2">total_tokens</th>
              <th className="px-3 py-2">latency_ms</th>
              <th className="px-3 py-2">cost</th>
              <th className="px-3 py-2">actions</th>
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <tr
                key={item.task_id}
                role="button"
                tabIndex={0}
                className="cursor-pointer border-b border-zinc-200 hover:bg-zinc-50"
                onClick={() => setSelected(item)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelected(item);
                  }
                }}
              >
                <td className="px-3 py-2 font-mono text-xs">{item.task_id}</td>
                <td className="px-3 py-2">{item.status}</td>
                <td className="px-3 py-2">
                  {item.score == null ? (
                    "—"
                  ) : (
                    <span className={`font-semibold ${scoreColor(item.score)}`}>
                      {item.score.toFixed(1)}
                    </span>
                  )}
                </td>
                <td className="px-3 py-2">{item.metrics?.total_tokens ?? "—"}</td>
                <td className="px-3 py-2">{item.metrics?.latency_ms ?? "—"}</td>
                <td className="px-3 py-2">
                  {item.metrics?.cost == null ? "—" : item.metrics.cost}
                </td>
                <td className="px-3 py-2">
                  {isRateLimitFailure(item) ? (
                    <button
                      type="button"
                      className="btn"
                      disabled={running}
                      onClick={(event) => {
                        event.stopPropagation();
                        rerunRateLimited(item);
                      }}
                    >
                      Rerun
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
            {results.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-zinc-500">
                  No task results.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>

      <section className="panel mt-4 overflow-x-auto">
        <div className="border-b border-zinc-200 bg-zinc-50 px-3 py-3">
          <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Run stats
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            Historical score aggregates for benchmarking. Each Run, Score, or Stats action appends a
            row (time in IST, model from summary). Click Stats to snapshot current task scores
            without re-running the model.
          </p>
        </div>
        <RunScoreStatsTable
          runs={runs}
          emptyMessage="No run snapshots yet. Run tasks, score, or click Stats."
        />
      </section>

      {selected ? (
        <div className="fixed inset-0 z-20 flex">
          <button
            type="button"
            className="h-full flex-1 bg-zinc-900/30"
            aria-label="Close detail"
            onClick={() => setSelected(null)}
          />
          <aside className="h-full w-full max-w-xl overflow-y-auto border-l border-zinc-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="font-mono text-sm font-semibold">{selected.task_id}</h2>
              <div className="flex gap-2">
                {isRateLimitFailure(selected) ? (
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={running}
                    onClick={() => rerunRateLimited(selected)}
                  >
                    Rerun
                  </button>
                ) : null}
                <button type="button" className="btn" onClick={() => setSelected(null)}>
                  Close
                </button>
              </div>
            </div>
            <dl className="mb-4 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="text-xs text-zinc-500">status</dt>
                <dd>{selected.status}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">model</dt>
                <dd className="break-all font-mono text-xs">{selected.model}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-xs text-zinc-500">score</dt>
                {selected.score == null ? (
                  <dd>—</dd>
                ) : (
                  <dd>
                    <div className="mt-1 flex items-center gap-2">
                      <span className={`text-sm font-semibold ${scoreColor(selected.score)}`}>
                        {selected.score.toFixed(1)} / 10
                      </span>
                    </div>
                    <div className="mt-1 h-2 w-full rounded-full bg-zinc-100">
                      <div
                        className={`h-2 rounded-full transition-all ${scoreBgColor(selected.score)}`}
                        style={{ width: `${(selected.score / 10) * 100}%` }}
                      />
                    </div>
                  </dd>
                )}
              </div>
              <div>
                <dt className="text-xs text-zinc-500">finish_reason</dt>
                <dd>{selected.finish_reason ?? "—"}</dd>
              </div>
            </dl>
            <div className="mb-3">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">
                Prompt
              </div>
              <pre className="whitespace-pre-wrap border border-zinc-200 bg-zinc-50 p-2 text-sm">
                {selected.prompt}
              </pre>
            </div>
            <div className="mb-3">
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">
                Response
              </div>
              <pre className="whitespace-pre-wrap border border-zinc-200 bg-zinc-50 p-2 text-sm">
                {selected.response || "—"}
              </pre>
            </div>
            {selected.error ? (
              <div className="mb-3">
                <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">
                  Error
                </div>
                <pre className="whitespace-pre-wrap border border-red-200 bg-red-50 p-2 text-sm text-red-800">
                  {selected.error.type}: {selected.error.message}
                </pre>
              </div>
            ) : null}
            <div>
              <div className="mb-1 text-xs uppercase tracking-wide text-zinc-500">
                Metrics
              </div>
              {selected.metrics ? (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border border-zinc-200 bg-zinc-50 p-3 text-sm">
                  <div>
                    <dt className="text-xs text-zinc-500">prompt tokens</dt>
                    <dd className="font-mono">{selected.metrics.prompt_tokens ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">completion tokens</dt>
                    <dd className="font-mono">{selected.metrics.completion_tokens ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">total tokens</dt>
                    <dd className="font-mono">{selected.metrics.total_tokens ?? "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">latency</dt>
                    <dd className="font-mono">{formatMs(selected.metrics.latency_ms)}</dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-xs text-zinc-500">cost</dt>
                    <dd className="font-mono">
                      {selected.metrics.cost == null ? "unavailable" : selected.metrics.cost}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-zinc-500">—</p>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
