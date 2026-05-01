# AI Handoff Context

Dokumen ini merangkum konteks teknis, perubahan kode, keputusan desain, dan catatan penting pada proyek `KBA-Telecommunication-Company-Churn-Analytics` agar bisa dipakai sebagai handoff ke AI lain atau ke engineer lain tanpa perlu mengulang investigasi dari nol.

## 1. Ringkasan Proyek

- Proyek: `Telco Churn Analytics`
- Lokasi repo: `C:\Users\dzakialthalsyah\Downloads\KBA-Telecommunication-Company-Churn-Analytics`
- Tujuan utama:
  - membangun repositori data analitik berbasis Medallion Architecture
  - mengolah dataset Kaggle telecom customer churn
  - menyajikan tabel bisnis ke Metabase
  - mendukung evaluasi/pemakaian model churn prediction
  - menerapkan RBAC sederhana untuk membatasi akses berdasarkan role pengguna

## 2. Arsitektur Saat Ini

Sistem menggunakan tiga komponen database/storage utama:

1. PostgreSQL catalog
   - Service: `catalog_db`
   - Database: `ducklake_catalog`
   - Fungsi: menyimpan metadata RBAC berupa tabel `roles` dan `users`

2. DuckDB warehouse
   - File utama: `data/gold/telco_warehouse.duckdb`
   - Fungsi: menyimpan data Medallion, tabel mart, dan view serving

3. Metabase internal DB
   - File H2: `metabase.db`
   - Fungsi: metadata internal Metabase, bukan warehouse bisnis utama

## 3. Masalah Awal yang Ditemukan

Saat menjalankan `docker-compose up --build`, service `telco_etl` gagal dengan error DuckDB binder:

`Binder Error: Table "s" does not have a column named "fe_drop_call_flag"`

Penyebabnya:

- `scripts/setup_ducklake.py` membuat `view_operational` dan `view_analyst` yang memilih kolom `s.fe_drop_call_flag`
- tetapi tabel `gold_customer_segments` pada saat itu tidak menurunkan kolom tersebut dari Silver
- di Silver, `fe_drop_call_flag` hanya dibuat jika `drop_vce_Mean` tersedia
- akibatnya, view RBAC mengasumsikan schema yang lebih kaya daripada tabel Gold aktual

## 4. Perubahan yang Sudah Dilakukan

### 4.1. Perbaikan bug `fe_drop_call_flag`

Perubahan pertama dilakukan untuk menghilangkan crash saat inisialisasi RBAC views.

#### File: `etl/layers/gold.py`

Perubahan:

- `fe_drop_call_flag` ditambahkan ke `keep_cols` di fungsi `_build_customer_segments()`
- ini memastikan bila Silver membentuk kolom `fe_drop_call_flag`, kolom tersebut ikut masuk ke `gold.customer_segments`

Alasan:

- view operasional dan analyst memang membutuhkan indikator ini
- sebelumnya kolom tersedia di Silver tetapi hilang di Gold

#### File: `scripts/setup_ducklake.py`

Perubahan:

- ditambahkan helper untuk membaca daftar kolom aktual dari tabel target
- `view_operational` dan `view_analyst` dibuat secara defensif: hanya memilih kolom yang benar-benar tersedia di `gold.customer_segments`

Alasan:

- mencegah startup gagal jika ada kolom fitur yang sifatnya opsional
- membuat pipeline lebih tahan terhadap perubahan schema minor di Silver/Gold

Catatan:

- RBAC view sekarang tidak lagi mengasumsikan semua kolom turunan selalu ada

### 4.2. Refactor schema DuckDB: `bronze`, `silver`, `gold`

Setelah itu dilakukan refactor struktur warehouse supaya layer Medallion tidak hanya dibedakan dengan prefix nama tabel, tetapi benar-benar memakai schema DuckDB terpisah.

#### Sebelum refactor

- `bronze_telecom_raw`
- `silver_telecom_cleaned`
- `gold_customer_segments`
- `gold_churn_risk`
- `gold_churn_summary`

