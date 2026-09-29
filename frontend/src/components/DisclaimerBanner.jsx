import React, { useState } from 'react';
import { AlertTriangle, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';

export default function DisclaimerBanner() {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-amber-50 border-l-4 border-amber-500 text-amber-900 px-4 py-3 rounded-r-lg shadow-xs mb-6 text-sm">
      <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 sm:justify-between">
        <div className="flex items-start sm:items-center gap-2 min-w-0">
          <AlertTriangle className="w-4.5 h-4.5 sm:w-5 sm:h-5 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
          <p className="leading-snug">
            <span className="font-semibold">Academic Research &amp; Health Safety Disclaimer:</span>{' '}
            <span className="text-amber-800 hidden sm:inline">
              This recommendation system is an educational prototype and does NOT provide medical advice.
            </span>
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="self-start sm:self-auto shrink-0 text-amber-700 hover:text-amber-900 flex items-center gap-1 text-xs font-medium cursor-pointer min-h-[32px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded"
          aria-expanded={expanded}
        >
          <span>{expanded ? 'Hide Details' : 'Read Full Safety Protocol'}</span>
          {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t border-amber-200 text-xs text-amber-800 space-y-1.5 animate-fadeIn">
          <p>
            • <strong>Educational Purpose:</strong> Built for an S2 Information Technology thesis at BINUS University ("Design and Evaluation of an AI-Based Personalized Running Training Recommendation System").
          </p>
          <p>
            • <strong>Stop Warning:</strong> Immediately stop exercising and consult a medical doctor if you experience dizziness, chest tightness, palpitations, joint pain, or shortness of breath.
          </p>
          <p>
            • <strong>No Medical Rehabilitation:</strong> This prototype is not intended for clinical rehabilitation of acute physical injuries or medical conditions.
          </p>
          <p>
            • <strong>Privacy & Anonymity:</strong> No personally identifiable information (such as real name or address) is stored. Evaluations use anonymous session identifiers.
          </p>
        </div>
      )}
    </div>
  );
}
