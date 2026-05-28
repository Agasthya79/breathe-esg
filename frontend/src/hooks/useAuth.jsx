import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { login as apiLogin } from '../api/client';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const u = localStorage.getItem('user');
      return u ? JSON.parse(u) : null;
    } catch { return null; }
  });

  const login = useCallback(async (username, password) => {
    const { data } = await apiLogin(username, password);
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    // Decode JWT payload
    const payload = JSON.parse(atob(data.access.split('.')[1]));
    const u = { username: payload.username || username, role: payload.role || 'analyst', id: payload.user_id };
    localStorage.setItem('user', JSON.stringify(u));
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    localStorage.clear();
    setUser(null);
  }, []);

  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
