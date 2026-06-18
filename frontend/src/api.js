// Thin API client for the Compli402 backend.
//
// The backend base URL is configured via the VITE_API_BASE_URL environment
// variable (see frontend/.env.example). It falls back to localhost:8000 for
// local development.

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function apiBaseUrl() {
  return API_BASE_URL;
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  let data = null;
  try {
    data = await res.json();
  } catch (_e) {
    data = null;
  }

  return { ok: res.ok, status: res.status, data };
}

// GET /api/compli402/health
export function getHealth() {
  return request("/api/compli402/health");
}

// POST /api/compli402/verify/intent
export function verifyIntent(intent) {
  return request("/api/compli402/verify/intent", {
    method: "POST",
    body: JSON.stringify(intent),
  });
}

// POST /api/compli402/execute
export function executeIntent(intent) {
  return request("/api/compli402/execute", {
    method: "POST",
    body: JSON.stringify(intent),
  });
}

// GET /api/compli402/proofs/latest
export function getLatestProof() {
  return request("/api/compli402/proofs/latest");
}
