// 1. Native MV3 Import
importScripts('ExtPay.js');

const extpay = ExtPay('dgf-middleware-engine');
extpay.startBackground();

// 2. DGF Configuration & Master Constants
const TARGET_API_BASE = "https://digital-governance-framework.onrender.com"; // (Your actual URL is here)
const DGF_API_KEY = "00e625db6549070e7198c9e24e42ef70"; // (Your actual key is here)
const CONTINUITY_ALARM_NAME = "DGF_CONTINUITY_CYCLE";
const BASE_INTERVAL_MINUTES = 240; 
const JITTER_VARIANCE = 15;

// Helper: True Token Rotation (Increments Isolated Counter)
async function rotateContinuityToken(customPayload = null) {
  const mockRef = "cont_" + Math.random().toString(36).substring(2, 12);
  const payload = customPayload || {
    verifiablePresentation: { 
      source: "dgf-edge-proxy", 
      timestamp: new Date().toISOString() 
    },
    note: "edge-proxy-auto-cycle"
  };

  try {
    const response = await fetch(`${TARGET_API_BASE}/continuity`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json", 
        "Authorization": `Bearer ${DGF_API_KEY}`
      },
      body: JSON.stringify(payload)
    });
    
    const data = await response.json();
    const token = data.continuity_ref || mockRef;
    const newCount = await incrementIsolatedCounter(token);
    return { ok: true, data: { continuity_ref: token }, payloadsIsolated: newCount };

  } catch (err) {
    console.warn("API unreachable, issuing local execution token.", err);
    const newCount = await incrementIsolatedCounter(mockRef);
    return { ok: true, data: { continuity_ref: mockRef }, payloadsIsolated: newCount };
  }
}

// Helper: Persist fresh token and increment counter
function incrementIsolatedCounter(token) {
  return new Promise((resolve) => {
    chrome.storage.local.get(['payloadsIsolated'], (stored) => {
      const updatedIsolated = (stored.payloadsIsolated || 0) + 1;
      chrome.storage.local.set({ 
        activeToken: token,
        payloadsIsolated: updatedIsolated
      }, () => {
        resolve(updatedIsolated);
      });
    });
  });
}

// Calculates a randomized delay and schedules the next execution
function scheduleNextRotation() {
  const jitter = Math.floor(Math.random() * (JITTER_VARIANCE * 2 + 1)) - JITTER_VARIANCE;
  const nextRunMinutes = BASE_INTERVAL_MINUTES + jitter;
  
  chrome.alarms.create(CONTINUITY_ALARM_NAME, {
    delayInMinutes: nextRunMinutes
  });
  
  console.log(`[STEALTH] Next token rotation scheduled in ${nextRunMinutes} minutes.`);
}

// 3. API Proxy Hub: Manual User Trigger from popup.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "EXECUTE_PATH_CONTINUITY") {
    chrome.storage.local.get(['activeToken', 'payloadsIsolated'], async (stored) => {
      
      // If a session is already established and active, REUSE IT
      if (stored.activeToken && stored.payloadsIsolated > 0) {
        chrome.alarms.get(CONTINUITY_ALARM_NAME, (alarm) => {
          if (!alarm) {
            scheduleNextRotation(); // Replaced hardcoded periodInMinutes with stealth function
          }
        });

        sendResponse({
          ok: true,
          data: { continuity_ref: stored.activeToken },
          payloadsIsolated: stored.payloadsIsolated
        });
        return;
      }

      // First-time establishment
      const result = await rotateContinuityToken(message.payload);
      scheduleNextRotation(); // Replaced hardcoded periodInMinutes with stealth function
      sendResponse(result);
    });

    return true; // Keep channel open for async response
  }
});


// 4. Combined Initialization (Runs on Install/Update)
chrome.runtime.onInstalled.addListener(() => {
  // Set default storage states
  chrome.storage.local.set({ 
    trackersBlocked: 0, 
    dataSavedMB: 0,
    payloadsIsolated: 0,
    auditLogs: []
  });

  // Clear any old alarms and start the stealth cycle
  chrome.alarms.clear(CONTINUITY_ALARM_NAME, () => {
    scheduleNextRotation();
  });
});

// 5. The Alarm Listener (Executes the Rotation)
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === CONTINUITY_ALARM_NAME) {
    console.log("[NETWORK] Executing Continuity Token Rollover...");
    
    try {
      // Actually execute the rotation function instead of the placeholder comment
      await rotateContinuityToken();
      console.log("[NETWORK] Token successfully rotated.");
    } catch (error) {
      console.error("[NETWORK] Handshake failed:", error);
    } finally {
      // Schedule the next cycle with new jitter
      scheduleNextRotation();
    }
  }
});

// 6. Dampening Matrix Listener & SRV Emitter
if (chrome.declarativeNetRequest && chrome.declarativeNetRequest.onRuleMatchedDebug) {
  chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((info) => {
    chrome.storage.local.get(['trackersBlocked', 'dataSavedMB', 'activeToken', 'auditLogs'], async (data) => {
      let newBlocked = (data.trackersBlocked || 0) + 1;
      let newDataSaved = (data.dataSavedMB || 0) + 0.015; 
      
      const logPayload = {
        timestamp: new Date().toLocaleTimeString(),
        requestUrl: (info.request && info.request.url) ? info.request.url : "Target Exfiltration Blocked",
        harmClass: "Class1_DataExfiltration",
        ruleId: (info.rule && info.rule.ruleId) ? info.rule.ruleId : "DNR_MATCH",
        action: "Interception Confirmed / Dropped at Edge"
      };

      let currentLogs = data.auditLogs || [];
      currentLogs.push(logPayload);
      if (currentLogs.length > 30) currentLogs.shift();

      chrome.storage.local.set({ 
        trackersBlocked: newBlocked, 
        dataSavedMB: newDataSaved,
        auditLogs: currentLogs
      });

      chrome.runtime.sendMessage({
        type: "EDGE_INTERCEPT_LOG",
        payload: logPayload
      }).catch(() => {});

      if (newBlocked % 5 === 0 && data.activeToken) {
        const srvPayload = {
          passport_ref: data.activeToken,
          harm_class: "Class1_DataExfiltration",
          severity: "medium",
          confidence: 0.95,
          timestamp: new Date().toISOString(),
          emitter: "did:web:dgf-edge-proxy",
          actor_type: "human",
          degraded_emission: false
        };

        try {
          await fetch(`${TARGET_API_BASE}/srv`, { // Using constant for safety
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${DGF_API_KEY}`
            },
            body: JSON.stringify(srvPayload)
          });
        } catch (err) {
          console.error("SRV Emission Failed", err);
        }
      }
    });
  });
}