import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, Mail, Loader2, CheckCircle2 } from 'lucide-react';
import { requestPasswordReset } from '../../api';
import Button from '../../components/ui/Button';

const inputClass = "w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[44px]";
const labelClass = "block text-xs font-semibold text-slate-700 mb-1";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await requestPasswordReset(email);
    } finally {
      // Always show the same generic confirmation, whether or not the
      // email exists -- matches the backend's non-enumerating response.
      setLoading(false);
      setSubmitted(true);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-slate-50">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="w-11 h-11 rounded-xl bg-linear-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-xs mb-3">
            <Activity className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Reset your password</h1>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6">
          {submitted ? (
            <div className="text-center py-4">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
              <p className="text-sm text-slate-700 font-semibold">Check your email</p>
              <p className="text-xs text-slate-500 mt-1">If an account exists for that address, a reset link has been sent.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className={labelClass}>Email</label>
                <input
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                />
              </div>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
                <span>{loading ? 'Sending...' : 'Send Reset Link'}</span>
              </Button>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-slate-500 mt-4">
          <Link to="/login" className="font-semibold text-indigo-600 hover:text-indigo-800">Back to login</Link>
        </p>
      </div>
    </div>
  );
}
