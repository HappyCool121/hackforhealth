"use client";

import { useState } from "react";

const DOCUMENTS = [
  { title: "Company medical chit", file: "company-medical-chit.pdf" },
  { title: "Referral letter", file: "referral-letter.pdf" },
  { title: "Healthier SG form", file: "healthier-sg-form.pdf" },
  { title: "Six-month check-up", file: "six-month-checkup-letter.pdf" },
  { title: "Driver's licence renewal", file: "drivers-license-renewal-form.pdf" },
] as const;

export default function TabletDocuments() {
  const [selected, setSelected] = useState(0);
  const document = DOCUMENTS[selected];
  const href = `/tablet-samples/${document.file}#toolbar=0&navpanes=0&scrollbar=0&view=FitH`;

  return (
    <main className="tabletDemo">
      <header>
        <div><span className="eyebrow">Two-device OCR demo</span><h1>Synthetic document display</h1></div>
        <p>Show this page on the tablet. Use the patient flow on your phone, tap <strong>Take a photo</strong>, and capture the displayed form.</p>
      </header>
      <nav aria-label="Synthetic documents">
        {DOCUMENTS.map((item, index) => <button className={selected === index ? "active" : ""} key={item.file} onClick={() => setSelected(index)}><span>{index + 1}</span>{item.title}</button>)}
      </nav>
      <section className="tabletViewer">
        <div className="tabletViewerTitle"><div><span>Synthetic form {selected + 1} of {DOCUMENTS.length}</span><strong>{document.title}</strong></div><a href={`/tablet-samples/${document.file}`} target="_blank">Open full screen</a></div>
        <object key={document.file} data={href} type="application/pdf" aria-label={document.title}><a href={`/tablet-samples/${document.file}`}>Open {document.title}</a></object>
      </section>
      <footer><strong>SYNTHETIC DEMO ONLY</strong> No real identity, entitlement, licence, insurer, or government document is represented.</footer>
    </main>
  );
}
