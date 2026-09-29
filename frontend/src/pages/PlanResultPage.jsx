import React, { useState } from 'react';
import {
  Award, Activity, Calendar, HelpCircle, ArrowLeft, Star, FileText, Sparkles, Sliders,
  User, CalendarDays, Target, Inbox
} from 'lucide-react';
import DisclaimerBanner from '../components/DisclaimerBanner';
import WorkoutCard from '../components/WorkoutCard';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import { EmptyState } from '../components/ui/StatusMessage';

export default function PlanResultPage({ planData, onNavigate, onSelectPlanForEvaluation }) {
  const [activeTab, setActiveTab] = useState('ai'); // 'ai' or 'rule'
  const [showProgression, setShowProgression] = useState(false);

  if (!planData) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-10">
        <EmptyState
          icon={Inbox}
          title="No generated plan found in this session"
          description="Create a runner profile first to generate a Rule-Based Baseline and AI-Personalized training plan."
          actionLabel="Create Training Plan"
          onAction={() => onNavigate('create')}
        />
      </div>
    );
  }

  const {
    plan_id,
    calculated_vdot,
    target_pace_per_km,
    rule_based_plan,
    ai_personalized_plan,
    explainability,
    ai_model_used
  } = planData;

  const currentWorkouts = activeTab === 'ai' 
    ? (ai_personalized_plan.workouts || rule_based_plan.week_1_plan.workouts)
    : rule_based_plan.week_1_plan.workouts;

  const weeklyVolume = activeTab === 'ai'
    ? (ai_personalized_plan.weekly_mileage_km || rule_based_plan.week_1_plan.weekly_mileage_km)
    : rule_based_plan.week_1_plan.weekly_mileage_km;

  const phys = explainability.physiological_engine_values || {};
  const constraints = explainability.applied_prototype_constraints || {};
  const inputs = explainability.runner_inputs_utilized || {};
  const aiSummary = ai_personalized_plan.ai_personalization_summary || explainability.ai_personalization_summary || [];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <DisclaimerBanner />

      {/* Top Banner Navigation & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <button
          onClick={() => onNavigate('create')}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 cursor-pointer min-h-[36px]"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Edit Profile Parameters</span>
        </button>

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => onNavigate('details')} variant="secondary" size="sm">
            <FileText className="w-3.5 h-3.5 text-slate-500" />
            <span>Pace Zones</span>
          </Button>

          <Button
            onClick={() => {
              onSelectPlanForEvaluation(plan_id, 'rule_based');
              onNavigate('evaluate');
            }}
            variant="secondary"
            size="sm"
          >
            <Sliders className="w-3.5 h-3.5 text-slate-500" />
            <span>Evaluate Baseline</span>
          </Button>

          <Button
            onClick={() => {
              onSelectPlanForEvaluation(plan_id, 'ai_personalized');
              onNavigate('evaluate');
            }}
            size="sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Evaluate AI Plan</span>
          </Button>
        </div>
      </div>

      {/* Plan Summary Strip: runner profile snapshot at a glance */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        <Badge variant="neutral" icon={User}>
          {inputs.age || '—'} y/o • {inputs.experience_level || 'Runner'}
        </Badge>
        <Badge variant="neutral" icon={CalendarDays}>
          {inputs.training_frequency || `${rule_based_plan.week_1_plan.workouts.filter(w => w.workout_type !== 'Rest & Recovery').length} days/week`}
        </Badge>
        <Badge variant="neutral" icon={Target}>
          {inputs.target_race || 'Target race'}
        </Badge>
        <Badge variant={activeTab === 'ai' ? 'indigo' : 'slate'} icon={activeTab === 'ai' ? Sparkles : Sliders}>
          Viewing: {activeTab === 'ai' ? 'AI-Personalized Plan' : 'Rule-Based Baseline'}
        </Badge>
      </div>

      {/* Metrics Dashboard Overview */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-5 sm:p-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between pb-6 border-b border-slate-100 gap-4">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 text-xs font-semibold mb-2">
              <Award className="w-3 h-3" />
              <span>AI Component: {ai_model_used}</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">Personalized Training Plan</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Plan ID: <span className="font-mono text-slate-700">{plan_id.slice(0, 8)}...</span> • Week 1 Microcycle
            </p>
          </div>

          {/* S2 Academic Comparison Toggle (neutral labels, no "winner" framing) */}
          <div className="bg-slate-100 p-1 rounded-xl flex items-center gap-1 self-start md:self-auto border border-slate-200 w-full md:w-auto">
            <button
              onClick={() => setActiveTab('ai')}
              className={`flex-1 md:flex-none px-3 py-2 md:py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1 min-h-[40px] md:min-h-0 ${
                activeTab === 'ai'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>AI-Personalized</span>
            </button>
            <button
              onClick={() => setActiveTab('rule')}
              className={`flex-1 md:flex-none px-3 py-2 md:py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1 min-h-[40px] md:min-h-0 ${
                activeTab === 'rule'
                  ? 'bg-white text-indigo-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>Rule-Based</span>
            </button>
          </div>
        </div>

        {/* 4 Metric Badges */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-6">
          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Calculated VDOT</span>
            <div className="flex items-baseline space-x-1.5 mt-1">
              <span className="text-2xl font-black text-slate-900">{calculated_vdot.toFixed(1)}</span>
              <span className="text-[11px] text-emerald-600 font-medium">Jack Daniels Index</span>
            </div>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Target Race Pace</span>
            <div className="flex items-baseline space-x-1.5 mt-1">
              <span className="text-2xl font-black text-indigo-600">{target_pace_per_km}</span>
              <span className="text-[11px] text-slate-500 font-medium">/km</span>
            </div>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Weekly Volume</span>
            <div className="flex items-baseline space-x-1.5 mt-1">
              <span className="text-2xl font-black text-slate-900">{weeklyVolume.toFixed(1)}</span>
              <span className="text-[11px] text-slate-500 font-medium">km / week</span>
            </div>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-100">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Feasibility Rating</span>
            <div className="mt-1">
              <span className="text-sm font-bold text-emerald-700 block truncate">
                {phys.feasibility_status || 'Realistic'}
              </span>
              <span className="text-[10px] text-slate-500">Pace Delta: {phys.pace_delta_percentage || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Coach Overview Message if in AI tab */}
        {activeTab === 'ai' && ai_personalized_plan.coach_overview && (
          <div className="mt-6 p-4 rounded-xl bg-linear-to-r from-indigo-50/80 to-purple-50/80 border border-indigo-100 text-xs text-slate-700 leading-relaxed">
            <div className="flex items-center space-x-1.5 text-indigo-900 font-bold mb-1">
              <Activity className="w-4 h-4 text-indigo-600" />
              <span>AI Running Coach Assessment:</span>
            </div>
            <p>{ai_personalized_plan.coach_overview}</p>
          </div>
        )}
      </div>

      {/* Weekly Schedule Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            {activeTab === 'ai' ? 'AI-Personalized Microcycle (Week 1)' : 'Rule-Based Baseline Microcycle (Week 1)'}
          </h3>
          <p className="text-xs text-slate-500">
            {activeTab === 'ai' 
              ? 'Enriched with personalized warm-up/cool-down protocols, mental pacing cues, and non-medical limitation adaptations.' 
              : 'Deterministic physiological allocation according to Jack Daniels VDOT and weekly volume constraints.'}
          </p>
        </div>

        <button
          onClick={() => setShowProgression(!showProgression)}
          className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center space-x-1 cursor-pointer"
        >
          <Calendar className="w-3.5 h-3.5" />
          <span>{showProgression ? 'Hide Multi-Week Roadmap' : 'Show Multi-Week Roadmap'}</span>
        </button>
      </div>

      {/* Multi-Week Progression Table (Collapsible) */}
      {showProgression && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 shadow-xs overflow-x-auto animate-fadeIn">
          <h4 className="font-bold text-slate-900 text-sm mb-1">Periodized Progression Schedule (≤10% Volume Constraint)</h4>
          <p className="text-xs text-slate-500 mb-4">
            Structured periodization incorporating progressive volume build, deload cutback weeks, and race taper.
          </p>
          <table className="w-full min-w-[640px] text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase">
                <th className="py-2 px-3">Week</th>
                <th className="py-2 px-3">Target Volume</th>
                <th className="py-2 px-3">Training Phase</th>
                <th className="py-2 px-3">Physiological Focus</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {rule_based_plan.progression_schedule.map((p) => (
                <tr key={p.week_number} className="hover:bg-slate-50">
                  <td className="py-2.5 px-3 font-bold text-slate-900 whitespace-nowrap">Week {p.week_number}</td>
                  <td className="py-2.5 px-3 font-semibold text-indigo-700 whitespace-nowrap">{p.target_mileage_km} km</td>
                  <td className="py-2.5 px-3 whitespace-nowrap">
                    <Badge variant="neutral">{p.phase}</Badge>
                  </td>
                  <td className="py-2.5 px-3 text-slate-600">{p.focus_note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Weekly Grid of Workouts */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-10 items-stretch">
        {currentWorkouts.map((workout, idx) => (
          <div key={idx} className="h-full flex flex-col">
            <WorkoutCard 
              workout={workout} 
              isAiPlan={activeTab === 'ai'} 
            />
          </div>
        ))}
      </div>

      {/* 4-Part Explainability & Traceability Matrix */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs mb-8">
        <div className="flex items-center space-x-2 mb-4">
          <HelpCircle className="w-5 h-5 text-indigo-600" />
          <h3 className="font-bold text-slate-900 text-lg">System Explainability & Traceability Matrix</h3>
        </div>

        <p className="text-xs text-slate-600 mb-6 leading-relaxed">
          For academic defensibility, the decision pathway distinguishes between <strong>input parameters</strong>, 
          <strong> physiological calculations</strong>, <strong>prototype heuristic constraints</strong>, and <strong>LLM personalization elements</strong>:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          {/* Part 1: Runner Inputs */}
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
            <span className="font-bold text-slate-900 text-sm block mb-2 flex items-center space-x-1.5">
              <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-700 inline-flex items-center justify-center text-[11px]">1</span>
              <span>Runner Inputs Utilized</span>
            </span>
            <ul className="space-y-1 text-slate-600">
              <li>• <strong>Runner:</strong> {inputs.age || '21'} y/o, {inputs.gender || 'Male'}, {inputs.experience_level || 'Intermediate'}</li>
              <li>• <strong>5K PB:</strong> {inputs.pb_5k || '24:56'} (Pace: {phys.pb_5k_pace || '04:59 /km'})</li>
              <li>• <strong>Target Goal:</strong> {inputs.target_race || '5K in 23:00'}</li>
              <li>• <strong>Weekly Capacity:</strong> {inputs.current_weekly_mileage || '25 km/week'} across {inputs.training_frequency || '4 days/week'}</li>
              <li>• <strong>Limitation:</strong> {inputs.injury_limitations || 'None reported'}</li>
            </ul>
          </div>

          {/* Part 2: Physiological Engine Values */}
          <div className="p-4 rounded-xl bg-indigo-50/50 border border-indigo-100">
            <span className="font-bold text-indigo-950 text-sm block mb-2 flex items-center space-x-1.5">
              <span className="w-5 h-5 rounded-full bg-indigo-200 text-indigo-800 inline-flex items-center justify-center text-[11px]">2</span>
              <span>Physiological Engine Values</span>
            </span>
            <ul className="space-y-1 text-slate-700">
              <li>• <strong>Jack Daniels VDOT:</strong> {phys.calculated_vdot || calculated_vdot.toFixed(1)}</li>
              <li>• <strong>Required Race Pace:</strong> {phys.target_race_pace || target_pace_per_km}</li>
              <li>• <strong>Pace Delta:</strong> {phys.pace_delta_percentage || 'N/A'} ({phys.feasibility_status || 'Realistic'})</li>
              <li>• <strong>Easy Aerobic Zone:</strong> {phys.training_pace_zones?.easy_zone || 'Zone 2'}</li>
              <li>• <strong>Threshold Zone:</strong> {phys.training_pace_zones?.threshold_zone || 'Zone 4'}</li>
            </ul>
          </div>

          {/* Part 3: Predefined Prototype Constraints */}
          <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200/70">
            <span className="font-bold text-amber-950 text-sm block mb-2 flex items-center space-x-1.5">
              <span className="w-5 h-5 rounded-full bg-amber-200 text-amber-800 inline-flex items-center justify-center text-[11px]">3</span>
              <span>Predefined Prototype Constraints</span>
            </span>
            <ul className="space-y-1 text-slate-700">
              <li>• <strong>Polarized Heuristic:</strong> ~80% aerobic volume / ~20% quality volume split design rule.</li>
              <li>• <strong>Baseline Volume Cap:</strong> Initial microcycle volume equals baseline ({inputs.current_weekly_mileage || '25 km'}).</li>
              <li>• <strong>Long Run Boundary:</strong> Long run capped at ≤30% of total weekly volume.</li>
              <li>• <strong>Progression Constraint:</strong> Weekly increases bounded by ≤8–10% rule with deloads.</li>
            </ul>
          </div>

          {/* Part 4: AI Personalization Summary */}
          <div className="p-4 rounded-xl bg-purple-50/50 border border-purple-200/70">
            <span className="font-bold text-purple-950 text-sm block mb-2 flex items-center space-x-1.5">
              <span className="w-5 h-5 rounded-full bg-purple-200 text-purple-800 inline-flex items-center justify-center text-[11px]">4</span>
              <span>AI Personalization Summary</span>
            </span>
            <ul className="space-y-1 text-slate-700">
              {aiSummary.map((item, i) => (
                <li key={i}>• {item}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Comparative Evaluation CTA */}
      <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-6 text-center shadow-xs">
        <h3 className="text-lg font-bold text-emerald-950">Comparative Thesis Evaluation</h3>
        <p className="text-xs text-emerald-800 max-w-xl mx-auto mt-1 mb-4 leading-relaxed">
          To provide rigorous empirical data for the S2 research paper, please evaluate both plans independently. 
          Rate the <strong>Rule-Based Baseline</strong> and the <strong>AI-Personalized Plan</strong> on Personalization, Usefulness, Clarity, and Confidence.
        </p>
        <div className="flex flex-col sm:flex-row flex-wrap justify-center gap-3">
          <Button
            onClick={() => {
              onSelectPlanForEvaluation(plan_id, 'rule_based');
              onNavigate('evaluate');
            }}
            variant="secondary"
          >
            <Sliders className="w-3.5 h-3.5 text-slate-600" />
            <span>Evaluate Rule-Based Baseline</span>
          </Button>

          <Button
            onClick={() => {
              onSelectPlanForEvaluation(plan_id, 'ai_personalized');
              onNavigate('evaluate');
            }}
            variant="success"
          >
            <Sparkles className="w-3.5 h-3.5 fill-current" />
            <span>Evaluate AI-Personalized Plan</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
