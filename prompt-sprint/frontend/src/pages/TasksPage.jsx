import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

function nextTaskId(tasks) {
  const used = new Set(tasks.map((task) => task.task_id));
  let index = tasks.length + 1;
  while (used.has(`task_${String(index).padStart(3, "0")}`)) {
    index += 1;
  }
  return `task_${String(index).padStart(3, "0")}`;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [lockedIds, setLockedIds] = useState(new Set());
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const payload = await api("/tasks");
      setTasks(payload);
      setLockedIds(new Set(payload.map((task) => task.task_id)));
      setSelected(new Set());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const allSelected = useMemo(
    () => tasks.length > 0 && selected.size === tasks.length,
    [tasks, selected]
  );

  function updateTask(index, key, value) {
    setTasks((prev) =>
      prev.map((task, current) =>
        current === index ? { ...task, [key]: value } : task
      )
    );
  }

  function addTask() {
    const task_id = nextTaskId(tasks);
    setTasks((prev) => [...prev, { task_id, prompt: "" }]);
  }

  function deleteTask(index) {
    const task = tasks[index];
    setTasks((prev) => prev.filter((_, current) => current !== index));
    setSelected((prev) => {
      const next = new Set(prev);
      next.delete(task.task_id);
      return next;
    });
  }

  function deleteSelected() {
    setTasks((prev) => prev.filter((task) => !selected.has(task.task_id)));
    setSelected(new Set());
  }

  function toggleSelected(taskId) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  function toggleAll() {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(tasks.map((task) => task.task_id)));
  }

  async function save() {
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const payload = await api("/tasks", { method: "PUT", body: tasks });
      setTasks(payload);
      setLockedIds(new Set(payload.map((task) => task.task_id)));
      setSelected(new Set());
      setNotice("Tasks saved.");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-zinc-500">Loading tasks...</p>;
  }

  return (
    <div>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">Tasks</h1>
          <p className="text-sm text-zinc-500">
            Edit prompts in tasks.json. Task ids lock after the first save.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="btn"
            onClick={deleteSelected}
            disabled={selected.size === 0}
          >
            Delete selected
          </button>
          <button type="button" className="btn" onClick={addTask}>
            Add task
          </button>
          <button type="button" className="btn-primary" onClick={save} disabled={saving}>
            {saving ? "Saving..." : "Save all"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mb-4 border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="mb-4 border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm text-zinc-700">
          {notice}
        </div>
      ) : null}

      <div className="panel overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-200 bg-zinc-50 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
              <th className="w-10 px-3 py-2">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  aria-label="Select all"
                />
              </th>
              <th className="w-44 px-3 py-2">task_id</th>
              <th className="px-3 py-2">prompt</th>
              <th className="w-20 px-3 py-2">actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task, index) => {
              const locked = lockedIds.has(task.task_id);
              return (
                <tr key={`${task.task_id}-${index}`} className="border-b border-zinc-200 align-top">
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={selected.has(task.task_id)}
                      onChange={() => toggleSelected(task.task_id)}
                      aria-label={`Select ${task.task_id}`}
                    />
                  </td>
                  <td className="px-3 py-2">
                    <input
                      className="input font-mono text-xs"
                      value={task.task_id}
                      disabled={locked}
                      onChange={(event) =>
                        updateTask(index, "task_id", event.target.value)
                      }
                    />
                  </td>
                  <td className="px-3 py-2">
                    <textarea
                      className="input min-h-[4.5rem] resize-y"
                      value={task.prompt}
                      onChange={(event) =>
                        updateTask(index, "prompt", event.target.value)
                      }
                    />
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="text-sm text-zinc-600 hover:text-zinc-900"
                      onClick={() => deleteTask(index)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
            {tasks.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-8 text-center text-sm text-zinc-500">
                  No tasks. Add a task to get started.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
