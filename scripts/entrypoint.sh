#!/bin/bash
set -e

echo "Waiting for catalog database..."
until python -c "import psycopg2, os; psycopg2.connect(os.getenv('CATALOG_URL'))" > /dev/null 2>&1; do
  echo "Postgres not ready, retrying in 2s..."
  sleep 2
done

echo "Running PostgreSQL catalog setup (roles & users)..."
python scripts/setup_ducklake.py --catalog-only

echo "Running ETL Pipeline (Bronze -> Silver -> Gold)..."
python etl/run_pipeline.py

echo "ETL complete. DuckDB ready for Metabase."

echo "Setting up Metabase RBAC (via API)..."
python scripts/setup_metabase_rbac.py

echo "All done."