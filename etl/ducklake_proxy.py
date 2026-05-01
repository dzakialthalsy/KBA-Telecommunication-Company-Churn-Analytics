"""
DuckLake Proxy — RBAC Access Control
Query helper yang membatasi akses data berdasarkan role pengguna.
Role didapat dari PostgreSQL katalog, view didapat dari DuckDB.

Penggunaan:
    proxy = DuckLakeProxy("ops_manager")
    df = proxy.query("SELECT * FROM view_operational LIMIT 100")
"""

import duckdb
import psycopg2
import pandas as pd
import os
from loguru import logger

# Mapping role → view yang diizinkan
ROLE_VIEW_MAP = {
    "Executive":   ["view_executive", "gold.churn_summary"],
    "Operational": ["view_operational", "view_executive"],
    "Analyst":     ["view_analyst", "view_operational", "view_executive",
                    "gold.churn_summary", "gold.churn_risk",
                    "gold.customer_segments", "silver.telecom_cleaned"],
}


class DuckLakeProxy:
    def __init__(self, username: str):
        self.username = username
        self.role = self._get_role_from_catalog()
        self.allowed_views = ROLE_VIEW_MAP.get(self.role, [])
        self.db_path = os.getenv("DUCKDB_PATH")
        logger.info(f"[PROXY] User '{username}' → role '{self.role}'")
        logger.info(f"[PROXY] Views diizinkan: {self.allowed_views}")

    def _get_role_from_catalog(self) -> str:
        """Ambil role user dari PostgreSQL katalog."""
        try:
            conn = psycopg2.connect(os.getenv("CATALOG_URL"))
            cur = conn.cursor()
            cur.execute("""
                SELECT r.role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.username = %s
            """, (self.username,))
            result = cur.fetchone()
            cur.close()
            conn.close()
            if not result:
                raise PermissionError(
                    f"User '{self.username}' tidak ditemukan di katalog."
                )
            return result[0]
        except psycopg2.Error as e:
            raise ConnectionError(f"Gagal konek ke katalog: {e}")

    def query(self, sql: str) -> pd.DataFrame:
        """
        Jalankan query SQL dengan validasi akses RBAC.
        Hanya view/tabel yang diizinkan untuk role ini yang bisa diakses.
        """
        sql_lower = sql.lower()

        # Cek apakah query mengakses view/tabel yang diizinkan
        has_access = any(
            view.lower() in sql_lower
            for view in self.allowed_views
        )

        if not has_access:
            raise PermissionError(
                f"[PROXY] ❌ Akses DITOLAK untuk role '{self.role}'. "
                f"View yang diizinkan: {self.allowed_views}"
            )

        con = duckdb.connect(self.db_path, read_only=True)
        try:
            result = con.execute(sql).df()
            logger.info(
                f"[PROXY] ✓ Query berhasil — {len(result):,} baris "
                f"(role: {self.role})"
            )
            return result
        finally:
            con.close()

    def get_allowed_views(self) -> list:
        """Return daftar view yang boleh diakses role ini."""
        return self.allowed_views


# ── Contoh penggunaan ─────────────────────────────────────────────────────
if __name__ == "__main__":
    # Executive — hanya bisa lihat KPI agregat
    proxy_exec = DuckLakeProxy("ceo_user")
    df = proxy_exec.query("SELECT * FROM view_executive")
    print(f"Executive melihat {len(df)} baris KPI")

    # Operational — bisa lihat data per pelanggan
    proxy_ops = DuckLakeProxy("ops_manager")
    df2 = proxy_ops.query(
        "SELECT * FROM view_operational WHERE risk_level = 'High' LIMIT 10"
    )
    print(f"Operational melihat {len(df2)} pelanggan High Risk")

    # Analyst — akses penuh
    proxy_analyst = DuckLakeProxy("data_analyst")
    df3 = proxy_analyst.query("SELECT * FROM view_analyst LIMIT 5")
    print(f"Analyst melihat {len(df3)} baris data lengkap")
