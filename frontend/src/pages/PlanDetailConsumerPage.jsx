import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Award } from 'lucide-react';
import { fetchPlanById } from '../api';
import Badge from '../components/ui/Badge';
import WorkoutCard from '../components/WorkoutCard';
import { LoadingState, ErrorState } from '../components/ui/StatusMessage';

export default function PlanDetailConsumerPage() {
  const { id } = useParams();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setPlan(await fetchPlanById(id));
    } catch (err) {
      setError(err.message || 'This plan could not be found.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

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
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold mb-3">
              <Award className="w-3 h-3" /> Personalized Training Plan
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

          <h3 className="text-lg font-bold text-slate-900 mb-4">Week 1 Schedule</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plan.ai_personalized_plan.workouts.map((w, idx) => (
              <WorkoutCard key={idx} workout={w} />
            ))}
          </div>

          <p className="text-[11px] text-slate-400 mt-6 text-center">
            Full multi-week daily schedules are coming in a future update. For now, use this week-1 schedule as your training template each week of your {plan.rule_based_plan.week_1_plan ? '' : ''}plan.
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
