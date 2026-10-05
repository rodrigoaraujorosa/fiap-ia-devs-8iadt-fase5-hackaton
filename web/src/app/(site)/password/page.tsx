import type { Metadata } from "next";

import { SetPassword } from "@/components/SetPassword";

export const metadata: Metadata = { title: "Criar senha · ImobiQ", robots: { index: false } };

export default function PasswordPage() {
  return (
    <div className="mx-auto max-w-md">
      <SetPassword />
    </div>
  );
}
