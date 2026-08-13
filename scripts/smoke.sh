#!/usr/bin/env sh
set -eu

base_url="${PUBLIC_BASE_URL:-http://localhost:8080}"
curl -fsS "$base_url/api/v1/health"
curl -fsS "$base_url" >/dev/null
curl -fsS "$base_url/api/openapi.json" >/dev/null
echo "ClinicPass smoke checks passed at $base_url"

