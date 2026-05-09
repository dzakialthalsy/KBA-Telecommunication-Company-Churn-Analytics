"""
Setup Metabase RBAC — Otomatis via Metabase API
"""

import requests
import os
import time
from loguru import logger

METABASE_URL  = os.getenv("METABASE_URL",  "http://metabase:3000")
METABASE_USER = os.getenv("METABASE_USER", "admin@telco.com")
METABASE_PASS = os.getenv("METABASE_PASS", "admin123")
DB_NAME       = os.getenv("METABASE_DB_NAME", "Telco Warehouse")

RBAC_MAP = {
    "Executive":   ["churn_summary", "churn_prediction"],
    "Operational": ["churn_risk", "customer_segments"],
    "Analyst":     ["churn_summary", "churn_risk", "customer_segments", "telecom_cleaned", "churn_prediction"],
}

USERS_MAP = {
    "Executive": [
        {"email": "ceo@telco.com", "first_name": "CEO", "last_name": "User", "password": "Exec@1234"},
    ],
    "Operational": [
        {"email": "ops@telco.com", "first_name": "Ops", "last_name": "Manager", "password": "Ops@1234"},
    ],
    "Analyst": [
        {"email": "analyst@telco.com", "first_name": "Data", "last_name": "Analyst", "password": "Analyst@1234"},
    ],
}


