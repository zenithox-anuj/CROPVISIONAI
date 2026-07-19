import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = localStorage.getItem("cv_access");
    if (!t) { setLoading(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data))
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  const persist = (tokens) => {
    localStorage.setItem("cv_access", tokens.access_token);
    localStorage.setItem("cv_refresh", tokens.refresh_token);
    setUser(tokens.user);
  };

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    persist(data);
    return data.user;
  };

  const signup = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    persist(data);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("cv_access");
    localStorage.removeItem("cv_refresh");
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
