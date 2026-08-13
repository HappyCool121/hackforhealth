# Synthetic fixture pack

Every person, identifier, organization, and entitlement in this folder is fictional. Never replace these files with real patient information.

- `screening-voucher.txt`: expected to pass most readiness checks in fixture mode.
- `expired-authorization.txt`: intentionally incomplete/expired for an exception demo.
- `referral.txt`: a second supported document type.

## Ready-to-upload visual samples

`tablet-display/` contains five polished, visibly watermarked PDFs used for the two-device camera demo and the patient UI's one-click shortcuts:

- `company-medical-chit.pdf`: clean end-to-end path.
- `referral-letter.pdf`: administrative referral example.
- `healthier-sg-form.pdf`: fictional Healthier SG administrative form with no official affiliation.
- `six-month-checkup-letter.pdf`: deliberate Central/West clinic mismatch.
- `drivers-license-renewal-form.pdf`: fictional driver's-licence renewal medical administration form.

Regenerate them with `make demo-assets`. The same files are copied to `apps/web/public/tablet-samples/`. Open `/demo/tablet-documents` on a tablet and photograph the selected form from the patient flow on a phone. One-click selection still uses the real patient upload endpoint.

Official judging fixtures, when supplied, must be placed outside version control until redistribution permission is confirmed.