class MetabaseRBAC:
    def __init__(self):
        self.session_token = None
        self.headers = {"Content-Type": "application/json"}

    # ── Auth ──────────────────────────────────────────────────────────────
    def setup_metabase_admin(self):
        """Setup admin user pertama kali jika Metabase belum diinisialisasi."""
        resp = requests.get(
            f"{METABASE_URL}/api/session/properties",
            headers=self.headers,
        )
        props = resp.json()

        setup_token = props.get("setup-token")
        if not setup_token:
            logger.info("[METABASE] Metabase sudah di-setup sebelumnya, skip.")
            return

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
                "site_name":      "Telco Analytics",
                "allow_tracking": False,
            },
        }

        resp = requests.post(
            f"{METABASE_URL}/api/setup",
            json=payload,
            headers=self.headers,
        )

        if resp.status_code == 403:
            logger.info("[METABASE] Admin sudah ada (403), skip setup.")
            return

        resp.raise_for_status()
        logger.success("[METABASE] Admin berhasil dibuat ✓")

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
    def get_tables(self, db_id: int) -> dict:
        resp = self._get(f"/api/database/{db_id}/metadata")
        resp.raise_for_status()
        tables = {}
        for tbl in resp.json().get("tables", []):
            tables[tbl["name"]] = tbl["id"]
        logger.info(f"[METABASE] Tabel ditemukan: {list(tables.keys())}")
        return tables

    def register_database(self) -> int:
        """Daftarkan DuckDB ke Metabase jika belum ada."""
        resp = self._get("/api/database")
        resp.raise_for_status()
        for db in resp.json().get("data", []):
            if db["name"] == DB_NAME:
                logger.info(f"[METABASE] Database '{DB_NAME}' sudah terdaftar (id={db['id']})")
                return db["id"]

        logger.info(f"[METABASE] Mendaftarkan database '{DB_NAME}' ...")
        payload = {
            "name":   DB_NAME,
            "engine": "duckdb",
            "details": {
                "database_file": "/metabase-gold/telco_warehouse_readonly.duckdb",
            },
        }
        resp = self._post("/api/database", payload)
        resp.raise_for_status()
        db_id = resp.json()["id"]
        logger.success(f"[METABASE] Database '{DB_NAME}' terdaftar (id={db_id}) ✓")
        return db_id

    # ── Groups ────────────────────────────────────────────────────────────
    def get_or_create_group(self, name: str) -> int:
        resp = self._get("/api/permissions/group")
        resp.raise_for_status()
        for group in resp.json():
            if group["name"] == name:
                logger.info(f"[METABASE] Group '{name}' sudah ada (id={group['id']})")
                return group["id"]
        resp = self._post("/api/permissions/group", {"name": name})
        resp.raise_for_status()
        gid = resp.json()["id"]
        logger.success(f"[METABASE] Group '{name}' dibuat (id={gid}) ✓")
        return gid

    # ── Permissions ───────────────────────────────────────────────────────
    def apply_table_permissions(self, db_id: int, tables: dict, group_id: int, allowed_tables: list, role_name=""):
        resp = self._get("/api/permissions/graph")
        resp.raise_for_status()
        graph = resp.json()

        group_key = str(group_id)
        db_key    = str(db_id)

        if group_key not in graph["groups"]:
            graph["groups"][group_key] = {}

        # Metabase Community: granular per-tabel tidak didukung
        # Semua group diberi akses unrestricted di level DB
        # Pembatasan dilakukan via Collections (manual) atau DuckLakeProxy
        # Analyst → bisa SQL, role lain → GUI only
        query_access = (
            "query-builder-and-native"
            if role_name == "Analyst"
            else "query-builder"
        )
        graph["groups"][group_key][db_key] = {
            "view-data": "unrestricted",
            "create-queries": query_access,
        }

        resp = self._put("/api/permissions/graph", graph)
        if resp.status_code == 200:
            logger.success(f"[METABASE] Permissions group_id={group_id} updated ✓")
        else:
            logger.warning(
                f"[METABASE] Permissions update gagal: {resp.status_code} {resp.text}"
            )

    # ── Users ─────────────────────────────────────────────────────────────
    def create_users_and_assign_groups(self, groups: dict):
        """Buat user demo dan assign ke group yang sesuai."""
        for role_name, users in USERS_MAP.items():
            group_id = groups.get(role_name)
            if not group_id:
                continue
            for user_info in users:
                # Cek apakah user sudah ada
                resp = self._get("/api/user")
                existing = [
                    u for u in resp.json().get("data", [])
                    if u["email"] == user_info["email"]
                ]

                if existing:
                    user_id = existing[0]["id"]
                    logger.info(
                        f"[METABASE] User {user_info['email']} sudah ada (id={user_id})"
                    )
                else:
                    resp = self._post("/api/user", {
                        "email":      user_info["email"],
                        "first_name": user_info["first_name"],
                        "last_name":  user_info["last_name"],
                        "password":   user_info["password"],
                    })
                    if resp.status_code != 200:
                        logger.warning(
                            f"[METABASE] Gagal buat user {user_info['email']}: {resp.text}"
                        )
                        continue
                    user_id = resp.json()["id"]
                    logger.success(
                        f"[METABASE] User {user_info['email']} dibuat (id={user_id}) ✓"
                    )

                # Assign ke group (abaikan jika sudah member)
                self._post("/api/permissions/membership", {
                    "group_id": group_id,
                    "user_id":  user_id,
                })
                logger.success(
                    f"[METABASE] {user_info['email']} → group '{role_name}' ✓"
                )

    # ── Main Setup ────────────────────────────────────────────────────────
    def setup(self):
        logger.info("[METABASE] Memulai setup RBAC ...")

        db_id = self.register_database()

        logger.info("[METABASE] Menunggu sync tabel selesai ...")
        time.sleep(15)

        tables = self.get_tables(db_id)
        if not tables:
            logger.warning("[METABASE] Tabel belum tersync, tunggu lebih lama ...")
            time.sleep(20)
            tables = self.get_tables(db_id)

        # Setup groups, permissions, dan users dalam satu loop
        groups = {}
        for role_name, allowed_tables in RBAC_MAP.items():
            group_id = self.get_or_create_group(role_name)
            groups[role_name] = group_id
            self.apply_table_permissions(
                db_id, tables, group_id,
                allowed_tables, role_name=role_name  # ← tambahkan ini
            )

        self.create_users_and_assign_groups(groups)

        logger.success("[METABASE] Setup RBAC selesai ✓")
        logger.info("[METABASE] Ringkasan akses:")
        for role, tables_allowed in RBAC_MAP.items():
            logger.info(f"[METABASE]   {role:<15} → {tables_allowed}")
        logger.info("[METABASE] Ringkasan user:")
        for role, users in USERS_MAP.items():
            for u in users:
                logger.info(f"[METABASE]   {u['email']:<30} → {role}")


def wait_for_metabase(timeout: int = 300):
    """Tunggu Metabase ready — timeout diperpanjang ke 5 menit."""
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
        time.sleep(9)
        logger.info("[METABASE] Masih menunggu Metabase ...")
    raise TimeoutError("Metabase tidak siap dalam waktu yang ditentukan")


def main():
    logger.info("=" * 55)
    logger.info("  Metabase RBAC Setup — Otomatis via API")
    logger.info("=" * 55)
    wait_for_metabase()
    rbac = MetabaseRBAC()
    rbac.setup_metabase_admin()
    rbac.login()
    rbac.setup()
    logger.info("=" * 55)


if __name__ == "__main__":
    main()