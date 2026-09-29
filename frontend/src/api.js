const API_BASE = '/api';

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    // Send/receive the httpOnly session cookie on every request. The dev
    // server proxies /api to the backend same-origin (see vite.config.js),
    // so this also works correctly across the proxy boundary.
    credentials: 'include',
    headers: options.body ? { 'Content-Type': 'application/json', ...options.headers } : options.headers,
    ...options,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errorData = await res.json();
      // The backend's error handler always returns a friendly string in
      // `detail` (see backend/app/core/errors.py) -- never a raw Pydantic
      // error array. The JSON.stringify fallback only guards against a
      // response shape we didn't anticipate.
      if (errorData && errorData.detail) {
        detail = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch {
      // Non-JSON error body; keep the generic message above.
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

// --- Health ---

export async function fetchHealth() {
  return apiFetch('/health');
}

// --- Research: training plans (anonymous flow, unchanged) ---

export async function generateTrainingPlan(profileData) {
  return apiFetch('/plans/generate', { method: 'POST', body: JSON.stringify(profileData) });
}

export async function fetchPlanById(planId) {
  return apiFetch(`/plans/${planId}`);
}

export async function fetchRecentPlans() {
  return apiFetch('/plans');
}

export async function submitPlanEvaluation(evalData) {
  return apiFetch('/evaluations', { method: 'POST', body: JSON.stringify(evalData) });
}

export async function fetchEvaluationStats() {
  return apiFetch('/evaluations/stats');
}

// --- Authentication ---

export async function registerAccount({ email, password, displayName }) {
  return apiFetch('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
}

export async function login({ email, password }) {
  return apiFetch('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
}

export async function logout() {
  return apiFetch('/auth/logout', { method: 'POST' });
}

export async function fetchCurrentUser() {
  return apiFetch('/auth/me');
}

export async function requestPasswordReset(email) {
  return apiFetch('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) });
}

export async function resetPassword({ token, newPassword }) {
  return apiFetch('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}

// --- Consumer user profile ---

export async function fetchMyProfile() {
  return apiFetch('/users/me/profile');
}

export async function updateMyProfile(updates) {
  return apiFetch('/users/me/profile', { method: 'PATCH', body: JSON.stringify(updates) });
}

// --- Consumer plans ---

export async function fetchMyPlans() {
  return apiFetch('/plans/mine');
}

export async function fetchPlanWorkouts(planId) {
  return apiFetch(`/plans/${planId}/workouts`);
}

// --- Dashboard ---

export async function fetchDashboardSummary() {
  return apiFetch('/dashboard/summary');
}

// --- Workouts ---

export async function createWorkout(payload) {
  return apiFetch('/workouts', { method: 'POST', body: JSON.stringify(payload) });
}

export async function fetchWorkouts({ dateFrom, dateTo, workoutType, page = 1, pageSize = 20 } = {}) {
  const params = new URLSearchParams();
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  if (workoutType) params.set('workout_type', workoutType);
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  return apiFetch(`/workouts?${params.toString()}`);
}

export async function fetchWorkoutById(workoutId) {
  return apiFetch(`/workouts/${workoutId}`);
}

export async function updateWorkout(workoutId, updates) {
  return apiFetch(`/workouts/${workoutId}`, { method: 'PATCH', body: JSON.stringify(updates) });
}

export async function deleteWorkout(workoutId) {
  return apiFetch(`/workouts/${workoutId}`, { method: 'DELETE' });
}
