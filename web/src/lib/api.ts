const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
// No servidor (SSR dentro do Docker) a API é acessada pela rede interna do compose
export const API_URL =
  typeof window === "undefined" ? (process.env.INTERNAL_API_URL ?? PUBLIC_API_URL) : PUBLIC_API_URL;

export type Property = {
  id: string;
  title: string;
  property_type: string;
  purpose: "venda" | "aluguel";
  neighborhood: string;
  zone: string;
  city: string;
  price: number;
  condo_fee: number | null;
  iptu: number | null;
  bedrooms: number;
  suites: number;
  bathrooms: number;
  parking: number;
  area_m2: number;
  description: string;
  amenities: string[];
  furnished: boolean;
  pet_friendly: boolean;
  accepts_financing: boolean;
  estimated_yield: number | null;
  near_metro: boolean;
  available: boolean;
  similarity?: number | null;
};

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`GET ${path} falhou: ${res.status}`);
  return res.json() as Promise<T>;
}

export const brl = (value: number) =>
  value.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
