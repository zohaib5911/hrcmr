import type { Metadata } from "next";
import { RotaSettings } from "@/components/rota/settings";
export const metadata: Metadata = { title: "Rota settings" };
export default function Page() {
  return <RotaSettings />;
}
