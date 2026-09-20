import type { Metadata } from "next";
import { ChartFigure } from "@/components/charts/ChartFigure";
import { ImportanceChart } from "@/components/charts/ImportanceChart";
import { Callout, PageIntro, Section } from "@/components/ui/Section";
import tableStyles from "@/components/ui/DataTable.module.css";
import { loadComparatorSummary, loadModelDetails, loadOverview, loadPerformance } from "@/lib/data";
import { formatDate, formatDecimal, formatInteger, formatPercent } from "@/lib/format";
import { modelReport } from "@/lib/models";
import { REPOSITORY_URL, socialMetadata } from "@/lib/site";
import type { Period, Segment } from "@/lib/types";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Méthodologie",
  ...socialMetadata({
    title: "Méthodologie · MatchPoint",
    description:
      "Données, découpage temporel, baseline Elo, modèle LightGBM, comparateur dans le navigateur, replay par chaîne de Markov et limites connues.",
    path: "/methodologie",
  }),
};

const HYPERPARAMETER_LABELS: Record<string, string> = {
  learning_rate: "Taux d'apprentissage",
  num_leaves: "Feuilles par arbre",
  min_data_in_leaf: "Matchs minimum par feuille",
  feature_fraction: "Part des variables par arbre",
  bagging_fraction: "Part des matchs par arbre",
  lambda_l2: "Régularisation L2",
};

const FEATURE_GROUPS = [
  {
    title: "Elo",
    text: "Elo global et Elo de la surface des deux joueurs, leurs écarts et leur combinaison 50/50.",
  },
  {
    title: "Classement ATP",
    text: "Rang et points au classement avant le match, sous forme de rapports logarithmiques.",
  },
  {
    title: "Forme récente",
    text: "Part de victoires sur les 10 et 20 derniers matchs, toutes surfaces et sur la surface du jour.",
  },
  {
    title: "Service et retour",
    text: "Part des points gagnés au service et au retour sur les 30 derniers matchs renseignés.",
  },
  {
    title: "Face-à-face",
    text: "Victoires de chacun dans les confrontations précédentes, et part lissée pour le joueur A.",
  },
  {
    title: "Repos et fatigue",
    text: "Jours depuis le dernier match joué (plafonnés à 60) et matchs déjà disputés dans le tournoi.",
  },
  {
    title: "Profil",
    text: "Âge, taille, main dominante et nombre de matchs joués en carrière et sur la surface.",
  },
  {
    title: "Contexte",
    text: "Surface, niveau du tournoi, tour, format en 3 ou 5 sets et taille du tableau.",
  },
];

function periodText(period: Period): string {
  return `du ${formatDate(period.start)} au ${formatDate(period.end)}`;
}

function segmentByValue(segments: Segment[], dimension: Segment["dimension"], value: string) {
  return segments.find((segment) => segment.dimension === dimension && segment.value === value);
}

