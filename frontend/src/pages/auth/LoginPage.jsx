import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Activity, LogIn, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import Button from '../../components/ui/Button';

const inputClass = "w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white min-h-[44px]";
const labelClass = "block text-xs font-semibold text-slate-700 mb-1";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const redirectTo = location.state?.from || '/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message || 'Unable to log in. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10 bg-slate-50">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-6">
          <div className="w-11 h-11 rounded-xl bg-linear-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-xs mb-3">
            <Activity className="w-6 h-6" />
          </div>
          <h1 className="text-xl font-bold text-slate-900">Log in to RunAI</h1>
          <p className="text-xs text-slate-500 mt-1">Welcome back. Let's get you training.</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6">
          {error && (
            <div className="mb-4 p-3 bg-rose-50 border-l-4 border-rose-500 text-rose-800 rounded-r-lg text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

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
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className={labelClass}>Password</label>
                <Link to="/forgot-password" className="text-[11px] font-semibold text-indigo-600 hover:text-indigo-800">
                  Forgot password?
                </Link>
              </div>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <LogIn className="w-4 h-4" />}
              <span>{loading ? 'Logging in...' : 'Log In'}</span>
            </Button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-500 mt-4">
          Don't have an account?{' '}
          <Link to="/register" className="font-semibold text-indigo-600 hover:text-indigo-800">Create one</Link>
        </p>
        <p className="text-center text-[11px] text-slate-400 mt-2">
          Participating in the S2 research study?{' '}
          <Link to="/research" className="font-semibold text-slate-600 hover:text-slate-800">Continue to the research prototype</Link>
        </p>
      </div>
    </div>
  );
}
