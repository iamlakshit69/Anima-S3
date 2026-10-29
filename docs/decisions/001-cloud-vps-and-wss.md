# Decision 001: Cloud Server Deployment and WSS Transport

- **Date:** 2026-10-29
- **Author:** lakshitsingh & Agent
- **Status:** Approved
- **Affects:** Transport layer, Security, Phase 1 server, Phase 2 firmware

---

## Context
In Section 1.3 and Appendix A of the Architecture Plan, the initial assumption was:
- Transport: `ws://` on a trusted LAN for v1, with `wss://` reserved for later internet exposure.
- Server running locally on the same home network.

During kickoff clarification (Open Item O2), the owner decided that the Python server will be hosted on a cloud VPS/VM, and the ESP32-S3 will connect to it over the public internet via Wi-Fi.

## Options Considered
1. **Option A (Original Plan):** Plain `ws://` on LAN only.
   - *Pros:* Simpler setup initially, no TLS certificates or domain management required.
   - *Cons:* Server cannot be hosted on a remote cloud VM; tokens and audio transmitted in cleartext over the internet if routed outside LAN.
2. **Option B (Approved):** Direct Cloud VPS deployment with TLS (`wss://`).
   - *Pros:* Satisfies the owner's operational deployment model directly; secure token authentication and audio streaming across the internet; avoids a risky plain ws:// over public IP.
   - *Cons:* Server must support SSL/TLS termination (either natively in `websockets` or via reverse proxy like Caddy/Nginx) and firmware must configure root CA certificates or cert pinning.

## Decision
Adopt **Option B**:
- The server will support TLS configuration natively via SSL context or reverse proxy.
- The device token is sent securely via `Authorization: Bearer <device_token>` header over TLS.
- For local fake device tests, both `ws://` and `wss://` will be supported.
- Firmware will include mbedTLS x509 verification or cert bundle.

## Consequences
- Need TLS configuration in `server/anima_server/config.py` (`ssl_certfile`, `ssl_keyfile`, or proxy header trust).
- ESP-IDF config must enable mbedTLS in PSRAM to prevent internal RAM exhaustion.