export default function MethodologyPage() {
  const overview = loadOverview();
  const details = loadModelDetails();
  const comparator = loadComparatorSummary();
  const performance = loadPerformance();
  const model = modelReport(performance, "model");
  const elo = modelReport(performance, "elo");
  const { dataset } = overview;
  const snapshot = overview.source.revision.slice(0, 7);
  const masters = segmentByValue(performance.segments, "tourney_level", "M");
  const rookies = performance.segments.find(
    (segment) => segment.dimension === "experience" && segment.value.startsWith("moins"),
  );
  const veterans = performance.segments.find(
    (segment) => segment.dimension === "experience" && !segment.value.startsWith("moins"),
  );
  const booster = details.gradientBoosting;
  const calibrationNames: Record<string, string> = {
    aucune: "aucune",
    platt: "Platt",
    isotonique: "isotonique",
  };
  const totalPeriodMatches = overview.periods.reduce((total, period) => total + period.matches, 0);

  return (
    <div className="container">
      <PageIntro eyebrow="Transparence" title="Méthodologie">
        <p>
          Comment les données sont préparées, comment les modèles sont construits et évalués, et
          surtout ce qu&apos;ils ne savent pas faire.
        </p>
      </PageIntro>

      <nav aria-label="Sommaire de la méthodologie" className={styles.toc}>
        <ol>
          <li>
            <a href="#donnees">Données</a>
          </li>
          <li>
            <a href="#decoupage">Découpage temporel</a>
          </li>
          <li>
            <a href="#elo">Baseline Elo</a>
          </li>
          <li>
            <a href="#modele">Modèle LightGBM</a>
          </li>
          <li>
            <a href="#comparateur">Comparateur de joueurs</a>
          </li>
          <li>
            <a href="#replay">Replay point par point</a>
          </li>
          <li>
            <a href="#limites">Limites connues</a>
          </li>
          <li>
            <a href="#reproduire">Reproduire les résultats</a>
          </li>
        </ol>
      </nav>

      <div className={styles.prose}>
        <Section id="donnees" title="Données">
          <p>
            Les résultats proviennent du dépôt <strong>tennis_atp</strong> de Jeff Sackmann (Tennis
            Abstract) : {formatInteger(dataset.totalMatches)} matchs du circuit principal (Grand
            Chelem, Masters 1000, ATP 250 et 500, Masters de fin d&apos;année, Coupe Davis, Jeux
            olympiques) disputés par {formatInteger(dataset.players)} joueurs entre{" "}
            {new Date(dataset.firstDate).getUTCFullYear()} et le {formatDate(dataset.lastDate)}.
          </p>
          <Callout title="Une source qui a disparu">
            <p>
              En septembre 2026, le dépôt original n&apos;est plus accessible publiquement. Le
              pipeline le tente toujours en premier, puis se replie sur une copie publique épinglée
              sur le dernier commit publié par l&apos;auteur (<code>{snapshot}</code>, « thru 8 jun
              2026 »). L&apos;empreinte Git d&apos;un commit dépend de tout son contenu : les
              fichiers sont donc identiques à l&apos;original.
            </p>
          </Callout>
          <p>Nettoyage appliqué avant tout calcul :</p>
          <ul>
            <li>
              {formatInteger(dataset.walkovers)} forfaits et {formatInteger(dataset.retirements)}{" "}
              abandons ou disqualifications sont exclus du Elo, de l&apos;apprentissage et de
              l&apos;évaluation, car ils ne reflètent pas un résultat sportif. Les abandons comptent
              toutefois comme matchs joués pour la fatigue et le repos.
            </li>
            <li>
              {formatInteger(dataset.unknownScores)} matchs au score illisible et{" "}
              {formatInteger(dataset.discardedRows)} lignes incohérentes (joueur contre lui-même,
              format inconnu) sont écartés.
            </li>
            <li>
              Tailles hors de 150–215 cm, âges hors de 14–50 ans et classements non positifs sont
              traités comme manquants. Le jeu est rejeté si une date est incohérente ou si
              l&apos;ordre chronologique est rompu.
            </li>
            <li>
              La base ne donne que la date de début du tournoi : la date de chaque match est estimée
              à partir du tour, ce qui fixe l&apos;ordre chronologique et le calcul des jours de
              repos.
            </li>
          </ul>
        </Section>

        <Section id="decoupage" title="Découpage temporel">
          <p>
            Règle non négociable : aucune information postérieure à un match ne sert à le prédire.
            Le découpage est donc chronologique, jamais aléatoire.
          </p>
          <ol className={styles.timeline}>
            {overview.periods.map((period) => (
              <li
                key={period.name}
                className={styles[period.name]}
                style={{ flexGrow: Math.max(period.matches / totalPeriodMatches, 0.18) }}
              >
                <span className={styles.periodName}>{period.label}</span>
                <span className={styles.periodDates}>{periodText(period)}</span>
                <span className={styles.periodCount}>{formatInteger(period.matches)} matchs</span>
              </li>
            ))}
          </ol>
          <p>
            Le Elo et toutes les variables sont calculés en un seul passage chronologique depuis
            1968 : pour chaque match, seuls les matchs antérieurs sont pris en compte. Les
            hyperparamètres et la calibration sont choisis sur 2024 ; la période de test n&apos;est
            utilisée qu&apos;une fois, pour le verdict. Un tournoi appartient à la période de sa
            date de début.
          </p>
        </Section>

        <Section id="elo" title="Baseline Elo">
          <p>
            Chaque joueur possède un Elo global et un Elo par surface (dur, terre battue, gazon).
          </p>
          <dl className={styles.formulas}>
            <div>
              <dt>Probabilité de victoire</dt>
              <dd>
                <code>P(A) = 1 / (1 + 10^((R_B − R_A) / 400))</code>
              </dd>
            </div>
            <div>
              <dt>Mise à jour après le match</dt>
              <dd>
                <code>R&apos; = R + K × (S − P)</code>, avec S = 1 pour le vainqueur et 0 pour le
                perdant
              </dd>
            </div>
            <div>
              <dt>Facteur K dégressif</dt>
              <dd>
                <code>
                  K = {details.elo.kNumerator} / (n + {details.elo.kOffset})^{details.elo.kShape}
                </code>
                , où n est le nombre de matchs déjà joués
              </dd>
            </div>
            <div>
              <dt>Baseline retenue</dt>
              <dd>
                moyenne à {formatPercent(details.elo.surfaceWeight, 0)} de l&apos;Elo global et de
                l&apos;Elo de la surface, tous deux partant de {details.elo.initialRating}
              </dd>
            </div>
          </dl>
          <p>
            Ces paramètres viennent de la littérature (FiveThirtyEight, Kovalchik 2016) et ne sont
            pas optimisés sur nos données, pour que la baseline ne profite d&apos;aucun réglage
            opportuniste. Sur la période de test, la combinaison atteint{" "}
            {formatPercent(elo.accuracy)} d&apos;exactitude. Elle est cependant trop confiante
            (erreur de calibration de {formatPercent(elo.calibrationError)}) : c&apos;est pourquoi
            la page performance ajoute un « Elo recalibré » par régression logistique, ajustée sur
            les seules années d&apos;entraînement.
          </p>
        </Section>

        <Section id="modele" title="Modèle LightGBM">
          <p>
            Le modèle avancé est un gradient boosting d&apos;arbres de décision (LightGBM). Il
            reçoit {formatInteger(details.importance.features.length)} variables, toutes connues
            avant le premier point du match :
          </p>
          <ul className={styles.featureGrid}>
            {FEATURE_GROUPS.map((group) => (
              <li key={group.title}>
                <strong>{group.title}.</strong> {group.text}
              </li>
            ))}
          </ul>
          <p>
            Chaque match est présenté deux fois à l&apos;entraînement, une fois du point de vue de
            chaque joueur, et la prédiction finale moyenne les deux points de vue : P(A bat B) + P(B
            bat A) vaut toujours exactement 100 %.
          </p>
          <h3>Recherche d&apos;hyperparamètres</h3>
          <p>
            Recherche aléatoire de {booster.trials} configurations : chacune est entraînée sur
            1991–2023, arrêtée au meilleur nombre d&apos;arbres sur 2024, et jugée sur la log loss
            de 2024. Aucune validation croisée aléatoire : elle mélangerait passé et futur.
          </p>
          <div
            className={tableStyles.scroll}
            tabIndex={0}
            role="region"
            aria-label="Hyperparamètres retenus"
          >
            <table className={tableStyles.table}>
              <caption>Configuration retenue</caption>
              <thead>
                <tr>
                  <th scope="col">Paramètre</th>
                  <th scope="col">Valeur</th>
                  <th scope="col">Valeurs testées</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(booster.hyperparameters).map(([name, value]) => (
                  <tr key={name}>
                    <th scope="row">{HYPERPARAMETER_LABELS[name] ?? name}</th>
                    <td>{formatDecimal(value, Number.isInteger(value) ? 0 : 2)}</td>
                    <td>
                      {(booster.searchSpace[name] ?? [])
                        .map((item) => formatDecimal(item, Number.isInteger(item) ? 0 : 2))
                        .join(" · ")}
                    </td>
                  </tr>
                ))}
                <tr>
                  <th scope="row">Nombre d&apos;arbres</th>
                  <td>{formatInteger(booster.trees)}</td>
                  <td>arrêt anticipé, jusqu&apos;à 6 000</td>
                </tr>
              </tbody>
            </table>
          </div>
          <h3>Calibration</h3>
          <p>
            Trois options ont été comparées par validation croisée sur les deux moitiés de 2024 :{" "}
            {Object.entries(booster.calibration.candidates)
              .map(
                ([name, value]) =>
                  `${calibrationNames[name] ?? name} (log loss ${formatDecimal(value, 4)})`,
              )
              .join(", ")}
            . Option retenue : <strong>{calibrationNames[booster.calibration.chosen]}</strong>
            {booster.calibration.chosen === "aucune"
              ? ", la sortie brute de LightGBM étant déjà bien calibrée."
              : "."}
          </p>
          <h3>Variables testées et écartées</h3>
          <p>
            Le jeu de variables n&apos;est pas figé, mais une idée n&apos;est retenue que si elle
            améliore vraiment les prévisions. La décision ne se prend jamais sur la période de test,
            qui deviendrait alors un jeu de réglage : elle se prend sur un backtest glissant
            2015-2024 de 26 785 matchs, à hyperparamètres identiques pour toutes les variantes.
            Quatre pistes ont été mesurées ainsi, et toutes écartées : les aces et doubles fautes,
            les balles de break sauvées, la durée des matchs comme indice de fatigue, et un Elo de
            surface initialisé à l&apos;Elo global plutôt qu&apos;à 1 500.
          </p>
          <p>
            Le service détaillé illustre le piège : il gagnait 0,0019 de log loss sur les{" "}
            {formatInteger(performance.models[0]?.matches ?? 0)} matchs de test, écart apparemment
            significatif, mais ne gagnait plus rien (−0,00001) sur six fois plus de matchs. À titre
            de comparaison, retirer le classement ATP du modèle coûte 0,0046 de log loss, et retirer
            le service et le retour 0,0022 : les variables conservées ont un effet d&apos;un ordre
            de grandeur supérieur. Le détail chiffré figure dans le{" "}
            <a
              href={`${REPOSITORY_URL}#variables-testées--ce-qui-aide-ce-qui-naide-pas`}
              rel="noopener"
            >
              README
            </a>
            .
          </p>
          <h3>Ce qui pèse dans la décision</h3>
          <ChartFigure
            title="Importance des familles de variables"
            description="Part du gain total des arbres apportée par chaque famille de variables dans le modèle final."
            table={
              <table className={tableStyles.table}>
                <thead>
                  <tr>
                    <th scope="col">Variable</th>
                    <th scope="col">Part du gain</th>
                  </tr>
                </thead>
                <tbody>
                  {details.importance.features.map((feature) => (
                    <tr key={feature.name}>
                      <th scope="row">{feature.label}</th>
                      <td>{formatPercent(feature.share, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <ImportanceChart
              title="Importance des familles de variables"
              families={details.importance.families}
            />
          </ChartFigure>
          <p>
            Le Elo reste le socle de la décision. Les autres familles apportent des signaux
            qu&apos;il ne voit pas directement, comme la qualité au service et au retour,
            l&apos;expérience ou le classement officiel, pour un poids cumulé de{" "}
            {formatPercent(
              details.importance.families
                .filter((family) => family.key !== "elo")
                .reduce((total, family) => total + family.share, 0),
              0,
            )}
            .
          </p>
        </Section>

        <Section id="comparateur" title="Comparateur de joueurs">
          <p>
            Le comparateur utilise exactement le modèle évalué plus haut, sans aucun serveur. À
            chaque rafraîchissement, le pipeline exporte trois fichiers :
          </p>
          <ul>
            <li>
              <strong>le modèle</strong>, converti au format ONNX avec <code>onnxmltools</code> puis
              passé en double précision, et exécuté dans le navigateur par{" "}
              <code>onnxruntime-web</code> ;
            </li>
            <li>
              <strong>l&apos;état de chaque joueur</strong> à l&apos;issue de son dernier match :
              Elo global et par surface, forme, service et retour, classement, âge (
              {formatInteger(comparator.players)} joueurs ayant au moins {comparator.minMatches}{" "}
              matchs dans la base) ;
            </li>
            <li>
              <strong>les face-à-face</strong> des paires qui se sont déjà rencontrées ; pour les
              autres, le bilan vaut simplement 0-0.
            </li>
          </ul>
          <p>
            Le navigateur combine les deux joueurs choisis pour fabriquer les{" "}
            {formatInteger(comparator.metadata.features.length)} variables, dans les deux sens (A
            contre B, puis B contre A), et fait tourner le modèle localement. Le match imaginé est
            un premier tour du type de tournoi choisi, les deux joueurs arrivant reposés (
            {comparator.metadata.neutralRestDays} jours depuis leur dernier match), chacun tel
            qu&apos;il était à son dernier match connu.
          </p>
          <h3>Trois garde-fous contre une divergence silencieuse</h3>
          <ul>
            <li>
              La conversion ONNX standard compare les valeurs en simple précision : sur le modèle
              publié, elle s&apos;écarte de LightGBM jusqu&apos;à{" "}
              {formatDecimal(comparator.metadata.parity.float32MaxDifference * 100, 1)} points de
              probabilité. Le modèle est donc passé en double précision, et son export est refusé si
              l&apos;écart dépasse 1e-6 : sur les {formatInteger(comparator.metadata.parity.rows)}{" "}
              lignes de la période de test, l&apos;écart maximal est de{" "}
              {comparator.metadata.parity.maxDifference.toExponential(1).replace(".", ",")}.
            </li>
            <li>
              Les variables sont recalculées en TypeScript à partir des mêmes formules que le
              pipeline Python ; une fixture commune vérifie que les deux implémentations produisent
              le même vecteur, valeurs manquantes comprises.
            </li>
            <li>
              Des cas de contrôle sur de vrais joueurs sont prédits par Python à l&apos;export, puis
              recalculés de bout en bout par <code>onnxruntime-web</code> dans les tests : ils
              doivent coïncider à 1e-6 près.
            </li>
          </ul>
          <h3>Ce que le comparateur ne dit pas</h3>
          <p>
            Un avertissement s&apos;affiche quand un joueur compte moins de{" "}
            {comparator.reliableMatches} matchs dans la base ou n&apos;a pas joué depuis plus
            d&apos;un an : l&apos;estimation repose alors sur un historique trop mince ou périmé.
            Les duels entre époques sont des extrapolations, le modèle n&apos;ayant appris que sur
            des joueurs contemporains. Enfin, aucune explication détaillée de la prévision (de type
            SHAP) n&apos;est affichée : le moteur du navigateur ne la calcule pas, et une
            approximation serait moins honnête que son absence.
          </p>
        </Section>

        <Section id="replay" title="Replay point par point">
          <p>
            Les matchs rejoués viennent du{" "}
            <a href="https://github.com/JeffSackmann/tennis_MatchChartingProject" rel="noopener">
              Match Charting Project
            </a>
            , où des bénévoles notent chaque point. Le score est reconstitué point par point et
            confronté au relevé et au score officiel : un seul écart et le match est rejeté.
          </p>
          <ol>
            <li>
              La probabilité d&apos;avant-match vient du backtest annuel : un modèle entraîné
              uniquement sur les saisons précédant le match. Aucune finale n&apos;a été vue par le
              modèle qui la prédit.
            </li>
            <li>
              Cette probabilité est traduite en deux chances de gagner un point sur son service,{" "}
              <code>μ + d</code> et <code>μ − d</code>, où μ est la moyenne du circuit sur la
              surface lors des trois saisons précédentes et d est choisi pour retrouver exactement
              la probabilité d&apos;avant-match.
            </li>
            <li>
              Une chaîne de Markov (point, jeu, tie-break, set, match) donne ensuite la probabilité
              exacte de victoire depuis n&apos;importe quel score, en respectant la règle du set
              décisif de l&apos;époque : jeu décisif à 12-12 à Wimbledon en 2019, super tie-break en
              10 points depuis 2022, avantage avant cela.
            </li>
          </ol>
          <p>
            Le calcul exact a été vérifié contre des simulations de Monte-Carlo dans les tests
            automatisés.
          </p>
        </Section>

        <Section id="limites" title="Limites connues">
          <ul className={styles.limits}>
            <li>
              <strong>Joueurs peu connus du modèle.</strong> Seuls les matchs du circuit principal
              sont utilisés : un joueur qui sort des Challengers arrive presque sans historique.
              {rookies && veterans
                ? ` Sur la période de test, l'écart reste faible (${formatPercent(rookies.model.accuracy)} d'exactitude quand l'un des joueurs a moins de 30 matchs en base, ${formatPercent(veterans.model.accuracy)} sinon), mais ces prévisions reposent sur peu d'information.`
                : ""}
            </li>
            <li>
              <strong>Blessures et contexte invisibles.</strong> Le modèle ignore une blessure en
              cours, une maladie, la motivation, la météo, l&apos;altitude, le type de balle ou le
              fait de jouer en salle.
            </li>
            {masters && masters.model.accuracy < masters.elo.accuracy ? (
              <li>
                <strong>Moins bon que le Elo en Masters 1000.</strong> Sur les{" "}
                {formatInteger(masters.matches)} matchs de Masters 1000 de la période de test,
                LightGBM en prédit {formatPercent(masters.model.accuracy)} contre{" "}
                {formatPercent(masters.elo.accuracy)} pour le Elo. L&apos;écart est faible au regard
                du nombre de matchs, mais il est affiché tel quel.
              </li>
            ) : null}
            <li>
              <strong>Exclusion des abandons.</strong> Avant un match, personne ne sait qu&apos;il
              finira sur abandon : les retirer de l&apos;évaluation rend les scores légèrement
              optimistes, pour les deux modèles.
            </li>
            <li>
              <strong>Gain modeste.</strong> Environ{" "}
              {formatDecimal((model.accuracy - elo.accuracy) * 100, 1)} points d&apos;exactitude de
              plus que le Elo : un tiers des matchs restent mal prédits, ce qui est la norme pour le
              tennis masculin.
            </li>
            <li>
              <strong>Un replay sans dynamique.</strong> La chaîne de Markov suppose que chaque
              point est indépendant et que les forces au service restent constantes : la courbe
              reflète le tableau d&apos;affichage, pas l&apos;élan ou la fatigue du jour.
            </li>
            <li>
              <strong>Approximations de la base.</strong> ATP 250 et 500 ne sont pas distingués, la
              moquette est rattachée au dur, la date de chaque match est estimée et les données
              s&apos;arrêtent le {formatDate(dataset.lastDate)}.
            </li>
          </ul>
        </Section>

        <Section id="reproduire" title="Reproduire les résultats">
          <p>
            Tout le code est public sur <a href={REPOSITORY_URL}>GitHub</a>. Un workflow
            hebdomadaire relance le pipeline et met à jour les fichiers publiés si les données ont
            changé.
          </p>
          <pre className={styles.code}>
            <code>{`python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pipeline
cd web && npm ci && npm run dev`}</code>
          </pre>
        </Section>
      </div>
    </div>
  );
}
