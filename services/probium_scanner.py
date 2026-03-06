from dataclasses import dataclass
from services.data_source import get_matches_and_odds
from services.probium_engine import (
    estimate_real_prob,
    calculate_ev,
    calculate_edge,
)


@dataclass
class Bet:

    home: str
    away: str
    market: str
    odd: float
    prob: float
    ev: float
    edge: float
    league: str

    @property
    def score(self):

        return (self.ev * 40) + (self.prob * 40) + (self.edge * 20)


def run_scanner(api_key):

    data = get_matches_and_odds(api_key)

    bets = []

    for item in data:

        odd = item["odd"]

        prob = estimate_real_prob(odd)

        ev = calculate_ev(prob, odd)

        edge = calculate_edge(prob, odd)

        if ev > 0.03 and prob > 0.55:

            bets.append(
                Bet(
                    home=item["home"],
                    away=item["away"],
                    market=item["market"],
                    odd=odd,
                    prob=prob,
                    ev=ev,
                    edge=edge,
                    league=item["league"],
                )
            )

    bets.sort(key=lambda x: x.score, reverse=True)

    return bets[:5]