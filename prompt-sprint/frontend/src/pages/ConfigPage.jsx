import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import FieldRow from "../components/FieldRow.jsx";
import Toggle from "../components/Toggle.jsx";

const emptyForm = {
  provider: "openrouter",
  model: "",
  available_models: [],
  temperature: 0,
  max_tokens: 32768,
  timeout_seconds: 300,
  continue_on_error: true,
  overwrite_existing: false,
  scoring: false,
  judge_model: "",
  extra_params: "{}",
  api_key: "",
  api_base: "",
};

export default function ConfigPage() {
  const [providers, setProviders] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [useDefaultTokens, setUseDefaultTokens] = useState(false);
  const [modelDraft, setModelDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selected = useMemo(
    () => providers.find((item) => item.name === form.provider) || null,
    [providers, form.provider]
  );

  function setField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [config, providerList] = await Promise.all([
        api("/config"),
        api("/providers"),
      ]);
      setProviders(providerList);
      const active =
        providerList.find((item) => item.name === config.provider) ||
        providerList[0];
      setForm({
        provider: config.provider,
        model: config.model || "",
        available_models: Array.isArray(config.available_models)
          ? config.available_models
          : [],
        temperature: config.temperature ?? 0,
        max_tokens: config.max_tokens ?? 32768,
        timeout_seconds: config.timeout_seconds ?? 300,
        continue_on_error: Boolean(config.continue_on_error),
        overwrite_existing: Boolean(config.overwrite_existing),
        scoring: Boolean(config.scoring),
        judge_model: config.judge_model || "",
        extra_params: JSON.stringify(config.extra_params || {}, null, 2),
        api_key: "",
        api_base: active?.api_base || "",
      });
      setUseDefaultTokens(config.max_tokens == null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function onProviderChange(name) {
    const next = providers.find((item) => item.name === name);
    setForm((prev) => ({
      ...prev,
      provider: name,
      api_key: "",
      api_base: next?.api_base || "",
    }));
  }

  function addModel(value) {
    const model = (value || modelDraft).trim();
    if (!model) return;
    setForm((prev) => {
      if (prev.available_models.includes(model)) return prev;
      return { ...prev, available_models: [...prev.available_models, model] };
    });
    setModelDraft("");
  }

  function removeModel(model) {
    setForm((prev) => ({
      ...prev,
      available_models: prev.available_models.filter((item) => item !== model),
    }));
  }

  async function save(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setNotice("");
    let extraParams = {};
    try {
      extraParams = form.extra_params.trim()
        ? JSON.parse(form.extra_params)
        : {};
      if (
        extraParams === null ||
        typeof extraParams !== "object" ||
        Array.isArray(extraParams)
      ) {
        throw new Error("Extra params must be a JSON object.");
      }
    } catch (err) {
      setSaving(false);
      setError(err.message.includes("JSON") ? err.message : "Extra params must be valid JSON.");
      return;
    }

    const body = {
      provider: form.provider,
      model: form.model.trim(),
      available_models: form.available_models,
      temperature: Number(form.temperature),
      max_tokens: useDefaultTokens ? null : Number(form.max_tokens),
      timeout_seconds: Number(form.timeout_seconds),
      continue_on_error: form.continue_on_error,
      overwrite_existing: form.overwrite_existing,
      scoring: form.scoring,
      extra_params: extraParams,
    };
    if (form.judge_model.trim()) body.judge_model = form.judge_model.trim();
    if (form.api_key.trim()) body.api_key = form.api_key.trim();
    if (selected?.base_env) body.api_base = form.api_base.trim();

    try {
      await api("/config", { method: "PUT", body });
      setNotice("Configuration saved.");
      setForm((prev) => ({ ...prev, api_key: "" }));
      const providerList = await api("/providers");
      setProviders(providerList);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-zinc-500">Loading configuration...</p>;
  }

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-lg font-semibold text-zinc-900">Configuration</h1>
        <p className="text-sm text-zinc-500">
          Provider, model, credentials, and run flags. Values write to config.json
          and .env.
        </p>
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

      <form onSubmit={save} className="panel px-4">
        <FieldRow label="Provider" hint="LiteLLM provider id">
          <select
            className="input max-w-sm"
            value={form.provider}
            onChange={(event) => onProviderChange(event.target.value)}
          >
            {providers.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name}
              </option>
            ))}
          </select>
        </FieldRow>

        <FieldRow label="Model" hint={selected ? `Prefix ${selected.prefix}` : ""}>
          <input
            className="input"
            value={form.model}
            onChange={(event) => setField("model", event.target.value)}
            required
          />
        </FieldRow>

        <FieldRow
          label="Available models"
          hint="Active model must be in this list. Enter to add."
        >
          <div className="flex flex-wrap gap-1.5">
            {form.available_models.map((model) => (
              <span
                key={model}
                className="inline-flex items-center gap-1 border border-zinc-300 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-800"
              >
                {model}
                <button
                  type="button"
                  className="text-zinc-500 hover:text-zinc-900"
                  onClick={() => removeModel(model)}
                  aria-label={`Remove ${model}`}
                >
                  x
                </button>
              </span>
            ))}
          </div>
          <input
            className="input mt-2"
            placeholder="Add model id"
            value={modelDraft}
            onChange={(event) => setModelDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                addModel();
              }
            }}
          />
        </FieldRow>

        <FieldRow
          label="API key"
          hint={
            selected?.api_key_set
              ? `${selected.key_env} is set. Leave blank to keep it.`
              : `${selected?.key_env || "API key"} is not set.`
          }
        >
          <input
            className="input max-w-lg"
            type="password"
            autoComplete="new-password"
            value={form.api_key}
            onChange={(event) => setField("api_key", event.target.value)}
            placeholder={selected?.api_key_set ? "••••••••" : "Enter API key"}
          />
        </FieldRow>

        {selected?.base_env ? (
          <FieldRow label="Base API URL" hint={selected.base_env}>
            <input
              className="input"
              value={form.api_base}
              onChange={(event) => setField("api_base", event.target.value)}
            />
          </FieldRow>
        ) : null}

        <FieldRow label="Temperature" hint="0.0 – 2.0">
          <input
            className="input max-w-[8rem]"
            type="number"
            min="0"
            max="2"
            step="0.1"
            value={form.temperature}
            onChange={(event) => setField("temperature", event.target.value)}
            required
          />
        </FieldRow>

        <FieldRow label="Max tokens">
          <div className="flex flex-col gap-2">
            <Toggle
              checked={useDefaultTokens}
              onChange={setUseDefaultTokens}
              label="Use provider default"
            />
            <input
              className="input max-w-[10rem]"
              type="number"
              min="1"
              step="1"
              disabled={useDefaultTokens}
              value={form.max_tokens}
              onChange={(event) => setField("max_tokens", event.target.value)}
            />
          </div>
        </FieldRow>

        <FieldRow label="Timeout (s)">
          <input
            className="input max-w-[8rem]"
            type="number"
            min="1"
            step="1"
            value={form.timeout_seconds}
            onChange={(event) => setField("timeout_seconds", event.target.value)}
            required
          />
        </FieldRow>

        <FieldRow label="Scoring">
          <div className="flex flex-col gap-2">
            <Toggle
              checked={form.scoring}
              onChange={(value) => setField("scoring", value)}
              label="Score successful responses"
            />
            {form.scoring ? (
              <input
                className="input"
                placeholder="Judge model (optional, same prefix)"
                value={form.judge_model}
                onChange={(event) => setField("judge_model", event.target.value)}
              />
            ) : null}
          </div>
        </FieldRow>

        <FieldRow label="Run flags">
          <div className="flex flex-col gap-2">
            <Toggle
              checked={form.continue_on_error}
              onChange={(value) => setField("continue_on_error", value)}
              label="Continue on error"
            />
            <Toggle
              checked={form.overwrite_existing}
              onChange={(value) => setField("overwrite_existing", value)}
              label="Overwrite existing results"
            />
          </div>
        </FieldRow>

        <FieldRow label="Extra params" hint="JSON object passed to litellm.completion()">
          <textarea
            className="input min-h-[7rem] font-mono text-xs"
            value={form.extra_params}
            onChange={(event) => setField("extra_params", event.target.value)}
            spellCheck={false}
          />
        </FieldRow>

        <div className="flex justify-end py-4">
          <button className="btn-primary" type="submit" disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
