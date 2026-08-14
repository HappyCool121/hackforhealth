# ClinicPass technical submission source

This is the editable content source for the generated four-page PDF at `output/submission/01-ClinicPass-main-report.pdf`. The rendering script contains the layout-specific concise copy. An identical compatibility copy remains at `output/pdf/ClinicPass-technical-submission.pdf`.

Team name on the cover: **ClinicPass**.

## Executive summary

ClinicPass V2 moves provisional administrative eligibility and pre-registration ahead of arrival. Patients use a clearly simulated identity handoff or manual entry, confirm a reusable masked profile, complete a versioned General or Occupational Health questionnaire, choose requested services, and upload watermarked synthetic evidence. AGNES or the labelled fixture provider extracts administrative facts into field assertions with page evidence and bounding boxes. Eleven deterministic rules compare identity, validity, issuer, organisation, package, panel clinic, service coverage, supporting documents, billing route, and conflicts against immutable synthetic reference releases. Outcomes are provisional, review-required, or blocked—never guaranteed coverage. Staff review the original beside extracted fields, preserve audited corrections, and request finding-level manager overrides. Approval is rejected for stale inputs, active processing, Needs Action, or unresolved findings. Identity, e-card, and originals are attested separately on site. A schema-validating, idempotent Clinic Assist V2 mock receives the masked profile, visit, questionnaire, eligibility, service, evidence, review, correction, override, and attestation records. ClinicPass does not make clinical, fitness, remote identity, reimbursement, or final-payment decisions.

## Claim status

Prototype claims in the PDF are backed by `docs/validation-results.md`. The checked-in synthetic benchmark reports deterministic rule/provenance outcomes only. Live extraction accuracy, human review time, correction rate, ready-before-arrival rate, and provider cost remain explicitly unmeasured until the official labelled fixture set, reviewer study, and live provider billing data are supplied.

## Page-four AI disclosure

- **AGNES 2.0 Flash:** live classification and administrative extraction from synthetic document images.
- **OpenAI Codex:** implementation, testing, debugging, and documentation assistance.
- The team reviewed and validated generated code, model outputs, and submission claims.
- Microsoft Copilot Studio is documented as a future port and was not implemented.
- Public repository: <https://github.com/HappyCool121/hackforhealth>

## Required owner metadata before final submission

The repository owner must supply the institution, member names, and contact person. These values are not inferable from the source and must not be fabricated.
