import { AppNav } from "@/components/AppNav";
import { SessionProvider } from "@/components/Session";

/** Layout do app ImobiQ (menu + conteúdo). A rota /embed fica fora deste grupo: é o chat dentro do widget. */
export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <AppNav />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
    </SessionProvider>
  );
}
