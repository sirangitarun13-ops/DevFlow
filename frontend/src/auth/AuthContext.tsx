import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, tokenStore } from "../api/client";
import type { RoleCode, User } from "../api/types";

interface AuthContextValue { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<void>; logout: () => void; hasRole: (...roles: RoleCode[]) => boolean; canManage: boolean }
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const restore = async () => { if (tokenStore.get()) { try { setUser(await api.me()); } catch { tokenStore.clear(); } } setLoading(false); };
    void restore();
    const expired = () => setUser(null);
    window.addEventListener("devflow:session-expired", expired);
    return () => window.removeEventListener("devflow:session-expired", expired);
  }, []);
  const value = useMemo<AuthContextValue>(() => {
    const codes = user?.roles.map((role) => role.code) ?? [];
    return { user, loading, login: async (email, password) => { const result = await api.login(email, password); tokenStore.set(result.access_token); setUser(await api.me()); }, logout: () => { tokenStore.clear(); setUser(null); }, hasRole: (...roles) => roles.some((role) => codes.includes(role)), canManage: codes.some((role) => ["admin", "project_manager", "team_lead"].includes(role)) };
  }, [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }
