import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlusCircle, FileText } from 'lucide-react';
import { fetchMyPlans } from '../api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/StatusMessage';

export default function PlansPage() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setPlans(await fetchMyPlans());
    } catch (err) {
      setError(err.message || 'Failed to load your training plans.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-slate-900">Your Training Plans</h2>
        <Link to="/plans/new"><Button size="sm"><PlusCircle className="w-3.5 h-3.5" /> New Plan</Button></Link>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-4 sm:p-5">
        {loading ? (
          <LoadingState label="Loading your plans..." />
        ) : error ? (
          <ErrorState message={error} actionLabel="Try Again" onAction={load} />
        ) : plans.length === 0 ? (
          <EmptyState
            icon={FileText}
            title="No training plans yet"
            description="Generate a personalized training plan based on your runner profile."
            actionLabel="Create Your First Plan"
            onAction={() => window.location.assign('/plans/new')}
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {plans.map((p) => (
              <Link
                key={p.plan_id}
                to={`/plans/${p.plan_id}`}
                className="flex items-center justify-between gap-3 py-3 hover:bg-slate-50 -mx-2 px-2 rounded-lg transition-colors"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-900">{p.race_distance}</span>
                    <Badge variant={p.status === 'active' ? 'indigo' : 'neutral'}>{p.status}</Badge>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Target {p.target_time} &middot; VDOT {p.calculated_vdot.toFixed(1)}
                  </div>
                </div>
                <span className="text-[11px] text-slate-400 shrink-0">
                  {p.start_date ? new Date(p.start_date).toLocaleDateString() : new Date(p.created_at).toLocaleDateString()}
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
