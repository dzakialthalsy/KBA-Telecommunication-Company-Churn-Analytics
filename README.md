# 📡 Telco Churn Analytics — Kelompok 4

> **Kecerdasan Bisnis dan Analitik**
> Strategi Peningkatan Retensi Pelanggan Telekomunikasi melalui Sistem Analitik Loyalitas dan Prediksi Churn

## 👥 Anggota Tim

| Nama | NIM | Peran |
|---|---|---|
| Dzaki Althalsyah | 245150407111071 | Project Manager |
| M. Rifa Aqilla | 245150407111047 | Business / Data Analyst |
| Dhea Akmalia Fibri | 245150407111081 | BI / Data Engineer |
| Fairuz El Fauzy | 245150407111032 | ML Engineer & QA |

---

## 🏗️ Arsitektur: Medallion (Bronze → Silver → Gold)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEDALLION ARCHITECTURE                        │
├──────────────┬──────────────────────┬───────────────────────────┤
│   🥉 BRONZE  │     🥈 SILVER        │        🥇 GOLD            │
│  Raw Layer   │   Cleaned Layer      │   Business Layer          │
├──────────────┼──────────────────────┼───────────────────────────┤
│ • Data masuk │ • Cleaning &         │ • Agregasi KPI bisnis     │
│   apa adanya │   standardisasi      │ • Segmentasi pelanggan    │
│ • +metadata  │ • Feature eng.       │ • Churn risk per customer │
│ • Append-only│ • Deduplication      │ • Executive summary       │
│              │ • Type casting       │ • Dikonsumsi Metabase     │
├──────────────┼──────────────────────┼───────────────────────────┤
│bronze_       │silver_               │gold_customer_segments     │
│telecom_raw   │telecom_cleaned       │gold_churn_risk            │
│              │                      │gold_churn_summary         │
└──────────────┴──────────────────────┴───────────────────────────┘
         Semua layer tersimpan dalam: data/gold/telco_warehouse.duckdb
```

## 🗂️ Struktur Folder

```
telco-churn-analytics/
│
├── data/
│   ├── raw/        # Dataset CSV asli Kaggle — jangan dimodifikasi
│   ├── bronze/     # Placeholder (data Bronze ada di DuckDB)
│   ├── silver/     # Placeholder (data Silver ada di DuckDB)
│   └── gold/       # telco_warehouse.duckdb — semua layer tersimpan di sini
│
├── etl/
│   ├── layers/
│   │   ├── bronze.py   # DE-07: Raw ingestion + metadata
│   │   ├── silver.py   # DE-08: Cleaning, feature engineering
│   │   └── gold.py     # DE-09: Business aggregates, mart
│   └── run_pipeline.py # Entry point: python etl/run_pipeline.py
│
├── ml/
│   ├── colab/          # Notebooks Google Colab (EDA, training, evaluasi)
│   ├── models/
│   │   ├── best_model.joblib   # Model terbaik (export dari Colab)
│   │   └── churn_scores.csv    # Output skor per pelanggan → dipakai Gold
│   └── reports/        # CSV evaluasi model (AUC-ROC, F1, dll)
│
├── dashboard/          # Query & konfigurasi Metabase
├── docs/               # PRD, PM signoff, data dictionary, SOP
├── scripts/
│   └── health_check.py # Cek kesiapan environment sebelum run
├── tests/              # Unit tests pipeline
│
├── docker-compose.yml  # 2 services: etl + metabase
├── Dockerfile
├── requirements.txt
└── .env.example
```

## 🚀 Quick Start

```bash
# 1. Setup
git clone https://github.com/<username>/telco-churn-analytics.git
cd telco-churn-analytics
cp .env.example .env

# 2. Letakkan dataset
# Download: https://www.kaggle.com/datasets/abhinav89/telecom-customer
# Simpan ke: data/raw/telecom_customer.csv

# 3. Cek environment
python scripts/health_check.py

# 4. Jalankan Medallion pipeline + Metabase
docker compose up --build
```

| Service | URL | Tabel Gold yang tersedia |
|---|---|---|
| Metabase | http://localhost:3000 | gold_churn_risk, gold_customer_segments, gold_churn_summary |

## 🔗 Integrasi ML → Gold Layer

Setelah Fairuz selesai training di Google Colab (ML-10):

```python
# Di Colab — export skor per pelanggan
scores_df = pd.DataFrame({
    "customer_id":    test_ids,
    "ml_churn_score": model.predict_proba(X_test)[:, 1],
    "ml_churn_label": model.predict(X_test)
})
scores_df.to_csv("churn_scores.csv", index=False)
```

Simpan `churn_scores.csv` ke `ml/models/` → jalankan ulang ETL → Gold layer otomatis pakai ML score.

## 📊 Tabel Gold & KPI

| Tabel | Dikonsumsi oleh | KPI |
|---|---|---|
| `gold_churn_summary` | Executive Overview | Churn Rate, Retention Rate, ARPU |
| `gold_customer_segments` | At-Risk Board | Segmen: High Value / At-Risk / Watch / Stable / Churned |
| `gold_churn_risk` | Drill-Down + ML eval | ml_churn_score, risk_level, reason codes |