#### Sesudah refactor

- `bronze.telecom_raw`
- `silver.telecom_cleaned`
- `gold.customer_segments`
- `gold.churn_risk`
- `gold.churn_summary`

Alasan refactor:

- pemisahan layer jadi lebih eksplisit
- lebih rapi secara arsitektur
- lebih cocok untuk penjelasan Medallion Architecture di laporan/PRD
- mengurangi ketergantungan pada naming convention prefix saja

## 5. File yang Diubah dan Rinciannya

### 5.1. `etl/layers/bronze.py`

Perubahan:

- menambahkan schema `bronze`
- nama tabel diganti dari flat table menjadi `bronze.telecom_raw`
- menambahkan `CREATE SCHEMA IF NOT EXISTS bronze`
- menambahkan cleanup untuk tabel legacy `bronze_telecom_raw`

Perilaku loading saat ini:

- Bronze masih bersifat `full reload per run`
- tabel di-drop lalu dibuat ulang
- ini berarti implementasi saat ini **bukan append-only historis**

Implikasi:

- kalau ada dokumen/PRD yang menyebut Bronze append-only, itu perlu diperbaiki atau dijelaskan ulang

### 5.2. `etl/layers/silver.py`

Perubahan:

- referensi sumber diubah menjadi `bronze.telecom_raw`
- target tabel diubah menjadi `silver.telecom_cleaned`
- menambahkan schema `silver`
- menambahkan cleanup untuk tabel legacy `silver_telecom_cleaned`

Feature engineering di Silver yang penting:

- `fe_high_care_call`
- `fe_revenue_drop`
- `fe_low_usage`
- `fe_drop_call_flag`
- `fe_churn_risk_rule`

Perkiraan jumlah kolom Silver:

- dataset awal sekitar 100 kolom
- Silver menghapus 11 kolom tidak relevan
- hasil kurasi utama sekitar 89 kolom
- lalu ditambah 5 kolom feature engineering
- total Silver akhir kira-kira sekitar 94 kolom, bergantung pada keberadaan kolom input yang dibutuhkan

### 5.3. `etl/layers/gold.py`

Perubahan:

- sumber Silver diubah menjadi `silver.telecom_cleaned`
- schema `gold` ditambahkan
- target tabel diubah menjadi:
  - `gold.customer_segments`
  - `gold.churn_risk`
  - `gold.churn_summary`
- cleanup ditambahkan untuk nama tabel legacy:
  - `gold_customer_segments`
  - `gold_churn_risk`
  - `gold_churn_summary`
- `fe_drop_call_flag` kini ikut dipertahankan di `gold.customer_segments`

Catatan penting:

- `gold.churn_risk` masih mendukung fallback rule-based jika file ML scores belum tersedia
- `fe_churn_risk_rule` menjadi fallback untuk `ml_churn_score`

### 5.4. `scripts/setup_ducklake.py`

Perubahan:

- helper introspeksi kolom ditambahkan agar view lebih defensif
- referensi tabel Gold diubah menjadi schema-based:
  - `gold.churn_summary`
  - `gold.churn_risk`
  - `gold.customer_segments`
- `view_executive`, `view_operational`, dan `view_analyst` tetap dipertahankan sebagai view serving utama

Peran tiap view:

- `view_executive`
  - hanya KPI agregat
  - sumber: `gold.churn_summary`

- `view_operational`
  - fokus pada data pelanggan berisiko
  - sumber utama: join `gold.churn_risk` dan `gold.customer_segments`

- `view_analyst`
  - akses terluas untuk eksplorasi analitik
  - juga dibangun dari join `gold.churn_risk` dan `gold.customer_segments`

### 5.5. `etl/ducklake_proxy.py`

Perubahan:

- whitelist objek yang diizinkan per role diperbarui ke nama schema-based:
  - `gold.churn_summary`
  - `gold.churn_risk`
  - `gold.customer_segments`
  - `silver.telecom_cleaned`

Role map saat ini:

- `Executive`
  - `view_executive`
  - `gold.churn_summary`

