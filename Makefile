# On Windows without make, run the commands by hand or use WSL / Git Bash with make installed.
MATCH ?= derby_01
SPEED ?= 4

.PHONY: dev test lint fmt seed replay

dev:
	uv run uvicorn backend.app.main:app --reload --port 8000 & \
	cd frontend && npm run dev

test:
	uv run pytest
	@if [ -f frontend/package.json ]; then cd frontend && npm test --if-present; fi

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run python -m mypy .
	@if [ -f frontend/package.json ]; then cd frontend && npm run lint --if-present; fi

fmt:
	uv run ruff check --fix .
	uv run ruff format .

seed:
	uv run python -m scripts.seed

replay:
	uv run python -m scripts.replay --match $(MATCH) --speed $(SPEED)
