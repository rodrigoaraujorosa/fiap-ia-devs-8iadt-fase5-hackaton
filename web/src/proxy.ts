import { NextResponse } from "next/server";

import { frameAncestors, getWidgetPolicy } from "@/lib/widgetPolicy";

/** /embed (chat do widget): com a restrição de domínios ligada, só os sites da lista podem embutir o iframe. */
export async function proxy() {
  const response = NextResponse.next();
  const policy = await getWidgetPolicy();
  if (policy?.restrict) response.headers.set("Content-Security-Policy", `frame-ancestors ${frameAncestors(policy)}`);
  return response;
}

export const config = { matcher: "/embed" };
