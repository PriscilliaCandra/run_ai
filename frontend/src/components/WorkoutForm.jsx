import React, { useState } from 'react';
import { Save, Loader2, AlertCircle } from 'lucide-react';
import Button from './ui/Button';
import { WORKOUT_TYPES, parseDurationToSeconds, formatSecondsToDuration, computeLivePace, todayIsoDate } from '../utils/workout';

const inputClass = "w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[44px]";
const labelClass = "block text-xs font-semibold text-slate-700 mb-1";
const hintClass = "text-[11px] text-slate-400 mt-1 block";

export default function WorkoutForm({ initial, onSubmit, submitLabel = 'Save Workout', submitting = false, submitError = null }) {
  const [form, setForm] = useState({
    workout_date: initial?.workout_date || todayIsoDate(),
    distance_km: initial ? String(initial.distance_km) : '',
    duration_input: initial ? formatSecondsToDuration(initial.duration_seconds) : '',
    workout_type: initial?.workout_type || 'EASY',
    avg_heart_rate: initial?.avg_heart_rate ?? '',
    max_heart_rate: initial?.max_heart_rate ?? '',
    cadence_spm: initial?.cadence_spm ?? '',
    elevation_gain_m: initial?.elevation_gain_m ?? '',
    rpe: initial?.rpe ?? null,
    notes: initial?.notes || '',
  });
  const [localError, setLocalError] = useState(null);

  const livePace = computeLivePace(form.distance_km, form.duration_input);

  const handleChange = (field, value) => setForm({ ...form, [field]: value });

  const handleSubmit = (e) => {
    e.preventDefault();
    setLocalError(null);

    const distanceMeters = Math.round(parseFloat(form.distance_km) * 1000);
    const durationSeconds = parseDurationToSeconds(form.duration_input);

    if (!distanceMeters || distanceMeters <= 0) {
      setLocalError('Please enter a valid distance in km.');
      return;
    }
    if (!durationSeconds || durationSeconds <= 0) {
      setLocalError('Please enter a valid duration as MM:SS or HH:MM:SS (e.g. 28:30 or 1:15:00).');
      return;
    }

    onSubmit({
      workout_date: form.workout_date,
      distance_meters: distanceMeters,
      duration_seconds: durationSeconds,
      workout_type: form.workout_type,
      avg_heart_rate: form.avg_heart_rate === '' ? null : parseInt(form.avg_heart_rate),
      max_heart_rate: form.max_heart_rate === '' ? null : parseInt(form.max_heart_rate),
      cadence_spm: form.cadence_spm === '' ? null : parseInt(form.cadence_spm),
      elevation_gain_m: form.elevation_gain_m === '' ? null : parseInt(form.elevation_gain_m),
      rpe: form.rpe === null || form.rpe === '' ? null : parseInt(form.rpe),
      notes: form.notes.trim() ? form.notes.trim() : null,
    });
  };

  const displayError = localError || submitError;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {displayError && (
        <div className="p-3 bg-rose-50 border-l-4 border-rose-500 text-rose-800 rounded-r-lg text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{displayError}</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className={labelClass}>Date <span className="text-rose-500">*</span></label>
          <input
            type="date"
            required
            max={todayIsoDate()}
            value={form.workout_date}
            onChange={(e) => handleChange('workout_date', e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Workout Type <span className="text-rose-500">*</span></label>
          <select
            value={form.workout_type}
            onChange={(e) => handleChange('workout_type', e.target.value)}
            className={inputClass}
          >
            {WORKOUT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className={labelClass}>Distance (km) <span className="text-rose-500">*</span></label>
          <input
            type="number"
            step="0.01"
            min="0.1"
            required
            placeholder="5.0"
            value={form.distance_km}
            onChange={(e) => handleChange('distance_km', e.target.value)}
            className={inputClass}
          />
        </div>
        <div>
          <label className={labelClass}>Duration <span className="text-rose-500">*</span></label>
          <input
            type="text"
            required
            placeholder="28:30"
            value={form.duration_input}
            onChange={(e) => handleChange('duration_input', e.target.value)}
            className={inputClass}
          />
          <span className={hintClass}>MM:SS or HH:MM:SS</span>
        </div>
        <div className="bg-indigo-50/70 p-3 rounded-xl border border-indigo-100 flex flex-col justify-center">
          <span className="text-[11px] font-semibold text-indigo-700 uppercase tracking-wider">Pace (auto)</span>
          <span className="text-lg font-black text-indigo-950 mt-0.5">{livePace || '—'}</span>
        </div>
      </div>

      <div className="pt-4 border-t border-slate-100">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">Optional Details</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <div>
            <label className={labelClass}>Average Heart Rate (bpm)</label>
            <input type="number" min="30" max="250" value={form.avg_heart_rate} onChange={(e) => handleChange('avg_heart_rate', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Max Heart Rate (bpm)</label>
            <input type="number" min="30" max="250" value={form.max_heart_rate} onChange={(e) => handleChange('max_heart_rate', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Cadence (steps/min)</label>
            <input type="number" min="100" max="250" value={form.cadence_spm} onChange={(e) => handleChange('cadence_spm', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Elevation Gain (m)</label>
            <input type="number" min="0" max="10000" value={form.elevation_gain_m} onChange={(e) => handleChange('elevation_gain_m', e.target.value)} className={inputClass} />
          </div>
        </div>

        <div className="mb-4">
          <label className={labelClass}>RPE (Rate of Perceived Exertion), 1–10 <span className="text-slate-400 font-normal">(Optional)</span></label>
          <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5 mt-1">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((val) => (
              <button
                key={val}
                type="button"
                onClick={() => handleChange('rpe', form.rpe === val ? null : val)}
                className={`min-h-[40px] rounded-lg border text-xs font-bold transition-all cursor-pointer ${
                  form.rpe === val
                    ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                }`}
              >
                {val}
              </button>
            ))}
          </div>
          <span className={hintClass}>1 = very light effort, 10 = maximal effort. (Not the same scale as the research evaluation survey.)</span>
        </div>

        <div>
          <label className={labelClass}>Notes <span className="text-slate-400 font-normal">(Optional)</span></label>
          <textarea
            rows={3}
            maxLength={2000}
            placeholder="How did it feel? Anything worth remembering about this run?"
            value={form.notes}
            onChange={(e) => handleChange('notes', e.target.value)}
            className="w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white"
          />
        </div>
      </div>

      <div className="pt-4 border-t border-slate-100 flex justify-end">
        <Button type="submit" disabled={submitting} className="w-full sm:w-auto">
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          <span>{submitting ? 'Saving...' : submitLabel}</span>
        </Button>
      </div>
    </form>
  );
}
