const extpay = ExtPay('dgf-middleware-engine');

document.addEventListener("DOMContentLoaded", async () => {
  const btnEstablish = document.getElementById("btn-establish");
  const btnUpgrade = document.getElementById("btn-upgrade");
  const continuityStatus = document.getElementById("continuity-status");
  const ledgerBlock = document.getElementById("ledger-block");
  const modeBadge = document.querySelector(".mode-badge");
  const btnTerminal = document.getElementById("btn-audit");

  let isProUser = false;
  let telemetryInterval = null;
  let toastTimeout = null;
  let thresholdAlertTriggered = false;

  // 1. Verify Monetization Status
  try {
    const user = await extpay.getUser();
    if (user.paid) {
      isProUser = true;
      if (modeBadge) {
        modeBadge.innerText = "PRO MODE";
        modeBadge.style.color = "#60a5fa";
        modeBadge.style.borderColor = "#3b82f6";
        modeBadge.style.backgroundColor = "rgba(59, 130, 246, 0.1)";
      }
    }
  } catch (err) {
    console.log("ExtPay offline", err);
  }

  // 2. Pulse Animation Keyframes & Floating Toast Overlay
  const showProtectionToast = () => {
    // Inject the keyframes once if not already present
    let styleTag = document.getElementById("toast-pulse-animations");
    if (!styleTag) {
      styleTag = document.createElement("style");
      styleTag.id = "toast-pulse-animations";
      styleTag.textContent = `
        @keyframes toastPulseIn {
          0% {
            opacity: 0;
            transform: scale(0.94);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 rgba(16, 185, 129, 0);
          }
          65% {
            opacity: 1;
            transform: scale(1.02);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.7), 0 0 18px rgba(16, 185, 129, 0.5);
          }
          100% {
            opacity: 1;
            transform: scale(1);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6), 0 0 8px rgba(16, 185, 129, 0.25);
          }
        }

        @keyframes toastPulseOut {
          0% {
            opacity: 1;
            transform: scale(1);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6), 0 0 8px rgba(16, 185, 129, 0.25);
          }
          35% {
            opacity: 0.95;
            transform: scale(1.02);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.7), 0 0 16px rgba(16, 185, 129, 0.45);
          }
          100% {
            opacity: 0;
            transform: scale(0.94);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5), 0 0 0 rgba(16, 185, 129, 0);
          }
        }
      `;
      document.head.appendChild(styleTag);
    }

    let toast = document.getElementById("protection-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "protection-toast";
      toast.style.cssText = `
        position: fixed;
        bottom: 160px;
        left: 14px;
        right: 14px;
        background-color: #1e293b;
        border: 1px solid #10b981;
        border-radius: 6px;
        padding: 10px 12px;
        color: #e2e8f0;
        font-size: 11px;
        line-height: 1.4;
        z-index: 99999;
        pointer-events: none;
        opacity: 0;
      `;
      toast.innerHTML = `<span style="color: #34d399; font-weight: 700;">Protection Active:</span> Declarative filtering remains fully operational in the background. Upgrade to Pro ($19.99) to unlock persistent live telemetry and unrestricted Terminal Edge logs.`;
      document.body.appendChild(toast);
    }

    // Trigger smooth 0.9s entrance pulse
    toast.style.animation = "toastPulseIn 0.9s cubic-bezier(0.16, 1, 0.3, 1) forwards";

    // Hold steady for 4 seconds, then trigger 0.9s exit pulse
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
      toast.style.animation = "toastPulseOut 0.9s cubic-bezier(0.7, 0, 0.84, 0) forwards";
    }, 4000);
  };

  // 3. Handle Pro Upgrade click
  if (btnUpgrade) {
    btnUpgrade.addEventListener("click", () => {
      extpay.openPaymentPage();
    });
  }

  // 4. Handle Terminal: View Edge Audit Log Button Click
  if (btnTerminal) {
    btnTerminal.addEventListener("click", () => {
      chrome.storage.local.get(['trackersBlocked'], (data) => {
        const blockedCount = data.trackersBlocked || 0;

        if (!isProUser && blockedCount >= 50) {
          if (btnUpgrade) btnUpgrade.classList.remove("hidden");
          showProtectionToast();
          return;
        }

        chrome.tabs.create({ url: chrome.runtime.getURL("audit.html") });
      });
    });
  }

  // 5. Explicit Manual Continuity Handshake
  if (btnEstablish) {
    btnEstablish.addEventListener("click", () => {
      btnEstablish.innerText = "Establishing...";
      btnEstablish.disabled = true;

      chrome.runtime.sendMessage({
        type: "EXECUTE_PATH_CONTINUITY",
        payload: { 
          verifiablePresentation: { 
            source: "dgf-edge-proxy", 
            timestamp: new Date().toISOString() 
          },
          note: "edge-proxy-init"
        }
      }, (response) => {
        if (response && response.ok && response.data && response.data.continuity_ref) {
          
          if (continuityStatus) {
            continuityStatus.innerText = response.data.continuity_ref;
            continuityStatus.classList.add("status-active");
          }
          
          if (ledgerBlock) ledgerBlock.classList.remove("hidden");
          
          const telemetryBlock = document.getElementById("telemetry-block");
          if (telemetryBlock) telemetryBlock.classList.remove("hidden");
          
          btnEstablish.classList.add("hidden");
          
          if (!isProUser && btnUpgrade) {
            btnUpgrade.classList.remove("hidden");
          }

          // Start live telemetry polling loop only after manual handshake
          const updateTelemetryUI = () => {
            chrome.storage.local.get(['trackersBlocked', 'dataSavedMB', 'payloadsIsolated', 'activeToken'], (data) => {
              const elBlocked = document.getElementById("metric-blocked");
              const elData = document.getElementById("metric-data");
              const elIsolated = document.getElementById("metric-isolated");
              
              let blockedCount = data.trackersBlocked || 0;
              let dataMB = data.dataSavedMB || 0.00;
              let isolatedCount = data.payloadsIsolated || 1;

              // Reflect current token if updated by background alarm
              if (data.activeToken && continuityStatus) {
                continuityStatus.innerText = data.activeToken;
              }

              // Enforce Normal Mode 50-Tracker / 0.75 MB Threshold
              if (!isProUser && (blockedCount >= 50 || dataMB >= 0.75)) {
                if (elBlocked) elBlocked.innerText = "0050";
                if (elData) elData.innerText = "0.75 MB";
                if (elIsolated) elIsolated.innerText = String(isolatedCount).padStart(4, '0');

                if (btnUpgrade) btnUpgrade.classList.remove("hidden");

                if (!thresholdAlertTriggered) {
                  showProtectionToast();
                  thresholdAlertTriggered = true;
                }

                if (telemetryInterval) {
                  clearInterval(telemetryInterval);
                }
                return;
              }

              // Standard live rendering with CSS animation triggers
              if (elBlocked) {
                const newBlockedText = String(blockedCount).padStart(4, '0');
                if (elBlocked.innerText !== newBlockedText) {
                  elBlocked.innerText = newBlockedText;
                  elBlocked.classList.remove('data-update-flash');
                  void elBlocked.offsetWidth; // Trigger DOM reflow to restart animation
                  elBlocked.classList.add('data-update-flash');
                }
              }

              if (elData) {
                const newDataText = dataMB.toFixed(2) + " MB";
                if (elData.innerText !== newDataText) {
                  elData.innerText = newDataText;
                  elData.classList.remove('data-update-flash');
                  void elData.offsetWidth; 
                  elData.classList.add('data-update-flash');
                }
              }

              if (elIsolated) {
                const newIsolatedText = String(isolatedCount).padStart(4, '0');
                if (elIsolated.innerText !== newIsolatedText) {
                  elIsolated.innerText = newIsolatedText;
                  elIsolated.classList.remove('data-update-flash');
                  void elIsolated.offsetWidth; 
                  elIsolated.classList.add('data-update-flash');
                }
              }
            });
          };

          updateTelemetryUI();
          telemetryInterval = setInterval(updateTelemetryUI, 2000);

        } else {
          btnEstablish.innerText = "Establish Identity Continuity";
          btnEstablish.disabled = false;
          if (continuityStatus) {
            continuityStatus.innerText = "Connection Failed";
            continuityStatus.style.color = "#ef4444"; 
          }
        }
      });
    });
  }
});