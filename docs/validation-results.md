# ClinicPass V2 validation results

Run date: 2026-08-15. Data: synthetic only. Submission source snapshot: demo commit `190dae0`.

| Check | Result | Evidence |
|---|---|---|
| API regression suite | 42 passed | `make test-api`; includes clean/expired/wrong-patient/wrong-clinic/unknown-code/outside-service/conflict, stale correction, roles, CSRF, scanner, attestations, schema export, and idempotency |
| API lint and types | Passed | Ruff and mypy |
| Web unit tests | 4 passed | Same-origin proxy, method forwarding, polling, status rendering |
| Web browser tests | 2 passed | Playwright 1.62.1 on desktop and mobile Chromium; simulation and in-person safety boundaries |
| Web lint, types, production build | Passed | ESLint, TypeScript, Next.js 16.3.0 optimized build |
| Mock Clinic Assist contract | 2 passed | Clinic Assist `2.0.0` health, schema validation, authentication, and idempotent replay |
| npm audit | 0 vulnerabilities | Lockfile audit after Playwright pin |
| V2 migration round trip | Passed on SQLite | `0001 → 0005 → 0004 → 0005`; CI repeats upgrade/downgrade/re-upgrade on PostgreSQL 16 |
| Deterministic V2 benchmark | 11/11 scenarios; 0 false passes on blocking set | [`clinicpass-v2-results.json`](../output/benchmark/clinicpass-v2-results.json) |
| Provenance policy | Passed in synthetic rule fixtures | Every assertion is cited or explicit `UNSUPPORTED`/`CONFLICTING`; live extraction exact-match remains unmeasured |
| Reusable prefill | 11 fields available | `general-health@1.0` and `occupational-health@1.0` definitions |
| Approval safety | Passed | Rejects Needs Action, stale/hash mismatch, pending scan/processing, inline overrides, and unresolved findings |
| On-site safety | Passed | Three distinct attestation records required before `CHECKED_IN` |
| Canonical export | Passed | Draft 2020-12 schema validation, idempotency replay, request hash/correlation/attempt storage, no exported transition on failure |
| Public export | Passed after final verification | Sanitized export script excludes private spec, secrets, caches, and Git metadata |

The benchmark scope is deliberately narrow: deterministic rule outcomes, false-pass protection, provenance state, prefill availability, and evaluation-service latency in the local synthetic environment. It does not claim live AGNES critical-field exact match, human clean/exception review time, manual correction rate, ready-before-arrival rate, or provider cost. Those require the official labelled fixture set, a reviewer study, and live billing telemetry.

Docker Desktop was unavailable during the original local V2 validation pass. The deployment source subsequently passed its PostgreSQL migration upgrade/downgrade/re-upgrade, API, Web, Playwright, Gitleaks, and public-export checks before the live Render services were updated. This submission repository repeats those checks in its own GitHub Actions workflows but is not the Render deployment source and cannot trigger a deployment. The live application is listed separately in the repository README.
