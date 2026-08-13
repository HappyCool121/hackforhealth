"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import ClinicNav from "@/components/ClinicNav";
import { api, CaseRecord, prettyStatus, visitReasonLabel } from "@/lib/api";

type User = { name: string; role: string };
export default function Queue() {
  const router = useRouter(); const [user, setUser] = useState<User>(); const [cases, setCases] = useState<CaseRecord[]>([]); const [status, setStatus] = useState(""); const [search, setSearch] = useState("");
  const load = useCallback(async () => { try { const me = await api<User>("/auth/me"); setUser(me); setCases(await api(`/clinic/cases?status=${status}&search=${encodeURIComponent(search)}`)); } catch { router.replace("/clinic"); } }, [router, search, status]);
  useEffect(() => { void load(); }, [load]);
  return <main className="clinicShell"><ClinicNav role={user?.role} /><div className="workspace"><header className="workspaceHeader"><div><span className="eyebrow">Central Family Clinic</span><h1>Review queue</h1></div><div className="avatar">{user?.name?.split(" ").map((part) => part[0]).join("")}</div></header><section className="toolbar"><input aria-label="Search cases" placeholder="Search patient or reference" value={search} onChange={(event) => setSearch(event.target.value)} /><select aria-label="Filter status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="READY_FOR_REVIEW">Ready for review</option><option value="NEEDS_ACTION">Needs action</option><option value="APPROVED_FOR_CHECK_IN">Approved</option><option value="CHECKED_IN">Checked in</option></select></section><section className="queueTable"><div className="queueHead"><span>Patient</span><span>Visit</span><span>Readiness</span><span>Updated</span></div>{cases.length === 0 && <div className="empty"><h2>No cases here yet</h2><p>Start a patient registration, then return to this queue.</p></div>}{cases.map((item) => <Link className="queueRow" href={`/clinic/cases/${item.id}`} key={item.id}><span><strong>{item.patient_name}</strong><small>{item.reference} · ID ••••{item.id_last4}</small></span><span>{visitReasonLabel(item.visit_reason)}<small>{item.appointment_type} · {item.appointment_date || "Today / arrival"}</small></span><span><i className={`dot ${item.status.toLowerCase()}`} />{prettyStatus(item.status)}</span><span>{new Date(item.updated_at).toLocaleString()}</span></Link>)}</section></div></main>;
}
