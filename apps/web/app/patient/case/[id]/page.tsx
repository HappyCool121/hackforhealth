"use client";

import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import {
  api,
  CaseRecord,
  DocumentRecord,
  documentCategoryLabel,
  documentRequirementLabel,
  prettyStatus,
  queueStatusLabel,
  visitReasonLabel,
} from "@/lib/api";

const SAMPLES = [
  { id: "chit", title: "Company medical chit", note: "Clean demo path", href: "/tablet-samples/company-medical-chit.pdf", filename: "company-medical-chit.pdf", format: "PDF" },
  { id: "referral", title: "Referral letter", note: "Specialist referral example", href: "/tablet-samples/referral-letter.pdf", filename: "referral-letter.pdf", format: "PDF" },
  { id: "hsg", title: "Healthier SG form", note: "Periodic care administration", href: "/tablet-samples/healthier-sg-form.pdf", filename: "healthier-sg-form.pdf", format: "PDF" },
  { id: "checkup", title: "Six-month check-up", note: "Contains a clinic mismatch", href: "/tablet-samples/six-month-checkup-letter.pdf", filename: "six-month-checkup-letter.pdf", format: "PDF" },
  { id: "licence", title: "Driver's licence renewal", note: "Renewal medical administration", href: "/tablet-samples/drivers-license-renewal-form.pdf", filename: "drivers-license-renewal-form.pdf", format: "PDF" },
] as const;

const SUMMARY_LABELS: Record<string, string> = {
  document_title: "Document",
  issuer: "Issued by",
  valid_from: "Valid from",
  valid_to: "Valid until",
  checkup_frequency: "Check-up frequency",
  preparation_instructions: "Preparation",
  supporting_document_note: "What to bring",
};

function Progress({ active }: { active: number }) {
  return (
    <div className="journeyProgress" aria-label={`Step ${active} of 4`}>
      {["Identity", "Visit", "Documents", "Review"].map((label, index) => (
        <div className={index + 1 <= active ? "active" : ""} key={label}>
          <span>{index + 1}</span><small>{label}</small>
        </div>
      ))}
    </div>
  );
}

function documentStatus(document: DocumentRecord) {
  if (document.status === "QUEUED") return "Queued for secure reading";
  if (document.status === "PROCESSING") return "Reading document…";
  if (document.status === "ERROR") return "Could not read document";
  return "Ready for review";
}

