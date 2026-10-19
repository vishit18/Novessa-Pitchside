# On Windows without make, run the commands by hand or use WSL / Git Bash with make installed.
MATCH ?= derby_01
SPEED ?= 4

.PHONY: dev test lint fmt seed replay

dev:
	uv run uvicorn backend.app.main:app --reload --port 8000 & \
	cd frontend && npm run dev

test:
	uv run pytest
	cd frontend && npm test --if-present

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run python -m mypy .
	cd frontend && npm run lint --if-present

fmt:
	uv run ruff check --fix .
	uv run ruff format .

seed:
	uv run python scripts/seed.py

replay:
	uv run python scripts/replay.py --match $(MATCH) --speed $(SPEED)
