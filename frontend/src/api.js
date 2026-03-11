const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const TOKEN_STORAGE_KEY = "hospital-bed-auth-token";

function normalizeErrorDetail(detail) {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => normalizeErrorDetail(item))
      .filter(Boolean)
      .join(" ");
  }

  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }

    if (typeof detail.msg === "string" && detail.msg.trim()) {
      if (Array.isArray(detail.loc) && detail.loc.length) {
        return `${detail.loc.join(".")}: ${detail.msg}`;
      }
      return detail.msg;
    }

    if (typeof detail.detail === "string" && detail.detail.trim()) {
      return detail.detail;
    }
  }

  return null;
}

function createError(status, detail) {
  const error = new Error(normalizeErrorDetail(detail) || `Request failed with status ${status}`);
  error.status = status;
  return error;
}

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token) {
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request(path, { method = "GET", token, body } = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: body ? JSON.stringify(body) : undefined
    });
  } catch (error) {
    throw createError(0, error?.message || "Unable to reach the API server.");
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    throw createError(response.status, payload?.detail);
  }

  return payload;
}

export async function login(credentials) {
  const payload = await request("/api/auth/login", { method: "POST", body: credentials });
  setStoredToken(payload.token);
  return payload;
}

export async function logout(token) {
  try {
    await request("/api/auth/logout", { method: "POST", token });
  } finally {
    clearStoredToken();
  }
}

export function fetchCurrentUser(token) {
  return request("/api/auth/me", { token });
}

export function fetchDashboard(token, horizonHours = 72) {
  return request(`/api/dashboard?horizon_hours=${horizonHours}`, { token });
}

export function saveThresholds(token, thresholds) {
  return request("/api/admin/thresholds", {
    method: "PUT",
    token,
    body: { thresholds }
  });
}

export function fetchAlertHistory(token, limit = 24) {
  return request(`/api/admin/alerts/history?limit=${limit}`, { token });
}

export function fetchScenarios(token) {
  return request("/api/admin/scenarios", { token });
}

export function saveScenario(token, scenario) {
  return request("/api/admin/scenarios", {
    method: "POST",
    token,
    body: scenario
  });
}

export function deleteScenario(token, scenarioId) {
  return request(`/api/admin/scenarios/${scenarioId}`, {
    method: "DELETE",
    token
  });
}

export function simulateScenario(token, scenarioId, horizonHours = 72) {
  return request(`/api/admin/scenarios/${scenarioId}/simulate?horizon_hours=${horizonHours}`, {
    method: "POST",
    token
  });
}

export function ingestDataset(token, datasetName, csvText) {
  return request("/api/admin/datasets/ingest", {
    method: "POST",
    token,
    body: { dataset_name: datasetName, csv_text: csvText }
  });
}

export function retrainModels(token) {
  return request("/api/admin/models/retrain", {
    method: "POST",
    token
  });
}
