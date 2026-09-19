import type { Replay } from "@/lib/types";
import type { ScoreSnapshot } from "./replayState";
import { PLAYER_COLORS } from "./ReplayChart";
import styles from "./ReplayPlayer.module.css";

type ScoreboardProps = { replay: Replay; snapshot: ScoreSnapshot };

export function Scoreboard({ replay, snapshot }: ScoreboardProps) {
  const players = [0, 1] as const;
  const showCurrentSet = !snapshot.finished;
  return (
    <table className={styles.scoreboard}>
      <caption className="visually-hidden">Tableau d&apos;affichage</caption>
      <thead>
        <tr>
          <th scope="col">
            <span className="visually-hidden">Joueur</span>
          </th>
          {snapshot.completedSets.map((_, index) => (
            <th scope="col" key={index}>
              <span aria-hidden="true">S{index + 1}</span>
              <span className="visually-hidden">Set {index + 1}</span>
            </th>
          ))}
          {showCurrentSet ? (
            <>
              <th scope="col">
                <span aria-hidden="true">S{snapshot.completedSets.length + 1}</span>
                <span className="visually-hidden">Set en cours</span>
              </th>
              <th scope="col">{snapshot.tiebreak ? "TB" : "Pts"}</th>
            </>
          ) : null}
        </tr>
      </thead>
      <tbody>
        {players.map((player) => {
          const serving = snapshot.nextServer === player;
          const won = snapshot.finished && replay.winner === player;
          return (
            <tr key={player}>
              <th scope="row">
                <span className={styles.playerCell}>
                  <span
                    className={styles.swatch}
                    style={{ background: PLAYER_COLORS[player] }}
                    aria-hidden="true"
                  />
                  <span className={styles.playerName}>
                    <span className={styles.fullName}>{replay.players[player]}</span>
                    <span className={styles.shortName}>{replay.shortNames[player]}</span>
                  </span>
                  {serving ? (
                    <span className={styles.serve}>
                      <span aria-hidden="true">●</span>
                      <span className="visually-hidden">au service</span>
                    </span>
                  ) : null}
                  {won ? <span className={styles.winnerTag}>Vainqueur</span> : null}
                </span>
              </th>
              {snapshot.completedSets.map((games, index) => {
                const tiebreak = replay.tiebreaks[index];
                const setWon = games[player] > games[player === 0 ? 1 : 0];
                return (
                  <td key={index} className={setWon ? styles.setWon : styles.setLost}>
                    {games[player]}
                    {tiebreak && !setWon ? <sup>{tiebreak[player]}</sup> : null}
                  </td>
                );
              })}
              {showCurrentSet ? (
                <>
                  <td className={styles.currentSet}>{snapshot.games[player]}</td>
                  <td className={styles.points}>{snapshot.points[player]}</td>
                </>
              ) : null}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
