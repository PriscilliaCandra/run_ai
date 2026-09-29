import React, { useState, useEffect } from 'react';
import { Star, ArrowLeft, CheckCircle2, AlertCircle, Loader2, Sparkles, Award, Sliders, ArrowRight } from 'lucide-react';
import DisclaimerBanner from '../components/DisclaimerBanner';
import Button from '../components/ui/Button';
import { submitPlanEvaluation } from '../api';

const LIKERT_CRITERIA = [
  {
    key: 'personalization_score',
    title: '1. Personalization',
    description: 'How well does this plan adapt to your specific age, 5K personal best, target race goal, and reported injury limitations?',
    labels: ['1 - Very Generic', '2 - Somewhat Generic', '3 - Moderate', '4 - Well Personalized', '5 - Highly Personalized']
  },
  {
    key: 'usefulness_score',
    title: '2. Perceived Usefulness',
    description: 'How practical and helpful is this weekly schedule for guiding your real-world running routine?',
    labels: ['1 - Not Useful', '2 - Slightly Useful', '3 - Moderately Useful', '4 - Very Useful', '5 - Extremely Useful']
  },
  {
    key: 'clarity_score',
    title: '3. Clarity of Workouts & Paces',
    description: 'Are the pace targets, warm-up protocols, execution details, and recovery advice easy to comprehend?',
    labels: ['1 - Very Confusing', '2 - Somewhat Unclear', '3 - Acceptable', '4 - Clear & Direct', '5 - Crystal Clear']
  },
  {
    key: 'confidence_score',
    title: '4. Confidence in Following the Plan',
    description: 'How confident do you feel that you could safely adhere to this plan without suffering overtraining or burnout?',
    labels: ['1 - No Confidence', '2 - Low Confidence', '3 - Neutral', '4 - Confident', '5 - Highly Confident']
  }
];

