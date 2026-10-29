// DGF Phase 1: Local DNA Sequencer (content.js)

let loadTime = Date.now();
let firstInteraction = false;
let recentMouseMoves = []; // Temporary buffer for pre-click jitter

// The Cellular Regeneration Function (Zero Memory Bloat)
const updateChromosome = (key, newValue) => {
  chrome.storage.local.get([key], (result) => {
    // If no DNA exists yet, seed it. Otherwise, blend 90% old with 10% new.
    let currentAvg = result[key] || newValue;
    let mutatedAvg = (currentAvg * 0.9) + (newValue * 0.1); 
    
    chrome.storage.local.set({ [key]: mutatedAvg });
  });
};

// 1. Time-to-Interactive (TTI) Cadence
const recordTTI = () => {
  if (!firstInteraction) {
    firstInteraction = true;
    let tti = Date.now() - loadTime;
    updateChromosome('average_dwell_tti', tti);
  }
};

// 2. Scroll Velocity Curve (Pixels per millisecond)
let lastScrollTop = window.scrollY;
let lastScrollTime = Date.now();

window.addEventListener('scroll', () => {
  recordTTI();
  let now = Date.now();
  let currentScrollTop = window.scrollY;
  let timeDelta = now - lastScrollTime;
  
  if (timeDelta > 0) {
    let distance = Math.abs(currentScrollTop - lastScrollTop);
    let velocity = distance / timeDelta; 
    
    // Filter out micro-drifts to only capture intentional scrolling
    if (velocity > 0.1) { 
       updateChromosome('scroll_velocity_curve', velocity);
    }
  }
  lastScrollTop = currentScrollTop;
  lastScrollTime = now;
}, { passive: true }); // passive: true ensures ZERO lag on the user's actual scrolling

// 3. Cursor Jitter Radius (The Pre-Click Micro-Stutter)
window.addEventListener('mousemove', (e) => {
  recordTTI();
  recentMouseMoves.push({ x: e.clientX, y: e.clientY, time: Date.now() });
  
  // Keep only the mouse coordinates from the last 200 milliseconds
  recentMouseMoves = recentMouseMoves.filter(m => Date.now() - m.time < 200);
}, { passive: true });

window.addEventListener('mousedown', () => {
  // Calculate the bounding box of the cursor's micro-movements just before the click
  if (recentMouseMoves.length > 2) {
    let xs = recentMouseMoves.map(m => m.x);
    let ys = recentMouseMoves.map(m => m.y);
    let minX = Math.min(...xs), maxX = Math.max(...xs);
    let minY = Math.min(...ys), maxY = Math.max(...ys);
    
    // The "Jitter Radius" is the pixel area of hesitation
    let jitterArea = (maxX - minX) * (maxY - minY); 
    updateChromosome('cursor_jitter_radius', jitterArea);
  }
  
  // Flush the buffer to keep memory entirely flat
  recentMouseMoves = []; 
}, { passive: true });