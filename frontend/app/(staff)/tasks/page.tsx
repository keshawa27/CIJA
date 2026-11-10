"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api, type MyTask } from "@/lib/api";
import { Badge, ErrorNote, formatDate, PriorityBadge, STAGE_LABEL } from "@/lib/ui";

export default function TasksPage() {
  const queryClient = useQueryClient();
  const tasks = useQuery({ queryKey: ["tasks"], queryFn: () => api<MyTask[]>("/tasks"), refetchInterval: 20_000 });
  const complete = useMutation({
    mutationFn: (id: string) => api(`/tasks/${id}/complete`, { method: "POST" }),
    onSettled: () => queryClient.invalidateQueries(),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">My tasks</h1>
      <ErrorNote error={tasks.error ?? complete.error} />
      {tasks.data?.length === 0 && <p className="card text-slate-600">Nothing to do right now.</p>}
      {!!tasks.data?.length && (
        <div className="card relative overflow-x-auto p-0">
          <table className="w-full">
            <thead className="hidden border-b border-slate-200 bg-slate-50 sm:table-header-group">
              <tr>
                <th className="th">Task</th>
                <th className="th">Case</th>
                <th className="th">Priority</th>
                <th className="th">Due</th>
                <th className="th"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {tasks.data.map((task) => (
                <tr key={task.id} className="block border-b border-slate-100 py-2 last:border-0 sm:table-row sm:py-0">
                  <td className="td block sm:table-cell">
                    {task.title}
                    <span className="block text-xs text-slate-600">{STAGE_LABEL[task.stage]} stage</span>
                  </td>
                  <td className="td block sm:table-cell">
                    <Link href={`/cases/${task.intake_id}`} className="font-medium text-teal-800 underline">
                      {task.client_name}
                    </Link>
                    <span className="block font-mono text-xs text-slate-600">{task.reference_code}</span>
                  </td>
                  <td className="td inline-block sm:table-cell"><PriorityBadge priority={task.priority} /></td>
                  <td className="td inline-block whitespace-nowrap sm:table-cell">
                    <span className="sm:hidden">Due </span>
                    {formatDate(task.due_at)}{" "}
                    {task.overdue && <Badge className="border-red-300 bg-red-100 text-red-900">Overdue</Badge>}
                  </td>
                  <td className="td block sm:table-cell sm:text-right">
                    <button type="button" className="btn-secondary" disabled={complete.isPending}
                      onClick={() => complete.mutate(task.id)}>
                      Mark done
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
