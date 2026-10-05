"use client";

import { KeyRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { PasswordInput } from "@/components/PasswordInput";
import { useSession } from "@/components/Session";
import { FeedbackLine, Field, buttonClass } from "@/components/settings/controls";
import { Card } from "@/components/ui";
import { ApiError, apiGet, apiPost } from "@/lib/api";

const MIN_LENGTH = 8;
type LinkInfo = { email: string; name: string | null; has_password: boolean; needs_terms: boolean };

/** Tela do link de convite ou de "esqueci minha senha": a pessoa cria a senha e já entra. */
export function SetPassword() {
  const router = useRouter();
  const { refresh } = useSession();
  const [token, setToken] = useState<string | null>(null);
  const [info, setInfo] = useState<LinkInfo | null>(null);
  const [invalid, setInvalid] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const first = window.setTimeout(async () => {
      const value = new URLSearchParams(window.location.search).get("token");
      if (!value) {
        setInvalid("Link incompleto. Abra o link que chegou no seu e-mail.");
        return;
      }
      try {
        setInfo(await apiGet<LinkInfo>(`/auth/password?token=${encodeURIComponent(value)}`));
        setToken(value);
      } catch (err) {
        setInvalid(err instanceof ApiError && err.status === 400 ? err.message : "Não consegui conferir o link agora.");
      }
    }, 0);
    return () => window.clearTimeout(first);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await apiPost("/auth/password", { token, password, accept_terms: accepted });
      await refresh();
      router.replace("/dashboard");
    } catch (err) {
      const known = err instanceof ApiError && (err.status === 400 || err.status === 422);
      setError(known ? err.message : "Não foi possível salvar a senha agora.");
      setBusy(false);
    }
  }

  const title = info?.has_password ? "Redefinir senha" : "Criar senha";
  if (invalid) {
    return (
      <Card title="Link inválido">
        <p className="text-sm text-ink-2">{invalid}</p>
        <p className="mt-3 text-sm">
          <Link href="/dashboard" className="font-medium text-brand underline-offset-2 hover:underline">
            Ir para o login
          </Link>{" "}
          <span className="text-muted">e usar &ldquo;Esqueci minha senha&rdquo; para receber um link novo.</span>
        </p>
      </Card>
    );
  }
  if (!info) {
    return (
      <Card title="Criar senha">
        <div className="h-32 animate-pulse rounded-lg bg-surface-2" />
      </Card>
    );
  }

  const tooShort = password.length > 0 && password.length < MIN_LENGTH;
  const mismatch = confirm.length > 0 && confirm !== password;
  return (
    <Card title={title}>
      <form onSubmit={submit} className="space-y-3">
        <p className="text-sm text-ink-2">
          Acesso de <strong className="font-medium text-ink">{info.email}</strong> ao ImobiQ.
        </p>
        {/* campo oculto com o e-mail: os gerenciadores de senha salvam a senha no usuário certo */}
        <input type="email" autoComplete="username" value={info.email} readOnly hidden />
        <Field label="Nova senha" htmlFor="new-password" hint={`Pelo menos ${MIN_LENGTH} caracteres.`}>
          <PasswordInput
            id="new-password"
            autoComplete="new-password"
            required
            minLength={MIN_LENGTH}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Field label="Repita a senha" htmlFor="confirm-password">
          <PasswordInput
            id="confirm-password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </Field>
        {info.needs_terms && (
          <label className="flex items-start gap-2 text-sm text-ink-2">
            <input
              type="checkbox"
              required
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
              className="mt-0.5 size-4 shrink-0 accent-brand"
            />
            <span>
              Li e aceito os{" "}
              <Link href="/termos" target="_blank" className="font-medium text-brand underline-offset-2 hover:underline">
                Termos de Uso
              </Link>{" "}
              e a{" "}
              <Link href="/privacidade" target="_blank" className="font-medium text-brand underline-offset-2 hover:underline">
                Política de Privacidade
              </Link>
              .
            </span>
          </label>
        )}
        <button
          type="submit"
          disabled={busy || password.length < MIN_LENGTH || confirm !== password || (info.needs_terms && !accepted)}
          className={`${buttonClass} bg-brand text-white hover:opacity-90`}
        >
          <KeyRound className="size-4" aria-hidden /> {busy ? "Salvando…" : "Salvar e entrar"}
        </button>
        {tooShort && <FeedbackLine feedback={{ tone: "error", text: `A senha precisa de pelo menos ${MIN_LENGTH} caracteres.` }} />}
        {mismatch && <FeedbackLine feedback={{ tone: "error", text: "As senhas não são iguais." }} />}
        {error && <FeedbackLine feedback={{ tone: "error", text: error }} />}
      </form>
    </Card>
  );
}
