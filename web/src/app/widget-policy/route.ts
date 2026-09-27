import { allowsHost, getWidgetPolicy } from "@/lib/widgetPolicy";

export const dynamic = "force-dynamic";

/** O widget.js pergunta se pode aparecer no site em que foi colocado (GET /widget-policy?origin=https://site). */
export async function GET(request: Request) {
  const origin = new URL(request.url).searchParams.get("origin") ?? "";
  let host = "";
  try {
    host = new URL(origin).host;
  } catch {
    /* origem inválida: só passa se a restrição estiver desligada */
  }
  const allowed = allowsHost(await getWidgetPolicy(), host);
  return Response.json({ allowed }, { headers: { "Access-Control-Allow-Origin": "*", "Cache-Control": "no-store" } });
}