export default function PatientCase() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const uploadCounter = useRef(0);
  const [record, setRecord] = useState<CaseRecord | null>(null);
  const [stage, setStage] = useState<3 | 4>(3);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [uploads, setUploads] = useState<Array<{ id: string; name: string; status: "uploading" | "error"; message?: string }>>([]);
  const accessToken = search.get("token");

  const load = useCallback(async () => {
    try {
      setRecord(await api(`/patient/cases/${id}`));
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Case not found");
    }
  }, [id]);

  useEffect(() => {
    async function initialLoad() {
      if (accessToken) await api(`/patient/cases/${id}/access?token=${encodeURIComponent(accessToken)}`, { method: "POST" });
      await load();
    }
    void initialLoad();
  }, [accessToken, id, load]);

  useEffect(() => {
    const hasActiveDocument = record?.documents?.some((document) => ["QUEUED", "PROCESSING"].includes(document.status));
    const queueIsLive = Boolean(record?.queue_number) && !["CANCELLED", "COMPLETED", "EXPORTED"].includes(record?.status || "");
    if (!record || (!hasActiveDocument && !["PROCESSING", "SUBMITTED"].includes(record.status) && !queueIsLive)) return;
    const timer = setInterval(() => void load(), 1800);
    return () => clearInterval(timer);
  }, [record, load]);

  async function uploadFiles(files: File[]) {
    const accepted = files.filter((file) => file.size > 0);
    if (!accepted.length) return;
    setError("");
    for (const [index, file] of accepted.entries()) {
      uploadCounter.current += 1;
      const uploadId = `${uploadCounter.current}-${index}-${file.name}`;
      setUploads((current) => [...current, { id: uploadId, name: file.name, status: "uploading" }]);
      const form = new FormData();
      form.append("file", file);
      try {
        await api(`/patient/cases/${id}/documents`, { method: "POST", body: form });
        setUploads((current) => current.filter((item) => item.id !== uploadId));
        await load();
      } catch (reason) {
        const message = reason instanceof Error ? reason.message : "Upload failed";
        setUploads((current) => current.map((item) => item.id === uploadId ? { ...item, status: "error", message } : item));
      }
    }
    if (cameraInput.current) cameraInput.current.value = "";
    if (fileInput.current) fileInput.current.value = "";
  }

  async function uploadSample(sample: typeof SAMPLES[number]) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(sample.href);
      if (!response.ok) throw new Error("Could not load the synthetic sample");
      const blob = await response.blob();
      await uploadFiles([new File([blob], sample.filename, { type: blob.type })]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not use sample");
    } finally {
      setBusy(false);
    }
  }

  function chooseFiles(event: ChangeEvent<HTMLInputElement>) {
    void uploadFiles(Array.from(event.target.files || []));
  }

  function dropFiles(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void uploadFiles(Array.from(event.dataTransfer.files));
  }

  async function removeDocument(documentId: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/patient/cases/${id}/documents/${documentId}`, { method: "DELETE" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove document");
    } finally {
      setBusy(false);
    }
  }

  async function retryDocument(documentId: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/patient/cases/${id}/documents/${documentId}/retry`, { method: "POST" });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not retry document");
    } finally {
      setBusy(false);
    }
  }

  function continueToReview() {
    const usable = record?.documents?.some((document) => document.status !== "ERROR");
    if (record?.document_requirement === "yes" && !usable) {
      setError("You indicated documents are needed. Upload a document successfully before continuing.");
      return;
    }
    setError("");
    setStage(4);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function submitCase() {
    setBusy(true);
    setError("");
    try {
      setRecord(await api(`/patient/cases/${id}/submit`, { method: "POST" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !record) return <main className="patientJourney"><div className="alert error">{error}</div></main>;
  if (!record) return <main className="patientJourney"><div className="loading">Loading registration…</div></main>;

  const editable = ["DRAFT", "NEEDS_ACTION"].includes(record.status);
  const documents = record.documents || [];

  if (editable && stage === 3) {
    return (
      <main className="patientJourney patientUploadJourney">
        <Progress active={3} />
        <section className="panel uploadPanel">
          <span className="eyebrow">Step 3 of 4 · Supporting documents</span>
          <h1>Upload anything relevant</h1>
          <p className="uploadLead">Please upload the relevant documents (insurance medical chit, government letter for check-up, referral letter, insurance e-card, etc.).</p>
          <div className={`dropZone ${dragging ? "dragging" : ""}`} onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDragOver={(event) => event.preventDefault()} onDrop={dropFiles}>
            <span className="uploadGlyph">↑</span>
            <strong>Take a clear photo or choose files</strong>
            <p>PDF, PNG, JPEG, HEIC or HEIF · up to 10 MB · PDFs up to 6 pages</p>
            <div className="uploadButtons">
              <button className="button primary" type="button" onClick={() => cameraInput.current?.click()}>Take a photo</button>
              <button className="button secondary" type="button" onClick={() => fileInput.current?.click()}>Choose files</button>
            </div>
            <input className="srOnly" ref={cameraInput} type="file" accept="image/*" capture="environment" onChange={chooseFiles} />
            <input className="srOnly" ref={fileInput} type="file" accept=".pdf,.png,.jpg,.jpeg,.heic,.heif" multiple onChange={chooseFiles} />
            <small className="desktopDropHint">On desktop, you can also drag files here.</small>
          </div>
          <div className="captureTips"><strong>For the clearest result</strong><span>Capture the full page on a flat surface, avoid glare, and check that small text is readable.</span></div>
        </section>

        {(uploads.length > 0 || documents.length > 0) && <section className="panel"><div className="sectionHeading"><h2>Your documents</h2><span>{documents.length} received</span></div>
          {uploads.map((upload) => <div className="documentCard uploadPending" key={upload.id}><span className="docIcon">UP</span><div><strong>{upload.name}</strong><small>{upload.status === "uploading" ? "Uploading securely…" : upload.message}</small><span className={upload.status === "uploading" ? "miniProgress moving" : "miniProgress failed"} /></div></div>)}
          {documents.map((document) => <div className={`documentCard ${document.status.toLowerCase()}`} key={document.id}>
            <span className="docIcon">{document.media_type === "application/pdf" ? "PDF" : "IMG"}</span>
            <div className="documentBody">
              <div className="documentTitle"><strong>{document.filename}</strong><span className={`documentState ${document.status.toLowerCase()}`}>{documentStatus(document)}</span></div>
              <small>{document.page_count} {document.page_count === 1 ? "page" : "pages"} · {documentCategoryLabel(document.category)}</small>
              {document.processing_provider && <small className="providerLine">{document.processing_provider === "agnes" ? "Read by AGNES live image model" : "Read in deterministic fixture mode"}</small>}
              {Object.keys(document.patient_summary || {}).length > 0 && <dl className="patientExtraction">{Object.entries(document.patient_summary).map(([key, value]) => <div key={key}><dt>{SUMMARY_LABELS[key] || prettyStatus(key)}</dt><dd>{value}</dd></div>)}</dl>}
              {document.quality_warnings?.map((warning) => <small className="warning" key={warning}>{warning}</small>)}
              {document.error && <div className="inlineError">{document.error}</div>}
              <div className="documentActions">
                {document.status === "ERROR" && <button type="button" onClick={() => void retryDocument(document.id)} disabled={busy}>Retry reading</button>}
                {document.status !== "PROCESSING" && <button type="button" onClick={() => void removeDocument(document.id)} disabled={busy}>Remove</button>}
              </div>
            </div>
          </div>)}
        </section>}

        <section className="panel samplePanel">
          <div className="sectionHeading"><div><span className="eyebrow">Demo shortcut</span><h2>Try a synthetic sample</h2></div><span>Never use real patient data</span></div>
          <p className="muted">Each watermarked sample goes through the same upload and AI processing path as a camera photo. For the two-device demo, <a className="inlineLink" href="/demo/tablet-documents" target="_blank">open the tablet display</a> and photograph it with this phone.</p>
          <div className="sampleGrid">{SAMPLES.map((sample) => <article key={sample.id}><span className="sampleFormat">{sample.format}</span><div><strong>{sample.title}</strong><small>{sample.note}</small></div><button type="button" onClick={() => void uploadSample(sample)} disabled={busy}>Use sample</button><a href={sample.href} download>Download</a></article>)}</div>
        </section>

        {record.document_requirement !== "yes" && documents.length === 0 && <div className="alert info">You can continue without an upload. The clinic will review your “{record.document_requirement === "no" ? "no documents needed" : "not sure"}” declaration.</div>}
        {error && <div className="alert error" role="alert">{error}</div>}
        <button className="button primary wide journeyNext" type="button" disabled={uploads.some((upload) => upload.status === "uploading")} onClick={continueToReview}>Continue to review</button>
      </main>
    );
  }

  if (editable && stage === 4) {
    return (
      <main className="patientJourney">
        <Progress active={4} />
        <section className="panel reviewPanel">
          <span className="eyebrow">Step 4 of 4 · Review</span>
          <h1>Check before submitting</h1>
          <p className="muted">The clinic will review any model-read information. This is not an identity check or coverage decision.</p>
          <dl className="reviewSummary">
            <div><dt>Patient</dt><dd>{record.patient_name}<small>ID ••••{record.id_last4} · {record.identity_source === "singpass_demo" ? "MyInfo demo" : "Manual entry"}</small></dd></div>
            <div><dt>Visit</dt><dd>{visitReasonLabel(record.visit_reason)}<small>{record.appointment_type}{record.appointment_date ? ` · ${record.appointment_date}` : ""}</small></dd></div>
            <div><dt>Documents needed?</dt><dd>{documentRequirementLabel(record.document_requirement)}</dd></div>
            <div><dt>Documents received</dt><dd>{documents.length ? documents.map((document) => document.filename).join(", ") : "None uploaded - clinic to confirm"}</dd></div>
          </dl>
          {documents.some((document) => ["QUEUED", "PROCESSING"].includes(document.status)) && <div className="alert info">You can submit now. Secure document reading will continue in the background.</div>}
          <div className="declaration"><span>✓</span><p>I understand that clinic staff must check my original identity document, e-card, and supporting documents in person. Any package or payment interpretation is preliminary.</p></div>
          {error && <div className="alert error" role="alert">{error}</div>}
          <div className="reviewActions"><button className="button secondary" type="button" onClick={() => setStage(3)}>Back to documents</button><button className="button primary" type="button" disabled={busy} onClick={() => void submitCase()}>{busy ? "Submitting…" : "Submit for clinic review"}</button></div>
        </section>
      </main>
    );
  }

  return (
    <main className="patientJourney">
      <Progress active={4} />
      <div className="caseHeader"><div><span className="eyebrow">{record.reference}</span><h1>{prettyStatus(record.status)}</h1></div><span className={`status ${record.status.toLowerCase()}`}>{prettyStatus(record.status)}</span></div>
      {record.ai_provider === "fixture" && <div className="alert info">Demo fixture mode is active. Live judging uses the configured AGNES image model.</div>}
      {record.ai_provider === "agnes" && <div className="alert agnes"><strong>AGNES live parsing complete.</strong><br />The clinic will verify the extracted administrative details.</div>}
      {record.queue_number && <section className="queueLive" aria-live="polite"><div><span className="eyebrow">Live clinic queue</span><strong>{record.queue_number}</strong></div><div><small>{queueStatusLabel(record.queue_status)}</small><b>{record.room_assignment || "Waiting for room assignment"}</b><time>{record.queue_updated_at ? `Updated ${new Date(record.queue_updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Updates automatically"}</time></div><i aria-hidden="true" /></section>}
      {record.status === "APPROVED_FOR_CHECK_IN" && <div className="alert success"><strong>Ready for on-site check-in.</strong><br />Bring your identity document, e-card, and original supporting documents. This is not a coverage guarantee.</div>}
      {["PROCESSING", "SUBMITTED"].includes(record.status) && <div className="alert info">We are reading your document. This page updates automatically.</div>}
      {record.status === "READY_FOR_REVIEW" && <div className="alert success"><strong>Submitted for clinic review.</strong><br />Your administrative information is being checked by clinic staff.</div>}
      <section className="panel"><h2>Visit summary</h2><dl className="details patientDetails"><div><dt>Name</dt><dd>{record.patient_name}</dd></div><div><dt>Reason</dt><dd>{visitReasonLabel(record.visit_reason)}</dd></div><div><dt>Documents</dt><dd>{documentRequirementLabel(record.document_requirement)}</dd></div><div><dt>Visit</dt><dd>{record.appointment_type}{record.appointment_date ? ` · ${record.appointment_date}` : ""}</dd></div><div><dt>Clinic</dt><dd>Central Family Clinic</dd></div><div><dt>Identity entry</dt><dd>{record.identity_source === "singpass_demo" ? "MyInfo demo" : "Manual"}</dd></div></dl></section>
      <section className="panel"><h2>Supporting documents</h2>
        {documents.length === 0 && <p className="muted">No documents were uploaded. The clinic will review your declaration.</p>}
        {documents.map((document) => <div className="documentRow" key={document.id}><span className="docIcon">{document.media_type === "application/pdf" ? "PDF" : "IMG"}</span><div><strong>{document.filename}</strong><small>{documentCategoryLabel(document.category)} · {documentStatus(document)}</small>{document.quality_warnings?.map((warning) => <small className="warning" key={warning}>{warning}</small>)}</div></div>)}
      </section>
      {record.rules.length > 0 && <section className="panel"><h2>Readiness checks</h2><div className="ruleList">{record.rules.map((rule) => <div className="rule" key={rule.code}><span className={`ruleState ${rule.status.toLowerCase()}`}>{rule.status}</span><div><strong>{rule.label}</strong><small>{rule.explanation}</small></div></div>)}</div></section>}
      {error && <div className="alert error" role="alert">{error}</div>}
    </main>
  );
}
