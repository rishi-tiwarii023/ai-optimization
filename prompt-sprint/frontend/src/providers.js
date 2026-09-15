export function withPrefix(model, prefix) {
  const value = (model || "").trim();
  if (!value) return "";
  if (!prefix || value.startsWith(prefix)) return value;
  return `${prefix}${value}`;
}

export function knownPrefixes(providers) {
  return [...new Set((providers || []).map((item) => item.prefix).filter(Boolean))];
}

export function normalizeModelId(model, prefix, prefixes) {
  const value = (model || "").trim();
  if (!value) return "";
  if (prefix && value.startsWith(prefix)) return value;
  if ((prefixes || []).some((item) => item && item !== prefix && value.startsWith(item))) {
    return "";
  }
  return withPrefix(value, prefix);
}

export function resolveProvider(name, providers) {
  const trimmed = (name || "").trim();
  if (!trimmed) return null;
  const known = (providers || []).find((item) => item.name === trimmed);
  if (known) return known;
  const envName = trimmed.toUpperCase().replace(/-/g, "_");
  return {
    name: trimmed,
    prefix: `${trimmed}/`,
    key_env: `${envName}_API_KEY`,
    base_env: `${envName}_API_BASE`,
    base_optional: true,
    custom: true,
    api_key_set: false,
    api_base: "",
  };
}
