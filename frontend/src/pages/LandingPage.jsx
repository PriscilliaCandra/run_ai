import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Activity, BrainCircuit, Sparkles, FlaskConical } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Button from '../components/ui/Button';

export default function LandingPage() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12">
      <div className="text-center py-10 sm:py-14 px-4 sm:px-8 bg-linear-to-b from-indigo-50/70 via-white to-slate-50 rounded-2xl border border-indigo-100 shadow-xs mb-10">
        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight max-w-3xl mx-auto">
          Personalized Running Training, Built on Physiology You Can Trust
        </h1>
        <p className="mt-4 text-sm sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
          A running training plan personalized by AI, but never at the expense of the physiology that keeps you safe.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row flex-wrap justify-center gap-3">
          {isAuthenticated ? (
            <Link to="/dashboard">
              <Button size="lg" className="w-full sm:w-auto">
                <span>Go to Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </Button>
            </Link>
          ) : (
            <>
              <Link to="/register">
                <Button size="lg" className="w-full sm:w-auto">
                  <span>Create Free Account</span>
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link to="/login">
                <Button variant="secondary" size="lg" className="w-full sm:w-auto">
                  <span>Log In</span>
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-10">
        <div className="bg-white p-5 sm:p-6 rounded-xl border border-slate-200">
          <Activity className="w-6 h-6 text-indigo-600 mb-3" />
          <h3 className="font-bold text-slate-900 text-base mb-2">Physiologically Grounded</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Every pace and mileage target is calculated deterministically first -- the AI personalizes around it, never instead of it.
          </p>
        </div>
        <div className="bg-white p-5 sm:p-6 rounded-xl border border-slate-200">
          <BrainCircuit className="w-6 h-6 text-purple-600 mb-3" />
          <h3 className="font-bold text-slate-900 text-base mb-2">Constrained AI</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            The AI cannot change your distances, paces, or weekly mileage. It only personalizes the guidance around them.
          </p>
        </div>
        <div className="bg-white p-5 sm:p-6 rounded-xl border border-slate-200">
          <Sparkles className="w-6 h-6 text-emerald-600 mb-3" />
          <h3 className="font-bold text-slate-900 text-base mb-2">Explainable</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            See exactly why each workout was prescribed -- no black-box training advice.
          </p>
        </div>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-center sm:text-left">
        <div className="flex items-center gap-3 justify-center sm:justify-start">
          <div className="w-10 h-10 rounded-lg bg-slate-200 text-slate-600 flex items-center justify-center shrink-0">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-800">BINUS University S2 Research Study</p>
            <p className="text-xs text-slate-500">This platform also hosts an academic thesis evaluation. No account required to participate.</p>
          </div>
        </div>
        <Link to="/research" className="shrink-0">
          <Button variant="secondary" size="sm">Continue to Research Prototype</Button>
        </Link>
      </div>
    </div>
  );
}
