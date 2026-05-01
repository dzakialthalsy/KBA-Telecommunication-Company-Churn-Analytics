"""
Export Metabase DuckDB — Gold Only (termasuk telecom_cleaned)
Membuat file DuckDB terpisah yang hanya berisi schema gold:
  - gold.churn_summary      → KPI agregat (Executive)
  - gold.churn_risk         → skor risiko per pelanggan (Operational)
  - gold.customer_segments  → segmentasi pelanggan (Operational)
  - gold.telecom_cleaned    → data lengkap 94 kolom (Analyst)
    ↑ dipindah dari silver ke gold khusus untuk file Metabase
      agar sidebar Metabase hanya tampilkan 1 schema (gold)

File ini yang di-mount ke Metabase, bukan file utama.
RBAC per tabel dikontrol otomatis via scripts/setup_metabase_rbac.py
"""

import duckdb
from pathlib import Path
from loguru import logger

# Tabel dari schema gold (file utama)
GOLD_TABLES = [
    "churn_summary",
    "churn_risk",
    "customer_segments",
]

# Tabel dari schema silver yang dipindah ke gold di file Metabase
SILVER_TO_GOLD_TABLES = [
    "telecom_cleaned",   # 94 kolom, khusus Analyst
]


def export_metabase_duckdb(source_path: Path, output_path: Path) -> None:
    """
    Baca tabel gold & silver dari source DuckDB, tulis semua ke schema gold
    di file DuckDB baru. Schema silver & bronze TIDAK muncul di file output.

    Args:
        source_path : path file DuckDB utama (telco_warehouse.duckdb)
        output_path : path file output untuk Metabase (telco_warehouse_readonly.duckdb)
    """
    logger.info(f"[EXPORT] Source : {source_path.name}")
    logger.info(f"[EXPORT] Output : {output_path.name}")

    # Hapus file lama agar tidak ada sisa schema/tabel stale
    if output_path.exists():
        output_path.unlink()
        logger.info("[EXPORT] File lama dihapus, membuat dari awal ...")

    src = duckdb.connect(str(source_path), read_only=True)
    dst = duckdb.connect(str(output_path))

    try:
        dst.execute("CREATE SCHEMA IF NOT EXISTS gold")

        # ── Export tabel Gold ─────────────────────────────────────────────
        logger.info("[EXPORT] Mengekspor tabel gold ...")
        for table in GOLD_TABLES:
            try:
                df = src.execute(f"SELECT * FROM gold.{table}").df()
                dst.execute(f"DROP TABLE IF EXISTS gold.{table}")
                dst.execute(f"CREATE TABLE gold.{table} AS SELECT * FROM df")
                logger.success(
                    f"[EXPORT] gold.{table:<25} → {len(df):>10,} baris ✓"
                )
            except Exception as e:
                logger.warning(f"[EXPORT] gold.{table} dilewati: {e}")

        # ── Export tabel Silver → dipindah ke schema gold ─────────────────
        logger.info("[EXPORT] Mengekspor silver → gold (telecom_cleaned) ...")
        for table in SILVER_TO_GOLD_TABLES:
            try:
                df = src.execute(f"SELECT * FROM silver.{table}").df()
                dst.execute(f"DROP TABLE IF EXISTS gold.{table}")
                dst.execute(f"CREATE TABLE gold.{table} AS SELECT * FROM df")
                logger.success(
                    f"[EXPORT] silver.{table} → gold.{table:<15} "
                    f"→ {len(df):>10,} baris, {len(df.columns)} kolom ✓"
                )
            except Exception as e:
                logger.warning(f"[EXPORT] silver.{table} dilewati: {e}")

        # ── Validasi schema main kosong ───────────────────────────────────
        tables_in_main = dst.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
        if not tables_in_main:
            logger.info("[EXPORT] Schema 'main' kosong ✓")

        # ── Validasi tidak ada schema silver/bronze ───────────────────────
        schemas = dst.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchall()
        schema_names = [s[0] for s in schemas]
        logger.info(f"[EXPORT] Schema di file Metabase: {schema_names}")
        assert "bronze" not in schema_names, "bronze tidak boleh ada!"
        assert "silver" not in schema_names, "silver tidak boleh ada!"

        logger.success("[EXPORT] Hanya schema 'gold' yang berisi tabel ✓")
        logger.info("[EXPORT] Struktur file Metabase:")
        logger.info("[EXPORT]   gold.churn_summary     → Executive")
        logger.info("[EXPORT]   gold.churn_risk        → Operational")
        logger.info("[EXPORT]   gold.customer_segments → Operational")
        logger.info("[EXPORT]   gold.telecom_cleaned   → Analyst (94 kolom)")
        logger.info(f"[EXPORT]   Metabase koneksi ke: {output_path}")

    finally:
        src.close()
        dst.close()