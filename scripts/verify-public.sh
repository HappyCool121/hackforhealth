#!/usr/bin/env sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
public_dir="$root_dir/submission-public"

test -f "$public_dir/.clinicpass-public-export"
test -f "$public_dir/.gitignore"
test -f "$public_dir/README.md"
test -f "$public_dir/copilot/clinicpass-actions.openapi.v2.json"
test -f "$public_dir/output/pdf/ClinicPass-technical-submission.pdf"
test -f "$public_dir/output/submission/01-ClinicPass-main-report.pdf"
test -f "$public_dir/output/submission/02-ClinicPass-synthetic-demo-documents.pdf"
test -f "$public_dir/output/submission/03-ClinicPass-patient-surface.pdf"
test -f "$public_dir/output/submission/04-ClinicPass-clinic-admin-surface.pdf"
test -f "$public_dir/services/api/app/ai.py"
test -f "$public_dir/services/api/app/migrations/versions/0002_patient_intake_and_vision.py"
test -f "$public_dir/services/api/app/migrations/versions/0003_live_queue_and_room.py"
test -f "$public_dir/apps/web/app/patient/start/page.tsx"
test -f "$public_dir/apps/web/public/tablet-samples/company-medical-chit.pdf"
test -f "$public_dir/apps/web/public/tablet-samples/drivers-license-renewal-form.pdf"
test -f "$public_dir/apps/web/app/demo/tablet-documents/page.tsx"
test -f "$public_dir/apps/web/app/clinic/queue/page.tsx"
test -f "$public_dir/scripts/generate-demo-documents.py"
test ! -e "$public_dir/spec(1).md"
test ! -e "$public_dir/.env"

for forbidden in '*.pem' '*.key' '*.p12' '*.pfx' 'id_rsa' 'id_ed25519'; do
  if find "$public_dir" -type f -name "$forbidden" | grep -q .; then
    echo "Credential-like file found in public export: $forbidden" >&2; exit 1
  fi
done

if find "$public_dir" -type d \( -name .git -o -name node_modules -o -name .venv -o -name .mypy_cache -o -name .ruff_cache \) | grep -q .; then
  echo "Git metadata, dependencies, or tool caches found in public export." >&2; exit 1
fi
if grep -R -E '[A]GNES_API_KEY=[A-Za-z0-9_-]{16,}|B[E]GIN (RSA |EC |OPENSSH )?PRIVATE KEY' "$public_dir" --exclude='.env.example' >/dev/null 2>&1; then
  echo "Likely secret found in public export." >&2; exit 1
fi
if grep -R -E 'gh[pousr]_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9_-]{20,}' "$public_dir" --exclude='.env.example' >/dev/null 2>&1; then
  echo "Provider credential pattern found in public export." >&2; exit 1
fi
python3 -m json.tool "$public_dir/copilot/clinicpass-actions.openapi.v2.json" >/dev/null
pages=""
if [ -x "$root_dir/services/api/.venv/bin/python" ]; then
  pages=$("$root_dir/services/api/.venv/bin/python" -c 'from pypdf import PdfReader; import sys; print(len(PdfReader(sys.argv[1]).pages))' "$public_dir/output/pdf/ClinicPass-technical-submission.pdf")
elif command -v pdfinfo >/dev/null 2>&1; then
  pages=$(pdfinfo "$public_dir/output/pdf/ClinicPass-technical-submission.pdf" | awk '/^Pages:/ {print $2}')
fi
if [ -n "$pages" ] && [ "$pages" != "4" ]; then
  echo "Judging submission must be exactly four pages." >&2; exit 1
fi
echo "Public judging repository verification passed."
