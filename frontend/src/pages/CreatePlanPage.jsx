import React, { useState, useMemo } from 'react';
import { ArrowRight, Sparkles, Loader2, AlertCircle } from 'lucide-react';
import DisclaimerBanner from '../components/DisclaimerBanner';
import Button from '../components/ui/Button';
import { generateTrainingPlan } from '../api';

const inputClass = "w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[44px]";
const labelClass = "block text-xs font-semibold text-slate-700 mb-1";
const hintClass = "text-[11px] text-slate-400 mt-1 block";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function CreatePlanPage({ onPlanGenerated }) {
  const [formData, setFormData] = useState({
    age: 21,
    gender: 'Male',
    experience_level: 'Intermediate',
    pb_5k: '24:56',
    pb_10k: '',
    target_race_distance: '5K',
    target_race_time: '23:00',
    current_weekly_mileage: 25.0,
    training_days_per_week: 4,
    preferred_training_days: ['Tuesday', 'Thursday', 'Friday', 'Sunday'],
    plan_duration_weeks: 8,
    injury_limitations: 'Mild knee discomfort on hard asphalt downhills',
    easy_run_pace: '05:45',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Compute live target race pace
  const liveTargetPace = useMemo(() => {
    try {
      const timeStr = formData.target_race_time.trim();
      const parts = timeStr.split(':');
      let totalSec = 0;
      if (parts.length === 2) {
        totalSec = parseInt(parts[0]) * 60 + parseInt(parts[1]);
      } else if (parts.length === 3) {
        totalSec = parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
      } else {
        return null;
      }

      let distKm = 5.0;
      if (formData.target_race_distance === '10K') distKm = 10.0;
      if (formData.target_race_distance === 'Half Marathon') distKm = 21.0975;

      const secPerKm = Math.round(totalSec / distKm);
      const min = Math.floor(secPerKm / 60);
      const sec = secPerKm % 60;
      return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')} /km`;
    } catch {
      return null;
    }
  }, [formData.target_race_time, formData.target_race_distance]);

  const handleWeekdayToggle = (day) => {
    const current = [...formData.preferred_training_days];
    const exists = current.includes(day);

    let updated;
    if (exists) {
      if (current.length <= 1) return; // Must have at least 1 day
      updated = current.filter(d => d !== day);
    } else {
      updated = [...current, day];
    }

    setFormData({
      ...formData,
      preferred_training_days: updated,
      training_days_per_week: Math.min(Math.max(updated.length, 1), 7)
    });
  };

  const handleFillExample = () => {
    setFormData({
      age: 21,
      gender: 'Male',
      experience_level: 'Intermediate',
      pb_5k: '24:56',
      pb_10k: '51:30',
      target_race_distance: '5K',
      target_race_time: '23:00',
      current_weekly_mileage: 25.0,
      training_days_per_week: 4,
      preferred_training_days: ['Tuesday', 'Thursday', 'Friday', 'Sunday'],
      plan_duration_weeks: 8,
      injury_limitations: 'Mild patellar discomfort after long runs',
      easy_run_pace: '05:45',
    });
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const payload = {
        ...formData,
        age: parseInt(formData.age),
        current_weekly_mileage: parseFloat(formData.current_weekly_mileage),
        training_days_per_week: parseInt(formData.training_days_per_week),
        plan_duration_weeks: parseInt(formData.plan_duration_weeks),
        pb_10k: formData.pb_10k ? formData.pb_10k.trim() : null,
        injury_limitations: formData.injury_limitations ? formData.injury_limitations.trim() : null,
      };

      const result = await generateTrainingPlan(payload);
      onPlanGenerated(result);
    } catch (err) {
      setError(err.message || 'Error communicating with recommendation server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <DisclaimerBanner />

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-100 gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Create Running Profile</h2>
            <p className="text-xs text-slate-500 mt-1">
              Enter your physiological and race parameters for rule-based VDOT modeling and AI personalization.
            </p>
          </div>

          <button
            type="button"
            onClick={handleFillExample}
            className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg border border-indigo-200 transition-colors flex items-center space-x-1.5 self-start cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
            <span>Load S2 Research Example</span>
          </button>
        </div>

        {error && (
          <div className="my-5 p-4 bg-rose-50 border-l-4 border-rose-500 text-rose-800 rounded-r-lg text-xs flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Validation Error</p>
              <p>{error}</p>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-6">
          {/* Section 1: Runner Profile */}
          <div className="space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">1. Runner Profile</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Age</label>
                <input
                  type="number"
                  min="12"
                  max="99"
                  required
                  value={formData.age}
                  onChange={(e) => setFormData({ ...formData, age: e.target.value })}
                  className={inputClass}
                />
              </div>

              <div>
                <label className={labelClass}>Gender</label>
                <select
                  value={formData.gender}
                  onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                  className={inputClass}
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other / Prefer not to say</option>
                </select>
              </div>

              <div>
                <label className={labelClass}>Experience Level</label>
                <select
                  value={formData.experience_level}
                  onChange={(e) => setFormData({ ...formData, experience_level: e.target.value })}
                  className={inputClass}
                >
                  <option value="Beginner">Beginner (&lt; 1 yr)</option>
                  <option value="Intermediate">Intermediate (1-3 yrs)</option>
                  <option value="Advanced">Advanced (3+ yrs / Competitive)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Section 2: Performance Benchmarks */}
          <div className="space-y-4 pt-4 border-t border-slate-100">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">2. Performance Benchmarks</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>
                  5K Personal Best <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="24:56"
                  required
                  value={formData.pb_5k}
                  onChange={(e) => setFormData({ ...formData, pb_5k: e.target.value })}
                  className={inputClass}
                />
                <span className={hintClass}>Format: MM:SS (e.g. 24:56)</span>
              </div>

              <div>
                <label className={labelClass}>
                  10K Personal Best <span className="text-slate-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="52:00"
                  value={formData.pb_10k}
                  onChange={(e) => setFormData({ ...formData, pb_10k: e.target.value })}
                  className={inputClass}
                />
                <span className={hintClass}>Format: MM:SS (e.g. 52:10)</span>
              </div>

              <div>
                <label className={labelClass}>
                  Average Easy Run Pace <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  placeholder="05:45"
                  required
                  value={formData.easy_run_pace}
                  onChange={(e) => setFormData({ ...formData, easy_run_pace: e.target.value })}
                  className={inputClass}
                />
                <span className={hintClass}>Format: MM:SS /km (e.g. 05:45)</span>
              </div>
            </div>
          </div>

          {/* Section 3: Target Race Goal */}
          <div className="space-y-4 pt-4 border-t border-slate-100">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">3. Target Race Goal</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Target Race Distance</label>
                <select
                  value={formData.target_race_distance}
                  onChange={(e) => setFormData({ ...formData, target_race_distance: e.target.value })}
                  className={`${inputClass} font-medium`}
                >
                  <option value="5K">5K (5.0 km)</option>
                  <option value="10K">10K (10.0 km)</option>
                  <option value="Half Marathon">Half Marathon (21.1 km)</option>
                </select>
              </div>

              <div>
                <label className={labelClass}>Target Race Time</label>
                <input
                  type="text"
                  placeholder="23:00"
                  required
                  value={formData.target_race_time}
                  onChange={(e) => setFormData({ ...formData, target_race_time: e.target.value })}
                  className={inputClass}
                />
                <span className={hintClass}>MM:SS or HH:MM:SS</span>
              </div>

              <div className="bg-indigo-50/70 p-3 rounded-xl border border-indigo-100 flex flex-col justify-center">
                <span className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wider">Required Race Pace</span>
                <span className="text-lg font-black text-indigo-950 mt-0.5">
                  {liveTargetPace || 'Enter target time'}
                </span>
              </div>
            </div>
          </div>

          {/* Section 4: Preferences & Constraints */}
          <div className="space-y-4 pt-4 border-t border-slate-100">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">4. Preferences &amp; Constraints</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>
                  Current Weekly Mileage (km/week)
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="5"
                  max="180"
                  required
                  value={formData.current_weekly_mileage}
                  onChange={(e) => setFormData({ ...formData, current_weekly_mileage: e.target.value })}
                  className={inputClass}
                />
                <span className={hintClass}>Baseline week mileage will respect this volume.</span>
              </div>

              <div>
                <label className={labelClass}>
                  Plan Duration ({formData.plan_duration_weeks} Weeks)
                </label>
                <input
                  type="range"
                  min="4"
                  max="16"
                  step="1"
                  value={formData.plan_duration_weeks}
                  onChange={(e) => setFormData({ ...formData, plan_duration_weeks: e.target.value })}
                  className="w-full accent-indigo-600 mt-3 min-h-[44px] sm:min-h-0"
                />
                <div className="flex justify-between text-[11px] text-slate-400 -mt-1">
                  <span>4 wks</span>
                  <span className="font-semibold text-indigo-600">{formData.plan_duration_weeks} weeks</span>
                  <span>16 wks</span>
                </div>
              </div>
            </div>

            {/* Preferred Training Days Pill Selection */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-2">
                Preferred Workout Days ({formData.preferred_training_days.length} days selected)
              </label>
              <div className="flex flex-wrap gap-2">
                {WEEKDAYS.map((day) => {
                  const isSelected = formData.preferred_training_days.includes(day);
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => handleWeekdayToggle(day)}
                      className={`min-w-[52px] min-h-[40px] px-3 py-2 rounded-lg text-xs font-semibold transition-all border cursor-pointer ${
                        isSelected
                          ? 'bg-indigo-600 text-white border-indigo-600 shadow-2xs'
                          : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      {day.slice(0, 3)}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Injury Limitations */}
            <div>
              <label className={labelClass}>
                Injury History / Limitations <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Mild shin splints, tight calves, previous hamstring strain"
                value={formData.injury_limitations}
                onChange={(e) => setFormData({ ...formData, injury_limitations: e.target.value })}
                className={inputClass}
              />
              <span className={hintClass}>
                The AI component will tailor warm-ups, execution cues, and recovery advice for this limitation.
              </span>
            </div>
          </div>

          {/* Submit Action */}
          <div className="pt-6 border-t border-slate-100 flex justify-end">
            <Button type="submit" disabled={loading} size="lg" className="w-full sm:w-auto">
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Computing VDOT &amp; Generating AI Plan...</span>
                </>
              ) : (
                <>
                  <span>Generate Personalized Training Plan</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
