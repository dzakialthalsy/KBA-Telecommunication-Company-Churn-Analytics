"""Health Check — validasi environment Medallion pipeline."""

import sys
from pathlib import Path

checks = []


def check(label, condition, fix=""):
    checks.append(("✓" if condition else "✗", label, fix))


check("Dataset CSV ada di data/raw/",
      Path("data/raw/telecom_customer.csv").exists(),
      "Download dari Kaggle → simpan ke data/raw/telecom_customer.csv")

check("Folder Bronze tersedia", Path("data/bronze").exists(), "mkdir -p data/bronze")
check("Folder Silver tersedia", Path("data/silver").exists(), "mkdir -p data/silver")
check("Folder Gold tersedia",   Path("data/gold").exists(),   "mkdir -p data/gold")

check(".env file ada", Path(".env").exists(), "cp .env.example .env")

try:
    import duckdb, sklearn, pandas, loguru
    check("Python packages terinstall", True)
except ImportError as e:
    check("Python packages terinstall", False, f"pip install -r requirements.txt ({e})")

check("ETL Bronze layer ada", Path("etl/layers/bronze.py").exists())
check("ETL Silver layer ada", Path("etl/layers/silver.py").exists())
check("ETL Gold layer ada",   Path("etl/layers/gold.py").exists())

ml_scores = Path("ml/models/churn_scores.csv")
if ml_scores.exists():
    check("ML scores tersedia (Gold akan pakai ML score)", True)
else:
    check("ML scores belum ada (Gold pakai rule-based fallback)", True,
          "Jalankan Colab ML-10 → export churn_scores.csv → simpan ke ml/models/")

print("\n── Medallion Pipeline Health Check ──────────────────")
all_ok = True
for status, label, *fix in checks:
    print(f"  {status}  {label}")
    if status == "✗":
        print(f"     → {fix[0] if fix else ''}")
        all_ok = False

print("─────────────────────────────────────────────────────")
print("  Bronze → Silver → Gold: " + ("SIAP ✓" if all_ok else "ADA MASALAH ✗"))
sys.exit(0 if all_ok else 1)
