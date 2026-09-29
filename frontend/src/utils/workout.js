// Shared constants/helpers for the workout logging feature. Mirrors the
// backend's controlled vocabulary (app/workouts/schemas.py::WorkoutType)
// and duration convention (app/schemas.py::parse_time_to_seconds).

export const WORKOUT_TYPES = [
  { value: 'EASY', label: 'Easy' },
  { value: 'LONG_RUN', label: 'Long Run' },
  { value: 'TEMPO', label: 'Tempo' },
  { value: 'INTERVAL', label: 'Interval' },
  { value: 'RECOVERY', label: 'Recovery' },
  { value: 'RACE', label: 'Race' },
  { value: 'OTHER', label: 'Other' },
];

export function workoutTypeLabel(value) {
  return WORKOUT_TYPES.find((t) => t.value === value)?.label || value;
}

// "MM:SS" or "HH:MM:SS" -> total seconds. Returns null if unparseable.
export function parseDurationToSeconds(input) {
  if (!input) return null;
  const parts = input.trim().split(':').map((p) => parseInt(p, 10));
  if (parts.some((p) => Number.isNaN(p))) return null;
  if (parts.length === 2) {
    const [m, s] = parts;
    return m * 60 + s;
  }
  if (parts.length === 3) {
    const [h, m, s] = parts;
    return h * 3600 + m * 60 + s;
  }
  return null;
}

// total seconds -> "MM:SS" or "H:MM:SS" for durations over an hour.
export function formatSecondsToDuration(totalSeconds) {
  if (totalSeconds == null) return '';
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

// Live pace preview while typing, mirroring CreatePlanPage's liveTargetPace pattern.
export function computeLivePace(distanceKmStr, durationInput) {
  const distanceKm = parseFloat(distanceKmStr);
  const durationSeconds = parseDurationToSeconds(durationInput);
  if (!distanceKm || distanceKm <= 0 || !durationSeconds) return null;
  const secPerKm = Math.round(durationSeconds / distanceKm);
  const min = Math.floor(secPerKm / 60);
  const sec = secPerKm % 60;
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')} /km`;
}

// Consumer-facing labels for the derived completion state (never stored --
// see app/workouts/service.py::derive_completion_status). Deliberately never
// says "Missed" or "Failed" anywhere in the UI.
export function completionLabel(status) {
  if (status === 'completed') return 'Completed';
  if (status === 'missed') return 'Not logged';
  if (status === 'scheduled') return 'Not logged yet';
  return null;
}

export function todayIsoDate() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}
