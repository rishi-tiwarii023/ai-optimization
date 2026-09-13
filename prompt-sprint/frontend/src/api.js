function formatDetail(detail) {
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item.msg || JSON.stringify(item))
      .join("; ");
  }
  return JSON.stringify(detail);
}

export async function api(path, options = {}) {
  const { body, headers, ...rest } = options;
  const res = await fetch(`/api${path}`, {
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...rest,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(formatDetail(err.detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function streamPost(path, body, onLine) {
  const res = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(formatDetail(err.detail));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let exitCode = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";
    for (const chunk of chunks) {
      const dataLine = chunk.split("\n").find((line) => line.startsWith("data: "));
      if (!dataLine) continue;
      const data = JSON.parse(dataLine.slice(6));
      if (data.error) throw new Error(data.error);
      if (data.line !== undefined) onLine(data.line);
      if (data.done) exitCode = data.exit_code;
    }
  }
  return exitCode;
}
