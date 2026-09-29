import React from 'react';
import { ArrowLeft, BookOpen, Ruler } from 'lucide-react';
import DisclaimerBanner from '../components/DisclaimerBanner';
import Badge from '../components/ui/Badge';
import { EmptyState } from '../components/ui/StatusMessage';

export default function PlanDetailPage({ planData, onNavigate }) {
  if (!planData) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-10">
        <EmptyState
          icon={Ruler}
          title="No training plan to inspect yet"
          description="Generate a training plan first to see its individualized VDOT pace zones."
          actionLabel="Create Training Plan"
          onAction={() => onNavigate('create')}
        />
      </div>
    );
  }

  const { calculated_vdot, target_pace_per_km, rule_based_plan } = planData;
  const paces = rule_based_plan.paces;

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <DisclaimerBanner />

      <button
        onClick={() => onNavigate('result')}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-6 cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Weekly Training Plan</span>
      </button>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8 mb-8">
        <div className="flex items-center space-x-2 text-indigo-700 font-bold text-xs uppercase tracking-wider mb-2">
          <BookOpen className="w-4 h-4" />
          <span>Exercise Physiology Reference</span>
        </div>
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">Physiological Pace Zones & VDOT Modeling</h2>
        <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
          The mathematical and physiological framework powering the rule-based component of this research prototype.
        </p>

        {/* VDOT Formula Box */}
        <div className="mt-6 p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-2">
          <div className="font-bold text-slate-900">Jack Daniels VDOT Mathematical Formulation:</div>
          <div className="font-mono text-[11px] text-slate-700 bg-white p-2.5 rounded-lg border border-slate-200 overflow-x-auto">
            VO2 = -4.60 + 0.182258 * v + 0.000104 * v^2<br />
            %VO2max = 0.8 + 0.1894393 * e^(-0.012778 * t) + 0.2989558 * e^(-0.1932605 * t)<br />
            VDOT = VO2 / %VO2max
          </div>
          <p className="text-slate-600 text-[11px] leading-relaxed">
            Where <em>v</em> is race velocity in meters per minute and <em>t</em> is race duration in minutes. 
            For your baseline 5K, the computed VDOT index is <strong>{calculated_vdot.toFixed(1)}</strong>.
          </p>
        </div>

        {/* 5 Physiological Training Zones Table */}
        <div className="mt-8 space-y-4">
          <h3 className="text-sm font-bold text-slate-900">Calculated Individualized Pace Zones</h3>

          {/* Easy Run */}
          <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/40">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
              <span className="font-bold text-blue-950 text-sm">Zone 2: Easy / Recovery Pace (E)</span>
              <span className="font-black text-blue-700 text-sm">{paces.easy.pace_range}</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">{paces.easy.purpose}</p>
            <Badge variant="blue" className="mt-2">{paces.easy.intensity}</Badge>
          </div>

          {/* Marathon / Steady */}
          <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/40">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
              <span className="font-bold text-emerald-950 text-sm">Zone 3: Marathon / Steady Pace (M)</span>
              <span className="font-black text-emerald-700 text-sm">{paces.marathon.pace_range}</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">{paces.marathon.purpose}</p>
            <Badge variant="emerald" className="mt-2">{paces.marathon.intensity}</Badge>
          </div>

          {/* Threshold */}
          <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/40">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
              <span className="font-bold text-amber-950 text-sm">Zone 4: Lactate Threshold / Tempo (T)</span>
              <span className="font-black text-amber-700 text-sm">{paces.threshold.pace_range}</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">{paces.threshold.purpose}</p>
            <Badge variant="amber" className="mt-2">{paces.threshold.intensity}</Badge>
          </div>

          {/* Interval */}
          <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/40">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
              <span className="font-bold text-rose-950 text-sm">Zone 5: VO2max Interval Pace (I)</span>
              <span className="font-black text-rose-700 text-sm">{paces.interval.pace_range}</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">{paces.interval.purpose}</p>
            <Badge variant="rose" className="mt-2">{paces.interval.intensity}</Badge>
          </div>

          {/* Repetition */}
          <div className="p-4 rounded-xl border border-purple-200 bg-purple-50/40">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-2">
              <span className="font-bold text-purple-950 text-sm">Anaerobic: Repetition / Speed Pace (R)</span>
              <span className="font-black text-purple-700 text-sm">{paces.repetition.pace_range}</span>
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">{paces.repetition.purpose}</p>
            <Badge variant="purple" className="mt-2">{paces.repetition.intensity}</Badge>
          </div>
        </div>
      </div>
    </div>
  );
}
