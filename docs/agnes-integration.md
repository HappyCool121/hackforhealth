# AGNES AI integration

ClinicPass uses AGNES as the primary live document-intelligence model through its OpenAI-compatible chat-completions API. Live mode performs image understanding rather than sending OCR text alone.

## Configuration

```dotenv
AI_PROVIDER=agnes
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
AGNES_MODEL=agnes-2.0-flash
AGNES_API_KEY=<provided out of band>
AGNES_TIMEOUT_SECONDS=45
```

The key is read only by the API/worker containers and must never use a `NEXT_PUBLIC_` variable. Verify access with `make smoke-agnes`.

## Calls and validation

The worker validates each upload, renders up to six PDF pages, corrects image orientation, and reduces each page to a maximum 1,800-pixel JPEG. It sends those pages as private data URLs alongside compact `{id,page,text}` OCR evidence records. No local path or publicly hosted patient URL is sent.

The configured endpoint was probed with a synthetic in-memory image and successfully read the document through a data URL. AGNES's public documentation specifies image URL content blocks; re-run `make smoke-agnes` after any endpoint/model change to protect this capability assumption.

The worker makes two forced tool calls:

1. `classify_document` returns `medical_chit`, `referral`, `healthier_sg`, `government_checkup`, `driver_license_renewal`, `insurance_ecard`, `screening_voucher`, `authorization`, or `unknown`.
2. `extract_document` returns administrative fields and evidence-ID citations, including issuer, patient identifiers, membership/policy identifiers, validity, clinic, package, check-up frequency, billing, payer, and preparation/supporting notes where present.

Responses are parsed as JSON, validated with Pydantic, and citations are retained only if their IDs exist in the OCR evidence map. A provider error marks the document `ERROR` and creates an audit event; a submitted case then finalizes through the same deterministic readiness rules. There is no silent fallback to fixture results.

Uploads begin processing while the case is still a draft. If a patient submits during processing, the case remains `PROCESSING` until all queued documents finish. Documentless `no`/`unsure` declarations skip AGNES and go directly to staff review.

AGNES must not decide eligibility, approve check-in, infer medical facts, or claim coverage. See the [AGNES quickstart](https://agnes-ai.com/en/docs/quickstart) and [AGNES 2.0 Flash API](https://agnes-ai.com/en/docs/agnes-20-flash).
