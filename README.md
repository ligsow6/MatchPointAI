# MatchPoint

Prédiction de matchs de tennis ATP : baseline Elo par surface, modèle de gradient boosting évalué sur un backtest temporel strict, et replay point par point de finales historiques.

Documentation complète à venir.

## Jeu de données nettoyé

`python -m pipeline` produit `data/processed/matches.csv.gz` (non versionné), une ligne par match ATP depuis 1968 :

| Colonne | Description |
| --- | --- |
| `match_key` | Identifiant unique `tourney_id-match_num` |
| `tourney_level` | `G` Grand Chelem, `M` Masters 1000, `A` ATP 250/500, `F` Masters de fin d'année, `D` Coupe Davis, `O` Jeux olympiques |
| `tourney_date` | Date de début du tournoi |
| `match_date` | Date estimée du match (début du tournoi + décalage selon le tour) |
| `surface` | `Hard`, `Clay` ou `Grass` (la moquette est rattachée au dur) |
| `round`, `round_order` | Tour et son rang chronologique dans le tableau |
| `best_of` | 3 ou 5 sets |
| `outcome` | `completed`, `retirement` (abandon, disqualification), `walkover` ou `unknown` |
| `winner_*`, `loser_*` | Identifiant, nom, main, taille, âge, classement et points ATP avant le match |
| `w_*`, `l_*` | Points au service, points gagnés sur première et seconde balle |

Règles appliquées : suppression des lignes sans date, au format inconnu (`best_of` différent de 3 ou 5), des matchs d'un joueur contre lui-même et des niveaux hors circuit principal ; tailles hors de 150–215 cm, âges hors de 14–50 ans et classements non positifs remplacés par des valeurs manquantes. Le jeu est rejeté si une date est incohérente, si l'ordre chronologique est rompu ou si un identifiant est dupliqué.
