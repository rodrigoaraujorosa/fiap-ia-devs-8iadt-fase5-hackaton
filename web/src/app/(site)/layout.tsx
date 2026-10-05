import Link from "next/link";

import { AppNav } from "@/components/AppNav";
import { SessionProvider } from "@/components/Session";

/** Layout do app ImobiQ (menu + conteúdo). A rota /embed fica fora deste grupo: é o chat dentro do widget. */
export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AppNav />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
      <footer className="border-t border-line">
        <p className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-xs text-muted">
          <span>ImobiQ · prova de conceito acadêmica (Hackathon FIAP Pós Tech)</span>
          <Link href="/privacidade" className="ml-auto underline-offset-2 hover:text-ink-2 hover:underline">
            Política de Privacidade
          </Link>
          <Link href="/termos" className="underline-offset-2 hover:text-ink-2 hover:underline">
            Termos de Uso
          </Link>
        </p>
      </footer>
    </SessionProvider>
  );
}
