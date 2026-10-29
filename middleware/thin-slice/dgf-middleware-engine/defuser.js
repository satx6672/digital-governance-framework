// DGF Edge Defuser: Weaponized Anti-Adblock & Bait Neutralizer

(function () {
  'use strict';

  // 1. PURGE PERSISTENT STORAGE LOCKS
  // Clear any adblock penalty flags stored across past reloads
  try {
    const purgeKeys = ['fbs_adblock', 'fbs_ab', 'adblock', 'adblocker', 'adBlockDetected', 'sp_consent', 'ab_detected'];
    purgeKeys.forEach(k => {
      sessionStorage.removeItem(k);
      localStorage.removeItem(k);
    });
  } catch (e) {}

  // 2. SPOOF BAIT ELEMENT DIMENSIONS (Bypasses offsetHeight / offsetWidth checks)
  // Anti-adblock scripts check if an injected dummy ad div has collapsed to 0px
  const originalOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
  if (originalOffsetHeight) {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', {
      get() {
        if (this.className && typeof this.className === 'string' && /adsbox|ad-banner|ad-unit|ad_unit|ad-slot|ad-placement|carbonads/i.test(this.className)) {
          return 250;
        }
        return originalOffsetHeight.get.call(this);
      }
    });
  }

  const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
  if (originalOffsetWidth) {
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
      get() {
        if (this.className && typeof this.className === 'string' && /adsbox|ad-banner|ad-unit|ad_unit|ad-slot|ad-placement|carbonads/i.test(this.className)) {
          return 300;
        }
        return originalOffsetWidth.get.call(this);
      }
    });
  }

  // 3. INTERCEPT DYNAMIC <SCRIPT> INJECTIONS (Bypasses script.onerror checks)
  const originalCreateElement = Document.prototype.createElement;
  Document.prototype.createElement = function (tagName, options) {
    const el = originalCreateElement.call(this, tagName, options);
    if (typeof tagName === 'string' && tagName.toLowerCase() === 'script') {
      const originalSetAttribute = el.setAttribute;
      Object.defineProperty(el, 'src', {
        set(val) {
          if (typeof val === 'string' && /adservice|pagead2|doubleclick|googletagservices|adnxs|ad-delivery|adsystem|quantserve/i.test(val)) {
            // Emulate successful load asynchronously before error events can trigger
            setTimeout(() => {
              if (typeof el.onload === 'function') el.onload(new Event('load'));
              el.dispatchEvent(new Event('load'));
            }, 0);
            return;
          }
          originalSetAttribute.call(el, 'src', val);
        },
        get() {
          return el.getAttribute('src') || '';
        }
      });
    }
    return el;
  };

  // 4. INTERCEPT XHR & FETCH BAIT CANARIES
  const originalFetch = window.fetch;
  if (originalFetch) {
    window.fetch = async function (...args) {
      const url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
      if (/pagead2|doubleclick|adsystem|adnxs|adservice|ad-delivery|quantserve/i.test(url)) {
        return new Response('/* dgf-neutralized */', {
          status: 200,
          statusText: 'OK',
          headers: { 'Content-Type': 'application/javascript' }
        });
      }
      return originalFetch.apply(this, args);
    };
  }

  const originalOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this._interceptUrl = url;
    return originalOpen.apply(this, arguments);
  };

  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (body) {
    if (this._interceptUrl && /adservice|pagead2|doubleclick|googletagservices|adnxs|ad-delivery|adsystem/i.test(this._interceptUrl)) {
      setTimeout(() => {
        Object.defineProperty(this, 'readyState', { value: 4 });
        Object.defineProperty(this, 'status', { value: 200 });
        Object.defineProperty(this, 'responseText', { value: '{"status":"ok"}' });
        this.dispatchEvent(new Event('readystatechange'));
        this.dispatchEvent(new Event('load'));
      }, 0);
      return;
    }
    return originalSend.apply(this, arguments);
  };

  // 5. SURROGATE GLOBALS & CMP FLAGS
  const noop = () => {};
  window.canRunAds = true;
  window.isAdBlockActive = false;
  window.isAdblock = false;
  window.fbs_adblock = false;
  window.google_ad_client = true;

  window.ga = window.ga || noop;
  window.gtag = window.gtag || noop;
  window.google_tag_manager = window.google_tag_manager || {};
  window.dataLayer = window.dataLayer || [];
  window.adsbygoogle = window.adsbygoogle || [];
  window.adsbygoogle.push = noop;

  window.googletag = window.googletag || {
    cmd: [],
    display: noop,
    enableServices: noop,
    pubads: () => ({
      addEventListener: noop,
      clear: noop,
      collapseEmptyDivs: noop,
      disableInitialLoad: noop,
      enableAsyncRendering: noop,
      enableSingleRequest: noop,
      refresh: noop,
      setTargeting: noop
    })
  };

  // 6. RECURSIVE DOM SHREDDER & SHADOW DOM PIERCER
  const neutralizeModals = (rootNode = document) => {
    // 1. Shred modals within the current DOM or Shadow Root context
    const potentialModals = rootNode.querySelectorAll('div, section, aside, [role="dialog"], [aria-modal="true"]');
    potentialModals.forEach(el => {
      const text = el.textContent || '';
      if (
        /ad\s*blocker|ad-blocker|adblock/i.test(text) &&
        (/disable|turn off|whitelist|advertising helps|ad-free/i.test(text))
      ) {
        el.remove();
      }
    });

    // 2. Remove high-z-index background dimmers in the current context
    rootNode.querySelectorAll('[class*="fader"], [class*="backdrop"], [class*="overlay"]').forEach(el => {
      const style = window.getComputedStyle(el);
      if (style.position === 'fixed' && !el.children.length) {
        el.remove();
      }
    });

    // 3. Enforce body scrolling and remove article blurs (Only run on main document)
    if (rootNode === document) {
      if (document.body) {
        if (document.body.style.overflow === 'hidden') document.body.style.setProperty('overflow', 'auto', 'important');
        if (document.body.style.position === 'fixed') document.body.style.setProperty('position', 'static', 'important');
        if (document.body.style.filter) document.body.style.setProperty('filter', 'none', 'important');
      }
      if (document.documentElement && document.documentElement.style.overflow === 'hidden') {
        document.documentElement.style.setProperty('overflow', 'auto', 'important');
      }

      document.querySelectorAll('main, article, #main-content, div[class*="article"]').forEach(node => {
        if (node.style.filter && node.style.filter.includes('blur')) {
          node.style.setProperty('filter', 'none', 'important');
        }
      });
    }

    // 4. THE PIERCER: Find all elements and recursively dive into their Shadow Roots
    // This allows the shredder to bypass encapsulation and destroy hidden modals
    rootNode.querySelectorAll('*').forEach(el => {
      if (el.shadowRoot) {
        neutralizeModals(el.shadowRoot);
      }
    });
  };

  // Run on load and attach to the observer
  document.addEventListener('DOMContentLoaded', () => neutralizeModals(document));
  window.addEventListener('load', () => neutralizeModals(document));

  // 7. THROTTLED MUTATION OBSERVER
  // Prevents CPU spikes by grouping rapid DOM changes into a single animation frame
  let isScanScheduled = false;

  const observer = new MutationObserver(() => {
    // If a scan is already queued for the next frame, ignore this mutation
    if (!isScanScheduled) {
      isScanScheduled = true;
      
      // Schedule the recursive shredder for the next browser paint
      window.requestAnimationFrame(() => {
        neutralizeModals(document);
        isScanScheduled = false; // Unlock for the next batch of mutations
      });
    }
  });

  // Attach observer once documentElement exists
  if (document.documentElement) {
    observer.observe(document.documentElement, { childList: true, subtree: true });
  } else {
    document.addEventListener('readystatechange', () => {
      if (document.documentElement) {
        observer.observe(document.documentElement, { childList: true, subtree: true });
      }
    });
  }
})();