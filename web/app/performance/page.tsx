import type { Metadata } from "next";
import Link from "next/link";
import { CalibrationChart } from "@/components/charts/CalibrationChart";
import { ChartFigure, ChartLegend } from "@/components/charts/ChartFigure";
import { CHART_COLORS } from "@/components/charts/theme";
import { YearlyChart } from "@/components/charts/YearlyChart";
import { ComparisonTable } from "@/components/performance/ComparisonTable";
import { MetricsTable } from "@/components/performance/MetricsTable";
import { SegmentsTable } from "@/components/performance/SegmentsTable";
import { Callout, PageIntro, Section } from "@/components/ui/Section";
import tableStyles from "@/components/ui/DataTable.module.css";
import { loadOverview, loadPerformance } from "@/lib/data";
import {
  formatDate,
  formatDecimal,
  formatInteger,
  formatPercent,
  formatSigned,
} from "@/lib/format";
import { comparisonWith, differenceFor, modelReport } from "@/lib/models";
import type { ModelReport, Segment, YearResult } from "@/lib/types";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "Performance du modèle",
  description: "Backtest temporel du modèle LightGBM face à la baseline Elo par surface.",
};

function CalibrationTable({ reports }: { reports: ModelReport[] }) {
  return (
    <table className={tableStyles.table}>
      <thead>
        <tr>
          <th scope="col">Tranche prédite</th>
          {reports.map((report) => (
            <th scope="col" key={report.key} colSpan={2}>
              {report.label}
            </th>
          ))}
        </tr>
        <tr>
          <th scope="col">
            <span className="visually-hidden">Tranche</span>
          </th>
          {reports.flatMap((report) => [
            <th scope="col" key={`${report.key}-p`}>
              Prédit
            </th>,
            <th scope="col" key={`${report.key}-o`}>
              Observé
            </th>,
          ])}
        </tr>
      </thead>
      <tbody>
        {reports[0]?.calibration.map((bin, index) => (
          <tr key={bin.lower}>
            <th scope="row">
              {formatPercent(bin.lower, 0)} – {formatPercent(bin.upper, 0)}
            </th>
            {reports.flatMap((report) => {
              const item = report.calibration[index];
              return [
                <td key={`${report.key}-p`}>{item ? formatPercent(item.predicted) : "—"}</td>,
                <td key={`${report.key}-o`}>{item ? formatPercent(item.observed) : "—"}</td>,
              ];
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function YearlyTable({ years }: { years: YearResult[] }) {
  return (
    <table className={tableStyles.table}>
      <thead>
        <tr>
          <th scope="col">Saison</th>
          <th scope="col">Matchs</th>
          <th scope="col">Exactitude Elo</th>
          <th scope="col">Exactitude LightGBM</th>
          <th scope="col">Log loss Elo</th>
          <th scope="col">Log loss LightGBM</th>
          <th scope="col">Brier Elo</th>
          <th scope="col">Brier LightGBM</th>
        </tr>
      </thead>
      <tbody>
        {years.map((year) => (
          <tr key={year.year}>
            <th scope="row">{year.year}</th>
            <td>{formatInteger(year.matches)}</td>
            <td>{formatPercent(year.elo.accuracy)}</td>
            <td>{formatPercent(year.model.accuracy)}</td>
            <td>{formatDecimal(year.elo.logLoss, 3)}</td>
            <td>{formatDecimal(year.model.logLoss, 3)}</td>
            <td>{formatDecimal(year.elo.brier, 3)}</td>
            <td>{formatDecimal(year.model.brier, 3)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function groupSegments(segments: Segment[]): { title: string; items: Segment[] }[] {
  const groups = new Map<string, Segment[]>();
  for (const segment of segments) {
    groups.set(segment.title, [...(groups.get(segment.title) ?? []), segment]);
  }
  return [...groups.entries()].map(([title, items]) => ({
    title,
    items: [...items].sort((left, right) => right.matches - left.matches),
  }));
}

export default function PerformancePage() {
  const overview = loadOverview();
  const performance = loadPerformance();
  const model = modelReport(performance, "model");
  const elo = modelReport(performance, "elo");
  const recalibrated = modelReport(performance, "elo_recalibrated");
  const versusElo = comparisonWith(performance, "elo");
  const versusRecalibrated = comparisonWith(performance, "elo_recalibrated");
  const test = overview.periods.find((period) => period.name === "test");
  const accuracyGap = differenceFor(versusElo, "accuracy");
  const logLossGap = differenceFor(versusRecalibrated, "logLoss");
  const weakerSegments = performance.segments.filter(
    (segment) => segment.model.accuracy < segment.elo.accuracy,
  );
  const beatsYears = performance.yearly.filter((year) => year.model.logLoss < year.elo.logLoss);
  const seasonSizes = performance.yearly
    .slice(0, -1)
    .map((year) => year.matches)
    .sort((left, right) => left - right);
  const typicalSeason =
    Math.round((seasonSizes[Math.floor(seasonSizes.length / 2)] ?? 0) / 100) * 100;
  const firstYear = performance.yearly[0]?.year;
  const lastYear = performance.yearly.at(-1)?.year;
  const legend = (
    <ChartLegend
      items={[
        { label: model.label, color: CHART_COLORS.model },
        { label: elo.label, color: CHART_COLORS.elo },
      ]}
    />
  );

  return (
    <div className="container">
      <PageIntro eyebrow="Backtest" title="Performance du modèle">
        <p>
          Tous les chiffres de cette page sont calculés sur des matchs que les modèles n&apos;ont
          jamais vus :{" "}
          {test
            ? `${formatInteger(test.matches)} matchs joués du ${formatDate(test.start)} au ${formatDate(test.end)}`
            : "la période de test"}
          . Forfaits et abandons en cours de match sont exclus, car ils ne reflètent pas un résultat
          sportif.
        </p>
      </PageIntro>

      <Section
        id="resultats"
        title="Résultats sur la période de test"
        lead={
          <p>
            LightGBM prédit correctement {formatPercent(model.accuracy)} des matchs, contre{" "}
            {formatPercent(elo.accuracy)} pour le Elo par surface, soit{" "}
            {formatSigned(accuracyGap.mean * 100, 1)} points. Le « Elo recalibré » garde les mêmes
            pronostics que le Elo, mais corrige son excès de confiance à partir des données
            d&apos;entraînement : il isole ce que le modèle apporte au-delà d&apos;une simple
            calibration.
          </p>
        }
      >
        <MetricsTable models={performance.models} />
        <dl className={styles.glossary}>
          <div>
            <dt>Exactitude</dt>
            <dd>Part des matchs où le joueur jugé favori a gagné.</dd>
          </div>
          <div>
            <dt>Log loss</dt>
            <dd>
              Pénalise fortement les erreurs commises avec assurance. Un pile ou face obtient 0,693.
            </dd>
          </div>
          <div>
            <dt>Score de Brier</dt>
            <dd>
              Écart quadratique moyen entre la probabilité annoncée et le résultat. Pile ou face :
              0,25.
            </dd>
          </div>
          <div>
            <dt>Erreur de calibration</dt>
            <dd>Écart moyen entre la probabilité annoncée et la fréquence de victoire observée.</dd>
          </div>
        </dl>
      </Section>

      <Section
        id="significativite"
        title="L'écart est-il significatif ?"
        lead={
          <p>
            Intervalles de confiance à 95 % obtenus par bootstrap apparié (2 000 rééchantillonnages
            des mêmes matchs pour les deux modèles). Un écart est jugé significatif quand son
            intervalle n&apos;inclut pas zéro.
          </p>
        }
      >
        <div className={styles.stack}>
          <ComparisonTable differences={versusElo} referenceLabel={elo.label} />
          <ComparisonTable differences={versusRecalibrated} referenceLabel={recalibrated.label} />
        </div>
        <Callout title="Lecture honnête">
          <p>
            Le gain est réel mais modeste : environ {formatSigned(accuracyGap.mean * 100, 1)} points
            d&apos;exactitude. Une partie de l&apos;amélioration de la log loss vient simplement
            d&apos;une meilleure calibration, puisque le Elo recalibré réduit déjà l&apos;écart.
            Même face à lui, LightGBM reste meilleur ({formatSigned(logLossGap.mean, 3)} de log
            loss) : les variables supplémentaires apportent une information que le Elo seul ne capte
            pas.
          </p>
        </Callout>
      </Section>

      <Section
        id="calibration"
        title="Calibration"
        lead={
          <p>
            Quand un modèle annonce 70 %, le favori doit gagner environ 7 matchs sur 10. Plus les
            points sont proches de la diagonale, mieux le modèle est calibré. Le Elo classique est
            trop sûr de lui : ses favoris gagnent moins souvent qu&apos;annoncé.
          </p>
        }
      >
        <ChartFigure
          title="Courbe de calibration sur la période de test"
          description="Probabilité prédite pour le favori (axe horizontal) contre fréquence de victoire observée (axe vertical), par tranches de 5 points ; la diagonale représente une calibration parfaite."
          legend={legend}
          table={<CalibrationTable reports={[model, elo]} />}
        >
          <CalibrationChart
            title="Courbe de calibration"
            series={[
              {
                key: "model",
                label: model.label,
                color: CHART_COLORS.model,
                bins: model.calibration,
              },
              { key: "elo", label: elo.label, color: CHART_COLORS.elo, bins: elo.calibration },
            ]}
          />
        </ChartFigure>
      </Section>

      <Section
        id="dans-le-temps"
        title="Saison après saison"
        lead={
          <p>
            Backtest glissant de {firstYear} à {lastYear} : chaque saison est prédite par un modèle
            réentraîné uniquement sur les saisons antérieures, avec des hyperparamètres fixés une
            fois pour toutes sur 2005. LightGBM obtient une meilleure log loss que le Elo sur{" "}
            {beatsYears.length} saisons sur {performance.yearly.length}.
          </p>
        }
      >
        <ChartFigure
          title="Performance par saison"
          description={`Comparaison annuelle du Elo et de LightGBM, de ${firstYear} à ${lastYear}. Une saison complète compte environ ${formatInteger(typicalSeason)} matchs, la saison ${lastYear} s'arrête le ${formatDate(overview.dataset.lastDate)} : un écart d'un point d'exactitude d'une année sur l'autre reste dans le bruit statistique.`}
          legend={legend}
          table={<YearlyTable years={performance.yearly} />}
        >
          <YearlyChart years={performance.yearly} labels={{ model: model.label, elo: elo.label }} />
        </ChartFigure>
      </Section>

      <Section
        id="segments"
        title="Où le modèle réussit, où il peine"
        lead={
          <p>
            Découpage de la période de test.
            {weakerSegments.length > 0
              ? ` LightGBM fait moins bien que le Elo en exactitude sur : ${weakerSegments
                  .map((segment) => segment.label)
                  .join(", ")}.`
              : " LightGBM fait au moins aussi bien que le Elo sur chaque segment."}{" "}
            Les petits segments (moins de quelques centaines de matchs) sont très bruités.
          </p>
        }
      >
        <div className={styles.stack}>
          {groupSegments(performance.segments).map((group) => (
            <SegmentsTable key={group.title} title={group.title} segments={group.items} />
          ))}
        </div>
        <p className={styles.more}>
          Les raisons de ces écarts et les limites connues sont détaillées dans la{" "}
          <Link href="/methodologie#limites">méthodologie</Link>.
        </p>
      </Section>
    </div>
  );
}
