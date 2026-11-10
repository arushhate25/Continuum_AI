import type {
  AuditEntry,
  ClaimDetail,
  ClaimView,
  Handover,
  Metrics,
  Role,
  Source,
  StatusInfo,
} from "./types";

// NEXT_PUBLIC_* values are baked in at build time: redeploy after changing it.
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, role: Role, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Role": role, ...(init.headers || {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server. It may still be waking up; try again in a moment.");
  }
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
      else if (body && body.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  status: (role: Role) => request<StatusInfo>("/status", role),
  loadDemo: (role: Role) => request<StatusInfo>("/demo/load", role, { method: "POST" }),
  extract: (role: Role, provider?: string) =>
    request<StatusInfo>(`/extract${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`, role, {
      method: "POST",
    }),
  sources: (role: Role) => request<Source[]>("/sources", role),
  claims: (role: Role) => request<ClaimView[]>("/claims", role),
  claim: (role: Role, id: string) => request<ClaimDetail>(`/claims/${encodeURIComponent(id)}`, role),
  review: (role: Role, id: string, action: "approve" | "reject" | "edit", statement?: string) =>
    request<ClaimView>(`/claims/${encodeURIComponent(id)}/review`, role, {
      method: "POST",
      body: JSON.stringify({ action, statement }),
    }),
  handover: (role: Role) => request<Handover>("/handover", role),
  audit: (role: Role) => request<AuditEntry[]>("/audit", role),
  metrics: (role: Role) => request<Metrics>("/metrics", role),
};

/** Free hosting sleeps after inactivity. Poll /health until it answers.
 *  `onSlow` fires if the first attempt takes more than ~3s. */
export async function waitForBackend(onSlow: () => void, maxMs = 120_000): Promise<boolean> {
  const started = Date.now();
  const slowTimer = setTimeout(onSlow, 3000);
  try {
    while (Date.now() - started < maxMs) {
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 8000);
        const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal });
        clearTimeout(t);
        if (res.ok) return true;
      } catch {
        /* not up yet */
      }
      await new Promise((r) => setTimeout(r, 3000));
    }
    return false;
  } finally {
    clearTimeout(slowTimer);
  }
}

export function errorMessage(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}
