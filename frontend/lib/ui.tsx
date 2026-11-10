"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type Priority, type User } from "./api";

export const STAGES = ["triaged", "assigned", "contacted", "assessment", "plan", "closed"] as const;

export const STAGE_LABEL: Record<string, string> = {
  submitted: "Submitted",
  triaged: "Triaged",
  assigned: "Assigned",
  contacted: "Contacted",
  assessment: "Assessment",
  plan: "Plan",
  closed: "Closed",
};

export const PRIORITIES: Priority[] = ["urgent", "high", "standard", "low"];

export const NEED_LABEL: Record<string, string> = {
  digital_safety: "Staying safe online and with technology",
  housing: "Housing",
  financial: "Money and bills",
  legal: "Legal help",
  counselling: "Someone to talk to",
  other: "Something else",
};

export const ROLE_LABEL: Record<string, string> = {
  caseworker: "Caseworker",
  team_lead: "Team lead",
  manager: "Manager",
  admin: "Admin",
};

const PRIORITY_STYLE: Record<Priority, string> = {
  urgent: "bg-red-100 text-red-900 border-red-300",
  high: "bg-amber-100 text-amber-900 border-amber-300",
  standard: "bg-sky-100 text-sky-900 border-sky-300",
  low: "bg-slate-100 text-slate-800 border-slate-300",
};

export const PRIORITY_BAR: Record<Priority, string> = {
  urgent: "bg-red-600",
  high: "bg-amber-500",
  standard: "bg-sky-600",
  low: "bg-slate-400",
};

// The priority is always written out, so colour is never the only signal.
export function PriorityBadge({ priority }: { priority: Priority }) {
  return <Badge className={PRIORITY_STYLE[priority]}>{priority}</Badge>;
}

export function Badge({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <span className={`inline-block rounded border px-1.5 py-0.5 text-xs font-semibold capitalize ${className}`}>
      {children}
    </span>
  );
}

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-AU", { day: "numeric", month: "short", year: "numeric" });

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-AU", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function useMe() {
  return useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me"), retry: false, staleTime: 60_000 });
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="error whitespace-pre-line">
      {error instanceof Error ? error.message : "Something went wrong."}
    </p>
  );
}
