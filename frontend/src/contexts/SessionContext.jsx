import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from '../lib/apiClient';
import { authApi } from '../lib/api';

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [expired, setExpired] = useState(false);
  const [justLoggedOut, setJustLoggedOut] = useState(false);
  const logoutTimerRef = React.useRef(null);

  const bootstrap = useCallback(async () => {
    try {
      // quick health probe
      await apiClient.get('/health', { retries: 0 });
    } catch (err) {
      // backend may be down; still mark loaded so UI can render offline
      setLoaded(true);
      return;
    }

    // read token hint from localStorage
    const token = localStorage.getItem('doctalk_token');
    const local = localStorage.getItem('doctalk_session');
    const parsed = local ? JSON.parse(local) : null;

    if (token) {
      try {
        const data = await authApi.me(token);
        if (!data) {
          // malformed or empty response — clear session hint and bail
          localStorage.removeItem('doctalk_session');
          setSession(null);
          setLoaded(true);
          return;
        }
        const role = data.role || (parsed && parsed.role) || null;
        setSession({ ...(data || {}), role, token });
        setLoaded(true);
        return;
      } catch (e) {
        // fallthrough to clear
      }
    }

    // no valid session
    localStorage.removeItem('doctalk_session');
    setSession(null);
    setLoaded(true);
  }, []);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const login = async ({ token, sessionHint }) => {
    try {
      if (token) localStorage.setItem('doctalk_token', token);
      if (sessionHint) localStorage.setItem('doctalk_session', JSON.stringify(sessionHint));
    } catch (e) {}
    // attempt to verify and populate profile
    if (token) {
      try {
        const data = await authApi.me(token);
        if (data) {
          setSession({ ...(data || {}), role: data.role || sessionHint?.role, token });
          setExpired(false);
          return;
        }
        // if data falsy, fall through to hint-only session below
        setExpired(false);
        return;
      } catch (e) {}
    }
    // fallback to hint-only session
    setSession({ ...(sessionHint || {}), token });
  };

  const logout = async () => {
    // No explicit server logout endpoint in current backend; clear local session only
    // If a server-side logout is added later, call it here.
    try { localStorage.removeItem('doctalk_token'); localStorage.removeItem('doctalk_session'); } catch (e) {}
    setSession(null);
    setExpired(false);
    setJustLoggedOut(true);
    // auto-clear success message after 3s
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    logoutTimerRef.current = setTimeout(() => setJustLoggedOut(false), 3000);
  };

  const startLogoutTimer = (ms = 3000) => {
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    logoutTimerRef.current = setTimeout(() => setJustLoggedOut(false), ms);
  };

  const clearLogoutTimer = () => {
    if (logoutTimerRef.current) { clearTimeout(logoutTimerRef.current); logoutTimerRef.current = null; }
  };

  const markExpired = () => {
    setSession(null);
    setExpired(true);
    try { localStorage.removeItem('doctalk_token'); localStorage.removeItem('doctalk_session'); } catch (e) {}
  };

  useEffect(() => {
    return () => {
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    };
  }, []);

  return (
    <SessionContext.Provider value={{ session, loaded, expired, justLoggedOut, login, logout, markExpired, startLogoutTimer, clearLogoutTimer }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within SessionProvider');
  return ctx;
}

export default SessionContext;
