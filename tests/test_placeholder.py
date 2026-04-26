"""Placeholder tests — akan diisi sesuai task DE-07 s/d ML-09."""


def test_project_structure():
    """Validasi struktur folder proyek tersedia."""
    from pathlib import Path
    assert Path("etl/run_pipeline.py").exists(), "ETL entry point harus ada"
    assert Path("etl/extract.py").exists(), "ETL extract module harus ada"
    assert Path("etl/transform.py").exists(), "ETL transform module harus ada"
    assert Path("etl/load.py").exists(), "ETL load module harus ada"
    assert Path("ml/train.py").exists(), "ML training script harus ada"
    assert Path(".env.example").exists(), ".env.example harus ada"
    assert Path("docker-compose.yml").exists(), "docker-compose.yml harus ada"


def test_env_example_has_required_keys():
    """Validasi .env.example punya semua key yang dibutuhkan."""
    content = Path(".env.example").read_text()
    required_keys = [
        "RAW_DATA_PATH",
        "DUCKDB_PATH",
        "ML_TARGET_COLUMN",
        "MODEL_OUTPUT_PATH",
    ]
    for key in required_keys:
        assert key in content, f"Key {key} harus ada di .env.example"


from pathlib import Path
