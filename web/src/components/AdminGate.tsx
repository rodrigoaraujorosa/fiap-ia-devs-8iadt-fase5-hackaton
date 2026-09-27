"use client";

import { Lock, LogOut } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";

import { FeedbackLine, Field, buttonClass, inputClass } from "@/components/settings/controls";
import { Card } from "@/components/ui";
import { ApiError, apiGet, apiPost, setAdminToken, type AuthStatus } from "@/lib/api";

/** Páginas restritas (configurações, observabilidade): pedem a senha de administrador quando há ADMIN_PASSWORD. */
function AdminLogin({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { token } = await apiPost<{ token: string }>("/auth/login", { password });
      setAdminToken(token);
      onLogin();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? "Senha incorreta." : "Não foi possível entrar agora.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Acesso restrito">
      <form onSubmit={submit} className="space-y-3">
        <p className="flex items-center gap-1.5 text-sm text-ink-2">
          <Lock className="size-4 text-muted" aria-hidden /> As configurações são protegidas pela senha de administrador.
        </p>
        <Field label="Senha" htmlFor="admin-password">
          <input
            id="admin-password"
            type="password"
            autoComplete="current-password"
            autoFocus
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>
        <button type="submit" disabled={busy || !password} className={`${buttonClass} bg-brand text-white hover:opacity-90`}>
          {busy ? "Entrando…" : "Entrar"}
        </button>
        {error && <FeedbackLine feedback={{ tone: "error", text: error }} />}
      </form>
    </Card>
  );
}

export function AdminGate({
  title,
  subtitle,
  className = "mx-auto max-w-3xl space-y-4",
  actions,
  children,
}: {
  title: string;
  subtitle: string;
  className?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [failed, setFailed] = useState(false);

  const check = useCallback(async () => {
    try {
      setAuth(await apiGet<AuthStatus>("/auth/status"));
      setFailed(false);
    } catch {
      setFailed(true);
    }
  }, []);

  useEffect(() => {
    const first = window.setTimeout(check, 0);
    return () => window.clearTimeout(first);
  }, [check]);

  function logout() {
    setAdminToken(null);
    void check();
  }

  const open = auth && (!auth.required || auth.authenticated);
  return (
    <div className={className}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{title}</h1>
          <p className="text-sm text-ink-2">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {open && actions}
          {open && auth.required && (
            <button type="button" onClick={logout} className={`${buttonClass} border border-line text-ink-2 hover:text-ink`}>
              <LogOut className="size-4" aria-hidden /> Sair
            </button>
          )}
        </div>
      </div>
      {failed && <p className="text-sm text-danger">Não consegui falar com a API. Ela está rodando?</p>}
      {!auth && !failed && <div className="h-28 animate-pulse rounded-lg bg-surface-2" />}
      {auth && !open && (
        <div className="mx-auto max-w-3xl">
          <AdminLogin onLogin={check} />
        </div>
      )}
      {open && children}
    </div>
  );
}
