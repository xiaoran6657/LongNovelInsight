const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

export async function apiRequest<T>(
  path: string,
  options: {
    method?: string;
    json?: unknown;
    formData?: FormData;
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
    throw new ApiError(0, `Network error: ${e instanceof Error ? e.message : String(e)}`);
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // use status text as fallback
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}
