import React, { useState } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { Activity, LayoutDashboard, User, LogOut, LogIn, UserPlus, Menu, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function ConsumerLayout() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    setMenuOpen(false);
    navigate('/');
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-xs border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-3">
          <Link to="/" className="flex items-center gap-2.5 select-none min-w-0">
            <div className="w-9 h-9 shrink-0 rounded-xl bg-linear-to-br from-indigo-600 to-purple-600 text-white flex items-center justify-center shadow-xs">
              <Activity className="w-5 h-5" />
            </div>
            <span className="font-black text-slate-900 text-sm sm:text-base tracking-tight truncate">RunAI</span>
          </Link>

          <nav className="hidden sm:flex items-center gap-1 text-xs font-semibold">
            {isAuthenticated ? (
              <>
                <Link to="/dashboard" className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 flex items-center gap-1.5">
                  <LayoutDashboard className="w-3.5 h-3.5" /> Dashboard
                </Link>
                <Link to="/profile" className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 flex items-center gap-1.5">
                  <User className="w-3.5 h-3.5" /> Profile
                </Link>
                <button onClick={handleLogout} className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 flex items-center gap-1.5 cursor-pointer">
                  <LogOut className="w-3.5 h-3.5" /> Log Out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 flex items-center gap-1.5">
                  <LogIn className="w-3.5 h-3.5" /> Log In
                </Link>
                <Link to="/register" className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-1.5">
                  <UserPlus className="w-3.5 h-3.5" /> Sign Up
                </Link>
              </>
            )}
          </nav>

          <button
            onClick={() => setMenuOpen((o) => !o)}
            className="sm:hidden p-2.5 -mr-1.5 rounded-lg text-slate-600 hover:bg-slate-100 cursor-pointer"
            aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {menuOpen && (
          <nav className="sm:hidden border-t border-slate-200 bg-white px-3 py-2 flex flex-col gap-1 text-sm font-semibold">
            {isAuthenticated ? (
              <>
                <Link to="/dashboard" onClick={() => setMenuOpen(false)} className="px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 flex items-center gap-2.5 min-h-[44px]">
                  <LayoutDashboard className="w-4 h-4" /> Dashboard
                </Link>
                <Link to="/profile" onClick={() => setMenuOpen(false)} className="px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 flex items-center gap-2.5 min-h-[44px]">
                  <User className="w-4 h-4" /> Profile
                </Link>
                <button onClick={handleLogout} className="text-left px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 flex items-center gap-2.5 min-h-[44px] cursor-pointer">
                  <LogOut className="w-4 h-4" /> Log Out
                </button>
              </>
            ) : (
              <>
                <Link to="/login" onClick={() => setMenuOpen(false)} className="px-3 py-2.5 rounded-lg text-slate-600 hover:bg-slate-50 flex items-center gap-2.5 min-h-[44px]">
                  <LogIn className="w-4 h-4" /> Log In
                </Link>
                <Link to="/register" onClick={() => setMenuOpen(false)} className="px-3 py-2.5 rounded-lg bg-indigo-50 text-indigo-700 flex items-center gap-2.5 min-h-[44px]">
                  <UserPlus className="w-4 h-4" /> Sign Up
                </Link>
              </>
            )}
          </nav>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="bg-white border-t border-slate-200 py-5 text-center text-[11px] text-slate-400">
        RunAI Recommendation &middot; Personalized training, physiologically grounded.
      </footer>
    </div>
  );
}
