from dataclasses import dataclass, field

from pipeline.scoring import (
    REGULAR_SET,
    SET_RULES,
    MatchFormat,
    ScoreState,
    SetRule,
    other,
    tiebreak_point_server,
)

SetOutcomes = dict[tuple[int, int], float]


def game_hold_probability(
    serve_win: float, server_points: int = 0, receiver_points: int = 0
) -> float:
    """Probabilité que le serveur gagne le jeu ; à égalité (40-40) : p² / (p² + (1 - p)²)."""
    if server_points >= 4 and server_points - receiver_points >= 2:
        return 1.0
    if receiver_points >= 4 and receiver_points - server_points >= 2:
        return 0.0
    if server_points >= 3 and receiver_points >= 3:
        deuce = serve_win**2 / (serve_win**2 + (1.0 - serve_win) ** 2)
        lead = server_points - receiver_points
        if lead == 0:
            return deuce
        return serve_win + (1.0 - serve_win) * deuce if lead > 0 else serve_win * deuce
    return serve_win * game_hold_probability(serve_win, server_points + 1, receiver_points) + (
        1.0 - serve_win
    ) * game_hold_probability(serve_win, server_points, receiver_points + 1)


def pair_resolution(first_wins_both: float, first_loses_both: float) -> float:
    return first_wins_both / (first_wins_both + first_loses_both)


