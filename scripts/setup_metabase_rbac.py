"""
Setup Metabase RBAC — Otomatis via Metabase API
Membuat groups, mengatur permissions per tabel, tanpa perlu klik manual.

RBAC mapping sesuai PRD:
  Executive   → gold.churn_summary saja
  Operational → gold.churn_risk, gold.customer_segments
  Analyst     → semua tabel (termasuk gold.telecom_cleaned)

Dipanggil otomatis dari entrypoint.sh setelah ETL selesai.
"""

import requests
import os
import time
from loguru import logger

METABASE_URL  = os.getenv("METABASE_URL",  "http://metabase:3000")
METABASE_USER = os.getenv("METABASE_USER", "admin@telco.com")
METABASE_PASS = os.getenv("METABASE_PASS", "admin123")
DB_NAME       = os.getenv("METABASE_DB_NAME", "Telco Warehouse")

# Mapping group → tabel yang BOLEH diakses (sisanya unrestricted=false)
RBAC_MAP = {
    "Executive":   ["churn_summary"],
    "Operational": ["churn_risk", "customer_segments"],
    "Analyst":     ["churn_summary", "churn_risk", "customer_segments", "telecom_cleaned"],
}


class MetabaseRBAC:
    def __init__(self):
        self.session_token = None
        self.headers = {"Content-Type": "application/json"}

    # ── Auth ──────────────────────────────────────────────────────────────
    def login(self):
        logger.info(f"[METABASE] Login sebagai {METABASE_USER} ...")
        resp = requests.post(
            f"{METABASE_URL}/api/session",
            json={"username": METABASE_USER, "password": METABASE_PASS},
            headers=self.headers,
        )
        resp.raise_for_status()
        self.session_token = resp.json()["id"]
        self.headers["X-Metabase-Session"] = self.session_token
        logger.success("[METABASE] Login berhasil ✓")

    def _get(self, path):
        return requests.get(f"{METABASE_URL}{path}", headers=self.headers)

    def _put(self, path, data):
        return requests.put(f"{METABASE_URL}{path}", json=data, headers=self.headers)

    def _post(self, path, data):
        return requests.post(f"{METABASE_URL}{path}", json=data, headers=self.headers)

    # ── Database ──────────────────────────────────────────────────────────
    def get_database_id(self) -> int:
        """Cari ID database berdasarkan nama."""
        resp = self._get("/api/database")
        resp.raise_for_status()
        for db in resp.json().get("data", []):
            if db["name"] == DB_NAME:
                logger.info(f"[METABASE] Database '{DB_NAME}' ditemukan (id={db['id']})")
                return db["id"]
        raise ValueError(f"Database '{DB_NAME}' tidak ditemukan di Metabase")

    def get_tables(self, db_id: int) -> dict:
        """Return dict {nama_tabel: table_id} untuk database ini."""
        resp = self._get(f"/api/database/{db_id}/metadata")
        resp.raise_for_status()
        tables = {}
        for tbl in resp.json().get("tables", []):
            tables[tbl["name"]] = tbl["id"]
        logger.info(f"[METABASE] Tabel ditemukan: {list(tables.keys())}")
        return tables

    # ── Groups ────────────────────────────────────────────────────────────
    def get_or_create_group(self, name: str) -> int:
        """Cari group by name, buat baru jika belum ada."""
        resp = self._get("/api/permissions/group")
        resp.raise_for_status()
        for group in resp.json():
            if group["name"] == name:
                logger.info(f"[METABASE] Group '{name}' sudah ada (id={group['id']})")
                return group["id"]

        # Buat baru
        resp = self._post("/api/permissions/group", {"name": name})
        resp.raise_for_status()
        gid = resp.json()["id"]
        logger.success(f"[METABASE] Group '{name}' dibuat (id={gid}) ✓")
        return gid

    # ── Permissions ───────────────────────────────────────────────────────
    def apply_table_permissions(self, db_id: int, tables: dict, group_id: int, allowed_tables: list):
        """
        Set permissions per tabel untuk satu group.
        Tabel yang ada di allowed_tables → unrestricted (bisa query).
        Tabel lain → no (tidak bisa lihat sama sekali).
        """
        # Ambil permissions graph saat ini
        resp = self._get("/api/permissions/graph")
        resp.raise_for_status()
        graph = resp.json()

        group_key = str(group_id)
        db_key    = str(db_id)

        # Pastikan struktur graph ada
        if group_key not in graph["groups"]:
            graph["groups"][group_key] = {}
        if db_key not in graph["groups"][group_key]:
            graph["groups"][group_key][db_key] = {}

        # Set view-data per tabel
        table_permissions = {}
        for tbl_name, tbl_id in tables.items():
            if tbl_name in allowed_tables:
                table_permissions[str(tbl_id)] = {"read": "unrestricted", "query": "unrestricted"}
            else:
                table_permissions[str(tbl_id)] = {"read": "none", "query": "none"}

        graph["groups"][group_key][db_key] = {
            "view-data": "granular",
            "create-queries": "granular",
            "data": {"schemas": {"gold": table_permissions}},
        }

        resp = self._put("/api/permissions/graph", graph)
        if resp.status_code == 200:
            logger.success(
                f"[METABASE] Permissions group_id={group_id} "
                f"→ allow: {allowed_tables} ✓"
            )
        else:
            logger.warning(
                f"[METABASE] Permissions update gagal: {resp.status_code} {resp.text}"
            )

    # ── Main Setup ────────────────────────────────────────────────────────
    def setup(self):
        logger.info("[METABASE] Memulai setup RBAC ...")

        db_id  = self.get_database_id()
        tables = self.get_tables(db_id)

        for role_name, allowed_tables in RBAC_MAP.items():
            group_id = self.get_or_create_group(role_name)
            self.apply_table_permissions(db_id, tables, group_id, allowed_tables)

        logger.success("[METABASE] Setup RBAC selesai ✓")
        logger.info("[METABASE] Ringkasan akses:")
        for role, tables_allowed in RBAC_MAP.items():
            logger.info(f"[METABASE]   {role:<15} → {tables_allowed}")


