"""
Health Check — validasi environment sebelum run pipeline
Jalankan: python scripts/health_check.py
"""
import sys
from pathlib import Path

checks = []

def check(label, condition, fix=""):
    status = "✓" if condition else "✗"
    checks.append((status, label, fix))

# Dataset
check("Dataset CSV ada di data/raw/", Path("data/raw/telecom_customer.csv").exists(),
      "Download dari Kaggle dan simpan ke data/raw/telecom_customer.csv")

# .env
check(".env file ada", Path(".env").exists(), "cp .env.example .env")

# Python packages
try:
    import duckdb, sklearn, pandas, loguru
    check("Python packages terinstall", True)
except ImportError as e:
    check("Python packages terinstall", False, f"pip install -r requirements.txt ({e})")

print("\n── Health Check ─────────────────────────")
all_ok = True
for status, label, fix in checks:
    print(f"  {status}  {label}")
    if status == "✗":
        print(f"     → {fix}")
        all_ok = False

print("─────────────────────────────────────────")
print("  Status: " + ("SIAP ✓" if all_ok else "ADA MASALAH ✗"))
sys.exit(0 if all_ok else 1)
