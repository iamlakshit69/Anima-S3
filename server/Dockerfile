# syntax=docker/dockerfile:1
# server/Dockerfile — ANIMA-S3 server container image (Hugging Face Spaces & Docker compatible).

FROM python:3.11-slim

# Install system dependencies: libopus for Opus audio codec
RUN apt-get update \
    && apt-get install -y --no-install-recommends libopus0 git curl \
    && rm -rf /var/lib/apt/lists/*

# Set up user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY . ./server/
RUN chown -R appuser:appuser /app

USER appuser
ENV PYTHONPATH=/app/server

# Expose default port
EXPOSE 8765
EXPOSE 7860
EXPOSE 10000

CMD ["python", "-m", "anima_server.main"]
