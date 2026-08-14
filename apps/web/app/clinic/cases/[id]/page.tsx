"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import ClinicNav from "@/components/ClinicNav";
import {
  api,
  CaseRecord,
  DocumentRecord,
  FieldAssertion,
  Finding,
  documentCategoryLabel,
  documentRequirementLabel,
  prettyStatus,
  visitReasonLabel,
} from "@/lib/api";

type User = { id: string; role: "assistant" | "manager" };
const ATTESTATIONS = [
  ["IDENTITY_DOCUMENT", "Identity document sighted"],
  ["ECARD", "E-card sighted"],
  ["ORIGINAL_SUPPORTING_DOCUMENTS", "Original supporting documents sighted"],
] as const;

export default function CaseWorkspace() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<User>();
  const [record, setRecord] = useState<CaseRecord>();
  const [selected, setSelected] = useState<DocumentRecord>();
  const [selectedAssertion, setSelectedAssertion] = useState<FieldAssertion>();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [reason, setReason] = useState("Administrative evidence reviewed against the original document.");
  const [correctedValue, setCorrectedValue] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [exportKey] = useState(() => `clinicpass-${id}-${Date.now()}`);

  const load = useCallback(async () => {
    try {
      setUser(await api<User>("/auth/me"));
      const item = await api<CaseRecord>(`/clinic/cases/${id}`);
      setRecord(item);
      setSelected((current) => item.documents?.find((document) => document.id === current?.id) || item.documents?.[0]);
      setError("");
    } catch (reason) {
      if (reason instanceof Error && reason.message.includes("sign-in")) router.replace("/clinic");
      else setError(reason instanceof Error ? reason.message : "Could not load case");
    }
  }, [id, router]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!record || (record.status !== "PROCESSING" && !record.documents?.some((document) => ["QUEUED", "PROCESSING"].includes(document.status)))) return;
    const timer = setInterval(() => void load(), 2000);
    return () => clearInterval(timer);
  }, [load, record]);

  const assertions = useMemo(
    () => (record?.assertions || []).filter((item) => item.document_id === selected?.id),
    [record?.assertions, selected?.id],
  );
  const unresolved = record?.evaluation?.findings.filter((item) => item.status !== "PASS" && !item.override) || [];
  const approvalReady = record?.status === "READY_FOR_REVIEW" && !record.evaluation?.stale && unresolved.length === 0 && !record.documents?.some((item) => ["QUEUED", "PROCESSING"].includes(item.status));

  async function decision(action: "request_information" | "approve" | "cancel") {
    try {
      setRecord(await api(`/clinic/cases/${id}/review`, { method: "POST", body: JSON.stringify({ action, reason, override_failures: false }) }));
      setMessage(action === "approve" ? "Approval recorded against the fresh evaluation." : "Decision recorded.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Action failed"); }
  }

  async function saveCorrection() {
    if (!selectedAssertion) return;
    try {
      await api(`/clinic/cases/${id}/assertions/${selectedAssertion.id}`, { method: "PATCH", body: JSON.stringify({ corrected_value: correctedValue, reason: correctionReason }) });
      setMessage("Correction preserved with its original value; eligibility is now stale and will be re-evaluated.");
      setSelectedAssertion(undefined); setCorrectedValue(""); setCorrectionReason(""); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Correction failed"); }
  }

  async function handleFinding(finding: Finding) {
    const manager = user?.role === "manager";
    try {
      await api(`/clinic/cases/${id}/${manager ? "overrides" : "override-requests"}`, { method: "POST", body: JSON.stringify({ finding_id: finding.id, reason }) });
      setMessage(manager ? "Manager override recorded for this finding only." : "Override request sent to a manager.");
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Override action failed"); }
  }

  async function attest(type: string) {
    try {
      const result = await api<{ case: CaseRecord }>(`/clinic/cases/${id}/check-in/attestations`, { method: "POST", body: JSON.stringify({ attestation_type: type, confirmed: true }) });
      setRecord(result.case); setMessage("On-site check recorded separately with staff identity and time.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Attestation failed"); }
  }

  async function exportCase() {
    try {
      const result = await api<{ case: CaseRecord }>(`/clinic/cases/${id}/export`, { method: "POST", headers: { "Idempotency-Key": exportKey } });
      setRecord(result.case); setMessage("Schema-validated Clinic Assist V2 export accepted.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Export failed"); }
  }

  if (!record) return <main className="clinicShell"><ClinicNav role={user?.role} /><div className="workspace"><div className="loading">Loading case…</div>{error}</div></main>;

  return <main className="clinicShell"><ClinicNav role={user?.role} /><div className="workspace">
    <header className="workspaceHeader"><div><button className="back" onClick={() => router.push("/clinic/queue")}>← Review queue</button><h1>{record.patient_name}</h1><p>{record.reference} · ID ••••{record.id_last4}</p></div><span className={`status ${record.status.toLowerCase()}`}>{prettyStatus(record.status)}</span></header>
    <div className="alert info"><strong>{record.evaluation ? prettyStatus(record.evaluation.outcome) : "Evaluation pending"}</strong><br />Provisional administrative eligibility only. Identity, e-card, originals, final coverage, and payment remain subject to on-site and payer checks.</div>
    {record.ai_provider === "fixture" && <div className="alert info">Deterministic fixture extraction is active and clearly separated from live AGNES mode.</div>}
    {error && <div className="alert error">{error}</div>}{message && <div className="alert success">{message}</div>}
    <div className="caseGrid"><div>
      <section className="panel"><h2>Patient, visit, and reusable prefill</h2><dl className="details clinicIntakeDetails"><div><dt>Reason</dt><dd>{visitReasonLabel(record.visit_reason)}</dd></div><div><dt>Visit</dt><dd>{record.appointment_type}{record.appointment_date ? ` · ${record.appointment_date}` : ""}</dd></div><div><dt>Requested services</dt><dd>{record.requested_services.join(", ") || "Not selected"}</dd></div><div><dt>Questionnaire</dt><dd>{record.questionnaires?.map((item) => `${item.type}@${item.definition_version}`).join(", ") || "Missing"}</dd></div><div><dt>Documents</dt><dd>{documentRequirementLabel(record.document_requirement)}</dd></div><div><dt>Queue destination</dt><dd>{record.room_assignment || "Not assigned"}</dd></div></dl></section>
      <section className="panel"><div className="sectionHeading"><h2>Eligibility findings</h2>{record.evaluation && <span>{record.evaluation.ruleset_version} · refs {record.evaluation.reference_data_version}</span>}</div><div className="ruleList">{record.evaluation?.findings.map((finding) => <div className="rule findingRow" key={finding.id}><span className={`ruleState ${finding.status.toLowerCase()}`}>{finding.status}</span><div><strong>{prettyStatus(finding.code)}</strong><small>{finding.explanation}</small>{finding.override && <small className="overrideNote">Manager override: {finding.override.reason}</small>}</div>{finding.status !== "PASS" && !finding.override && <button type="button" onClick={() => void handleFinding(finding)}>{user?.role === "manager" ? "Override finding" : "Request override"}</button>}</div>) || <p className="muted">Evaluation will appear after processing.</p>}</div></section>
      <section className="panel"><h2>Document evidence and corrections</h2><div className="docTabs">{record.documents?.map((document) => <button className={selected?.id === document.id ? "active" : ""} onClick={() => { setSelected(document); setSelectedAssertion(undefined); }} key={document.id}>{document.filename}</button>)}</div>
        {!selected && <div className="emptyDocumentState"><strong>No document uploaded</strong><span>Staff must resolve the document declaration.</span></div>}
        {selected && <div className="evidenceWorkspace"><div className="documentPane"><div className="selectedDocumentMeta"><span>{documentCategoryLabel(selected.category)}</span><span>{prettyStatus(selected.status)}</span><span>{selected.scan_status}</span></div><object aria-label={`Original ${selected.filename}`} data={`/api/v1/clinic/cases/${id}/documents/${selected.id}/page/1`} type={selected.media_type}><a href={`/api/v1/clinic/cases/${id}/documents/${selected.id}/page/1`} target="_blank">Open original document</a></object>{selectedAssertion?.bounding_boxes?.length ? <div className="bboxHighlight">Highlighted citation · page {selectedAssertion.page} · box {selectedAssertion.bounding_boxes[0].join(", ")}</div> : <p className="muted">Select a field to locate its cited bounding box.</p>}</div><div className="assertionPane">{assertions.map((assertion) => <button className={`assertionCard ${selectedAssertion?.id === assertion.id ? "selected" : ""}`} key={assertion.id} onClick={() => { setSelectedAssertion(assertion); setCorrectedValue(assertion.normalized_value || ""); }}><span className={`support ${assertion.support_status.toLowerCase()}`}>{assertion.support_status}</span><strong>{prettyStatus(assertion.field_name)}</strong><span>{assertion.normalized_value || "Not found"}</span><small>{assertion.evidence_ids.length ? `${assertion.evidence_ids.length} citation(s) · page ${assertion.page}` : "No citation"}</small></button>)}</div></div>}
        {selectedAssertion && <div className="correctionEditor"><h3>Audited correction</h3><label>Authoritative value<input value={correctedValue} onChange={(event) => setCorrectedValue(event.target.value)} /></label><label>Reason<textarea value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} /></label><button className="button primary" disabled={!correctedValue || correctionReason.length < 3} onClick={() => void saveCorrection()}>Save correction and re-evaluate</button></div>}
      </section>
    </div><aside><section className="panel sticky"><h2>Staff decision</h2><p className="muted">Approval is server-gated by fresh inputs, completed processing, and resolution of every REVIEW/FAIL finding.</p><label>Decision / override reason<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>{["READY_FOR_REVIEW", "PROCESSING"].includes(record.status) && <><button className="button secondary wide" onClick={() => void decision("request_information")}>Request information</button><button className="button primary wide" onClick={() => void decision("approve")} disabled={!approvalReady}>Approve for on-site check-in</button>{!approvalReady && <small className="muted">Approval remains locked until all findings and processing are resolved.</small>}</>}{record.status === "NEEDS_ACTION" && <div className="alert info">Approval from Needs Action is prohibited. The patient must update and resubmit.</div>}{record.status === "APPROVED_FOR_CHECK_IN" && <div className="attestationList">{ATTESTATIONS.map(([type, label]) => { const done = record.attestations?.some((item) => item.type === type); return <button key={type} className={done ? "done" : ""} disabled={done} onClick={() => void attest(type)}>{done ? "✓ " : "Confirm "}{label}</button>; })}</div>}{record.status === "CHECKED_IN" && <button className="button primary wide" onClick={() => void exportCase()}>Export Clinic Assist V2 record</button>}{["EXPORTED", "COMPLETED"].includes(record.status) && <div className="alert success">Schema-validated export complete. Reusing the same key returns the same acceptance record.</div>}</section></aside></div>
  </div></main>;
}
