"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type User } from "@/lib/api";
import { ErrorNote } from "@/lib/ui";

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const user = await api<User>("/auth/login", {
        body: { email: form.get("email"), password: form.get("password") },
      });
      queryClient.clear(); // nothing cached from a previous user survives
      router.replace(user.role === "admin" ? "/admin/users" : "/dashboard");
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-sm flex-1 px-4 py-16">
      <h1 className="mb-6 text-2xl font-bold">Staff sign in</h1>
      <form method="post" onSubmit={signIn} className="card space-y-4">
        <div>
          <label htmlFor="email" className="label">Email</label>
          <input id="email" name="email" type="email" className="input" required autoComplete="username" />
        </div>
        <div>
          <label htmlFor="password" className="label">Password</label>
          <input id="password" name="password" type="password" className="input" required
            autoComplete="current-password" />
        </div>
        <ErrorNote error={error} />
        <button className="btn w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}
