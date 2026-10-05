"use client";

import { Info, KeyRound, Lock, ShieldX } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { useSession } from "@/components/Session";
import { FeedbackLine, Field, buttonClass, inputClass, type Feedback } from "@/components/settings/controls";
import { LEGAL } from "@/components/Legal";
import { Card } from "@/components/ui";
import { API_URL, ApiError, apiPost, ROLE_LABEL, type Role } from "@/lib/api";

const ALL_ROLES: readonly Role[] = ["admin", "gestor", "corretor", "visualizador"];
const ADMIN_ONLY: readonly Role[] = ["admin"];

/** Motivos que a API devolve em ?auth_error=... quando o login com Google não abre a sessão. */
const AUTH_ERRORS: Record<string, string> = {
  nao_autorizado: "Esta conta Google não tem acesso ao ImobiQ. Peça um convite a um administrador.",
  cancelado: "Login cancelado.",
  expirado: "O login demorou demais ou foi iniciado em outra aba. Tente de novo.",
  google: "O Google não confirmou o login. Tente de novo em instantes.",
};

function loginError(err: unknown, wrong: string): string {
  if (err instanceof ApiError && err.status === 401) return wrong;
  if (err instanceof ApiError && err.status === 429) return err.message;
  return "Não foi possível entrar agora.";
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 18 18" width="18" height="18" aria-hidden>
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z" />
    </svg>
  );
}

