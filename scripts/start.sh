#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then cp .env.example .env; fi
mkdir -p data/uploads
alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
