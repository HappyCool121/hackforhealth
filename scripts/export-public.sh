#!/usr/bin/env sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_dir="$root_dir/submission-public"
marker_name=".clinicpass-public-export"
stage_dir=$(mktemp -d "${TMPDIR:-/tmp}/clinicpass-public.XXXXXX")
backup_dir="$root_dir/.submission-public.backup.$$"

cleanup() {
  rm -rf "$stage_dir"
  if [ -d "$backup_dir" ]; then rm -rf "$backup_dir"; fi
}
trap cleanup EXIT INT TERM

for item in README.md SECURITY.md LICENSE Makefile compose.yaml .env.example apps services infra docs copilot fixtures scripts output; do
  rsync -a \
    --exclude node_modules --exclude .next --exclude .venv --exclude .uv-cache \
    --exclude __pycache__ --exclude .pytest_cache --exclude .mypy_cache --exclude .ruff_cache \
    --exclude .playwright-cli --exclude '*.tsbuildinfo' \
    "$root_dir/$item" "$stage_dir/"
done

cp "$root_dir/scripts/public.gitignore" "$stage_dir/.gitignore"

find "$stage_dir" -type d \( -name node_modules -o -name .next -o -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
find "$stage_dir" -type f \( -name '*.pyc' -o -name '*.log' -o -name '.DS_Store' \) -delete
touch "$stage_dir/$marker_name"

if grep -R -E '[A]GNES_API_KEY=[A-Za-z0-9_-]{16,}|B[E]GIN (RSA |EC |OPENSSH )?PRIVATE KEY' "$stage_dir" --exclude='.env.example' >/dev/null 2>&1; then
  echo "Refusing export: a likely secret was found." >&2
  exit 1
fi

if [ -e "$target_dir" ]; then
  if [ ! -f "$target_dir/$marker_name" ]; then
    echo "Refusing to replace $target_dir because the export marker is missing." >&2
    exit 1
  fi
  mv "$target_dir" "$backup_dir"
fi
mv "$stage_dir" "$target_dir"
echo "Sanitized judging repository generated at $target_dir"