/** E-mail e senha do usuário, com o caminho de "esqueci minha senha" (o link chega por e-mail). */
function EmailLogin({ onLogin }: { onLogin: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [forgot, setForgot] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback(null);
    try {
      if (forgot) {
        await apiPost("/auth/forgot", { email: email.trim() });
        setFeedback({ tone: "ok", text: "Se este e-mail tiver acesso, o link para criar uma nova senha chega em instantes." });
      } else {
        await apiPost("/auth/login", { email: email.trim(), password }); // a API abre a sessão num cookie HttpOnly
        onLogin();
      }
    } catch (err) {
      setFeedback({ tone: "error", text: forgot ? "Não foi possível enviar agora." : loginError(err, "E-mail ou senha incorretos.") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <Field label="E-mail" htmlFor="login-email">
        <input
          id="login-email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={inputClass}
        />
      </Field>
      {!forgot && (
        <Field label="Senha" htmlFor="login-password">
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={inputClass}
          />
        </Field>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="submit"
          disabled={busy || !email || (!forgot && !password)}
          className={`${buttonClass} bg-brand text-white hover:opacity-90`}
        >
          {forgot ? (busy ? "Enviando…" : "Enviar link por e-mail") : busy ? "Entrando…" : "Entrar"}
        </button>
        <button
          type="button"
          onClick={() => {
            setForgot((v) => !v);
            setFeedback(null);
          }}
          className="text-sm text-brand underline-offset-2 hover:underline"
        >
          {forgot ? "Voltar ao login" : "Esqueci minha senha"}
        </button>
      </div>
      <FeedbackLine feedback={feedback} />
    </form>
  );
}

function AdminPasswordForm({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiPost("/auth/login", { password });
      onLogin();
    } catch (err) {
      setError(loginError(err, "Senha incorreta."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <Field label="Senha de administrador" htmlFor="admin-password">
        <input
          id="admin-password"
          type="password"
          autoComplete="off"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputClass}
        />
      </Field>
      <button type="submit" disabled={busy || !password} className={`${buttonClass} border border-line text-ink hover:bg-surface-2`}>
        <KeyRound className="size-4" aria-hidden /> {busy ? "Entrando…" : "Entrar com a senha"}
      </button>
      {error && <FeedbackLine feedback={{ tone: "error", text: error }} />}
    </form>
  );
}

/** Tela de login: e-mail e senha, ou a conta Google do mesmo e-mail; a senha de administrador fica como emergência. */
function LoginCard() {
  const { session, refresh } = useSession();
  const pathname = usePathname();
  const [authError, setAuthError] = useState<string | null>(null);

  useEffect(() => {
    // a volta do Google traz o motivo na URL; depois de lido, sai da barra de endereços
    const first = window.setTimeout(() => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("auth_error");
      if (!code) return;
      setAuthError(AUTH_ERRORS[code] ?? "Não foi possível entrar.");
      params.delete("auth_error");
      const query = params.toString();
      window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
    }, 0);
    return () => window.clearTimeout(first);
  }, []);

  if (!session) return null;
  return (
    <Card title="Entrar no ImobiQ">
      <div className="space-y-4">
        <p className="flex items-center gap-1.5 text-sm text-ink-2">
          <Lock className="size-4 shrink-0 text-muted" aria-hidden /> Área restrita à equipe da imobiliária.
        </p>
        <div className="flex items-start gap-2 rounded-lg bg-surface-2 p-3 text-xs text-ink-2">
          <Info className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
          <p>
            Esta é uma prova de conceito com acesso por convite.
            {session.google && " Para entrar com o Google, a sua conta precisa estar pré-cadastrada para os testes."}{" "}
            {session.google ? "Sem conta Google, você" : "Você"} precisa receber um convite por e-mail para criar a
            senha. Para pedir acesso, escreva para{" "}
            <a href={`mailto:${LEGAL.email}`} className="font-medium text-brand underline-offset-2 hover:underline">
              {LEGAL.email}
            </a>
            .
          </p>
        </div>
        {authError && <FeedbackLine feedback={{ tone: "error", text: authError }} />}
        <EmailLogin onLogin={refresh} />
        {session.google && (
          <>
            <div className="flex items-center gap-3 text-xs text-muted" role="separator">
              <span className="h-px flex-1 bg-line" /> ou <span className="h-px flex-1 bg-line" />
            </div>
            <a
              href={`${API_URL}/auth/google/login?next=${encodeURIComponent(pathname)}`}
              className={`${buttonClass} w-full border border-line bg-white text-[#1f1f1f] hover:bg-[#f7f8f8]`}
            >
              <GoogleMark /> Entrar com Google
            </a>
          </>
        )}
        <p className="text-xs text-muted">
          Ao entrar, você concorda com os{" "}
          <Link href="/termos" className="underline underline-offset-2 hover:text-ink-2">
            Termos de Uso
          </Link>{" "}
          e a{" "}
          <Link href="/privacidade" className="underline underline-offset-2 hover:text-ink-2">
            Política de Privacidade
          </Link>
          .
        </p>
        {session.password && (
          <details className="border-t border-line pt-3">
            <summary className="cursor-pointer text-xs text-muted hover:text-ink-2">Acesso de emergência do administrador</summary>
            <div className="mt-3">
              <AdminPasswordForm onLogin={refresh} />
            </div>
          </details>
        )}
      </div>
    </Card>
  );
}

function NoAccess({ roles }: { roles: readonly Role[] }) {
  const { session } = useSession();
  return (
    <Card title="Sem acesso a esta área">
      <p className="flex items-start gap-1.5 text-sm text-ink-2">
        <ShieldX className="mt-0.5 size-4 shrink-0 text-warm" aria-hidden />
        <span>
          Seu perfil é <strong className="font-medium text-ink">{ROLE_LABEL[session?.user?.role ?? "visualizador"]}</strong>.
          Esta área é para {roles.map((r) => ROLE_LABEL[r]).join(", ")}. Fale com um administrador se precisar do acesso.
        </span>
      </p>
    </Card>
  );
}

/** Mostra o conteúdo só para quem está logado com um dos papéis; senão, o login ou o aviso de falta de acesso. */
export function Protected({ roles = ALL_ROLES, children }: { roles?: readonly Role[]; children: ReactNode }) {
  const { session, failed, hasRole } = useSession();
  if (failed && !session) return <p className="text-sm text-danger">Não consegui falar com a API. Ela está rodando?</p>;
  if (!session) return <div className="h-28 animate-pulse rounded-lg bg-surface-2" />;
  if (!session.user) {
    return (
      <div className="mx-auto max-w-md">
        <LoginCard />
      </div>
    );
  }
  if (!hasRole(roles)) {
    return (
      <div className="mx-auto max-w-xl">
        <NoAccess roles={roles} />
      </div>
    );
  }
  return <>{children}</>;
}

/** Página restrita com título (configurações, observabilidade). Por padrão, só administradores. */
export function AdminGate({
  title,
  subtitle,
  className = "mx-auto max-w-3xl space-y-4",
  roles = ADMIN_ONLY,
  children,
}: {
  title: string;
  subtitle: string;
  className?: string;
  roles?: readonly Role[];
  children: ReactNode;
}) {
  return (
    <div className={className}>
      <div>
        <h1 className="text-2xl font-semibold text-ink">{title}</h1>
        <p className="text-sm text-ink-2">{subtitle}</p>
      </div>
      <Protected roles={roles}>{children}</Protected>
    </div>
  );
}
