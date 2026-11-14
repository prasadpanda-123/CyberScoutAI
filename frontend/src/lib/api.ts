/**
 * CyberScout AI API Client
 * 
 * Uses same-origin HTTP requests to Flask backend.
 */

const API_BASE = "";  // Same-origin; no base URL needed.

// Core fetcher

export interface FetchOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined | null>;
}

async function redirectIfSessionExpired(path: string): Promise<void> {
  if (path === "/api/me") return;

  const redirectToLogin = () => {
    const loginPath = window.location.pathname.startsWith("/app") ? "/app/login" : "/login";
    window.location.href = loginPath + "?next=" + encodeURIComponent(window.location.pathname);
  };

  let sessionState: MeResponse;
  try {
    sessionState = await authApi.me();
  } catch (error) {
    if (error instanceof Error && error.message === "Unauthorized") {
      redirectToLogin();
    }
    return;
  }

  if (!sessionState.authenticated) redirectToLogin();
}

export async function fetchApi<T = unknown>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { params, headers, ...rest } = options;

  // Build URL with query string
  const url = new URL(API_BASE + path, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const response = await fetch(url.toString(), {
    credentials: "include",  // Always send session cookies
    headers: {
      ...(typeof rest.body === "string" ? { "Content-Type": "application/json" } : {}),
      "Accept": "application/json",
      "X-Requested-With": "XMLHttpRequest",
      ...headers,
    },
    ...rest,
  });

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.error ?? errorData.message ?? errorMessage;
    } catch {
      // Response body not JSON
    }

    if (response.status === 401) {
      await redirectIfSessionExpired(path);
      throw new Error("Unauthorized");
    }

    throw new Error(errorMessage);
  }

  // Handle empty responses
  const contentType = response.headers.get("content-type");
  if (!contentType || !contentType.includes("application/json")) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

// ─── Convenience Methods ──────────────────────────────────────────────────────

