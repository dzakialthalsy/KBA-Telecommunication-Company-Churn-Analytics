# KBA Telecommunication Company Churn Analytics

Proyek Kecerdasan Bisnis dan Analitik untuk membantu perusahaan telekomunikasi memantau churn, mengelompokkan pelanggan, dan menentukan prioritas retensi. Solusi ini memakai pipeline Medallion, DuckDB sebagai analytical warehouse, model machine learning untuk skor churn, dan Metabase untuk dashboard bisnis.

## Anggota Tim

| Nama | NIM | Peran |
| --- | --- | --- |
| Dzaki Althalsyah | 245150407111071 | Project Manager |
| M. Rifa Aqilla | 245150407111047 | Business / Data Analyst |
| Dhea Akmalia Fibri | 245150407111081 | BI / Data Engineer |
| Fairuz El Fauzy | 245150407111032 | ML Engineer & QA |

## Fitur Utama

- ETL Medallion: Bronze, Silver, dan Gold di DuckDB.
- Cleaning data pelanggan telekomunikasi: imputasi missing value, deduplikasi, koreksi tipe data, capping outlier, transformasi log, dan feature engineering.
- Gold layer untuk analitik bisnis: ringkasan churn, segmentasi pelanggan, risiko churn, dan prediksi churn berbasis ML jika skor tersedia.
- Export DuckDB khusus dashboard agar Metabase hanya membaca schema Gold.
- Setup Metabase otomatis dengan database, role, group, dan user demo.
- Aplikasi FastAPI opsional untuk prediksi churn per pelanggan.

## Arsitektur Data

```text
data/raw/Telecom_customer.csv
  -> bronze.telecom_raw
  -> silver.telecom_cleaned
  -> gold.customer_segments
  -> gold.churn_risk
  -> gold.churn_summary
  -> gold.churn_prediction (jika ml/models/churn_scores.csv tersedia)
  -> data/gold/telco_warehouse_readonly.duckdb untuk Metabase
```

File warehouse utama berada di `data/gold/telco_warehouse.duckdb`. Pipeline tetap menyimpan semua layer di warehouse utama, lalu membuat file read-only terpisah untuk konsumsi dashboard.

## Struktur Folder

```text
KBA-Telecommunication-Company-Churn-Analytics/
|-- dashboard/              # FastAPI predictor, template UI, builder inference bundle
|-- data/
|   |-- raw/                # Dataset CSV sumber
|   |-- bronze/             # Placeholder layer Bronze
|   |-- silver/             # Placeholder layer Silver
|   `-- gold/               # Output DuckDB warehouse dan export dashboard
|-- docs/                   # Dokumen PM, handoff, dan dokumentasi pendukung
|-- etl/
|   |-- layers/
|   |   |-- bronze.py       # Ingest data mentah ke bronze.telecom_raw
|   |   |-- silver.py       # Cleaning dan feature engineering ke silver.telecom_cleaned
|   |   `-- gold.py         # Tabel bisnis di schema gold
|   |-- export_metabase.py  # Export schema Gold untuk Metabase
|   `-- run_pipeline.py     # Entry point pipeline ETL
|-- ml/
|   |-- colab/              # Notebook training dan eksperimen ML
|   |-- models/             # Model dan skor churn
|   `-- reports/            # Laporan evaluasi model
|-- scripts/                # Health check, init catalog, setup Metabase RBAC
|-- tests/                  # Unit test pipeline
|-- docker-compose.yml      # catalog_db, etl, metabase, metabase_setup
|-- Dockerfile              # Image ETL
|-- Dockerfile.inference    # Image predictor FastAPI
|-- Dockerfile.metabase     # Image Metabase + plugin DuckDB
|-- requirements.txt
`-- .env.example
```

## Prasyarat

- Python 3.11 atau versi kompatibel.
- Docker dan Docker Compose untuk menjalankan pipeline plus Metabase.
- Dataset Kaggle Telecom Customer Churn disimpan di folder `data/raw/`.
- File `.env` dibuat dari `.env.example`.

Catatan dataset: pastikan nilai `RAW_DATA_PATH` di `.env` sama persis dengan nama file CSV di `data/raw/`. Di Docker/Linux, huruf besar dan kecil berpengaruh. Jika file bernama `Telecom_customer.csv`, gunakan path tersebut secara persis.

## Quick Start Lokal

```powershell
cd C:\Users\dzakialthalsyah\Downloads\KBA-Telecommunication-Company-Churn-Analytics
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\health_check.py
python etl\run_pipeline.py
```

Jika memakai Git Bash atau WSL, gunakan `cp .env.example .env` sebagai pengganti `copy`.

## Menjalankan dengan Docker dan Metabase

```powershell
docker compose up --build
```

Service yang dijalankan:

| Service | Fungsi |
| --- | --- |
| `catalog_db` | PostgreSQL catalog untuk metadata dan kebutuhan RBAC. |
| `etl` | Menjalankan pipeline Bronze -> Silver -> Gold. |
| `metabase` | Dashboard BI di `http://localhost:3000`. |
| `metabase_setup` | One-shot setup untuk database, group, permission, dan user demo. |

