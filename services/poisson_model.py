import random

def expected_goals(elo_home, elo_away):

    diff = elo_home - elo_away

    home = 1.4 + (diff / 400)
    away = 1.2 - (diff / 400)

    home = max(0.4, home)
    away = max(0.3, away)

    return home, away


def predict_score(elo_home, elo_away):

    h,a = expected_goals(elo_home, elo_away)

    return round(h), round(a)


def over25_prob():

    return random.uniform(0.45,0.70)


def btts_prob():

    return random.uniform(0.45,0.70)