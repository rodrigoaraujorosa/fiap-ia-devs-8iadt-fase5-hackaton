import { Activity, Settings } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/Brand";

/** Layout do app ImobiQ (menu + conteúdo). A rota /embed fica fora deste grupo: é o chat dentro do widget. */
export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
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
          <Link
            href="/observability"
            aria-label="Observabilidade"
            className="ml-auto inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink"
          >
            <Activity className="size-4" aria-hidden />
            <span className="hidden md:inline">Observabilidade</span>
          </Link>
          <Link
            href="/configuration"
            aria-label="Configurações"
            className="inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink"
          >
            <Settings className="size-4" aria-hidden />
            <span className="hidden md:inline">Configurações</span>
          </Link>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
    </>
  );
}
