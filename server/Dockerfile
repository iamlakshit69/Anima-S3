# syntax=docker/dockerfile:1
# server/Dockerfile — ANIMA-S3 server container image (Hugging Face Spaces & Docker compatible).

FROM python:3.11-slim

# Install system dependencies: libopus for Opus audio codec, curl/ca-certificates for downloads
RUN apt-get update \
    && apt-get install -y --no-install-recommends libopus0 git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set up user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Download quantized Kokoro INT8 ONNX model (~92 MB) and voices (~28 MB) to stay well under 512MB RAM
RUN mkdir -p /app/models \
    && curl -fSL -o /app/models/kokoro-v1.0.int8.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx \
    && curl -fSL -o /app/models/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin

# Copy server code
COPY . ./server/
RUN chown -R appuser:appuser /app

USER appuser
ENV PYTHONPATH=/app/server
ENV KOKORO_MODEL=/app/models/kokoro-v1.0.int8.onnx
ENV KOKORO_VOICES=/app/models/voices-v1.0.bin

# Expose default port
EXPOSE 8765
EXPOSE 7860
EXPOSE 10000

CMD ["python", "-m", "anima_server.main"]
