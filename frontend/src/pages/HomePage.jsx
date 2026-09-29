import React from 'react';
import { ArrowRight, ChevronRight, BrainCircuit, Activity, Award, FileSpreadsheet, Sparkles, UserCog, Calculator, Star } from 'lucide-react';
import DisclaimerBanner from '../components/DisclaimerBanner';
import Button from '../components/ui/Button';

const PIPELINE_STEPS = [
  {
    icon: UserCog,
    color: 'blue',
    title: 'Runner Profile',
    description: 'Age, experience, 5K/10K PBs, target race, available days, and injury notes.',
  },
  {
    icon: Calculator,
    color: 'emerald',
    title: 'Rule-Based Plan',
    description: 'Deterministic VDOT, pace zones, 80/20 volume split, and safe weekly progression.',
  },
  {
    icon: Sparkles,
    color: 'purple',
    title: 'AI Personalization',
    description: 'LLM enriches warm-ups, execution cues, and pacing — constrained to the rule-based numbers.',
  },
  {
    icon: Star,
    color: 'amber',
    title: 'Evaluation',
    description: '1–5 Likert ratings on Personalization, Usefulness, Clarity, and Confidence.',
  },
];

const STEP_COLORS = {
  blue: 'bg-blue-100 text-blue-700',
  emerald: 'bg-emerald-100 text-emerald-700',
  purple: 'bg-purple-100 text-purple-700',
  amber: 'bg-amber-100 text-amber-700',
};

export default function HomePage({ onNavigate }) {
  return (
    <div className="max-w-5xl mx-auto px-4 py-6 sm:py-8">
      <DisclaimerBanner />

      {/* Hero Header */}
      <div className="text-center py-8 sm:py-10 px-4 sm:px-8 bg-linear-to-b from-indigo-50/70 via-white to-slate-50 rounded-2xl border border-indigo-100 shadow-xs mb-8 sm:mb-10">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-100/70 text-indigo-800 text-[10px] sm:text-xs font-semibold uppercase tracking-wider mb-4">
          <Award className="w-3.5 h-3.5 shrink-0" />
          <span>BINUS University • S2 IT Research Prototype</span>
        </div>

        <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-900 tracking-tight leading-tight max-w-3xl mx-auto">
          Personalized Running Training Recommendation
        </h1>

        <p className="mt-4 text-sm sm:text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
          Built from a runner profile, deterministic rule-based training logic, and constrained AI personalization — so every plan stays explainable and physiologically bounded.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row flex-wrap justify-center gap-3">
          <Button onClick={() => onNavigate('create')} size="lg" className="w-full sm:w-auto">
            <span>Create Training Plan</span>
            <ArrowRight className="w-4 h-4" />
          </Button>

          <Button onClick={() => onNavigate('stats')} variant="secondary" size="lg" className="w-full sm:w-auto">
            <FileSpreadsheet className="w-4 h-4 text-slate-500" />
            <span>Research Evaluation Results</span>
          </Button>
        </div>
      </div>

      {/* Research Methodology Pipeline */}
      <div className="mb-10 sm:mb-12">
        <div className="text-center mb-6">
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900">How a Plan Is Generated</h2>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">Runner Profile → Rule-Based Plan → AI Personalization → Evaluation</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          {PIPELINE_STEPS.map((step, idx) => (
            <div key={step.title} className="relative bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center font-bold text-sm mb-3 ${STEP_COLORS[step.color]}`}>
                <step.icon className="w-4.5 h-4.5" />
              </div>
              <h3 className="font-bold text-slate-900 text-sm mb-1">
                <span className="text-slate-400 font-semibold mr-1">{idx + 1}.</span>
                {step.title}
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">{step.description}</p>

              {idx < PIPELINE_STEPS.length - 1 && (
                <ChevronRight className="hidden md:block absolute top-1/2 -right-2.5 -translate-y-1/2 w-5 h-5 text-slate-300 bg-slate-50 rounded-full p-0.5" />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Key Core Features */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
        <div className="bg-white p-5 sm:p-6 rounded-xl border border-slate-200">
          <Activity className="w-6 h-6 text-indigo-600 mb-3" />
          <h3 className="font-bold text-slate-900 text-base mb-2">Physiological Explainability</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Every prescribed workout and pace is mathematically traceable to the Jack Daniels running formula and the runner's baseline personal best.
          </p>
        </div>

        <div className="bg-white p-5 sm:p-6 rounded-xl border border-slate-200">
          <BrainCircuit className="w-6 h-6 text-purple-600 mb-3" />
          <h3 className="font-bold text-slate-900 text-base mb-2">Constrained AI Generation</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            The AI cannot change distances, paces, or mileage. It personalizes instructions strictly within the rule-based baseline's numbers.
          </p>
        </div>

        <div className="bg-white p-5 sm:p-6 rounded-xl border border-slate-200">
          <Sparkles className="w-6 h-6 text-emerald-600 mb-3" />
          <h3 className="font-bold text-slate-900 text-base mb-2">Baseline vs AI Comparison</h3>
          <p className="text-xs text-slate-600 leading-relaxed">
            Compare the deterministic Rule-Based Baseline against the AI-Personalized Plan side by side for the thesis evaluation.
          </p>
        </div>
      </div>
    </div>
  );
}
