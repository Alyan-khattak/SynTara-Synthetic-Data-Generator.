// ═══════════════════════════════════════════════════════════════════
// api.js — single API client module
// ═══════════════════════════════════════════════════════════════════
// IMP: every network call goes through apiFetch; components never call
//      fetch() directly. Base URL is defined once here.
// Matches API_PREFIX = "/api" from hackdata/constants/api.py
// ==============================================================

const API_BASE = "/api";

// ---------------- core fetch wrapper ----------------
/**
 * apiFetch — wraps fetch with JSON content-type and error extraction.
 *
 * On HTTP error it reads { message } from the response body and throws
 * Error(message) so callers can display the backend's readable text.
 * On network failure it throws Error(STRINGS.error.network) — but we
 * keep this module self-contained, so we use a literal here only.
 *
 * @param {string} path     — path relative to API_BASE (starts with /)
 * @param {object} options  — passed straight to fetch(); override method/body here
 * @returns {Promise<any>}  — parsed JSON from a successful response
 */
async function apiFetch(path, options = {}) {
  const defaults = {
    headers: { "Content-Type": "application/json" },
  };
  // merge: caller headers override defaults
  const merged = {
    ...defaults,
    ...options,
    headers: { ...defaults.headers, ...(options.headers || {}) },
  };

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, merged);
  } catch (networkErr) {
    // IMP: true network failure (server unreachable), not an HTTP error status
    throw new Error("Network error. Check the server is running.");
  }

  if (!response.ok) {
    // Try to read { message } from the error body; fall back to status text
    let msg = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && body.message) msg = body.message;
    } catch (_) {
      // body was not JSON — keep the status text message
    }
    throw new Error(msg);
  }

  return response.json();
}

// ---------------- public API functions ----------------

/** Returns the public config object from the backend (caps, weights, modules). */
export async function getConfig() {
  return apiFetch("/config");
}

/**
 * Starts a generation run.
 * @param {object} params — GenerateRequest fields (module, mode, query, n_rows, …)
 * @returns {Promise<{run_id: string, preview: object, status: string}>}
 */
export async function generateData(params) {
  return apiFetch("/generate", { method: "POST", body: JSON.stringify(params) });
}

/**
 * Polls the score status for a completed run.
 * @param {string} runId
 * @returns {Promise<{scores_status: string, scores: object}>}
 */
export async function getRunScores(runId) {
  return apiFetch(`/runs/${runId}/scores`);
}

/** Lists all runs (temp + saved). */
export async function listRuns() {
  return apiFetch("/runs");
}

/**
 * Saves a temp run to Artifacts/saved/.
 * @param {string} runId
 */
export async function saveRun(runId) {
  return apiFetch(`/runs/${runId}/save`, { method: "POST" });
}

/**
 * Opens a new window to trigger a file download.
 * IMP: no fetch needed for downloads — browser handles the stream directly.
 * @param {string} runId
 * @param {string} format  — "csv" | "json" | "sql" | "pdf"
 */
export async function downloadExport(runId, format) {
  window.open(`${API_BASE}/runs/${runId}/export?format=${format}`);
}

/**
 * Download a single table as a raw CSV file (Step B).
 * Opens a new window to let the browser handle the file stream.
 * @param {string} runId
 * @param {string} tableName
 */
export function downloadTableCsv(runId, tableName) {
  window.open(`${API_BASE}/runs/${runId}/export/table/${encodeURIComponent(tableName)}`);
}

/**
 * Fetch the ER diagram Mermaid text for a relational run (Step A).
 * @param {string} runId
 * @returns {Promise<{applicable: boolean, mermaid?: string, message?: string}>}
 */
export async function getRunSchema(runId) {
  return apiFetch(`/runs/${runId}/schema`);
}

/**
 * Regenerate synthetic data from an existing data-mode run (new seed).
 * @param {string} runId — original upload run_id
 */
export async function regenerateData(runId) {
  return apiFetch(`/runs/${runId}/regenerate`, { method: "POST" });
}

/**
 * Generate synthetic data from an already-uploaded CSV (Step A).
 * @param {string} runId
 * @param {object} settings — { n_rows, seed, missing_rate, outlier_rate, noise_level, correlation_adjustment }
 */
export async function generateDM(runId, settings) {
  return apiFetch(`/runs/${runId}/generate-dm`, { method: "POST", body: JSON.stringify(settings) });
}

/**
 * Fetch column profile + relationship matrix for a run (Steps C + D).
 * @param {string} runId
 */
export async function getProfile(runId) {
  return apiFetch(`/runs/${runId}/profile`);
}

/**
 * Run ML Lab pipeline (generate data, plant target, ML check).
 * @param {object} body — MLLabRequest fields
 */
export async function generateML(body) {
  return apiFetch("/ml/generate", { method: "POST", body: JSON.stringify(body) });
}

/**
 * Uploads a file for Data Mode synthesis.
 * @param {File} file
 */
export async function uploadDataset(file) {
  const formData = new FormData();
  formData.append("file", file);
  
  const response = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    body: formData,
  });
  
  if (!response.ok) {
    let msg = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const body = await response.json();
      if (body && body.detail) msg = body.detail;
      else if (body && body.message) msg = body.message;
    } catch (_) {}
    throw new Error(msg);
  }
  return response.json();
}
