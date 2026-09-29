import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { ArrowLeft, Pencil, Trash2, Clock, Gauge, HeartPulse, Footprints, Mountain, X, CalendarCheck, Unlink } from 'lucide-react';
import { fetchWorkoutById, updateWorkout, deleteWorkout } from '../api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import WorkoutForm from '../components/WorkoutForm';
import { LoadingState, ErrorState } from '../components/ui/StatusMessage';
import { workoutTypeLabel } from '../utils/workout';

export default function WorkoutDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [workout, setWorkout] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [unlinking, setUnlinking] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWorkoutById(id);
      setWorkout(data);
    } catch (err) {
      setError(err.message || 'This workout could not be found.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleUpdate = async (payload) => {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateWorkout(id, payload);
      setWorkout(updated);
      setEditing(false);
    } catch (err) {
      setSaveError(err.message || 'Failed to save changes.');
    } finally {
      setSaving(false);
    }
  };

  const handleUnlink = async () => {
    setUnlinking(true);
    try {
      const updated = await updateWorkout(id, { training_plan_workout_id: null });
      setWorkout(updated);
    } catch (err) {
      setError(err.message || 'Failed to unlink this workout.');
    } finally {
      setUnlinking(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteWorkout(id);
      navigate('/history', { replace: true });
    } catch (err) {
      setError(err.message || 'Failed to delete this workout.');
      setDeleting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <Link to="/history" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-6 min-h-[36px]">
        <ArrowLeft className="w-4 h-4" />
        <span>Back to History</span>
      </Link>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8">
        {loading ? (
          <LoadingState label="Loading workout..." />
        ) : error ? (
          <ErrorState message={error} actionLabel="Try Again" onAction={load} />
        ) : editing ? (
          <>
            <div className="flex items-center justify-between pb-6 border-b border-slate-100 mb-6">
              <h2 className="text-lg font-bold text-slate-900">Edit Workout</h2>
              <button onClick={() => setEditing(false)} className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 cursor-pointer" aria-label="Cancel editing">
                <X className="w-4 h-4" />
              </button>
            </div>
            <WorkoutForm
              initial={workout}
              onSubmit={handleUpdate}
              submitting={saving}
              submitError={saveError}
              submitLabel="Save Changes"
            />
          </>
        ) : (
          <>
            <div className="flex flex-wrap items-start justify-between gap-3 pb-6 border-b border-slate-100">
              <div>
                <Badge variant="indigo">{workoutTypeLabel(workout.workout_type)}</Badge>
                <h2 className="text-2xl font-black text-slate-900 mt-2">{workout.distance_km.toFixed(2)} km</h2>
                <p className="text-xs text-slate-500 mt-0.5">{new Date(workout.workout_date).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                  <Pencil className="w-3.5 h-3.5" /> Edit
                </Button>
                <Button variant="danger" size="sm" onClick={() => setConfirmingDelete(true)}>
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </Button>
              </div>
            </div>

            {confirmingDelete && (
              <div className="mt-4 p-4 bg-rose-50 border border-rose-200 rounded-xl text-sm">
                <p className="text-rose-800 font-semibold mb-1">Delete this workout?</p>
                <p className="text-xs text-rose-700 mb-3">This can't be undone from the app.</p>
                <div className="flex gap-2">
                  <Button variant="danger" size="sm" onClick={handleDelete} disabled={deleting}>
                    {deleting ? 'Deleting...' : 'Yes, delete it'}
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => setConfirmingDelete(false)}>Cancel</Button>
                </div>
              </div>
            )}

            {workout.linked_scheduled_workout && (
              <div className="mt-4 p-3.5 bg-indigo-50 border border-indigo-200 rounded-xl flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5 min-w-0">
                  <CalendarCheck className="w-4 h-4 text-indigo-600 shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <span className="text-xs font-bold text-indigo-900 block">
                      Planned: {workoutTypeLabel(workout.linked_scheduled_workout.workout_type) || workout.linked_scheduled_workout.workout_type}
                      {workout.linked_scheduled_workout.distance_km > 0 ? ` — ${workout.linked_scheduled_workout.distance_km.toFixed(1)} km` : ''}
                    </span>
                    <span className="text-[11px] text-indigo-600">{workout.linked_scheduled_workout.pace_target}</span>
                  </div>
                </div>
                <button
                  onClick={handleUnlink}
                  disabled={unlinking}
                  className="shrink-0 flex items-center gap-1 text-[11px] font-semibold text-indigo-700 hover:text-indigo-900 px-2 py-1.5 rounded-lg hover:bg-indigo-100 cursor-pointer disabled:opacity-50"
                >
                  <Unlink className="w-3.5 h-3.5" /> {unlinking ? 'Unlinking...' : 'Unlink from plan'}
                </button>
              </div>
            )}

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-6">
              <StatTile icon={Clock} label="Duration" value={formatDuration(workout.duration_seconds)} />
              <StatTile icon={Gauge} label="Pace" value={workout.pace_display} />
              <StatTile icon={HeartPulse} label="Avg HR" value={workout.avg_heart_rate ? `${workout.avg_heart_rate} bpm` : '—'} />
              <StatTile icon={Footprints} label="Cadence" value={workout.cadence_spm ? `${workout.cadence_spm} spm` : '—'} />
              <StatTile icon={HeartPulse} label="Max HR" value={workout.max_heart_rate ? `${workout.max_heart_rate} bpm` : '—'} />
              <StatTile icon={Mountain} label="Elevation" value={workout.elevation_gain_m != null ? `${workout.elevation_gain_m} m` : '—'} />
              <StatTile label="RPE" value={workout.rpe != null ? `${workout.rpe} / 10` : '—'} />
            </div>

            {workout.notes && (
              <div className="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-100 text-sm text-slate-700">
                <span className="font-semibold text-slate-900 block mb-1">Notes</span>
                {workout.notes}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, value }) {
  return (
    <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
        {Icon && <Icon className="w-3 h-3" />} {label}
      </span>
      <div className="text-sm font-bold text-slate-900 mt-1">{value}</div>
    </div>
  );
}

function formatDuration(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}
