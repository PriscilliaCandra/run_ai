import React from 'react';
import { Link } from 'react-router-dom';
import { Construction } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function PhaseTwoPlaceholderPage({ title, description }) {
  const { user } = useAuth();
  return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center">
      <div className="w-14 h-14 rounded-full bg-indigo-50 text-indigo-500 flex items-center justify-center mx-auto mb-4">
        <Construction className="w-7 h-7" />
      </div>
      <h2 className="text-xl font-bold text-slate-900">{title}</h2>
      <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto leading-relaxed">
        {description} This is part of the next development phase and isn't built yet
        {user ? `, ${user.display_name}` : ''} — your account and profile are ready for it.
      </p>
      <Link to="/profile" className="inline-block mt-6 text-xs font-semibold text-indigo-600 hover:text-indigo-800">
        Go to your profile →
      </Link>
    </div>
  );
}
