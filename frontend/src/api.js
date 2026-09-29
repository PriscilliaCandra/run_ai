const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function generateTrainingPlan(profileData) {
  const res = await fetch(`${API_BASE}/plans/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profileData),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const message = errorData.detail 
      ? (typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail))
      : 'Failed to generate training plan';
    throw new Error(message);
  }
  return res.json();
}

export async function fetchPlanById(planId) {
  const res = await fetch(`${API_BASE}/plans/${planId}`);
  if (!res.ok) throw new Error('Failed to retrieve training plan');
  return res.json();
}

export async function fetchRecentPlans() {
  const res = await fetch(`${API_BASE}/plans`);
  if (!res.ok) throw new Error('Failed to retrieve recent plans');
  return res.json();
}

export async function submitPlanEvaluation(evalData) {
  const res = await fetch(`${API_BASE}/evaluations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(evalData),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to submit evaluation');
  }
  return res.json();
}

export async function fetchEvaluationStats() {
  const res = await fetch(`${API_BASE}/evaluations/stats`);
  if (!res.ok) throw new Error('Failed to retrieve evaluation statistics');
  return res.json();
}
