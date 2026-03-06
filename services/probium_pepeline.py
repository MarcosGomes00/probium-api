import random

from services.data_source import get_matches
from services.elo_engine import elo_probability
from services.probium_engine import calculate_ev, calculate_edge
from services.poisson_model import predict_score, over25_prob, btts_prob
from services.ranking_engine import rank_bets
from services.form_engine import adjust_probability


def run_pipeline():

    matches = get_matches()

    bets = []

    for match in matches:

        base_prob = elo_probability(match["elo_home"], match["elo_away"])

        prob = adjust_probability(base_prob)

        odd = round((1 / prob) * random.uniform(1.05, 1.10), 2)

        ev = calculate_ev(prob, odd)

        edge = calculate_edge(prob, odd)

        if prob >= 0.55 and ev >= 0.01:

            score = predict_score(match["elo_home"], match["elo_away"])

            bets.append({
                "home": match["home"],
                "away": match["away"],
                "league": match["league"],
                "kickoff": match["kickoff"],
                "odd": odd,
                "prob": prob,
                "ev": ev,
                "edge": edge,
                "score": f"{score[0]}-{score[1]}",
                "over25": over25_prob(),
                "btts": btts_prob()
            })

    ranked = rank_bets(bets)

    return ranked[:5]