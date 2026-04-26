# PM-05 — Feature Prioritization (MoSCoW)

**Task ID:** PM-05  
**Owner:** Dzaki Althalsyah (Product Manager)  
**Sprint:** W2 — Rabu  
**Status:** ✅ Selesai  
**Dependency:** PM-04 (Dashboard requirement alignment)

---

## Konteks

Dokumen ini merupakan output dari task PM-05: memilih fitur wajib yang akan dikerjakan dalam 5 minggu dan mengeluarkan item _nice-to-have_ dari scope aktif. Metode yang digunakan adalah **MoSCoW prioritization framework**.

Keputusan ini diambil berdasarkan:
- PRD Kelompok 4 (Telco Churn Analytics)
- Kapasitas tim: 4 orang × 5 minggu × ~5 jam/hari efektif
- Stack teknis yang sudah ditetapkan: Python, DuckDB, scikit-learn (Colab), Metabase, Docker
- KPI kelulusan minimum: AUC-ROC ≥ 0.75, Accuracy ≥ 80%, ETL refresh < 2 jam

---

## MoSCoW Matrix

### 🔴 Must Have — Wajib selesai dalam 5 minggu

| Task ID | Fitur / Output | Owner | Sprint |
|---------|---------------|-------|--------|
| DE-06 | Docker environment & pipeline setup | Dhea | W2 |
| DE-07 | ETL extraction & staging layer (CSV → staging) | Dhea | W3 |
| DE-08 | Transformasi & data mart build (staging → mart) | Dhea | W3 |
| DE-09 | Tabel output churn risk score per pelanggan | Dhea | W3 |
| DE-10 | Dashboard executive: Churn Rate, ARPU, Revenue Change | Dhea | W4 |
| DE-11 | Dashboard at-risk list & customer drill-down | Dhea | W4 |
| ML-07 | Preprocessing pipeline (impute, encode, scale, split) | Fairuz | W3 |
| ML-08 | Training Decision Tree & Random Forest | Fairuz | W3 |
| ML-09 | Evaluasi model: Accuracy, F1, AUC-ROC | Fairuz | W3 |
| ML-10 | Best model selection & integrasi risk score ke mart | Fairuz | W4 |
| BA-04 | Desain churn rules & risk scoring logic | Rifa | W2 |
| BA-05 | Segmentasi pelanggan & threshold design | Rifa | W2 |
| BA-08 | Validasi rumus KPI turunan | Rifa | W3 |

**Alasan:** Semua item ini adalah inti dari pipeline data → model → dashboard. Tanpa salah satu pun, sistem tidak dapat berfungsi sebagai kesatuan.

---

### 🟡 Should Have — Dikerjakan jika Must Have selesai tepat waktu

| Task ID | Fitur / Output | Owner | Sprint |
|---------|---------------|-------|--------|
| DE-13 | ETL performance & validasi refresh < 2 jam | Dhea | W5 |
| DE-14 | Dashboard final polish & RBAC validation | Dhea | W5 |
| ML-11 | Dokumentasi model & feature importance report | Fairuz | W4 |
| ML-14 | Notebook cleanup & dokumentasi inline | Fairuz | W5 |
| BA-09 | Reason code churn & rekomendasi tindak lanjut | Rifa | W3 |
| BA-12 | Insight signoff & user guide draft | Rifa | W4 |
| DE-12 | Publish-ready integrated build (stabil untuk UAT) | Dhea | W4 |

**Alasan:** Item ini meningkatkan kualitas dan kelengkapan output, tetapi sistem tetap bisa berjalan tanpa mereka jika terjadi keterlambatan di Must Have.

---

### 🔵 Could Have — Dikerjakan hanya jika ada slack time

| Task ID | Fitur / Output | Owner | Sprint |
|---------|---------------|-------|--------|
| BA-11 | Threshold tuning & segment refinement | Rifa | W4 |
| ML-12 | Final performance check pada full dataset | Fairuz | W4 |
| PM-11 | SOP monitoring dashboard & arah handoff | Dzaki | W4 |
| BA-14 | Final insight report & analytic summary | Rifa | W5 |
| DE-15 | Archive final technical artifacts | Dhea | W5 |

---

### ⚫ Won't Have — Dikeluarkan dari scope 5 minggu

Item berikut ini **tidak masuk** dalam deliverable proyek ini. Bukan karena tidak penting, melainkan karena membutuhkan infrastruktur atau waktu di luar kapasitas 5 minggu.

| Fitur | Alasan dikeluarkan |
|-------|--------------------|
| Real-time streaming pipeline (Kafka/Flink) | Butuh infrastruktur tambahan, bukan bagian dari stack yang disepakati |
| Hyperparameter tuning exhaustive (GridSearchCV) | Waktu komputasi tidak terprediksi di scope Colab gratis |
| Multi-model ensemble (stacking/blending) | Kompleksitas tinggi, belum ada baseline yang stabil |
| Scheduled ETL otomatis via cron (cloud deploy) | Butuh server cloud aktif, di luar scope Docker lokal |
| Notifikasi email/Slack otomatis untuk churn alert | Integrasi eksternal, bukan bagian dari deliverable akademik |
| API REST endpoint untuk konsumsi risk score | Tidak ada konsumen API dalam scope proyek ini |
| SHAP/LIME explainability dashboard | Nice-to-have di atas model yang sudah kompleks |

---

## Kontribusi PM ke Tiap Anggota Tim

### → Dhea Akmalia Fibri (BI / Data Engineer)
- **DE-04:** Review & approve skema DWH sebelum build dimulai
- **DE-06:** Pastikan Docker bisa dijalankan semua anggota; bantu debug konflik environment
- **DE-09:** Validasi output tabel churn risk score sesuai format kebutuhan dashboard
- **DE-12:** Sign-off build terintegrasi sebagai gate sebelum UAT dimulai (W4)

### → Fairuz El Fauzy (ML Engineer)
- **ML-04:** Review rancangan pipeline preprocessing — pastikan selaras dengan output ETL Dhea
- **ML-09:** Review laporan evaluasi model sebelum integrasi ke dashboard (gate KPI)
- **ML-10:** Koordinasi format output risk score antara Fairuz dan Dhea (schema alignment)
- **ML-13:** Fasilitasi final acceptance test model di W5 sebagai gatekeeper KPI proyek

### → M. Rifa Aqilla (Business / Data Analyst)
- **BA-03:** Review & sign-off KPI dictionary sebelum Dhea mulai coding mart
- **BA-05:** Mediasi alignment threshold antara logika bisnis Rifa dan output model Fairuz
- **BA-09:** Approve format reason code churn sebelum Dhea memasangnya di halaman drill-down
- **BA-13:** Witness final KPI signoff di W5 — cegah perubahan definisi last-minute

---

## Catatan PM

> Semua item Won't Have didokumentasikan di sini agar tidak hilang. Jika proyek ini dilanjutkan ke iterasi berikutnya, item tersebut menjadi prioritas pertama yang dievaluasi ulang. Gunakan dokumen ini sebagai acuan ketika ada request tambahan fitur di tengah sprint — PM berhak menolak jika tidak masuk dalam Must/Should Have.

---

*Dibuat oleh: Dzaki Althalsyah (PM) — Sprint W2*  
*Disetujui sebagai bagian dari PM-06 Analytics Design Signoff*
