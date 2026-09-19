import Link from "next/link";
import { PageIntro } from "@/components/ui/Section";

export default function NotFound() {
  return (
    <div className="container">
      <PageIntro eyebrow="Erreur 404" title="Cette page est hors des limites">
        <p>
          La page demandée n&apos;existe pas ou a été déplacée. Retournez à l&apos;
          <Link href="/">accueil</Link> ou <Link href="/rejouer">rejouez une finale</Link>.
        </p>
      </PageIntro>
    </div>
  );
}
