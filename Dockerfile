FROM python:3.12-slim

# Dependencias del sistema para Pillow y lxml.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    zlib1g \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

# Carpeta para la base de datos (se monta como volumen en el NAS).
RUN mkdir -p /app/data
VOLUME ["/app/data"]

CMD ["python", "-m", "bot.main"]
