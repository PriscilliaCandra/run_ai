import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { PlusCircle } from 'lucide-react';
import WorkoutForm from '../components/WorkoutForm';
import { createWorkout } from '../api';

export default function LogWorkoutPage() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (payload) => {
    setSubmitting(true);
    setError(null);
    try {
      await createWorkout(payload);
      navigate('/history', { replace: true });
    } catch (err) {
      setError(err.message || 'Failed to log this workout. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8">
        <div className="flex items-center gap-2 pb-6 border-b border-slate-100">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center shrink-0">
            <PlusCircle className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Log a Workout</h2>
            <p className="text-xs text-slate-500">Record a run you've completed. Pace is calculated automatically.</p>
          </div>
        </div>

        <div className="mt-6">
          <WorkoutForm onSubmit={handleSubmit} submitting={submitting} submitError={error} submitLabel="Log Workout" />
        </div>
      </div>
    </div>
  );
}
