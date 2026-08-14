"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export type DemoCredentials = {
  assistantEmail: string;
  assistantPassword: string;
  managerEmail: string;
  managerPassword: string;
};

export default function ClinicLoginForm({ demoCredentials }: { demoCredentials?: DemoCredentials }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: data.get("email"), password: data.get("password") }),
      });
      router.push("/clinic/queue");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return <main className="loginShell">
    <section className="loginAside">
      <span className="eyebrow light">Clinic workspace</span>
      <h1>One clear queue.<br />Every detail traceable.</h1>
      <p>Review administrative readiness while keeping people in control.</p>
    </section>
    <section className="loginPanel">
      <form onSubmit={submit}>
        <span className="eyebrow">Staff access</span>
        <h2>Welcome back</h2>
        <p className="muted">{demoCredentials ? "Use a seeded synthetic demo account." : "Use the credentials provided by the demo operator."}</p>
        <label>Email<input name="email" type="email" autoComplete="username" defaultValue={demoCredentials?.assistantEmail || ""} required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" defaultValue={demoCredentials?.assistantPassword || ""} required /></label>
        {error && <div className="alert error">{error}</div>}
        <button className="button primary wide" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {demoCredentials && <small className="demoHint">Manager: {demoCredentials.managerEmail} / {demoCredentials.managerPassword}</small>}
      </form>
    </section>
  </main>;
}
