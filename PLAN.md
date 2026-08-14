# Plan: ClinicPass evidence-backed administrative pre-check refinement

## Goal

Move ClinicPass from a document-readiness demonstration to a synthetic-only, evidence-backed administrative eligibility and registration pre-processing prototype. The P0 implementation must let a patient enter registration data once, complete one required questionnaire before arrival, submit supporting evidence, receive deterministic reference-backed pre-checks, and pass a complete reviewed record to mock Clinic Assist without duplicate entry. Staff retain every approval decision, and identity, e-card, and original-document checks remain on site.

## Context

The current repository already provides a strong vertical slice: responsive patient and clinic surfaces, asynchronous document processing, OCR plus AGNES extraction, evidence identifiers, six deterministic readiness checks, documentless review, role-gated staff access, audit events, live queue updates, individual synthetic fixtures, and a mock Clinic Assist call.

The highest-priority gaps are administrative rather than additional AI capability:

- `Case` stores only a narrow patient and visit record.
- Extracted fields from multiple documents are merged by overwriting earlier values.
- Identity passes when any name or identifier suffix is present instead of being compared with registration data.
- Organisation and package checks test presence rather than a versioned relationship.
- Rule results are stored as a mutable JSON array rather than assessment history.
- Questionnaires and persisted consent records are absent.
- Overrides use one Boolean flag, and the UI confirms all on-site checks in one action.
- The mock Clinic Assist export contains too little data to demonstrate elimination of re-entry.
- Existing validation does not yet claim operational accuracy, task-time, cost, ready-before-arrival, or false-pass results.

P0 is a ten-working-day refinement programme. P1 and P2 work is explicitly deferred to `## Follow-up Work` so the critical path remains reviewable and achievable.

## Research Summary

