"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ClinicNav from "@/components/ClinicNav";
import { api, prettyStatus } from "@/lib/api";

type Metric = { total: number; by_status: Record<string, number>; disclaimer: string };
type Ref = { id: string; kind: string; code: string; label: string; active: boolean };
type Event = { id: string; case_id?: string; actor_type: string; action: string; created_at: string };
export default function Admin() {
  const router = useRouter(); const [metrics, setMetrics] = useState<Metric>(); const [refs, setRefs] = useState<Ref[]>([]); const [events, setEvents] = useState<Event[]>([]);
  useEffect(() => { Promise.all([api<Metric>("/admin/metrics"), api<Ref[]>("/admin/reference-data"), api<Event[]>("/admin/audit")]).then(([m, r, e]) => { setMetrics(m); setRefs(r); setEvents(e); }).catch(() => router.replace("/clinic/queue")); }, [router]);
  return <main className="clinicShell"><ClinicNav role="manager" /><div className="workspace"><header className="workspaceHeader"><div><span className="eyebrow">Manager controls</span><h1>Operations overview</h1></div></header><p className="muted">{metrics?.disclaimer}</p><section className="metricGrid"><article><small>Total cases</small><strong>{metrics?.total || 0}</strong></article>{Object.entries(metrics?.by_status || {}).map(([status, count]) => <article key={status}><small>{prettyStatus(status)}</small><strong>{count}</strong></article>)}</section><div className="adminGrid"><section className="panel"><h2>Reference data</h2>{refs.map((item) => <div className="referenceRow" key={item.id}><span><b>{item.code}</b><small>{item.kind}</small></span><span>{item.label}</span></div>)}</section><section className="panel"><h2>Immutable audit trail</h2>{events.slice(0, 30).map((event) => <div className="auditRow" key={event.id}><span><b>{event.action}</b><small>{event.actor_type} · {event.case_id?.slice(0, 8) || "system"}</small></span><time>{new Date(event.created_at).toLocaleString()}</time></div>)}</section></div></div></main>;
}

