# 📡 Telco Churn Analytics — Kelompok 4

> \*\*Kecerdasan Bisnis dan Analitik\*\*  
> Strategi Peningkatan Retensi Pelanggan Telekomunikasi melalui Sistem Analitik Loyalitas dan Prediksi Churn

## 👥 Anggota Tim

|Nama|NIM|Peran|
|-|-|-|
|Dzaki Althalsyah|245150407111071|Project Manager|
|M. Rifa Aqilla|245150407111047|Business / Data Analyst|
|Dhea Akmalia Fibri|245150407111081|BI / Data Engineer|
|Fairuz El Fauzy|245150407111032|ML Engineer \& QA|

## 🗂️ Struktur Folder

```
telco-churn-analytics/
│
├── data/
│   ├── raw/            # Dataset asli dari Kaggle (CSV) — jangan dimodifikasi
│   ├── staging/        # Hasil ekstraksi \& validasi awal (ETL layer 1)
│   └── mart/           # DuckDB warehouse: telco\_warehouse.duckdb
│
├── etl/                # ETL pipeline (Python): extract → transform → load ke DuckDB
├── ml/
│   ├── colab/          # Notebooks .ipynb untuk Google Colab (EDA, training, evaluasi)
│   ├── models/         # Model tersimpan (.joblib) — hasil export dari Colab
│   └── reports/        # Laporan evaluasi model (CSV, PNG)
│
├── dashboard/          # Query \& konfigurasi Metabase
├── docs/               # PRD, data dictionary, SOP, user guide
├── scripts/            # Utility: health\_check.py
├── tests/              # Unit tests ETL pipeline
│
├── docker-compose.yml  # 2 service: etl + metabase
├── Dockerfile          # Image Python 3.11 untuk ETL
├── requirements.txt    # Dependensi Python (ETL \& inference)
└── .env.example        # Template environment variables
```

## 🏗️ Arsitektur Sistem

```
\[Kaggle CSV]
     │
     ▼
\[Docker: ETL Service]  ←── Python: extract.py → transform.py → load.py
     │
     ▼
\[DuckDB File]  ←── data/mart/telco\_warehouse.duckdb  (mount ke Metabase)
     │
     ▼
\[Docker: Metabase]  ←── Dashboard interaktif → http://localhost:3000

\[Google Colab]  ←── EDA + Model Training (Fairuz) → export best\_model.joblib
     │
     └──► ml/models/best\_model.joblib  (dipakai ETL untuk scoring)
```

## 🚀 Quick Start

### 1\. Clone repo \& setup .env

```bash
git clone https://github.com/dzakialthalsy/telco-churn-analytics.git
cd telco-churn-analytics
cp .env.example .env
```

### 2\. Letakkan dataset

Download dari: https://www.kaggle.com/datasets/abhinav89/telecom-customer  
Simpan ke: `data/raw/telecom\_customer.csv`

### 3\. Cek environment

```bash
python scripts/health\_check.py
```

### 4\. Jalankan Docker (ETL + Metabase)

```bash
docker compose up --build
```

|Service|URL|Keterangan|
|-|-|-|
|Metabase|http://localhost:3000|Dashboard \& visualisasi|

### 5\. Jalankan ETL saja (tanpa Metabase)

```bash
docker compose run --rm etl
```

### 6\. ML Training → Google Colab

Buka notebook di folder `ml/colab/` → upload ke Google Colab → jalankan.  
Export model `.joblib` → simpan ke `ml/models/`.

## 📊 KPI Utama

|KPI|Target|
|-|-|
|Churn Rate|Terpantau real-time di dashboard|
|Retention Rate|≥ 75%|
|AUC-ROC Model|≥ 0.75|
|Akurasi Model|≥ 80%|
|ETL Refresh Time|< 2 jam|

## 🛠️ Tech Stack

|Layer|Tools|
|-|-|
|ETL Pipeline|Python 3.11, pandas, DuckDB|
|Data Warehouse|DuckDB (file-based, mount via Docker volume)|
|ML Training|Google Colab, scikit-learn, imbalanced-learn|
|Dashboard|Metabase (Docker)|
|Containerisasi|Docker \& Docker Compose|

## 📁 Konvensi Branch Git

```
main          → production-ready
develop       → integrasi semua fitur
feature/DE-xx → task Data Engineer (Dhea)
feature/ML-xx → task ML Engineer (Fairuz)
feature/BA-xx → task Analyst (Rifa)
docs/PM-xx    → dokumentasi PM (Dzaki)
```

