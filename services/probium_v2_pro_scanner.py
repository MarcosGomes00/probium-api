from dataclasses import dataclass
from services.flashscore_scraper import get_today_matches
from services.oddsportal_scraper import get_odds


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


def implied_prob(odd):

    return 1 / odd


def estimate_prob(odd):

    return implied_prob(odd) * 1.05


def analyze_match(match, odds):

    bets = []

    for game in odds:

        if game["home"] != match["home"]:
            continue

        odd = game["odd"]

        prob = estimate_prob(odd)

        ev = (prob * odd) - 1

        edge = prob - implied_prob(odd)

        if ev > 0.03 and prob > 0.55:

            bets.append(Bet(
                home=match["home"],
                away=match["away"],
                market="1",
                odd=odd,
                prob=prob,
                ev=ev,
                edge=edge,
                league=match["league"]
            ))

    return bets


def run_probium_v2_pro():

    matches = get_today_matches()

    odds = get_odds()

    all_bets = []

    for match in matches:

        bets = analyze_match(match, odds)

        all_bets.extend(bets)

    all_bets.sort(key=lambda x: x.score, reverse=True)

    return all_bets[:5]