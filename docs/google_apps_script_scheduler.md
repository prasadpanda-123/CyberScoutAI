# CyberScout AI — Google Apps Script External Scheduler Guide

This guide details the architecture, setup instructions, and security model for triggering CyberScout AI opportunity scans using **Google Apps Script** as a reliable external time-driven scheduler.

---

## 1. Architecture Overview

```
                 GOOGLE APPS SCRIPT (Time-Driven Trigger)
                                    │
                                    │ HTTPS POST /api/scheduler/trigger
                                    │ Headers: X-CyberScout-Timestamp, X-CyberScout-Nonce, X-CyberScout-Signature
                                    ▼
                     [ Authentication & Security Guard ]
                     ├── 1. HMAC-SHA256 Verification (hmac.compare_digest)
                     ├── 2. Timestamp Window Validation (±300 seconds)
                     ├── 3. Replay Protection (Unique Nonce in PostgreSQL)
                     └── 4. Concurrency Guard (Server Scan Lock)
                                    │
                                    ▼
                        [ Pipeline Scan Execution ]
                     ├── Collect → Extract → Clean → Deduplicate → Rank → Persist
                                    │
                                    ▼
                        [ Persistence Verified ]
                                    │
                         ┌──────────┴──────────┐
                      SUCCESS                FAILED
                         │                     │
                         ▼                     ▼
             [ Chained Email Dispatch ]     [ Log Failure ]
             ├── Generate Daily Digest      [ Bypass Email ]
             └── Brevo REST API (HTTPS/443)
                         │
                         ▼
                 [ Recipient Inbox ]
```

> [!IMPORTANT]
> **Google Apps Script triggers the scan only.**
> CyberScout AI executes the discovery pipeline and dispatches the report email directly from the server after scan completion via Brevo REST API. Google Apps Script **never** sends emails and **never** handles Brevo credentials.

---

## 2. Environment Variable Configuration

On your server deployment (e.g., Render Dashboard &rarr; Environment), configure the shared HMAC secret:

| Variable | Description | Example / Format |
|---|---|---|
| `CYBERSCOUT_SCHEDULER_SECRET` | High-entropy shared secret key | `64-character random hex string` |
| `EMAIL_PROVIDER` | Production email provider | `brevo` |
| `BREVO_API_KEY` | Brevo REST API v3 Key | `xkeysib-...` |
| `EMAIL_FROM` | Verified sender address in Brevo | `alerts@yourdomain.com` |
| `EMAIL_TO` | Target recipient list / dynamic admin | `admin@yourdomain.com` |

---

## 3. Google Apps Script Setup (Step-by-Step)

### Step 1: Create an Apps Script Project
1. Open [Google Apps Script](https://script.google.com/).
2. Click **New Project** and name it `CyberScout AI Scheduler`.

### Step 2: Paste the Reference Code
Copy the contents of [`docs/google_apps_script_scheduler.gs`](google_apps_script_scheduler.gs) into `Code.gs`.

### Step 3: Configure Secret in Script Properties
1. In the Apps Script Editor, go to **Project Settings** (gear icon) &rarr; **Script Properties**.
2. Add a new Script Property:
   - **Property**: `CYBERSCOUT_SCHEDULER_SECRET`
   - **Value**: `<Paste the same secret set in your Render environment>`
3. (Optional) Add `CYBERSCOUT_WEBHOOK_URL` if using a custom domain or custom path:
   - **Property**: `CYBERSCOUT_WEBHOOK_URL`
   - **Value**: `https://cyberscoutai.onrender.com/api/scheduler/trigger`

Alternatively, you can run the `setSchedulerSecret("your-secret-here")` function once from the editor.

### Step 4: Test the Connection
1. Select the `testCyberScoutTrigger` function from the dropdown.
2. Click **Run**.
3. View **Execution log** (`Ctrl + Enter` / `Cmd + Enter`).
4. You should see `CyberScout Trigger Response Code: 202` with body `{"status": "accepted", "message": "CyberScout scan accepted.", ...}`.

### Step 5: Activate Automated Daily Trigger
1. Select `createDailyTrigger` from the dropdown and click **Run**.
2. This creates a native Google time-driven trigger configured for your desired time (e.g., 6:00 AM daily).

---

## 4. Endpoints Specification

### POST `/api/scheduler/trigger` (or `/api/external/scheduler/trigger`)
- **Headers:**
  - `Content-Type`: `application/json`
  - `X-CyberScout-Timestamp`: UNIX timestamp in seconds
  - `X-CyberScout-Nonce`: Cryptographic UUID/nonce
  - `X-CyberScout-Signature`: `sha256=<hmac-hex-digest>`
- **Body:**
  ```json
  {
    "trigger": "google_apps_script",
    "requested_at": "2026-08-24T00:00:00.000Z",
    "nonce": "b3c9f268-d069-4e78-9e54-52fa95e4e892"
  }
  ```
- **Responses:**
  - `HTTP 202 Accepted`: Scan accepted for execution (`{"status": "accepted", "run_id": "...", "message": "CyberScout scan accepted."}`)
  - `HTTP 401 Unauthorized`: Invalid HMAC signature or expired timestamp window (> &plusmn;300s)
  - `HTTP 409 Conflict`: Nonce replay detected or scan already active

### GET `/api/scheduler/status`
- Returns public telemetry on scheduler mode, trigger source, and last execution state.

---

## 5. Security Model

1. **HMAC-SHA256 Signature**: The request payload and timestamp are hashed using `CYBERSCOUT_SCHEDULER_SECRET`. Constant-time comparison `hmac.compare_digest()` prevents timing attacks.
2. **Replay Protection**: Every incoming `nonce` / `request_id` is tracked in PostgreSQL table `scheduler_webhook_requests`. Duplicate requests return `HTTP 409`.
3. **Drift Protection**: Requests with timestamps older than 300 seconds (&plusmn;5 minutes) are immediately rejected (`HTTP 401`).
4. **Concurrency Lock**: Prevents overlapping scans with `scan_job_manager.is_scan_active()`.
5. **No Credential Exposure**: Logs and API responses never expose secrets, API keys, or signatures.
