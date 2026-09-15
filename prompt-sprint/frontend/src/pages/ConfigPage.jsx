import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import FieldRow from "../components/FieldRow.jsx";
import ProviderInput from "../components/ProviderInput.jsx";
import Toggle from "../components/Toggle.jsx";
import {
  knownPrefixes,
  normalizeModelId,
  resolveProvider,
} from "../providers.js";

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
    () => resolveProvider(form.provider, providers),
    [providers, form.provider]
  );
  const prefixes = useMemo(() => knownPrefixes(providers), [providers]);
  const prefix = selected?.prefix || "";

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
      const active = resolveProvider(config.provider, providerList);
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

  function applyProvider(name) {
    const trimmed = (name || "").trim();
    const next = resolveProvider(trimmed, providers);
    const nextPrefix = next?.prefix || "";
    setForm((prev) => {
      const providerChanged = Boolean(trimmed) && trimmed !== prev.provider;
      const nextModels = [];
      for (const item of prev.available_models) {
        const normalized = normalizeModelId(item, nextPrefix, prefixes);
        if (normalized && !nextModels.includes(normalized)) {
          nextModels.push(normalized);
        }
      }
      return {
        ...prev,
        provider: trimmed || prev.provider,
        api_key: providerChanged ? "" : prev.api_key,
        api_base: providerChanged
          ? next?.api_base || ""
          : prev.api_base || next?.api_base || "",
        model: normalizeModelId(prev.model, nextPrefix, prefixes) || nextPrefix,
        available_models: nextModels,
        judge_model: normalizeModelId(prev.judge_model, nextPrefix, prefixes),
      };
    });
  }

  function onProviderChange(name) {
    const known = providers.some((item) => item.name === name);
    if (known) {
      applyProvider(name);
      return;
    }
    const next = resolveProvider(name, providers);
    setForm((prev) => ({
      ...prev,
      provider: name,
      api_key: "",
      api_base: next?.api_base || "",
    }));
  }

  function addModel(value) {
    const model = normalizeModelId(value || modelDraft, prefix, prefixes);
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

    const providerName = form.provider.trim();
    const resolved = resolveProvider(providerName, providers);
    const nextPrefix = resolved?.prefix || "";
    const model = normalizeModelId(form.model, nextPrefix, prefixes);
    const available_models = [];
    for (const item of form.available_models) {
      const normalized = normalizeModelId(item, nextPrefix, prefixes);
      if (normalized && !available_models.includes(normalized)) {
        available_models.push(normalized);
      }
    }
    if (model && !available_models.includes(model)) {
      available_models.push(model);
    }
    const judgeModel = normalizeModelId(form.judge_model, nextPrefix, prefixes);

    const body = {
      provider: providerName,
      model,
      available_models,
      temperature: Number(form.temperature),
      max_tokens: useDefaultTokens ? null : Number(form.max_tokens),
      timeout_seconds: Number(form.timeout_seconds),
      continue_on_error: form.continue_on_error,
      overwrite_existing: form.overwrite_existing,
      scoring: form.scoring,
      extra_params: extraParams,
    };
    if (judgeModel) body.judge_model = judgeModel;
    if (form.api_key.trim()) body.api_key = form.api_key.trim();
    if (resolved?.base_env) body.api_base = form.api_base.trim();

    try {
      await api("/config", { method: "PUT", body });
      setNotice("Configuration saved.");
      setForm((prev) => ({
        ...prev,
        provider: providerName,
        model,
        available_models,
        judge_model: judgeModel,
        api_key: "",
      }));
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
        <FieldRow
          label="Provider"
          hint={
            selected?.custom
              ? `Custom LiteLLM id. Models use ${selected.prefix}`
              : "Pick a built-in provider or type any LiteLLM id"
          }
        >
          <ProviderInput
            value={form.provider}
            onChange={onProviderChange}
            onBlur={() => applyProvider(form.provider)}
            providers={providers}
            placeholder="openrouter, gemini, groq, ..."
          />
        </FieldRow>

        <FieldRow
          label="Model"
          hint={prefix ? `Prefix ${prefix} is added if missing` : ""}
        >
          <input
            className="input"
            value={form.model}
            onChange={(event) => setField("model", event.target.value)}
            onBlur={() => {
              const next = normalizeModelId(form.model, prefix, prefixes);
              if (next) setField("model", next);
            }}
            placeholder={prefix ? `${prefix}<model-id>` : "model id"}
            required
          />
        </FieldRow>

        <FieldRow
          label="Available models"
          hint="Type a model id and press Enter. Prefix is added automatically."
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
            placeholder={prefix ? `Add ${prefix}<model-id>` : "Add model id"}
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
          <FieldRow
            label="Base API URL"
            hint={
              selected.base_optional
                ? `${selected.base_env} (optional for this provider)`
                : selected.base_env
            }
          >
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
                placeholder={
                  prefix
                    ? `Judge model (optional, ${prefix})`
                    : "Judge model (optional, same prefix)"
                }
                value={form.judge_model}
                onChange={(event) => setField("judge_model", event.target.value)}
                onBlur={() => {
                  const next = normalizeModelId(form.judge_model, prefix, prefixes);
                  setField("judge_model", next);
                }}
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
