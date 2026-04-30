"""
Setup DuckLake Catalog — RBAC Initialization
Membuat tabel roles & users di PostgreSQL katalog,
lalu membuat DuckDB views per role di Gold layer.

Roles:
  Executive   → hanya bisa lihat gold_churn_summary (KPI agregat)
  Operational → bisa lihat gold_churn_risk & gold_customer_segments
  Analyst     → akses penuh semua tabel Gold & Silver
"""

import psycopg2
import duckdb
import os
import sys
from loguru import logger


def _existing_columns(con, table_name):
    """Ambil daftar kolom aktual dari tabel/view DuckDB."""
    rows = con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {row[1] for row in rows}


def _select_existing(columns, available_columns, alias):
    """Bangun daftar SELECT hanya untuk kolom yang memang tersedia."""
    selected = []
    for column in columns:
        if column in available_columns:
            selected.append(f"            {alias}.{column}")
    return ",\n".join(selected)


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


def create_rbac_views():
    """
    Buat DuckDB views per role di Gold layer.
    Views ini yang dikoneksikan ke Metabase per kelompok pengguna.

    Struktur views:
      view_executive   → gold_churn_summary saja (KPI agregat)
      view_operational → gold_churn_risk + gold_customer_segments
      view_analyst     → semua tabel Gold + silver_telecom_cleaned
    """
    db_path = os.getenv("DUCKDB_PATH")
    logger.info("[RBAC] Membuat DuckDB views per role ...")
    con = duckdb.connect(db_path)
    segment_columns = _existing_columns(con, "gold_customer_segments")

    # ── VIEW: Executive ───────────────────────────────────────────────────
    # Hanya KPI agregat — tidak ada data individual pelanggan
    con.execute("DROP VIEW IF EXISTS view_executive")
    con.execute("""
        CREATE VIEW view_executive AS
        SELECT
            segment,
            total_customers,
            churned_customers,
            ROUND(churn_rate * 100, 2)      AS churn_rate_pct,
            ROUND(retention_rate * 100, 2)  AS retention_rate_pct,
            at_risk_customers,
            avg_revenue_arpu,
            avg_revenue_change
        FROM gold_churn_summary
    """)
    logger.info("[RBAC] view_executive dibuat ✓")

    # ── VIEW: Operational ─────────────────────────────────────────────────
    # Data per pelanggan untuk tindak mitigasi — tanpa data finansial detail
    con.execute("DROP VIEW IF EXISTS view_operational")
    operational_segment_columns = _select_existing(
        [
            "customer_segment",
            "custcare_Mean",
            "fe_high_care_call",
            "fe_revenue_drop",
            "fe_drop_call_flag",
            "fe_churn_risk_rule",
        ],
        segment_columns,
        "s",
    )
    con.execute(f"""
        CREATE VIEW view_operational AS
        SELECT
            r.Customer_ID,
            r.churn,
            r.risk_level,
            r.ml_churn_score,
            r.ml_churn_label,
            r.risk_updated_at{',' if operational_segment_columns else ''}
{operational_segment_columns}
        FROM gold_churn_risk r
        LEFT JOIN gold_customer_segments s
            ON r.Customer_ID = s.Customer_ID
    """)
    logger.info("[RBAC] view_operational dibuat ✓")

    # ── VIEW: Analyst ─────────────────────────────────────────────────────
    # Akses penuh semua kolom Gold — untuk analisis mendalam
    con.execute("DROP VIEW IF EXISTS view_analyst")
    analyst_segment_columns = _select_existing(
        [
            "customer_segment",
            "avgrev",
            "change_rev",
            "custcare_Mean",
            "fe_high_care_call",
            "fe_revenue_drop",
            "fe_low_usage",
            "fe_drop_call_flag",
            "fe_churn_risk_rule",
        ],
        segment_columns,
        "s",
    )
    con.execute(f"""
        CREATE VIEW view_analyst AS
        SELECT
            r.*{',' if analyst_segment_columns else ''}
{analyst_segment_columns}
        FROM gold_churn_risk r
        LEFT JOIN gold_customer_segments s
            ON r.Customer_ID = s.Customer_ID
    """)
    logger.info("[RBAC] view_analyst dibuat ✓")

    con.close()
    logger.success("[RBAC] Semua views RBAC berhasil dibuat ✓")
    logger.info("[RBAC] Summary views:")
    logger.info("  view_executive   → gold_churn_summary (KPI agregat, no PII)")
    logger.info("  view_operational → risk + segmen per pelanggan")
    logger.info("  view_analyst     → akses penuh semua kolom Gold")


def main():
    logger.info("=" * 55)
    logger.info("  DuckLake Catalog Setup — RBAC Initialization")
    logger.info("=" * 55)

    init_postgres_catalog()
    create_rbac_views()

    logger.info("=" * 55)
    logger.success("  Setup selesai.")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
