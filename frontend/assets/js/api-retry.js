/*
  filename: api-retry.js
  description: Retry + timeout policy wrappers for FE Copilot REST API calls.
    Sits on top of the thin apiGet / apiPost helpers in api.js. Adds:
      - per-category default timeouts (compute / health / llm / workflow)
      - exponential backoff (1s, 2s, 4s) for transient errors (502, 503, 504,
        network failure, AbortError from timeout) with a max of 3 retries
      - friendly toast on final failure (when window.toast is available)
      - returns the same shape as apiGet / apiPost so callers can opt in
        incrementally without touching their parsing code.
    All wrappers are exposed on window so legacy IIFE files can pick them up.
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  "use strict";

  // -------------------------------------------------------------------------
  // Timeout categories. Tuned for the demo backend on localhost:8123.
  // The keys are the names used by callers via opts.category.
  // -------------------------------------------------------------------------
  const TIMEOUTS = {
    compute:  5000,    // cost-calc, capacity, sizing, stats, savings
    health:   5000,    // /health, /health/full, status pings
    llm:      30000,   // knowledge-search, agent converse, pre/post meeting
    workflow: 12000,   // workflow webhook fire
    default:  10000,
  };

  // Transient HTTP statuses that should trigger a retry. Anything else
  // (4xx in particular) is considered a permanent failure and surfaces
  // immediately so the caller can decide what to do.
  const TRANSIENT_STATUSES = new Set([502, 503, 504]);

  const DEFAULT_RETRIES = 3;
  // 1s, 2s, 4s.
  const BACKOFF_MS = [1000, 2000, 4000];

  function pickTimeout(category, override) {
    if (typeof override === "number" && override > 0) return override;
    if (category && TIMEOUTS[category]) return TIMEOUTS[category];
    return TIMEOUTS.default;
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function isTransientError(err, response) {
    if (response && TRANSIENT_STATUSES.has(response.status)) return true;
    if (!err) return false;
    if (err.name === "AbortError") return true;
    // TypeError is what fetch throws for offline / CORS / DNS failures.
    if (err.name === "TypeError") return true;
    if (err.__transient === true) return true;
    return false;
  }

  // Build a bare error with an attached __transient flag so retries can
  // recognise our own marker without sniffing the message.
  function makeTransient(message, status) {
    const e = new Error(message);
    e.__transient = true;
    if (status != null) e.status = status;
    return e;
  }

  // Show a friendly toast. Falls back to console.warn when no toast() is
  // available (e.g. on health.html which intentionally hides the toast host).
  function notifyError(label, err) {
    const msg = (err && err.message) ? err.message : String(err || "request failed");
    try {
      if (typeof window.toast === "function") {
        window.toast(label + ": " + msg, "bad");
        return;
      }
    } catch (_) { /* ignore */ }
    try { console.warn("[api-retry] " + label + " failed:", err); } catch (_) {}
  }

  // -------------------------------------------------------------------------
  // Core fetch with timeout + caller-supplied AbortSignal pass-through.
  // -------------------------------------------------------------------------
  async function fetchWithTimeout(url, init, timeoutMs, externalSignal) {
    const ctrl = new AbortController();
    let timedOut = false;
    const onAbort = () => {
      try { ctrl.abort(externalSignal && externalSignal.reason); }
      catch (_) { ctrl.abort(); }
    };
    if (externalSignal) {
      if (externalSignal.aborted) onAbort();
      else externalSignal.addEventListener("abort", onAbort, { once: true });
    }
    const timer = setTimeout(() => {
      timedOut = true;
      const reason = new Error("Request timed out after " + Math.round(timeoutMs / 1000) + "s");
      reason.name = "TimeoutError";
      try { ctrl.abort(reason); } catch (_) { ctrl.abort(); }
    }, timeoutMs);
    try {
      const res = await fetch(url, Object.assign({}, init, { signal: ctrl.signal }));
      return res;
    } catch (err) {
      // Translate the opaque "signal is aborted without reason" DOMException
      // into a clear message so the inline error and toast are readable.
      if (timedOut) {
        const e = new Error("Request timed out after " + Math.round(timeoutMs / 1000) + "s");
        e.name = "AbortError";
        e.__transient = true;
        throw e;
      }
      throw err;
    } finally {
      clearTimeout(timer);
      if (externalSignal) externalSignal.removeEventListener("abort", onAbort);
    }
  }

  // Parses an error response, returning either:
  //   - a thrown transient error if status is 502/503/504
  //   - a thrown permanent error otherwise
  // Mirrors the shape of api.js so callers see the same Error.message format.
  async function parseError(method, path, res) {
    let detail = String(res.status);
    try {
      const j = await res.json();
      if (j && j.detail != null) {
        // FastAPI/Pydantic 422 returns `detail` as a list of error objects.
        // Flatten to "loc -> msg" so the toast is readable instead of
        // "[object Object],[object Object]".
        if (Array.isArray(j.detail)) {
          const parts = j.detail.map((e) => {
            if (e && typeof e === "object") {
              const loc = Array.isArray(e.loc) ? e.loc.slice(-1)[0] : (e.loc || "");
              return loc ? loc + ": " + (e.msg || "invalid") : (e.msg || JSON.stringify(e));
            }
            return String(e);
          });
          detail = res.status + " - " + parts.join("; ");
        } else if (typeof j.detail === "string") {
          detail = res.status + " - " + j.detail;
        } else {
          detail = res.status + " - " + JSON.stringify(j.detail);
        }
      }
    } catch (_) { /* body might not be JSON */ }
    const message = method + " " + path + " failed: " + detail;
    if (TRANSIENT_STATUSES.has(res.status)) {
      throw makeTransient(message, res.status);
    }
    const e = new Error(message);
    e.status = res.status;
    throw e;
  }

  // -------------------------------------------------------------------------
  // The retry loop. Honours an external AbortSignal: if the signal fires
  // while we are sleeping between attempts, we re-throw immediately so the
  // caller's cancel UX is responsive.
  // -------------------------------------------------------------------------
  async function withRetries(fn, opts) {
    const maxRetries = (opts && typeof opts.retries === "number") ? opts.retries : DEFAULT_RETRIES;
    const externalSignal = opts && opts.signal;
    let lastErr = null;
    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      if (externalSignal && externalSignal.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      try {
        return await fn(attempt);
      } catch (err) {
        lastErr = err;
        // User cancellation should NOT be retried.
        if (err && err.name === "AbortError" && externalSignal && externalSignal.aborted) {
          throw err;
        }
        if (!isTransientError(err)) throw err;
        if (attempt >= maxRetries) break;
        const wait = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
        // Sleep, but bail out early if the caller cancels.
        await new Promise((resolve, reject) => {
          const t = setTimeout(resolve, wait);
          if (externalSignal) {
            externalSignal.addEventListener("abort", () => {
              clearTimeout(t);
              reject(new DOMException("Aborted", "AbortError"));
            }, { once: true });
          }
        });
      }
    }
    throw lastErr || new Error("request failed");
  }

  // -------------------------------------------------------------------------
  // Public wrappers. Same return shape as apiGet / apiPost.
  //
  //   apiGetWithRetry("/path", { category: "compute", signal, retries, timeoutMs, label, silent })
  //   apiPostWithRetry("/path", body, { category: "llm", ... })
  //
  //   - category: one of "compute", "health", "llm", "workflow", "default".
  //   - timeoutMs: override the category default for one call.
  //   - signal: external AbortSignal (e.g. autopilot, agent-builder Esc).
  //   - retries: override DEFAULT_RETRIES (3).
  //   - label: short human label used for the failure toast.
  //   - silent: if true, do NOT toast on final failure (callers that want to
  //     render the error inline; e.g. dashboard-stats hides its band instead).
  // -------------------------------------------------------------------------
  const API_BASE = "/api/v1";

  async function apiGetWithRetry(path, opts) {
    opts = opts || {};
    const url = path.startsWith("/api/") || path.startsWith("http") ? path : API_BASE + path;
    const timeout = pickTimeout(opts.category, opts.timeoutMs);
    const label = opts.label || ("GET " + path);
    try {
      return await withRetries(async () => {
        const res = await fetchWithTimeout(
          url,
          { method: "GET", cache: opts.cache || "default" },
          timeout,
          opts.signal,
        );
        if (!res.ok) await parseError("GET", path, res);
        return res.json();
      }, opts);
    } catch (e) {
      if (!opts.silent) notifyError(label, e);
      throw e;
    }
  }

  async function apiPostWithRetry(path, body, opts) {
    opts = opts || {};
    const url = path.startsWith("/api/") || path.startsWith("http") ? path : API_BASE + path;
    const timeout = pickTimeout(opts.category, opts.timeoutMs);
    const label = opts.label || ("POST " + path);
    const init = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
    };
    try {
      return await withRetries(async () => {
        const res = await fetchWithTimeout(url, init, timeout, opts.signal);
        if (!res.ok) await parseError("POST", path, res);
        return res.json();
      }, opts);
    } catch (e) {
      if (!opts.silent) notifyError(label, e);
      throw e;
    }
  }

  async function apiDeleteWithRetry(path, opts) {
    opts = opts || {};
    const url = path.startsWith("/api/") || path.startsWith("http") ? path : API_BASE + path;
    const timeout = pickTimeout(opts.category, opts.timeoutMs);
    const label = opts.label || ("DELETE " + path);
    try {
      return await withRetries(async () => {
        const res = await fetchWithTimeout(url, { method: "DELETE" }, timeout, opts.signal);
        if (!res.ok) await parseError("DELETE", path, res);
        // Some delete endpoints return 204 with no body.
        if (res.status === 204) return null;
        return res.json().catch(() => null);
      }, opts);
    } catch (e) {
      if (!opts.silent) notifyError(label, e);
      throw e;
    }
  }

  // Expose under window so the legacy IIFE-scoped pages can opt in.
  window.apiGetWithRetry = apiGetWithRetry;
  window.apiPostWithRetry = apiPostWithRetry;
  window.apiDeleteWithRetry = apiDeleteWithRetry;
  window.API_TIMEOUTS = TIMEOUTS;
})();
