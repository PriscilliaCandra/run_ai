import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { fetchCurrentUser, login as apiLogin, logout as apiLogout, registerAccount } from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const current = await fetchCurrentUser();
      setUser(current);
      return current;
    } catch {
      // 401 (or any failure) simply means no active session -- not an error to surface.
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const login = useCallback(async (email, password) => {
    const loggedInUser = await apiLogin({ email, password });
    setUser(loggedInUser);
    return loggedInUser;
  }, []);

  const register = useCallback(async (email, password, displayName) => {
    const newUser = await registerAccount({ email, password, displayName });
    setUser(newUser); // registration also logs the user in (see backend/app/auth/routes.py)
    return newUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
