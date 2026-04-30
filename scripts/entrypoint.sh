#!/bin/bash
set -e

echo "Starting DuckLake initialization..."

echo "Waiting for catalog database..."
until python -c "import psycopg2, os; psycopg2.connect(os.getenv('CATALOG_URL'))" > /dev/null 2>&1; do
  echo "Postgres not ready, retrying in 2s..."
  sleep 2
done

echo "Running DuckLake catalog setup (RBAC)..."
python scripts/setup_ducklake.py

echo "Running ETL Pipeline (Bronze -> Silver -> Gold)..."
python etl/run_pipeline.py

echo "ETL complete. DuckDB ready for Metabase."
