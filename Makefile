.PHONY: init up down logs build lint typecheck test test-api test-web test-e2e benchmark-v2 smoke smoke-agnes demo-assets export-public verify-public render-submission render-supporting render-screenshots verify-submission clean-data verify

init:
	cp -n .env.example .env || true

up: init
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

build:
	docker compose build

lint:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run --extra dev ruff check app tests
	cd apps/web && npm run lint

typecheck:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run --extra dev mypy app
	cd apps/web && npm run typecheck

test: test-api test-web

test-api:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run --extra dev pytest -q

test-web:
	cd apps/web && npm test

test-e2e:
	cd apps/web && npm run test:e2e

benchmark-v2:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run --extra dev python ../../scripts/run-v2-benchmark.py

smoke:
	./scripts/smoke.sh

smoke-agnes:
	docker compose run --rm -e AI_PROVIDER=agnes worker python -m app.smoke_agnes

demo-assets:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run python ../../scripts/generate-demo-documents.py

export-public:
	./scripts/export-public.sh

verify-public:
	./scripts/verify-public.sh

render-submission:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run python ../../scripts/render-submission.py

render-supporting:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run python ../../scripts/render-supporting-documents.py

render-screenshots:
	cd services/api && UV_CACHE_DIR=.uv-cache uv run python ../../scripts/render-screenshot-packs.py

verify-submission: render-submission render-supporting render-screenshots
	cd services/api && UV_CACHE_DIR=.uv-cache uv run python ../../scripts/verify-submission.py

clean-data:
	docker compose down -v

verify: build lint typecheck test verify-submission export-public verify-public
