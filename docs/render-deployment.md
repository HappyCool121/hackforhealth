# Live demo deployment context

The public ClinicPass V2 application runs separately on Render at <https://clinicpass-demo-happycool121-web.onrender.com>. This document describes that live topology for submission reviewers; it is not a deployment handoff.

`HappyCool121/hackforhealth` is a sanitized public submission repository. It intentionally excludes `render.yaml`, deployment state, credentials, and private operational notes. It is not connected to the Render Blueprint, so commits and GitHub Actions runs in this repository cannot deploy, redeploy, roll back, or otherwise change the live application.

## Live topology

- A public Next.js service provides the desktop clinic and mobile patient surfaces.
- A protected core service runs FastAPI and the asynchronous worker. Browser API requests use the Next.js same-origin gateway; the browser does not receive service-to-service credentials.
- A protected synthetic mock receives Clinic Assist `2.0.0` exports and validates them against the published JSON Schema.
- PostgreSQL stores synthetic workflow state and queued document bytes.

The deployed environment uses server-side secrets and hides seeded staff credentials from the public login page. No credentials or deployment-control values are included in this repository.

## Reviewer verification

1. Open the live Web URL and use only fictional identities and bundled watermarked documents.
2. Confirm the UI labels simulated identity, fixture extraction, and provisional administrative outcomes accurately.
3. Complete the clean and exception paths in [`demo-runbook.md`](demo-runbook.md).
4. Confirm identity, e-card, and original-document checks remain separate on-site actions.
5. Confirm Clinic Assist is presented as a schema-validating mock, not a production integration.

Free Render services may need time to wake after an idle period. Any operational deployment change belongs to the separate private deployment workflow and is outside this submission repository.
