// Thin wrappers around the explorer's JSON API (interactive/server/app.py).

async function request(path, options) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

export const getDatasets = () => request("/api/datasets");
export const getPoints = (dataset) => request(`/api/points?dataset=${encodeURIComponent(dataset)}`);

const post = (path, body) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const cluster = (body) => post("/api/cluster", body);
export const why = (body) => post("/api/why", body);
export const explain = (body) => post("/api/explain", body);
export const verify = (body) => post("/api/verify", body);
