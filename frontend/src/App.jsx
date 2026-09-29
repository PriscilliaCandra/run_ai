import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import ConsumerLayout from './layouts/ConsumerLayout';

import LandingPage from './pages/LandingPage';
import ProfilePage from './pages/ProfilePage';
import PhaseTwoPlaceholderPage from './pages/PhaseTwoPlaceholderPage';
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

        {/* Consumer product shell */}
        <Route element={<ConsumerLayout />}>
          <Route path="/" element={<LandingPage />} />

          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />

          {/* Routing/auth foundation only -- these are placeholders until
              Phase 2 (dashboard + workout logging) is approved and built. */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <PhaseTwoPlaceholderPage
                  title="Your Dashboard"
                  description="This week's summary, today's workout, and recent activity will live here."
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/plans"
            element={
              <ProtectedRoute>
                <PhaseTwoPlaceholderPage
                  title="Your Training Plans"
                  description="A list of your generated training plans will appear here."
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/plans/new"
            element={
              <ProtectedRoute>
                <PhaseTwoPlaceholderPage
                  title="Create a Training Plan"
                  description="The consumer plan-creation flow will live here, built on the same rule-based + AI engine as the research prototype."
                />
              </ProtectedRoute>
            }
          />
          <Route
            path="/plans/:id"
            element={
              <ProtectedRoute>
                <PhaseTwoPlaceholderPage
                  title="Training Plan"
                  description="Your plan's weekly schedule and detail view will live here."
                />
              </ProtectedRoute>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
