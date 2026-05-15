FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
        fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY webserver/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY webserver/api/app ./app
COPY frame-firmware ./frame-firmware

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
