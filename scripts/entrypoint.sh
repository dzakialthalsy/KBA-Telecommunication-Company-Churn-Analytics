#!/bin/bash
set -e

echo "Waiting for catalog database..."
until python -c "import psycopg2, os; psycopg2.connect(os.getenv('CATALOG_URL'))" > /dev/null 2>&1; do
  echo "Postgres not ready, retrying in 2s..."
  sleep 2
done

echo "Running PostgreSQL catalog setup (roles & users)..."
python scripts/setup_ducklake.py --catalog-only   # ← hanya init Postgres

echo "Running ETL Pipeline (Bronze -> Silver -> Gold)..."
python etl/run_pipeline.py   # ← tabel gold dibuat di sini

echo "Creating RBAC DuckDB views..."
python scripts/setup_ducklake.py --views-only   # ← baru buat views