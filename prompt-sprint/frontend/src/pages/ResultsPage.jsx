import { useEffect, useRef, useState } from "react";
import { api, streamPost } from "../api.js";
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
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const logRef = useRef(null);

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

  useEffect(() => {
    api("/providers")
      .then(setProviders)
      .catch((err) => setError(err.message));
    loadResults();
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
      await loadResults();
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
            <select
              className="input"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              <option value="">Use config</option>
              {providers.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name}
                </option>
              ))}
            </select>
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
              <Tile
                label="median range"
                value={
                  Array.isArray(scoreStats.median_range)
                    ? `${scoreStats.median_range[0]} – ${scoreStats.median_range[1]}`
                    : null
                }
              />
            </div>
          ) : null}
          {(() => {
            const scored = results.filter((r) => r.score != null);
            if (scored.length === 0) return null;
            const buckets = [
              { label: "0–2", min: 0, max: 2 },
              { label: "2–4", min: 2, max: 4 },
              { label: "4–6", min: 4, max: 6 },
              { label: "6–8", min: 6, max: 8 },
              { label: "8–10", min: 8, max: 10.001 },
            ];
            const counts = buckets.map((b) =>
              scored.filter((r) => r.score >= b.min && r.score < b.max).length,
            );
            const maxCount = Math.max(...counts, 1);
            return (
              <div className="mt-3">
                <div className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Score distribution
                </div>
                <div className="flex items-end gap-1">
                  {buckets.map((b, i) => (
                    <div key={b.label} className="flex flex-1 flex-col items-center gap-1">
                      <span className="text-xs text-zinc-500">{counts[i]}</span>
                      <div className="w-full bg-zinc-100" style={{ height: 56 }}>
                        <div
                          className={`w-full transition-all ${i >= 3 ? "bg-green-500" : i === 2 ? "bg-zinc-400" : "bg-amber-500"}`}
                          style={{
                            height: `${(counts[i] / maxCount) * 100}%`,
                            marginTop: `${((maxCount - counts[i]) / maxCount) * 100}%`,
                          }}
                        />
                      </div>
                      <span className="text-[10px] text-zinc-400">{b.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}
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
