import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import { fetchMyProfile, generateTrainingPlan } from '../api';
import Button from '../components/ui/Button';
import { LoadingState } from '../components/ui/StatusMessage';

const inputClass = "w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[44px]";
const labelClass = "block text-xs font-semibold text-slate-700 mb-1";
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function PlanNewPage() {
  const navigate = useNavigate();
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [form, setForm] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  // Runner Profile Integration: pre-fill from the user's saved profile
  // (age, PBs, target race, etc.) so they don't re-enter what's already known.
  useEffect(() => {
    (async () => {
      try {
        const profile = await fetchMyProfile();
        setForm({
          age: profile.age || 25,
          gender: 'Other',
          experience_level: profile.experience_level || 'Intermediate',
          pb_5k: profile.pb_5k || '24:00',
          pb_10k: profile.pb_10k || '',
          target_race_distance: profile.target_race_distance || '5K',
          target_race_time: profile.target_race_time || '23:00',
          current_weekly_mileage: profile.current_weekly_mileage || 20,
          training_days_per_week: profile.training_days_per_week || 4,
          preferred_training_days: ['Tuesday', 'Thursday', 'Saturday', 'Sunday'],
          plan_duration_weeks: 8,
          injury_limitations: profile.injury_limitations || '',
          easy_run_pace: profile.easy_run_pace || '06:00',
        });
      } finally {
        setLoadingProfile(false);
      }
    })();
  }, []);

  const liveTargetPace = useMemo(() => {
    if (!form) return null;
    try {
      const parts = form.target_race_time.trim().split(':');
      let totalSec = parts.length === 3
        ? parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2])
        : parseInt(parts[0]) * 60 + parseInt(parts[1]);
      let distKm = form.target_race_distance === '10K' ? 10.0 : form.target_race_distance === 'Half Marathon' ? 21.0975 : 5.0;
      const secPerKm = Math.round(totalSec / distKm);
      return `${String(Math.floor(secPerKm / 60)).padStart(2, '0')}:${String(secPerKm % 60).padStart(2, '0')} /km`;
    } catch { return null; }
  }, [form?.target_race_time, form?.target_race_distance]);

  const toggleDay = (day) => {
    const current = [...form.preferred_training_days];
    const exists = current.includes(day);
    if (exists && current.length <= 1) return;
    const updated = exists ? current.filter((d) => d !== day) : [...current, day];
    setForm({ ...form, preferred_training_days: updated, training_days_per_week: updated.length });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        ...form,
        age: parseInt(form.age),
        current_weekly_mileage: parseFloat(form.current_weekly_mileage),
        training_days_per_week: parseInt(form.training_days_per_week),
        plan_duration_weeks: parseInt(form.plan_duration_weeks),
        pb_10k: form.pb_10k ? form.pb_10k.trim() : null,
        injury_limitations: form.injury_limitations ? form.injury_limitations.trim() : null,
      };
      const result = await generateTrainingPlan(payload);
      navigate(`/plans/${result.plan_id}`, { replace: true });
    } catch (err) {
      setError(err.message || 'Failed to generate your training plan.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingProfile || !form) {
    return <div className="max-w-2xl mx-auto px-4 py-10"><LoadingState label="Loading your profile..." /></div>;
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8">
        <h2 className="text-xl font-bold text-slate-900 mb-1">Create a Training Plan</h2>
        <p className="text-xs text-slate-500 mb-6">Pre-filled from your profile where possible. This becomes your active plan.</p>

        {error && (
          <div className="mb-5 p-3.5 bg-rose-50 border-l-4 border-rose-500 text-rose-800 rounded-r-lg text-xs flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Age</label>
              <input type="number" min="12" max="99" required value={form.age} onChange={(e) => setForm({ ...form, age: e.target.value })} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Experience Level</label>
              <select value={form.experience_level} onChange={(e) => setForm({ ...form, experience_level: e.target.value })} className={inputClass}>
                <option value="Beginner">Beginner</option>
                <option value="Intermediate">Intermediate</option>
                <option value="Advanced">Advanced</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>5K Personal Best</label>
              <input type="text" required placeholder="24:00" value={form.pb_5k} onChange={(e) => setForm({ ...form, pb_5k: e.target.value })} className={inputClass} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Target Race Distance</label>
              <select value={form.target_race_distance} onChange={(e) => setForm({ ...form, target_race_distance: e.target.value })} className={inputClass}>
                <option value="5K">5K</option>
                <option value="10K">10K</option>
                <option value="Half Marathon">Half Marathon</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Target Race Time</label>
              <input type="text" required placeholder="23:00" value={form.target_race_time} onChange={(e) => setForm({ ...form, target_race_time: e.target.value })} className={inputClass} />
            </div>
            <div className="bg-indigo-50/70 p-3 rounded-xl border border-indigo-100 flex flex-col justify-center">
              <span className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wider">Required Pace</span>
              <span className="text-lg font-black text-indigo-950 mt-0.5">{liveTargetPace || '—'}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Current Weekly Mileage (km)</label>
              <input type="number" step="0.5" min="5" required value={form.current_weekly_mileage} onChange={(e) => setForm({ ...form, current_weekly_mileage: e.target.value })} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Easy Run Pace</label>
              <input type="text" required placeholder="06:00" value={form.easy_run_pace} onChange={(e) => setForm({ ...form, easy_run_pace: e.target.value })} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Plan Duration</label>
              <select value={form.plan_duration_weeks} onChange={(e) => setForm({ ...form, plan_duration_weeks: parseInt(e.target.value) })} className={inputClass}>
                <option value={4}>4 Weeks (Short Block)</option>
                <option value={6}>6 Weeks</option>
                <option value={8}>8 Weeks (Standard)</option>
                <option value={12}>12 Weeks (Comprehensive)</option>
                <option value={16}>16 Weeks (Marathon Prep)</option>
                <option value={20}>20 Weeks</option>
                <option value={24}>24 Weeks (Extended)</option>
              </select>
            </div>
          </div>

          <div>
            <label className={labelClass}>Preferred Training Days ({form.preferred_training_days.length})</label>
            <div className="flex flex-wrap gap-2">
              {WEEKDAYS.map((day) => (
                <button
                  key={day}
                  type="button"
                  onClick={() => toggleDay(day)}
                  className={`min-w-[52px] min-h-[40px] px-3 py-2 rounded-lg text-xs font-semibold border cursor-pointer ${
                    form.preferred_training_days.includes(day)
                      ? 'bg-indigo-600 text-white border-indigo-600'
                      : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  {day.slice(0, 3)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className={labelClass}>Injury / Limitations <span className="text-slate-400 font-normal">(Optional)</span></label>
            <input type="text" value={form.injury_limitations} onChange={(e) => setForm({ ...form, injury_limitations: e.target.value })} className={inputClass} />
          </div>

          <div className="pt-4 border-t border-slate-100 flex justify-end">
            <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
              <span>{submitting ? 'Generating...' : 'Generate Plan'}</span>
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
