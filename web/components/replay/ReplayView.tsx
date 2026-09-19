import Link from "next/link";
import { PageIntro } from "@/components/ui/Section";
import { loadReplay, loadReplayIndex } from "@/lib/data";
import { ReplayPicker } from "./ReplayPicker";
import { ReplayPlayer } from "./ReplayPlayer";
import styles from "./ReplayView.module.css";

export const DEFAULT_REPLAY = "wimbledon-2019";

export function ReplayView({ slug }: { slug: string }) {
  const replays = loadReplayIndex();
  const replay = loadReplay(slug);
  return (
    <div className="container">
      <PageIntro eyebrow="Replay" title="Rejouer un match">
        <p>
          Revivez une finale point par point et regardez la probabilité de victoire basculer. Avant
          le premier point, elle vient du modèle LightGBM ; ensuite, une chaîne de Markov la met à
          jour à chaque point selon le score.
        </p>
      </PageIntro>
      <ReplayPicker replays={replays} current={replay.slug} />
      <ReplayPlayer key={replay.slug} replay={replay} />
      <p className={styles.note}>
        Données point par point : Match Charting Project (Jeff Sackmann). La probabilité
        d&apos;avant-match provient d&apos;un modèle entraîné uniquement sur les saisons antérieures
        au match. Détails dans la <Link href="/methodologie#replay">méthodologie</Link>.
      </p>
    </div>
  );
}
