# ClinicPass

ClinicPass V2 is a provisional administrative eligibility and pre-registration workflow for primary-care clinics. It combines reusable patient profiles and versioned questionnaires with field-cited document extraction, versioned synthetic payer/package reference data, 11 deterministic eligibility rules, audited staff corrections, manager-only finding overrides, separate on-site attestations, and a canonical Clinic Assist V2 export. It does **not** make clinical decisions, verify identity or e-cards remotely, guarantee coverage, reimbursement, or the final patient-payable amount.

## Quick start

Runtime requirement: Docker Desktop with Compose v2. Local quality checks additionally use Node.js 24 and `uv`; the live demo itself does not require them.

```bash
cp .env.example .env
# Set the blank password and secret fields in .env before starting.
make up
```

Open <http://localhost:8080>. Demo staff accounts:

- Assistant: `assistant@clinicpass.test`
- Manager: `manager@clinicpass.test`

Set both staff passwords and all blank secret values locally in `.env`; credentials are intentionally not committed.

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
make benchmark-v2
make smoke
make demo-assets
make export-public
```

## Public submission and live demo

This repository, [`HappyCool121/hackforhealth`](https://github.com/HappyCool121/hackforhealth), is the sanitized public submission snapshot. The live Render application is available separately at <https://clinicpass-demo-happycool121-web.onrender.com>.

This repository is **not** the Render deployment source. Commits and GitHub Actions runs here do not trigger or modify the live application, its services, its database, or its deployment configuration.

See [`docs/demo-runbook.md`](docs/demo-runbook.md) for the synthetic-data demonstration flow and [`docs/render-deployment.md`](docs/render-deployment.md) for a non-operational description of the live topology. Architecture, safety boundaries, and the Microsoft Copilot Studio port are documented in [`docs/`](docs/).

## Rollout and rollback

The live application is deployed from the separate `clinicpass-demo` repository. Migration `0005_clinicpass_v2` in this submission preserves existing synthetic records and can be downgraded to `0004_durable_document_content`. Deployment rollback commits, branches, and feature flags belong to that separate deployment source; this repository cannot initiate a rollback or redeploy.

The step-by-step procedure is in [`docs/rollback.md`](docs/rollback.md).

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
.github/workflows/        Migration, API/Web, browser, secret, and public-export CI
```

## Data statement

Only synthetic demonstration data belongs in this repository. Never enter real patient data. See [`SECURITY.md`](SECURITY.md).
