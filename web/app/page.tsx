import Link from "next/link";
import { Callout } from "@/components/ui/Section";
import { StatGrid, StatTile } from "@/components/ui/StatTile";
import { loadOverview, loadPerformance, loadReplayIndex } from "@/lib/data";
import {
  formatDate,
  formatDecimal,
  formatInteger,
  formatPercent,
  formatSigned,
} from "@/lib/format";
import { comparisonWith, differenceFor, modelReport } from "@/lib/models";
import styles from "./page.module.css";

export default function HomePage() {
  const overview = loadOverview();
  const performance = loadPerformance();
  const replays = loadReplayIndex();
  const model = modelReport(performance, "model");
  const elo = modelReport(performance, "elo");
  const logLoss = differenceFor(comparisonWith(performance, "elo"), "logLoss");
  const test = overview.periods.find((period) => period.name === "test");
  const beatsYears = performance.yearly.filter(
    (year) => year.model.logLoss < year.elo.logLoss,
  ).length;

  return (
    <div className="container">
      <section className={styles.hero} aria-labelledby="accueil-titre">
        <p className={styles.eyebrow}>Tennis ATP · Machine learning · Backtest honnête</p>
        <h1 id="accueil-titre">
          Prédire un match de tennis, et mesurer honnêtement l&apos;erreur.
        </h1>
        <p className={styles.lead}>
          MatchPoint estime la probabilité de victoire de chaque joueur avant un match ATP. Un
          modèle de gradient boosting, nourri par {formatInteger(overview.dataset.totalMatches)}{" "}
          matchs depuis 1968, est confronté sans filtre à la référence du domaine : un classement
          Elo par surface.
        </p>
        <div className={styles.actions}>
          <Link href="/performance" className={styles.primary}>
            Voir les résultats
          </Link>
          <Link href="/rejouer" className={styles.secondary}>
            Rejouer une finale
          </Link>
        </div>
      </section>

      <section aria-labelledby="chiffres-titre" className={styles.block}>
        <h2 id="chiffres-titre">L&apos;essentiel en chiffres</h2>
        <p className={styles.blockLead}>
          Mesuré sur {formatInteger(model.matches)} matchs jamais vus pendant l&apos;entraînement
          {test ? `, du ${formatDate(test.start)} au ${formatDate(test.end)}` : ""}.
        </p>
        <StatGrid>
          <StatTile
            label="Bons pronostics du modèle"
            value={formatPercent(model.accuracy)}
            detail={`contre ${formatPercent(elo.accuracy)} pour la baseline Elo`}
            emphasis
          />
          <StatTile
            label="Log loss (plus bas = mieux)"
            value={formatDecimal(model.logLoss, 3)}
            detail={`${formatSigned(logLoss.mean, 3)} face au Elo, écart significatif`}
          />
          <StatTile
            label="Saisons où le modèle bat le Elo"
            value={`${beatsYears} / ${performance.yearly.length}`}
            detail={`backtest annuel ${performance.yearly[0]?.year ?? ""}–${
              performance.yearly.at(-1)?.year ?? ""
            }`}
          />
          <StatTile
            label="Matchs analysés"
            value={formatInteger(overview.dataset.totalMatches)}
            detail={`${formatInteger(overview.dataset.players)} joueurs, de 1968 à ${new Date(
              overview.dataset.lastDate,
            ).getUTCFullYear()}`}
          />
        </StatGrid>
      </section>

      <section aria-labelledby="demarche-titre" className={styles.block}>
        <h2 id="demarche-titre">La démarche</h2>
        <ol className={styles.steps}>
          <li>
            <h3>Des données publiques et vérifiées</h3>
            <p>
              Tous les matchs du circuit principal depuis 1968, nettoyés : forfaits et abandons sont
              exclus de l&apos;apprentissage, les valeurs aberrantes rejetées.
            </p>
          </li>
          <li>
            <h3>Une référence solide</h3>
            <p>
              Un Elo global et par surface, mis à jour match après match dans l&apos;ordre
              chronologique strict. C&apos;est la barre à franchir.
            </p>
          </li>
          <li>
            <h3>Un modèle qui doit faire mieux</h3>
            <p>
              LightGBM combine le Elo avec la forme récente, le service, le repos, le face-à-face ou
              le classement, sans jamais voir une information postérieure au match.
            </p>
          </li>
          <li>
            <h3>Une évaluation sans triche</h3>
            <p>
              Entraînement jusqu&apos;en 2023, réglages sur 2024, verdict sur 2025 et 2026 :
              exactitude, log loss, score de Brier et calibration, côte à côte.
            </p>
          </li>
        </ol>
      </section>

      <section aria-labelledby="replays-titre" className={styles.block}>
        <h2 id="replays-titre">Rejouer une finale point par point</h2>
        <p className={styles.blockLead}>
          Chaque point fait bouger la probabilité de victoire. Revivez les renversements de finales
          mythiques, à partir des données du Match Charting Project.
        </p>
        <ul className={styles.replayList}>
          {replays.map((replay) => (
            <li key={replay.slug}>
              <Link href={`/rejouer/${replay.slug}`} className={styles.replayCard}>
                <span className={styles.replayTitle}>{replay.title}</span>
                <span className={styles.replayPlayers}>
                  {replay.shortNames[replay.winner]} bat {replay.shortNames[1 - replay.winner]}
                </span>
                <span className={styles.replayScore}>{replay.score}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <Callout title="Ce que ce projet ne prétend pas">
        <p>
          Un modèle de pronostic n&apos;est pas une boule de cristal : il se trompe sur environ un
          match sur trois. La page <Link href="/methodologie">méthodologie</Link> détaille ses
          limites, et la page <Link href="/performance">performance</Link> montre où il fait moins
          bien que la baseline.
        </p>
      </Callout>
    </div>
  );
}
