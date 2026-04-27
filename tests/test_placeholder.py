"""Tests — Medallion Architecture | Telco Churn Analytics."""

from pathlib import Path


def test_medallion_folder_structure():
    """Validasi folder Bronze, Silver, Gold tersedia."""
    assert Path("data/bronze").exists(), "Bronze layer folder harus ada"
    assert Path("data/silver").exists(), "Silver layer folder harus ada"
    assert Path("data/gold").exists(),   "Gold layer folder harus ada"


def test_etl_layer_scripts_exist():
    """Validasi semua ETL layer scripts tersedia."""
    assert Path("etl/layers/bronze.py").exists(), "bronze.py harus ada"
    assert Path("etl/layers/silver.py").exists(), "silver.py harus ada"
    assert Path("etl/layers/gold.py").exists(),   "gold.py harus ada"
    assert Path("etl/run_pipeline.py").exists(),  "run_pipeline.py harus ada"


def test_env_example_has_medallion_paths():
    """Validasi .env.example punya key Medallion yang dibutuhkan."""
    content = Path(".env.example").read_text()
    for key in ["RAW_DATA_PATH", "DUCKDB_PATH", "ML_SCORES_PATH",
                "CHURN_HIGH_RISK_THRESHOLD", "CHURN_MEDIUM_RISK_THRESHOLD"]:
        assert key in content, f"{key} harus ada di .env.example"


def test_docker_compose_has_gold_mount():
    """Validasi docker-compose mount Gold layer ke Metabase."""
    content = Path("docker-compose.yml").read_text()
    assert "data/gold" in content, "Gold layer harus di-mount ke Metabase"
    assert "metabase-gold" in content, "Metabase harus baca dari Gold layer"
