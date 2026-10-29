# syntax=docker/dockerfile:1
# server/Dockerfile — ANIMA-S3 server container image.
#
# Build:
#   docker build -t anima-server -f server/Dockerfile server/
# Run:
#   docker run --env-file server/.env -p 8765:8765 -p 8766:8766 anima-server

FROM python:3.11-slim

# System dependencies: libopus for opuslib codec bindings
RUN apt-get update \
    && apt-get install -y --no-install-recommends libopus0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy server package first so pip can resolve deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full server package
COPY . ./server/
ENV PYTHONPATH=/app/server

EXPOSE 8765
EXPOSE 8766

CMD ["python", "-m", "anima_server.main"]

