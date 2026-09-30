export async function request(path, method = "GET", payload, signal) {
  const response = await fetch(`/api${path}`, {
    method,
    signal,
    headers:
      payload === undefined
        ? undefined
        : { "Content-Type": "application/json" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join(". ")
          : "The service is unavailable. Check the backend connection and try again.",
    );
  }
  return data;
}
