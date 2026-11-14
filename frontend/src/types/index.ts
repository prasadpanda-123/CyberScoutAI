// ─── Auth ────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  username: string;
  email: string;
  role: "Super Admin" | "Administrator" | "Operator" | "Viewer" | "User";
  is_active: boolean;
  created_at: string;
  last_login?: string;
  mfa_enabled?: boolean;
}

export interface AuthState {
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
}

// ─── Opportunities ────────────────────────────────────────────────────────────

export type OpportunityCategory =
  | "Internship"
  | "Job"
  | "Bug Bounty"
  | "Vulnerability Disclosure Program"
  | "CTF"
  | "Hackathon"
  | "Free Course"
  | "Scholarship"
  | "Research"
  | "Conference"
  | "Open Source"
  | "Other";

export type FreeOnlyDecision = "APPROVED" | "REJECTED" | "QUARANTINED" | "PENDING";

export interface Opportunity {
  id: string;
  title: string;
  organization?: string;
  category?: OpportunityCategory | string;
  description?: string;
  eligibility?: string;
  skills_required?: string[];
  location?: string;
  is_remote?: boolean;
  deadline?: string;
  is_free?: boolean;
  free_only_decision?: FreeOnlyDecision;
  pricing_verified?: boolean;
  source_url?: string;
  priority_score?: number;
  created_at?: string;
  updated_at?: string;
  is_saved?: boolean;
  compensation?: string;
  prize?: string;
}

export interface OpportunityListResponse {
  opportunities: Opportunity[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface OpportunityFilters {
  q?: string;
  category?: string;
  location?: string;
  is_remote?: boolean;
  is_free?: boolean;
  sort?: "deadline" | "created_at" | "priority_score" | "title";
  page?: number;
  per_page?: number;
}

// ─── Notifications ────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  opportunity_id?: string;
  notification_type?: string;
}

// ─── Dashboard Stats ──────────────────────────────────────────────────────────

export interface DashboardStats {
  total_opportunities: number;
  new_this_week: number;
  saved_count: number;
  expiring_soon: number;
}

// ─── Admin ────────────────────────────────────────────────────────────────────

export interface AdminStats {
  total_production: number;
  total_discovered: number;
  total_extracted: number;
  total_classified: number;
  total_approved: number;
  total_quarantined: number;
  total_rejected: number;
}

export interface SourceHealth {
  name: string;
  type: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  last_success?: string;
  last_error?: string;
  items_discovered?: number;
  error_count?: number;
}

export interface AuditLog {
  id: string;
  event_type: string;
  action: string;
  outcome: string;
  username?: string;
  source_ip?: string;
  created_at: string;
  details?: string;
}

export interface AppLog {
  id: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  module: string;
  message: string;
  created_at: string;
}

// ─── API Responses ────────────────────────────────────────────────────────────

export interface ApiError {
  status: "failed" | "error";
  error: string;
  request_id?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
  has_prev: boolean;
}

