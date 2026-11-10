"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { ErrorNote } from "@/lib/ui";

export default function StatusPage() {
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function lookUp(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const reference = new FormData(event.currentTarget).get("reference") as string;
    setStatus(null);
    setError(null);
    try {
      setStatus((await api<{ status: string }>(`/intake/status/${encodeURIComponent(reference.trim())}`)).status);
    } catch (e) {
      setError(e);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Check a request</h1>
      <form method="post" onSubmit={lookUp} className="card flex flex-wrap items-end gap-3">
        <div className="min-w-48 flex-1">
          <label htmlFor="reference" className="label">
            Reference code
          </label>
          <input id="reference" name="reference" className="input" placeholder="VELA-XXXXXXXX" required />
        </div>
        <button className="btn">Check</button>
      </form>
      {status && (
        <p className="card text-lg" role="status">
          Status: <strong>{status}</strong>
        </p>
      )}
      <ErrorNote error={error} />
    </div>
  );
}
