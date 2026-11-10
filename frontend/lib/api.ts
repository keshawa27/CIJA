export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type ValidationIssue = { loc: (string | number)[]; msg: string };

function describe(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: one entry per problem
    return (detail as ValidationIssue[])
      .map(({ loc, msg }) => {
        const field = loc.slice(1).join(".").replaceAll("_", " ");
        const text = msg.replace(/^Value error, /, "");
        return field ? `${field}: ${text}` : text;
      })
      .join("\n");
  }
  if (status === 429) return "Too many attempts. Please wait a minute and try again.";
  return "Something went wrong. Please try again.";
}

export async function api<T = void>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: options.method ?? (options.body ? "POST" : "GET"),
    headers: options.body ? { "Content-Type": "application/json" } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
    credentials: "same-origin",
  });
  if (!response.ok) {
    // Session expired while working: back to sign-in rather than a page full of errors.
    // A full page load on purpose, so no cached data from the old session survives.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    if (response.status === 401 && !path.startsWith("/auth/")) window.location.assign("/login");
    const payload = await response.json().catch(() => null);
    throw new ApiError(response.status, describe(payload?.detail, response.status));
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export type Role = "caseworker" | "team_lead" | "manager" | "admin";
export type Priority = "urgent" | "high" | "standard" | "low";

export type User = { id: string; email: string; name: string; role: Role; is_active: boolean };

export type Task = {
  id: string;
  intake_id: string;
  title: string;
  stage: string;
  mandatory: boolean;
  assigned_to: string | null;
  due_at: string;
  status: "open" | "done" | "skipped";
  completed_at: string | null;
  skip_reason: string | null;
};

export type MyTask = Task & { reference_code: string; client_name: string; priority: Priority; overdue: boolean };

export type CaseSummary = {
  id: string;
  reference_code: string;
  client_name: string | null;
  priority: Priority;
  service_stream: string;
  stage: string;
  assigned_to: string | null;
  assignee_name: string | null;
  submitted_at: string;
  stalled: boolean;
  possible_duplicate: boolean;
};

export type CaseDetail = {
  id: string;
  reference_code: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  email: string | null;
  phone: string | null;
  safe_contact_method: "email" | "phone" | "none";
  safe_to_leave_message: boolean;
  safe_contact_notes: string;
  needs: string[];
  immediate_safety_concern: boolean;
  housing_unstable: boolean;
  has_dependants: boolean;
  urgency_self_rating: number;
  free_text: string;
  consent_at: string;
  priority: Priority;
  service_stream: string;
  triage_score: number;
  triage_reasons: string[];
  triage_original_priority: Priority | null;
  triage_override_reason: string | null;
  stage: string;
  assigned_to: string | null;
  assignee_name: string | null;
  submitted_at: string;
  closed_at: string | null;
  duplicate_reference: string | null;
  tasks: Task[];
  notes: { id: string; author_name: string; body: string; created_at: string }[];
  timeline: { at: string; actor_name: string | null; action: string; detail: Record<string, unknown> }[];
};

export type Summary = {
  open_cases: number;
  urgent_open: number;
  stalled: number;
  closed: number;
  by_stage: Record<string, number>;
  by_priority: Record<Priority, number>;
  avg_cycle_days: number | null;
  step_completion_rate: number | null;
};

export type Notification = {
  id: string;
  intake_id: string | null;
  subject: string;
  body: string;
  created_at: string;
  read_at: string | null;
};

export type AuditEntry = {
  id: string;
  at: string;
  actor_name: string | null;
  action: string;
  entity: string;
  entity_id: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
};
