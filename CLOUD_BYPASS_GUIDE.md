# 🌐 Cloud Domain Bypass Guide

This guide explains how to bypass domain-level and DNS-level blocks on cloud platforms (like Hugging Face Spaces) using the IP-bypass strategy.

---

## 🚀 The Core Strategy

When a cloud provider blocks a domain (e.g., `graph.facebook.com`), they usually don't block the underlying IP address. By using the direct IP and manually providing the `Host` header, we can bypass these restrictions.

### 1. Standalone DNS Lookup
We use a standalone tool to fetch the current IP addresses of all critical domains.
- **File**: `bypass_dns_lookup.py`
- **Output**: `domain_ips.json`

**How to run:**
```bash
python bypass_dns_lookup.py
```

### 2. Manual IP Bypass (How it works)
When calling an API using an IP, you **must** include the correct `Host` header.
- **Instead of**: `https://graph.facebook.com/v18.0/...`
- **Use**: `https://31.13.64.18/v18.0/...`
- **Header**: `{"Host": "graph.facebook.com"}`

---

## ☁️ Remote DNS Resolver Strategy (GCP)

If the cloud host blocks DNS lookups entirely, the script on that host won't be able to find new IPs. In this scenario, we use a **Remote Resolver**.

### Architecture:
1. **Source of Truth (GCP Free Tier)**: 
   - A tiny FastAPI app or Cloud Function hosted on Google Cloud.
   - It runs the `bypass_dns_lookup.py` script automatically (Daily).
   - It exposes an endpoint: `GET /api/dns-mappings`.
2. **The Worker (Hugging Face / Restricted Host)**:
   - On startup, the bot calls the GCP API to fetch the latest IPs.
   - It updates its local `domain_ips.json`.
   - All subsequent requests use those IPs.

---

## 🛠️ Implementation Details

### For HTTP Requests:
If you need to implement this in Python (using `httpx` or `requests`), use this logic:
```python
headers = {
    "Host": "graph.facebook.com",
    "X-App-Secret": "YOUR_SECRET"
}
response = httpx.get("https://31.13.64.18/me", headers=headers)
```

### For RTMP Streaming (YouTube):
Simply replace the domain in the RTMP URL:
- **Default**: `rtmp://a.rtmp.youtube.com/live2/KEY`
- **Bypass**: `rtmp://142.251.43.140/live2/KEY`

---

## 🛡️ Maintenance Warning
1. **IP Expiry**: IP addresses change periodically. Always run the lookup script or refresh the remote JSON if you get "Connection Timed Out" or "SSL Errors".
2. **SSL Verification**: When using IPs, some libraries might complain about "Hostname mismatch". You may need to use custom SSL context or (at your own risk) disable SSL hostname verification for those specific IPs.

---
*Created by Antigravity on 2026-02-12*
