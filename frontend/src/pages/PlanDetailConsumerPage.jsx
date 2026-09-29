import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Award, CheckCircle2, Moon, Info } from 'lucide-react';
import { fetchPlanById, fetchPlanWorkouts } from '../api';
import Badge from '../components/ui/Badge';
import WorkoutCard from '../components/WorkoutCard';
import { LoadingState, ErrorState } from '../components/ui/StatusMessage';
import { completionLabel } from '../utils/workout';

export default function PlanDetailConsumerPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [scheduled, setScheduled] = useState([]); // enriched training_plan_workouts
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedWeek, setSelectedWeek] = useState(1);

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

  const progression = plan?.rule_based_plan?.progression_schedule || [];
  const currentProgression = progression.find((p) => p.week_number === selectedWeek) || progression[0];

  // Workouts for the selected week
  const weekScheduled = scheduled.filter((s) => s.week_number === selectedWeek);
  const scheduledByDay = Object.fromEntries(weekScheduled.map((s) => [s.day_of_week, s]));
  const loggableCount = weekScheduled.filter((s) => s.completion_status !== null).length;
  const completedCount = weekScheduled.filter((s) => s.completion_status === 'completed').length;

  // Determine display workouts:
  // Week 1 uses rich AI workouts if available, merged with week 1 scheduled rows
  // Week 2+ uses deterministic workouts from scheduled rows (or rule_based_plan.weeks)
  let displayItems = [];
  if (selectedWeek === 1 && plan?.ai_personalized_plan?.workouts) {
    displayItems = plan.ai_personalized_plan.workouts.map((w) => ({
      workout: w,
      scheduledItem: scheduledByDay[w.day] || null,
    }));
  } else if (weekScheduled.length > 0) {
    displayItems = weekScheduled.map((s) => ({
      workout: {
        day: s.day_of_week,
        workout_type: s.workout_type,
        distance_km: s.distance_km,
        pace_target: s.pace_target,
        intensity_zone: s.intensity_zone,
        purpose: s.purpose,
      },
      scheduledItem: s,
    }));
  } else if (plan?.rule_based_plan?.weeks?.[selectedWeek - 1]?.workouts) {
    displayItems = plan.rule_based_plan.weeks[selectedWeek - 1].workouts.map((w) => ({
      workout: w,
      scheduledItem: null,
    }));
  }

  const selectedWeekVolume = currentProgression?.target_mileage_km
    || (selectedWeek === 1 ? (plan?.ai_personalized_plan?.weekly_mileage_km || plan?.rule_based_plan?.week_1_plan?.weekly_mileage_km) : 0);

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
                label={`Week ${selectedWeek} Target`}
                value={`${typeof selectedWeekVolume === 'number' ? selectedWeekVolume.toFixed(1) : selectedWeekVolume} km`}
              />
              <Stat label="Feasibility" value={plan.explainability?.physiological_engine_values?.feasibility_status || '—'} small />
            </div>
          </div>

          {/* Multi-Week Navigation Tabs */}
          {progression.length > 1 && (
            <div className="bg-white rounded-xl border border-slate-200 p-2.5 mb-6 shadow-xs overflow-x-auto">
              <div className="flex items-center gap-2 min-w-max">
                {progression.map((p) => {
                  const isSelected = p.week_number === selectedWeek;
                  return (
                    <button
                      key={p.week_number}
                      type="button"
                      onClick={() => setSelectedWeek(p.week_number)}
                      className={`px-3.5 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer flex items-center gap-2 ${
                        isSelected
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'bg-slate-50 text-slate-700 hover:bg-slate-100 border border-slate-200/60'
                      }`}
                    >
                      <span>Week {p.week_number}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-sm font-normal ${
                        isSelected ? 'bg-indigo-700/80 text-indigo-100' : 'bg-slate-200 text-slate-600'
                      }`}>
                        {p.target_mileage_km} km
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-slate-900">Week {selectedWeek} Schedule</h3>
                {currentProgression?.phase && (
                  <Badge variant={selectedWeek === 1 ? 'blue' : currentProgression.phase.includes('Recovery') || currentProgression.phase.includes('Cutback') ? 'neutral' : currentProgression.phase.includes('Taper') ? 'purple' : 'indigo'}>
                    {currentProgression.phase}
                  </Badge>
                )}
              </div>
              {currentProgression?.focus_note && (
                <p className="text-xs text-slate-500 mt-0.5">{currentProgression.focus_note}</p>
              )}
            </div>
            {weekScheduled.length > 0 && loggableCount > 0 && (
              <span className="text-xs font-semibold text-slate-500 shrink-0">
                {completedCount} of {loggableCount} planned runs logged this week
              </span>
            )}
          </div>

          {displayItems.length === 0 ? (
            <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500">
              <Info className="w-5 h-5 text-slate-400 mx-auto mb-2" />
              <p className="font-semibold text-slate-700">Daily workouts are not available for Week {selectedWeek} in this plan.</p>
              <p className="text-slate-500 mt-1">This plan was generated with Week 1 detail only. Newly generated plans include full multi-week daily workouts.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-stretch">
              {displayItems.map(({ workout: w, scheduledItem: s }, idx) => {
                const isRest = w.workout_type.toLowerCase().includes('rest') || w.distance_km === 0;

                let topBanner = null;
                if (s && s.completion_status === 'completed') {
                  topBanner = (
                    <div className="bg-emerald-50/80 border-b border-emerald-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
                      <span className="inline-flex items-center gap-1.5 text-emerald-800 font-semibold text-xs">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                        Completed
                      </span>
                      {s.linked_workout_logs?.[0] && (
                        <Link
                          to={`/workouts/${s.linked_workout_logs[0].id}`}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800"
                        >
                          View Log &rarr;
                        </Link>
                      )}
                    </div>
                  );
                } else if (s && s.completion_status) {
                  topBanner = (
                    <div className="bg-amber-50/80 border-b border-amber-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
                      <span className="inline-flex items-center gap-1.5 text-amber-900 font-semibold text-xs">
                        <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                        {completionLabel(s.completion_status)}
                      </span>
                      {plan.status === 'archived' ? null : (
                        <button
                          onClick={() => navigate('/workouts/new', { state: { scheduledWorkout: s } })}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 cursor-pointer"
                        >
                          Log workout &rarr;
                        </button>
                      )}
                    </div>
                  );
                } else if (isRest) {
                  topBanner = (
                    <div className="bg-slate-50 border-b border-slate-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
                      <span className="inline-flex items-center gap-1.5 text-slate-500 font-medium text-xs">
                        <Moon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        Rest &amp; Recovery
                      </span>
                      <span className="text-[11px] text-slate-400 font-medium">Scheduled Rest</span>
                    </div>
                  );
                } else {
                  topBanner = (
                    <div className="bg-slate-50 border-b border-slate-100 px-3.5 py-2.5 flex items-center justify-between min-h-[40px]">
                      <span className="text-xs text-slate-500 font-medium">Planned Run</span>
                      <span className="text-[11px] text-slate-400 font-medium">Week {selectedWeek}</span>
                    </div>
                  );
                }

                let footer = null;
                if (s?.completion_status === 'completed' && s.linked_workout_logs?.[0]) {
                  const log = s.linked_workout_logs[0];
                  footer = (
                    <div className="p-3 bg-emerald-50/50 border-t border-emerald-100 text-xs text-emerald-900">
                      <span className="font-semibold text-emerald-800">Actual: </span>
                      <span>{log.distance_km.toFixed(2)} km &middot; {log.pace_display}</span>
                      {log.rpe != null && <span className="text-emerald-700"> &middot; RPE {log.rpe}/10</span>}
                    </div>
                  );
                }

                return (
                  <div key={idx} className="h-full flex flex-col">
                    <WorkoutCard
                      workout={w}
                      topBanner={topBanner}
                      footer={footer}
                    />
                  </div>
                );
              })}
            </div>
          )}
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
