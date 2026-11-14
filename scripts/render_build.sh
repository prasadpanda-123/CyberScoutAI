#!/usr/bin/env bash
set -euo pipefail

python -m pip install -r requirements.txt
npm ci
npm ci --prefix frontend
npm run build
python -m src.database.migrations.migration_manager
python scripts/prune_render_tests.py
