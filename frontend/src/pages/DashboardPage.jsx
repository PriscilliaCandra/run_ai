import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PlusCircle, Calendar, TrendingUp, Info, CheckCircle2, CalendarClock } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { fetchDashboardSummary } from '../api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import WorkoutCard from '../components/WorkoutCard';
import { LoadingState, ErrorState } from '../components/ui/StatusMessage';
import { workoutTypeLabel, completionLabel } from '../utils/workout';

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await fetchDashboardSummary());
    } catch (err) {
      setError(err.message || 'Failed to load your dashboard.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-900">Good to see you, {user?.display_name}</h1>

      {loading ? (
        <div className="mt-6"><LoadingState label="Loading your dashboard..." /></div>
      ) : error ? (
        <div className="mt-6"><ErrorState message={error} actionLabel="Try Again" onAction={load} /></div>
      ) : (
        <div className="mt-6 space-y-6">
          {/* This week's totals */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 sm:p-6">
            <h2 className="text-sm font-bold text-slate-800 mb-4">This Week</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <Stat label="Distance" value={`${summary.this_week.total_distance_km.toFixed(1)} km`} />
              <Stat label="Runs" value={summary.this_week.run_count} />
              <Stat label="Duration" value={formatDuration(summary.this_week.total_duration_seconds)} />
              <Stat label="Avg Pace" value={summary.this_week.average_pace_display || '—'} />
            </div>
          </div>

          {/* Active plan / today's workout */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-800">Training Plan</h2>
              <Link to="/plans" className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">View all plans</Link>
            </div>

            {!summary.active_plan ? (
              <div className="text-center py-6">
                <p className="text-sm text-slate-600 mb-3">You don't have an active training plan yet.</p>
                <Link to="/plans/new"><Button size="sm"><PlusCircle className="w-3.5 h-3.5" /> Create a Training Plan</Button></Link>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 mb-4">
                  <Badge variant="indigo" icon={Calendar}>
                    Week {summary.active_plan.current_week} of {summary.active_plan.total_weeks}
                  </Badge>
                  <Badge variant="neutral">{summary.active_plan.target_race_distance}</Badge>
                  <Badge variant="neutral">{summary.active_plan.target_pace_per_km} /km target</Badge>
                </div>
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden mb-4">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all"
                    style={{ width: `${(summary.active_plan.current_week / summary.active_plan.total_weeks) * 100}%` }}
                  />
                </div>

                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Today's Workout</h3>
                  {summary.active_plan.week1_total_loggable_count != null && (
                    <span className="text-[11px] font-semibold text-slate-500">
                      {summary.active_plan.week1_completed_count} of {summary.active_plan.week1_total_loggable_count} planned runs logged this week
                    </span>
                  )}
                </div>
                {!summary.active_plan.week1_detail_available ? (
                  <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
                    <Info className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>Detailed daily workouts aren't available past week 1 yet. Full weekly schedules are coming in a future update.</span>
                  </div>
                ) : summary.active_plan.today_scheduled_workout ? (
                  <TodayWorkoutCard workout={summary.active_plan.today_scheduled_workout} navigate={navigate} />
                ) : (
                  <p className="text-xs text-slate-500">No scheduled workout for today.</p>
                )}

                {summary.active_plan.week1_detail_available && summary.active_plan.upcoming_scheduled_workout && (
                  <div className="mt-3 p-3 bg-slate-50 rounded-xl border border-slate-100 flex items-center gap-2.5">
                    <CalendarClock className="w-4 h-4 text-slate-400 shrink-0" />
                    <span className="text-xs text-slate-600">
                      <span className="font-semibold text-slate-800">Up next:</span> {summary.active_plan.upcoming_scheduled_workout.day_of_week} &middot; {workoutTypeLabel(summary.active_plan.upcoming_scheduled_workout.workout_type)}
                      {summary.active_plan.upcoming_scheduled_workout.distance_km > 0 ? ` — ${summary.active_plan.upcoming_scheduled_workout.distance_km.toFixed(1)} km` : ''}
                    </span>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Log workout CTA */}
          <div className="bg-indigo-600 rounded-2xl p-5 sm:p-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
            <div>
              <h2 className="text-white font-bold">Ready to log a run?</h2>
              <p className="text-indigo-100 text-xs mt-0.5">Record your distance, time, and how it felt.</p>
            </div>
            <Link to="/workouts/new">
              <Button variant="secondary" className="shrink-0"><PlusCircle className="w-4 h-4" /> Log Workout</Button>
            </Link>
          </div>

          {/* Recent activity */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 sm:p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-800 flex items-center gap-1.5"><TrendingUp className="w-4 h-4 text-indigo-500" /> Recent Activity</h2>
              <Link to="/history" className="text-xs font-semibold text-indigo-600 hover:text-indigo-800">View history</Link>
            </div>
            {summary.recent_activities.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">No workouts logged yet.</p>
            ) : (
              <div className="divide-y divide-slate-100">
                {summary.recent_activities.map((w) => (
                  <Link key={w.id} to={`/workouts/${w.id}`} className="flex items-center justify-between py-2.5 hover:bg-slate-50 -mx-2 px-2 rounded-lg">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900">{new Date(w.workout_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                      <Badge variant="indigo">{workoutTypeLabel(w.workout_type)}</Badge>
                    </div>
                    <span className="text-xs text-slate-500">{w.distance_km.toFixed(2)} km &middot; {w.pace_display}</span>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function TodayWorkoutCard({ workout, navigate }) {
  const status = workout.completion_status; // null for rest days
  return (
    <div>
      {status && (
        <div className="flex items-center justify-between mb-2">
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
            status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
          }`}>
            {status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
            {completionLabel(status)}
          </span>
          {status === 'completed' && workout.linked_workout_logs?.[0] ? (
            <Link to={`/workouts/${workout.linked_workout_logs[0].id}`} className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800">
              View logged workout
            </Link>
          ) : (
            <button
              onClick={() => navigate('/workouts/new', { state: { scheduledWorkout: workout } })}
              className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer"
            >
              Log this workout
            </button>
          )}
        </div>
      )}
      <WorkoutCard
        workout={{
          day: workout.day_of_week,
          workout_type: workout.workout_type,
          distance_km: workout.distance_km,
          pace_target: workout.pace_target,
          intensity_zone: workout.intensity_zone,
          purpose: workout.purpose,
        }}
      />
      {status === 'completed' && workout.linked_workout_logs?.[0] && (
        <div className="mt-2 p-3 bg-emerald-50/60 border border-emerald-100 rounded-xl text-xs text-emerald-900">
          <span className="font-semibold">Actual: </span>
          {workout.linked_workout_logs[0].distance_km.toFixed(2)} km &middot; {workout.linked_workout_logs[0].pace_display}
          {workout.linked_workout_logs[0].rpe != null && <> &middot; RPE {workout.linked_workout_logs[0].rpe}/10</>}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
      <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">{label}</span>
      <div className="text-lg font-black text-slate-900 mt-0.5">{value}</div>
    </div>
  );
}

function formatDuration(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}
