import React from 'react';
import { Loader2, AlertTriangle, Inbox } from 'lucide-react';
import Button from './Button';

// Consistent loading / empty / error placeholder used across pages instead of
// bare text or raw error strings. Purely presentational.
export function LoadingState({ label = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center text-slate-400">
      <Loader2 className="w-6 h-6 animate-spin mb-3 text-indigo-500" />
      <p className="text-xs font-medium">{label}</p>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, description, actionLabel, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 px-4 text-center">
      <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mb-4">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      {description && <p className="text-xs text-slate-500 mt-1 max-w-sm leading-relaxed">{description}</p>}
      {actionLabel && onAction && (
        <Button onClick={onAction} size="sm" className="mt-4">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

export function ErrorState({ message, actionLabel, onAction }) {
  const friendly = message && message.toLowerCase().includes('failed to fetch')
    ? 'Could not reach the recommendation server. Please check your connection and try again.'
    : (message || 'Something went wrong. Please try again.');

  return (
    <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-center">
      <div className="flex flex-col items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-rose-500" />
        <p className="text-xs text-rose-800 font-medium max-w-sm">{friendly}</p>
        {actionLabel && onAction && (
          <Button onClick={onAction} size="sm" variant="secondary" className="mt-2 border-rose-300 text-rose-700 hover:bg-rose-50">
            {actionLabel}
          </Button>
        )}
      </div>
    </div>
  );
}
