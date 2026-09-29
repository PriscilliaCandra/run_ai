import React from 'react';
import { Activity, Flame, Shield, Moon, Clock, Compass, Info } from 'lucide-react';
import Badge from './ui/Badge';

export default function WorkoutCard({
  workout,
  isAiPlan = true,
  topBanner = null,
  footer = null,
  className = '',
}) {
  const isRest = workout.workout_type.toLowerCase().includes('rest') || workout.distance_km === 0;
  const isLong = workout.workout_type.toLowerCase().includes('long');
  const isQuality = workout.workout_type.toLowerCase().includes('interval') || workout.workout_type.toLowerCase().includes('tempo');

  const getBadgeVariant = () => {
    if (isRest) return 'neutral';
    if (isLong) return 'purple';
    if (isQuality) return 'rose';
    return 'blue'; // Easy run
  };

  const getHeaderIcon = () => {
    if (isRest) return <Moon className="w-5 h-5 text-slate-500" />;
    if (isLong) return <Compass className="w-5 h-5 text-purple-600" />;
    if (isQuality) return <Flame className="w-5 h-5 text-rose-600" />;
    return <Activity className="w-5 h-5 text-blue-600" />;
  };

  return (
    <div
      className={`rounded-xl border transition-all duration-200 bg-white shadow-xs hover:shadow-md flex flex-col justify-between h-full overflow-hidden ${
        isRest ? 'border-slate-200 bg-slate-50/20' : 'border-slate-200'
      } ${className}`}
    >
      <div>
        {/* Optional Top Banner (Status / Logging CTA) */}
        {topBanner}

        {/* Card Header */}
        <div className="p-4 border-b border-slate-100">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 shrink-0">
                {getHeaderIcon()}
              </div>
              <div className="min-w-0">
                <h3 className="font-bold text-slate-900 text-base leading-tight">{workout.day}</h3>
              </div>
            </div>

            <div className="text-right shrink-0">
              <div className="text-lg font-black text-slate-900 tracking-tight">
                {workout.distance_km > 0 ? `${workout.distance_km.toFixed(1)} km` : 'Rest Day'}
              </div>
            </div>
          </div>

          {/* Badge & Pace Row */}
          <div className="mt-2.5 pt-2 border-t border-slate-100/80 flex items-center justify-between gap-2 flex-wrap">
            <Badge variant={getBadgeVariant()}>{workout.workout_type}</Badge>
            {workout.pace_target && workout.pace_target !== 'N/A' && (
              <div className="text-xs font-semibold text-slate-600 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                <span>{workout.pace_target}</span>
              </div>
            )}
          </div>
        </div>

        {/* Card Body */}
        <div className="p-4 space-y-3 text-xs">
          {/* Intensity Zone */}
          <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100 flex items-start space-x-2">
            <Shield className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-slate-700">Target Intensity: </span>
              <span className="text-slate-600">{workout.intensity_zone}</span>
            </div>
          </div>

          {/* AI Warmup/Cooldown if available */}
          {workout.warmup_cooldown && (
            <div className="text-slate-700">
              <span className="font-semibold text-indigo-700">Warm-up & Cool-down: </span>
              <span className="text-slate-600">{workout.warmup_cooldown}</span>
            </div>
          )}

          {/* Workout Execution */}
          {workout.workout_execution && (
            <div className="text-slate-700 bg-amber-50/50 p-2.5 rounded-lg border border-amber-100/60">
              <span className="font-semibold text-amber-900">Workout Execution: </span>
              <span className="text-slate-800 leading-relaxed">{workout.workout_execution}</span>
            </div>
          )}

          {/* Purpose / Explainability */}
          <div className="text-slate-700">
            <span className="font-semibold text-slate-900 flex items-center space-x-1 mb-0.5">
              <Info className="w-3.5 h-3.5 text-blue-500 inline shrink-0" />
              <span>Workout Purpose:</span>
            </span>
            <p className="text-slate-600 italic leading-relaxed">{workout.purpose}</p>
          </div>

          {/* Recovery Instruction */}
          {workout.recovery_instruction && (
            <div className="pt-2 border-t border-slate-100 text-slate-600">
              <span className="font-medium text-slate-800">Recovery & Nutrition: </span>
              <span>{workout.recovery_instruction}</span>
            </div>
          )}
        </div>
      </div>

      {/* Optional Card Footer */}
      {footer && (
        <div className="mt-auto">
          {footer}
        </div>
      )}
    </div>
  );
}
