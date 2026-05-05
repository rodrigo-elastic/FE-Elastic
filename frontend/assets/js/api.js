/*
  filename: api.js
  description: Thin fetch wrappers for FE Copilot REST API. Includes a sanitizer so error messages rendered into the UI never leak Python file paths, module names, raw stack traces, or unbounded content.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
const API_BASE = "/api/v1";

// ============================================================ Error sanitizer
// W25C error path audit: every fetch failure path eventually reaches a toast,
// banner, or inline message. Without this guard, a 500 from a Python service
// can dump file paths, traceback markers, and module names straight into the
// UI. sanitizeError() collapses everything to a short single-line string with
// internal-path hints stripped.
function sanitizeError(err) {
  if (err == null) return "Unknown error";
  let msg = "";
  if (typeof err === "string") {
    msg = err;
  } else if (err && typeof err.message === "string") {
    msg = err.message;
  } else {
    try { msg = String(err); } catch (_) { msg = "Unknown error"; }
  }
  // Collapse newlines + any traceback chatter onto one line.
  msg = msg.replace(/\s*Traceback[\s\S]*$/i, "")
           .replace(/\r?\n/g, " ")
           .replace(/\s{2,}/g, " ")
           .trim();
  // Strip absolute file paths and Python module fragments that leak internals.
  msg = msg.replace(/\/(?:Users|home|var|tmp|opt|root|app)\/[^\s)'\"]+/g, "[path]")
           .replace(/\bFile \"[^\"]+\", line \d+/g, "")
           .replace(/\bat 0x[0-9a-fA-F]+/g, "")
           .replace(/<[^<>]*\bobject at\b[^<>]*>/g, "[object]");
  if (!msg) msg = "Request failed";
  // Hard cap so a giant blob never lands in a toast.
  if (msg.length > 200) msg = msg.slice(0, 200) + "...";
  return msg;
}

async function apiGet(path) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`);
  } catch (netErr) {
    // Network kill (browser offline, DNS fail) bubbles a TypeError. Surface it
    // with a friendly message instead of "Failed to fetch".
    throw new Error(`Network unavailable - check your connection (GET ${path})`);
  }
  if (!res.ok) {
    let detail = String(res.status);
    try {
      const j = await res.json();
      if (j && j.detail) detail = `${res.status} - ${sanitizeError(j.detail)}`;
    } catch (_) {}
    throw new Error(`GET ${path} failed: ${detail}`);
  }
  return res.json();
}

async function apiPost(path, body) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : null,
    });
  } catch (netErr) {
    throw new Error(`Network unavailable - check your connection (POST ${path})`);
  }
  if (!res.ok) {
    let detail = String(res.status);
    try {
      const j = await res.json();
      if (j && j.detail) detail = `${res.status} - ${sanitizeError(j.detail)}`;
    } catch (_) {}
    throw new Error(`POST ${path} failed: ${detail}`);
  }
  return res.json();
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

// Expose for non-module callers.
if (typeof window !== "undefined") {
  window.sanitizeError = sanitizeError;
}
