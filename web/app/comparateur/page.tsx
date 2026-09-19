import type { Metadata } from "next";
import { socialMetadata } from "@/lib/site";
import Link from "next/link";
import { Comparator } from "@/components/comparator/Comparator";
import { Callout, PageIntro } from "@/components/ui/Section";

export const metadata: Metadata = {
  title: "Comparateur de joueurs",
  ...socialMetadata({
    title: "Comparateur de joueurs · MatchPoint",
    description:
      "Choisissez deux joueurs ATP, actuels ou historiques, et obtenez une probabilité de victoire calculée dans votre navigateur.",
    path: "/comparateur",
  }),
};

export default function ComparatorPage() {
  return (
    <div className="container">
      <PageIntro eyebrow="Comparateur" title="Qui gagnerait ?">
        <p>
          Choisissez deux joueurs, de n&apos;importe quelle époque, qu&apos;ils se soient déjà
          affrontés ou non. Le modèle évalué sur la page{" "}
          <Link href="/performance">performance</Link> calcule la probabilité de victoire
          directement dans votre navigateur : aucune donnée n&apos;est envoyée à un serveur.
        </p>
      </PageIntro>
      <Comparator />
      <Callout title="À lire avant d'interpréter un résultat">
        <p>
          Le modèle a appris sur des matchs réels, entre joueurs de la même époque. Un duel entre
          générations est une extrapolation : les Elo de 1980 et de 2026 ne se mesurent pas contre
          les mêmes adversaires. Aucune explication détaillée de la prévision n&apos;est affichée :
          le moteur utilisé dans le navigateur ne permet pas de la calculer exactement, et une
          explication approximative serait moins honnête que son absence. Détails dans la{" "}
          <Link href="/methodologie#comparateur">méthodologie</Link>.
        </p>
      </Callout>
    </div>
  );
}
