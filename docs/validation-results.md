# Validation results

Run date: 2026-08-13. Data: synthetic only.

| Check | Result | Evidence |
|---|---|---|
| API tests | 21 passed | `make test-api` (`uv run --extra dev pytest -q`) |
| API lint and types | Passed | Ruff and mypy |
| Web unit tests | 1 passed | Node test runner |
| Web lint and types | Passed | ESLint and TypeScript |
| Production Web build | Passed | Next.js 16.3.0 production build |
| Dependency audit | 0 npm vulnerabilities | `npm audit` after lock update |
| Browser live-AGNES journey | Passed | Simulated Singpass/MyInfo, sample upload, live visual extraction, submit, staff approve, check in, mock export |
| Browser documentless journey | Passed | `no` declaration reached `READY_FOR_REVIEW`; supporting-document checks remained `REVIEW`, never `FAIL` |
| Live queue and room journey | Passed | Submission issued a queue number; staff approval updated the patient phone to Registration Counter 2; check-in updated it to Consultation Room 3 without reloading |
| Tablet document gallery | Passed | Five selectors and embedded full-size PDFs exercised at 1024 x 768 px; driver's-licence renewal selected successfully |
| Manager journey | Passed | Role-gated metrics, reference data, audit trail |
| Responsive width | Passed | Patient identity, intake, document, review, and status screens exercised at a 390 x 844 px viewport |
| Public export | Passed | Sanitization checks, lockfiles present, private spec and secrets absent |
| Database migration | Passed | Alembic upgraded PostgreSQL through `0003_live_queue_and_room` |
| Synthetic tablet forms | Passed | Five one-page watermarked PDFs rendered and visually inspected, including driver's-licence renewal |
| Compose definition | Passed | `docker compose config --quiet` |
| Full Docker boot | Passed | PostgreSQL healthy; migration exited successfully; API healthy; worker, Web, gateway, Mailpit, and mock Clinic Assist started |
| Fixture smoke | Passed | `make smoke` through `http://localhost:8080` |
| Live AGNES vision call | Passed | `make smoke-agnes` classified the watermarked synthetic image as `medical_chit` and extracted Jamie Tan |
| Browser console | Passed | 0 errors and 0 warnings after both end-to-end patient paths |

Operational accuracy, task-time, cost-per-case, ready-before-arrival, duplicate-entry, and false-pass metrics are not claimed yet. Populate them only after running the official labelled fixture set with the live endpoint.
