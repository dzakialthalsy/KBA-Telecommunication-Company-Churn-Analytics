# 🧪 Google Colab Notebooks — ML Pipeline

Folder ini berisi notebook `.ipynb` yang dijalankan di **Google Colab**.
Upload ke Google Drive lalu buka dengan Colab.

## Urutan Pengerjaan

| File | Task | Owner | Deskripsi |
|---|---|---|---|
| `01_EDA.ipynb` | ML-01, ML-02 | Fairuz | Exploratory Data Analysis + distribusi churn |
| `02_Preprocessing.ipynb` | ML-04, ML-05, ML-07 | Fairuz | Cleaning, encoding, feature selection, train-test split |
| `03_Model_Training.ipynb` | ML-08 | Fairuz | Training LR, Decision Tree, Random Forest |
| `04_Model_Evaluation.ipynb` | ML-09 | Fairuz | Evaluasi: Accuracy, F1, AUC-ROC, confusion matrix |
| `05_Export_Scores.ipynb` | ML-10 | Fairuz | Export churn risk score ke CSV → dipakai ETL (DE-09) |

## Setup Colab (jalankan di cell pertama setiap notebook)

```python
# Install packages yang tidak ada di Colab by default
!pip install duckdb imbalanced-learn --quiet

# Mount Google Drive (opsional, untuk simpan model)
from google.colab import drive
drive.mount('/content/drive')
```

## Cara Upload Dataset ke Colab

```python
from google.colab import files
uploaded = files.upload()   # upload telecom_customer.csv dari lokal

import pandas as pd
df = pd.read_csv('telecom_customer.csv')
print(df.shape)
```

## Export Model ke Lokal (untuk dipakai ETL Docker)

```python
import joblib
joblib.dump(best_model, 'best_model.joblib')
files.download('best_model.joblib')
# → simpan ke ml/models/best_model.joblib di repo GitHub
```
