import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as api from "../services/api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const envGoogleId = import.meta.env.VITE_GOOGLE_CLIENT_ID || null;
  const [config, setConfig] = useState({
    google_enabled: Boolean(envGoogleId),
    google_client_id: envGoogleId,
  });

  const logout = useCallback(() => {
    localStorage.removeItem(api.TOKEN_KEY);
    setUser(null);
  }, []);

  useEffect(() => {
    api.setUnauthorizedHandler(logout);
    (async () => {
      try {
        const serverConfig = await api.getAuthConfig();
        setConfig({
          google_enabled: Boolean(serverConfig.google_enabled || envGoogleId),
          google_client_id: serverConfig.google_client_id || envGoogleId,
        });
      } catch {
        /* backend offline - login page will say so */
      }
      if (localStorage.getItem(api.TOKEN_KEY)) {
        try { setUser(await api.fetchMe()); } catch { localStorage.removeItem(api.TOKEN_KEY); }
      }
      setBooting(false);
    })();
  }, [logout, envGoogleId]);

  // Apply the user's accent colour to the whole app.
  useEffect(() => {
    document.documentElement.dataset.accent = user?.accent || "violet";
  }, [user?.accent]);

  const startSession = useCallback(({ token, user }) => {
    localStorage.setItem(api.TOKEN_KEY, token);
    setUser(user);
  }, []);

  const value = useMemo(
    () => ({
      user, booting, config, setUser, logout,
      login: async (email, password) => startSession(await api.login({ email, password })),
      signup: async (name, email, password) => startSession(await api.signup({ name, email, password })),
      googleLogin: async (credential) => startSession(await api.googleLogin(credential)),
    }),
    [user, booting, config, logout, startSession]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
