/**
 * CyberScout AI — External Scheduler Trigger (Google Apps Script)
 * 
 * Secure time-driven trigger for executing CyberScout AI cybersecurity opportunity intelligence scans.
 * 
 * ARCHITECTURE PRINCIPLE:
 * - Google Apps Script ONLY sends a secure HTTPS trigger to CyberScout AI.
 * - CyberScout AI validates the HMAC-SHA256 signature and executes the scan pipeline.
 * - CyberScout AI server dispatches the intelligence report email via Brevo REST API.
 * - Google Apps Script NEVER touches email credentials or dispatches reports.
 * 
 * SETUP INSTRUCTIONS:
 * 1. Open Google Apps Script: https://script.google.com/
 * 2. Create a new project named "CyberScout AI Scheduler".
 * 3. Copy and paste this code into Code.gs.
 * 4. Configure Script Properties (Project Settings > Script Properties):
 *    - CYBERSCOUT_WEBHOOK_URL: https://cyberscoutai.onrender.com/api/external/scheduler/trigger
 *    - CYBERSCOUT_WEBHOOK_SECRET: <your-secure-shared-secret>
 * 5. Set up a Time-driven Trigger:
 *    - Triggers (alarm icon on left) > Add Trigger
 *    - Function: triggerCyberScoutScan
 *    - Event Source: Time-driven
 *    - Type: Day timer (e.g. Midnight to 1am or configured frequency)
 */

function triggerCyberScoutScan() {
  const scriptProps = PropertiesService.getScriptProperties();
  const url = scriptProps.getProperty("CYBERSCOUT_WEBHOOK_URL") || "https://cyberscoutai.onrender.com/api/external/scheduler/trigger";
  const secret = scriptProps.getProperty("CYBERSCOUT_WEBHOOK_SECRET");

  if (!secret) {
    throw new Error("Missing CYBERSCOUT_WEBHOOK_SECRET in Google Apps Script Properties. Please configure it in Project Settings.");
  }

  const timestamp = Math.floor(Date.now() / 1000).toString();
  const requestId = Utilities.getUuid();

  const payloadObject = {
    event: "scheduled_scan",
    source: "google_apps_script",
    request_id: requestId,
    timestamp: Number(timestamp)
  };

  const body = JSON.stringify(payloadObject);

  // Deterministic HMAC signing payload: timestamp + "." + request_id + "." + raw_body
  const signingPayload = timestamp + "." + requestId + "." + body;

  const signatureBytes = Utilities.computeHmacSha256Signature(signingPayload, secret);
  const signature = "sha256=" + signatureBytes.map(function(byte) {
    const hex = (byte < 0 ? byte + 256 : byte).toString(16);
    return ("0" + hex).slice(-2);
  }).join("");

  console.log("Dispatching CyberScout AI external scan trigger: " + requestId);

  const options = {
    method: "post",
    contentType: "application/json",
    payload: body,
    muteHttpExceptions: true,
    headers: {
      "X-CyberScout-Timestamp": timestamp,
      "X-CyberScout-Request-ID": requestId,
      "X-CyberScout-Signature": signature
    }
  };

  const response = UrlFetchApp.fetch(url, options);
  const statusCode = response.getResponseCode();
  const responseText = response.getContentText();

  console.log("CyberScout AI Response Status: " + statusCode);
  console.log("CyberScout AI Response Body: " + responseText);

  if (statusCode >= 200 && statusCode < 300) {
    console.log("Scan successfully accepted by CyberScout AI (HTTP " + statusCode + ")");
  } else if (statusCode === 409) {
    console.warn("Scan skipped or duplicate trigger (HTTP 409: " + responseText + ")");
  } else {
    throw new Error("CyberScout AI trigger failed with status " + statusCode + ": " + responseText);
  }
}
