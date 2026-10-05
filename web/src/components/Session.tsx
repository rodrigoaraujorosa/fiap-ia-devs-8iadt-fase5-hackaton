"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { apiGet, apiPost, type Role, type SessionInfo } from "@/lib/api";

type SessionState = {
  /** null enquanto carrega (ou se a API não respondeu: veja failed) */
  session: SessionInfo | null;
  failed: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
  /** o usuário logado tem um destes papéis? */
  hasRole: (roles: readonly Role[]) => boolean;
  /** pode alterar dados (gerar resumo, enviar e-mail)? O visualizador só lê. */
  canWrite: boolean;
};

const SessionContext = createContext<SessionState | null>(null);

/** Quem está logado e com qual papel: uma consulta só, compartilhada pelo menu e pelas telas. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setSession(await apiGet<SessionInfo>("/auth/me"));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(refresh, 0);
    return () => window.clearTimeout(first);
  }, [refresh]);

  const logout = useCallback(async () => {
    try {
      await apiPost("/auth/logout");
    } finally {
      await refresh();
    }
  }, [refresh]);

  const value = useMemo<SessionState>(() => {
    const role = session?.user?.role;
    return {
      session,
      failed,
      refresh,
      logout,
      hasRole: (roles) => !!role && roles.includes(role),
      canWrite: !!role && role !== "visualizador",
    };
  }, [session, failed, refresh, logout]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession fora do SessionProvider");
  return value;
}
