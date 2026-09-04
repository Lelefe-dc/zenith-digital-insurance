#!/usr/bin/env sh
set -eu

cd /app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
