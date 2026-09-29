import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Award, CheckCircle2 } from 'lucide-react';
import { fetchPlanById, fetchPlanWorkouts } from '../api';
import Badge from '../components/ui/Badge';
import WorkoutCard from '../components/WorkoutCard';
import { LoadingState, ErrorState } from '../components/ui/StatusMessage';
import { completionLabel } from '../utils/workout';

export default function PlanDetailConsumerPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [scheduled, setScheduled] = useState([]); // enriched training_plan_workouts, matched to plan.ai_personalized_plan.workouts by day
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [planRes, scheduledRes] = await Promise.all([
        fetchPlanById(id),
        fetchPlanWorkouts(id).catch(() => []), // best-effort: absent for anonymous/legacy plans
      ]);
      setPlan(planRes);
      setScheduled(scheduledRes);
    } catch (err) {
      setError(err.message || 'This plan could not be found.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const scheduledByDay = Object.fromEntries(scheduled.map((s) => [s.day_of_week, s]));
  const loggableCount = scheduled.filter((s) => s.completion_status !== null).length;
  const completedCount = scheduled.filter((s) => s.completion_status === 'completed').length;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Link to="/plans" className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-6 min-h-[36px]">
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Plans</span>
      </Link>

      {loading ? (
        <LoadingState label="Loading your plan..." />
      ) : error ? (
        <ErrorState message={error} actionLabel="Try Again" onAction={load} />
      ) : (
        <>
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 mb-6">
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold">
                <Award className="w-3 h-3" /> Personalized Training Plan
              </div>
              {plan.status === 'archived' && (
                <Badge variant="neutral">Archived — new workouts can't be linked to this plan</Badge>
              )}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <Stat label="VDOT" value={plan.calculated_vdot.toFixed(1)} />
              <Stat label="Target Pace" value={`${plan.target_pace_per_km} /km`} />
              <Stat
                label="Week 1 Volume"
                value={`${(plan.ai_personalized_plan.weekly_mileage_km || plan.rule_based_plan.week_1_plan.weekly_mileage_km).toFixed(1)} km`}
              />
              <Stat label="Feasibility" value={plan.explainability.physiological_engine_values?.feasibility_status || '—'} small />
            </div>
          </div>

          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-900">Week 1 Schedule</h3>
            {scheduled.length > 0 && (
              <span className="text-xs font-semibold text-slate-500">{completedCount} of {loggableCount} planned runs logged this week</span>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plan.ai_personalized_plan.workouts.map((w, idx) => {
              const s = scheduledByDay[w.day];
              return (
                <div key={idx}>
                  {s && s.completion_status && (
                    <div className="flex items-center justify-between mb-1.5 px-0.5">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        s.completion_status === 'completed' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                      }`}>
                        {s.completion_status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                        {completionLabel(s.completion_status)}
                      </span>
                      {s.completion_status === 'completed' && s.linked_workout_logs?.[0] ? (
                        <Link to={`/workouts/${s.linked_workout_logs[0].id}`} className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800">
                          View
                        </Link>
                      ) : plan.status === 'archived' ? null : (
                        // A new link into an archived plan is rejected server-side
                        // (Section 7's locked decision) -- don't offer an action
                        // here that would just fail; historical links (above)
                        // remain fully visible regardless of plan status.
                        <button
                          onClick={() => navigate('/workouts/new', { state: { scheduledWorkout: s } })}
                          className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer"
                        >
                          Log this workout
                        </button>
                      )}
                    </div>
                  )}
                  <WorkoutCard workout={w} />
                  {s?.completion_status === 'completed' && s.linked_workout_logs?.[0] && (
                    <div className="mt-1.5 p-2.5 bg-emerald-50/60 border border-emerald-100 rounded-xl text-[11px] text-emerald-900">
                      <span className="font-semibold">Actual: </span>
                      {s.linked_workout_logs[0].distance_km.toFixed(2)} km &middot; {s.linked_workout_logs[0].pace_display}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <p className="text-[11px] text-slate-400 mt-6 text-center">
            Full multi-week daily schedules aren't available past week 1 yet. For now, use this week-1 schedule as your training template each week of your plan.
          </p>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, small }) {
  return (
    <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100">
      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">{label}</span>
      <div className={`${small ? 'text-sm' : 'text-xl'} font-black text-slate-900 mt-1 truncate`}>{value}</div>
    </div>
  );
}
