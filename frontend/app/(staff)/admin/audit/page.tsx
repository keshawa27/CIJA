"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type AuditEntry } from "@/lib/api";
import { ErrorNote, formatDateTime } from "@/lib/ui";

const PAGE = 50;
const ACTIONS = [
  "intake.submitted",
  "stage.changed",
  "task.completed",
  "task.skipped",
  "triage.overridden",
  "case.reassigned",
  "case.viewed",
  "note.added",
  "login.success",
  "login.failed",
  "user.created",
  "user.updated",
];

export default function AuditPage() {
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const query = useQuery({
    queryKey: ["audit", action, offset],
    queryFn: () =>
      api<AuditEntry[]>(`/admin/audit?limit=${PAGE}&offset=${offset}${action ? `&action=${action}` : ""}`),
    placeholderData: keepPreviousData,
  });
  const rows = query.data ?? [];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Audit log</h1>
      <p className="text-sm text-slate-600">
        Every change and every time a case was opened. Entries cannot be edited or deleted.
      </p>
      <div className="w-64">
        <label htmlFor="action" className="label">Action</label>
        <select id="action" className="input" value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setOffset(0);
          }}>
          <option value="">All actions</option>
          {ACTIONS.map((a) => <option key={a}>{a}</option>)}
        </select>
      </div>
      <ErrorNote error={query.error} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">When</th>
              <th className="th">Who</th>
              <th className="th">Action</th>
              <th className="th">Detail</th>
              <th className="th">IP</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((entry) => (
              <tr key={entry.id} className="border-b border-slate-100 align-top last:border-0">
                <td className="td whitespace-nowrap">{formatDateTime(entry.at)}</td>
                <td className="td">{entry.actor_name ?? "System / public"}</td>
                <td className="td font-mono text-xs">{entry.action}</td>
                <td className="td font-mono text-xs break-all">
                  {Object.entries(entry.detail).map(([key, value]) => `${key}=${String(value)}`).join("  ")}
                </td>
                <td className="td font-mono text-xs">{entry.ip ?? "–"}</td>
              </tr>
            ))}
            {rows.length === 0 && !query.isLoading && (
              <tr><td className="td text-slate-600" colSpan={5}>No entries.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-3">
        <button type="button" className="btn-secondary" disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          Newer
        </button>
        <button type="button" className="btn-secondary" disabled={rows.length < PAGE}
          onClick={() => setOffset(offset + PAGE)}>
          Older
        </button>
        <span className="text-sm text-slate-600">Showing {rows.length ? offset + 1 : 0}–{offset + rows.length}</span>
      </div>
    </div>
  );
}
