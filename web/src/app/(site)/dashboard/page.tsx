import type { Metadata } from "next";

import { Protected } from "@/components/AdminGate";
import { Dashboard } from "@/components/dashboard/Dashboard";

export const metadata: Metadata = { title: "Dashboard · ImobiQ" };

export default function DashboardPage() {
  return (
    <Protected>
      <Dashboard />
    </Protected>
  );
}
