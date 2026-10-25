# Litmus worker. Build from the repository root:
#   docker build -f worker/Dockerfile -t litmus-worker .
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY core /app/core
COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir /app/core \
 && grep -v -e '^-e' -e '^pytest' -e '^httpx' /app/worker/requirements.txt > /tmp/requirements.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt

COPY db /app/db
COPY worker /app/worker
WORKDIR /app/worker

ENV MEDIA_DIR=/data/media PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "litmus_worker.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
