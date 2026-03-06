import random

from services.data_source import get_matches
from services.elo_engine import elo_probability
from services.probium_engine import calculate_ev, calculate_edge
from services.poisson_model import predict_score, over25_prob, btts_prob
from services.confidence_engine import confidence_level
from services.ranking_engine import rank_bets
from services.history_engine import record_bets
from services.telegram_engine import send_message
from services.historical_engine import HistoricalEngine


engine = HistoricalEngine()


def best_market(prob_home, prob_away, prob_draw, over25, btts):

    markets = []

    markets.append(("HOME WIN", prob_home))
    markets.append(("AWAY WIN", prob_away))
    markets.append(("DRAW", prob_draw))

    markets.append(("OVER 2.5", over25))
    markets.append(("UNDER 2.5", 1 - over25))

    markets.append(("BTTS YES", btts))
    markets.append(("BTTS NO", 1 - btts))

    best = None
    best_ev = -999

    for name, prob in markets:

        odd = round((1 / prob) * random.uniform(1.05, 1.12), 2)

        ev = calculate_ev(prob, odd)

        if ev > best_ev:

            best_ev = ev
            best = (name, prob, odd, ev)

    return best


def run_pipeline():

    matches = get_matches()

    bets = []

    for m in matches:

        elo_prob = elo_probability(
            m["elo_home"],
            m["elo_away"]
        )

        poisson = over25_prob()

        prob_home = engine.combined_probability(
            elo_prob,
            poisson,
            m["home"],
            m["away"]
        )

        prob_away = 1 - prob_home

        prob_draw = 0.25

        score = predict_score(
            m["elo_home"],
            m["elo_away"]
        )

        over25 = over25_prob()

        btts = btts_prob()

        market, prob, odd, ev = best_market(
            prob_home,
            prob_away,
            prob_draw,
            over25,
            btts
        )

        edge = calculate_edge(prob, odd)

        if prob < 0.55 or ev < 0.02:
            continue

        conf, stake = confidence_level(prob, ev)

        bets.append({

            "home": m["home"],
            "away": m["away"],
            "league": m["league"],
            "kickoff": m["kickoff"],

            "market": market,

            "odd": odd,
            "prob": prob,
            "ev": ev,
            "edge": edge,

            "score": f"{score[0]}-{score[1]}",
            "over25": over25,
            "btts": btts,

            "confidence": conf,
            "stake": stake

        })

    ranked = rank_bets(bets)

    top = ranked[:5]

    record_bets(top)

    send_message(top)

    return top