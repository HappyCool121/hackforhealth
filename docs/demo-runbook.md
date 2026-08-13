# Five-minute demo runbook

## Prepare

1. Copy `.env.example` to `.env`.
2. For the live AI demo set `AI_PROVIDER=agnes` and add `AGNES_API_KEY`. Keep the fixture setting for rehearsals without network access.
3. Run `make up`, then `make smoke`.
4. Open <http://localhost:8080> and Mailpit at <http://localhost:8025>. On the tablet, open <http://localhost:8080/demo/tablet-documents>.

## Story

1. **Patient identity:** choose “Start pre-registration,” open the clearly labelled Singpass demo, simulate approval, and allow the fictional Jamie Tan MyInfo profile.
2. **Visit:** select a reason for visit and answer whether documents are required. Point out that manual entry and a documentless clinic-review path remain available.
3. **Document:** select “Company medical chit” on the tablet, tap “Take a photo” on the phone, and photograph the displayed form. This starts AGNES parsing through the real upload endpoint. The one-click shortcut remains available as a fallback.
4. Show the patient-safe extracted summary and AGNES live/fixture label, continue to review, and submit. Point out the newly issued live queue number and waiting destination. If parsing is still active, explain that it finishes asynchronously.
5. **Clinic:** sign in as the assistant and open the case from the review queue. Show the visit reason and document declaration.
6. Show six deterministic checks, extracted fields, and page-grounded OCR evidence. Explain that AGNES extracts while rules and people decide.
7. Keep the patient page visible on the phone. Approve for check-in on the clinic/tablet surface and show the phone update automatically to “Registration Counter 2.”
8. In the clinic workspace confirm all three on-site checks. Show the patient phone update automatically to “Consultation Room 3,” then export to mock Clinic Assist.
9. Sign in as manager to show synthetic metrics, reference data, and the immutable event trail.

## Failure path

Use the one-click “Six-month check-up” sample to demonstrate a Central/West clinic mismatch and “Request information.” Mailpit displays the simulated patient message.

The fifth tablet sample is a fictional driver's-licence renewal medical form. It is deliberately labelled as neither a licence, government form, nor medical clearance.

## Documentless path

Choose GP consultation and “No documents needed,” continue without uploading, and submit. The case reaches staff review with a `REVIEW` supporting-document check rather than a false failure.

## Accounts

- Assistant: `assistant@clinicpass.test` / `DemoAssistant1!`
- Manager: `manager@clinicpass.test` / `DemoManager1!`

Never use real patient information in a demo.
