import React, { useState } from 'react';
import { Activity, PlusCircle, Calendar, Star, BarChart2, Home as HomeIcon, Menu, X } from 'lucide-react';
import HomePage from './pages/HomePage';
import CreatePlanPage from './pages/CreatePlanPage';
import PlanResultPage from './pages/PlanResultPage';
import PlanDetailPage from './pages/PlanDetailPage';
import EvaluationPage from './pages/EvaluationPage';
import EvaluationStatsPage from './pages/EvaluationStatsPage';

export default function App() {
  const [currentPage, setCurrentPage] = useState('home');
  const [currentPlan, setCurrentPlan] = useState(null);
  const [evaluatingPlanId, setEvaluatingPlanId] = useState(null);
  const [evaluatingPlanType, setEvaluatingPlanType] = useState('ai_personalized');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handlePlanGenerated = (planData) => {
    setCurrentPlan(planData);
    setEvaluatingPlanId(planData.plan_id);
    setEvaluatingPlanType('ai_personalized');
    setCurrentPage('result');
  };

  const handleSelectPlanForEvaluation = (planId, planType = 'ai_personalized') => {
    setEvaluatingPlanId(planId);
    setEvaluatingPlanType(planType);
    setCurrentPage('evaluate');
  };

  const goTo = (page) => {
    setCurrentPage(page);
    setMobileMenuOpen(false);
  };

  const NAV_ITEMS = [
    { key: 'home', label: 'Home', icon: HomeIcon, iconClass: '', visible: true },
    { key: 'create', label: 'New Plan', icon: PlusCircle, iconClass: 'text-indigo-600', visible: true },
    { key: 'result', label: 'Current Plan', icon: Calendar, iconClass: '', visible: !!currentPlan },
    { key: 'evaluate', label: 'Research Evaluation', icon: Star, iconClass: 'text-amber-500 fill-amber-500', visible: true },
    { key: 'stats', label: 'Survey Stats', icon: BarChart2, iconClass: 'text-slate-500', visible: true },
  ];

  const navButtonClass = (key) =>
    `px-3 py-1.5 rounded-lg transition-colors cursor-pointer flex items-center space-x-1.5 whitespace-nowrap ${
      currentPage === key
        ? key === 'evaluate'
          ? 'bg-emerald-50 text-emerald-700 font-bold'
          : 'bg-indigo-50 text-indigo-700 font-bold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
    }`;

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      {/* Navigation Header */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-xs border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
          {/* Logo / Branding */}
          <div
            onClick={() => goTo('home')}
            className="flex items-center space-x-2.5 cursor-pointer select-none min-w-0"
          >
            <div className="w-9 h-9 shrink-0 rounded-xl bg-linear-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-xs">
              <Activity className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="font-black text-slate-900 text-sm sm:text-base tracking-tight leading-tight flex items-center space-x-1.5">
                <span className="truncate">RunAI Recommendation</span>
                <span className="hidden md:inline-block shrink-0 text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700">S2 PROTOTYPE</span>
              </div>
              <div className="hidden sm:block text-[10px] text-slate-400 font-medium truncate">BINUS University • S2 Information Technology</div>
            </div>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden sm:flex items-center space-x-1 text-xs font-semibold shrink-0">
            {NAV_ITEMS.filter((item) => item.visible).map((item) => (
              <button key={item.key} onClick={() => goTo(item.key)} className={navButtonClass(item.key)}>
                <item.icon className={`w-3.5 h-3.5 shrink-0 ${item.iconClass}`} />
                <span className="hidden lg:inline">{item.label}</span>
                <span className="lg:hidden">
                  {item.key === 'evaluate' ? 'Evaluation' : item.key === 'stats' ? 'Stats' : item.label}
                </span>
              </button>
            ))}
          </nav>

          {/* Mobile menu toggle */}
          <button
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="sm:hidden -mr-1.5 p-2.5 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer shrink-0"
            aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <nav className="sm:hidden border-t border-slate-200 bg-white px-3 py-2 flex flex-col gap-1 text-sm font-semibold">
            {NAV_ITEMS.filter((item) => item.visible).map((item) => (
              <button
                key={item.key}
                onClick={() => goTo(item.key)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors cursor-pointer flex items-center space-x-2.5 min-h-[44px] ${
                  currentPage === item.key
                    ? item.key === 'evaluate'
                      ? 'bg-emerald-50 text-emerald-700 font-bold'
                      : 'bg-indigo-50 text-indigo-700 font-bold'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                <item.icon className={`w-4 h-4 shrink-0 ${item.iconClass}`} />
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        )}
      </header>

      {/* Main Content View Switcher */}
      <main className="flex-1">
        {currentPage === 'home' && (
          <HomePage onNavigate={goTo} />
        )}

        {currentPage === 'create' && (
          <CreatePlanPage onPlanGenerated={handlePlanGenerated} />
        )}

        {currentPage === 'result' && (
          <PlanResultPage
            planData={currentPlan}
            onNavigate={goTo}
            onSelectPlanForEvaluation={handleSelectPlanForEvaluation}
          />
        )}

        {currentPage === 'details' && (
          <PlanDetailPage
            planData={currentPlan}
            onNavigate={goTo}
          />
        )}

        {currentPage === 'evaluate' && (
          <EvaluationPage
            planId={evaluatingPlanId || (currentPlan ? currentPlan.plan_id : null)}
            planType={evaluatingPlanType}
            onSelectPlanType={setEvaluatingPlanType}
            onNavigate={goTo}
          />
        )}

        {currentPage === 'stats' && (
          <EvaluationStatsPage onNavigate={goTo} />
        )}
      </main>

      {/* Academic Footer */}
      <footer className="bg-white border-t border-slate-200 py-6 mt-12 text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-center sm:text-left">
          <div>
            <span className="font-semibold text-slate-700">
              "Design and Evaluation of an AI-Based Personalized Running Training Recommendation System"
            </span>
            <p className="text-[11px] text-slate-400 mt-0.5">
              BINUS University • Master of Information Technology (S2) Thesis Research Prototype
            </p>
          </div>
          <div className="text-[11px] text-slate-400">
            Rule-Based Physiology (VDOT & 80/20) + Modular LLM • Educational & Research Prototype
          </div>
        </div>
      </footer>
    </div>
  );
}
