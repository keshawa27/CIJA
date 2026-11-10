"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api, type CaseSummary, type Summary } from "@/lib/api";
import {
  Badge,
  ErrorNote,
  formatDate,
  PRIORITIES,
  PRIORITY_BAR,
  PriorityBadge,
  STAGE_LABEL,
  STAGES,
  useMe,
} from "@/lib/ui";

const REFRESH = 15_000; // the board polls, so it stays current on a wall screen

function Tile({ label, value, alert = false }: { label: string; value: string | number; alert?: boolean }) {
  return (
    <div className={`card ${alert ? "border-red-300 bg-red-50" : ""}`}>
      <p className="text-xs font-semibold tracking-wide text-slate-600 uppercase">{label}</p>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function CaseCard({ item, canOpen }: { item: CaseSummary; canOpen: boolean }) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs">{item.reference_code}</span>
        <PriorityBadge priority={item.priority} />
      </div>
      {item.client_name && <p className="mt-1 text-sm font-medium">{item.client_name}</p>}
      <p className="text-xs text-slate-600">
        {item.assignee_name ?? "Unassigned"} · {formatDate(item.submitted_at)}
      </p>
      <div className="mt-1 flex flex-wrap gap-1">
        {item.stalled && <Badge className="border-red-300 bg-red-100 text-red-900">Stalled</Badge>}
        {item.possible_duplicate && <Badge className="border-violet-300 bg-violet-100 text-violet-900">Duplicate?</Badge>}
      </div>
    </>
  );
  const style = `block rounded-md border bg-white p-2 shadow-sm ${item.stalled ? "border-red-400" : "border-slate-200"}`;
  return canOpen ? (
    <Link href={`/cases/${item.id}`} className={`${style} hover:border-teal-600`}>
      {body}
    </Link>
  ) : (
    <div className={style}>{body}</div>
  );
}

export default function DashboardPage() {
  const { data: me } = useMe();
  const [priority, setPriority] = useState("");
  const [assignee, setAssignee] = useState("");
  const [stalledOnly, setStalledOnly] = useState(false);
  const [showClosed, setShowClosed] = useState(false);

  const summary = useQuery({
    queryKey: ["summary"],
    queryFn: () => api<Summary>("/dashboard/summary"),
    refetchInterval: REFRESH,
  });
  const cases = useQuery({
    queryKey: ["cases"],
    queryFn: () => api<CaseSummary[]>("/cases"),
    refetchInterval: REFRESH,
  });

  const all = cases.data ?? [];
  const assignees = [...new Set(all.map((c) => c.assignee_name).filter(Boolean))].sort() as string[];
  const visible = all.filter(
    (c) =>
      (!priority || c.priority === priority) &&
      (!assignee || c.assignee_name === assignee) &&
      (!stalledOnly || c.stalled),
  );
  const columns = STAGES.filter((stage) => showClosed || stage !== "closed");
  const s = summary.data;
  const busiest = s ? Math.max(1, ...Object.values(s.by_priority)) : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{me?.role === "caseworker" ? "My cases" : "Intake dashboard"}</h1>
      <ErrorNote error={summary.error ?? cases.error} />

      {s && (
        <section aria-label="Summary" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Tile label="Open cases" value={s.open_cases} />
          <Tile label="Urgent, open" value={s.urgent_open} alert={s.urgent_open > 0} />
          <Tile label="Stalled" value={s.stalled} alert={s.stalled > 0} />
          <Tile label="Closed" value={s.closed} />
          <Tile label="Avg. days to close" value={s.avg_cycle_days ?? "–"} />
          <Tile
            label="All steps completed"
            value={s.step_completion_rate === null ? "–" : `${Math.round(s.step_completion_rate * 100)}%`}
          />
        </section>
      )}

      {s && (
        <section aria-label="Open cases by priority" className="card">
          <h2 className="mb-2 text-sm font-semibold">Open cases by priority</h2>
          <div className="space-y-1">
            {PRIORITIES.map((p) => (
              <div key={p} className="flex items-center gap-2 text-sm">
                <span className="w-20 capitalize">{p}</span>
                <div className="h-4 flex-1 rounded bg-slate-100">
                  <div className={`h-4 rounded ${PRIORITY_BAR[p]}`} style={{ width: `${(s.by_priority[p] / busiest) * 100}%` }} />
                </div>
                <span className="w-8 text-right tabular-nums">{s.by_priority[p]}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section aria-label="Filters" className="flex flex-wrap items-end gap-4">
        <div>
          <label htmlFor="priority" className="label">Priority</label>
          <select id="priority" className="input" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="">All</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>
            ))}
          </select>
        </div>
        {me?.role !== "caseworker" && (
          <div>
            <label htmlFor="assignee" className="label">Caseworker</label>
            <select id="assignee" className="input" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">All</option>
              {assignees.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </div>
        )}
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" className="h-4 w-4" checked={stalledOnly} onChange={(e) => setStalledOnly(e.target.checked)} />
          Stalled only
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" className="h-4 w-4" checked={showClosed} onChange={(e) => setShowClosed(e.target.checked)} />
          Show closed
        </label>
      </section>

      <section aria-label="Cases by stage" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-flow-col xl:auto-cols-fr xl:grid-cols-none">
        {columns.map((stage) => {
          const inStage = visible.filter((c) => c.stage === stage);
          return (
            <div key={stage} className="rounded-lg bg-slate-200/70 p-2">
              <h2 className="mb-2 flex items-center justify-between px-1 text-sm font-semibold">
                {STAGE_LABEL[stage]}
                <span className="rounded-full bg-white px-2 text-xs tabular-nums">{inStage.length}</span>
              </h2>
              <div className="space-y-2">
                {inStage.map((item) => (
                  <CaseCard key={item.id} item={item} canOpen={me?.role !== "manager"} />
                ))}
                {inStage.length === 0 && <p className="px-1 py-2 text-xs text-slate-600">No cases</p>}
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
