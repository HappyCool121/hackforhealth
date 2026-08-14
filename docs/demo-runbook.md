# ClinicPass V2 demo runbook

Use only fictional identities and bundled watermarked documents. Warm the Web, core, and mock services before the demo. Confirm `/api/v1/health` reports the intended extraction provider and the mock `/health` reports schema `2.0.0`.

## Clean path

1. On the phone, use the clearly labelled Singpass/MyInfo simulation. Point out that no real identity service is contacted.
2. Confirm the prefilled reusable profile and scheduled visit. Select `BASIC_SCREEN` and optionally `CBC`.
3. Complete `general-health@1.0`; call out the 11 explicitly confirmed prefilled fields instead of re-entry.
4. Photograph or upload the synthetic company medical chit. Show scan state, queued processing, field support, and no uncalibrated confidence percentage.
5. Review and submit. Keep the patient queue page open.
6. On clinic desktop, show the active immutable reference version and 11 deterministic findings. Describe the outcome as provisional administrative eligibility only.
7. In the two-pane evidence workspace, select a field to show its page/evidence IDs and bounding box. Make a harmless correction only in the exception demo, because corrections preserve the original and stale eligibility.
8. Approve only when the server unlocks the button: `READY_FOR_REVIEW`, fresh matching input hash, no active processing, and no unresolved finding.
9. On arrival, record identity document, e-card, and original supporting documents as three separate attestations. Show that check-in occurs only after the third.
10. Export with the Clinic Assist V2 action. Explain JSON Schema validation and idempotent replay; the mock is not a real Clinic Assist connection.

## Exception paths

- Use the six-month check-up fixture for a wrong-clinic block. Approval from `NEEDS_ACTION` is prohibited; update/resubmit before any decision.
- Use an unknown package or outside service to demonstrate that non-empty strings cannot pass reference validation.
- As an assistant, request an override for one finding. As a manager, apply that finding-level override with a reason; show that other findings remain unresolved.
- Correct a field beside its original document and show that evaluation becomes stale and refreshes before approval.
- Submit no document with a `no`/`unsure` declaration to demonstrate `REVIEW_REQUIRED`, not manufactured eligibility.
- Reuse the same export idempotency key and show the same acceptance reference.

## Boundaries to say aloud

ClinicPass does not remotely verify identity or e-cards, make clinical or fitness decisions, connect to real Singpass/payers/Clinic Assist/NEHR, guarantee reimbursement, or determine the final patient-payable amount. Staff sight originals on site, and all repository/demo data is synthetic.