- Repository inspection on 2026-08-14 confirmed FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Next.js 16.3, and React 19. Existing architecture and validation documentation support preserving the current provider seams and state guards rather than performing a rewrite.
- Microsoft currently documents REST API tools for Copilot Studio using an OpenAPI v2 JSON definition, and the feature remains preview functionality. P0 will preserve the existing facade; typed expansion is P1 and must be revalidated against [Microsoft's current documentation](https://learn.microsoft.com/en-sg/microsoft-copilot-studio/agent-extend-action-rest-api) before implementation.
- Singapore's PDPC identifies consent, purpose limitation, notification, accuracy, protection, retention limitation, transfer limitation, access/correction, breach notification, and accountability among the applicable data-protection obligations. P0 will implement demonstrable consent, masking, withdrawal-before-export, access control, audit, and deletion controls, while leaving production retention periods to sponsor and legal approval. See [PDPC data-protection obligations](https://www.pdpc.gov.sg/overview-of-pdpa/the-legislation/personal-data-protection-act/data-protection-obligations).
- SQLAlchemy's official examples distinguish mutable current rows from explicit history/version rows. ClinicPass will use explicit assessment and export records so past decisions remain queryable rather than adopting an opaque versioning helper. See [SQLAlchemy ORM examples](https://docs.sqlalchemy.org/20/orm/examples.html).
- The supplied refinement brief and local challenge specifications establish the judging priorities, synthetic scenarios, questionnaire requirements, and submission constraints. They do not establish production Clinic Assist, insurer, TPA, Singpass/MyInfo, retention, or authoritative coverage interfaces; those remain dependencies and must not be represented as implemented facts.

## Constraints

- Use synthetic data only. Never commit real patient, payer, employer, or clinic information.
- Preserve asynchronous processing, evidence-grounded extraction, visible AGNES-versus-fixture mode, documentless review, staff decision authority, audit events, and live queue updates.
- AI may classify and extract administrative facts but may not approve a case, change reference rules, make clinical recommendations, remotely verify identity, or guarantee coverage.
- Preserve the existing case lifecycle and public routes until replacement behavior is implemented, tested, and documented. Add a separate assessment status rather than overloading `Case.status`.
- Prefer additive migrations and compatibility adapters. Existing synthetic cases must remain readable.
- Keep the first implementation small, reviewable, and reversible. Avoid a broad rewrite of `services/api/app/main.py`; extract only domain logic needed for independent tests.
- Use versioned JSON for the initial eligibility and questionnaire catalogues so P0 introduces no new runtime dependency.
- Keep full synthetic identifiers out of ordinary logs, queues, notifications, model prompts unless strictly required, and non-detailed staff views.
- Preserve the four-page main-report limit and classify every quantitative statement as measured result, proposed target, or sourced baseline.
- Do not include hidden helper metadata, branded administrative sections, or private source-material text in public artifacts.

## Out of Scope

- A production Clinic Assist, insurer, TPA, Singpass/MyInfo, CHAS, e-card, NEHR, or payment integration.
- Autonomous eligibility or coverage decisions, clinical interpretation, diagnosis, treatment, or claim adjudication.
- Occupational Health questionnaire implementation in P0; its schema and journey are P1.
- A second TPA export adapter, Copilot Studio action expansion, reference-rule administration UI, or production retention scheduler in P0.
- Multi-tenant configuration, multi-language support, formal high availability, load testing, managed-cloud deployment, or real notification delivery.
- Unrelated UI redesigns, dependency upgrades, module renames, or opportunistic cleanup.

## Reversibility

- Add new tables and columns before changing reads; keep legacy `Case` fields and current routes available during the migration.
- Backfill only synthetic records, record the migration behavior in tests, and retain a read fallback until the new profile path passes regression tests.
- Store every eligibility run as a new immutable assessment record; never rewrite a prior outcome.
- Add candidate-level extraction provenance before removing the current resolved dictionary.
- Keep commits aligned to Steps A-E so each subsystem can be reverted independently.
- Do not delete existing helpers, response fields, or lifecycle states until replacement behavior has explicit coverage and all first-party consumers have migrated.
- Document any irreversible schema or data-retention action before execution. P0 should contain none.

---

## Step A: Establish the safety and judging baseline

### Status

`todo`

### Objective

Create the traceability and failing-test baseline that defines P0 safety, judging coverage, and measurable acceptance before implementation begins.

### Tasks

- [ ] Create `docs/judging-traceability.md` mapping each judging requirement to a product capability, code path, automated test, demo step, and report page.
- [ ] Create `docs/governance-and-risk-register.md` covering wrong-patient evidence, hallucinated packages, prompt injection, unauthorised disclosure, consent, retention, provider outage, and export duplication.
- [ ] Add failing rule tests for wrong name, wrong identifier, cross-document identity conflict, expired evidence, package ownership mismatch, age, clinic, uncovered service, missing supporting evidence, and unresolved billing.
- [ ] Add failing AI tests for unknown evidence identifiers, unsupported critical fields, prompt-like document instructions, malformed tool output, and provider outage without fixture fallback.
- [ ] Add failing access and workflow tests for missing consent, cross-clinic access, non-overridable identity mismatch, and repeated export.
- [ ] Record baseline timing events already available and identify the missing timestamps required to measure patient completion, staff review, processing, correction, and export.
- [ ] Update submission verification requirements for team metadata, required headings, exactly four pages, and an executive summary of no more than 200 words.

### Relevant Files

- `services/api/tests/`
- `scripts/verify-submission.py`
- `docs/validation-results.md`
- `docs/submission-source.md`

### Expected Changes

- create: `docs/judging-traceability.md`
- create: `docs/governance-and-risk-register.md`
- modify: targeted API, AI, rule, access, and submission-verification tests

### Do Not Modify

- Production behavior before the failing cases and expected outcomes are documented.
- Existing evidence, provider-failure, documentless-review, queue, and clinic-isolation expectations.
- Generated submission PDFs during this step.

### Commands

```bash
cd services/api
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest -q tests/test_rules.py tests/test_ai.py tests/test_api.py
cd ../..
python3 scripts/verify-submission.py
```

### Acceptance Criteria

- [ ] Every P0 requirement has a code, test, demo, and report mapping.
- [ ] All critical false-pass scenarios have an explicit expected `PRECHECK_BLOCKED` outcome.
- [ ] Unknown or incomplete non-critical data routes to `STAFF_REVIEW_REQUIRED`, not a false pass.
- [ ] A documentless `no` or `unsure` declaration remains reviewable.
- [ ] The risk register assigns a control, owner, residual risk, and test to each material risk.
- [ ] Submission verification detects missing mandatory metadata and invalid report length.
- [ ] Existing passing tests remain unchanged except where the new contract intentionally supersedes them.

### Validation Results

- `pytest` targeted baseline: not run
- `scripts/verify-submission.py`: not run

### Findings / Notes

- The new tests are expected to fail until Steps B-D implement the required behavior. Keep that failure list explicit rather than weakening assertions.

---

## Step B: Add canonical data, reference catalogues, and eligibility v2

### Status

`todo`

### Objective

Introduce an additive domain model and deterministic assessment engine that compares registered facts, document evidence, and versioned reference expectations without silently losing provenance.

### Tasks

- [ ] Add an Alembic migration and SQLAlchemy models for `PatientProfile`, `PayerOrganisation`, `PackageDefinition`, `EligibilityAssessment`, `QuestionnaireResponse`, `ConsentRecord`, `OnsiteCheck`, and `IntegrationExport`.
- [ ] Keep current `Case` fields during P0, create a one-to-one profile for new cases, and backfill existing synthetic cases with masked/partial values where full data does not exist.
- [ ] Define `RuleOutcome` with `code`, `label`, `status`, `severity`, `observed_value`, `expected_value`, `explanation`, and evidence references.
- [ ] Keep `Case.status` as the workflow lifecycle and add assessment statuses `PRECHECK_CLEAR`, `STAFF_REVIEW_REQUIRED`, and `PRECHECK_BLOCKED`.
- [ ] Use rule statuses `PASS`, `REVIEW`, `BLOCK`, and `ONSITE_REQUIRED`; remove `FAIL` only after the UI and all tests consume the new contract.
- [ ] Create `services/api/app/reference_data/eligibility_catalogue.v1.json` with schema version, source/version metadata, effective dates, and at least three synthetic organisations or schemes and five package/examination definitions.
- [ ] Seed and validate the BLPHS/WELL2, MOL0199VME/PEE226, and EVWPA scenarios described in the supplied synthetic material.
- [ ] Add `reference_data.py` for catalogue loading/validation and `eligibility.py` for independently tested rules; do not embed catalogue facts in AI prompts.
- [ ] Store all candidate values with document and evidence provenance, then resolve a selected value with rationale and conflict status.
- [ ] Implement identity, cross-document identity, validity, recognised issuer, package ownership, age, visit purpose, clinic, service coverage, supporting-document, billing, questionnaire, and on-site requirement rules.
- [ ] Persist each assessment with rule-set and reference-data versions instead of replacing `Case.rules`; keep a compatibility projection for existing clients during P0.

### Relevant Files

- `services/api/app/models.py`
- `services/api/app/schemas.py`
- `services/api/app/rules.py`
- `services/api/app/migrations/versions/`
- `services/api/tests/`

### Expected Changes

- create: additive migration `0004` for canonical registration and assessment records
- create: `services/api/app/reference_data.py`
- create: `services/api/app/reference_data/eligibility_catalogue.v1.json`
- create: `services/api/app/eligibility.py`
- modify: models, schemas, processing, rule compatibility layer, and focused tests

### Do Not Modify

- AI provider authority or prompts to include eligibility decisions.
- Existing case lifecycle states, patient queue behavior, or clinic scoping.
- Historical assessments after creation.
- Dependency manifests unless a demonstrated blocker is recorded first.

### Commands

```bash
cd services/api
UV_CACHE_DIR=.uv-cache uv run --extra dev alembic upgrade head
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest -q tests/test_rules.py tests/test_api.py
UV_CACHE_DIR=.uv-cache uv run --extra dev ruff check app tests
UV_CACHE_DIR=.uv-cache uv run --extra dev mypy app
```

### Acceptance Criteria

- [ ] Registration can represent every core field in the supplied synthetic patient fixture.
- [ ] At least three schemes and five package/examination definitions have effective dates and version metadata.
- [ ] Unknown package relationships, wrong-patient evidence, and expired documents never produce `PASS` or `PRECHECK_CLEAR`.
- [ ] Critical conflicting fields are retained, visible, and never overwritten silently.
- [ ] Every outcome identifies observed value, expected value, explanation, and supporting evidence or an explicit unsupported state.
- [ ] Assessment history and the rule/reference versions used for each run are queryable.
- [ ] Existing synthetic cases remain readable after migration.
- [ ] The documentless review path and existing queue transitions still pass.

### Validation Results

- Alembic upgrade: not run
- API rule and migration tests: not run
- Ruff and mypy: not run

### Findings / Notes

- JSON is the selected P0 catalogue format because it is reviewable and supported without adding a parser dependency.
- The current mutable `Case.rules` field remains only as a transitional response projection; the new assessment table is authoritative.

---

## Step C: Complete registration, grounded extraction, questionnaire, and consent

### Status

`todo`

### Objective

Let patients enter a complete synthetic registration record once, reuse it across the journey, complete the General Health questionnaire, and provide explicit versioned consent before live AI processing or submission.

### Tasks

- [ ] Expand `CaseCreate` and `CasePatch` compatibly with identity type and full synthetic identifier, masked identifier, date of birth, sex, nationality, address, postal code, phone numbers, email, and declared drug allergies.
- [ ] Keep the existing flat request fields temporarily while mapping them to `PatientProfile`; document their deprecation rather than removing them in P0.
- [ ] Expand the extraction schema for issuer, organisation, policy/contract/certificate, patient identity and DOB, appointment, package/examination code, services, add-ons, validity, clinic, payer, billing, employer/agency, preparation, originals, and transferability.
- [ ] Store `raw_extraction`, `validated_extraction`, candidate provenance, and resolved case fields separately.
- [ ] Require valid evidence references for critical extracted fields and mark missing support as `UNSUPPORTED`; distinguish OCR evidence from visual-only evidence.
- [ ] Preserve page and bounding-box information so staff can navigate to the supporting source region.
- [ ] Add a versioned JSON schema for the General Health questionnaire with demographics, medical history, medication/allergies, family history, lifestyle, pain, conditional questions, acknowledgement, signature, and permitted non-disclosure choices.
- [ ] Add authenticated patient endpoints to load the required questionnaire, autosave a draft, submit a signed response, and retrieve completion status.
- [ ] Add distinct `ConsentRecord` entries for registration collection, questionnaire storage, external AI processing, clinic disclosure, applicable payer/employer disclosure, and clinic-system export.
- [ ] Block live AI processing without its applicable active consent and block final submission without required questionnaire consent/signature.
- [ ] Replace query-string bearer-token persistence with a one-time exchange followed by an HTTP-only cookie; remove the exchange code from browser history immediately.
- [ ] Use secure cookies outside local development and add CSRF protection to state-changing browser requests.
- [ ] Update the mobile-first patient journey to registration, visit/payer, documents, pre-check, questionnaire, and consent/final review with section progress, autosave, and resume.
- [ ] Audit patient corrections to prefilled values without exposing questionnaire answers on queue/list screens.

### Relevant Files

- `services/api/app/ai.py`
- `services/api/app/main.py`
- `services/api/app/processing.py`
- `apps/web/app/patient/`
- `apps/web/lib/api.ts`

### Expected Changes

- create: `services/api/app/questionnaires.py`
- create: `services/api/app/questionnaires/general_health.v1.json`
- modify: extraction schemas, patient APIs, authentication flow, patient UI, shared Web types, and tests

### Do Not Modify

- Identity wording that clearly labels Singpass/MyInfo as simulated and requires on-site verification.
- AI prompts to request a final eligibility, coverage, or clinical decision.
- Patient-safe language to expose internal severity scores or unsupported coverage claims.
- Occupational Health questionnaire behavior in P0.

### Commands

```bash
cd services/api
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest -q tests/test_ai.py tests/test_api.py
cd ../../apps/web
npm test
npm run lint
npm run typecheck
npm run build
```

### Acceptance Criteria

- [ ] Registration data is entered once and reused in questionnaire, assessment, staff review, and export.
- [ ] Every critical extracted value is supported by a valid evidence reference or marked unsupported.
- [ ] Prompt-like document text cannot alter tool selection, reference data, workflow status, or approval.
- [ ] Live provider failure remains visible and never silently substitutes fixture output.
- [ ] The General Health questionnaire autosaves, resumes, applies conditional behavior, and works at the existing 390-by-844 mobile test size.
- [ ] Submission is blocked when required consent, signature, or questionnaire completion is absent.
- [ ] Consent type, text version, purpose, actor, and timestamp are persisted.
- [ ] Patient changes to prefilled fields are auditable.
- [ ] Queue and general staff-list responses contain no questionnaire answers or full identifiers.

### Validation Results

- API and AI tests: not run
- Web tests, lint, typecheck, and production build: not run
- Mobile browser journey: not run

### Findings / Notes

- General Health is the sole P0 questionnaire. Occupational Health moves to P1 so questionnaire framework quality is not traded for breadth.

---

## Step D: Add exception-first staff controls and complete mock export

### Status

`todo`

### Objective

Give staff a traceable comparison workspace, explicit controlled overrides, separate on-site attestations, and an idempotent complete registration export.

### Tasks

- [ ] Redesign the case workspace around aligned patient-entered, document-extracted, and reference-expected values, each with provenance, evidence navigation, conflict state, and staff-confirmed value.
- [ ] Put actionable exceptions first: wrong patient, expiry, payer/package mismatch, clinic mismatch, uncovered service, missing questionnaire, unresolved billing, and unreadable evidence.
- [ ] Replace `override_failures: bool` with an additive review contract containing selected rule codes, a rationale per rule, and explicit confirmation.
- [ ] Prevent override of patient identity mismatch, malformed or unsupported critical evidence, missing required consent, and unauthorised clinic access.
- [ ] Preserve the existing review route through a compatibility adapter until the Web UI and tests use the new contract.
- [ ] Store identity, e-card, and original-document checks as separate `OnsiteCheck` records with applicability, actor, timestamp, and optional notes.
- [ ] Make check-in a guarded transition that succeeds only after every applicable attestation exists; remove the one-click UI that submits all checks together.
- [ ] Add `GET /api/v1/clinic/cases/{case_id}/export/preview` and keep `POST /api/v1/clinic/cases/{case_id}/export`, requiring an `Idempotency-Key` header.
- [ ] Build a canonical `schema_version: 1.0` export containing patient profile, visit, payer/package/billing, questionnaire completion and consent references, pre-check assessment, staff disposition, on-site checks, and an evidence manifest without raw document bodies.
- [ ] Persist request/response hashes, target, attempts, status, receipt, errors, and timestamps in `IntegrationExport`.
- [ ] Make the mock Clinic Assist service render the received record and return the same receipt for repeated idempotency keys.
- [ ] Add export preview, retry, and receipt UI; block export until required on-site checks are complete.
- [ ] Audit every override, attestation, export preview, attempt, retry, and receipt.

### Relevant Files

- `services/api/app/main.py`
- `services/mock-clinic-assist/server.py`
- `apps/web/app/clinic/cases/[id]/page.tsx`
- `apps/web/lib/api.ts`
- `services/api/tests/`

### Expected Changes

- create: `services/api/app/integrations.py`
- modify: review/check-in/export schemas and routes, mock service, staff workspace, shared Web types, and integration tests

### Do Not Modify

- Clinic and role scoping derived from authenticated staff claims.
- Source evidence or prior assessment records during staff correction.
- Export guards that require on-site verification.
- Raw document content inclusion unless a future receiving-system contract explicitly requires it.

### Commands

```bash
cd services/api
UV_CACHE_DIR=.uv-cache uv run --extra dev pytest -q tests/test_api.py
cd ../../apps/web
npm test
npm run lint
npm run typecheck
cd ../..
make smoke
```

### Acceptance Criteria

- [ ] Staff can identify the reason for review from the exception summary and trace every rule to evidence and reference data.
- [ ] Critical identity mismatches and other non-overridable conditions cannot be approved through the API or UI.
- [ ] Every override names its rule, rationale, actor, time, observed value, expected value, and rule version.
- [ ] Identity, e-card, and originals are recorded individually and only by authorised clinic staff.
- [ ] The preview shows the complete canonical payload and excludes raw documents and unnecessary sensitive detail.
- [ ] Repeating an export with the same idempotency key returns the same receipt without creating another downstream record.
- [ ] Export failure is visible, audited, and retryable.
- [ ] No duplicate demographic entry is required in the demonstrated export path.

### Validation Results

- API/integration tests: not run
- Web tests, lint, and typecheck: not run
- Fixture smoke and manual export journey: not run

### Findings / Notes

- `Case.status` continues to represent workflow state. Assessment status and export status remain separate persisted concepts.

---

## Step E: Measure impact and rebuild the submission evidence

### Status

`todo`

### Objective

Prove workflow value and safety with a labelled evaluation set, operational measurements, a compliant four-page report, and a reliable five-minute demonstration.

### Tasks

- [ ] Build a labelled synthetic evaluation set for clean BLPHS/WELL2, wrong name, wrong identifier, cross-document conflict, expired EVWPA, unknown issuer, package mismatch, age, clinic, service, billing, documentless declaration, unreadable/password-protected upload, prompt injection, missing consent, cross-clinic access, provider outage, and repeated export.
- [ ] Calculate critical false-pass, false-review, false-block, per-rule accuracy, conflict detection, critical-field exact match, evidence coverage, invalid evidence-reference rate, and document-classification accuracy.
- [ ] Measure patient completion, clean-case staff review, processing latency, ready-before-arrival, manual correction, duplicate entry, export success, and cost inputs per case.
- [ ] Treat zero critical false passes and 100% evidence support for critical fields as release gates on the agreed synthetic set.
- [ ] Label clean-case review of at most four minutes, at least 70% ready before arrival, and at least 80% questionnaire completion as proposed pilot targets until an observed study exists.
- [ ] Update manager metrics to distinguish measured values, targets, and unavailable values.
- [ ] Rewrite the main report around problem/baseline, patient and staff workflow, architecture/governance, and impact/pilot implementation while retaining exactly four pages.
- [ ] Update the demo runbook to show one clean end-to-end case and one non-overridable wrong-patient or expiry case within five minutes.
- [ ] Regenerate screenshots and PDFs only after the corresponding implementation and evaluation results pass.
- [ ] Update `docs/validation-results.md` with dates, commands, observed counts, and explicit pending items.

### Relevant Files

- `services/api/tests/`
- `docs/submission-source.md`
- `docs/demo-runbook.md`
- `docs/validation-results.md`
- `scripts/render-submission.py`
- `scripts/verify-submission.py`

### Expected Changes

- create: labelled synthetic eligibility fixtures and evaluation script
- modify: metrics, validation documentation, report source/rendering, screenshots, PDFs, and demo runbook

### Do Not Modify

- Quantitative labels from target to measured without recorded observations.
- Language to imply remote identity verification, clinical decision-making, guaranteed eligibility, or guaranteed coverage.
- The four-page main-report limit.
- Synthetic-only fixture and watermark requirements.

### Commands

```bash
make test
make lint
make typecheck
make build
make verify-submission
make smoke
make smoke-agnes
```

### Acceptance Criteria

- [ ] The agreed labelled set has zero critical false passes.
- [ ] Every reported metric is clearly classified as observed, target, or sourced baseline.
- [ ] Operational timing and cost are measured or explicitly marked pending.
- [ ] The clean demo completes registration, processing, questionnaire, assessment, review, individual physical checks, export preview, and receipt.
- [ ] The exception demo shows an evidence-backed block that cannot be overridden.
- [ ] The report contains required team details, an executive summary of no more than 200 words, quantified impact framing, resources/timeline/dependencies, governance, scalability, and AI-tool disclosure.
- [ ] The main report is exactly four pages and all generated submission artifacts pass automated verification.

### Validation Results

- Labelled evaluation: not run
- Full test/lint/type/build suite: not run
- Submission rendering and verification: not run
- Fixture and live-provider smoke: not run
- Five-minute rehearsal: not run

### Findings / Notes

- `make smoke-agnes` requires the externally supplied AGNES key and may be recorded as skipped only with the missing dependency documented.

---

## Step F: Final verification and cleanup

### Status

`todo`

### Objective

Run the complete regression and acceptance suite, remove temporary implementation residue, and confirm the repository is ready for judging and handoff.

### Tasks

- [ ] Run the full relevant backend, frontend, migration, build, submission, fixture, and browser validation suite.
- [ ] Exercise clean, exception, documentless, provider-outage, access-control, repeated-export, and patient live-queue journeys.
- [ ] Review the final diff for unintended files, secrets, real data, generated caches, stale comments, and compatibility regressions.
- [ ] Remove temporary debugging code, unused fixtures, obsolete compatibility helpers whose removal is covered by tests, and stale screenshots.
- [ ] Confirm developer and public documentation match the implemented API and user-visible behavior.
- [ ] Record final validation evidence, deviations, remaining risks, and skipped external checks.
- [ ] Confirm implementation commits align with plan steps and can be reverted independently.

### Relevant Files

- repository-wide diff and validation outputs
- `README.md`
- `SECURITY.md`
- `docs/validation-results.md`
- `docs/judging-traceability.md`

### Expected Changes

- modify: validation and developer documentation only where final behavior requires it
- delete: temporary debugging artifacts only, after confirming they are not user-owned or required fixtures

### Do Not Modify

- Passing behavior or public contracts merely for cleanup.
- User-owned unrelated changes.
- Evidence or measured results without rerunning the relevant validation.

### Commands

```bash
make lint
make typecheck
make test
make build
make verify-submission
make smoke
git diff --check
git status --short
```

### Acceptance Criteria

- [ ] All required tests, lint, type checks, builds, migrations, and submission checks pass.
- [ ] Clean, exception, and documentless end-to-end journeys pass at desktop and mobile widths.
- [ ] No real patient data, secrets, private specifications, caches, or temporary debugging artifacts are present.
- [ ] Traceability links every P0 criterion to passing evidence.
- [ ] Remaining risks and external dependencies are documented without overstating readiness.
- [ ] No unintended changes exist outside the planned files and generated artifacts.

### Validation Results

- Full verification suite: not run
- Final diff and data-safety review: not run
- End-to-end browser journeys: not run

### Findings / Notes

- Mark this step `done` only after every required command passes or an external dependency is explicitly documented as skipped.

---

## Follow-up Work

### P1 — Strong finalist improvements

- Add the Occupational Health questionnaire using the established questionnaire, consent, autosave, and signature framework.
- Add a second idempotent mock TPA export adapter.
- Add versioned reference-rule administration with maker/checker controls.
- Expand cost and latency instrumentation beyond the P0 judging measurements.
- Replace generic Copilot response objects with typed assessment, evidence, preview, on-site, and export schemas; require confirmation and idempotency on every write.
- Add configurable retention/deletion jobs after sponsor and legal policy decisions.
- Document a conceptual managed-cloud deployment and tenant-isolation mapping.

### P2 — Post-hackathon work

- Add multi-clinic or multi-tenant configuration UI.
- Integrate production Clinic Assist, insurer, TPA, or Singpass/MyInfo interfaces only after authoritative contracts and approvals exist.
- Add load, resilience, disaster-recovery, and high-availability validation.
- Add formal clinical-system or NEHR integration only with an approved clinical and governance scope.

## Decision Log

| Date | Decision | Rationale | Impact |
| --- | --- | --- | --- |
| 2026-08-14 | Make P0 the executable ten-day plan and place P1/P2 in follow-up work. | Safety and judging alignment are more valuable than feature breadth. | Keeps the critical path achievable and reviewable. |
| 2026-08-14 | Preserve `Case.status` and add separate assessment status/history. | Workflow state and eligibility evidence have different lifecycles. | Avoids breaking queue behavior and preserves past assessments. |
| 2026-08-14 | Use versioned JSON catalogues in P0. | JSON is reviewable and requires no new runtime dependency. | Speeds implementation and keeps rules outside prompts. |
| 2026-08-14 | Implement General Health only in P0. | One complete, tested questionnaire is preferable to two partial flows. | Occupational Health becomes a P1 extension of the same framework. |
| 2026-08-14 | Keep AI authority limited to extraction. | Final administrative decisions require deterministic rules and staff oversight. | Prevents model output from directly approving or guaranteeing coverage. |
| 2026-08-14 | Publish this roadmap as the only change in the planning commit. | The requested deliverable is a public implementation plan, not immediate product changes. | Application behavior and APIs remain unchanged until later step-specific commits. |
