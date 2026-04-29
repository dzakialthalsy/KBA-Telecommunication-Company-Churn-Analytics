#!/bin/bash
set -e

echo "Menjalankan ETL Pipeline (Bronze → Silver → Gold)..."
python etl/run_pipeline.py

echo "ETL selesai. DuckDB siap digunakan Metabase."