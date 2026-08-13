# ClinicPass

ClinicPass is a pre-registration and eligibility-readiness workflow for primary-care clinics. Patients use a clearly simulated Singpass/MyInfo handoff or manual entry, state their visit reason, and photograph or upload any supporting documents before arrival. Clinic staff review evidence-backed extraction and deterministic readiness checks. It does **not** make clinical decisions, verify identity remotely, or guarantee coverage.

## Quick start

Runtime requirement: Docker Desktop with Compose v2. Local quality checks additionally use Node.js 24 and `uv`; the live demo itself does not require them.

```bash
cp .env.example .env
make up
```

Open <http://localhost:8080>. Demo staff accounts:

- Assistant: `assistant@clinicpass.test` / `DemoAssistant1!`
- Manager: `manager@clinicpass.test` / `DemoManager1!`

Mail notifications are visible at <http://localhost:8025>. API documentation is at <http://localhost:8080/api/docs>.

The default `AI_PROVIDER=fixture` gives reproducible, clearly labelled demo extraction. For a live AGNES image-understanding demo, set `AI_PROVIDER=agnes` and `AGNES_API_KEY`, then restart `api` and `worker`.

```bash
docker compose up -d --force-recreate api worker
curl -fsS http://localhost:8080/api/v1/health
make smoke-agnes
```

The patient document screen includes five watermarked synthetic PDFs. Generate them with `make demo-assets`; choosing one in the UI still sends it through the real multipart upload and worker pipeline. For the two-device demonstration, open <http://localhost:8080/demo/tablet-documents> on the tablet and use the phone's “Take a photo” action to capture the displayed form.

```bash
make test
make smoke
make demo-assets
make export-public
```

Architecture, demo flow, safety boundaries, and the Microsoft Copilot Studio port are documented in [`docs/`](docs/).

## Submission package

- [`01-ClinicPass-main-report.pdf`](output/submission/01-ClinicPass-main-report.pdf) — required main report, exactly four pages with a 191-word executive summary and AI-tool disclosure
- [`02-ClinicPass-synthetic-demo-documents.pdf`](output/submission/02-ClinicPass-synthetic-demo-documents.pdf) — five watermarked synthetic documents for the phone-camera demonstration
- [`03-ClinicPass-patient-surface.pdf`](output/submission/03-ClinicPass-patient-surface.pdf) — patient journey screenshots, including live AGNES extraction and queue/room updates
- [`04-ClinicPass-clinic-admin-surface.pdf`](output/submission/04-ClinicPass-clinic-admin-surface.pdf) — clinic queue, evidence review, approval, and check-in screenshots

The compatibility copy at [`output/pdf/ClinicPass-technical-submission.pdf`](output/pdf/ClinicPass-technical-submission.pdf) contains the same four-page main report.

## Repository layout

```text
apps/web/                 Patient and clinic/admin Web UI
services/api/             API, worker, rules, OCR, and AGNES adapter
services/mock-clinic-assist/
docs/                     Architecture, demo and Copilot port
fixtures/                 Synthetic-only demo documents
scripts/                  Validation and public export tooling
submission-public/        Locally generated sanitized judging copy (source-workspace only)
```

## Data statement

Only synthetic demonstration data belongs in this repository. Never enter real patient data. See [`SECURITY.md`](SECURITY.md).
