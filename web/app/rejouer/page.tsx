import type { Metadata } from "next";
import { DEFAULT_REPLAY, ReplayView } from "@/components/replay/ReplayView";

export const metadata: Metadata = {
  title: "Rejouer un match",
  description:
    "Finales mythiques rejouées point par point avec l'évolution de la probabilité de victoire.",
};

export default function ReplayPage() {
  return <ReplayView slug={DEFAULT_REPLAY} />;
}
