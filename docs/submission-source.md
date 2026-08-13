# ClinicPass technical submission source

This is the editable content source for the generated four-page PDF at `output/submission/01-ClinicPass-main-report.pdf`. The rendering script contains the layout-specific concise copy. An identical compatibility copy remains at `output/pdf/ClinicPass-technical-submission.pdf`.

Team name on the cover: **ClinicPass**.

## Executive summary

ClinicPass moves administrative pre-registration ahead of arrival for scheduled and walk-in primary-care visits. Patients use a clearly simulated Singpass/MyInfo handoff or manual entry, state their visit reason and document need, then photograph, upload, or select a watermarked synthetic sample. PDFs become page images and photos are normalized; AGNES receives private visual inputs together with local OCR evidence and extracts administrative facts through constrained tool calls. Six transparent rules evaluate identity details, validity, clinic restrictions, organization/package codes, supporting documents, and billing completeness. A patient who declares no documents or uncertainty can still reach staff review without a false failure. Submission issues a live queue number; clinic actions update the patient's destination in real time. Clinic staff inspect grounded evidence, resolve exceptions, and make the final administrative decision. Identity, e-card, and originals are always verified in person. The runnable Docker prototype includes responsive patient and clinic/manager Web UIs, PostgreSQL, an asynchronous worker, five tablet-ready fixtures, audit events, Mailpit notifications, mock Clinic Assist export, and a documented Microsoft Copilot Studio port. Fixture mode supports rehearsals; live AGNES errors fail visibly rather than silently substituting results. ClinicPass does not make clinical decisions or guarantee coverage.

## Claim status

Prototype claims in the PDF are backed by `docs/validation-results.md`. Operational time, accuracy, cost, and pilot-impact figures remain explicitly labelled measurement targets until the official fixture set and live AGNES key are supplied.

## Page-four AI disclosure

- **AGNES 2.0 Flash:** live classification and administrative extraction from synthetic document images.
- **OpenAI Codex:** implementation, testing, debugging, and documentation assistance.
- The team reviewed and validated generated code, model outputs, and submission claims.
- Microsoft Copilot Studio is documented as a future port and was not implemented.
- Public repository: <https://github.com/HappyCool121/hackforhealth>
