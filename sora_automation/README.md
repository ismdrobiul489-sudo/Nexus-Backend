# Sora Automation PoC - Summary & Guide

This project explores the feasibility of automating video generation on Sora.com. Due to advanced security measures (Cloudflare, Sentinel tokens, regional locks), we shifted from direct API interaction to a **Session-based Playwright Automation** strategy.

## Status
- **Phase 1: API Exploration (Completed):** Identified key endpoints (`/backend/nf/create`, `/backend/nf/pending/v2`) and the necessity of Bearer tokens, Cookies, and Sentinel tokens. 
- **Phase 2: Security Challenges (Identified):** OpenAI uses TLS fingerprinting and regional blocks (e.g., Bangladesh is restricted).
- **Phase 3: Playwright Solution (Implemented):** Developed a suite that bypasses API security by using a real browser state.

## Files Created
1. `test_sora.py`: The original API-based script (Advanced TLS impersonation via `curl_cffi`).
2. `save_session.py`: Captures a manual login session (cookies, storage) into `auth_state.json`.
3. `auto_generate.py`: Uses the saved session to generate videos headlessly (mimicking a logged-in user).
4. `sora.txt`: Log of valid headers/traces from a successful browser session.

## How to Resume Work

### 1. Prerequisite
Ensure you have a **UK/US VPN** active on your local machine.

### 2. Capture Session
Run this on your local machine to log in and save the session:
```bash
python sora_automation/save_session.py
```
*Wait for the Chromium window to open, log in manually, and wait for it to reach the profile page.*

### 3. Automated Generation
Once `auth_state.json` is generated, you can run headless generation anywhere (including Docker):
```bash
python sora_automation/auto_generate.py
```

## Future Architecture (Hugging Face Docker)
To deploy this on Hugging Face:
1. Include `auth_state.json` in your repository.
2. Ensure `playwright` and `chromium` are installed in the Dockerfile.
3. Expose a REST API (FastAPI) that triggers `auto_generate.py`.

---
*Work paused as of Feb 09, 2026. Documentation ready for future handover.*
