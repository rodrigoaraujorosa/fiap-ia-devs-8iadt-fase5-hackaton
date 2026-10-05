"use client";

import { Activity, LogOut, Settings } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/Brand";
import { useSession } from "@/components/Session";
import { ROLE_LABEL } from "@/lib/api";

/** Menu do app: os links de cada área aparecem só para os papéis que têm acesso a ela. */
export function AppNav() {
  const { session, hasRole, logout } = useSession();
  const user = session?.user ?? null;
  // sem sessão carregada ou sem login, os links ficam à mostra: a própria tela pede o login
  const open = !user;
  const showInsights = open || hasRole(["admin", "gestor", "visualizador"]);
  const showSettings = open || hasRole(["admin"]);

  return (
    <header className="border-b border-line bg-surface">
      <nav className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:gap-5">
        <Link href="/" aria-label="ImobiQ, página inicial">
          <Logo />
        </Link>
        <Link href="/chat" className="text-sm text-ink-2 hover:text-ink">
          <span className="sm:hidden">Chat</span>
          <span className="hidden sm:inline">Chat do lead</span>
        </Link>
        <Link href="/dashboard" className="text-sm text-ink-2 hover:text-ink">
          <span className="sm:hidden">Dashboard</span>
          <span className="hidden sm:inline">Dashboard do corretor</span>
        </Link>
        <span className="ml-auto" />
        {showInsights && (
          <Link
            href="/observability"
            aria-label="Observabilidade"
            className="inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink"
          >
            <Activity className="size-4" aria-hidden />
            <span className="hidden md:inline">Observabilidade</span>
          </Link>
        )}
        {showSettings && (
          <Link
            href="/configuration"
            aria-label="Configurações"
            className="inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink"
          >
            <Settings className="size-4" aria-hidden />
            <span className="hidden md:inline">Configurações</span>
          </Link>
        )}
        {session?.required && user && (
          <div className="flex items-center gap-2 border-l border-line pl-4">
            {user.picture ? (
              // eslint-disable-next-line @next/next/no-img-element -- foto do perfil do Google, de domínio externo
              <img src={user.picture} alt="" width={28} height={28} referrerPolicy="no-referrer" className="size-7 rounded-full" />
            ) : (
              <span aria-hidden className="grid size-7 place-items-center rounded-full bg-surface-2 text-xs font-semibold text-ink-2">
                {user.name.slice(0, 1).toUpperCase()}
              </span>
            )}
            <span className="hidden text-sm leading-tight lg:block">
              <span className="block max-w-40 truncate font-medium text-ink">{user.name}</span>
              <span className="block text-xs text-muted">{ROLE_LABEL[user.role]}</span>
            </span>
            <button
              type="button"
              onClick={logout}
              aria-label="Sair"
              title="Sair"
              className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              <LogOut className="size-4" aria-hidden />
            </button>
          </div>
        )}
      </nav>
    </header>
  );
}
