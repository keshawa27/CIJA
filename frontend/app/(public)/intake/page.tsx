"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { ErrorNote, NEED_LABEL } from "@/lib/ui";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="card space-y-4">
      <legend className="px-1 text-lg font-semibold">{title}</legend>
      {children}
    </fieldset>
  );
}

function Check({ name, value, children }: { name: string; value?: string; children: React.ReactNode }) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <input type="checkbox" name={name} value={value} className="mt-0.5 h-4 w-4" />
      <span>{children}</span>
    </label>
  );
}

export default function IntakePage() {
  const [contact, setContact] = useState("email");
  const [reference, setReference] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => (form.get(name) as string).trim();
    const needs = form.getAll("needs");
    if (needs.length === 0) {
      setError(new Error("Please choose at least one kind of support."));
      return;
    }
    setSending(true);
    setError(null);
    try {
      const result = await api<{ reference_code: string }>("/intake", {
        body: {
          first_name: text("first_name"),
          last_name: text("last_name"),
          date_of_birth: text("date_of_birth") || null,
          email: text("email") || null,
          phone: text("phone") || null,
          safe_contact_method: contact,
          safe_to_leave_message: form.has("safe_to_leave_message"),
          safe_contact_notes: text("safe_contact_notes"),
          needs,
          immediate_safety_concern: form.has("immediate_safety_concern"),
          housing_unstable: form.has("housing_unstable"),
          has_dependants: form.has("has_dependants"),
          urgency_self_rating: Number(form.get("urgency_self_rating")),
          free_text: text("free_text"),
          consent: form.has("consent"),
          website: text("website"),
        },
      });
      setReference(result.reference_code);
      window.scrollTo(0, 0);
    } catch (e) {
      setError(e);
    } finally {
      setSending(false);
    }
  }

  if (reference) {
    return (
      <div className="space-y-4" role="status">
        <h1 className="text-2xl font-bold">Thank you. We have your request.</h1>
        <div className="card">
          <p className="text-sm text-slate-600">Your reference code</p>
          <p className="font-mono text-2xl font-bold tracking-wider">{reference}</p>
        </div>
        <p>
          Keep this code somewhere safe. A member of our team will contact you using the method you told us is safe.
          You can use the code to <Link href="/status" className="underline">check your request</Link>.
        </p>
        <p className="error">
          If you are in immediate danger, call <strong>000</strong>.
        </p>
      </div>
    );
  }

  return (
    <form method="post" onSubmit={submit} className="space-y-6">
      <h1 className="text-2xl font-bold">Ask for support</h1>

      <div className="rounded-md border border-teal-300 bg-teal-50 p-4 text-sm text-teal-950">
        <p className="font-semibold">How we use your information</p>
        <p>
          We collect these details only to understand what support you need and to contact you safely. They are seen
          only by the Vela Client Services staff working on your request. You can ask to see or correct your
          information at any time.
        </p>
      </div>

      <Section title="About you">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="first_name" className="label">First name</label>
            <input id="first_name" name="first_name" className="input" required maxLength={80} autoComplete="off" />
          </div>
          <div>
            <label htmlFor="last_name" className="label">Last name</label>
            <input id="last_name" name="last_name" className="input" required maxLength={80} autoComplete="off" />
          </div>
        </div>
        <div className="sm:w-1/2">
          <label htmlFor="date_of_birth" className="label">Date of birth (optional)</label>
          <input id="date_of_birth" name="date_of_birth" type="date" className="input" />
        </div>
      </Section>

      <Section title="How can we safely contact you?">
        <div className="space-y-2" role="radiogroup" aria-label="Safest way to contact you">
          {[
            ["email", "Email is safe"],
            ["phone", "Phone is safe"],
            ["none", "It is not safe to contact me right now"],
          ].map(([value, label]) => (
            <label key={value} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="safe_contact_method"
                value={value}
                checked={contact === value}
                onChange={() => setContact(value)}
                className="h-4 w-4"
              />
              {label}
            </label>
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="email" className="label">Email{contact !== "email" && " (optional)"}</label>
            <input id="email" name="email" type="email" className="input" required={contact === "email"}
              autoComplete="off" />
          </div>
          <div>
            <label htmlFor="phone" className="label">Phone{contact !== "phone" && " (optional)"}</label>
            <input id="phone" name="phone" type="tel" className="input" required={contact === "phone"}
              pattern="[0-9+() \-]{6,20}" title="6 to 20 digits; spaces, +, - and brackets are allowed"
              autoComplete="off" />
          </div>
        </div>
        <Check name="safe_to_leave_message">It is safe to leave a message or voicemail</Check>
        <div>
          <label htmlFor="safe_contact_notes" className="label">
            Anything we should know about contacting you? (optional)
          </label>
          <textarea id="safe_contact_notes" name="safe_contact_notes" className="input" rows={2} maxLength={500}
            placeholder="For example: only call on weekdays between 10am and 2pm" />
        </div>
      </Section>

      <Section title="What do you need help with?">
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(NEED_LABEL).map(([value, label]) => (
            <Check key={value} name="needs" value={value}>{label}</Check>
          ))}
        </div>
      </Section>

      <Section title="Your situation">
        <Check name="immediate_safety_concern">I am worried about my safety right now</Check>
        <Check name="housing_unstable">I do not have a safe or stable place to stay</Check>
        <Check name="has_dependants">I care for children or other dependants</Check>
        <div className="sm:w-1/2">
          <label htmlFor="urgency_self_rating" className="label">How urgent does this feel to you?</label>
          <select id="urgency_self_rating" name="urgency_self_rating" className="input" defaultValue="3">
            <option value="1">1 – Not urgent</option>
            <option value="2">2</option>
            <option value="3">3 – Somewhat urgent</option>
            <option value="4">4</option>
            <option value="5">5 – Very urgent</option>
          </select>
        </div>
        <div>
          <label htmlFor="free_text" className="label">Anything else you would like us to know? (optional)</label>
          <textarea id="free_text" name="free_text" className="input" rows={4} maxLength={2000} />
        </div>
      </Section>

      {/* Honeypot: invisible to people, so anything typed here came from a bot. */}
      <div className="hidden" aria-hidden="true">
        <label>Website<input name="website" tabIndex={-1} autoComplete="off" /></label>
      </div>

      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" name="consent" required className="mt-0.5 h-4 w-4" />
        <span>I agree to Vela collecting and using this information to respond to my request.</span>
      </label>

      <ErrorNote error={error} />
      <button className="btn" disabled={sending}>{sending ? "Sending…" : "Send my request"}</button>
    </form>
  );
}
