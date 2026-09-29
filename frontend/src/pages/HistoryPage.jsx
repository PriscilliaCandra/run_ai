import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlusCircle, ChevronLeft, ChevronRight, ListChecks } from 'lucide-react';
import { fetchWorkouts } from '../api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { LoadingState, ErrorState, EmptyState } from '../components/ui/StatusMessage';
import { WORKOUT_TYPES, workoutTypeLabel } from '../utils/workout';

const inputClass = "w-full px-3 py-2 border border-slate-300 rounded-lg text-xs focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[40px]";

export default function HistoryPage() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [workoutType, setWorkoutType] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchWorkouts({
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        workoutType: workoutType || undefined,
        page,
        pageSize,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err.message || 'Failed to load your workout history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [page, dateFrom, dateTo, workoutType]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleFilterChange = (setter) => (e) => {
    setter(e.target.value);
    setPage(1);
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Workout History</h2>
          <p className="text-xs text-slate-500 mt-0.5">{total} logged workout{total === 1 ? '' : 's'}</p>
        </div>
        <Link to="/workouts/new">
          <Button size="sm"><PlusCircle className="w-3.5 h-3.5" /> Log Workout</Button>
        </Link>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-4 sm:p-5 mb-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="text-[11px] font-semibold text-slate-500 block mb-1">From</label>
            <input type="date" value={dateFrom} onChange={handleFilterChange(setDateFrom)} className={inputClass} />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-slate-500 block mb-1">To</label>
            <input type="date" value={dateTo} onChange={handleFilterChange(setDateTo)} className={inputClass} />
          </div>
          <div>
            <label className="text-[11px] font-semibold text-slate-500 block mb-1">Workout Type</label>
            <select value={workoutType} onChange={handleFilterChange(setWorkoutType)} className={inputClass}>
              <option value="">All types</option>
              {WORKOUT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-4 sm:p-5">
        {loading ? (
          <LoadingState label="Loading history..." />
        ) : error ? (
          <ErrorState message={error} actionLabel="Try Again" onAction={load} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={ListChecks}
            title="No workouts found"
            description={total === 0 && !dateFrom && !dateTo && !workoutType ? "You haven't logged any workouts yet." : "No workouts match these filters."}
            actionLabel={total === 0 ? "Log Your First Workout" : undefined}
            onAction={total === 0 ? () => window.location.assign('/workouts/new') : undefined}
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((w) => (
              <Link
                key={w.id}
                to={`/workouts/${w.id}`}
                className="flex items-center justify-between gap-3 py-3 hover:bg-slate-50 -mx-2 px-2 rounded-lg transition-colors"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-900">
                      {new Date(w.workout_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                    <Badge variant="indigo">{workoutTypeLabel(w.workout_type)}</Badge>
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {w.distance_km.toFixed(2)} km &middot; {w.pace_display}
                    {w.rpe != null && <> &middot; RPE {w.rpe}/10</>}
                  </div>
                </div>
                <div className="text-xs font-semibold text-slate-400 shrink-0">
                  {Math.floor(w.duration_seconds / 60)} min
                </div>
              </Link>
            ))}
          </div>
        )}

        {!loading && !error && items.length > 0 && totalPages > 1 && (
          <div className="flex items-center justify-between pt-4 mt-2 border-t border-slate-100">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="w-3.5 h-3.5" /> Prev
            </Button>
            <span className="text-xs text-slate-500">Page {page} of {totalPages}</span>
            <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
