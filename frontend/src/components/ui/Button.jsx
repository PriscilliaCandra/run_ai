import React from 'react';

// Shared button primitive so primary/secondary/ghost actions look and behave
// consistently across every page (same radius, shadow, focus ring, min touch
// target). Renders a plain <button> — no routing/behavior change.
const VARIANTS = {
  primary: 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs disabled:hover:bg-indigo-600',
  secondary: 'bg-white hover:bg-slate-50 text-slate-700 border border-slate-300 shadow-2xs disabled:hover:bg-white',
  ghost: 'bg-transparent hover:bg-slate-100 text-slate-600',
  success: 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs disabled:hover:bg-emerald-600',
  danger: 'bg-rose-600 hover:bg-rose-700 text-white shadow-xs disabled:hover:bg-rose-600',
};

const SIZES = {
  sm: 'px-3 py-1.5 text-xs min-h-[36px]',
  md: 'px-4 py-2.5 text-sm min-h-[44px]',
  lg: 'px-6 py-3 text-sm min-h-[48px]',
};

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  ...rest
}) {
  return (
    <button
      type={type}
      className={`inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 ${VARIANTS[variant] || VARIANTS.primary} ${SIZES[size] || SIZES.md} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
