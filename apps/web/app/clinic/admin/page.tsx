"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ClinicNav from "@/components/ClinicNav";
import { api, prettyStatus } from "@/lib/api";

type Metric = { total: number; by_status: Record<string, number>; disclaimer: string };
type EvaluationMetric = { evaluation_count: number; outcomes: Record<string, number>; processing_latency_seconds: { p50?: number; p95?: number }; latest_benchmark?: Record<string, number>; targets_are_not_claims: boolean; disclaimer: string };
type Release = { id: string; version: string; description: string; active: boolean; activated_at?: string };
type Event = { id: string; case_id?: string; actor_type: string; action: string; created_at: string; chain_verified: boolean };

export default function Admin() {
  const router = useRouter();
  const [metrics, setMetrics] = useState<Metric>();
  const [evaluation, setEvaluation] = useState<EvaluationMetric>();
  const [releases, setReleases] = useState<Release[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  useEffect(() => {
    Promise.all([
      api<Metric>("/admin/metrics"),
      api<EvaluationMetric>("/admin/evaluation-metrics"),
      api<Release[]>("/admin/reference-data/releases"),
      api<Event[]>("/admin/audit"),
    ]).then(([caseMetrics, evaluationMetrics, referenceReleases, auditEvents]) => {
      setMetrics(caseMetrics); setEvaluation(evaluationMetrics); setReleases(referenceReleases); setEvents(auditEvents);
    }).catch(() => router.replace("/clinic/queue"));
  }, [router]);
  return <main className="clinicShell"><ClinicNav role="manager" /><div className="workspace"><header className="workspaceHeader"><div><span className="eyebrow">Manager controls</span><h1>Eligibility operations</h1></div></header><p className="muted">{evaluation?.disclaimer || metrics?.disclaimer}</p>{evaluation?.targets_are_not_claims && <div className="alert info">Prototype targets are not displayed as achieved metrics until the labelled benchmark runner records a result.</div>}<section className="metricGrid"><article><small>Total cases</small><strong>{metrics?.total || 0}</strong></article><article><small>Evaluations</small><strong>{evaluation?.evaluation_count || 0}</strong></article><article><small>Processing P50</small><strong>{evaluation?.processing_latency_seconds.p50 ?? "—"}</strong></article><article><small>Processing P95</small><strong>{evaluation?.processing_latency_seconds.p95 ?? "—"}</strong></article>{Object.entries(evaluation?.outcomes || {}).map(([status, count]) => <article key={status}><small>{prettyStatus(status)}</small><strong>{count}</strong></article>)}</section><div className="adminGrid"><section className="panel"><h2>Versioned reference releases</h2>{releases.map((item) => <div className="referenceRow" key={item.id}><span><b>{item.version}</b><small>{item.active ? "Active and immutable" : "Draft"}</small></span><span>{item.description}</span></div>)}</section><section className="panel"><h2>Chained audit trail</h2>{events[0] && <div className={events[0].chain_verified ? "alert success" : "alert error"}>{events[0].chain_verified ? "Integrity chain verified" : "Audit integrity check failed"}</div>}{events.slice(0, 30).map((event) => <div className="auditRow" key={event.id}><span><b>{event.action}</b><small>{event.actor_type} · {event.case_id?.slice(0, 8) || "system"}</small></span><time>{new Date(event.created_at).toLocaleString()}</time></div>)}</section></div></div></main>;
}
