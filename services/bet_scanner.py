from dataclasses import dataclass
from services.data_source import get_matches_and_odds
from services.probium_engine import (
    estimate_real_prob,
    calculate_ev,
    calculate_edge
)


@dataclass
class Bet:

    home: str
    away: str
    market: str
    prob: float
    odd: float
    ev: float
    edge: float
    league: str

    @property
    def score(self):

        return (self.ev * 40) + (self.prob * 40) + (self.edge * 20)


def run_scanner():

    data = get_matches_and_odds()

    bets = []

    for item in data:

        odd = item["odd"]

        prob = estimate_real_prob(odd)

        ev = calculate_ev(prob, odd)

        edge = calculate_edge(prob, odd)

        # filtros profissionais
        if prob >= 0.55 and ev >= 0.01 and edge >= 0.01:

            bets.append(
                Bet(
                    home=item["home"],
                    away=item["away"],
                    market=item["market"],
                    prob=prob,
                    odd=odd,
                    ev=ev,
                    edge=edge,
                    league=item["league"],
                )
            )

    bets.sort(key=lambda x: x.score, reverse=True)

    return bets[:5]