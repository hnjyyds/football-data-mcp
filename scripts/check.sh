#!/usr/bin/env bash
set -euo pipefail

uv run ruff check football_data_mcp tests frontend/test_server.py
uv run mypy
uv run pyright
uv run pytest -q -p no:cacheprovider

(
  cd frontend
  npm test -- --run
  npm run build
)
