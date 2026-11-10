"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { api, type Notification, type Role } from "@/lib/api";
import { formatDateTime, ROLE_LABEL, useMe } from "@/lib/ui";

// Navigation only. What each role may actually do is enforced by the API.
const NAV: { href: string; label: string; roles: Role[] }[] = [
  { href: "/dashboard", label: "Dashboard", roles: ["caseworker", "team_lead", "manager"] },
  { href: "/tasks", label: "My tasks", roles: ["caseworker", "team_lead"] },
  { href: "/admin/users", label: "Users", roles: ["admin"] },
  { href: "/admin/audit", label: "Audit log", roles: ["admin", "team_lead"] },
];

function Notifications({ canOpenCases }: { canOpenCases: boolean }) {
  const queryClient = useQueryClient();
  const { data = [] } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api<Notification[]>("/notifications"),
    refetchInterval: 20_000,
  });
  const unread = data.filter((n) => !n.read_at).length;

  async function markRead(notification: Notification) {
    if (notification.read_at) return;
    await api(`/notifications/${notification.id}/read`, { method: "POST" });
    queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  return (
    <details className="relative">
      <summary className="btn-secondary list-none" aria-label={`Notifications, ${unread} unread`}>
        Notifications
        {unread > 0 && (
          <span className="ml-2 rounded-full bg-red-700 px-1.5 text-xs font-bold text-white">{unread}</span>
        )}
      </summary>
      <ul className="absolute left-0 z-20 mt-2 max-h-96 w-80 max-w-[calc(100vw-2rem)] overflow-y-auto sm:right-0 sm:left-auto rounded-lg border border-slate-200 bg-white shadow-lg">
        {data.length === 0 && <li className="p-3 text-sm text-slate-600">No notifications.</li>}
        {data.map((n) => {
          const content = (
            <>
              <p className={`text-sm ${n.read_at ? "text-slate-600" : "font-semibold"}`}>{n.subject}</p>
              <p className="text-xs text-slate-600">{formatDateTime(n.created_at)}</p>
            </>
          );
          return (
            <li key={n.id} className="border-b border-slate-100 last:border-0">
              {canOpenCases && n.intake_id ? (
                <Link href={`/cases/${n.intake_id}`} onClick={() => markRead(n)} className="block p-3 hover:bg-slate-50">
                  {content}
                </Link>
              ) : (
                <button type="button" onClick={() => markRead(n)} className="block w-full p-3 text-left hover:bg-slate-50">
                  {content}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </details>
  );
}

export default function StaffLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { data: me, isError } = useMe();

  useEffect(() => {
    if (isError) router.replace("/login"); // not signed in, or the session expired
  }, [isError, router]);

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    queryClient.clear();
    router.replace("/login");
  }

  if (!me) return <p className="p-8 text-slate-600">Loading…</p>;

  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-lg font-semibold text-teal-800">Vela intake</span>
          <nav className="flex flex-wrap gap-1" aria-label="Main">
            {NAV.filter((item) => item.roles.includes(me.role)).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname.startsWith(item.href) ? "page" : undefined}
                className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 aria-[current=page]:bg-teal-50 aria-[current=page]:text-teal-900"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <Notifications canOpenCases={me.role === "caseworker" || me.role === "team_lead"} />
            <span className="text-sm text-slate-700">
              {me.name} <span className="text-slate-500">({ROLE_LABEL[me.role]})</span>
            </span>
            <button type="button" onClick={signOut} className="btn-secondary">
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
    </>
  );
}
