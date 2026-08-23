/**
 * ============================================================================
 * CYBERSCOUT AI — SECURE GOOGLE APPS SCRIPT EXTERNAL TRIGGER
 * ============================================================================
 *
 * File: docs/google_apps_script_scheduler.gs
 * Description: Time-driven external trigger for CyberScout AI opportunity scanning.
 *
 * IMPORTANT ARCHITECTURE RULES:
 * 1. This script ONLY triggers the server-side scan endpoint.
 * 2. This script NEVER sends email or calls MailApp/GmailApp.
 * 3. This script NEVER stores or handles Brevo credentials.
 * 4. CyberScout AI executes the scan pipeline and dispatches daily reports
 *    directly from the server via Brevo after scan completion.
 *
 * ============================================================================
 */

// Configuration Constants
var CYBERSCOUT_CONFIG = {
  // Update this to your production Render URL or custom domain
  ENDPOINT_URL: 'https://cyberscoutai.onrender.com/api/scheduler/trigger',
  
  // Property keys in ScriptProperties
  PROPERTY_SECRET_KEY: 'CYBERSCOUT_SCHEDULER_SECRET',
  PROPERTY_ENDPOINT_KEY: 'CYBERSCOUT_WEBHOOK_URL'
};

/**
 * Helper: Generate a cryptographically random UUID/nonce.
 */
function generateNonce_() {
  return Utilities.getUuid();
}

/**
 * Helper: Compute HMAC-SHA256 signature in lowercase hexadecimal.
 * Canonical string format: <timestamp>.<nonce>.<raw_json_body>
 */
function computeHmacSignature_(secret, canonicalString) {
  var rawHash = Utilities.computeHmacSha256Signature(canonicalString, secret);
  var hexString = rawHash.map(function(byte) {
    var v = (byte < 0 ? byte + 256 : byte).toString(16);
    return v.length === 1 ? '0' + v : v;
  }).join('');
  return 'sha256=' + hexString;
}

/**
 * 1. Store the shared HMAC secret securely in Script Properties.
 * Run this function once manually in the Apps Script Editor.
 */
function setSchedulerSecret(secretValue) {
  var secret = secretValue || 'REPLACE_WITH_YOUR_LONG_RANDOM_SECRET';
  if (secret === 'REPLACE_WITH_YOUR_LONG_RANDOM_SECRET') {
    Logger.log('ERROR: Please provide a valid high-entropy secret string.');
    return;
  }
  var props = PropertiesService.getScriptProperties();
  props.setProperty(CYBERSCOUT_CONFIG.PROPERTY_SECRET_KEY, secret.trim());
  props.setProperty(CYBERSCOUT_CONFIG.PROPERTY_ENDPOINT_KEY, CYBERSCOUT_CONFIG.ENDPOINT_URL);
  Logger.log('SUCCESS: CyberScout scheduler secret configured securely in Script Properties.');
}

/**
 * 2. Primary Scan Trigger function called by Time-Driven Trigger.
 * Sends an HMAC-SHA256 authenticated HTTPS POST request to CyberScout AI.
 */
function triggerCyberScoutScan() {
  var props = PropertiesService.getScriptProperties();
  var secret = props.getProperty(CYBERSCOUT_CONFIG.PROPERTY_SECRET_KEY);
  var endpointUrl = props.getProperty(CYBERSCOUT_CONFIG.PROPERTY_ENDPOINT_KEY) || CYBERSCOUT_CONFIG.ENDPOINT_URL;

  if (!secret) {
    Logger.log('ERROR: ' + CYBERSCOUT_CONFIG.PROPERTY_SECRET_KEY + ' is not set in Script Properties.');
    return { success: false, error: 'Missing secret property' };
  }

  // 1. Prepare timestamp & nonce
  var timestamp = Math.floor(new Date().getTime() / 1000).toString();
  var nonce = generateNonce_();

  // 2. Construct canonical payload body
  var payloadObj = {
    trigger: 'google_apps_script',
    source: 'google_apps_script',
    event: 'daily_scheduled_scan',
    nonce: nonce,
    request_id: nonce,
    requested_at: new Date().toISOString(),
    send_empty_report: false
  };
  var rawBody = JSON.stringify(payloadObj);

  // 3. Compute HMAC-SHA256 signature
  var canonicalString = timestamp + '.' + nonce + '.' + rawBody;
  var signature = computeHmacSignature_(secret, canonicalString);

  // 4. Dispatch HTTPS POST request
  var options = {
    method: 'post',
    contentType: 'application/json',
    payload: rawBody,
    headers: {
      'X-CyberScout-Timestamp': timestamp,
      'X-CyberScout-Nonce': nonce,
      'X-CyberScout-Request-ID': nonce,
      'X-CyberScout-Signature': signature
    },
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(endpointUrl, options);
    var statusCode = response.getResponseCode();
    var responseBody = response.getContentText();

    Logger.log('CyberScout Trigger Response Code: ' + statusCode);
    Logger.log('CyberScout Trigger Response Body: ' + responseBody);

    return {
      success: statusCode === 200 || statusCode === 202,
      statusCode: statusCode,
      response: responseBody
    };
  } catch (err) {
    Logger.log('ERROR contacting CyberScout AI: ' + err.toString());
    return {
      success: false,
      error: err.toString()
    };
  }
}

/**
 * 3. Set up an automated daily time-driven trigger.
 * Example: Runs every morning between 6:00 AM and 7:00 AM.
 */
function createDailyTrigger() {
  // Remove existing triggers to prevent duplicates
  deleteCyberScoutTriggers();

  ScriptApp.newTrigger('triggerCyberScoutScan')
    .timeBased()
    .everyDays(1)
    .atHour(6) // 6:00 AM in your Google Apps Script project timezone
    .create();

  Logger.log('SUCCESS: Daily CyberScout time-driven trigger created for 06:00 AM.');
}

/**
 * 4. Remove all existing triggers for triggerCyberScoutScan.
 */
function deleteCyberScoutTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  var count = 0;
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'triggerCyberScoutScan') {
      ScriptApp.deleteTrigger(triggers[i]);
      count++;
    }
  }
  Logger.log('Deleted ' + count + ' existing CyberScout trigger(s).');
}

/**
 * 5. Test function to manually verify connection and HMAC authentication.
 */
function testCyberScoutTrigger() {
  Logger.log('Starting CyberScout trigger test...');
  var result = triggerCyberScoutScan();
  Logger.log('Test result: ' + JSON.stringify(result));
}
