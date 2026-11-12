const TOKEN_KEY = "innonest.token";

export class ApiError extends Error {
  status: number;
  code: string;
  details: { field: string; message: string }[] | null;
  constructor(status: number, code: string, message: string, details: { field: string; message: string }[] | null) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokenStore = {
  get: () => {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (token: string) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      return;
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      return;
    }
  },
};

type Options = { method?: string; body?: unknown; form?: FormData; params?: Record<string, string | number | boolean | undefined | null> };

function buildUrl(path: string, params?: Options["params"]) {
  const query = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  });
  const suffix = query.toString();
  return `/api/v1${path}${suffix ? `?${suffix}` : ""}`;
}

async function send(path: string, options: Options = {}): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  const response = await fetch(buildUrl(path, options.params), { method: options.method ?? (body ? "POST" : "GET"), headers, body });
  if (!response.ok) {
    let payload: { error?: { code: string; message: string; details: ApiError["details"] } } = {};
    try {
      payload = await response.json();
    } catch {
      payload = {};
    }
    const error = payload.error;
    if (response.status === 401 && tokenStore.get()) {
      tokenStore.clear();
      window.dispatchEvent(new Event("innonest:signed-out"));
    }
    throw new ApiError(response.status, error?.code ?? "error", error?.message ?? "Something went wrong", error?.details ?? null);
  }
  return response;
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const response = await send(path, options);
  return (await response.json()) as T;
}

export async function download(path: string, filename: string, params?: Options["params"]) {
  const response = await send(path, { params });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function openFile(path: string) {
  const response = await send(path);
  const blob = await response.blob();
  window.open(URL.createObjectURL(blob), "_blank", "noopener");
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details?.length) return `${error.message}: ${error.details.map((d) => d.message).join("; ")}`;
    return error.message;
  }
  return error instanceof Error ? error.message : "Something went wrong";
}