- `Operational`
  - `view_operational`
  - `view_executive`

- `Analyst`
  - `view_analyst`
  - `view_operational`
  - `view_executive`
  - `gold.churn_summary`
  - `gold.churn_risk`
  - `gold.customer_segments`
  - `silver.telecom_cleaned`

Catatan keamanan:

- mekanisme RBAC saat ini adalah RBAC sederhana level aplikasi
- validasi query dilakukan dengan pengecekan substring nama objek pada SQL
- ini cukup untuk proyek akademik/demo
- ini bukan enforcement security enterprise-grade

### 5.6. `etl/run_pipeline.py`

Perubahan:

- log summary diperbarui agar menampilkan nama tabel schema-based:
  - `bronze.telecom_raw`
  - `silver.telecom_cleaned`

### 5.7. `etl/load.py`

Perubahan:

- menambahkan schema `gold`
- `mart_churn_risk` dipindahkan menjadi `gold.mart_churn_risk`
- `etl_run_log` dipindahkan menjadi `gold.etl_run_log`
- cleanup ditambahkan untuk nama tabel lama tanpa schema

### 5.8. `ml/train.py`

Perubahan:

- query training diubah dari `SELECT * FROM mart_churn_risk` menjadi `SELECT * FROM gold.mart_churn_risk`

## 6. Status RBAC terhadap PRD

Ada dua konteks PRD yang sempat dibahas:

1. PRD/laporan teknis panjang
   - fokus pada Medallion, ETL, C4, teknologi, dan kamus data
   - belum cukup eksplisit menjelaskan implementasi RBAC aktual

2. PRD ringkas yang kemudian dijelaskan ulang oleh user
   - sudah menyebut:
     - target audience yang jelas
     - kebutuhan keamanan melalui RBAC
   - secara konseptual, RBAC memang sudah ada di PRD tersebut

Kesimpulan final:

- implementasi RBAC proyek tidak bertentangan dengan PRD ringkas
- role bisnis di PRD ringkas:
  - Manajemen Eksekutif
  - Manager Operasional & Customer Relation
  - Data Analyst / BI Analyst
- implementasi teknis menerjemahkannya menjadi:
  - `Executive`
  - `Operational`
  - `Analyst`

Yang masih disarankan untuk dokumentasi:

- perjelas mapping role ke view/tabel
- perjelas bahwa role enforcement dilakukan lewat PostgreSQL catalog + restricted views DuckDB
- update nama tabel Gold ke schema-based naming

## 7. Catatan tentang Bronze: append-only vs full reload

Poin ini penting karena sempat menjadi bahan evaluasi dokumen.

Kondisi aktual kode:

- Bronze saat ini **bukan append-only**
- Bronze di-refresh ulang setiap pipeline run
- implementasinya lebih dekat ke `full reload raw staging`

Rekomendasi:

- untuk proyek ini, lebih baik dokumentasi yang disesuaikan
- jangan memaksakan append-only bila sistem tidak membutuhkan histori ingest multi-batch

Kalau suatu saat ingin benar-benar append-only:

- perlu `INSERT` alih-alih `DROP + CREATE`
- perlu kolom seperti `batch_id`
- perlu mekanisme dedup / idempotency

## 8. Status Verifikasi

Yang sudah diverifikasi:

- file Python yang diubah berhasil lolos `python -m py_compile`
- referensi schema-based sudah diperbarui di file penting yang disentuh

Yang belum diverifikasi penuh dari sisi runtime oleh agent ini:

- belum ada verifikasi end-to-end penuh hasil `docker-compose up --build` setelah seluruh refactor schema
- belum ada inspeksi langsung ke isi database DuckDB hasil run terbaru
- belum ada pengujian Metabase setelah perubahan nama tabel schema-based

Implikasi:

- kemungkinan besar masih ada file dokumentasi/query/dashboard yang belum diperbarui
- terutama jika ada query hardcoded ke nama tabel lama

## 9. Risiko / Hal yang Perlu Dicek Lanjutan

### 9.1. Dokumentasi

