"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import ClinicNav from "@/components/ClinicNav";
import {
  api,
  CaseRecord,
  DocumentRecord,
  documentCategoryLabel,
  documentRequirementLabel,
  prettyStatus,
  visitReasonLabel,
} from "@/lib/api";

type User = { role: string };

export default function CaseWorkspace() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [user, setUser] = useState<User>();
  const [record, setRecord] = useState<CaseRecord>();
  const [selected, setSelected] = useState<DocumentRecord>();
  const [error, setError] = useState("");
  const [reason, setReason] = useState("Please provide a clearer or current supporting document.");

  const load = useCallback(async () => {
    try {
      setUser(await api("/auth/me"));
      const item = await api<CaseRecord>(`/clinic/cases/${id}`);
      setRecord(item);
      setSelected((current) => item.documents?.find((document) => document.id === current?.id) || item.documents?.[0]);
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

  async function decision(action: "request_information" | "approve" | "cancel", override = false) {
    try {
      setRecord(await api(`/clinic/cases/${id}/review`, {
        method: "POST",
        body: JSON.stringify({ action, reason, override_failures: override }),
      }));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Action failed");
    }
  }

  async function checkIn() {
    try {
      setRecord(await api(`/clinic/cases/${id}/check-in`, {
        method: "POST",
        body: JSON.stringify({ identity_checked_on_site: true, ecard_checked_on_site: true, originals_checked_on_site: true }),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Check-in failed");
    }
  }

  async function exportCase() {
    try {
      const result = await api<{ case: CaseRecord }>(`/clinic/cases/${id}/export`, { method: "POST" });
      setRecord(result.case);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Export failed");
    }
  }

  if (!record) return <main className="clinicShell"><ClinicNav role={user?.role} /><div className="workspace"><div className="loading">Loading case…</div>{error}</div></main>;
  const hasFailure = record.rules.some((rule) => rule.status === "FAIL");

  return (
    <main className="clinicShell">
      <ClinicNav role={user?.role} />
      <div className="workspace">
        <header className="workspaceHeader"><div><button className="back" onClick={() => router.push("/clinic/queue")}>← Review queue</button><h1>{record.patient_name}</h1><p>{record.reference} · ID ••••{record.id_last4}</p></div><span className={`status ${record.status.toLowerCase()}`}>{prettyStatus(record.status)}</span></header>
        {record.ai_provider === "fixture" && <div className="alert info">Fixture AI mode is active. Results below are deterministic - not a live AGNES response.</div>}
        {record.ai_provider === "agnes" && <div className="alert agnes">Documents were parsed by the live AGNES image model. Confirm every administrative fact against the grounded evidence.</div>}
        {error && <div className="alert error">{error}</div>}
        <div className="caseGrid">
          <div>
            <section className="panel"><h2>Patient and visit</h2><dl className="details clinicIntakeDetails"><div><dt>Reason</dt><dd>{visitReasonLabel(record.visit_reason)}</dd></div><div><dt>Visit type</dt><dd>{record.appointment_type}{record.appointment_date ? ` · ${record.appointment_date}` : ""}</dd></div><div><dt>Document declaration</dt><dd>{documentRequirementLabel(record.document_requirement)}</dd></div><div><dt>Identity entry</dt><dd>{record.identity_source === "singpass_demo" ? "Simulated Singpass/MyInfo" : "Manual entry"}</dd></div><div><dt>Live queue</dt><dd>{record.queue_number || "Not issued"}</dd></div><div><dt>Patient destination</dt><dd>{record.room_assignment || "Not assigned"}</dd></div></dl><p className="privacyNote">Identity and e-card have not been verified online. Complete the physical checks at arrival.</p></section>
            <section className="panel"><h2>Readiness checks</h2><div className="ruleList">{record.rules.length === 0 && <p className="muted">Checks will appear after submission and document processing.</p>}{record.rules.map((rule) => <div className="rule" key={rule.code}><span className={`ruleState ${rule.status.toLowerCase()}`}>{rule.status}</span><div><strong>{rule.label}</strong><small>{rule.explanation}</small></div></div>)}</div></section>
            <section className="panel"><h2>Documents and extraction</h2>
              {!record.documents?.length && <div className="emptyDocumentState"><strong>No document uploaded</strong><span>The patient declared “{record.document_requirement}”. Confirm whether supporting evidence is required.</span></div>}
              <div className="docTabs">{record.documents?.map((document) => <button className={selected?.id === document.id ? "active" : ""} onClick={() => setSelected(document)} key={document.id}>{document.filename}</button>)}</div>
              {selected && <><div className="selectedDocumentMeta"><span>{documentCategoryLabel(selected.category)}</span><span>{prettyStatus(selected.status)}</span><span>{selected.processing_provider === "agnes" ? "AGNES live" : "Fixture model"}</span></div><dl className="extraction">{Object.entries(selected.extracted_data || {}).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value || <em>Not found</em>}</dd></div>)}</dl><h3>Grounded OCR evidence</h3><div className="evidenceList">{selected.evidence?.map((item) => <div key={item.evidence_id}><b>Page {item.page}</b><span>{item.text}</span><small>{item.evidence_id}</small></div>)}</div></>}
            </section>
          </div>
          <aside><section className="panel sticky"><h2>Staff decision</h2><p className="muted">AI extraction supports your review. You make the administrative decision.</p>{["READY_FOR_REVIEW", "NEEDS_ACTION", "PROCESSING"].includes(record.status) && <><label>Decision note<textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label><button className="button secondary wide" onClick={() => void decision("request_information")}>Request information</button><button className="button primary wide" onClick={() => void decision("approve", hasFailure)} disabled={record.status === "PROCESSING"}>Approve for check-in{hasFailure ? " with override" : ""}</button></>}{record.status === "APPROVED_FOR_CHECK_IN" && <><div className="checklist"><span>✓ Identity checked in person</span><span>✓ E-card checked in person</span><span>✓ Originals sighted</span></div><button className="button primary wide" onClick={() => void checkIn()}>Confirm all and check in</button></>}{record.status === "CHECKED_IN" && <button className="button primary wide" onClick={() => void exportCase()}>Export to mock Clinic Assist</button>}{["EXPORTED", "COMPLETED"].includes(record.status) && <div className="alert success">Workflow complete. The audit record contains the export reference.</div>}</section></aside>
        </div>
      </div>
    </main>
  );
}
