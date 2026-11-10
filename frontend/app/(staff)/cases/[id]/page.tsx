"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api, type CaseDetail, type Task, type User } from "@/lib/api";
import {
  Badge,
  ErrorNote,
  formatDate,
  formatDateTime,
  NEED_LABEL,
  PRIORITIES,
  PriorityBadge,
  STAGE_LABEL,
  STAGES,
  useMe,
} from "@/lib/ui";

const CONTACT_LABEL = { email: "Email", phone: "Phone", none: "No safe contact method" };

const ACTION_LABEL: Record<string, string> = {
  "intake.submitted": "Intake submitted and triaged",
  "stage.changed": "Stage changed",
  "task.completed": "Step completed",
  "task.skipped": "Step skipped",
  "triage.overridden": "Priority changed",
  "case.reassigned": "Case reassigned",
  "note.added": "Note added",
};

function timelineText(action: string, detail: Record<string, unknown>): string {
  const label = ACTION_LABEL[action] ?? action;
  if (action === "stage.changed") return `${label}: ${STAGE_LABEL[detail.to as string] ?? detail.to}`;
  if (action === "task.completed") return `${label}: ${detail.title}`;
  if (action === "task.skipped") return `${label}: ${detail.title} (${detail.reason})`;
  if (action === "triage.overridden") return `${label}: ${detail.from} → ${detail.to} (${detail.reason})`;
  return label;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-slate-600 uppercase">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

export default function CasePage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const isLead = me?.role === "team_lead";
  const [skipping, setSkipping] = useState<string | null>(null); // id of the task being skipped

  const query = useQuery({ queryKey: ["case", id], queryFn: () => api<CaseDetail>(`/cases/${id}`) });
  const assignees = useQuery({
    queryKey: ["assignees"],
    queryFn: () => api<User[]>("/cases/assignees"),
    enabled: isLead,
  });

  // Every change goes through here: call the API, then refetch whatever is on screen.
  const change = useMutation({
    mutationFn: ({ path, method, body }: { path: string; method?: string; body?: unknown }) =>
      api(path, { method, body }),
    onSettled: () => queryClient.invalidateQueries(),
  });

  // Runs a form's API call and clears the form once it succeeds.
  function submitWith(build: (form: FormData) => { path: string; method?: string; body?: unknown }) {
    return (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const form = event.currentTarget;
      change.mutate(build(new FormData(form)), {
        onSuccess: () => {
          form.reset();
          setSkipping(null);
        },
      });
    };
  }

  if (query.error) {
    return (
      <div className="space-y-4">
        <ErrorNote error={query.error} />
        <Link href="/dashboard" className="underline">Back to dashboard</Link>
      </div>
    );
  }
  const c = query.data;
  if (!c) return <p className="text-slate-600">Loading…</p>;

  const reached = STAGES.indexOf(c.stage as (typeof STAGES)[number]);
  const tasksByStage = STAGES.map((stage) => [stage, c.tasks.filter((t) => t.stage === stage)] as const).filter(
    ([, tasks]) => tasks.length > 0,
  );

  const taskRow = (task: Task) => (
    <li key={task.id} className="border-b border-slate-100 py-2 last:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <span aria-hidden="true" className="w-5 text-center">
          {task.status === "done" ? "✓" : task.status === "skipped" ? "–" : "○"}
        </span>
        <span className={`flex-1 text-sm ${task.status === "open" ? "font-medium" : "text-slate-600"}`}>
          {task.title}
          <span className="sr-only"> ({task.status})</span>
          {task.status === "skipped" && (
            <span className="block text-xs">Skipped: {task.skip_reason}</span>
          )}
        </span>
        {task.status === "open" ? (
          <>
            <span className="text-xs text-slate-600">Due {formatDate(task.due_at)}</span>
            {new Date(task.due_at) < new Date() && (
              <Badge className="border-red-300 bg-red-100 text-red-900">Overdue</Badge>
            )}
            <button type="button" className="btn-secondary" disabled={change.isPending}
              onClick={() => change.mutate({ path: `/tasks/${task.id}/complete`, method: "POST" })}>
              Mark done
            </button>
            {isLead && (
              <button type="button" className="btn-secondary" aria-expanded={skipping === task.id}
                onClick={() => setSkipping(skipping === task.id ? null : task.id)}>
                Skip…
              </button>
            )}
          </>
        ) : (
          task.completed_at && <span className="text-xs text-slate-600">{formatDateTime(task.completed_at)}</span>
        )}
      </div>
      {skipping === task.id && (
        <form method="post" className="mt-2 flex flex-wrap items-end gap-2 pl-7"
          onSubmit={submitWith((form) => ({ path: `/tasks/${task.id}/skip`, body: { reason: form.get("reason") } }))}>
          <div className="min-w-48 flex-1">
            <label htmlFor={`skip-${task.id}`} className="label">Why is this step being skipped?</label>
            <input id={`skip-${task.id}`} name="reason" className="input" required minLength={5} maxLength={500} />
          </div>
          <button className="btn" disabled={change.isPending}>Skip step</button>
        </form>
      )}
    </li>
  );

  return (
    <div className="space-y-6">
      <div>
        <Link href="/dashboard" className="text-sm underline">← Dashboard</Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">{c.first_name} {c.last_name}</h1>
          <span className="font-mono text-sm text-slate-600">{c.reference_code}</span>
          <PriorityBadge priority={c.priority} />
        </div>
        <p className="text-sm text-slate-600">
          Submitted {formatDateTime(c.submitted_at)} · Assigned to {c.assignee_name ?? "nobody"}
          {c.closed_at && ` · Closed ${formatDateTime(c.closed_at)}`}
        </p>
      </div>

      <ol aria-label="Progress through the intake journey" className="flex flex-wrap gap-1">
        {STAGES.map((stage, i) => (
          <li key={stage} aria-current={i === reached ? "step" : undefined}
            className={`rounded-md border px-3 py-1 text-sm ${
              i < reached
                ? "border-teal-200 bg-teal-50 text-teal-900"
                : i === reached
                  ? "border-teal-700 bg-teal-700 font-semibold text-white"
                  : "border-slate-200 bg-white text-slate-500"
            }`}>
            {i < reached && <span aria-hidden="true">✓ </span>}
            {STAGE_LABEL[stage]}
          </li>
        ))}
      </ol>

      <ErrorNote error={change.error} />

      {c.duplicate_reference && (
        <p className="rounded-md border border-violet-300 bg-violet-50 px-3 py-2 text-sm text-violet-950">
          Possible duplicate: the same email or phone was used for <span className="font-mono">{c.duplicate_reference}</span>.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <section className="card" aria-labelledby="steps">
            <h2 id="steps" className="mb-2 text-lg font-semibold">Steps</h2>
            {tasksByStage.map(([stage, tasks]) => (
              <div key={stage} className="mb-3 last:mb-0">
                <h3 className="text-xs font-semibold tracking-wide text-slate-600 uppercase">{STAGE_LABEL[stage]}</h3>
                <ul>{tasks.map(taskRow)}</ul>
              </div>
            ))}
            {c.stage === "closed" && <p className="text-sm text-slate-600">All steps finished. This case is closed.</p>}
          </section>

          <section className="card" aria-labelledby="notes">
            <h2 id="notes" className="mb-2 text-lg font-semibold">Notes</h2>
            {c.notes.length === 0 && <p className="text-sm text-slate-600">No notes yet.</p>}
            <ul className="space-y-3">
              {c.notes.map((note) => (
                <li key={note.id} className="rounded-md bg-slate-50 p-3">
                  <p className="text-sm whitespace-pre-line">{note.body}</p>
                  <p className="mt-1 text-xs text-slate-600">{note.author_name} · {formatDateTime(note.created_at)}</p>
                </li>
              ))}
            </ul>
            <form method="post" className="mt-3 space-y-2"
              onSubmit={submitWith((form) => ({ path: `/cases/${id}/notes`, body: { body: form.get("body") } }))}>
              <label htmlFor="note" className="label">Add a note</label>
              <textarea id="note" name="body" className="input" rows={3} required maxLength={4000} />
              <button className="btn" disabled={change.isPending}>Save note</button>
            </form>
          </section>

          <section className="card" aria-labelledby="history">
            <h2 id="history" className="mb-2 text-lg font-semibold">History</h2>
            <ol className="space-y-1">
              {c.timeline.map((entry, i) => (
                <li key={i} className="flex flex-wrap gap-x-3 text-sm">
                  <span className="w-32 shrink-0 text-xs leading-5 text-slate-600">{formatDateTime(entry.at)}</span>
                  <span className="flex-1">{timelineText(entry.action, entry.detail)}</span>
                  <span className="text-xs leading-5 text-slate-600">{entry.actor_name ?? "System"}</span>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <div className="space-y-6">
          <section className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4" aria-labelledby="contact">
            <h2 id="contact" className="mb-2 text-lg font-semibold">Safe contact</h2>
            <dl className="space-y-2">
              <Field label="Contact by">{CONTACT_LABEL[c.safe_contact_method]}</Field>
              <Field label="Leave a message?">{c.safe_to_leave_message ? "Yes, safe" : "No — do not leave a message"}</Field>
              {c.safe_contact_notes && <Field label="Client's instructions">{c.safe_contact_notes}</Field>}
              {(["email", "phone"] as const).map((method) => (
                <Field key={method} label={CONTACT_LABEL[method]}>
                  {c[method] ?? "–"}
                  {c[method] && c.safe_contact_method !== method && (
                    <strong className="block text-red-800">Not marked safe — do not use</strong>
                  )}
                </Field>
              ))}
            </dl>
          </section>

          <section className="card" aria-labelledby="triage">
            <h2 id="triage" className="mb-2 text-lg font-semibold">Triage</h2>
            <dl className="space-y-2">
              <Field label="Priority">
                <PriorityBadge priority={c.priority} /> <span className="text-slate-600">score {c.triage_score}</span>
              </Field>
              <Field label="Why">
                <ul className="list-disc pl-4">
                  {c.triage_reasons.map((reason) => <li key={reason}>{reason}</li>)}
                </ul>
              </Field>
              {c.triage_original_priority && (
                <Field label="Changed by team lead">
                  Was <span className="capitalize">{c.triage_original_priority}</span>. {c.triage_override_reason}
                </Field>
              )}
              <Field label="Service stream">{c.service_stream.replace("_", " ")}</Field>
            </dl>

            {isLead && c.stage !== "closed" && (
              <>
                <form method="post" className="mt-4 space-y-2 border-t border-slate-200 pt-3"
                  onSubmit={submitWith((form) => ({
                    path: `/cases/${id}/triage`,
                    method: "PATCH",
                    body: { priority: form.get("priority"), reason: form.get("reason") },
                  }))}>
                  <label htmlFor="priority" className="label">Change priority</label>
                  <select id="priority" name="priority" className="input" defaultValue={c.priority}>
                    {PRIORITIES.map((p) => <option key={p} value={p}>{p[0].toUpperCase() + p.slice(1)}</option>)}
                  </select>
                  <label htmlFor="reason" className="label">Reason</label>
                  <input id="reason" name="reason" className="input" required minLength={5} maxLength={500} />
                  <button className="btn-secondary" disabled={change.isPending}>Change priority</button>
                </form>

                <form method="post" className="mt-4 space-y-2 border-t border-slate-200 pt-3"
                  onSubmit={submitWith((form) => ({
                    path: `/cases/${id}/assignee`,
                    method: "PATCH",
                    body: { user_id: form.get("user_id") },
                  }))}>
                  <label htmlFor="user_id" className="label">Reassign to</label>
                  <select id="user_id" name="user_id" className="input" defaultValue={c.assigned_to ?? ""} required>
                    <option value="" disabled>Choose…</option>
                    {assignees.data?.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                  </select>
                  <button className="btn-secondary" disabled={change.isPending}>Reassign</button>
                </form>
              </>
            )}
          </section>

          <section className="card" aria-labelledby="client">
            <h2 id="client" className="mb-2 text-lg font-semibold">What the client told us</h2>
            <dl className="space-y-2">
              <Field label="Date of birth">{c.date_of_birth ? formatDate(c.date_of_birth) : "–"}</Field>
              <Field label="Needs">{c.needs.map((n) => NEED_LABEL[n] ?? n).join("; ")}</Field>
              <Field label="Safety concern right now">{c.immediate_safety_concern ? "Yes" : "No"}</Field>
              <Field label="Housing unstable">{c.housing_unstable ? "Yes" : "No"}</Field>
              <Field label="Has dependants">{c.has_dependants ? "Yes" : "No"}</Field>
              <Field label="Urgency (self-rated)">{c.urgency_self_rating} of 5</Field>
              {c.free_text && <Field label="In their words"><span className="whitespace-pre-line">{c.free_text}</span></Field>}
              <Field label="Consent given">{formatDateTime(c.consent_at)}</Field>
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}
