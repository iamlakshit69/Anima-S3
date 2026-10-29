# WSS / TLS Setup Guide

This guide explains how to configure the ANIMA-S3 server for secure WebSocket connections
(`wss://`) using TLS, and how to point the ESP32-S3 firmware at the TLS endpoint.

---

## TLS Status in the Server

TLS is already wired in `server/anima_server/main.py`.
When `SSL_CERTFILE` and `SSL_KEYFILE` are both set in `.env` (or the environment),
the server creates an `ssl.SSLContext` and passes it to `websockets.serve()`:

```python
ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(cfg.ssl_certfile, keyfile=cfg.ssl_keyfile)
```

The device WebSocket port then accepts `wss://` connections.

---

## Option A — Self-Signed Certificate (Development / Home LAN)

> [!WARNING]
> Self-signed certificates are **not trusted by browsers or by the ESP32 default CA store**.
> You must embed the certificate in the firmware (see below). Do not use in production.

### 1. Generate the certificate

```bash
openssl req -x509 -newkey rsa:2048 -keyout server.key -out server.crt \
    -sha256 -days 365 -nodes \
    -subj "/CN=anima-server" \
    -addext "subjectAltName=IP:192.168.1.100,DNS:anima.local"
```

Replace `192.168.1.100` with the actual server IP.

### 2. Configure the server

Add to your `.env` file:

```dotenv
SSL_CERTFILE=/path/to/server.crt
SSL_KEYFILE=/path/to/server.key
```

Restart the server:

```bash
cd server
PYTHONPATH=. ../.venv/bin/python -m anima_server.main
# Server log should say: TLS enabled with certfile=...
```

Verify the endpoint:

```bash
openssl s_client -connect 192.168.1.100:8765 -CAfile server.crt
```

---

## Option B — Let's Encrypt / Public CA (Production / Cloud VPS)

> [!TIP]
> Use [Certbot](https://certbot.eff.org/) with the `--standalone` plugin if port 80 is free,
> or the DNS-01 challenge if a reverse proxy is in use.

```bash
sudo certbot certonly --standalone -d anima.example.com
# Certificates land in /etc/letsencrypt/live/anima.example.com/
```

Add to `.env`:

```dotenv
SSL_CERTFILE=/etc/letsencrypt/live/anima.example.com/fullchain.pem
SSL_KEYFILE=/etc/letsencrypt/live/anima.example.com/privkey.pem
```

Let's Encrypt certificates are already trusted by the ESP-IDF CA bundle, so no
firmware change is needed.

---

## ESP32 Firmware Configuration

### Option B (Public CA)

ESP-IDF includes Mozilla's CA bundle by default. No extra steps needed.

In `firmware/main/config.h`, set:

```c
#define CONFIG_SERVER_URL "wss://anima.example.com:8765/v1/device"
```

### Option A (Self-Signed)

The self-signed `server.crt` must be embedded in the firmware so the TLS stack
can verify the server.

1. **Copy the PEM file into the firmware tree:**

   ```bash
   cp /path/to/server.crt firmware/main/certs/server_cert.pem
   ```

2. **Embed via ESP-IDF `EMBED_TXTFILES` in `CMakeLists.txt`:**

   ```cmake
   idf_component_register(
       SRCS "main.cc" ...
       EMBED_TXTFILES "certs/server_cert.pem"
   )
   ```

3. **Pass the certificate to `esp_websocket_client_config_t`:**

   ```c
   extern const uint8_t server_cert_pem_start[] asm("_binary_server_cert_pem_start");
   extern const uint8_t server_cert_pem_end[]   asm("_binary_server_cert_pem_end");

   esp_websocket_client_config_t ws_cfg = {
       .uri = CONFIG_SERVER_URL,
       .cert_pem = (const char*)server_cert_pem_start,
   };
   ```

> [!CAUTION]
> Certificate pin information (GPIO, SPI) in `docs/HARDWARE.md` is the authoritative source.
> Never flash the device without human approval (Rule R15, AGENTS.md §7).

---

## Docker / Reverse Proxy (recommended for production)

Run NGINX or Caddy in front of the WebSocket server. NGINX example:

```nginx
stream {
    server {
        listen 443 ssl;
        ssl_certificate     /etc/letsencrypt/live/anima.example.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/anima.example.com/privkey.pem;
        proxy_pass 127.0.0.1:8765;
    }
}
```

In this case, set `SSL_CERTFILE=` (empty) in `.env` so the Python server listens on
plain `ws://` at `127.0.0.1:8765` and TLS termination is handled by NGINX.

---

## Quick Reference

| Scenario | `SSL_CERTFILE` | `SSL_KEYFILE` | ESP32 cert needed |
|---|---|---|---|
| Dev / no TLS | *(empty)* | *(empty)* | No |
| Self-signed | `/path/to/server.crt` | `/path/to/server.key` | Yes — embed PEM |
| Let's Encrypt | `/etc/letsencrypt/.../fullchain.pem` | `/etc/letsencrypt/.../privkey.pem` | No |
| NGINX proxy | *(empty)* | *(empty)* | Depends on CA |

