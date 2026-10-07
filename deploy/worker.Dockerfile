FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY tools/signing-requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home worker
COPY tools /app/tools
COPY data /app/data
COPY web/legal/manifest.json /app/web/legal/manifest.json
USER 10001
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/tools
CMD ["python", "tools/cloud_worker.py"]
