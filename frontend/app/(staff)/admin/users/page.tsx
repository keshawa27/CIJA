"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type User } from "@/lib/api";
import { ErrorNote, ROLE_LABEL, useMe } from "@/lib/ui";

export default function UsersPage() {
  const queryClient = useQueryClient();
  const { data: me } = useMe();
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/admin/users") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["users"] });

  const update = useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: string; is_active?: boolean }) =>
      api(`/admin/users/${id}`, { method: "PATCH", body }),
    onSettled: refresh,
  });
  const create = useMutation({
    mutationFn: (body: Record<string, FormDataEntryValue>) => api("/admin/users", { body }),
    onSettled: refresh,
  });

  function addUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    create.mutate(Object.fromEntries(new FormData(form)), { onSuccess: () => form.reset() });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Users</h1>
      <ErrorNote error={users.error ?? update.error} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Name</th>
              <th className="th">Email</th>
              <th className="th">Role</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.data?.map((user) => {
              const self = user.id === me?.id; // the API also refuses these changes to your own account
              return (
                <tr key={user.id} className="border-b border-slate-100 last:border-0">
                  <td className="td font-medium">{user.name}</td>
                  <td className="td">{user.email}</td>
                  <td className="td">
                    <select className="input w-auto" aria-label={`Role for ${user.name}`} value={user.role}
                      disabled={self || update.isPending}
                      onChange={(e) => update.mutate({ id: user.id, role: e.target.value })}>
                      {Object.entries(ROLE_LABEL).map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="td">
                    <button type="button" className="btn-secondary" disabled={self || update.isPending}
                      onClick={() => update.mutate({ id: user.id, is_active: !user.is_active })}>
                      {user.is_active ? "Active — deactivate" : "Inactive — reactivate"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <form method="post" onSubmit={addUser} className="card space-y-4">
        <h2 className="text-lg font-semibold">Add a user</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label htmlFor="name" className="label">Name</label>
            <input id="name" name="name" className="input" required maxLength={120} />
          </div>
          <div>
            <label htmlFor="email" className="label">Email</label>
            <input id="email" name="email" type="email" className="input" required />
          </div>
          <div>
            <label htmlFor="role" className="label">Role</label>
            <select id="role" name="role" className="input">
              {Object.entries(ROLE_LABEL).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="password" className="label">Password (12+ characters)</label>
            <input id="password" name="password" type="password" className="input" required minLength={12}
              autoComplete="new-password" />
          </div>
        </div>
        <ErrorNote error={create.error} />
        <button className="btn" disabled={create.isPending}>Add user</button>
      </form>
    </div>
  );
}