def wait_for_metabase(timeout: int = 120):
    """Tunggu Metabase ready sebelum setup RBAC."""
    logger.info(f"[METABASE] Menunggu Metabase siap di {METABASE_URL} ...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{METABASE_URL}/api/health", timeout=5)
            if resp.status_code == 200:
                logger.success("[METABASE] Metabase siap ✓")
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(5)
        logger.info("[METABASE] Masih menunggu Metabase ...")
    raise TimeoutError("Metabase tidak siap dalam waktu yang ditentukan")

def setup_metabase_admin(self):
    """Setup admin user pertama kali jika Metabase belum diinisialisasi."""
    # Cek apakah Metabase sudah di-setup
    resp = requests.get(f"{METABASE_URL}/api/session/properties")
    props = resp.json()
    
    if props.get("setup-token") is None:
        logger.info("[METABASE] Metabase sudah di-setup sebelumnya, skip.")
        return

    setup_token = props["setup-token"]
    logger.info("[METABASE] Metabase belum di-setup, menginisialisasi admin ...")

    payload = {
        "token": setup_token,
        "user": {
            "email":      METABASE_USER,
            "password":   METABASE_PASS,
            "first_name": "Admin",
            "last_name":  "Telco",
            "site_name":  "Telco Analytics",
        },
        "prefs": {
            "site_name":          "Telco Analytics",
            "allow_tracking":     False,
        },
    }

    resp = requests.post(
        f"{METABASE_URL}/api/setup",
        json=payload,
        headers=self.headers,
    )
    resp.raise_for_status()
    logger.success("[METABASE] Admin berhasil dibuat ✓")


def main():
    logger.info("=" * 55)
    logger.info("  Metabase RBAC Setup — Otomatis via API")
    logger.info("=" * 55)
    wait_for_metabase()
    rbac = MetabaseRBAC()
    rbac.setup_metabase_admin()   # ← tambahkan ini SEBELUM login
    rbac.login()
    rbac.setup()
    logger.info("=" * 55)


if __name__ == "__main__":
    main()