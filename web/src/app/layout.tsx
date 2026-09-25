import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Settings } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/Brand";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ImobiQ — Agente SDR Imobiliário",
  description: "POC de agente SDR imobiliário com IA generativa (Hackathon FIAP Fase 5)",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
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
              href="/configuration"
              aria-label="Configurações"
              className="ml-auto inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink"
            >
              <Settings className="size-4" aria-hidden />
              <span className="hidden sm:inline">Configurações</span>
            </Link>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