export default function EvaluationPage({ planId, planType = 'ai_personalized', onNavigate, onSelectPlanType }) {
  const [selectedPlanType, setSelectedPlanType] = useState(planType);
  const [scores, setScores] = useState({
    personalization_score: 5,
    usefulness_score: 5,
    clarity_score: 5,
    confidence_score: 4,
  });
  const [comments, setComments] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setSelectedPlanType(planType);
  }, [planType]);

  const handleScoreChange = (key, value) => {
    setScores({ ...scores, [key]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!planId) {
      setError('No active training plan selected to evaluate. Please generate or select a plan first.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await submitPlanEvaluation({
        training_plan_id: planId,
        evaluated_plan_type: selectedPlanType,
        personalization_score: scores.personalization_score,
        usefulness_score: scores.usefulness_score,
        clarity_score: scores.clarity_score,
        confidence_score: scores.confidence_score,
        comments: comments.trim() ? comments.trim() : null
      });
      setSuccess(true);
    } catch (err) {
      setError(err.message || 'Error submitting research evaluation.');
    } finally {
      setLoading(false);
    }
  };

  const otherPlanType = selectedPlanType === 'ai_personalized' ? 'rule_based' : 'ai_personalized';
  const otherPlanTitle = selectedPlanType === 'ai_personalized' ? 'Rule-Based Baseline Plan' : 'AI-Personalized Plan';

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <DisclaimerBanner />

      <button
        onClick={() => onNavigate('result')}
        className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 mb-6 cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Generated Plan</span>
      </button>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8">
        <div className="pb-6 border-b border-slate-100">
          <div className="inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 text-xs font-semibold mb-2">
            <Award className="w-3.5 h-3.5" />
            <span>Comparative Research Instrument</span>
          </div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Evaluate Training Plan</h2>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            Plan ID: <span className="font-mono text-slate-700">{planId ? `${planId.slice(0, 8)}...` : 'None'}</span> • 
            Evaluations are disaggregated to compare the mathematical baseline against the AI-personalized plan.
          </p>

          {/* Explicit Plan Type Selector */}
          {!success && (
            <div className="mt-4 p-3 bg-slate-50 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <span className="text-xs font-bold text-slate-800">You are evaluating:</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedPlanType('rule_based');
                    if (onSelectPlanType) onSelectPlanType('rule_based');
                  }}
                  aria-pressed={selectedPlanType === 'rule_based'}
                  className={`flex-1 sm:flex-none min-h-[40px] px-3 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                    selectedPlanType === 'rule_based'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  <Sliders className="w-3.5 h-3.5" />
                  <span>Rule-Based Baseline</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setSelectedPlanType('ai_personalized');
                    if (onSelectPlanType) onSelectPlanType('ai_personalized');
                  }}
                  aria-pressed={selectedPlanType === 'ai_personalized'}
                  className={`flex-1 sm:flex-none min-h-[40px] px-3 py-2 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                    selectedPlanType === 'ai_personalized'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>AI-Personalized Plan</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {success ? (
          <div className="py-12 text-center space-y-4">
            <div className="w-12 h-12 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-7 h-7" />
            </div>
            <h3 className="text-xl font-bold text-slate-900">
              Evaluation Recorded for {selectedPlanType === 'ai_personalized' ? 'AI-Personalized Plan' : 'Rule-Based Baseline'}!
            </h3>
            <p className="text-xs text-slate-600 max-w-md mx-auto leading-relaxed">
              Your ratings have been stored in the research database under the <code>{selectedPlanType}</code> category.
            </p>
            <div className="pt-4 flex flex-col sm:flex-row flex-wrap justify-center gap-3">
              <Button
                onClick={() => {
                  setSelectedPlanType(otherPlanType);
                  if (onSelectPlanType) onSelectPlanType(otherPlanType);
                  setSuccess(false);
                  setScores({
                    personalization_score: otherPlanType === 'rule_based' ? 3 : 5,
                    usefulness_score: 4,
                    clarity_score: 5,
                    confidence_score: 4,
                  });
                  setComments('');
                }}
              >
                <span>Now Rate {otherPlanTitle}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>

              <Button onClick={() => onNavigate('stats')} variant="secondary">
                View Comparative Survey Analytics
              </Button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-6 space-y-6">
            {error && (
              <div className="p-3.5 bg-rose-50 border-l-4 border-rose-500 text-rose-800 rounded-r-lg text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {LIKERT_CRITERIA.map((criterion, idx) => {
              const currentScore = scores[criterion.key];
              return (
                <div key={criterion.key} className="p-4 rounded-xl bg-slate-50 border border-slate-200/70">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 mb-1">
                    <h3 className="text-sm font-bold text-slate-900">
                      <span className="text-slate-400 font-semibold mr-1">{idx + 1}/{LIKERT_CRITERIA.length}</span>
                      {criterion.title}
                    </h3>
                    <span className="text-xs font-semibold text-indigo-700">
                      Score: {currentScore} / 5 ({criterion.labels[currentScore - 1]})
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mb-3">{criterion.description}</p>

                  {/* 1-5 Button selector: horizontal row on desktop, still touch-friendly on mobile */}
                  <div className="grid grid-cols-5 gap-1.5 sm:gap-2">
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => handleScoreChange(criterion.key, val)}
                        aria-label={`${criterion.title}: ${criterion.labels[val - 1]}`}
                        aria-pressed={currentScore === val}
                        className={`min-h-[56px] py-2 text-xs font-bold rounded-lg border transition-all cursor-pointer flex flex-col items-center justify-center gap-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                          currentScore === val
                            ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                            : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                        }`}
                      >
                        <Star className={`w-3.5 h-3.5 ${currentScore >= val ? 'fill-current' : 'text-slate-300'}`} />
                        <span>{val}</span>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}

            {/* Optional Qualitative Feedback */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-700">
                Qualitative Feedback for {selectedPlanType === 'ai_personalized' ? 'AI-Personalized Plan' : 'Rule-Based Baseline Plan'} <span className="text-slate-400 font-normal">(Optional)</span>
              </label>
              <textarea
                rows={3}
                placeholder="What did you like about this specific plan? Were any paces or workouts challenging? Any suggestions for improvement?"
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                className="w-full px-3 py-2.5 border border-slate-300 rounded-lg text-xs focus:outline-hidden focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white"
              />
            </div>

            {/* Submit Action */}
            <div className="pt-4 border-t border-slate-100 flex justify-end">
              <Button type="submit" disabled={loading} variant="success" className="w-full sm:w-auto">
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Submitting Evaluation...</span>
                  </>
                ) : (
                  <>
                    <span>Submit Score for {selectedPlanType === 'ai_personalized' ? 'AI Plan' : 'Baseline'}</span>
                    <CheckCircle2 className="w-4 h-4" />
                  </>
                )}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
