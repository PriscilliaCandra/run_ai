import React, { useEffect, useState } from 'react';
import { FileSpreadsheet, Download, RefreshCw, Star, MessageSquare, ArrowLeft, BarChart2, Sliders, Sparkles, ClipboardList } from 'lucide-react';
import DisclaimerBanner from '../components/DisclaimerBanner';
import Button from '../components/ui/Button';
import { LoadingState, EmptyState, ErrorState } from '../components/ui/StatusMessage';
import { fetchEvaluationStats } from '../api';

const STAT_GROUP_STYLES = {
  rule_based: {
    border: 'border-slate-200',
    bg: 'bg-slate-50',
    title: 'text-slate-800',
    badge: 'bg-slate-200 text-slate-700',
    bar: 'bg-slate-500',
    metricCard: 'bg-white border-slate-200',
  },
  ai_personalized: {
    border: 'border-indigo-200',
    bg: 'bg-indigo-50/60',
    title: 'text-indigo-800',
    badge: 'bg-indigo-200 text-indigo-800',
    bar: 'bg-indigo-500',
    metricCard: 'bg-white border-indigo-100',
  },
};

function formatStat(value) {
  return value === null || value === undefined ? '—' : value.toFixed(2);
}

function StatGroupCard({ title, icon, styleKey, data }) {
  const style = STAT_GROUP_STYLES[styleKey];
  const hasData = data && data.count > 0;
  const dimensions = hasData
    ? [
        { label: 'Personalization', stats: data.personalization },
        { label: 'Usefulness', stats: data.usefulness },
        { label: 'Clarity', stats: data.clarity },
        { label: 'Confidence', stats: data.confidence },
      ]
    : [];

  return (
    <div className={`rounded-2xl border p-5 ${style.border} ${style.bg}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          {icon}
          <h3 className={`font-bold text-sm ${style.title}`}>{title}</h3>
        </div>
        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${style.badge}`}>
          N = {data ? data.count : 0}
        </span>
      </div>

      {!hasData ? (
        <p className="text-xs text-slate-400 italic py-8 text-center">
          No evaluations submitted yet for this plan type.
        </p>
      ) : (
        <>
          {/* Horizontal scroll is scoped to this table container only, never the page */}
          <div className="overflow-x-auto -mx-1 mb-4">
            <table className="w-full min-w-[300px] text-xs border-collapse px-1">
              <thead>
                <tr className="text-[10px] uppercase text-slate-500 border-b border-slate-300/60">
                  <th className="text-left font-semibold py-1.5">Dimension</th>
                  <th className="text-right font-semibold py-1.5">Mean</th>
                  <th className="text-right font-semibold py-1.5">Median</th>
                  <th className="text-right font-semibold py-1.5">SD</th>
                </tr>
              </thead>
              <tbody>
                {dimensions.map((d) => (
                  <tr key={d.label} className="border-b border-slate-200/60 last:border-0">
                    <td className="py-2 text-slate-700 font-medium whitespace-nowrap">{d.label}</td>
                    <td className="py-2 text-right font-bold text-slate-900">{formatStat(d.stats.mean)}</td>
                    <td className="py-2 text-right text-slate-700">{formatStat(d.stats.median)}</td>
                    <td className="py-2 text-right text-slate-500">
                      {d.stats.std_dev === null ? (
                        <span title="Not available for a single observation (N=1)">N/A</span>
                      ) : (
                        formatStat(d.stats.std_dev)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-[11px] font-bold text-slate-700">Overall Mean (all 4 dimensions)</span>
              <span className={`text-sm font-black ${style.title}`}>{formatStat(data.overall_mean)} / 5.00</span>
            </div>
            <div className="w-full h-2.5 bg-white/70 rounded-full overflow-hidden border border-white">
              <div
                className={`h-full rounded-full transition-all duration-500 ${style.bar}`}
                style={{ width: `${((data.overall_mean || 0) / 5.0) * 100}%` }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function EvaluationStatsPage({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchEvaluationStats();
      setStats(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch evaluation analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, []);

  const handleExportJSON = () => {
    if (!stats) return;
    const blob = new Blob([JSON.stringify(stats, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `research_evaluation_dataset_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <DisclaimerBanner />

      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <button
          onClick={() => onNavigate('home')}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-slate-900 cursor-pointer min-h-[36px]"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </button>

        <div className="flex items-center gap-2">
          <Button onClick={loadStats} variant="secondary" size="sm" title="Refresh statistics">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </Button>

          <Button onClick={handleExportJSON} disabled={!stats || stats.total_evaluations === 0} size="sm">
            <Download className="w-3.5 h-3.5" />
            <span>Export Research JSON</span>
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 shadow-xs p-6 sm:p-8 mb-8">
        <div className="flex items-center space-x-2 text-indigo-700 font-bold text-xs uppercase tracking-wider mb-2">
          <BarChart2 className="w-4 h-4" />
          <span>Thesis Empirical Evaluation Results</span>
        </div>
        <h2 className="text-2xl font-black text-slate-900 tracking-tight">System Evaluation Dashboard</h2>
        <p className="text-xs text-slate-500 mt-1 max-w-2xl leading-relaxed">
          Aggregated quantitative Likert ratings (1-5 scale) evaluating the AI-based personalized running training recommendation system.
        </p>

        {loading ? (
          <LoadingState label="Loading evaluation metrics..." />
        ) : error ? (
          <ErrorState message={error} actionLabel="Try Again" onAction={loadStats} />
        ) : stats.total_evaluations === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="No evaluations submitted yet"
            description="Generate a training plan and submit your first Rule-Based Baseline or AI-Personalized evaluation to see statistics here."
            actionLabel="Generate a Plan Now"
            onAction={() => onNavigate('create')}
          />
        ) : (
          <div className="mt-6 space-y-8">
            {/* Comparative Statistics: Rule-Based Baseline vs AI-Personalized (kept disaggregated, never combined) */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-800">Comparative Results by Plan Type</h3>
                <span className="text-[11px] text-slate-400">
                  {stats.total_evaluations} total evaluation{stats.total_evaluations === 1 ? '' : 's'} collected
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <StatGroupCard
                  title="Rule-Based Baseline"
                  icon={<Sliders className="w-4 h-4 text-slate-600" />}
                  styleKey="rule_based"
                  data={stats.rule_based_stats}
                />
                <StatGroupCard
                  title="AI-Personalized Plan"
                  icon={<Sparkles className="w-4 h-4 text-indigo-600" />}
                  styleKey="ai_personalized"
                  data={stats.ai_personalized_stats}
                />
              </div>
              <p className="text-[11px] text-slate-400 mt-2 leading-relaxed">
                Scores are reported separately per plan type, as recorded by <code>evaluated_plan_type</code>. This dashboard does not combine them into a single score, and observed differences here are descriptive only — not a claim of statistical superiority.
              </p>
            </div>

            {/* Qualitative Feedback List */}
            <div>
              <div className="flex items-center space-x-2 text-slate-800 font-bold text-sm mb-3">
                <MessageSquare className="w-4 h-4 text-indigo-600" />
                <span>Recent Qualitative User Comments ({stats.recent_comments.length})</span>
              </div>

              {stats.recent_comments.length === 0 ? (
                <p className="text-xs text-slate-400 italic">No written comments provided yet.</p>
              ) : (
                <div className="space-y-3">
                  {stats.recent_comments.map((c) => (
                    <div key={c.id} className="p-3.5 rounded-xl border border-slate-200 bg-white text-xs space-y-1.5 shadow-2xs">
                      <div className="flex items-center justify-between text-slate-400 text-[11px]">
                        <span className="flex items-center gap-2">
                          <span>Plan ID: {c.training_plan_id.slice(0, 8)}...</span>
                          <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                            c.evaluated_plan_type === 'ai_personalized'
                              ? 'bg-indigo-100 text-indigo-700'
                              : 'bg-slate-200 text-slate-700'
                          }`}>
                            {c.evaluated_plan_type === 'ai_personalized' ? 'AI-Personalized' : 'Rule-Based'}
                          </span>
                        </span>
                        <span>{new Date(c.created_at).toLocaleDateString()}</span>
                      </div>
                      <p className="text-slate-800 italic">"{c.comments}"</p>
                      <div className="flex flex-wrap gap-2 text-[10px] pt-1">
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600">Pers: {c.scores.personalization}/5</span>
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600">Use: {c.scores.usefulness}/5</span>
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600">Clar: {c.scores.clarity}/5</span>
                        <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600">Conf: {c.scores.confidence}/5</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
