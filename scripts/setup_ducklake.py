"""
Setup DuckLake Catalog — RBAC Initialization
Membuat tabel roles & users di PostgreSQL katalog.

Roles:
  Executive   → hanya bisa lihat gold.churn_summary (KPI agregat)
  Operational → bisa lihat gold.churn_risk & gold.customer_segments
  Analyst     → akses penuh semua tabel Gold & Silver

Catatan arsitektur:
  RBAC tidak lagi diimplementasikan sebagai DuckDB views terpisah.
  Kontrol akses dilakukan di layer aplikasi (DuckLakeProxy) dan
  di Metabase permissions — sesuai Medallion Architecture yang bersih
  (bronze / silver / gold tanpa schema tambahan).
"""

import psycopg2
import os
import argparse
from loguru import logger


def init_postgres_catalog():
    """Buat tabel roles & users di PostgreSQL, isi data awal."""
    logger.info("[CATALOG] Inisialisasi PostgreSQL katalog ...")
    conn = psycopg2.connect(os.getenv("CATALOG_URL"))
    cur = conn.cursor()

    # Buat tabel roles & users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id        SERIAL PRIMARY KEY,
            role_name VARCHAR(50) UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id        SERIAL PRIMARY KEY,
            username  VARCHAR(50) UNIQUE NOT NULL,
            role_id   INTEGER REFERENCES roles(id),
            full_name VARCHAR(100)
        );
    """)

    # Insert roles
    roles = [("Executive",), ("Operational",), ("Analyst",)]
    cur.executemany(
        "INSERT INTO roles (role_name) VALUES (%s) ON CONFLICT (role_name) DO NOTHING",
        roles
    )

    # Insert contoh users per role
    users = [
        ("ceo_user",     "Executive",   "VP / Direktur"),
        ("ops_manager",  "Operational", "Manager Operasional & CR"),
        ("data_analyst", "Analyst",     "Data / BI Analyst"),
    ]
    for username, role_name, full_name in users:
        cur.execute("""
            INSERT INTO users (username, role_id, full_name)
            SELECT %s, id, %s FROM roles WHERE role_name = %s
            ON CONFLICT (username) DO NOTHING
        """, (username, full_name, role_name))

    conn.commit()
    cur.close()
    conn.close()
    logger.success("[CATALOG] PostgreSQL katalog berhasil diinisialisasi ✓")
    logger.info("[CATALOG] Roles terdaftar: Executive, Operational, Analyst")
    logger.info("[CATALOG] Users terdaftar: ceo_user, ops_manager, data_analyst")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog-only",
        action="store_true",
        help="Hanya inisialisasi PostgreSQL catalog (roles & users)"
    )
    args = parser.parse_args()

    logger.info("=" * 55)
    logger.info("  DuckLake Catalog Setup — RBAC Initialization")
    logger.info("=" * 55)

    init_postgres_catalog()

    logger.success("  Setup selesai.")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()