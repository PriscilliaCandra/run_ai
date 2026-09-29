import React from 'react';

// Consistent pill badge used across workout cards, plan-type labels, and
// research metadata. Purely presentational — no behavior change.
const VARIANTS = {
  neutral: 'bg-slate-100 text-slate-700 border-slate-200',
  slate: 'bg-slate-200 text-slate-700 border-slate-300',
  indigo: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  purple: 'bg-purple-100 text-purple-800 border-purple-300',
  emerald: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  amber: 'bg-amber-100 text-amber-800 border-amber-200',
  rose: 'bg-rose-100 text-rose-800 border-rose-300',
  blue: 'bg-blue-100 text-blue-800 border-blue-300',
};

export default function Badge({ children, variant = 'neutral', icon: Icon, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-semibold leading-none ${VARIANTS[variant] || VARIANTS.neutral} ${className}`}
    >
      {Icon && <Icon className="w-3 h-3 shrink-0" />}
      {children}
    </span>
  );
}
