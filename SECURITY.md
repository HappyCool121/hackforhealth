# Security and synthetic-data policy

ClinicPass V2 is a hackathon prototype for provisional administrative eligibility. It is not approved for real patient data, identity verification, clinical decisions, fitness decisions, payment guarantees, or insurer reimbursement guarantees.

## Supported deployment boundary

- Use only the bundled, visibly synthetic fixtures and fictional identities.
- Keep AGNES, staff, gateway, Clinic Assist, encryption, and HMAC secrets outside Git.
- Enable `COOKIE_SECURE=true`, `CSRF_ENABLED=true`, `UPLOAD_SCAN_REQUIRED=true`, and a dedicated Fernet `ENCRYPTION_KEY` on any shared HTTPS deployment.
- Replace `UPLOAD_SCANNER=deterministic_demo` with an operational malware-scanning adapter before production use. The bundled scanner is deliberately labelled and is only a fail-closed interface demonstration.
- Run `python -m app.maintenance` on a schedule matching `RETENTION_DAYS`; the job removes retained document bytes, questionnaires, and reusable sensitive profile fields from expired terminal cases.

## Implemented controls

- Staff sessions use Secure/HttpOnly/SameSite cookies outside localhost. State-changing staff requests require a session-bound signed double-submit `X-CSRF-Token` and validate browser origin.
- Patient share links contain no reusable token. A short-lived, one-time bootstrap code is exchanged in a request body and rotated into an HttpOnly cookie.
- Login, patient access, upload, retry, and notification endpoints use database-backed fixed-window limits with HMAC-pseudonymized keys.
- Uploads are allow-listed, content-parsed, page/size-limited, randomly stored, and scanned before the worker can read them.
- Full identity values are Fernet-encrypted at rest, indexed only by keyed HMAC, and masked in routine responses. Questionnaire data never enters document-extraction prompts.
- Audit events are append-only at the application layer and linked by an HMAC integrity digest. Logs and audit details exclude document content, prompts, tokens, and full identifiers.
- Active reference-data releases are immutable. Evaluation hashes bind profile, visit, services, documents, assertions, corrections, questionnaire state, and reference version.
- Approval rejects stale evaluation, pending processing, `NEEDS_ACTION`, and unresolved findings. Only managers can apply a reasoned finding-level override. Identity, e-card, and original documents are attested separately on site.
- Clinic Assist exports are schema-validated, idempotent, narrowly authenticated, and leave the case unexported after rejection or transport failure.

## Reporting

Do not open a public issue containing patient-like data, secrets, raw uploads, or exploit payloads. Report suspected vulnerabilities privately to the repository owner and include only synthetic reproduction data.
