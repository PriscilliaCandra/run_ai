import React, { useEffect, useState } from 'react';
import { User, LogOut, Save, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { fetchMyProfile, updateMyProfile } from '../api';
import Button from '../components/ui/Button';
import { LoadingState, ErrorState } from '../components/ui/StatusMessage';

const inputClass = "w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[44px]";
const labelClass = "block text-xs font-semibold text-slate-700 mb-1";

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saved, setSaved] = useState(false);

  const load = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchMyProfile();
      setProfile(data);
    } catch (err) {
      setLoadError(err.message || 'Failed to load your profile.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleChange = (field, value) => {
    setProfile({ ...profile, [field]: value });
    setSaved(false);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    try {
      const payload = {
        ...profile,
        age: profile.age === '' || profile.age === null ? null : parseInt(profile.age),
        current_weekly_mileage: profile.current_weekly_mileage === '' || profile.current_weekly_mileage === null ? null : parseFloat(profile.current_weekly_mileage),
        training_days_per_week: profile.training_days_per_week === '' || profile.training_days_per_week === null ? null : parseInt(profile.training_days_per_week),
      };
      delete payload.updated_at;
      const updated = await updateMyProfile(payload);
      setProfile(updated);
      setSaved(true);
    } catch (err) {
      setSaveError(err.message || 'Failed to save your profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8 mb-6">
        <div className="flex items-center justify-between flex-wrap gap-3 pb-6 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">{user?.display_name}</h2>
              <p className="text-xs text-slate-500">{user?.email}</p>
            </div>
          </div>
          <Button onClick={logout} variant="secondary" size="sm">
            <LogOut className="w-3.5 h-3.5" />
            <span>Log Out</span>
          </Button>
        </div>

        <div className="mt-6">
          <h3 className="text-sm font-bold text-slate-900 mb-1">Runner Profile</h3>
          <p className="text-xs text-slate-500 mb-4">
            Used to personalize future training plans. All fields are optional and can be updated any time.
          </p>

          {loading ? (
            <LoadingState label="Loading your profile..." />
          ) : loadError ? (
            <ErrorState message={loadError} actionLabel="Try Again" onAction={load} />
          ) : (
            <form onSubmit={handleSave} className="space-y-4">
              {saveError && (
                <div className="p-3 bg-rose-50 border-l-4 border-rose-500 text-rose-800 rounded-r-lg text-xs flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <span>{saveError}</span>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className={labelClass}>Age</label>
                  <input type="number" min="12" max="99" value={profile.age ?? ''} onChange={(e) => handleChange('age', e.target.value)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Experience Level</label>
                  <select value={profile.experience_level ?? ''} onChange={(e) => handleChange('experience_level', e.target.value || null)} className={inputClass}>
                    <option value="">Not set</option>
                    <option value="Beginner">Beginner</option>
                    <option value="Intermediate">Intermediate</option>
                    <option value="Advanced">Advanced</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Training Days / Week</label>
                  <input type="number" min="1" max="7" value={profile.training_days_per_week ?? ''} onChange={(e) => handleChange('training_days_per_week', e.target.value)} className={inputClass} />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className={labelClass}>5K Personal Best</label>
                  <input type="text" placeholder="24:56" value={profile.pb_5k ?? ''} onChange={(e) => handleChange('pb_5k', e.target.value || null)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>10K Personal Best</label>
                  <input type="text" placeholder="52:10" value={profile.pb_10k ?? ''} onChange={(e) => handleChange('pb_10k', e.target.value || null)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Easy Run Pace</label>
                  <input type="text" placeholder="05:45" value={profile.easy_run_pace ?? ''} onChange={(e) => handleChange('easy_run_pace', e.target.value || null)} className={inputClass} />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className={labelClass}>Target Race Distance</label>
                  <select value={profile.target_race_distance ?? ''} onChange={(e) => handleChange('target_race_distance', e.target.value || null)} className={inputClass}>
                    <option value="">Not set</option>
                    <option value="5K">5K</option>
                    <option value="10K">10K</option>
                    <option value="Half Marathon">Half Marathon</option>
                  </select>
                </div>
                <div>
                  <label className={labelClass}>Target Race Time</label>
                  <input type="text" placeholder="23:00" value={profile.target_race_time ?? ''} onChange={(e) => handleChange('target_race_time', e.target.value || null)} className={inputClass} />
                </div>
                <div>
                  <label className={labelClass}>Current Weekly Mileage (km)</label>
                  <input type="number" step="0.5" min="0" value={profile.current_weekly_mileage ?? ''} onChange={(e) => handleChange('current_weekly_mileage', e.target.value)} className={inputClass} />
                </div>
              </div>

              <div>
                <label className={labelClass}>Injury / Limitations <span className="text-slate-400 font-normal">(Optional)</span></label>
                <input type="text" value={profile.injury_limitations ?? ''} onChange={(e) => handleChange('injury_limitations', e.target.value || null)} className={inputClass} />
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-end gap-3">
                {saved && (
                  <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                    <CheckCircle2 className="w-4 h-4" /> Saved
                  </span>
                )}
                <Button type="submit" disabled={saving}>
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  <span>{saving ? 'Saving...' : 'Save Profile'}</span>
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
