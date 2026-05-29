/**
 * Enterprise polling coordinator — dedupe, abort stale, exponential backoff on 504.
 */
const inflight = new Map();
const backoffUntil = new Map();

const DEFAULT_BACKOFF_MS = 2500;
const MAX_BACKOFF_MS = 60000;

function backoffKey(url) {
  return url;
}

export function getPollingBackoffMs(url) {
  const until = backoffUntil.get(backoffKey(url)) || 0;
  const wait = until - Date.now();
  return wait > 0 ? wait : 0;
}

function registerBackoff(url, attempt = 1) {
  const delay = Math.min(DEFAULT_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
  backoffUntil.set(backoffKey(url), Date.now() + delay);
  if (typeof console !== "undefined") {
    console.info("[POLLING_GOVERNANCE] backoff", url, `${delay}ms`);
  }
  return delay;
}

function clearBackoff(url) {
  backoffUntil.delete(backoffKey(url));
}

/**
 * Fetch with deduplication and AbortController per logical key.
 */
export async function coordinatedFetch(url, {
  key = url,
  signal: externalSignal,
  init = {},
} = {}) {
  const wait = getPollingBackoffMs(url);
  if (wait > 0) {
    await new Promise((r) => setTimeout(r, wait));
  }

  const existing = inflight.get(key);
  if (existing) {
    if (typeof console !== "undefined") {
      console.debug("[POLLING_GOVERNANCE] dedupe", key);
    }
    return existing;
  }

  const controller = new AbortController();
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      externalSignal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }

  const promise = (async () => {
    try {
      const res = await fetch(url, { ...init, signal: controller.signal });
      if (res.status === 504) {
        registerBackoff(url);
        return { ok: false, status: 504, data: null, aborted: false };
      }
      if (res.status === 499 || res.status === 204) {
        return { ok: false, status: res.status, data: null, aborted: true };
      }
      clearBackoff(url);
      const data = res.ok ? await res.json() : null;
      return { ok: res.ok, status: res.status, data, aborted: false };
    } catch (err) {
      if (err?.name === "AbortError") {
        return { ok: false, status: 0, data: null, aborted: true };
      }
      return { ok: false, status: 0, data: null, aborted: false, error: err };
    } finally {
      inflight.delete(key);
    }
  })();

  inflight.set(key, promise);
  return promise;
}

export function abortPollingKey(key) {
  inflight.delete(key);
}

export function resetPollingGovernance() {
  inflight.clear();
  backoffUntil.clear();
}
