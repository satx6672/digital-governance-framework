document.addEventListener("DOMContentLoaded", () => {
  const terminal = document.getElementById("terminal");

  // Helper function to append and scroll
  function appendLog(log) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `
      <div class="timestamp">[${log.timestamp}]</div>
      <div class="threat">THREAT VECTOR: ${log.requestUrl}</div>
      <div class="harm-class">HARMONICS ENGINE: Normalizing threat to ${log.harmClass}</div>
      <div class="action">ACTION TAKEN: Rule ID #${log.ruleId} Matched. ${log.action}</div>
    `;
    terminal.appendChild(entry);
    window.scrollTo(0, document.body.scrollHeight);
  }

  // 1. Back-fill previously blocked trackers so the screen isn't blank
  chrome.storage.local.get(['auditLogs'], (data) => {
    if (data.auditLogs && data.auditLogs.length > 0) {
      terminal.innerHTML = ""; // Clear the initial placeholder
      data.auditLogs.forEach(appendLog);
    }
  });

  // 2. Stream new intercept events live
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "EDGE_INTERCEPT_LOG") {
      // Clear the "waiting for payload" placeholder if it's the only thing there
      if (terminal.children.length === 1 && terminal.innerText.includes("System initialized")) {
        terminal.innerHTML = "";
      }
      appendLog(message.payload);
    }
  });
});