Akses Metabase lokal:

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@telco.com` | `Admin@1234` |
| Executive | `ceo@telco.com` | `Exec@1234` |
| Operational | `ops@telco.com` | `Ops@1234` |
| Analyst | `analyst@telco.com` | `Analyst@1234` |

Credential di atas mengikuti nilai default proyek dan hanya ditujukan untuk demo lokal. Jika `.env` diubah, gunakan credential dari file tersebut.

## Output Gold Layer

| Tabel | Tujuan | Konsumen utama |
| --- | --- | --- |
| `gold.churn_summary` | KPI agregat: total customer, churn rate, retention rate, ARPU, dan pelanggan berisiko. | Executive |
| `gold.customer_segments` | Segmentasi pelanggan: Churned, At-Risk, Watch, High Value, Stable. | Operational |
| `gold.churn_risk` | Skor risiko churn per pelanggan, risk level, dan informasi pendukung. | Operational / Analyst |
| `gold.churn_prediction` | Hasil prediksi ML untuk data test/scored customer jika `churn_scores.csv` tersedia. | Executive / Analyst |
| `gold.telecom_cleaned` | Data cleaned lengkap yang diekspor dari Silver ke schema Gold khusus untuk analisis di Metabase. | Analyst |

## Integrasi ML

Pipeline Gold akan mencoba membaca skor ML dari `ml/models/churn_scores.csv`. Format kolom yang didukung:

| Kolom | Keterangan |
| --- | --- |
| `Customer_ID`, `customer_id`, atau `CustomerID` | ID pelanggan. |
| `ml_churn_score` | Probabilitas churn dari model. |
| `ml_churn_label` | Label prediksi churn. |

Jika file skor ML belum tersedia atau formatnya tidak sesuai, pipeline tetap berjalan memakai fallback rule-based dari fitur `fe_churn_risk_rule`.

Contoh export skor dari notebook:

```python
scores_df = pd.DataFrame({
    "customer_id": test_ids,
    "ml_churn_score": model.predict_proba(X_test)[:, 1],
    "ml_churn_label": model.predict(X_test),
})
scores_df.to_csv("ml/models/churn_scores.csv", index=False)
```

Setelah file skor tersedia, jalankan ulang:

```powershell
python etl\run_pipeline.py
```

## FastAPI Predictor Opsional

Untuk membuat bundle inference dan menjalankan aplikasi prediksi:

```powershell
python dashboard\build_inference_bundle.py
uvicorn dashboard.churn_app:app --host 0.0.0.0 --port 8000
```

Endpoint utama:

| Endpoint | Fungsi |
| --- | --- |
| `GET /` | Form prediksi churn berbasis template HTML. |
| `GET /health` | Health check aplikasi. |
| `POST /predict` | Prediksi churn dari payload fitur pelanggan. |

Alternatif Docker:

```powershell
docker build -f Dockerfile.inference -t telco-churn-inference .
docker run --rm -p 8000:8000 telco-churn-inference
```

## Environment Variables Penting

| Variable | Fungsi |
| --- | --- |
| `RAW_DATA_PATH` | Lokasi dataset CSV sumber. |
| `DUCKDB_PATH` | Lokasi warehouse utama DuckDB. |
| `ML_SCORES_PATH` | Lokasi file skor ML untuk Gold layer. |
| `ETL_LOG_LEVEL` | Level logging ETL. |
| `METABASE_URL` | URL Metabase untuk setup otomatis. |
| `METABASE_USER` | Email admin Metabase. |
| `METABASE_PASS` | Password admin Metabase. |
| `METABASE_DB_NAME` | Nama database yang didaftarkan ke Metabase. |
| `CATALOG_URL` | Koneksi PostgreSQL catalog. |

## Verifikasi dan Test

```powershell
python scripts\health_check.py
python -m pytest
```

`health_check.py` memvalidasi keberadaan dataset, folder layer, `.env`, dependency Python, file ETL, dan skor ML jika tersedia.

## Troubleshooting Singkat

| Masalah | Penyebab umum | Solusi |
| --- | --- | --- |
| Dataset tidak ditemukan | `RAW_DATA_PATH` tidak sama dengan nama file sebenarnya. | Sesuaikan path di `.env` atau rename file CSV. |
| Metabase belum menampilkan tabel | Sync database belum selesai atau ETL belum berhasil. | Tunggu beberapa saat, cek log `etl` dan `metabase_setup`. |
| `gold.churn_prediction` tidak ada | `ml/models/churn_scores.csv` belum tersedia atau gagal dibaca. | Export skor ML, pastikan kolom wajib ada, lalu jalankan ulang ETL. |
| Predictor gagal start | `churn_inference_bundle.joblib` belum dibuat. | Jalankan `python dashboard\build_inference_bundle.py`. |