@dataclass
class MatchModel:
    """Chaîne de Markov hiérarchique point → jeu → set → match (points i.i.d. au service).

    serve_win[i] est la probabilité que le joueur i gagne un point sur son propre service.
    """

    serve_win: tuple[float, float]
    match_format: MatchFormat
    _tiebreaks: dict[tuple[int, int, int, int], float] = field(default_factory=dict)
    _sets: dict[tuple[int, int, int, SetRule], SetOutcomes] = field(default_factory=dict)
    _matches: dict[tuple[int, int, int], float] = field(default_factory=dict)

    def point_probability(self, server: int) -> float:
        return self.serve_win[0] if server == 0 else 1.0 - self.serve_win[1]

    def hold_probability(self, server: int) -> float:
        return game_hold_probability(self.serve_win[server])

    def tiebreak_probability(
        self, points: tuple[int, int], first_server: int, target: int
    ) -> float:
        key = (points[0], points[1], first_server, target)
        if key not in self._tiebreaks:
            self._tiebreaks[key] = self._tiebreak(points, first_server, target)
        return self._tiebreaks[key]

    def _tiebreak(self, points: tuple[int, int], first_server: int, target: int) -> float:
        first, second = points
        if first >= target and first - second >= 2:
            return 1.0
        if second >= target and second - first >= 2:
            return 0.0
        if first == second and first >= target - 1:
            wins_both = self.point_probability(0) * self.point_probability(1)
            loses_both = (1.0 - self.point_probability(0)) * (1.0 - self.point_probability(1))
            return pair_resolution(wins_both, loses_both)
        server = tiebreak_point_server(first_server, first + second)
        win = self.point_probability(server)
        return win * self.tiebreak_probability((first + 1, second), first_server, target) + (
            1.0 - win
        ) * self.tiebreak_probability((first, second + 1), first_server, target)

    def set_outcomes(self, games: tuple[int, int], server: int, rule: SetRule) -> SetOutcomes:
        """Distribution de (vainqueur du set, serveur du premier jeu du set suivant)."""
        key = (games[0], games[1], server, rule)
        if key not in self._sets:
            self._sets[key] = self._set(games, server, rule)
        return self._sets[key]

    def _set(self, games: tuple[int, int], server: int, rule: SetRule) -> SetOutcomes:
        first, second = games
        for player in (0, 1):
            own, opposing = games[player], games[other(player)]
            reached_tiebreak_win = rule.tiebreak_at is not None and own == rule.tiebreak_at + 1
            if (reached_tiebreak_win and opposing == rule.tiebreak_at) or (
                own >= 6 and own - opposing >= 2
            ):
                return {(player, server): 1.0}
        if rule.tiebreak_at is not None and first == second == rule.tiebreak_at:
            won = self.tiebreak_probability((0, 0), server, rule.tiebreak_target)
            return {(0, other(server)): won, (1, other(server)): 1.0 - won}
        if first == second and first >= 5 and rule.tiebreak_at is None:
            return self._advantage_tie(server)
        hold = self.hold_probability(server)
        server_wins = self.set_outcomes(increment(games, server), other(server), rule)
        receiver_wins = self.set_outcomes(increment(games, other(server)), other(server), rule)
        return merge(server_wins, hold, receiver_wins, 1.0 - hold)

    def _advantage_tie(self, server: int) -> SetOutcomes:
        first_game = (
            self.hold_probability(server) if server == 0 else 1.0 - self.hold_probability(1)
        )
        second_server = other(server)
        second_game = (
            self.hold_probability(0) if second_server == 0 else 1.0 - self.hold_probability(1)
        )
        won = pair_resolution(first_game * second_game, (1.0 - first_game) * (1.0 - second_game))
        return {(0, server): won, (1, server): 1.0 - won}

    def rule_for(self, sets: tuple[int, int]) -> SetRule:
        needed = self.match_format.sets_to_win
        if sets[0] == sets[1] == needed - 1:
            return SET_RULES[self.match_format.final_set]
        return REGULAR_SET

    def from_set_start(self, sets: tuple[int, int], server: int) -> float:
        key = (sets[0], sets[1], server)
        if key not in self._matches:
            self._matches[key] = self._from_set_start(sets, server)
        return self._matches[key]

    def _from_set_start(self, sets: tuple[int, int], server: int) -> float:
        needed = self.match_format.sets_to_win
        if sets[0] == needed:
            return 1.0
        if sets[1] == needed:
            return 0.0
        return self.after_set(sets, self.set_outcomes((0, 0), server, self.rule_for(sets)))

    def after_set(self, sets: tuple[int, int], outcomes: SetOutcomes) -> float:
        return sum(
            probability * self.from_set_start(increment(sets, winner), next_server)
            for (winner, next_server), probability in outcomes.items()
        )

    def win_probability(self, state: ScoreState) -> float:
        """Probabilité que le joueur 0 gagne le match depuis un score quelconque."""
        if state.winner is not None:
            return 1.0 if state.winner == 0 else 0.0
        rule = self.rule_for(state.sets)
        if state.tiebreak_server is not None:
            won = self.tiebreak_probability(
                state.points, state.tiebreak_server, rule.tiebreak_target
            )
            next_server = other(state.tiebreak_server)
            outcomes = {(0, next_server): won, (1, next_server): 1.0 - won}
            return self.after_set(state.sets, outcomes)
        server = state.server
        hold = game_hold_probability(
            self.serve_win[server], state.points[server], state.points[other(server)]
        )
        server_wins = self.set_outcomes(increment(state.games, server), other(server), rule)
        receiver_wins = self.set_outcomes(
            increment(state.games, other(server)), other(server), rule
        )
        return self.after_set(state.sets, merge(server_wins, hold, receiver_wins, 1.0 - hold))


def increment(pair: tuple[int, int], player: int) -> tuple[int, int]:
    return (pair[0] + 1, pair[1]) if player == 0 else (pair[0], pair[1] + 1)


def merge(
    first: SetOutcomes, first_weight: float, second: SetOutcomes, second_weight: float
) -> SetOutcomes:
    merged: SetOutcomes = {}
    for outcomes, weight in ((first, first_weight), (second, second_weight)):
        for key, probability in outcomes.items():
            merged[key] = merged.get(key, 0.0) + weight * probability
    return merged


def serve_probabilities_for(
    pre_match_probability: float,
    tour_serve_win: float,
    first_server: int,
    match_format: MatchFormat,
) -> tuple[float, float]:
    """Trouve (μ + d, μ - d) tel que P(victoire à 0-0) égale la probabilité d'avant-match."""
    target = min(max(pre_match_probability, 0.01), 0.99)
    low, high = -0.3, 0.3
    for _ in range(60):
        middle = 0.5 * (low + high)
        model = MatchModel((tour_serve_win + middle, tour_serve_win - middle), match_format)
        if model.win_probability(ScoreState(server=first_server)) < target:
            low = middle
        else:
            high = middle
    spread = 0.5 * (low + high)
    return tour_serve_win + spread, tour_serve_win - spread
