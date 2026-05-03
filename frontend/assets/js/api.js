/*
  filename: api.js
  description: Thin fetch wrappers for FE Copilot REST API.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
const API_BASE = "/api/v1";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : null,
  });
  if (!res.ok) {
    let detail = String(res.status);
    try {
      const j = await res.json();
      if (j && j.detail) detail = `${res.status} — ${j.detail}`;
    } catch (_) {}
    throw new Error(`POST ${path} failed: ${detail}`);
  }
  return res.json();
}

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}
