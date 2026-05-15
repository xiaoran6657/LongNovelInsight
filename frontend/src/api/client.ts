const _rawBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const BASE_URL = _rawBaseUrl.replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

function _extractDetail(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const d = (body as Record<string, unknown>).detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(String).join("; ");
  if (d && typeof d === "object") {
    const msg = (d as Record<string, unknown>).message ?? (d as Record<string, unknown>).msg;
    return typeof msg === "string" ? msg : JSON.stringify(d);
  }
  return "";
}

export async function apiRequest<T>(
  path: string,
  options: {
    method?: string;
    json?: unknown;
    formData?: FormData;
    signal?: AbortSignal;
  } = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {};

  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const init: RequestInit = {
    method: options.method || "GET",
    headers,
    signal: options.signal,
  };

  if (options.json !== undefined) {
    init.body = JSON.stringify(options.json);
  } else if (options.formData !== undefined) {
    init.body = options.formData;
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(0, "Request aborted");
    }
    throw new ApiError(0, `Network error: ${e instanceof Error ? e.message : String(e)}`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      const extracted = _extractDetail(body);
      if (extracted) detail = extracted;
    } catch {
      // use status text as fallback
    }
    throw new ApiError(response.status, detail);
  }

  // Handle 204 No Content or empty body
  const contentLength = response.headers.get("content-length");
  if (response.status === 204 || contentLength === "0") {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) return undefined as T;

  return JSON.parse(text) as T;
}
