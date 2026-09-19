import type { Metadata } from "next";
import { socialMetadata } from "@/lib/site";
import { DEFAULT_REPLAY, ReplayView } from "@/components/replay/ReplayView";

export const metadata: Metadata = {
  title: "Rejouer un match",
  ...socialMetadata({
    title: "Rejouer un match · MatchPoint",
    description:
      "Finales mythiques rejouées point par point avec l'évolution de la probabilité de victoire.",
    path: "/rejouer",
  }),
};

export default function ReplayPage() {
  return <ReplayView slug={DEFAULT_REPLAY} />;
}
