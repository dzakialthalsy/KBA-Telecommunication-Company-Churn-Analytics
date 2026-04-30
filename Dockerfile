FROM python:3.11-slim

LABEL maintainer="Kelompok 4 - Kecerdasan Bisnis dan Analitik"
LABEL description="Telco Churn Analytics — ETL Pipeline"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/raw data/staging data/gold ml/models ml/reports

# Berikan permission execute pada entrypoint
RUN chmod +x /app/scripts/entrypoint.sh

# Gunakan CMD (bukan ENTRYPOINT) agar docker-compose tidak konflik
CMD ["/app/scripts/entrypoint.sh"]