Yang kemungkinan perlu di-update:

- PRD
- laporan teknis
- README
- dokumentasi dashboard/Metabase
- dokumen yang menyebut nama tabel Gold lama

Perubahan yang paling penting untuk dokumen:

- `gold_churn_risk` -> `gold.churn_risk`
- `gold_customer_segments` -> `gold.customer_segments`
- `gold_churn_summary` -> `gold.churn_summary`
- `silver_telecom_cleaned` -> `silver.telecom_cleaned`
- `bronze_telecom_raw` -> `bronze.telecom_raw`

### 9.2. Metabase

Karena Gold sekarang ada dalam schema `gold`, perlu dicek:

- apakah DuckDB driver/Metabase menampilkan schema dengan benar
- apakah pertanyaan/dashboard Metabase yang lama masih menunjuk ke tabel lama
- apakah read-only copy masih konsisten dengan schema baru

### 9.3. Query hardcoded

Perlu dicari bila ada file lain yang masih memakai nama lama:

- `gold_churn_risk`
- `gold_customer_segments`
- `gold_churn_summary`
- `silver_telecom_cleaned`
- `bronze_telecom_raw`
- `mart_churn_risk`

### 9.4. Keamanan RBAC

RBAC sekarang cocok untuk demonstrasi/praktikum, tetapi belum kuat secara keamanan produksi karena:

- validasi akses bersifat string match pada SQL
- tidak memakai native database privilege
- belum ada audit log akses user
- belum ada row-level atau column-level security

Jika proyek berkembang, arah penguatan yang masuk akal:

- native privilege enforcement
- view-only access yang lebih ketat
- per-user connection atau per-role connection
- audit logging
- pembatasan row/column yang lebih granular

## 10. Ringkasan Perubahan yang Paling Penting

Kalau AI lain butuh ringkasan cepat, ini inti perubahannya:

1. Memperbaiki bug ETL startup karena `fe_drop_call_flag` dirujuk di RBAC views tetapi tidak selalu ada di Gold.
2. Menambahkan `fe_drop_call_flag` ke `gold.customer_segments`.
3. Membuat `view_operational` dan `view_analyst` lebih defensif terhadap kolom opsional.
4. Mengubah warehouse DuckDB dari flat table naming ke schema-based Medallion:
   - `bronze.telecom_raw`
   - `silver.telecom_cleaned`
   - `gold.customer_segments`
   - `gold.churn_risk`
   - `gold.churn_summary`
5. Menyesuaikan proxy RBAC, mart loading, dan ML training ke nama tabel baru.
6. Menetapkan bahwa Bronze saat ini adalah full reload, bukan append-only historis.

## 11. Prompt Konteks Singkat untuk AI Lain

Jika ingin memberi konteks cepat ke AI lain, bisa gunakan ringkasan ini:

> Saya sedang mengerjakan proyek `KBA-Telecommunication-Company-Churn-Analytics`. Proyek ini memakai PostgreSQL sebagai catalog RBAC, DuckDB sebagai warehouse utama, Metabase untuk BI, dan Medallion Architecture di DuckDB. Warehouse baru saja direfactor dari nama tabel flat ke schema `bronze`, `silver`, `gold`. Nama tabel aktif sekarang adalah `bronze.telecom_raw`, `silver.telecom_cleaned`, `gold.customer_segments`, `gold.churn_risk`, `gold.churn_summary`, serta `gold.mart_churn_risk`. Sebelumnya ada bug binder di `setup_ducklake.py` karena `fe_drop_call_flag` dirujuk di RBAC view tetapi tidak selalu ada di Gold; bug itu sudah diperbaiki dengan menurunkan kolom ke Gold dan membuat view lebih defensif. RBAC saat ini memakai role `Executive`, `Operational`, `Analyst`, dengan serving views `view_executive`, `view_operational`, dan `view_analyst`. Saya butuh bantuan lanjutan dengan asumsi refactor schema ini sudah terjadi, tetapi runtime end-to-end Docker/Metabase belum diverifikasi penuh.

