import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PlusCircle, Calendar, TrendingUp, Info, CheckCircle2, CalendarClock } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { fetchDashboardSummary, fetchDashboardProgress } from '../api';
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
                  {summary.active_plan.current_week_total_loggable_count != null && (
                    <span className="text-[11px] font-semibold text-slate-500">
                      {summary.active_plan.current_week_completed_count} of {summary.active_plan.current_week_total_loggable_count} planned runs logged this week
                    </span>
                  )}
                </div>
                {!summary.active_plan.current_week_detail_available ? (
                  <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 flex items-start gap-2">
                    <Info className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>Detailed daily workouts are not available for this week. If you have completed your training schedule, congratulations!</span>
                  </div>
                ) : summary.active_plan.today_scheduled_workout ? (
                  <TodayWorkoutCard workout={summary.active_plan.today_scheduled_workout} navigate={navigate} />
                ) : (
                  <p className="text-xs text-slate-500">No scheduled workout for today.</p>
                )}

                {summary.active_plan.current_week_detail_available && summary.active_plan.upcoming_scheduled_workout && (
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

          {/* Progress -- Phase 4: deterministic weekly trend, no scores/predictions */}
          <ProgressSection />
        </div>
      )}
    </div>
  );
}

function ProgressSection() {
  const [progress, setProgress] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setProgress(await fetchDashboardProgress(8));
    } catch (err) {
      setError(err.message || 'Failed to load your progress.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const hasAnyData = progress?.weeks.some((w) => w.run_count > 0);
  const currentWeek = progress?.weeks[progress.weeks.length - 1];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 sm:p-6">
      <h2 className="text-sm font-bold text-slate-800 mb-4">Your Progress</h2>
      {loading ? (
        <LoadingState label="Loading your progress..." />
      ) : error ? (
        <ErrorState message={error} actionLabel="Try Again" onAction={load} />
      ) : !hasAnyData ? (
        <p className="text-xs text-slate-500 py-4 text-center">Log a few workouts to start seeing your progress here.</p>
      ) : (
        <>
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block mb-2">Weekly Distance</span>
          <WeeklyDistanceBars weeks={progress.weeks} />
          <p className="text-xs text-slate-600 mt-3">
            <span className="font-semibold text-slate-900">{currentWeek.logged_days_count}</span> day{currentWeek.logged_days_count === 1 ? '' : 's'} logged this week
          </p>
          {progress.observations.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-100 space-y-1.5">
              {progress.observations.map((obs, idx) => (
                <p key={idx} className="text-xs text-slate-600">{obs}</p>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function WeeklyDistanceBars({ weeks }) {
  const maxDistance = Math.max(...weeks.map((w) => w.total_distance_km), 0.1);
  return (
    <div className="flex items-end gap-1 sm:gap-1.5 h-20">
      {weeks.map((w) => {
        const heightPct = Math.max((w.total_distance_km / maxDistance) * 100, w.total_distance_km > 0 ? 4 : 0);
        return (
          <div
            key={w.week_start}
            className="flex-1 h-full flex flex-col justify-end min-w-0"
            title={`${w.week_start} to ${w.week_end}: ${w.total_distance_km.toFixed(1)} km${w.is_current_week ? ' (this week, in progress)' : ''}`}
          >
            <div
              className={`w-full rounded-t-sm ${w.is_current_week ? 'bg-indigo-300 border border-dashed border-indigo-500' : 'bg-indigo-500'}`}
              style={{ height: `${heightPct}%` }}
            />
          </div>
        );
      })}
    </div>
  );
}

function TodayWorkoutCard({ workout, navigate }) {
  const status = workout.completion_status; // null for rest days
  const isRest = workout.workout_type.toLowerCase().includes('rest') || workout.distance_km === 0;

  let topBanner = null;
  if (status === 'completed') {
    topBanner = (
      <div className="bg-emerald-50/80 border-b border-emerald-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
        <span className="inline-flex items-center gap-1.5 text-emerald-800 font-semibold text-xs">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
          Completed
        </span>
        {workout.linked_workout_logs?.[0] && (
          <Link
            to={`/workouts/${workout.linked_workout_logs[0].id}`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
          >
            View logged workout &rarr;
          </Link>
        )}
      </div>
    );
  } else if (status) {
    topBanner = (
      <div className="bg-amber-50/80 border-b border-amber-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
        <span className="inline-flex items-center gap-1.5 text-amber-900 font-semibold text-xs">
          <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
          {completionLabel(status)}
        </span>
        <button
          onClick={() => navigate('/workouts/new', { state: { scheduledWorkout: workout } })}
          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer"
        >
          Log this workout &rarr;
        </button>
      </div>
    );
  } else if (isRest) {
    topBanner = (
      <div className="bg-slate-50 border-b border-slate-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
        <span className="text-slate-500 font-medium text-xs">Rest &amp; Recovery</span>
        <span className="text-[11px] text-slate-400 font-medium">Scheduled Rest</span>
      </div>
    );
  }

  let footer = null;
  if (status === 'completed' && workout.linked_workout_logs?.[0]) {
    const log = workout.linked_workout_logs[0];
    footer = (
      <div className="p-3 bg-emerald-50/50 border-t border-emerald-100 text-xs text-emerald-900">
        <span className="font-semibold text-emerald-800">Actual: </span>
        <span>{log.distance_km.toFixed(2)} km &middot; {log.pace_display}</span>
        {log.rpe != null && <span className="text-emerald-700"> &middot; RPE {log.rpe}/10</span>}
      </div>
    );
  }

  return (
    <WorkoutCard
      workout={{
        day: workout.day_of_week,
        workout_type: workout.workout_type,
        distance_km: workout.distance_km,
        pace_target: workout.pace_target,
        intensity_zone: workout.intensity_zone,
        purpose: workout.purpose,
      }}
      topBanner={topBanner}
      footer={footer}
    />
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