export const api = {
  get: <T>(path: string, params?: FetchOptions["params"]) =>
    fetchApi<T>(path, { method: "GET", params }),

  post: <T>(path: string, body?: unknown, params?: FetchOptions["params"]) =>
    fetchApi<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
      params,
    }),

  put: <T>(path: string, body?: unknown) =>
    fetchApi<T>(path, {
      method: "PUT",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  patch: <T>(path: string, body?: unknown) =>
    fetchApi<T>(path, {
      method: "PATCH",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),

  delete: <T>(path: string) =>
    fetchApi<T>(path, { method: "DELETE" }),
};

// ─── Auth APIs ────────────────────────────────────────────────────────────────

export interface MeResponse {
  authenticated: boolean;
  user: {
    username: string;
    email: string;
    role: string;
    is_admin?: boolean;
  } | null;
}

export const authApi = {
  me: () => api.get<MeResponse>("/api/me"),
  login: (credentials: { username: string; password: string }) =>
    api.post<{ status: string; message?: string }>("/login", credentials),
  adminLogin: (credentials: { username: string; password: string }) =>
    api.post<{ status: string; message?: string; mfa_required?: boolean }>("/admin/login", credentials),
  adminVerifyOtp: (otp: string) =>
    api.post<{ status: string; message?: string }>("/admin/verify-otp", { otp }),
  register: (data: { username: string; email: string; password: string }) =>
    api.post<{ status: string; message?: string }>("/register", data),
  logout: () => api.post<{ status: string }>("/logout"),
  forgotPassword: (email: string) =>
    api.post<{ status: string; message?: string }>("/forgot-password", { email }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post<{ status: string; message?: string }>("/profile/change-password", data),
};

// ─── Opportunity APIs ─────────────────────────────────────────────────────────

export const opportunitiesApi = {
  list: (filters?: Record<string, string | number | boolean | undefined>) =>
    api.get<{
      opportunities: any[];
      total: number;
      page: number;
      per_page: number;
      total_pages: number;
      has_next: boolean;
      has_prev: boolean;
    }>("/api/opportunities", filters),

  detail: (id: string) =>
    api.get<{ status: string; opportunity: any }>(`/api/opportunities/${id}`),

  toggleSave: (id: string) =>
    api.post<{ status: string; saved: boolean }>(`/api/opportunities/${id}/bookmark`),

  saved: () =>
    api.get<{ opportunities: any[]; total: number }>("/api/opportunities/saved"),
};

// ─── Dashboard APIs ───────────────────────────────────────────────────────────

export const dashboardApi = {
  stats: () => api.get<any>("/api/stats"),
  charts: () => api.get<any>("/api/dashboard/charts"),
  insights: () => api.get<any>("/api/insights"),
  qualityStats: () => api.get<any>("/api/quality/stats"),
};

// ─── Notification APIs ────────────────────────────────────────────────────────

export interface NotificationPreferences {
  email_notifications_enabled: boolean;
  in_app_notifications_enabled: boolean;
  notify_new_opportunities: boolean;
  delivery_mode: "immediate" | "digest" | string;
  digest_frequency: "daily" | "weekly" | string;
}

export const notificationsApi = {
  list: () => api.get<{ status: string; notifications: any[]; unread_count: number }>("/api/notifications"),
  markRead: (id: string) =>
    api.post<{ status: string; id: string }>("/notifications/mark-read", { notification_id: id }),
  markAllRead: () =>
    api.post<{ status: string; updated_count: number }>("/notifications/mark-all-read"),
  preferences: () =>
    api.get<{ status: string; preferences: NotificationPreferences }>("/notifications/preferences"),
  updatePreferences: (data: Partial<NotificationPreferences>) =>
    api.post<{ status: string; preferences: NotificationPreferences }>("/notifications/preferences", data),
};

// ─── Analytics APIs ───────────────────────────────────────────────────────────

export const analyticsApi = {
  get: () => api.get<any>("/api/analytics"),
  trends: () => api.get<any>("/api/trends"),
};

// ─── Admin APIs ───────────────────────────────────────────────────────────────

export interface AdminDashboardStats {
  total_production: number;
  total_discovered: number;
  total_extracted: number;
  total_classified: number;
  total_approved: number;
  total_quarantined: number;
  total_rejected: number;
  report_date: string;
}

export interface AdminDailyApiBudget {
  provider: string;
  operation: string;
  daily_limit: number;
  unit: string;
}

export interface AdminSourceDefinition {
  id: string;
  name: string;
  type: string;
  description?: string;
  details?: string;
  status?: string;
}

export interface AdminSourceHealthRecord {
  source_id: string;
  health_status?: string;
  items_seen?: number;
  last_attempt?: string | null;
}

export const adminApi = {
  stats: () => api.get<AdminDashboardStats>("/admin/api/stats"),
  dailyBudgets: () =>
    api.get<{
      scope: "application_config";
      usage_tracking: "not_persisted";
      daily_limits: AdminDailyApiBudget[];
    }>("/admin/api/daily-budgets"),
  system: () => api.get<any>("/admin/api/system"),
  logs: (params?: Record<string, string | number>) => api.get<any>("/admin/api/logs", params),
  auditLogs: (params?: Record<string, string | number>) => api.get<any>("/admin/api/audit-logs", params),
  collectors: () => api.get<any>("/admin/api/collectors"),
  triggerRun: () => api.post<any>("/admin/api/run"),
  triggerReport: () => api.post<any>("/admin/api/report/trigger"),
  smtpHealth: () => api.get<any>("/admin/api/system/smtp-health"),
  schedulerPause: () => api.post<any>("/admin/api/scheduler/pause"),
  schedulerResume: () => api.post<any>("/admin/api/scheduler/resume"),
  schedulerRestart: () => api.post<any>("/admin/api/scheduler/restart"),
  schedulerStatus: () =>
    api.get<{
      status: string;
      background_daemon: {
        running: boolean;
        job_count: number;
        schedule_type: string;
        interval_seconds: number;
      };
      scan_active: boolean;
      report_schedule: {
        enabled: boolean;
        frequency: string;
        timezone: string;
        report_time: string;
        next_run: string;
        last_email_sent: string;
        last_pipeline_run: string;
      };
    }>("/admin/api/scheduler/status"),
  dbHealth: () => api.get<any>("/admin/api/db/health"),
  emailTest: (email: string) => api.post<any>("/admin/api/email/test", { email }),

  // Newly added by backend-api
  users: () => api.get<{ status: string; users: any[]; admins: any[] }>("/admin/api/users"),
  createUser: (data: { username: string; email: string; password: string; role: string }) =>
    api.post<{ status: string; message: string }>("/admin/api/users", data),
  toggleUser: (userId: string) =>
    api.patch<{ status: string; is_active: boolean }>(`/admin/api/users/${userId}`),
  deleteUser: (userId: string) =>
    api.delete<{ status: string; message: string }>(`/admin/api/users/${userId}`),
  sourceHealth: () =>
    api.get<{
      status: string;
      sources: AdminSourceDefinition[];
      records: AdminSourceHealthRecord[];
    }>("/admin/api/source-health"),
  dataQuality: () => api.get<{ status: string; quarantine: any[]; metrics: any }>("/admin/api/data-quality"),
  quarantineAction: (data: {
    action: "approve" | "reject";
    item_id: string;
    record_type?: "Production Opportunity" | "Staged Candidate";
  }) =>
    api.post<{ status: string; action?: string; error?: string }>("/admin/quarantine/action", data),
  diagnostics: () => api.get<{ status: string; diagnostics: any }>("/admin/api/diagnostics"),
};
