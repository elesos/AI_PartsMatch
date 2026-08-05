#!/bin/sh
set -eu

alembic upgrade head
python -m app.scripts.bootstrap_configs
python -m app.scripts.bootstrap_admin
python /app/scripts/seed.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
