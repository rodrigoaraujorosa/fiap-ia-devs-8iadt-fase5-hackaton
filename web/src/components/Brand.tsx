import Image from "next/image";
import { useId } from "react";

/**
 * Identidade ImobiQ. Símbolo: uma casa em linha cuja cauda diagonal forma o "Q" (e lembra uma lupa:
 * buscar e qualificar). Mesmo desenho do favicon (app/icon.svg).
 */
export function LogoMark({ size = 28, className = "" }: { size?: number; className?: string }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0d9488" />
          <stop offset="1" stopColor="#0f5f59" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${id}-bg)`} />
      <path
        d="M8.5 15.2 16 8.8l7.5 6.4v7.3a1.5 1.5 0 0 1-1.5 1.5H10a1.5 1.5 0 0 1-1.5-1.5z"
        fill="none"
        stroke="#fff"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <path d="M18.6 19.8 25 26.2" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="16" cy="17.6" r="1.7" fill="#99f6e4" />
    </svg>
  );
}

export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span className="inline-flex items-center gap-2">
      <LogoMark size={size} />
      <span className="text-[1.05rem] font-semibold tracking-tight text-ink">
        Imobi<span className="text-brand">Q</span>
      </span>
    </span>
  );
}

/** Avatar da assistente Laris: balão de conversa com um telhado dentro. */
/** Avatar da Laris (robô com headset): o mesmo do widget e do bot do Telegram (public/laris-avatar.svg). */
export function LarisAvatar({ size = 36 }: { size?: number }) {
  return (
    <Image
      src="/laris-avatar.svg"
      width={size}
      height={size}
      alt=""
      aria-hidden
      unoptimized
      className="shrink-0 rounded-full"
    />
  );
}
