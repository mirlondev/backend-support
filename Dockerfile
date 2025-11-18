# ---- WeasyPrint + Django ----
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgobject-2.0-0 libglib2.0-0 libpango-1.0-0 libpangoft2-1.0-0 \
    libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libfontconfig1 \
    shared-mime-info fonts-liberation fonts-dejavu-core fontconfig \
    gcc g++ libpq-dev \
 && fc-cache -fv \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
# on rend start.sh exécutable PEU IMPORTE où il est
RUN find /app -name start.sh -exec chmod +x {} \;

# Railway injecte $PORT automatiquement
CMD ["bash", "/app/start.sh"]