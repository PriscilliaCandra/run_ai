import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import ConsumerLayout from './layouts/ConsumerLayout';

import LandingPage from './pages/LandingPage';
import ProfilePage from './pages/ProfilePage';
import DashboardPage from './pages/DashboardPage';
import PlansPage from './pages/PlansPage';
import PlanNewPage from './pages/PlanNewPage';
import PlanDetailConsumerPage from './pages/PlanDetailConsumerPage';
import HistoryPage from './pages/HistoryPage';
import LogWorkoutPage from './pages/LogWorkoutPage';
import WorkoutDetailPage from './pages/WorkoutDetailPage';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import ForgotPasswordPage from './pages/auth/ForgotPasswordPage';
import ResetPasswordPage from './pages/auth/ResetPasswordPage';
import ResearchApp from './ResearchApp';

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* The unmodified S2 research prototype: anonymous, no login required. */}
        <Route path="/research/*" element={<ResearchApp />} />

        {/* Auth pages have their own minimal centered layout (see LoginPage etc.),
            not the consumer app chrome. */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

        {/* Consumer product shell (Phase 2) */}
        <Route element={<ConsumerLayout />}>
          <Route path="/" element={<LandingPage />} />

          <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
          <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />

          <Route path="/plans" element={<ProtectedRoute><PlansPage /></ProtectedRoute>} />
          <Route path="/plans/new" element={<ProtectedRoute><PlanNewPage /></ProtectedRoute>} />
          <Route path="/plans/:id" element={<ProtectedRoute><PlanDetailConsumerPage /></ProtectedRoute>} />

          <Route path="/history" element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
          <Route path="/workouts/new" element={<ProtectedRoute><LogWorkoutPage /></ProtectedRoute>} />
          <Route path="/workouts/:id" element={<ProtectedRoute><WorkoutDetailPage /></ProtectedRoute>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
