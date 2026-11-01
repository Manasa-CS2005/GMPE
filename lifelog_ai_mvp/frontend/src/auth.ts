export type AccountUser = {
  id: number;
  full_name: string;
  email: string;
  email_verified: boolean;
  created_at: string;
};

export type AccountProfile = {
  full_name: string;
  email: string;
  email_verified: boolean;
  has_profile_image: boolean;
  preferred_language: string;
  timezone: string;
  writing_style: string;
  journal_tone: string;
  interests: string;
  goals: string;
  reminder_time: string;
  email_notifications: boolean;
  in_app_notifications: boolean;
};

export type ApiMemory = {
  id: number;
  title: string;
  source_text: string;
  mode: string;
  tags: string;
  mood: string;
  memory_date: string;
  result: Record<string, unknown>;
  created_at: string;
};

export type ApiTask = {
  id: number;
  memory_id: number | null;
  title: string;
  description: string;
  due_date: string | null;
  due_time: string | null;
  priority: "low" | "normal" | "high";
  completed: boolean;
  reminder_enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type ApiMood = {
  id: number;
  mood: "Sunny" | "Soft" | "Focused" | "Cloudy" | "Restless";
  checkin_date: string;
  created_at: string;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function csrfCookie() {
  const csrf = document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("lifelog_csrf="))
    ?.slice("lifelog_csrf=".length);
  return csrf ? decodeURIComponent(csrf) : "";
}

async function ensureCsrf() {
  let token = csrfCookie();
  if (!token) {
    const response = await fetch("/api/auth/csrf", { credentials: "same-origin" });
    if (!response.ok) throw new ApiError(response.status, "Could not initialize a secure request.");
    token = csrfCookie();
  }
  if (!token) throw new ApiError(403, "Could not initialize a secure request.");
  return token;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    headers.set("X-CSRF-Token", await ensureCsrf());
  }
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
  });
  const data = await response.json().catch(() => ({})) as {
    detail?: unknown;
    message?: string;
  };
  if (!response.ok) {
    const detail = typeof data.detail === "string"
      ? data.detail
      : Array.isArray(data.detail)
        ? data.detail.map((item) => typeof item === "object" && item !== null && "msg" in item
          ? String(item.msg)
          : "Invalid request").join(" ")
        : data.message;
    throw new ApiError(response.status, detail ?? "Request failed.");
  }
  return data as T;
}
