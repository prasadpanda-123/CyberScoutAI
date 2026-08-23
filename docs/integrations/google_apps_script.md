# CyberScout AI — External Scheduler Integration Guide (Google Apps Script)

## Overview
CyberScout AI uses an **External Scheduler Architecture** where Google Apps Script serves as the authoritative time-driven trigger.

```
GOOGLE APPS SCRIPT
       │
       │ Secure HTTPS POST (HMAC-SHA256 Signed)
       ▼
/api/external/scheduler/trigger
       │
       ▼
Authentication Layer (HMAC & ±5m Timestamp Guard)
       │
       ▼
Replay & Concurrency Protection (PostgreSQL Lock)
       │
       ▼
CyberScout Scan Pipeline (Collect → Deduplicate → Rank → Persist)
       │
       ▼
Server-Side Intelligence Report Generation
       │
       ▼
Server-Side Email Dispatch via Brevo REST API (HTTPS/443)
       │
       ▼
Administrator / Subscribers
```

> **CRITICAL SECURITY BOUNDARY:**
> - Google Apps Script **ONLY triggers** the scan endpoint.
> - The CyberScout AI web server **executes the scan and sends the email**.
> - Google Apps Script never holds Brevo credentials or dispatches reports.

---

## 1. Environment Configuration

### Server Environment Variables (Render Web Service)
Ensure the following variables are configured in Render:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `SCHEDULER_WEBHOOK_SECRET` | Shared high-entropy HMAC-SHA256 secret | `e.g. 64-character random hex string` |
| `EMAIL_PROVIDER` | Production email provider | `brevo` |
| `BREVO_API_KEY` | Render secret Brevo API Key | `xkeysib-...` |
| `EMAIL_FROM` | Verified Brevo sender address | `notifications@yourdomain.com` |

---

## 2. Google Apps Script Setup

1. Open [Google Apps Script](https://script.google.com/).
2. Create a new project: **CyberScout AI Scheduler**.
3. Paste the contents of [`scripts/google_apps_script_trigger.js`](file:///d:/VibeCoding/CyberScout%20AI/CyberScoutAI/scripts/google_apps_script_trigger.js) into `Code.gs`.
4. Open **Project Settings** (gear icon on the left navigation) &rarr; **Script Properties**:
   - `CYBERSCOUT_WEBHOOK_URL`: `https://cyberscoutai.onrender.com/api/external/scheduler/trigger`
   - `CYBERSCOUT_WEBHOOK_SECRET`: *(Same secret configured in Render)*
5. Configure the Time-Driven Trigger:
   - Navigate to **Triggers** (alarm clock icon).
   - Click **+ Add Trigger**.
   - Choose function to run: `triggerCyberScoutScan`.
   - Select event source: `Time-driven`.
   - Select type: `Day timer` (e.g. `Midnight to 1am`).

---

## 3. Manual Testing & Verification

### Python Manual Trigger Script
Run from the repository root:
```python
import hashlib, hmac, json, os, time, uuid, requests

secret = os.getenv("SCHEDULER_WEBHOOK_SECRET", "test_secret_key")
url = "http://localhost:5000/api/external/scheduler/trigger"

timestamp = str(int(time.time()))
request_id = f"test-{uuid.uuid4()}"
body = json.dumps({
    "event": "scheduled_scan",
    "source": "manual_test_script",
    "request_id": request_id,
    "timestamp": int(timestamp),
    "dry_run": True
})

signing_payload = f"{timestamp}.{request_id}.{body}"
signature = "sha256=" + hmac.new(secret.encode(), signing_payload.encode(), hashlib.sha256).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-CyberScout-Timestamp": timestamp,
    "X-CyberScout-Request-ID": request_id,
    "X-CyberScout-Signature": signature
}

resp = requests.post(url, headers=headers, data=body)
print(f"Status: {resp.status_code}, Response: {resp.json()}")
```
